import logging
from os import environ
from pathlib import Path
import re
import shutil
import subprocess
from typing import Set, Union, List

from config import load_config
from plots import Clock_trace_generator, MCP_trace_generator, etroc_hitmaps_generator, TBplot
from process_binaries import consolidate_acquisition
from run_number import (extract_run_number, find_file_by_run_number, 
                        get_all_run_numbers)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from cernbox_api import CERNBoxAPI
from rich.logging import RichHandler
import time

TB_CONFIG = load_config()
CONFIG = TB_CONFIG.watchdog
# Dirs n Paths
ETROC_BINARY_DIR = TB_CONFIG.telescope_config.etroc_binary_data_directory
SCOPE_BINARY_DIR =  TB_CONFIG.oscilloscope.binary_data_directory
RUN_NUMBER_PATH = TB_CONFIG.test_beam.project_directory / 'daq/static/next_run_number.txt'

# Regular Expressions / File matching
SCOPE_TRC_FILE_REGEX = r"C(\d+)--Trace(\d+).trc"
MCP_FILENAME_REGEX = rf"C{TB_CONFIG.oscilloscope.mcp_channel_number}--Trace(\d+).trc"
CLOCK_FILENAME_REGEX = rf"C{TB_CONFIG.oscilloscope.clock_channel_number}--Trace(\d+).trc"
MERGED_FILENAME_REGEX = r"run_(\d+).root"
MERGED_FILENAME = lambda run_number: f"run_{run_number}.root"
ETROC_FILENAME_REGEX_FUNC = lambda rb: rf"output_run_(\d+)_rb{rb}.dat"
RUN_LOG_REGEX = r"runs_(\d+)_(\d+).json"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    handlers=[RichHandler()])
logging.getLogger("plots").setLevel(logging.INFO)
logging.getLogger("process_binaries").setLevel(logging.INFO)
logging.getLogger("run_number").setLevel(logging.INFO)

def get_run_log(run_number:int) -> Union[Path, None]:
    for run_log_path in TB_CONFIG.run_config.run_log_directory.iterdir():
        run_log_match = re.match(RUN_LOG_REGEX, run_log_path.name)
        if not run_log_match:
            continue
        run_start, run_stop = map(int, run_log_match.groups())
        num_runs = TB_CONFIG.run_config.num_runs
        if run_start <= run_number <= run_stop and (num_runs - 1) == (run_stop-run_start):
            return run_log_path 
        else:
            logging.debug(f"Run log not found by checking: \
                            {run_start=}<={run_number=}<={run_stop} and {num_runs=}-1 == ({run_start-run_stop})")           

def get_unmerged_runs(merged_root_dir: Path) -> Set:
    """
    Finds unmerged runs by comparing run numbers between trace files and etroc binaries
    """
    merged_runs = get_all_run_numbers(
        merged_root_dir,
        MERGED_FILENAME_REGEX
    )

    all_runs = set()
    all_runs |= get_all_run_numbers(SCOPE_BINARY_DIR, MCP_FILENAME_REGEX)
    all_runs |= get_all_run_numbers(SCOPE_BINARY_DIR, CLOCK_FILENAME_REGEX)

    etroc_runs = set()
    for rb in TB_CONFIG.telescope_config.rbs:
        # need to use "&" bec if there were any runs with not all rbs binary data
        etroc_runs &= get_all_run_numbers(
            ETROC_BINARY_DIR, ETROC_FILENAME_REGEX_FUNC(rb))
    all_runs |= etroc_runs
    return all_runs - merged_runs


def print_run_number(run_number: int) -> None:
    print("\n")
    logging.info(f"###############################")
    logging.info(f"######     MERGING RUN   ######")
    logging.info(f"######        {run_number}     ######")
    logging.info(f"###############################")
    print("\n")

def extract_event_run_number(file_path, reg_expressions: List[str]) -> Union[int, None]:
    """Extracts run number from file path, returning first match in the reg expressions"""
    for reg_exp in reg_expressions:
        event_run_number = extract_run_number(file_path, reg_exp, force_file_exist=False)
        if event_run_number is not None:
            return event_run_number
        
