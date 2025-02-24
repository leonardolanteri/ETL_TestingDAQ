try:
    from config import TelescopeConfig
except ImportError:
    raise ImportError("Please run setup.sh for the test beam in order to set up the pathing correctly :)")

from module_test_sw.tamalero.KCU import KCU
from module_test_sw.tamalero.ReadoutBoard import ReadoutBoard
from module_test_sw.tamalero.FIFO import FIFO
from module_test_sw.tamalero.DataFrame import DataFrame
from module_test_sw.tamalero import utils
from pathlib import Path
from functools import wraps
import subprocess
from emoji import emojize
from typing import List, Dict
import sys

class ETL_Telescope:
    def __init__(self, telescope_config: TelescopeConfig, thresholds_filename_prefix:str = None):
        self.config = telescope_config
        self.kcu: KCU = utils.get_kcu(self.config.kcu_ip_address, control_hub=True, verbose=True)

        if (self.kcu == 0):
            # if not basic connection was established the get_kcu function returns 0
            # this would cause the RB init to fail.
            sys.exit(1)
        # check that the KCU is actually connected
        data = 0xabcd1234
        self.kcu.write_node("LOOPBACK.LOOPBACK", data)
        if (data != self.kcu.read_node("LOOPBACK.LOOPBACK")):
            print("No communications with KCU105... quitting")
            sys.exit(1)
        else:
            print("Successful Test Communication with KCU!!")
        self.readout_boards: Dict[int,ReadoutBoard] = {}

        self.startup_readout_boards()
        self.check_all_rb_configured()
        self.check_VTRXs() 
        self.connect_modules()
        self.configure_ETROCs(thresholds_filename_prefix=thresholds_filename_prefix)
        self.test_etroc_daq()

    def startup_readout_boards(self):
        for sh in self.config.service_hybrids:
            self.readout_boards[sh.readout_board_id] = (
                    ReadoutBoard(
                        rb      = sh.readout_board_id, 
                        trigger = True, 
                        kcu     = self.kcu, 
                        config  = sh.readout_board_config, 
                        verbose = False
                    )
                )

    def check_all_rb_configured(self):
        all_configured = all(rb.configured for rb in self.readout_boards.values())
        utils.header(configured=all_configured)
        return all_configured

    def check_VTRXs(self):
        # VTRX Power Up
        for rb in self.readout_boards.values():
            print("--------------")
            rb.VTRX.get_version()
            print(f"VTRX+ Info for RB {rb.rb}")
            print(f"Version {rb.VTRX.ver}")
            print("status at power up:")
            rb.VTRX.status()
            print("--------------")

    def connect_modules(self):
        for sh in self.config.service_hybrids:
            rb = self.readout_boards[sh.readout_board_id]
            moduleids = [mod_slot[0] if len(mod_slot)>0 else 0 for mod_slot in sh.module_select]
            print(moduleids)
            rb.connect_modules(moduleids=moduleids)

            for mod in rb.modules:
                mod.show_status()

    def configure_ETROCs(self, thresholds_filename_prefix: str = None):
        thresholds_dir = self.config.thresholds_directory

        thresholds_filename_prefix = thresholds_filename_prefix
        offset = self.config.offset
        l1a_delay = self.config.l1a_delay
        power_mode = self.config.power_mode
        for rb in self.readout_boards.values():
            for mod in rb.modules:
                if mod.connected:
                    for etroc in mod.ETROCs:
                        if etroc.is_connected():
                            print(f"Found ETROC {etroc.chip_no}")
                            if self.config.reuse_thresholds:
                                filename = Path(f'thresholds_module_{etroc.module_id}_etroc_{etroc.chip_no}.yaml')
                                thresholds_file = thresholds_dir/filename
                                if not thresholds_file.exists():
                                    raise FileNotFoundError(f"These the thresholds at {thresholds_file} do not exist. You can update the config's 'reuse thresholds' flag to False to perform a threshold scan")
                                print("*********Reusing Thresholds************")
                                thresholds = utils.load_yaml(thresholds_file)
                                etroc.physics_config(
                                    offset=offset, 
                                    L1Adelay=l1a_delay, 
                                    thresholds=thresholds, 
                                    powerMode=power_mode
                                )
                            else:
                                etroc.physics_config(
                                    offset = offset, 
                                    L1Adelay = l1a_delay, 
                                    thresholds = None, # this runs a threshold scan and saves it to outdir
                                    out_dir = thresholds_dir, 
                                    powerMode = power_mode)
                        else:
                            print(f"ETROC {etroc.chip_no} is not connected!")
                    for etroc in mod.ETROCs:
                        etroc.reset()
    
    def test_etroc_daq(self):
        """
        Sends l1a's and checks for data in the FIFO
        """
        # fifos
        fifos: list[FIFO] = []
        for rb in self.readout_boards.values():
            fifos.append(FIFO(rb))

        df = DataFrame("ETROC2")

        fifos[0].send_l1a(1)
        for fifo in fifos:
            fifo.reset()

        # Reset ETROCS
        for rb in self.readout_boards.values():
            for mod in rb.modules:
                for etroc in mod.ETROCs:
                    etroc.reset()

        print(emojize(':factory:'), " Producing some test data")
        fifos[0].send_l1a(10)

        for i, fifo in enumerate(fifos):
            print(emojize(':closed_mailbox_with_raised_flag:'), f" Data in FIFO {i}:")
            for x in fifos[i].pretty_read(df):
                print(x)

    @property
    def ETROC_temperatures(self) -> List[dict]:
        ...


    def poke_boards(self):
        # Should we still repoke all the boards? It is possible but I am not sure if it is needed...
        ...



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

class KcuStream:
    """
    Syncs daq steps for the scope and etroc. 
    """
    def __init__(self, kcu_ipadress: str, readout_board_ids:List[int], project_dir: Path, binary_dir: Path):
        self.kcu_ip_address = kcu_ipadress
        self.project_dir = project_dir
        self.binary_dir = binary_dir
        self.readout_board_ids = readout_board_ids
        self.run_number_path  = project_dir / Path('daq/static/next_run_number.txt')
        self.is_scope_acquiring_path = project_dir / Path('daq/static/is_scope_acquiring.txt')
        self.etroc_daq_process = None
    # These are so the flags are always set to false when entering and exiting!
    def __enter__(self):
        self.is_scope_acquiring = False
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        self.is_scope_acquiring = False
        if self.etroc_daq_process is not None:
            # this makse sure to kill the process if a bug happens!
            self.etroc_daq_process.kill()

    @property
    def etroc_daq_command(self) -> List[str]:
        etroc_daq_script = self.project_dir / Path('daq/daq_stream.py')
        print(str(etroc_daq_script))
        print(str(self.binary_dir))
        print(self.kcu_ip_address)
        print(",".join(map(str,self.readout_board_ids)))
        print(str(get_run_number(self.project_dir/Path('daq/static/next_run_number.txt'))))
        print(str(self.is_scope_acquiring_path))
        return ['python', str(etroc_daq_script), 
            '--l1a_rate', '0', 
            '--ext_l1a', 
            '--kcu', str(self.kcu_ip_address), 
            '--rb', ",".join(map(str,self.readout_board_ids)), # do comma seperated for each rb
            '--run', str(get_run_number(self.project_dir/Path('daq/static/next_run_number.txt'))), 
            '--lock', str(self.is_scope_acquiring_path),# lock waits for scope to be ready
            '--binary_dir', str(self.binary_dir)
            ] 

    def startup(self) -> None:
        self.etroc_daq_process = subprocess.Popen(self.etroc_daq_command) #self.etroc_daq_command
  
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