import sys
# This is very important, sometimes the python path gets confused
for py_path in sys.path:
    if "module_test_sw" in py_path and "ETL_TestingDAQ" not in py_path:
        print("COME ON MAN!!! the yucky is in there!")
        sys.path.remove("/home/etl/Test_Stand/module_test_sw")

from pathlib import Path
from functools import wraps
from etl_telescope import ETL_Telescope
from lecroy_controller import LecroyController as Lecroy
import time
from config import TelescopeConfig, load_config

from pathlib import Path
from functools import wraps
import subprocess
from emoji import emojize
from typing import List
import json
from datetime import datetime

#---------------- SETUPs BASED ON CONFIG --------------------------#

def is_beam_on(option: str) -> bool:
    """
    Bit scuffed but whatever, forces the selection of y or abort.
    """
    switcher = {
        'y': lambda: print("Beam is on!"),
        'abort': lambda: sys.exit("CMON MAN! Aborting test beam run...")
    }
    if isinstance(option, str):
        option = option.strip().lower()
    func = switcher.get(option, None)
    if func:
        func()
        return True
    elif func is None:
        return False
    else:
        print("Invalid option. Please enter 'y' or 'abort'.")
        return False

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

def set_run_number(run_number_path: Path, run: int):
    with open(run_number_path, 'w') as file:
        file.write(str(run))


class RunDaqStreamPY:
    """Runs the daq_stream.py script in a safe pythonic manner"""
    def __init__(self, telescope_config: TelescopeConfig, daq_dir: Path):
        self.telescope_config = telescope_config
        self.kcu_ip_address = self.telescope_config.kcu_ip_address
        self.rbs = [sh.rb for sh in self.telescope_config.service_hybrids]
        self.stream_daq_process = None

        # Paths
        self.daq_dir = daq_dir
        if not self.daq_dir.is_dir():
            raise ValueError(f"This {self.daq_dir} was not found or is not a directory.")
        
        self.static_dir              = self.daq_dir / Path('static')
        self.daq_stream_path         = self.daq_dir / Path("daq_stream.py")
        self.run_number_path         = self.static_dir / Path('next_run_number.txt')
        self.is_scope_acquiring_path = self.static_dir / Path('is_scope_acquiring.txt')
        self.binary_dir = self.telescope_config.etroc_binary_data_directory

        self.is_rb_ready_paths = [self.static_dir/Path(f'is_rb_{rb}_ready.txt') for rb in self.rbs]

    # These are so the flags are always set to false when entering and exiting!
    def __enter__(self):
        # Start all statuses to False
        self.is_scope_acquiring = False
        for is_rb_ready_path in self.is_rb_ready_paths:
            self.set_status(is_rb_ready_path, False)
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        # Return all statuses to False
        self.is_scope_acquiring = False
        for is_rb_ready_path in self.is_rb_ready_paths:
            self.set_status(is_rb_ready_path, False)

        # this makse sure to kill the process if a bug happens!    
        if self.stream_daq_process is not None: # hand checked this becomes None once completed
            self.stream_daq_process.kill()

    @property
    def stream_daq_command(self) -> List[str]:
        return ['python', str(self.daq_stream_path), 
            '--l1a_rate', '0', 
            '--ext_l1a', 
            '--kcu', str(self.kcu_ip_address), 
            '--rb', ",".join(map(str,self.rbs)),
            '--run', str(get_run_number(self.run_number_path)), 
            '--lock', str(self.is_scope_acquiring_path), # lock waits for scope to be ready
            '--binary_dir', str(self.binary_dir),
            '--daq_static_dir', str(self.static_dir),
        ] 

    def launch(self) -> None:
        """Launches the daq_stream.py which streams the data from the KCU."""
        self.stream_daq_process = subprocess.Popen(self.stream_daq_command) 

    def wait_til_done(self) -> None:
        if self.stream_daq_process is not None: #just in case
            self.stream_daq_process.wait()
        else:
            print("DAQ stream subprocess completed or never started")

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
        if status == "":
            raise ValueError("No status, is an empty string, please start it in the False state, by typing False into the text file.")
        elif status not in ["True", "False"]:
            raise ValueError(f"Status (your_status=\"{status}\") was found to not be \"True\" or \"False\", please check code that sets the status here and in .")
        return status == "True"
    
    @staticmethod
    @ensure_path_exists
    def set_status(path: Path, status: bool):
        with open(path, "w") as f:
            value = "True" if status else "False"
            f.write(value)
            f.truncate()
        return value == "True"

    @property
    def rbs_are_ready(self) -> bool:
        return all(self.get_status(p) for p in self.is_rb_ready_paths)

