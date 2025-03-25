export TAMALERO_BASE=$PWD/module_test_sw
export TEST_BEAM_BASE=$PWD
export PYTHONPATH=$PYTHONPATH:$PWD
export PYTHONPATH=$PYTHONPATH:$TAMALERO_BASE
export PYTHONIOENCODING=utf8


# Check if the file exists
SETUP_FILE="local_setup.sh"
if [ -f "$SETUP_FILE" ]; then
    source "$SETUP_FILE"
else
    echo "Error: '$SETUP_FILE' not found. Please set up the '$SETUP_FILE' file; see the README for details."
    exit 1
fi

echo "Set PYTHONPATH"
echo $PYTHONPATH
echo "Set LD_LIBRARY_PATH"
echo $LD_LIBRARY_PATH
echo "Set CERNBOX_HOST"
echo $CERNBOX_HOST

#sudo mount -t cifs //192.168.0.6/Waveforms /home/etl/Test_Stand/daq/LecroyMount -o user=mothra,uid=etl,gid=etl,vers=2.0