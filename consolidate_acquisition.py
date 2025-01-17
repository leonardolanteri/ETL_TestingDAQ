"""
Decodes the ETROC and Oscilliscope binary
Performs fit on the KCU Clock and MCP signals
"""
from binary_decoders import etroc, lecroy
from oscilliscope_fitting import clock, mcp
import awkward as ak
import uproot
import numpy as np
# CLOCK CONFIGURABLES
CLOCK_THRESH_LOW, CLOCK_THRESH_HIGH = 0.25, 0.8 #used to pick out the edges (between 0 and 1, percentage of the absolute amplitude)
CLOCK_MEAUREMENT_POINT = 0.5 #between 0 and 1, after the fit, where along the fitted y axis do we take the clock value

def consolidate_acquisition(output_file_path: str, etroc_binary_paths: list[str]=None, mcp_binary_path: str=None, clock_binary_path: str=None, oscilliscope_reference_path: str=None):
    def convert_oscilliscope_reference() -> lecroy.LecroyReader:
        """
        This will likely be removed one day. It is used to calculated timeoffset
        But this is to get the same output as the previous test beams... 
        ->To calculate the time offset they take the difference in time between the chosen channel 
        and an unused channel 1 and NOT the differnece between the clock channel and mcp channel which I feel like makes more sense.
        BUT for SPS Oct 2024, it was done correctly because only the mcp and clock channels were inputted
        So you might have to give the same path for the clock or mcp here if you want to get the same output as before.

        Moreover this should probably be calculated in the analysis part of the code. But for backwards compatability it will be done here...
        """
        return lecroy.LecroyReader(oscilliscope_reference_path)
    print("Converting Oscilliscope Reference") # AGAIN I DONT THINK THIS IS NECESSARY!!!!!!!!!!!!!!
    oscilliscope_reference_wavefrom = convert_oscilliscope_reference()

    print("Converting MCP Channel Binary")
    mcp_waveform = lecroy.LecroyReader(mcp_binary_path)

    print("Converting Clock Channel Binary")
    clock_waveform = lecroy.LecroyReader(clock_binary_path)

    nanoseconds, scaled_volts = mcp.MCPSignalScaler.normalize(mcp_waveform.x * 1e9, mcp_waveform.y)
    peak_times, peak_volts = mcp.MCPSignalScaler._calc_mcp_peaks(nanoseconds, mcp_waveform.y)
    mcp_timestamps = mcp.linear_interpolation(nanoseconds, scaled_volts, peak_times, threshold=0.4)

    print("Performing Clock Wavefrom Fits")
    clock_timestamps = clock.calc_clock(
        ak.from_numpy(clock_waveform.x*1e9), ak.from_numpy(clock_waveform.y),
        CLOCK_THRESH_LOW, CLOCK_THRESH_HIGH, CLOCK_MEAUREMENT_POINT
    )

    print("Converting ETROC Binary")
    etroc_unpacked_data = etroc.converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = etroc.root_dumper(etroc_unpacked_data) # root dumper name is due to history 
    etroc_data_map = dict(zip(
        ak.fields(etroc_data), ak.unzip(etroc_data)
    ))
    
    print("Making consolidated array and dumpong to root file")
    ref_trigger_times, ref_horz_offset = oscilliscope_reference_wavefrom.segment_times
    _, mcp_horz_offset = mcp_waveform.segment_times
    _, clock_horz_offset = clock_waveform.segment_times
    oscilliscope_merged_map = {
        "i_evt": list(range(len(clock_waveform.x))),
        "segment_time": ref_trigger_times,
        "channel": np.stack(
            [oscilliscope_reference_wavefrom.y, 
             mcp_waveform.y, 
             clock_waveform.y], 
            axis=1),
        "time": clock_waveform.x, # I should save all out right?!
        "timeoffsets": np.stack( # see timeoffset calculation in binary_decoders/lecroy.py 
            [ref_horz_offset-ref_horz_offset, 
             mcp_horz_offset-ref_horz_offset, 
             clock_horz_offset-ref_horz_offset], 
            axis=1),
        "mcp_amp": peak_volts,
        "Clock": clock_timestamps, 
        "LP1_40": mcp_timestamps
    }

    consolidated_array = etroc_data_map | oscilliscope_merged_map
    with uproot.recreate(output_file_path) as output:
        output["pulse"] = consolidated_array


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

