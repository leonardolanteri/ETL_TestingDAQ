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
CHANNEL_NUM = 1 #channel with square wave voltage (by index!! so subtract 1 to whatever it is on oscilloscope)

def generate_old_awk_array(oscilliscope_reference_reader: lecroy.LecroyReader, mcp_reader: lecroy.LecroyReader, clock_reader: lecroy.LecroyReader) -> ak.Array:
    """
    This is just so it can work with the old code (ie the dat2root compiled script). If an updated mcp fitting routine was made this code could be removed.
    5000 * {
        i_evt: uint32,
        segment_time: float32,
        channel: 4 * 502 * float32,
        time: 1 * 502 * float32,
        timeoffsets: 8 * float32 #one for each channel
    }
    """
    ref_trigger_times, ref_horz_offset = oscilliscope_reference_reader.get_segment_times()
    _, mcp_horz_offset = mcp_reader.get_segment_times()
    _, clock_horz_offset = clock_reader.get_segment_times()
    return ak.Array({
        "i_evt": list(range(len(clock_reader.x))),
        "segment_time": ref_trigger_times,
        "channel": np.stack(
            [oscilliscope_reference_reader.y, 
             mcp_reader.y, 
             clock_reader.y], 
            axis=1),
        "time": clock_reader.x,
        "timeoffsets": np.stack(
            [ref_horz_offset-ref_horz_offset, 
             mcp_horz_offset-ref_horz_offset, 
             clock_horz_offset-ref_horz_offset], 
            axis=1)
    })

    # take both of these and make one awkward array whose fields match the root file branches

def consolidate_acquisition(output_file_path: str, etroc_binary_paths: list[str], mcp_binary_path: str, clock_binary_path: str, oscilliscope_reference_path: str):
    def convert_etroc_binary() -> ak.Array:
        first_binary_convert = etroc.converter(etroc_binary_paths, skip_trigger_check=True)
        return etroc.root_dumper(first_binary_convert) # root dumper name is due to history 

    def convert_oscilliscope_reference() -> ak.Array:
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

    print("Performing fit on MCP")
    mcp_fit_data = mcp.fit(generate_old_awk_array(
        oscilliscope_reference_wavefrom, mcp_waveform, clock_waveform
    ))

    print("Performing Clock Wavefrom Fits")
    clock_timestamps = clock.calc_clock(
        clock_waveform.x, clock_waveform.y,
        CLOCK_THRESH_LOW, CLOCK_THRESH_HIGH, CLOCK_MEAUREMENT_POINT
    )

    print("Converting ETROC Binary")
    etroc_data = convert_etroc_binary()
    etroc_data_map = dict(zip(
        ak.fields(etroc_data), ak.unzip(etroc_data)
    ))
    
    # merged_data_map = mcp_fit_map | mcp_map |  etroc_data_map
    
    # merged_data_map['Clock'] = clock_timestamps

    # with uproot.recreate(output_file_path) as output:
    #     output["pulse"] = merged_data_map


wf = consolidate_acquisition(
    "run_6000_new.root"
    ["unit_test/input_data/run_6000/output_run_6000_rb0.dat", 
     "unit_test/input_data/run_6000/output_run_6000_rb1.dat", 
     "unit_test/input_data/run_6000/output_run_6000_rb2.dat"],
     "/home/users/hswanson13/ETL_TestingDAQ/unit_test/input_data/run_6000/C2--Trace6000.trc", #MCP
     "/home/users/hswanson13/ETL_TestingDAQ/unit_test/input_data/run_6000/C3--Trace6000.trc"  #CLOCK
)