################################################################################################################################
#####################################-------------TEST BEAM ROUTINE-------------################################################
################################################################################################################################
if __name__ == '__main__':
    import argparse
    argParser = argparse.ArgumentParser(description = "DAQ Test Beam argparser")
    argParser.add_argument('--etl_power_up', action='store_true', help="Flag to power up JUST etl front-end electronics")
    args = argParser.parse_args()
    
    # LOAD THE CONFIG
    tb_config = load_config()
    telescope_config = tb_config.telescope_config
    scope_config = tb_config.oscilloscope
    project_dir = tb_config.test_beam.project_directory
    
    # GET RUN NUMBERS
    daq_dir = project_dir / Path('daq')
    run_number_path = daq_dir/Path('static/next_run_number.txt')
    run_start = get_run_number(run_number_path)
    num_runs = tb_config.run_config.num_runs
    run_stop = run_start + num_runs - 1 

    # Initialize Run Log
    run_group_path = tb_config.run_config.run_log_directory / Path(f"runs_{run_start}_{run_stop}.json")
    new_run_group = {
        "config": tb_config.model_dump(mode="json"),
        "runs": []
    }
    with open(run_group_path, mode='w') as f:
        json.dump(new_run_group, f)
    
    # CONFIGURE FRONT END ELECTRONICS
    thresholds_dir = telescope_config.all_thresholds_directory / Path(f"run_{run_start}_{run_stop}")
    thresholds_dir.mkdir(exist_ok=True)
    etl_telescope = ETL_Telescope(telescope_config, thresholds_dir=thresholds_dir)
    if args.etl_power_up:
        sys.exit("ETL Power up option gave exiting early!")

    # DAQ
    active_channels = [chnl_num for chnl_num in scope_config.channels]
    with Lecroy(scope_config.ip_address, active_channels=active_channels) as lecroy, RunDaqStreamPY(telescope_config, daq_dir) as daq_stream:
        lecroy.setup_from_config(scope_config)

        user_input_for_beam_on = None
        while not is_beam_on(user_input_for_beam_on):
            user_input_for_beam_on = input("Need somebody to turn the beam on! Is it on? (y/abort) ")

        print(f"----------STARTING RUNS {run_start} TO {run_stop}----------")
        for run in range(run_start, run_start+num_runs):
            start_time = datetime.now()
            set_run_number(run_number_path, run=run)

            print("\n")
            print(f"::::::::::: ACQUIRING RUN {run} :::::::::::")
            daq_stream.launch() # WILL STOP UNTIL daq_stream.is_scope_acquiring is set
            
            print("Waiting for streams to be ready...")
            while not daq_stream.rbs_are_ready:
                time.sleep(0.2) 
            print("Streams ready!")
            
            print(">>>>> starting scope acquisition <<<<<<")
            # Starts all daq streams bec its waiting for scope to begin!
            daq_stream.is_scope_acquiring = True 
            # 6 microseconds of delay between these lines
            lecroy.do_acquisition() # this hangs until acquisition is done.
            print(">>>>> scope acquisition finished <<<<<<")
            
            # Ends all daq streams
            daq_stream.is_scope_acquiring = False 
            print("letting daq stream know scope is done!")
            for chnl in lecroy.channels.values():
                chnl.save(run)
            print("saved the waveforms now waiting for daq stream")
            # SAFETY: Lets daq_stream.py finish (otherwise it gets killed when exiting the context manager!)
            daq_stream.wait_til_done()
            print("daq stream done")
            # Output run log
            with open(run_group_path, 'r+') as f:
                run_group_log = json.load(f)
                if 'runs' in run_group_log:
                    run_group_log['runs'].append(
                        {
                            'run_number': run,
                            'finish_time': datetime.now().isoformat(),
                            'start_time': start_time.isoformat(),
                            'temperatures': 123 #etl_telescope.etroc_temperatures
                        }
                    )
                    f.seek(0) # 
                    json.dump(run_group_log, f, indent=4)
                else:
                    print("Run log corrupted during runs, lost the 'runs' key, skipping logging...")

            print(f"::::::::::: FINISHED RUN {run} :::::::::::")

    # uhal._core.NonValidatedMemory