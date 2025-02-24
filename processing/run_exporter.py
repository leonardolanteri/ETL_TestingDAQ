#!/usr/bin/env python3
import os
import glob

with open('exported_runs.log','r') as f:
    run_log=f.readlines()

skip_list = []
for run in run_log:
   skip_list.append(run.split("\n")[0])

local_path = "ScopeHandler/ScopeData"
fnal_path  = "ireed@cmslpc339.fnal.gov:/eos/uscms/store/group/cmstestbeam/ETL_SPS_Oct_2024"

local_files = glob.glob("{}/ETROCData/output_run*rb0.root".format(local_path))
local_files.sort()
print("Found {} total runs".format(len(local_files)))
print("{} runs have already been exported".format((len(run_log))))

for run in local_files:
    num = run.split("run_")[1].split("_rb0")[0]
    if (num in skip_list) or (int(num) < 10110):
        print("--------------------")
        print("Run {} has already been exported".format(num))
        continue
 
    if ((int(num) % 10) == 0):
        with open('exported_runs.log', 'w') as f:
            f.writelines(run_log)

    print("------------")
    print("Moving run {} files from the test stand to LPC".format(num))

    os.system(f'scp module_test_sw/ETROC_output/output_run_{num}_rb0.dat  {fnal_path}/ETROC_output')
    os.system(f'scp {local_path}/ETROCData/output_run_{num}_rb0.root      {fnal_path}/ETROCData')
    os.system(f'scp {local_path}/LecroyConverted/converted_run{num}.root  {fnal_path}/LecroyConverted')
    os.system(f'scp {local_path}/LecroyMerged/run_{num}.root              {fnal_path}/LecroyMerged')
    os.system(f'scp {local_path}/LecroyRaw/C1--Trace{num}.trc             {fnal_path}/LecroyRaw')
    os.system(f'scp {local_path}/LecroyRaw/C2--Trace{num}.trc             {fnal_path}/LecroyRaw')
    os.system(f'scp {local_path}/LecroyRaw/C3--Trace{num}.trc             {fnal_path}/LecroyRaw')
    os.system(f'scp {local_path}/LecroyRaw/C4--Trace{num}.trc             {fnal_path}/LecroyRaw')
    os.system(f'scp {local_path}/LecroyTimingDAQ/run_scope{num}.root      {fnal_path}/LecroyTimingDAQ')
    os.system(f'scp {local_path}/Telescope/tracks_run{num}.root           {fnal_path}/Telescope')
    run_log.append(num+"\n")
