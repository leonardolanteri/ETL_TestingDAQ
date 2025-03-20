export TAMALERO_BASE=$PWD/module_test_sw
export TEST_BEAM_BASE=$PWD
export PYTHONPATH=$PYTHONPATH:$PWD
export PYTHONPATH=$PYTHONPATH:$TAMALERO_BASE
export PYTHONIOENCODING=utf8
echo "Set PYTHONPATH"
echo $PYTHONPATH
echo "Set LD_LIBRARY"
echo $LD_LIBRARY_PATH

# #If you do it the preinstall way (SAFEST)
export PYTHONPATH=$PYTHONPATH:/home/etl/ipbus-software/uhal/python/pkg/
export LD_LIBRARY_PATH=/opt/cactus/lib:$LD_LIBRARY_PATH

# #If you do it conda package way (POTENTIALLY CONVIENENT)
# conda install hswanson::ipbus-uhal2
# #This is needed to get the binaries
# LD_LIBRARY_PATH=$CONDA_PREFIX/opt/cactus/lib/lib/:$LD_LIBRARY_PATH



#sudo mount -t cifs //192.168.0.6/Waveforms /home/etl/Test_Stand/daq/LecroyMount -o user=mothra,uid=etl,gid=etl,vers=2.0