def upload_to_cernbox(merged_path: Path, etroc_binaries: List[Path], mcp_binary: Path, clock_binary: Path) -> None:
    start = time.perf_counter()
    cernbox = CERNBoxAPI()
    remote_base = Path(CONFIG.final_archive_directory.name)
    cernbox.upload(
        remote_dir=remote_base / CONFIG.final_merged_dir.name,
        local_path=merged_path
    )
    for etroc_path in etroc_binaries:
        cernbox.upload(
            remote_dir=remote_base / CONFIG.final_etroc_binary_dir.name,
            local_path=etroc_path
        )
    cernbox.upload(
        remote_dir=remote_base / CONFIG.final_scope_binary_dir.name,
        local_path=mcp_binary
    )
    cernbox.upload(
        remote_dir=remote_base / CONFIG.final_scope_binary_dir.name,
        local_path=clock_binary
    )
    logging.info(f"[CERNBOX] Uploads took {time.perf_counter()-start}s")

############################################################################################
############################# WATCHDOG EVENT HANDLERS ######################################
############################################################################################

class EtrocHitMapsHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.src_path.endswith(".dat"):
            return 
        logging.info(f'[ETROC HIT MAP] ETROC Binary {Path(event.src_path).name} has been created')

        file_path = Path(event.src_path)
        try:
            # Generate hitmap
            output_file = etroc_hitmaps_generator(file_path, CONFIG.etroc_hitmap_dir)
            logging.info(f"[ETROC HITMAP] {output_file.name}")
        except Exception as e:
            # daq_stream.py writes multiple times to the etroc binary file 
            # which causes this to fire prematurely.
            return
class ClockPlotsHandler(FileSystemEventHandler):
    def on_created(self, event):
        file_path = Path(event.src_path)
        match = re.match(SCOPE_TRC_FILE_REGEX, file_path.name)
        if not match or match.group(1) != str(TB_CONFIG.oscilloscope.clock_channel_number):
            return

        try:
            output_file = Clock_trace_generator(file_path, CONFIG.clock_plots_dir, match.group(2))
            logging.info(f'[CLOCK PLOT] {output_file.name}')
        except Exception as e:
            logging.error(f"Failed to generate CLOCK traces plot for {file_path.name}: {e}")

class McpPlotsHandler(FileSystemEventHandler):
    def on_created(self, event):
        file_path = Path(event.src_path)
        match = re.match(SCOPE_TRC_FILE_REGEX, file_path.name)
        if not match or match.group(1) != str(TB_CONFIG.oscilloscope.mcp_channel_number):
            return

        try:
            output_file = MCP_trace_generator(file_path, CONFIG.mcp_plots_dir, match.group(2))
            logging.info(f'[MCP PLOT] {output_file.name}')
        except Exception as e:
            logging.error(f"Failed to generate MCP traces plot for {file_path.name}: {e}")

class MergeToRootHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith(".yaml"):
            logging.info(f"DAQ made internal log at {event.src_path}")
            return
        event_file_path = Path(event.src_path)
        if not event_file_path.exists():
            logging.debug(f"Probably merged file was already created so this file has been moved: {event_file_path}")
            return
        if event_file_path.is_dir():
            logging.warning(f"File path is a directory. {event_file_path}")
            return
        
        etroc_regs = [ETROC_FILENAME_REGEX_FUNC(rb) for rb in TB_CONFIG.telescope_config.rbs]
        scope_regs = [CLOCK_FILENAME_REGEX, MCP_FILENAME_REGEX]

        ##################### Get run number from event
        event_run_number = extract_event_run_number(event_file_path, etroc_regs+scope_regs)
        if event_run_number is None:
            logging.warning(f"UNABLE TO MATCH RUN RUMBER FOR: {event_file_path}")
            return
        merged_path = CONFIG.final_merged_dir / MERGED_FILENAME(event_run_number)

        if merged_path.exists():
            return
        ###################### Check we have all binary files
        # Check if we have all required binaries: etroc(s), mcp and clock
        found_etroc_binaries = [find_file_by_run_number(ETROC_BINARY_DIR, event_run_number, reg) 
                                for reg in etroc_regs]
        found_mcp_binary   = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, MCP_FILENAME_REGEX)
        found_clock_binary = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, CLOCK_FILENAME_REGEX)

        found_binaries = found_etroc_binaries + [found_mcp_binary] + [found_clock_binary]
        num_found_files = len([i for i in found_binaries if i is not None])
        num_needed_files = len(found_binaries)
        logging.info(
            f"[MERGE PROGRESS {num_found_files}/{num_needed_files}]: EVENT TRIGGERED BY {event_file_path.name}"
        )
        if not all(found_binaries):
            return
        
        ######################### Get Run log
        run_log = get_run_log(event_run_number)
        if run_log is None:
            logging.error(f"NOT MERGING RUN {event_run_number}: Run log not found")
            return
        
        logging.info(print_run_number(event_run_number))

        ##################################################################################
        merged_path = CONFIG.final_merged_dir / MERGED_FILENAME(event_run_number)
        consolidate_acquisition(
            merged_path,
            etroc_binary_paths=list(map(str, found_etroc_binaries)),
            mcp_binary_path=str(found_mcp_binary),
            clock_binary_path=str(found_clock_binary),
            run_log_path=run_log
        )
        ##################################################################################
        try:
            upload_to_cernbox(
                merged_path,
                found_etroc_binaries,
                found_mcp_binary,
                found_clock_binary
            )
        except Exception as e:
            logging.error(f"CERNBOX upload failed due to an exception: {e}")
        #################################################################################
        # Doing this here because using another watchdog might be more dangerous!
        for etroc_path in found_etroc_binaries:
            shutil.move(
                str(etroc_path),
                str(CONFIG.final_etroc_binary_dir)
            )
        shutil.move(str(found_mcp_binary), str(CONFIG.final_scope_binary_dir))
        shutil.move(str(found_clock_binary), str(CONFIG.final_scope_binary_dir))

