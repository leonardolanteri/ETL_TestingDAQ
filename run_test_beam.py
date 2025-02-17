import subprocess
from pathlib import Path
from test_beam.config import TBConfig, Oscilliscope, ChannelConfig, TriggerConfig, RunConfig, TelescopeConfig
from functools import wraps
from test_beam.tamalero_interface import ETL_Telescope
from lecroy import LecroyController
import time
from typing import List

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
    def setup_trigger(trigger_config: TriggerConfig):
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
            setup_trigger(chnl_config.trigger)

# def setup_etl_telescope(etl_telescope: ETL_Telescope, run_config: RunConfig, telescope_config: TelescopeConfig, thresholds_filename_prefix: str = None):
#     for sh in telescope_config.service_hybrids:
#         etl_telescope.add_readout_board(sh.readout_board_config, sh.readout_board_id)
#     etl_telescope.check_all_rb_configured()

#     etl_telescope.check_VTRXs()

#     for sh in telescope_config.service_hybrids:
#         etl_telescope.connect_module(sh.readout_board_id, sh.module_select)

#     etl_telescope.configure_ETROCs(
#         l1a_delay  = run_config.l1a_delay, 
#         offset     = run_config.offset,
#         power_mode = run_config.power_mode,
#         reuse_thresholds_dir = run_config.thresholds_directory,
#         thresholds_filename_prefix = thresholds_filename_prefix)

#     etl_telescope.test_etroc_daq()

class RunKcuStream:
    """
    Syncs daq steps for the scope and etroc. 
    """
    def __init__(self, kcu_ipadress: str, readout_board_ids:List[int], project_dir: Path):
        self.kcu_ip_address = kcu_ipadress
        self.project_dir = project_dir
        self.readout_board_ids = readout_board_ids
        self.run_number_path  = project_dir / Path('etroc/next_run_number.txt')
        self.is_scope_acquiring_path = project_dir / Path('etroc/is_scope_acquiring.txt')

    # These are so the flags are always set to false when entering and exiting!
    def __enter__(self):
        self.is_scope_acquiring = False
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.is_scope_acquiring = False

    @property
    def etroc_daq_command(self) -> List[str]:
        etroc_daq_script = self.project_dir / Path('etroc/daq.py')
        return ['/usr/bin/python3', str(etroc_daq_script), 
            '--l1a_rate', '0', 
            '--ext_l1a', 
            '--kcu', self.kcu_ip_address, 
            '--rb', ",".join(self.readout_board_ids), # do comma seperated for each rb
            '--run', str(get_run_number(self.project_dir/Path('etroc/next_run_number.txt'))), 
            '--lock', str(self.is_scope_acquiring_path)] # lock waits for scope to be ready

    def setup(self) -> None:
        etroc_daq_process = subprocess.Popen(['/usr/bin/python3', 'etroc/test.py']) #self.etroc_daq_command
        #etroc_daq.wait()
        if etroc_daq_process.returncode != 0: # Check for errors
            raise RuntimeError(f"ETROC DAQ process failed with return code {etroc_daq_process.returncode}")

    @property
    def is_scope_acquiring(self) -> bool:
        return self.get_status(self.is_scope_acquiring_path)

    @is_scope_acquiring.setter
    def is_scope_acquiring(self, status: bool):
        self._is_scope_acquiring = self.set_status(self.is_scope_acquiring_path, status)

    @staticmethod
    @ensure_path_exists
    def get_status(path: Path) -> bool:
        with open(path) as file:
            status = file.read().strip()
        return status == "True"
    
    @staticmethod
    @ensure_path_exists
    def set_status(path: Path, status: bool):
        with open(path, "w") as f:
            value = "True" if status else "False"
            f.write(value)
            f.truncate()
        return value == "True"
    
import tomli
with open('test_beam.toml', 'rb') as f:
    data = tomli.load(f)

tb_config = TBConfig.model_validate(data)
scope_config = tb_config.oscilloscope
project_dir = tb_config.test_beam.project_directory
run_start = get_run_number(project_dir / Path('etroc/next_run_number.txt'))
run_stop = run_start + tb_config.run_config.num_runs

# etl_telescope = ETL_Telescope(tb_config.run_config.kcu_ip_address)
# setup_etl_telescope(
#     etl_telescope, 
#     tb_config.run_config, 
#     tb_config.telescope_config, 
#     thresholds_filename_prefix=f"runs_{run_start}_{run_stop}_")

active_channels = [chnl_num for chnl_num in scope_config.channels]
with LecroyController(scope_config.ip_address, active_channels=active_channels) as lecroy:
    setup_scope(lecroy, scope_config)

    exit()
    # with RunKcuStream(tb_config) as kcu_stream:
    #     kcu_stream.setup()
    #     #allow for all the streams to reach the locked point
    #     # I dont like this logic, could instead let kcu stream know when all are ready!
    #     # or import and set up the streams in here!
    #     time.sleep(3) 
    #     kcu_stream.is_scope_acquiring = True
    #     lecroy.do_acquisition()

    # need to output to csv with information


# Test Start Up
# -> verify it works atleat runs etc...
# First check thresholds are saved correctly


# Do threshold scan, set thresholds at baseline