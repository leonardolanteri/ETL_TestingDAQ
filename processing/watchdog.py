from process_binaries import consolidate_acquisition
import logging
from config import load_config
import time
import sys
import logging
from pathlib import Path
from typing import Set, Union
import re
from run_number import find_file_by_run_number, extract_run_number, get_all_run_numbers
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from config import load_config
from plots import etroc_hitmaps_generator, MCP_trace_generator, Clock_trace_generator

TB_CONFIG = load_config()
ETROC_BINARY_DIR = TB_CONFIG.telescope_config.etroc_binary_data_directory
SCOPE_BINARY_DIR =  TB_CONFIG.oscilloscope.binary_data_directory
BASE_DIR = TB_CONFIG.watchdog.base_directory
RUN_NUMBER_PATH = TB_CONFIG.test_beam.project_directory/Path('daq/static/next_run_number.txt')
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

def create_output_dir(handler) -> Path:
    """
    Creates output dir for handler, if it already exists it does nothing
    """
    if not hasattr(handler, "output_dirname"):
        raise AttributeError("Handler does not have the output_dirname defined")
    output_path =  BASE_DIR / Path(handler.output_dirname)
    output_path.mkdir(exist_ok=True) # throws error if parents dont exists :)
    return output_path

def get_run_log(run_number:int) -> Union[Path, None]:
    for run_log_path in TB_CONFIG.run_config.run_log_directory.iterdir():
        run_log_match = re.match(RUN_LOG_REGEX, run_log_path.name)
        if not run_log_match:
            continue
        run_start, run_stop = map(int, run_log_match.groups())
        print(run_start, run_stop)
        print(TB_CONFIG.run_config.num_runs)
        if run_start < run_number < run_stop and (TB_CONFIG.run_config.num_runs - 1) == (run_stop-run_start) :
            return run_log_path

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

############################################################################################
############################# WATCHDOG EVENT HANDLERS ######################################
############################################################################################

class EtrocHitMapsHandler(FileSystemEventHandler):
    output_dirname = "etroc_hitmaps"
    # def __init__(self, *args, **kwargs):
    #     super(EtrocHitMapsHandler, self).__init__(*args, **kwargs)
    def on_created(self, event):
        if not event.src_path.endswith(".dat"):
            return 
        
        logging.info(f'[ETROC HIT MAP] ETROC Binary at {event.src_path} has been created')
        file_path = Path(event.src_path)
        output_dir = create_output_dir(self)
        try:
            # Generate hitmap
            etroc_hitmaps_generator(file_path, output_dir)
        except Exception as e:
            logging.error(f"Failed to generate hitmap for {file_path}: {e}")
    
class ClockPlotsHandler(FileSystemEventHandler):
    output_dirname = "clock_plots"

    def on_created(self, event):
        file_path = Path(event.src_path)
        match = re.match(SCOPE_TRC_FILE_REGEX, file_path.name)
        if not match or match.group(1) != str(TB_CONFIG.oscilloscope.clock_channel_number):
            return

        logging.info(f'[CLOCK PLOT] Scope Clock Trace file at {event.src_path} has been created')
        output_dir = create_output_dir(self)
        try:
            Clock_trace_generator(file_path, output_dir, match.group(2))
        except Exception as e:
            logging.error(f"Failed to generate CLOCK traces plot for {file_path}: {e}")

class McpPlotsHandler(FileSystemEventHandler):
    output_dirname = "mcp_plots"

    def on_created(self, event):
        file_path = Path(event.src_path)
        match = re.match(SCOPE_TRC_FILE_REGEX, file_path.name)
        if not match or match.group(1) != str(TB_CONFIG.oscilloscope.mcp_channel_number):
            return

        logging.info(f'[MCP PLOT] Scope MCP Trace file at {event.src_path} has been created')
        output_dir = create_output_dir(self)
        try:
            MCP_trace_generator(file_path, output_dir, match.group(2))
        except Exception as e:
            logging.error(f"Failed to generate MCP traces plot for {file_path}: {e}")