class ArchiveWatcherHandler(FileSystemEventHandler):
    def on_created(self, event):
        file_path = Path(event.src_path)
        logging.info(f"[ARCHIVED 💿]: {file_path.name}")

        # expression = re.compile(MERGED_FILENAME_REGEX)
        # if expression.match(file_path.name):
        #     root_plot = TBplot(file_path)
        #     root_plot.etroc_hitmap(output_directory=TB_CONFIG.watchdog.etroc_hitmap_dir)

class ConfigUpdateHandler(FileSystemEventHandler):
    def __init__(self, observer):
        super(ConfigUpdateHandler).__init__()
        self.observer = observer

    def on_modified(self, event):
        logging.critical("Config updated, EXITING WATCHDOG!")
        subprocess.Popen(['notify-send', "ETL TB - CRITICAL - Config was updated, exiting watchdog"])
        self.observer.stop()

if __name__ == "__main__":
    pc_observer = Observer()
    polling_observer = PollingObserver()

    etroc_hitmaps_handler = EtrocHitMapsHandler()
    clock_plots_handler = ClockPlotsHandler()
    mcp_plots_handler = McpPlotsHandler()
    merge_to_root_handler = MergeToRootHandler()

    # Display User the unmerged runs
    logging.info("========= UNMERGED RUNS =========")
    logging.info(
        sorted(get_unmerged_runs(CONFIG.final_merged_dir)))
    logging.info("=================================\n")

    pc_observer.schedule(merge_to_root_handler, ETROC_BINARY_DIR)
    polling_observer.schedule(merge_to_root_handler, SCOPE_BINARY_DIR)

    polling_observer.schedule(ArchiveWatcherHandler(), CONFIG.final_archive_directory, 
                              recursive=True)

    # Add both from chipid and from binary? Probably actually
    # pc_observer.schedule(etroc_hitmaps_handler,  CONFIG.final_merged_dir)
    # pc_observer.schedule(clock_plots_handler,    CONFIG.final_scope_binary_dir)
    # pc_observer.schedule(mcp_plots_handler,      CONFIG.final_scope_binary_dir)

    pc_observer.schedule(
        ConfigUpdateHandler(observer=pc_observer), 
        TB_CONFIG.test_beam.project_directory / Path("configs/active_config/"))
    
    logging.info(f"""
--------- CONFIG DIRECTORIES ---------
ETROC BINARIES = {ETROC_BINARY_DIR}
SCOPE BINARIES = {SCOPE_BINARY_DIR}
ARCHIVE        = {CONFIG.final_archive_directory}
------------------------------------------                 
""")
    
    pc_observer.start()
    polling_observer.start()
    logging.info(f"🐶 Watchdog is now monitoring directories...")

    try: # thx watchdog documentation
        while pc_observer.is_alive():
            pc_observer.join(1)
    finally:
        pc_observer.stop()
        pc_observer.join()
        polling_observer.stop()
        polling_observer.join()