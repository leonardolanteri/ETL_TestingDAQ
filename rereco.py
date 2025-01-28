"""
Simple rereco routine that uses asyncio

Please watch this video if you are new to multiprocessing:
https://www.youtube.com/watch?v=X7vBbelRXn0 
"""
from pathlib import Path
from consolidate_acquisition import consolidate_acquisition
# idea is to get it darn fast with multithreading
from multiprocessing import Pool
import asyncio
import logging
import time
logging.basicConfig(level=logging.ERROR)

trace_file = lambda chnl, run: Path(f'/media/etl/Storage/SPS_October_2024/LecroyRaw/C{chnl}--Trace{run}.trc')
etroc_file = lambda run: Path(f"/home/etl/Test_Stand/module_test_sw/ETROC_output/output_run_{run}_rb0.dat")

MCP_channel = 2
CLK_channel = 3

output_file_dir = Path(f"rereco_data2")
output_file_dir.parent.mkdir(parents=True, exist_ok=True)
output_file = lambda run: Path(f"run_{run}.root")

run_start = 12011
run_stop = 12110

def consolidate_acquisition_task(run):
    print(f'Consolidating run: {run}')
    consolidate_acquisition(
        output_file_dir / output_file(run),
        etroc_binary_paths=[etroc_file(run)],
        mcp_binary_path=trace_file(MCP_channel, run),
        clock_binary_path=trace_file(CLK_channel, run),
        oscilliscope_reference_path=trace_file(MCP_channel, run)
    )

t_consolidated = time.perf_counter()
with Pool() as pool:
    results = pool.imap_unordered(
        consolidate_acquisition_task, range(run_start, run_stop + 1)
    )

    for _ in results:
        ...

print(f"COMPLETED IN: {(time.perf_counter()-t_consolidated):.2f} seconds")