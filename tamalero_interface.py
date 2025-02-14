from yaml import load, CLoader as Loader, CDumper as Dumper
from module_test_sw.tamalero.KCU import KCU
from module_test_sw.tamalero.ReadoutBoard import ReadoutBoard
from module_test_sw.tamalero.utils import get_kcu, load_yaml, header
from module_test_sw.tamalero.FIFO import FIFO
from module_test_sw.tamalero.DataFrame import DataFrame
from emoji import emojize

class ETL_Telescope:
    def __init__(self, kcu_ipaddress:str):
        self.kcu = get_kcu(kcu_ipaddress, control_hub=True, verbose=True)
        self.readout_boards: ReadoutBoard = []

    def add_readout_board(self, readout_board_config:str, readout_board_id:int):
        self.readout_boards.append(
                ReadoutBoard(
                    rb      = readout_board_id, 
                    trigger = True, 
                    kcu     = self.kcu, 
                    config  = readout_board_config, 
                    verbose = False
                )
            )

    def check_all_rb_configured(self):
        all_configured = all(rb.configured for rb in self.readout_boards)
        header(configured=all_configured)
        return all_configured

    def check_VTRXs(self):
        # VTRX Power Up
        for rb in self.readout_boards:
            print("--------------")
            rb.VTRX.get_version()
            print(f"VTRX+ Info for RB {rb.rb}")
            print(f"Version {rb.VTRX.ver}")
            print("status at power up:")
            rb.VTRX.status()
            print("--------------")

    def connect_module(self, readout_board_id:int, module_select: list[list[int]]):
        """connects a module to single readout board by searching for matching id"""
        for rb in self.readout_boards:
            if readout_board_id != rb.rb:
                continue
            moduleids = [mod_slot[0] if len(mod_slot)>0 else 0 for mod_slot in module_select]
            print(moduleids)
            rb.connect_modules(moduleids=moduleids)

            for mod in rb.modules:
                mod.show_status()

    def configure_ETROCs(self, l1a_delay=0, offset=10, power_mode='i1', reuse_thresholds_dir: str = None):
        for rb in self.readout_boards:
            for mod in rb.modules:
                if mod.connected:
                    for etroc in mod.ETROCs:
                        if reuse_thresholds_dir is not None:
                            with open(f'{reuse_thresholds_dir}/thresholds_module_{etroc.module_id}_etroc_{etroc.chip_no}.yaml', 'r') as f:
                                thresholds = load(f, Loader=Loader)
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
                                out_dir = reuse_thresholds_dir, 
                                powerMode = power_mode)
                    for etroc in mod.ETROCs:
                        etroc.reset()
    
    def test_etroc_daq(self):
        # fifos
        fifos: list[FIFO] = []
        for rb in self.readout_boards:
            fifos.append(FIFO(rb))

        df = DataFrame("ETROC2")

        fifos[0].send_l1a(1)
        for fifo in fifos:
            fifo.reset()

        # Reset ETROCS
        for rb in self.readout_boards:
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
    def ETROC_temperatures(self) -> list[dict]:
        ...


    def poke_boards(self):
        # Should we still repoke all the boards? It is possible but I am not sure if it is needed...
        ...