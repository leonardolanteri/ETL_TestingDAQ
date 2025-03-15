from etroc_binary_decoder import converter, root_dumper
from lecroy_binary_decoder import LecroyReader
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend otherwise the multithread crushes
import matplotlib.pyplot as plt
import mplhep as hep
from process_binaries import consolidate_acquisition
import logging
from config import load_config
import time
import sys
import logging
from pathlib import Path
from typing import Set, Union
import re

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
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def get_next_run_number() -> int:
    """Looks at the daq/static/next_run_number.txt which stores the next run number from daq"""
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

def find_run_number(file_path: Path, reg_expression: str) -> Union[None, int]:
    """
    From file path it extracts the run number, if no run number is found it returns nothing. 
    Only one capture group is allowed in the regular expression
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found for: {file_path}")

    expression = re.compile(reg_expression)
    match = expression.match(file_path.name)
    if not match:
        return None

    if len(match.groups()) != 1:
        raise ValueError(f"Please provide only one capture group in regular expression, {len(match.groups())} found. Remember in regex capture groups are denoted by parenthesis ()")

    run_num_raw = match.group(1)
    if not run_num_raw.isdigit():
        raise ValueError(f"Your inputted regular expression did not output an integer. Output: {run_num_raw}")

    return int(run_num_raw)

def find_file_by_run_number(source_directory: Path, run_number: int, filename_regex: str):
    """
    Looks through all files in source directory, matching the filename using the filename_regex,
    returns the file with matching run number.
    """
    for file in source_directory.iterdir():
        matched_run_number = find_run_number(file, filename_regex)
        if matched_run_number is None:
            continue

        if run_number == matched_run_number:
            return file

def get_unmerged_runs(merged_root_dir: Path) -> Set:
    """
    Finds unmerged runs by comparing run numbers between trace files and etroc binaries
    """
    def find_run_numbers(directory: Path, reg_expression: str) -> Set[int]:
        """
        Finds all run numbers in a directory based off of a regular expression.
        Supports only one capture group in the regular expression (this should be for the run number!)
        If a non integer string is found, it raises a Value Error.
        """
        run_numbers = set()
        if not directory.is_dir():
            raise NotADirectoryError(f"Directory not found for: {directory}")
        
        for file in directory.iterdir():
            run_num = find_run_number(file, reg_expression)
            if run_num is not None:
                run_numbers.add(run_num)
        return run_numbers

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

def etroc_hitmaps_generator(path: Path, output_dir: Path) -> None:
    """
    Generates a hitmap from ETROC binary data and saves it in the specified output directory.
    """
    # Set CMS style for plots
    plt.style.use(hep.style.CMS)

    # Convert the paths in strings and the binaries in ak.arrays
    etroc_binary_paths = [str(path)] 
    etroc_unpacked_data = converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = root_dumper(etroc_unpacked_data)

    if etroc_data is None:
        logging.warning(f"No ETROC data available for {path}.")
        return

    hits = np.zeros([16, 16])
    mask = []  # Define mask if needed

    for ev in etroc_data:
        for row, col in zip(ev.row, ev.col):
            if (row, col) not in mask:
                hits[row][col] += 1

    fig, ax = plt.subplots(1, 1, figsize=(7, 7))
    cax = ax.matshow(hits)
    ax.set_ylabel(r'$Row$')
    ax.set_xlabel(r'$Column$')
    fig.colorbar(cax, ax=ax)
    run_number = path.name.split("_")[2]
    ax.set_title(f"Hitmap run_{run_number}", fontsize=20)

    # Define output file path 
    output_file = output_dir / f"hitmap_run_{run_number}.png"
    fig.savefig(output_file)
    plt.close(fig)
    logging.info(f"Generated and saved hitmap at: {output_file}")



def MCP_trace_generator(path: Path, output_dir: Path, run_number: str) -> None:
    """
    Plots all events from path (they have to be Lecroy binaries) and saves the histogram on outputdir.
    """

    reader = LecroyReader(str(path))

    # Create a figure and axis explicitly for thread safety
    fig, ax = plt.subplots(figsize=(10, 6))

    for event_num in range(reader.n_events):
        t, v = reader.x[event_num] * 1e9, reader.y[event_num]
        ax.plot(t, v, alpha=0.3)  # Alpha for transparency to see overlapping traces

    # Add trigger & min/max voltage lines
    ax.axvline(0, label="Trigger (t=0)", color='black', linewidth=1.2)
    ax.axhline(reader.minVerticalValue, label=f'Min V = {reader.minVerticalValue:.3}V', color='red', linestyle='--')
    ax.axhline(reader.maxVerticalValue, label=f'Max V = {reader.maxVerticalValue:.3}V', color='red', linestyle='--')

    # Labels and legend
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"All {reader.n_events} Events MCP - Channel {reader.channel}")
    ax.legend()
    ax.grid()

    output_file = output_dir / f"MCP_traces_run_{run_number}.png"
    fig.savefig(output_file)
    plt.close(fig) 

    logging.info(f"Generated and saved MCP trace at: {output_file}")

def Clock_trace_generator(path: Path, output_dir: Path, run_number: str) -> None:
    """
    Plots all events from path (they have to be Lecroy binaries) and saves the histogram on outputdir.
    """
    reader = LecroyReader(str(path))

    # Create a figure and axis explicitly for thread safety
    fig, ax = plt.subplots(figsize=(10, 6))

    for event_num in range(reader.n_events):
        t, v = reader.x[event_num] * 1e9, reader.y[event_num]
        ax.plot(t, v, alpha=0.3)  # Alpha for transparency to see overlapping traces

    # Add min/max voltage lines
    ax.axhline(reader.minVerticalValue, label=f'Min V = {reader.minVerticalValue:.3}V', color='red', linestyle='--')
    ax.axhline(reader.maxVerticalValue, label=f'Max V = {reader.maxVerticalValue:.3}V', color='red', linestyle='--')

    # Labels and legend
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"All {reader.n_events} Events Clock - Channel {reader.channel}")
    ax.legend()
    ax.grid()

    output_file = output_dir / f"Clock_traces_run_{run_number}.png"
    fig.savefig(output_file)
    plt.close(fig) 

    logging.info(f"Generated and saved Clock traces at: {output_file}")


class EtrocHitMapsHandler(FileSystemEventHandler):
    output_dirname = "etroc_hitmaps"
    # def __init__(self, *args, **kwargs):
    #     super(EtrocHitMapsHandler, self).__init__(*args, **kwargs)
    def on_created(self, event):
        if event.src_path.endswith(".dat"):
            logging.info(f'[ETROC HIT MAP] ETROC Binary at {event.src_path} has been created')
            file_path = Path(event.src_path)
            output_dir = create_output_dir(self)
            try:
                # Generate hitmap
                etroc_hitmaps_generator(file_path,output_dir)
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

    rbs = config.TelescopeConfig.rbs
    output_dirname = 'merged_root'

    def on_created(self, event):
        etroc_regs = [ETROC_FILENAME_REGEX_FUNC(rb) for rb in TB_CONFIG.telescope_config.rbs]
        scope_regs = [CLOCK_FILENAME_REGEX, MCP_FILENAME_REGEX]

        # Get run number from event
        event_run_number = None
        for reg_exp in etroc_regs + scope_regs:
            event_run_number = find_run_number(Path(event.src_path), reg_exp)
            if event_run_number is not None:
                break

        if event_run_number is None:
            logging.warning(f"Did not find event run number for this file path: {event.src_path}")
            return

        found_etroc_runs = [
            find_file_by_run_number(ETROC_BINARY_DIR, event_run_number, reg) for reg in etroc_regs
        ]
        found_mcp_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, MCP_FILENAME_REGEX)
        found_clock_run = find_file_by_run_number(SCOPE_BINARY_DIR, event_run_number, CLOCK_FILENAME_REGEX)
        if None in found_etroc_runs or found_mcp_run is None or found_clock_run is None:
            # Need all three data files
            return

        run_log = get_run_log(event_run_number)
        if run_log is None:
            logging.error(f"NOT MERGING RUN {event_run_number}: Run log not found")
            return

        logging.info(f'[MERGED ROOT FILE] Creating merged root file at {event.src_path}')
        consolidate_acquisition(
            create_output_dir(self) / Path(MERGED_FILENAME(event_run_number)),
            etroc_binary_paths=list(map(str, found_etroc_runs)),
            mcp_binary_path=str(found_mcp_run),
            clock_binary_path=str(found_clock_run),
            run_log_path=run_log
        )

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