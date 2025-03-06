import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from config import load_config
import logging
import os
import Path

TB_CONFIG = load_config()
ETROC_BINARY_DIR = TB_CONFIG.telescope_config.etroc_binary_data_directory
SCOPE_BINARY_DIR =  TB_CONFIG.oscilloscope.binary_data_directory
BASE_DIR = TB_CONFIG.watchdog.base_directory
WATCHDOG_LOG_PATH = BASE_DIR / Path("watchdog_logs")

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def create_output_dir(handler) -> Path:
    """
    Creates output dir for handler, if it already exists it does nothing
    """
    if not hasattr(handler, "__output_dirname__"):
        raise AttributeError("Handler does not have the __output_dir__ defined")
    output_path =  BASE_DIR / Path(handler.__output_dirname__)
    output_path.mkdir(exist_ok=True) # throws error if parents dont exists :)
    return output_path

def create_log_file(handler) -> None:
    # Create watchdog path if it does not exist
    if not WATCHDOG_LOG_PATH.isdir():
        WATCHDOG_LOG_PATH.mkdir()

    

class EtrocHitMaps(FileSystemEventHandler):
    __output_dirname__ = "etroc_hitmaps"

    def on_created(self, event):
        print(f'ETROC Binary at {event.src_path} has been created')
        if event.src_path.endswith(".dat"):
            ...

class ScopeClockHistograms(FileSystemEventHandler):
    __output_dirname__ = "clock_histograms"

    def on_created(self, event):
        print(f'Scope Clock Trace file at {event.src_path} has been created')
        # DO CLOCK HISTOGRAM HERE...
        # check what the channel is...

class ScopeMcpPlots(FileSystemEventHandler):
    __output_dirname__ = "mcp_plots"

    def on_created(self, event):
        print(f'Scope MCP Trace file at {event.src_path} has been created')
        # DO MCP Waveforms HERE...
        # output mcpwaveforms to directory
        # Catch up yes...

class ConfigUpdate(FileSystemEventHandler):
    def on_created(self, event):
        print("Config updated, reloading with new config parameters!")
        # Just exit the watchdog with a big explanation
        # The config has changed please rerun the watchdog in order to load the new config
        # do this on file changes, or if new active config

class MergeToRoot(FileSystemEventHandler):
    __output_dirname__ = 'merged_root'

    def on_created(self, event):
        # REMEMBER TO INCLUDE THE LOG FOR EACH RUN! Adds bload data but we do not care!
        print("The expected binaries are in their respective directories, attempting merge!")
        # Catch up yes...
        # will need functionality to wait for multiple binaries (look at telescope mode)

class DataBackupHandler(FileSystemEventHandler):
    def on_created(self, event):
        print("Merged root file made, attempting backup store of binaries and root file")

if __name__ == "__main__":

    observer = Observer()

    processing_handlers = [
        (EtrocHitMaps(), ETROC_BINARY_DIR),
        (ScopeClockHistograms(), SCOPE_BINARY_DIR),
        (ScopeMcpPlots(), SCOPE_BINARY_DIR),
        (MergeToRoot(), SCOPE_BINARY_DIR),
        (MergeToRoot(), ETROC_BINARY_DIR)
    ]

    for handler, directory in processing_handlers:
        create_output_dir(handler)
        create_log_file(handler)
        observer.schedule(handler, directory)




    # Make watchdog dirs if they do not exist

    # Check if run log exists if not make it
    # -> Assume nothing is processed if it does not exist so start from first dat file
    # <*> for every processed file done add a line to the csv


    # Catchup logic
    # for dir_path, handlers in directories.items():
    #     for file in os.listdir(dir_path):
    #         filename = os.path.join(dir_path, file)
    #         event = FileCreatedEvent(filename)
    #         if isinstance(handlers, list):
    #             for handler in handlers:
    #                 handler.on_created(event)
    #         else:
    #             handlers.on_created(event)


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    