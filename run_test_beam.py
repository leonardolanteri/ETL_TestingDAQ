import subprocess
import time
import tomllib
from pathlib import Path
from test_beam_config import Config as TBConfig

with open('test_beam.toml', 'rb') as f:
    data = tomllib.load(f)
tb_config = TBConfig.model_validate(data)

run_number_path = tb_config.project_directory / Path('daq/next_run_number.txt')
running_etroc_acquisition = tb_config.project_directory / Path('daq/running_ETROC_acquisition.txt')
running_scope_acquisition = tb_config.project_directory / Path('daq/running_acquisition.txt')

with open(run_number_path, 'r') as file:
    run_number = file.read().strip()
#------------------Ready ETROC Data Acquisition---------------------#

with open(running_etroc_acquisition, 'w') as file:
    file.write("True")
    file.truncate()

etroc_daq_script = tb_config.project_directory / Path('daq/etroc.py')
subprocess.Popen(
    ['/usr/bin/python3', str(etroc_daq_script), 
     '--l1a_rate', '0', 
     '--ext_l1a', 
     '--kcu', '192.168.0.10', 
     '--rb', '0', 
     '--run', str(run_number), 
     '--lock', str(running_scope_acquisition)]
)
time.sleep(15)
#-----------------Ready Oscilliscope Data Acquisition--------------#

# Wait for ETROC to be rady
with open(running_etroc_acquisition) as file:
    kcu_acquisition_flag = file.read()
print("kcu_acquisition_flag ",kcu_acquisition_flag)
iteration = 0
while kcu_acquisition_flag == "False":
    #if args.force_acquisition: break
    if iteration == 0:
        print(f"Waiting for the KCU.")
    with open(running_etroc_acquisition) as file:
        kcu_acquisition_flag = file.read()
    iteration+=1

# This tells the daq/etroc to start taking data
with open(running_scope_acquisition, "w") as f:
    f.write("True")
    f.truncate()

scope_daq_script = tb_config.project_directory / Path('daq/lecroy.py')
subprocess.run(
    [ # OSCILLISCOPE DAQ
    '/usr/bin/python3', str(scope_daq_script), 
    '--runNum', str(run_number), 
    '--numEvents',  str(tb_config.num_events),
    '--sampleRate', str(tb_config.oscilloscope.sample_rate), 
    '--horizontalWindow', str(tb_config.oscilloscope.horizontal_window), 
    '--trigCh',     tb_config.oscilloscope.mcp_channel, 
    '--trig',       str(tb_config.oscilloscope.trigger), 
    '--vScale2',    str(tb_config.oscilloscope.v_scale_2), 
    '--vScale4',    str(tb_config.oscilloscope.v_scale_3), 
    '--vPos2',      str(tb_config.oscilloscope.v_position_2), 
    '--vPos3',      str(tb_config.oscilloscope.v_position_3), 
    '--timeoffset', str(tb_config.oscilloscope.time_offset), 
    '--trigSlope',  tb_config.oscilloscope.trigger_slope,
    '--display', "1"
    ]
)
with open(running_scope_acquisition, "w") as f:
    f.write("False")
    f.truncate()
with open(running_etroc_acquisition, "w") as f:
    f.write("False")
    f.truncate()


# Start
# waits for beam prompt
# temperature monitoring


class RunTB:
    def __init__(self, tb_config:TBConfig):
        # Validate the Config File
        with open('test_beam.toml', 'rb') as f:
            data = tomllib.load(f)
        tb_config = TBConfig.model_validate(data)

        self.run_number_path  = tb_config.project_directory / Path('daq/next_run_number.txt')
        self.etroc_ready_path = tb_config.project_directory / Path('daq/running_ETROC_acquisition.txt')
        self.scope_ready_path = tb_config.project_directory / Path('daq/running_acquisition.txt')

        # ---Initialize the set up--- #
        # Poke board
        # Telescope.py

    def take_run(self):
        self.is_etroc_ready = True
        etroc_daq_script = tb_config.project_directory / Path('daq/etroc.py')
        subprocess.Popen(
            ['/usr/bin/python3', str(etroc_daq_script), 
            '--l1a_rate', '0', 
            '--ext_l1a', 
            '--kcu', '192.168.0.10', 
            '--rb', '0', 
            '--run', str(run_number), 
            '--lock', str(self.running_scope_acquisition)]
        )
        time.sleep(15)
        # Wait for ETROC to be rady
        print("kcu_acquisition_flag ",self.is_etroc_ready)
        iteration = 0
        while not self.is_etroc_ready:
            #if args.force_acquisition: break
            if iteration == 0:
                print(f"Waiting for the KCU.")
            iteration+=1

        self.set_status(self.running_scope_acquisition, "True")
        self.is_scope_ready = True
        scope_daq_script = tb_config.project_directory / Path('daq/lecroy.py')
        subprocess.run(
            [ # OSCILLISCOPE DAQ
            '/usr/bin/python3', str(scope_daq_script), 
            '--runNum', str(run_number), 
            '--numEvents',  str(tb_config.num_events),
            '--sampleRate', str(tb_config.oscilloscope.sample_rate), 
            '--horizontalWindow', str(tb_config.oscilloscope.horizontal_window), 
            '--trigCh',     tb_config.oscilloscope.mcp_channel, 
            '--trig',       str(tb_config.oscilloscope.trigger), 
            '--vScale2',    str(tb_config.oscilloscope.v_scale_2), 
            '--vScale4',    str(tb_config.oscilloscope.v_scale_3), 
            '--vPos2',      str(tb_config.oscilloscope.v_position_2), 
            '--vPos3',      str(tb_config.oscilloscope.v_position_3), 
            '--timeoffset', str(tb_config.oscilloscope.time_offset), 
            '--trigSlope',  tb_config.oscilloscope.trigger_slope,
            '--display', "1"
            ]
        )
        self.set_status(self.running_scope_acquisition, "False")
        self.set_status(self.running_etroc_acquisition, "False")

    @property
    def is_etroc_ready(self) -> bool:
        return self.get_status(self.etroc_ready_path)

    @is_etroc_ready.setter
    def is_etroc_ready(self, status: bool):
        self.is_etroc_ready = self.set_status(self.etroc_ready_path, is_ready=status)

    @property
    def is_scope_ready(self) -> bool:
        return self.get_status(self.scope_ready_path)

    @is_scope_ready.setter
    def is_scope_ready(self, status: bool):
        self.is_scope_ready = self.set_status(self.scope_ready_path, is_ready=status)

    @staticmethod
    def get_status(path: Path) -> bool:
        with open(path) as file:
            status = file.read().strip()
        return status == "True"
    @staticmethod
    def set_status(path: Path, is_ready: bool = True):
        with open(path, "w") as f:
            value = "True" if is_ready else "False"
            f.write(value)
            f.truncate()
        return value == "True"

    @property   
    def run_number(self):
        with open(run_number_path, 'r') as file:
            run_number = file.read().strip()
        return run_number