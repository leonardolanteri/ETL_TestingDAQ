from etroc_binary_decoder import converter, root_dumper
from lecroy_binary_decoder import LecroyReader
from pathlib import Path
import logging
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use a non-GUI backend otherwise the multithread crushes
import matplotlib.pyplot as plt
import mplhep 
logger = logging.getLogger(__name__)
import uproot
from run_number import extract_run_number
import awkward as ak

MERGED_FILENAME_REGEX = r"run_(\d+).root"

class TBplot:
    def __init__(self, root_file_path: Path):
        self.path = root_file_path
        if not self.path.exists():
            raise ValueError(f"The path {self.path} does not exist, please provide an exisiting path")
        if not self.path.is_file():
            raise ValueError(f"The path {self.path}  is not a file, please provide a path to a .root file")

        self.root_file = uproot.open(str(self.path))
        self.tree = self.root_file["pulse"]

    def available_branches(self) -> None:
        print("The available branches are: ")
        print(self.tree.keys())

    def find_chipds(self) -> list:
        self.branch = ["chipid"]
        events = self.tree.arrays(self.branch, library="ak")
        chipid_list = np.unique(np.concatenate(events["chipid"].to_list()))
        return chipid_list

    def etroc_hitmap(self, chipid_list:list = None, output_directory: Path = None) -> None:
        """
        Generates an ETROC HitMap for every chipid given, if none are given (default) it looks for all the chipids on the provided root file and generates a hitmap for each one of them
        """

        branches = ["chipid", "row", "col"]
        events = self.tree.arrays(branches, library="ak")
        print(events)
        if chipid_list is None:
            chipid_list = self.find_chipds()

        figs = []
        for chip_id in chipid_list:
            hits = np.zeros((16, 16))
        
            # zip zip zip :)
            for event_chipids, event_rows, event_cols in zip(events["chipid"], events["row"], events["col"]):
                #print(event_chipids, event_rows, event_cols)
                for cid, r, c in zip(event_chipids, event_rows, event_cols):
                    if cid == chip_id:
                        hits[r, c] += 1
        
            module_id = int(chip_id) >> 2
            # Plot the hitmap for this chip_id
            fig, ax = plt.subplots(figsize=(7, 7))
            cax = ax.matshow(hits, cmap="viridis")
            fig.colorbar(cax, ax=ax)
            ax.set_xlabel("Column")
            ax.set_ylabel("Row")
            ax.set_title(f"Hitmap from ROOT file for module_id = {module_id}, chipid = {chip_id}, run = {self.path.name}")
            figs.append(fig)
        
            if output_directory:
                fig.savefig(output_directory / f"{self.path.stem}_root_etroc_chipid_{chip_id}_mod_{module_id}_hitmap.png")
        return figs

    def mcp_plot(self, one_every_n:int = 10,  output_directory: Path = None) -> None:
        """
        Generates the plot with all the MCP traces stored in the root file; it plots one trace every 'one_every_n' event
        """

        branches = ["mcp_volts", "mcp_seconds"]
        events = self.tree.arrays(branches, library="ak")

        for i in range(len(events["mcp_seconds"])): 
            if i % one_every_n == 0:
                time_series = events["mcp_seconds"][i]  
                voltage_series = events["mcp_volts"][i]  
                plt.plot(time_series, voltage_series, alpha=0.3, linewidth=0.8)
            
        plt.xlabel("Time (ns)")
        plt.ylabel("Voltage (V)")
        plt.title(f"MCP Waveforms for {self.path.stem}")
        plt.grid(True)
        if output_directory:
            plt.savefig(output_directory / f"{self.path.stem}_root_mcp_plot.png")

    def clock_plot(self, one_every_n:int = 100,  output_directory: Path = None) -> None:
        """
        Generates the plot with all the clock traces stored in the root file; it plots one trace every 'one_every_n' event
        """

        branches = ["clock_volts", "clock_seconds"]
        events = self.tree.arrays(branches, library="ak")
        regex = MERGED_FILENAME_REGEX
        run_number = extract_run_number(self.path, regex, force_file_exist=True)

        for i in range(len(events["clock_seconds"])): 
            if i % one_every_n == 0:
                time_series = events["clock_seconds"][i]  
                voltage_series = events["clock_volts"][i]  
                plt.plot(time_series, voltage_series, alpha=0.3, linewidth=0.8)
            
        plt.xlabel("Time (ns)")
        plt.ylabel("Voltage (V)")
        plt.title(f"Clock Waveforms run {run_number}")
        plt.grid(True)
        if output_directory:
            plt.savefig(output_directory / f"{self.path.stem}_clock_plot.png")

