try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

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
                        if self.config.reuse_thresholds:
                            filename = Path(f'{thresholds_filename_prefix}thresholds_module_{etroc.module_id}_etroc_{etroc.chip_no}.yaml')
                            thresholds_file = thresholds_dir/filename
                            if not thresholds_file.exists():
                                raise FileNotFoundError("These thresholds you chose do not exist, please update the config switching the reuse thresholds flag to False to perform a threhold scan")
                            with open(thresholds_file, 'r') as f:
                                thresholds = utils.load_yaml(f, Loader=Loader)
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
