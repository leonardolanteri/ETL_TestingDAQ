#!/bin/bash
index=`cat ScopeHandler/Lecroy/Acquisition/next_run_number.txt`

#i/usr/bin/python3 telescope.py -- --kcu 192.168.0.10 --offset $2 --delay 32
echo -n "True" > $TAMALERO_BASE/running_ETROC_acquisition.txt

pwd
cd module_test_sw
(/usr/bin/python3 daq.py --l1a_rate 0 --ext_l1a --kcu 192.168.0.10 --rb 0 --run $index --lock "../ScopeHandler/Lecroy/Acquisition/running_acquisition.txt") &
(sleep 15


cd ..

echo $1
echo $2
echo $3 
echo $4
echo $5
echo $6
echo $7
echo $8
echo $9
echo $10
echo $11
echo $12

pwd
/usr/bin/python3 ScopeHandler/Lecroy/Acquisition/acquisition_wrapper.py --nevents $1 --sample_rate $3 --horizontal_window $4 --trigger_channel $5 --trigger $6 --v_scale_2 $7  --v_scale_3 $8 --v_position_2 $9 --v_position_3 ${10} --time_offset ${11} --trigger_slope ${12})


/usr/bin/python3 data_dumper.py --input "../ScopeHandler/ScopeData/ETROC_output/output_run_${index}_rb0.dat" --rbs 0 --skip_trigger_check

# remember: 0,1,2
#/usr/bin/python3 root_dumper.py --input ${index} #_rb0 # Run in other shell with root configured
echo -n "False" > $TAMALERO_BASE/running_ETROC_acquisition.txt
echo -n "True" > $TAMALERO_BASE/merging.txt
echo -n "True" > ScopeHandler/Lecroy/Acquisition/merging.txt