def etroc_binary_monitor(path: Path, output_dir: Path, run_number: int) -> Path:
    """
    Generates a hitmap from ETROC binary data and saves it in the specified output directory.
    Also outputs the etroc data as json.
    """
    # Set CMS style for plots
    plt.style.use(mplhep.style.CMS)

    # Convert the paths in strings and the binaries in ak.arrays
    etroc_binary_paths = [str(path)] 
    etroc_unpacked_data = converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = root_dumper(etroc_unpacked_data)

    if etroc_data is None:
        logger.warning(f"No ETROC data available for {path}.")
        return

    ak.to_json(
        etroc_data, 
        output_dir / f"run_{run_number}_etroc_binary.json",
        num_indent_spaces=2)

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
    ax.set_title(f"Hitmap for {path.stem}", fontsize=20)

    # Define output file path 
    output_file = output_dir / f"run_{run_number}_binary_etroc_hitmap.png"
    fig.savefig(output_file)
    plt.close(fig)
    return output_file

def MCP_trace_generator(path: Path, output_dir: Path, run_number: int) -> Path:
    """
    Plots all events from path (they have to be Lecroy binaries) and saves the histogram on outputdir.
    """
    reader = LecroyReader(str(path))

    # Create a figure and axis explicitly for thread safety
    fig, ax = plt.subplots(figsize=(10, 6))

    for event_num in range(reader.n_events):
        if event_num % 10 == 0:
            t, v = reader.x[event_num] * 1e9, reader.y[event_num]
            ax.plot(t, v, alpha=0.3)  # Alpha for transparency to see overlapping traces

    # Add trigger & min/max voltage lines
    ax.axvline(0, label="Trigger (t=0)", color='black', linewidth=1.2)
    ax.axhline(reader.minVerticalValue, label=f'Min V = {reader.minVerticalValue:.3}V', color='red', linestyle='--')
    ax.axhline(reader.maxVerticalValue, label=f'Max V = {reader.maxVerticalValue:.3}V', color='red', linestyle='--')

    # Labels and legend
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"All {reader.n_events/10} Events MCP - Channel {reader.channel}")
    ax.legend(loc="upper right")
    ax.grid()

    output_file = output_dir / f"run_{run_number}_binary_mcp_plot.png"
    fig.savefig(output_file)
    plt.close(fig) 
    return output_file

def Clock_trace_generator(path: Path, output_dir: Path, run_number: int) -> None:
    """
    Plots all events from path (they have to be Lecroy binaries) and saves the histogram on outputdir.
    """
    reader = LecroyReader(str(path))

    # Create a figure and axis explicitly for thread safety
    fig, ax = plt.subplots(figsize=(10, 6))

    for event_num in range(reader.n_events):
        if event_num % 10 == 0:
            t, v = reader.x[event_num] * 1e9, reader.y[event_num]
            ax.plot(t, v, alpha=0.3)  # Alpha for transparency to see overlapping traces

    # Add min/max voltage lines
    ax.axhline(reader.minVerticalValue, label=f'Min V = {reader.minVerticalValue:.3}V', color='red', linestyle='--')
    ax.axhline(reader.maxVerticalValue, label=f'Max V = {reader.maxVerticalValue:.3}V', color='red', linestyle='--')

    # Labels and legend
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title(f"All {reader.n_events/10} Events Clock - Channel {reader.channel}")
    ax.legend(loc="upper right")
    ax.grid()

    output_file = output_dir / f"run_{run_number}_{path.stem}_binary_clock_plot.png"
    fig.savefig(output_file)
    plt.close(fig) 
    return output_file