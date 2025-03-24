from process_binaries import consolidate_acquisition
import logging
from config import load_config
import time
import sys
import logging
from pathlib import Path
from typing import Set, Union
import re
from run_number import find_file_by_run_number, extract_run_number, get_all_run_numbers, get_next_run_number
import time
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from config import load_config
from plots import etroc_hitmaps_generator, MCP_trace_generator, Clock_trace_generator
import subprocess
import shutil

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
                    datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger("plots")
logging.getLogger("process_binaries")
logging.getLogger("run_number")

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
    logging.info(f"######    DAQ ON RUN     ######")
    logging.info(f"######      {run_number}       ######")
    logging.info(f"###############################")
    print("\n")

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
        file_path = Path(event.src_path)
        if not file_path.exists():
            logging.debug(f"Probably merged file was already created so this file has been moved: {file_path}")
            return
        if file_path.is_dir():
            logging.warning(f"File path is a directory. {file_path}")
            return
        
        etroc_regs = [ETROC_FILENAME_REGEX_FUNC(rb) for rb in TB_CONFIG.telescope_config.rbs]
        scope_regs = [CLOCK_FILENAME_REGEX, MCP_FILENAME_REGEX]

        ##################### Get run number from event
        event_run_number = None
        for reg_exp in etroc_regs + scope_regs:
            event_run_number = extract_run_number(file_path, reg_exp, force_file_exist=False)
            if event_run_number is not None:
                break
        if event_run_number is None:
            logging.warning(f"UNABLE TO MATCH RUN RUMBER FOR: {file_path}")
            return
        merged_path = CONFIG.final_merged_dir / MERGED_FILENAME(event_run_number)
        if merged_path.exists():
            print("HEYEYEHEHEYEH=========================")
            return
        ##################################################################################
        # Check if we have all required binaries: etroc(s), mcp and clock
        found_etroc_runs = [
            find_file_by_run_number(ETROC_BINARY_DIR, event_run_number, reg) for reg in etroc_regs
        ]
        found_mcp_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, MCP_FILENAME_REGEX)
        found_clock_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, CLOCK_FILENAME_REGEX)

        # Need all required binaries
        num_found_files = 0
        num_found_files += len([i for i in found_etroc_runs if i is not None]) 
        num_found_files += 1 if found_mcp_run else 0
        num_found_files += 1 if found_clock_run else 0
        num_needed_files = len(found_etroc_runs) + 2
        logging.info(
            f"[MERGE PROGRESS {num_found_files}/{num_needed_files}]: EVENT TRIGGERED BY {file_path.name}"
        )
        if None in found_etroc_runs or found_mcp_run is None or found_clock_run is None:
            return
        ##################################################################################
        run_log = get_run_log(event_run_number)
        if run_log is None:
            logging.error(f"NOT MERGING RUN {event_run_number}: Run log not found")
            return
        ##################################################################################
        consolidate_acquisition(
            CONFIG.final_merged_dir / MERGED_FILENAME(event_run_number),
            etroc_binary_paths=list(map(str, found_etroc_runs)),
            mcp_binary_path=str(found_mcp_run),
            clock_binary_path=str(found_clock_run),
            run_log_path=run_log
        )
        logging.info(f"[MERGED ✅] {CONFIG.final_merged_dir.name}")
        ##################################################################################

        # Doing this here because using another watchdog might be more dangerous!
        for etroc_path in found_etroc_runs:
            shutil.move(
                str(etroc_path),
                str(CONFIG.final_etroc_binary_dir)
            )
        shutil.move(str(found_mcp_run), str(CONFIG.final_scope_binary_dir))
        shutil.move(str(found_clock_run), str(CONFIG.final_scope_binary_dir))


class BackupWatcherHandler(FileSystemEventHandler):
    def on_created(self, event):
        file_path = Path(event.src_path)
        logging.info(f"[ARCHIVED ✅]: {file_path.name}")


class NewRunNumberHandler(FileSystemEventHandler):
    def on_closed(self, event):
        if str(RUN_NUMBER_PATH) != event.src_path:
            return 
        run_number = get_next_run_number(Path(event.src_path))
        if run_number is None:
            return
        print_run_number(run_number)

class ConfigUpdateHandler(FileSystemEventHandler):
    def __init__(self, observer):
        super(ConfigUpdateHandler).__init__()
        self.observer = observer

    def on_modified(self, event):
        logging.critical("Config updated, EXITING WATCHDOG!")
        subprocess.Popen(['notify-send', "ETL TB - CRITICAL - Config was updated, exiting watchdog"])
        self.observer.stop()
        
        # Just exit the watchdog with a big explanation
        # The config has changed please rerun the watchdog in order to load the new config
        # do this on file changes, or if new active config

if __name__ == "__main__":
    pc_observer = Observer()
    polling_observer = PollingObserver()

    etroc_hitmaps_handler = EtrocHitMapsHandler()
    clock_plots_handler = ClockPlotsHandler()
    mcp_plots_handler = McpPlotsHandler()
    merge_to_root_handler = MergeToRootHandler()
    new_run_number_handler = NewRunNumberHandler()

    # Display User the unmerged runs
    logging.info("========= UNMERGED RUNS =========")
    logging.info(
        sorted(get_unmerged_runs(CONFIG.final_merged_dir)))
    logging.info("=================================\n")

    pc_observer.schedule(merge_to_root_handler, ETROC_BINARY_DIR)
    polling_observer.schedule(merge_to_root_handler, SCOPE_BINARY_DIR)

    polling_observer.schedule(BackupWatcherHandler(), CONFIG.final_archive_directory, 
                              recursive=True)


    # pc_observer.schedule(etroc_hitmaps_handler,  CONFIG.final_merged_dir)
    # pc_observer.schedule(clock_plots_handler,    CONFIG.final_scope_binary_dir)
    # pc_observer.schedule(mcp_plots_handler,      CONFIG.final_scope_binary_dir)
    pc_observer.schedule(new_run_number_handler, RUN_NUMBER_PATH.parent)

    pc_observer.schedule(
        ConfigUpdateHandler(observer=pc_observer), 
        TB_CONFIG.test_beam.project_directory / Path("configs/active_config/"))
    
    pc_observer.start()
    polling_observer.start()
    logging.info(f"🐶 Watchdog is now monitoring directories...")

    # print the first run number
    run_number = get_next_run_number(RUN_NUMBER_PATH)
    if run_number is None:
        raise ValueError(f"Run number was not found at {run_number}")
    print_run_number(run_number)

    try: # thx watchdog documentation
        while pc_observer.is_alive():
            pc_observer.join(1)
    finally:
        pc_observer.stop()
        pc_observer.join()
        polling_observer.stop()
        polling_observer.join()