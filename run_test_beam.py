import sys
# This is very important, sometimes the python path gets confused
for py_path in sys.path:
    if "module_test_sw" in py_path and "ETL_TestingDAQ" not in py_path:
        print("COME ON MAN!!! the yucky is in there!")
        sys.path.remove("/home/etl/Test_Stand/module_test_sw")

from pathlib import Path
from config import TBConfig, Oscilliscope, ChannelConfig, TriggerConfig, RunConfig, TelescopeConfig
from functools import wraps
from test_beam.etl_telescope import ETL_Telescope
from lecroy import LecroyController
from test_beam.etl_telescope import KcuStream
import time

def ensure_path_exists(func):
    @wraps(func)
    def wrapper(path: Path, *args, **kwargs):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        return func(path, *args, **kwargs)
    return wrapper

def get_run_number(run_number_path: Path):
    with open(run_number_path, 'r') as file:
        run_number = file.read().strip()
    return int(run_number)

#---------------- SETUPs BASED ON CONFIG --------------------------#
def setup_scope(lecroy: LecroyController, scope_config: Oscilliscope):
    """
    Takes the configs and sets up and setups up the oscilliscope based on the config values
    """
    def setup_trigger(chnl_num:int, trigger_config: TriggerConfig):
        """Sets up trigger channel based on trigger config"""
        lecroy.set_trigger_mode(trigger_config.mode)
        lecroy.set_trigger_select(
            lecroy.channels[chnl_num], 
            condition=trigger_config.condition, 
            level=trigger_config.level, 
            units=trigger_config.units)
        lecroy.set_trigger_slope(trigger_config.slope) 

    def setup_channel(chnl_num: int, channel_config: ChannelConfig):
        """Sets up a channel based on the config"""
        vertical_axis = channel_config.vertical_axis
        lecroy.channels[chnl_num].set_vertical_axis(
            vertical_axis.lower,
            vertical_axis.upper, 
            units=vertical_axis.units)
        lecroy.channels[chnl_num].set_coupling(channel_config.coupling)

    lecroy.set_sample_rate(scope_config.sample_rate[0]) #take first elem because second is the units...
    horz_window, units = scope_config.horizontal_window
    lecroy.set_horizontal_window(horz_window, units=units)
    lecroy.set_sample_mode(scope_config.sample_mode)
    lecroy.set_number_of_segments(scope_config.number_of_segments)
    lecroy.set_segment_display(scope_config.segment_display) 

    for chnl_num, chnl_config in scope_config.channels.items():
        setup_channel(chnl_num, chnl_config)
        if chnl_config.trigger is not None:
            setup_trigger(chnl_num, chnl_config.trigger)


################################################################################################################################
################################-------------START OF TEST BEAM ROUTINE-------------############################################
################################################################################################################################

import tomli
with open('test_beam.toml', 'rb') as f:
    data = tomli.load(f)
tb_config = TBConfig.model_validate(data)

project_dir = tb_config.test_beam.project_directory
run_start = get_run_number(project_dir / Path('etroc/next_run_number.txt'))
run_stop = run_start + tb_config.run_config.num_runs

# initializes the electronics!
etl_telescope = ETL_Telescope(tb_config.telescope_config, thresholds_filename_prefix=f"Run_{run_start}_{run_stop}_")

scope_config = tb_config.oscilloscope
active_channels = [chnl_num for chnl_num in scope_config.channels]
with LecroyController(scope_config.ip_address, active_channels=active_channels) as lecroy:
    setup_scope(lecroy, scope_config)
    
    beam_on = input("Need somebody to turn the beam on! Is it on? (y/n/abort)")
    kcu_ip_address = tb_config.telescope_config.kcu_ip_address
    rb_ids = list(etl_telescope.readout_boards.keys())
    binary_dir = tb_config.telescope_config.etroc_binary_data_directory
    with KcuStream(kcu_ip_address, rb_ids, project_dir, binary_dir) as kcu_stream:
        kcu_stream.startup()
        #allow for all the streams to reach the locked point
        # I dont like this logic, could instead let kcu stream know when all are ready!
        # or import and set up the streams in here!

        print("sleeping for 5 seconds to make sure processes are done!")
        time.sleep(1) 
        kcu_stream.is_scope_acquiring = True # this should make all the streams go zoom
        print("Starting Scope acquisition!")
        lecroy.do_acquisition()
        for chnl in lecroy.channels.values(): # These are the active channels :)
            chnl.save(run_start)
    # need to output to csv with information


# Test Start Up
# -> verify it works atleat runs etc...
# First check thresholds are saved correctly


# Do threshold scan, set thresholds at baseline