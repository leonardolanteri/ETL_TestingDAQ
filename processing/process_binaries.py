"""
Decodes the ETROC and Oscilliscope binary

Simple processing routine that uses multiprocessing
Please watch this video if you are new to multiprocessing:
https://www.youtube.com/watch?v=X7vBbelRXn0 
"""
from lecroy_binary_decoder import LecroyReader
from etroc_binary_decoder import converter, root_dumper

import logging
import time
from multiprocessing import Pool
from pathlib import Path
from typing import List
import awkward as ak
import uproot
import json
import traceback
import base64

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def consolidate_acquisition(output_file_path: str, etroc_binary_paths: List[str]=None, mcp_binary_path: str=None, clock_binary_path: str=None, run_log_path:str = None):
    t_file_reads = time.perf_counter()
    mcp_waveform = LecroyReader(mcp_binary_path)
    clock_waveform = LecroyReader(clock_binary_path)
    etroc_unpacked_data = converter(etroc_binary_paths, skip_trigger_check=True)
    etroc_data = root_dumper(etroc_unpacked_data) # root dumper name is due to history 
    if etroc_data is None:
        print(f"no etroc data from {etroc_binary_paths}")
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

    with open(run_log_path, "r") as f:
        run_log = json.load(f)

    with uproot.recreate(output_file_path) as output:
        # Store Merged data
        etroc_data.update(oscillicsope_waveforms) #oscillicsope_waveforms | etroc_data
        output["pulse"] = etroc_data
        
        # Store Binary in root file
        binary_paths = list(
            map(Path, etroc_binary_paths)) + [ Path(mcp_binary_path), Path(clock_binary_path)]
        for bin_path in binary_paths:
            output['binary-file-'+bin_path.name] = base64.b64encode(bin_path.read_bytes()).decode('utf-8')
        # Store Run Log
        output["run_log"] = json.dumps(run_log)
        logger.debug(f"THIS IS THE RUN LOG: {run_log}")

        # logger.debug(ak.Array(etroc_data['event']))
        # logger.debug(ak.Array(oscillicsope_waveforms['mcp_volts']))
        N_events_etroc = len(etroc_data['event'])
        N_events_scope = len(oscillicsope_waveforms['mcp_volts'])
        if N_events_etroc != N_events_scope:
            logger.error(f"The length of the branches doesn't match for run: {output_file_path}, {N_events_etroc} vs {N_events_scope}")
    
    logger.info(f"WRITE FILE TOOK {(time.perf_counter()-t_write_files):.2f} seconds")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Process ETROC and Oscilloscope binaries.")
    parser.add_argument('--run_start', type=int, required=True, help='Start run number')
    parser.add_argument('--run_stop', type=int, required=True, help='Stop run number')
    parser.add_argument('--output_dir', type=Path, help='Output directory')
    parser.add_argument('--mcp_channel', type=int, default=2, help='Channel number of the mcp')
    parser.add_argument('--clock_channel', type=int, default=3, help='Channel number of the clock')
    parser.add_argument('--trace_binary_dir', type=Path, help='Directory of trace files (mcp and clock)')
    parser.add_argument('--etroc_binary_dir', type=Path, help='Directory of etroc files')
    parser.add_argument('--run_log_path', type=Path, help='Directory of the run log that contains the used config and run condition information')
    parser.add_argument('--processes', type=int, default=3, help='Number of multiprocesses to spawn')
    parser.add_argument('--overwrite', action="store_true", help='Will overwrite any already merged files. Otherwise it skips them.')
    args = parser.parse_args()
    
    # /eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/LecroyRaw/
    # /eos/uscms/store/group/cmstestbeam/ETL_DESY_March_2024/rawDat/
    if not args.output_dir.is_dir():
        raise ValueError(f"Your output dir does not exist or is not a directory: {args.output_dir}")
    if not args.trace_binary_dir.is_dir():
        raise ValueError(f"Your inputted trace binary directory does not exist or is not a directory: {args.trace_binary_dir}")
    if not args.etroc_binary_dir.is_dir():
        raise ValueError(f"Your inputted etroc binary directory does not exist or is not a directory: {args.etroc_binary_dir}")
    
    trace_path  = lambda chnl, run: args.trace_binary_dir/Path(f"C{chnl}--Trace{run}.trc")
    etroc_path  = lambda run: args.etroc_binary_dir/Path(f"output_run_{run}_rb0.dat")
    output_path = lambda run: args.output_dir/Path(f"run_{run}.root")

    def consolidate_acquisition_task(run):
        if output_path(run).is_file() and not args.overwrite:
            logger.info(f"The file: {output_path(run)}, is already created.")
            return
        logger.info(f'Consolidating run: {run}')
        try:
            consolidate_acquisition(
                output_path(run),
                etroc_binary_paths=[etroc_path(run)],
                mcp_binary_path=trace_path(args.mcp_channel, run),
                clock_binary_path=trace_path(args.clock_channel, run),
                run_log_path=args.run_log_path,
            )
        except Exception as e:
            logger.error(f"AN ERROR HAS OCCURED DURING CONVERSION!: {e}")
            logger.error(traceback.format_exc())

    t_consolidated = time.perf_counter()
    with Pool(processes=args.processes) as pool:
        results = pool.imap_unordered(
            consolidate_acquisition_task, range(args.run_start, args.run_stop + 1)
        )
        for _ in results:
            pass

    logger.info(f"COMPLETED IN: {(time.perf_counter()-t_consolidated):.2f} seconds")

