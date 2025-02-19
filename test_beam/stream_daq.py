from pathlib import Path
from typing import List
from functools import wraps
import subprocess

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