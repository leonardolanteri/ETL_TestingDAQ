from pathlib import Path
import uproot
import numpy as np
import matplotlib.pyplot as plt
import mplhep as hep
import awkward as ak
import time
from run_number import extract_run_number

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

    def print_path(self) -> None:
        print(f"The path of the chosen root file is: {self.path}")

    def get_path(self) -> Path:
        return self.path
    
    def available_branches(self) -> None:
        print("The available branches are: ")
        print(self.tree.keys())

    def find_chipds(self) -> list:
        self.branch = ["chipid"]
        self.events = self.tree.arrays(self.branch, library="ak")
        chipid_list = np.unique(np.concatenate(self.events["chipid"].to_list()))
        return chipid_list

    def etroc_hitmap(self, chipid_list:list = None) -> None:
        """
        GeneratPlots an ETROC HitMap for every chipid given, if none are given (default) it looks for all the chipids on the provided root file and generates a hitmap for each one of them
        """

        self.branches = ["chipid", "row", "col"]
        self.events = self.tree.arrays(self.branches, library="ak")
        regex = MERGED_FILENAME_REGEX
        run_number = extract_run_number(self.path, regex, force_file_exist=True)

        if chipid_list is None:
            chipid_list = self.find_chipds()

        for chip_id in chipid_list:
            hits = np.zeros((16, 16))
        
            # zip zip zip :)
            for event_chipids, event_rows, event_cols in zip(self.events["chipid"], self.events["row"], self.events["col"]):
                #print(event_chipids, event_rows, event_cols)
                for cid, r, c in zip(event_chipids, event_rows, event_cols):
                    if cid == chip_id:
                        hits[r, c] += 1
        
        chip_id_converted = int(chip_id) >> 2
        # Plot the hitmap for this chip_id
        fig, ax = plt.subplots(figsize=(7, 7))
        cax = ax.matshow(hits, cmap="viridis")
        fig.colorbar(cax, ax=ax)
        ax.set_xlabel("Column")
        ax.set_ylabel("Row")
        ax.set_title(f"Hitmap from ROOT file for chipid = {chip_id_converted}, run {run_number}")
        plt.show()


    def mcp_plot(self, one_every_n:int = 10) -> None:
        """
        Generates the plot with all the MCP traces stored in the root file; it plots one trace every 'one_every_n' event
        """

        self.branches = ["mcp_volts", "mcp_seconds"]
        self.events = self.tree.arrays(self.branches, library="ak")
        regex = MERGED_FILENAME_REGEX
        run_number = extract_run_number(self.path, regex, force_file_exist=True)

        for i in range(len(self.events["mcp_seconds"])): 
            if i % one_every_n == 0:
                time_series = self.events["mcp_seconds"][i]  
                voltage_series = self.events["mcp_volts"][i]  
                plt.plot(time_series, voltage_series, alpha=0.3, linewidth=0.8)
            
        plt.xlabel("Time (ns)")
        plt.ylabel("Voltage (V)")
        plt.title(f"MCP Waveforms run {run_number}")
        plt.grid(True)
        plt.show()


    def clock_plot(self, one_every_n:int = 100) -> None:
        """
        Generates the plot with all the clock traces stored in the root file; it plots one trace every 'one_every_n' event
        """

        self.branches = ["clock_volts", "clock_seconds"]
        self.events = self.tree.arrays(self.branches, library="ak")
        regex = MERGED_FILENAME_REGEX
        run_number = extract_run_number(self.path, regex, force_file_exist=True)

        for i in range(len(self.events["clock_seconds"])): 
            if i % one_every_n == 0:
                time_series = self.events["clock_seconds"][i]  
                voltage_series = self.events["clock_volts"][i]  
                plt.plot(time_series, voltage_series, alpha=0.3, linewidth=0.8)
            
        plt.xlabel("Time (ns)")
        plt.ylabel("Voltage (V)")
        plt.title(f"Clock Waveforms run {run_number}")
        plt.grid(True)
        plt.show()

            


