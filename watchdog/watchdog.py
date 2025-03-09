import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from config import load_config
import logging
from pathlib import Path
from typing import Set, Union
import re
import sys

TB_CONFIG = load_config()
ETROC_BINARY_DIR = TB_CONFIG.telescope_config.etroc_binary_data_directory
SCOPE_BINARY_DIR =  TB_CONFIG.oscilloscope.binary_data_directory
BASE_DIR = TB_CONFIG.watchdog.base_directory
RUN_NUMBER_PATH = TB_CONFIG.test_beam.project_directory/Path('daq/static/next_run_number.txt')
MCP_FILENAME_REGEX = rf"C{TB_CONFIG.oscilloscope.mcp_channel_number}--Trace(\d+).trc"
CLOCK_FILENAME_REGEX = rf"C{TB_CONFIG.oscilloscope.clock_channel_number}--Trace(\d+).trc"
MERGED_FILENAME_REGEX = r"run_(\d+).root"
ETROC_FILENAME_REGEX_FUNC = lambda rb: rf"output_run_(\d+)_rb{rb}.root"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def get_run_number():
    with open(RUN_NUMBER_PATH, 'r') as file:
        run_number = file.read().strip()
    return int(run_number)

def create_output_dir(handler) -> Path:
    """
    Creates output dir for handler, if it already exists it does nothing
    """
    if not hasattr(handler, "output_dirname"):
        raise AttributeError("Handler does not have the output_dirname defined")
    output_path =  BASE_DIR / Path(handler.output_dirname)
    output_path.mkdir(exist_ok=True) # throws error if parents dont exists :)
    return output_path

def find_run_numbers(directory: Path, reg_expression: str) -> Set[int]:
    """
    Finds all run numbers in a directory based off of a regular expression.
    Supports only one capture group in the regular expression (this should be for the run number!)
    If a non integer string is found, it raises a Value Error.
    """
    run_numbers = set()
    if not directory.is_dir():
        raise NotADirectoryError(f"Directory not found for: {directory}")
    
    expression = re.compile(reg_expression)
    for file in directory.iterdir():
        if not file.is_file():
            continue
        if match := expression.match(file.name):
            if len(match.groups()) != 1:
                raise ValueError(f"Please provide only one capture group in regular expresion, {len(match.groups())} found. Remember in regex capture groups are denoted by parenthesis ()") 
            run_num_raw = match.group(1)
            if run_num_raw.isdigit():
                run_numbers.add(int(run_num_raw))
            else:
                raise ValueError(f"Your inputted regular expression did not output an integer. Output: {run_num_raw}")
    return run_numbers

def get_unmerged_runs(merged_root_dir: Path) -> Set:
    """
    Finds unmerged runs by comparing run numbers between trace files and etroc binaries
    """
    merged_runs = find_run_numbers(
        merged_root_dir,
        MERGED_FILENAME_REGEX
    )

    all_runs = set()
    all_runs  |= find_run_numbers(SCOPE_BINARY_DIR, MCP_FILENAME_REGEX)
    all_runs  |= find_run_numbers(SCOPE_BINARY_DIR, CLOCK_FILENAME_REGEX)

    etroc_runs = set()
    for rb in TB_CONFIG.telescope_config.rbs:
        # need to use "&" bec if there were any runs with not all rbs binary data
        etroc_runs &= find_run_numbers(
            ETROC_BINARY_DIR, ETROC_FILENAME_REGEX_FUNC(rb))
    all_runs |= etroc_runs
    return all_runs - merged_runs

class EtrocHitMapsHandler(FileSystemEventHandler):
    output_dirname = "etroc_hitmaps"
    # def __init__(self, *args, **kwargs):
    #     super(EtrocHitMapsHandler, self).__init__(*args, **kwargs)
    def on_created(self, event):
        if event.src_path.endswith(".dat"):
            logging.info(f'[ETROC HIT MAP] ETROC Binary at {event.src_path} has been created')

    def on_modified(self, event):
        # Not sure if this works,
        if event.src_path.endswith(".dat"):
            logging.info(f"[ETROC HIT MAP] Making hitmap for ETROC binary at {event.src_path}")
            ...
    
class ClockPlotsHandler(FileSystemEventHandler):
    output_dirname = "clock_histograms"

    def on_created(self, event):
        logging.info(f'[CLOCK PLOT] Scope Clock Trace file at {event.src_path} has been created')
        # DO CLOCK HISTOGRAM HERE...
        # check what the channel is...

class McpPlotsHandler(FileSystemEventHandler):
    output_dirname = "mcp_plots"

    def on_created(self, event):
        logging.info(f'[MCP PLOT] Scope MCP Trace file at {event.src_path} has been created')
        # DO MCP Waveforms HERE...
        # output mcpwaveforms to directory

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
        # REMEMBER TO INCLUDE THE LOG FOR EACH RUN! Adds bload data but we do not care!
        logging.info("The expected binaries are in their respective directories, attempting merge!")
        # will need functionality to wait for multiple binaries (look at telescope mode)

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
    print("========= UNMERGED RUNS =========")
    print(
        sorted(get_unmerged_runs(merged_root_dir)))
    print("=================================\n")

    for handler, directory in processing_handlers:
        # Make watchdog dirs if they do not exist
        create_output_dir(handler)
        observer.schedule(handler, directory)

    observer.schedule(DataBackupHandler(), merged_root_dir)

    observer.schedule(
        ConfigUpdateHandler(), 
        TB_CONFIG.test_beam.project_directory / Path("configs/active_config/"))


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    