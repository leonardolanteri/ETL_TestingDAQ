"""
Decodes the ETROC and Oscilliscope binary
Performs fit on the KCU Clock and MCP signals
"""
from binary_decoders import etroc, lecroy
from oscilliscope_fitting import clock, mcp
import awkward as ak
import uproot
import numpy as np
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
        output["pulse"] = consolidated_array

    logger.info(f"WRITE FILE TOOK {(time.perf_counter()-t_write_files):.2f} seconds")


# from datetime import datetime

# start = datetime.now()
# consolidate_acquisition(
#     "run_5100_new.root",
#     etroc_binary_paths=["unit_test/input_data/run_6000/output_run_6000_rb0.dat"],
#     mcp_binary_path="/home/users/hswanson13/ETL_TestingDAQ/unit_test/input_data/run_6000/C2--Trace6000.trc", #MCP
#     clock_binary_path="/home/users/hswanson13/ETL_TestingDAQ/unit_test/input_data/run_6000/C3--Trace6000.trc",  #CLOCK
#     oscilliscope_reference_path="/home/users/hswanson13/ETL_TestingDAQ/unit_test/input_data/run_6000/C1--Trace6000.trc"
# )
# elapsed_time = datetime.now()-start
# print(elapsed_time.total_seconds())

