"""
Decodes the ETROC and Oscilliscope binary

Simple processing routine that uses multiprocessing
Please watch this video if you are new to multiprocessing:
https://www.youtube.com/watch?v=X7vBbelRXn0 
"""
from lecroy import LecroyReader
from etroc import converter, root_dumper
import awkward as ak
import uproot
import logging
import time
import os
from multiprocessing import Pool
from pathlib import Path

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def consolidate_acquisition(output_file_path: str, etroc_binary_paths: list[str]=None, mcp_binary_path: str=None, clock_binary_path: str=None):
    t_file_reads = time.perf_counter()
    mcp_waveform = LecroyReader(mcp_binary_path)
    clock_waveform = LecroyReader(clock_binary_path)
    etroc_unpacked_data = converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = root_dumper(etroc_unpacked_data) # root dumper name is due to history 
    if etroc_data is None:
        print("no etroc data")
        return
    logger.info(f"LOADING FILES TOOK {(time.perf_counter()-t_file_reads):.2f} seconds")

    oscillicsope_waveforms = {
        'mcp_volts': mcp_waveform.y,
        'mcp_seconds': mcp_waveform.x,
        'clock_volts': clock_waveform.y,
        'clock_seconds': clock_waveform.x,
    } 
    etroc_data = dict(zip(ak.fields(etroc_data), ak.unzip(etroc_data)))

    t_write_files = time.perf_counter()
    with uproot.recreate(output_file_path) as output:
        try:
            output["pulse"] = oscillicsope_waveforms | etroc_data
        except:
            N_events_etroc = len(etroc_data[list(etroc_data.keys())[0]])
            N_events_scope = len(oscillicsope_waveforms[list(oscillicsope_waveforms.keys())[0]])
            print(f"The length of the branches doesn't match for run: {output_file_path}, {N_events_etroc} vs {N_events_scope}")
    
    logger.info(f"WRITE FILE TOOK {(time.perf_counter()-t_write_files):.2f} seconds")


# trace_file = lambda chnl, run: Path(f'/media/etl/Storage/SPS_October_2024/LecroyRaw/C{chnl}--Trace{run}.trc')
# etroc_file = lambda run: Path(f"/home/etl/Test_Stand/module_test_sw/ETROC_output/output_run_{run}_rb0.dat")

trace_file = lambda chnl, run: Path(f"/eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/LecroyRaw/C{chnl}--Trace{run}.trc")
etroc_file = lambda run: Path(f"/eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/rawDat/output_run_{run}_rb0.dat")

MCP_channel = 2
CLK_channel = 3

output_file_dir = Path(f"rereco_data2")
output_file_dir.parent.mkdir(parents=True, exist_ok=True)
output_file = lambda run: Path(f"run_{run}.root")

run_start = 2800
run_stop = 3000

def consolidate_acquisition_task(run):
    if (os.path.exists(f"{output_file_dir}/{output_file(run)}")):
        print(f"The file: {output_file(run)}, is already created.")
        return
    print(f'Consolidating run: {run}')
    try:
        consolidate_acquisition(
            output_file_dir / output_file(run),
            etroc_binary_paths=[etroc_file(run)],
            mcp_binary_path=trace_file(MCP_channel, run),
            clock_binary_path=trace_file(CLK_channel, run),
        )
    except:
        print("AN ERROR HAS OCCURED DURING CONVERSION!")

t_consolidated = time.perf_counter()
with Pool() as pool:
    results = pool.imap_unordered(
        consolidate_acquisition_task, range(run_start, run_stop + 1)
    )
    for _ in results:
        pass

print(f"COMPLETED IN: {(time.perf_counter()-t_consolidated):.2f} seconds")