class ConfigUpdateHandler(FileSystemEventHandler):
    def on_modified(self, event):
        logging.critical("Config updated, EXITING WATCHDOG!")
        sys.exit("boomshackalacka")
        # Just exit the watchdog with a big explanation
        # The config has changed please rerun the watchdog in order to load the new config
        # do this on file changes, or if new active config

class MergeToRootHandler(FileSystemEventHandler):
    output_dirname = 'merged_root'

    def on_created(self, event):
        etroc_regs = [ETROC_FILENAME_REGEX_FUNC(rb) for rb in TB_CONFIG.telescope_config.rbs]
        scope_regs = [CLOCK_FILENAME_REGEX, MCP_FILENAME_REGEX]

        # Get run number from event
        event_run_number = None
        for reg_exp in etroc_regs + scope_regs:
            event_run_number = extract_run_number(Path(event.src_path), reg_exp)
            if event_run_number is not None:
                break
        if event_run_number is None:
            logging.warning(f"Did not find event run number for this file path: {event.src_path}")
            return

        # Check if we have all required binaries: etroc(s), mcp and clock
        found_etroc_runs = [
            find_file_by_run_number(ETROC_BINARY_DIR, event_run_number, reg) for reg in etroc_regs
        ]
        found_mcp_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, MCP_FILENAME_REGEX)
        found_clock_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, CLOCK_FILENAME_REGEX)
        if None in found_etroc_runs or found_mcp_run is None or found_clock_run is None:
            # Need all required binaries
            return

        run_log = get_run_log(event_run_number)
        if run_log is None:
            logging.error(f"NOT MERGING RUN {event_run_number}: Run log not found")
            return

        logging.info(f'[MERGED ROOT FILE] Creating merged root file at {event.src_path}')
        merged_path = create_output_dir(self) / Path(MERGED_FILENAME(event_run_number))
        consolidate_acquisition(
            merged_path,
            etroc_binary_paths=list(map(str, found_etroc_runs)),
            mcp_binary_path=str(found_mcp_run),
            clock_binary_path=str(found_clock_run),
            run_log_path=run_log
        )
        logging.info(f"Finished merging {event_run_number} at {merged_path}")

class DataBackupHandler(FileSystemEventHandler):
    def on_created(self, event):
        logging.info("Merged root file made, attempting backup store of binaries and root file")

if __name__ == "__main__":
    observer = Observer()

    etroc_hitmaps_handler = EtrocHitMapsHandler()
    clock_plots_handler = ClockPlotsHandler()
    mcp_plots_handler = McpPlotsHandler()
    merge_to_root_handler = MergeToRootHandler()
    processing_handlers = [
        (etroc_hitmaps_handler, ETROC_BINARY_DIR),
        (clock_plots_handler,   SCOPE_BINARY_DIR),
        (mcp_plots_handler,     SCOPE_BINARY_DIR),
        (merge_to_root_handler, SCOPE_BINARY_DIR),
        (merge_to_root_handler, ETROC_BINARY_DIR)
    ]
    merged_root_dir = BASE_DIR/Path(merge_to_root_handler.output_dirname)
    # Display User the unmerged runs
    logging.info("========= UNMERGED RUNS =========")
    logging.info(
        sorted(get_unmerged_runs(merged_root_dir)))
    logging.info("=================================\n")

    for handler, directory in processing_handlers:
        # Make watchdog dirs if they do not exist
        # Needed to create the folders directly in the handlers
        #create_output_dir(handler)
        observer.schedule(handler, directory)

    observer.schedule(DataBackupHandler(), merged_root_dir)

    observer.schedule(
        ConfigUpdateHandler(), 
        TB_CONFIG.test_beam.project_directory / Path("configs/active_config/"))
    
    observer.start()
    logging.info(f"🐶 Watchdog is now monitoring directories...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()