"""
Decodes the ETROC and Oscilliscope binary
Performs fit on the KCU Clock and MCP signals

Simple processing routine that uses multiprocessing
Please watch this video if you are new to multiprocessing:
https://www.youtube.com/watch?v=X7vBbelRXn0 
"""
from binary_decoders import etroc, lecroy
from oscilliscope_fitting import clock, mcp
import awkward as ak
import uproot
import numpy as np
import asyncio
import logging
import time
from multiprocessing import Pool
from pathlib import Path
import os

# idea is to get it darn fast with multithreading

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CLOCK CONFIGURABLES
CLOCK_THRESH_LOW, CLOCK_THRESH_HIGH = 0.25, 0.8 #used to pick out the edges (between 0 and 1, percentage of the absolute amplitude)
CLOCK_MEAUREMENT_POINT = 0.5 #between 0 and 1, after the fit, where along the fitted y axis do we take the clock value
MCP_MAX_AMP = -1.35
def consolidate_acquisition(output_file_path: str, etroc_binary_paths: list[str]=None, mcp_binary_path: str=None, clock_binary_path: str=None):
    t_file_reads = time.perf_counter()

    mcp_waveform = lecroy.LecroyReader(mcp_binary_path)
    clock_waveform = lecroy.LecroyReader(clock_binary_path)
    etroc_unpacked_data = etroc.converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = etroc.root_dumper(etroc_unpacked_data) # root dumper name is due to history 
    if etroc_data is None:
        print("no etroc data")
        # no etroc data...
        return
    
    logger.info(f"LOADING FILES TOOK {(time.perf_counter()-t_file_reads):.2f} seconds")
    t_process_files = time.perf_counter()

    nanoseconds, scaled_volts = mcp.MCPSignalScaler.normalize(mcp_waveform.x * 1e9, mcp_waveform.y, signal_saturation_level=MCP_MAX_AMP)
    peak_times, peak_volts = mcp.MCPSignalScaler._calc_mcp_peaks(nanoseconds, mcp_waveform.y)
    mcp_timestamps = mcp.linear_interpolation(nanoseconds, scaled_volts, peak_times, threshold=0.4)
    clock_timestamps = clock.calc_clock(
        ak.from_numpy(clock_waveform.x*1e9), ak.from_numpy(clock_waveform.y),
        CLOCK_THRESH_LOW, CLOCK_THRESH_HIGH, CLOCK_MEAUREMENT_POINT
    )
    logger.info(f"PROCESS FILES TOOK {(time.perf_counter()-t_process_files):.2f} seconds")
    t_write_files = time.perf_counter()

    etroc_data_map = dict(zip(
        ak.fields(etroc_data), ak.unzip(etroc_data)
    ))

    mcp_trigger_times, _ = mcp_waveform.segment_times
    oscilliscope_merged_map = {
        "i_evt": list(range(len(clock_waveform.x))),
        "segment_time": mcp_trigger_times,
        "mcp_volts": mcp_waveform.y,
        "mcp_seconds": mcp_waveform.x,
        "clock_volts": clock_waveform.y,
        "clock_seconds": clock_waveform.x,
        "mcp_amplitude": peak_volts,
        "clock_timestamp": clock_timestamps, 
        "mcp_timestamp": mcp_timestamps #actually LP1_40
    }

    consolidated_array = etroc_data_map | oscilliscope_merged_map

    with uproot.recreate(output_file_path) as output:
        try:
            output["pulse"] = consolidated_array
        except:
            N_events_etroc = len(etroc_data_map[list(etroc_data_map.keys())[0]])
            N_events_scope = len(oscilliscope_merged_map[list(oscilliscope_merged_map.keys())[0]])
            print(f"The length of the branches doesn't match for run: {output_file_path}, {N_events_etroc} vs {N_events_scope}")

    logger.info(f"WRITE FILE TOOK {(time.perf_counter()-t_write_files):.2f} seconds")


# trace_file = lambda chnl, run: Path(f'/media/etl/Storage/SPS_October_2024/LecroyRaw/C{chnl}--Trace{run}.trc')
# etroc_file = lambda run: Path(f"/home/etl/Test_Stand/module_test_sw/ETROC_output/output_run_{run}_rb0.dat")

trace_file = lambda chnl, run: f"/eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/LecroyRaw/C{chnl}--Trace{run}.trc"
etroc_file = lambda run: f"/eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/rawDat/output_run_{run}_rb0.dat"

MCP_channel = 2
CLK_channel = 3

output_file_dir = Path(f"rereco_data2")
output_file_dir.parent.mkdir(parents=True, exist_ok=True)
output_file = lambda run: Path(f"run_{run}.root")

run_start = 2800 # 12011
run_stop = 3000 # 12110

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
            clock_binary_path=trace_file(CLK_channel, run)
            # oscilliscope_reference_path=trace_file(MCP_channel, run)
        )
    except:
        print("AN ERROR HAS OCCURED DURING CONVERSION!")

t_consolidated = time.perf_counter()
with Pool() as pool:
    results = pool.imap_unordered(
        consolidate_acquisition_task, range(run_start, run_stop + 1)
    )
    # for i in range(run_start, run_stop + 1):
    #     consolidate_acquisition_task(i)
    for r in results:
        pass # print(r)

print(f"COMPLETED IN: {(time.perf_counter()-t_consolidated):.2f} seconds")
