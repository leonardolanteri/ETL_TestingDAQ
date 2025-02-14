import subprocess
from pathlib import Path
from test_beam_config import TBConfig
from functools import wraps
import time
from tamalero_interface import ETL_Telescope
from lecroy import LecroyController

class TestBeam:
    # is this needed? like, everything could run one after another...
    def __init__(self, config_path):
        # open config, say not implemented if it isnt a toml file
        self.config_path = config_path

        self.observers = {
            'configure_telescope': [],
            'daq': [],

        }
        ...

    def attach(self, event_type, observer):
        ...

def ensure_path_exists(func):
    @wraps(func)
    def wrapper(path: Path, *args, **kwargs):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        return func(path, *args, **kwargs)
    return wrapper

class RunSession:
    """
    Syncs daq steps for the scope and etroc. 
    TODO: Instead of calling subprocess, try to import the functionality, need to test it all works first :/
    """
    def __init__(self, tb_config:TBConfig):
        self.tb_config = tb_config
        self.run_number_path  = tb_config.test_beam.project_directory / Path('daq/next_run_number.txt')
        self.etroc_ready_path = tb_config.test_beam.project_directory / Path('daq/running_ETROC_acquisition.txt')
        self.scope_ready_path = tb_config.test_beam.project_directory / Path('daq/running_acquisition.txt')

    # These are so the flags are always set to false when entering and exiting!
    def __enter__(self):
        self.is_scope_ready = False
        self.is_etroc_ready = False
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.is_scope_ready = False
        self.is_etroc_ready = False

    @property
    def etroc_daq_command(self) -> list[str]:
        etroc_daq_script = self.tb_config.test_beam.project_directory / Path('daq/etroc.py')
        return ['/usr/bin/python3', str(etroc_daq_script), 
            '--l1a_rate', '0', 
            '--ext_l1a', 
            '--kcu', self.tb_config.run_config.kcu_ip_address, 
            '--rb', '0', # why 0 here??? For multi should it be different?
            '--run', str(self.run_number), 
            '--lock', str(self.scope_ready_path)] # lock waits for scope to be ready

    def execute(self) -> None:
        etroc_daq = subprocess.Popen(['/usr/bin/python3', 'daq/test.py']) #self.etroc_daq_command
        scope_daq = subprocess.Popen(['/usr/bin/python3', 'daq/test.py']) #self.scope_daq_command

        # This lets both scope and etroc know eachother are ready for data taking
        self.is_scope_ready = True 
        self.is_etroc_ready = True 

        etroc_daq.wait()
        scope_daq.wait()

        # Check for errors
        if etroc_daq.returncode != 0:
            raise RuntimeError(f"ETROC DAQ process failed with return code {etroc_daq.returncode}")
        if scope_daq.returncode != 0:
            raise RuntimeError(f"Scope DAQ process failed with return code {scope_daq.returncode}")

    @property
    def is_etroc_ready(self) -> bool:
        return self.get_status(self.etroc_ready_path)

    @is_etroc_ready.setter
    def is_etroc_ready(self, status: bool):
        self._is_etroc_ready = self.set_status(self.etroc_ready_path, is_ready=status)

    @property
    def is_scope_ready(self) -> bool:
        return self.get_status(self.scope_ready_path)

    @is_scope_ready.setter
    def is_scope_ready(self, status: bool):
        self._is_scope_ready = self.set_status(self.scope_ready_path, is_ready=status)

    @staticmethod
    @ensure_path_exists
    def get_status(path: Path) -> bool:
        with open(path) as file:
            status = file.read().strip()
        return status == "True"
    
    @staticmethod
    @ensure_path_exists
    def set_status(path: Path, is_ready: bool = True):
        with open(path, "w") as f:
            value = "True" if is_ready else "False"
            f.write(value)
            f.truncate()
        return value == "True"

    @property   
    def run_number(self) -> int:
        with open(self.run_number_path, 'r') as file:
            run_number = file.read().strip()
        return int(run_number)
    
import tomllib
with open('test_beam.toml', 'rb') as f:
    data = tomllib.load(f)

tb_config = TBConfig.model_validate(data)
run_config = tb_config.run_config
telescope_setup = tb_config.telescope_setup
scope_config = tb_config.oscilloscope

proj_dir = tb_config.test_beam.project_directory
service_hybrids = tb_config.telescope_setup.service_hybrids

etl_telescope = ETL_Telescope(tb_config.run_config.kcu_ip_address)

for sh in telescope_setup.service_hybrids:
    etl_telescope.add_readout_board(sh.readout_board_config, sh.readout_board_id)
etl_telescope.check_all_rb_configured()

etl_telescope.check_VTRXs()

for sh in telescope_setup.service_hybrids:
    etl_telescope.connect_module(sh.readout_board_id, sh.module_select)

etl_telescope.configure_ETROCs(
    l1a_delay  = run_config.l1a_delay, 
    offset     = run_config.offset,
    power_mode = run_config.power_mode,
    reuse_thresholds_dir = run_config.reuse_thresholds_directory)

etl_telescope.test_etroc_daq()

# SCOPE SETUP
active_channels = [chnl_num for chnl_num in scope_config.channels]
with LecroyController(scope_config.ip_address, active_channels=active_channels) as lecroy:
    lecroy.set_sample_rate(scope_config.sample_rate)
    horz_window, units = scope_config.horizontal_window
    lecroy.set_horizontal_window(horz_window, units=units)
    lecroy.set_sample_mode(scope_config.sample_mode)
    lecroy.set_number_of_segments(scope_config.number_of_segments)
    lecroy.set_segment_display(scope_config.segment_display)    
    
    # Set up Channels
    for chnl_num, chnl_config in scope_config.channels.items():
        vertical_axis = chnl_config.vertical_axis
        lecroy.channels[chnl_num].set_vertical_axis(
            vertical_axis.lower,
            vertical_axis.upper, 
            units=vertical_axis.units)
        lecroy.channels[chnl_num].set_coupling(chnl_config.coupling)
        if chnl_config.trigger is not None:
            trigger_config = chnl_config.trigger
            lecroy.set_trigger_mode(trigger_config.mode)
            lecroy.set_trigger_select(
                lecroy.channels[chnl_num], 
                condition=trigger_config.condition, 
                level=trigger_config.level, 
                units=trigger_config.units)
            lecroy.set_trigger_slope(trigger_config.slope)

with RunSession(tb_config) as run:
    print(f"Starting run {run.run_number}")
    print(f"{run.is_etroc_ready=}, {run.is_scope_ready=}")
    run.execute()


