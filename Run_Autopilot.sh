#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;36m'
NC='\033[0m'
nicerStatus(){
    if [ ${2} == "True" ]; then
        echo -e "${1}${GREEN}True${NC}"
    else
        echo -e "${1}${RED}False${NC}"
    fi
}

valFinder(){
    IFS='['
    read -ra parts <<< "$1"
    IFS=']'
    read -ra chan <<< ${parts[4]}
    read -ra var <<< ${parts[5]}
    read -ra value <<< ${parts[6]}
}

biasHelper(){
    staleLog=true
    if ! [[ -n $(find $HOME -amin -5 -iname 'CAENGECO2020.log') ]]; then
        echo "Stale HV log file, check HV supply status"
    else
        staleLog=false
    fi
    IFS=$'\r\n'
    command eval 'lines=($(tail $HOME/CAENGECO2020.log))'
    #check for "ch [3]" and "VMon"
    for ((j=${#ljnes[@]}-1; j>=0; j--)); do
        valFinder "${lines[$j]}"
        if [[ ${chan[0]} == '3' ]] && [[ ${var[0]} == 'VMon' ]]; then
            break
        fi
    done
    #round to nearest 5
    biasV=$(awk '{print $1}' <<< ${value[0]})
    biasV=$(echo $biasV | awk '{print int(($biasV / 5) + 0.5) * 5}')
}

# 2) Threshold offset
# 3) Number of events
# 4) The number of the PCb board, use "-" to separate boards id in multilayer setup
# 5) Wirebonded/Bump-bonded wb or bb
# 6) Beam energy
# 7) tracker
# 8) ETROC Power mode: i1,i2,i3,i4
# 9) Multilayer setup

offset=$2 # vth
n_events=$3
board_number=$4
bond=$5
energy=$6
isTrack=$7
powerMode=$8 # I1 (high) to I4 (low)
isMulti=$9
run_number=`cat ScopeHandler/Lecroy/Acquisition/next_run_number.txt`

echo -e "Starting configuration for run $run_number on KCU. ${RED}Turn beam OFF!!${NC}"
cd module_test_sw
source setup.sh
/usr/bin/python3 telescope.py  --configuration cern_1 --kcu 192.168.0.10 --offset $3 --delay 14 
#/usr/bin/python3 poke_board.py --configuration modulev1 --etrocs 0 --kcu 192.168.0.10 --dark_mode --mask telescope_config_data/cern_test_2024-05-13-20-07-26/noise_width_module_106_etroc_2.yaml
/usr/bin/python3 poke_board.py --configuration modulev1 --etrocs 2 --kcu 192.168.0.10 --dark_mode
cd ..

if [ "$isTrack" = true ]
then
    echo -e "You are starting a telescope run. Have you entered the run number ${BLUE}$run_number${NC} on telescope? And turn ${RED}BEAM ON${NC} now"
    read dummy
fi

scope_path="ScopeHandler/Lecroy/"
merging_dir="ScopeHandler/ScopeData/LecroyMerged/"

# Scope variables
sample_rate=20 #GHz
horizontal_window=50 #ns
trigger_channel="C2"
trigger="-0.3" #V
v_scale_2=0.2
v_scale_3=0.2
v_position_2=3
v_position_3="-3"
time_offset=0
trigger_slope="NEG"

for (( i = 1; i <= $1; i++ )); do
    run_number=`cat ScopeHandler/Lecroy/Acquisition/next_run_number.txt`
    echo -e "---------------------------------"
    echo -e "Batch Run ${i} of ${1}"
    echo -e "Overall Run Number: ${run_number}"
    echo -e "---------------------------------"
    #TODO: add a reminder to confirm bias channel of HV
    biasHelper
    if $staleLog; then
        echo -e "${RED}ERROR: The HV log file has not been update for more than 5 minutes${NC}"
        echo -e "${RED}ERROR${NC}: Path to HV file: ${BLUE}$HOME/CAENGECO2020.log${NC}"
        echo -e "${RED}ERROR: Check that the HV supply has not tripped${NC}"
    fi

    #/usr/bin/python3 poke_board.py --configuration modulev0b --etrocs 0  --kcu 192.168.0.10 --rb 1 --bitslip
    #/usr/bin/python3 poke_board.py --configuration modulev1  --etrocs 2  --kcu 192.168.0.10 --rb 2 --bitslip
    #/usr/bin/python3 poke_board.py --configuration modulev1  --etrocs 2  --kcu 192.168.0.10 --rb 1 --bitslip
    ./autopilot.sh $n_events $offset $sample_rate $horizontal_window $trigger_channel $trigger $v_scale_2 $v_scale_3 $v_position_2 $v_position_3 $time_offset $trigger_slope

    cd module_test_sw
    temperature=$(/usr/bin/python3 poke_board.py --configuration modulev1 --etrocs 2 --rbs 0 --modules 1 --kcu 192.168.0.10 --temperature)
    cd ..

    sleep 7s
    kcu=`cat ${TAMALERO_BASE}/running_ETROC_acquisition.txt`
    scope=`cat ${scope_path}Acquisition/running_acquisition.txt`
    conversion=`cat ${scope_path}Conversion/ongoing_conversion.txt`
    merging=`cat ${scope_path}Merging/ongoing_merging.txt`
    nicerStatus "Running ETROC acquisition: " $kcu
    nicerStatus "Running SCOPE acquisition: " $scope
    nicerStatus "Converting files:          " $conversion
    nicerStatus "Merging files:             " $merging

    while [ $kcu == "True" ] || [ $scope == "True" ] || [ $conversion == "True" ] || [ $merging == "True" ]; do
        echo "Waiting..."
        sleep 1s
        kcu=`cat ${TAMALERO_BASE}/running_ETROC_acquisition.txt`
        scope=`cat ${scope_path}Acquisition/running_acquisition.txt`
        conversion=`cat ${scope_path}Conversion/ongoing_conversion.txt`
        merging=`cat ${scope_path}Merging/ongoing_merging.txt`
        nicerStatus "Running ETROC acquisition: " $kcu
        nicerStatus "Running SCOPE acquisition: " $scope
        nicerStatus "Converting files:          " $conversion
        nicerStatus "Merging files:             " $merging
    done

    test_successful=`test "$merging_dir/run_$run_number.root"`

    printf "$run_number,$biasV,$offset,$n_events,$board_number,$bond,$energy,`date -u`,$isTrack,$powerMode,$temperature,$isMulti,$sample_rate,$horizontal_window,$trigger_channel,$trigger,$v_scale_2,$v_scale_3,$v_position_2,$v_position_3,$time_offset,$trigger_slope\n">>./run_log_SPS_Oct2024.csv
done
