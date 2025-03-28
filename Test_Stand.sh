source source /cvmfs/sft.cern.ch/lcg/releases/LCG_99/ROOT/v6.22.06/x86_64-ubuntu2004-gcc9-opt/bin/thisroot.sh
source vivado.sh
cd ${HOME}/Test_Stand/etl_test_fw-v3.2.0/program.sh
source program.sh
cd ${HOME}/Test_Stand/ETL_TestingDAQ/module_test_sw/
source setup.sh
/opt/cactus/bin/controlhub_start
PROMPT_COMMAND='echo -en "\033]0; Tamalero \a"'
echo "\n"
echo "Please turn on the readout board, using this command:"
echo "ipython test_tamalero.py -- --control_hub --kcu 192.168.0.10 --verbose --configuration modulev0b --power_up"
echo "\n"
echo "And check if lpGBT gates are locked:"
echo "ipython -i test_ETROC.py -- --test_chip --hard_reset --partial --configuration modulev0b --module 1"
