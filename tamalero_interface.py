# lets identify the main parts

# 1. get_KCU

# 2. Instantiate ReadoutBoards

# 3. Power Up Trigger lpGBT

# 4. Connect modules

# 5. configure ETROC

# 6. test_etroc_daq

# 7. Set DAQ LPGBT configured

from yaml import load, CLoader as Loader, CDumper as Dumper
from module_test_sw.tamalero.KCU import KCU
from module_test_sw.tamalero.ReadoutBoard import ReadoutBoard
from module_test_sw.tamalero.utils import get_kcu, load_yaml, header
from module_test_sw.tamalero.FIFO import FIFO
from module_test_sw.tamalero.DataFrame import DataFrame

class ETL_Software:
    def __init__(self, kcu_ipaddress:str, readout_board_config:str, readout_board_names: list[str | int]):
        self.kcu = get_kcu(kcu_ipaddress, control_hub=True, verbose=True)
        self.readout_board_names:str  = readout_board_names
        self.readout_board_config:str = readout_board_config
        self.readout_boards: ReadoutBoard = {}

        for rb_name in self.readout_board_names:
            self.readout_boards[rb_name](
                ReadoutBoard(
                    rb      = rb_name, 
                    trigger = True, 
                    kcu     = self.kcu, 
                    config  = self.readout_board_config, 
                    verbose = False
                )
            )

        header(configured=all(rb.configured for rb in self.readout_boards))

    def power_up_trigger_LPGBT(self):
        ...

    def connect_modules(self):
        ...

    def configure_ETROCs(self, l1a_delay, offset, power_mode, thresholds_path):
        # self.l1a_delay
        # self.offset
        # self.power_mode
        # self.threshodlds_path = None
        ...
    
    def test_etroc_daq(self):
        ...

    def set_DAQ_LPGBT_configured(self):
        ...