import subprocess
from pathlib import Path
from test_beam_config import Config as TBConfig
from functools import wraps
import time

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
    @property
    def scope_daq_command(self) -> list[str]:
        # need to still pass in the configurable output directory for binaries!
        scope_daq_script = self.tb_config.project_directory / Path('daq/lecroy.py')
        return [
            '/usr/bin/python3', str(scope_daq_script), 
            '--runNum', str(self.run_number), 
            '--numEvents',  str(self.tb_config.run_config.num_events),
            '--sampleRate', str(self.tb_config.oscilloscope.sample_rate), 
            '--horizontalWindow', str(self.tb_config.oscilloscope.horizontal_window), 
            '--trigCh',     self.tb_config.oscilloscope.mcp_channel, 
            '--trig',       str(self.tb_config.oscilloscope.trigger), 
            '--vScale2',    str(self.tb_config.oscilloscope.v_scale_2), 
            '--vScale4',    str(self.tb_config.oscilloscope.v_scale_3), 
            '--vPos2',      str(self.tb_config.oscilloscope.v_position_2), 
            '--vPos3',      str(self.tb_config.oscilloscope.v_position_3), 
            '--timeoffset', str(self.tb_config.oscilloscope.time_offset), 
            '--trigSlope',  self.tb_config.oscilloscope.trigger_slope,
            '--display', "1",
            '--lock', str(self.etroc_ready_path),
            '--ip_address', str(tb_config.oscilloscope.ip_address),
            '--run_log_path', str(tb_config.test_beam.project_directory / Path('daq/RunLog.txt'))
            ]

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
    

# ---Initialize the set up--- #
# telescope_script = tb_config.project_directory / Path('telescope.py')
# subprocess.run([
#     '/usr/bin/python3', str(telescope_script),
#     '--configuration', 'cern_1', # make this generated by tb_config I think  or have a function above do it!
#     '--kcu', tb_config.run_config.kcu_ip_address,
#     '--offset', str(tb_config.run_config.offset),
#     '--delay', str(tb_config.run_config.l1a_delay)
# ])

# # Run poke_board.py script with dark_mode
# poke_board_script = tb_config.project_directory / Path('poke_board.py')
# subprocess.run([
#     '/usr/bin/python3', str(poke_board_script),
#     '--configuration', 'modulev1',
#     '--etrocs', '2',
#     '--kcu', tb_config.run_config.kcu_ip_address,
#     '--dark_mode'
# ])

import tomllib
with open('test_beam.toml', 'rb') as f:
    data = tomllib.load(f)

tb_config = TBConfig.model_validate(data)
proj_dir = tb_config.test_beam.project_directory
service_hybrids = tb_config.telescope_setup.service_hybrids


import os
import glob
from emoji import emojize
import argparse

from yaml import load, CLoader as Loader, CDumper as Dumper
from module_test_sw.tamalero.ReadoutBoard import ReadoutBoard
from module_test_sw.tamalero.utils import get_kcu, load_yaml, header
from module_test_sw.tamalero.FIFO import FIFO
from module_test_sw.tamalero.DataFrame import DataFrame

thresholds_dir = "" # these should be saved out somewhere!
reuse_thresholds = False


print("Getting the KCU")
kcu = get_kcu(tb_config.run_config.kcu_ip_address, control_hub=True, verbose=True)

print("Configuring Readout Boards")
for service_hybrid in service_hybrids:
    service_hybrid.readout_board = ReadoutBoard(
        rb      = service_hybrid.readout_board_name, 
        trigger = True, 
        kcu     = kcu, 
        config  = service_hybrid.module_config_name, 
        verbose = False
    )

header(configured=all(rb for rb in service_hybrids.readout_board.configured))

print("Power up init sequence for: DAQ")
for service_hybrid in service_hybrids:
    rb: ReadoutBoard = service_hybrid.readout_board

    # VTRX Power Up
    rb.VTRX.get_version()
    print(f"VTRX Version {rb.VTRX.ver}")
    print("VTRX status at power up:")
    rb.VTRX.status()

    # Trigger LpGBT
    rb.get_trigger()
    print(" > Power up init sequence for: Trigger")
    rb.TRIG_LPGBT.power_up_init()
    print("Done Configuring Trigger lpGBT")


# Connect modules
print("Connecting Modules")
for service_hybrid in service_hybrids:
    rb: ReadoutBoard = service_hybrid.readout_board

    moduleids = [mod_slot[0] if len(mod_slot)>0 else 0 for mod_slot in service_hybrid.modules]
    print(moduleids)
    rb.connect_modules(moduleids=moduleids)

    for mod in rb.modules:
        mod.show_status()


# Connect modules
print("Connecting Modules")
for service_hybrid in service_hybrids:
    rb: ReadoutBoard = service_hybrid.readout_board
    run_config = tb_config.run_config
    for mod in rb.modules:
        if mod.connected:
            for etroc in mod.ETROCs:
                if reuse_thresholds:
                    with open(f'{thresholds_dir}/thresholds_module_{etroc.module_id}_etroc_{etroc.chip_no}.yaml', 'r') as f:
                        thresholds = load(f, Loader=Loader)
                    etroc.physics_config(
                        offset=run_config.offset, 
                        L1Adelay=run_config.l1a_delay, 
                        thresholds=thresholds, 
                        powerMode=run_config.power_mode
                    )
                else:
                    etroc.physics_config(
                        offset = run_config.offset, 
                        L1Adelay = run_config.l1a_delay, 
                        thresholds = None, # this runs a threshold scan and saves it to outdir
                        out_dir = thresholds_dir, 
                        powerMode = run_config.power_mode)
            for etroc in mod.ETROCs:
                etroc.reset()

# fifos
fifos: list[FIFO] = []
for service_hybrid in service_hybrids:
    rb: ReadoutBoard = service_hybrid.readout_board    
    fifos.append(FIFO(rb))

df = DataFrame("ETROC2")

fifos[0].send_l1a(1)
for fifo in fifos:
    fifo.reset()

for service_hybrid in service_hybrids:
    rb: ReadoutBoard = service_hybrid.readout_board  
    for mod in rb.modules:
        for etroc in mod.ETROCs:
            etroc.reset()

print(emojize(':factory:'), " Producing some test data")
fifos[0].send_l1a(10)

for i, fifo in enumerate(fifos):
    print(emojize(':closed_mailbox_with_raised_flag:'), f" Data in FIFO {i}:")
    for x in fifos[i].pretty_read(df):
        print(x)

rb.DAQ_LPGBT.set_configured()

if rb.ver > 1:
    rb.is_configured()
    t_end = time.time() + 10
    from module_test_sw.tamalero.Monitoring import Monitoring, blink_rhett

    print("RB configured successfully. Rhett is happy " + emojize(":dog_face:"))
    rb.disable_rhett()
    time.sleep(0.5)
    rb.enable_rhett()
    time.sleep(0.5)
    rb.disable_rhett()
    time.sleep(0.5)
    rb.enable_rhett()


with RunSession(tb_config) as run:
    print(f"Starting run {run.run_number}")
    print(f"{run.is_etroc_ready=}, {run.is_scope_ready=}")
    run.execute()


