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

def etroc_hitmaps_generator(path: Path, output_dir: Path) -> None:
    """
    Generates a hitmap from ETROC binary data and saves it in the specified output directory.
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
    logger.info(f"Generated and saved hitmap at: {output_file}")

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
    ax.legend(loc="upper right")
    ax.grid()

    output_file = output_dir / f"MCP_traces_run_{run_number}.png"
    fig.savefig(output_file)
    plt.close(fig) 

    logger.info(f"[MCP PLOT] saved at: {output_file}")

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
    ax.legend(loc="upper right")
    ax.grid()

    output_file = output_dir / f"Clock_traces_run_{run_number}.png"
    fig.savefig(output_file)
    plt.close(fig) 

    logger.info(f"[CLOCK PLOT] saved at: {output_file}")
