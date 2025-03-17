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
import logging

logger = logging.getLogger(__name__)
class ETL_Telescope:
    def __init__(self, telescope_config: TelescopeConfig):
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
            logger.error("No communications with KCU105... quitting")
            sys.exit(1)
        else:
            logger.info("Successful Test Communication with KCU!!")
        self.readout_boards: Dict[int,ReadoutBoard] = {}
        
        self.thresholds = {}
        # i apologize that this does not read very procedurally
        self.startup_readout_boards()
        self.check_all_rb_configured()
        self.check_VTRXs() 
        self.connect_modules()
        self.configure_ETROCs()
        self.test_etroc_daq()

    def startup_readout_boards(self):
        for sh in self.config.service_hybrids:
            self.readout_boards[sh.rb] = (
                    ReadoutBoard(
                        rb      = sh.rb, 
                        trigger = True, 
                        kcu     = self.kcu, 
                        config  = sh.readout_board_config, 
                        verbose = False
                    )
                )
    
    @property
    def rbs(self) -> List[int]:
        return list(self.readout_boards.keys())

    def check_all_rb_configured(self):
        all_configured = all(
            readout_board.configured for readout_board in self.readout_boards.values())
        utils.header(configured=all_configured)
        return all_configured

    def check_VTRXs(self):
        # VTRX Power Up
        for readout_board in self.readout_boards.values():
            logger.info("--------------")
            readout_board.VTRX.get_version()
            logger.info(f"VTRX+ Info for RB {readout_board.rb}")
            logger.info(f"Version {readout_board.VTRX.ver}")
            logger.info("status at power up:")
            readout_board.VTRX.status()
            logger.info("--------------")

    def connect_modules(self):
        for sh in self.config.service_hybrids:
            readout_board = self.readout_boards[sh.rb]
            moduleids = [mod_slot[0] if len(mod_slot)>0 else 0 for mod_slot in sh.module_select]
            logger.info(moduleids)
            readout_board.connect_modules(moduleids=moduleids)

            for mod in readout_board.modules:
                mod.show_status()

    def configure_ETROCs(self):
        offset = self.config.offset
        l1a_delay = self.config.l1a_delay
        power_mode = self.config.power_mode
        modules = []
        for readout_board in self.readout_boards.values():
            for mod in readout_board.modules:
                modules.append(mod)
                if not mod.connected:
                    logger.info(f"Module {mod.module_id} is not connected!")
                    continue
                for etroc in mod.ETROCs:
                    if not etroc.is_connected():
                        logger.info(f"ETROC {etroc.chip_no} is not connected!")
                        continue

                    etroc.set_power_mode(power_mode)
                    etroc.enable_data_readout(broadcast=True)
                    etroc.wr_reg("workMode", 0, broadcast=True)
                    etroc.set_L1Adelay(delay=l1a_delay, broadcast=True)
                    baseline, noise_width = etroc.run_threshold_scan(offset=offset) # threshold = baseline + offset !!
                    self.thresholds[f"rb_{readout_board.rb}_module_{mod.module_id}_etroc_{etroc.chip_no}"] = {
                        "noise_width": noise_width,
                        "baseline": baseline
                    }
                for etroc in mod.ETROCs:
                    etroc.reset()

        if not any(mod.connected for mod in modules):
            raise ConnectionError("No modules connected, aborting...")

    def test_etroc_daq(self):
        """
        Sends l1a's and checks for data in the FIFO
        """
        # fifos
        fifos: list[FIFO] = []
        for readout_board in self.readout_boards.values():
            fifos.append(FIFO(readout_board))

        df = DataFrame("ETROC2")

        fifos[0].send_l1a(1)
        for fifo in fifos:
            fifo.reset()

        # Reset ETROCS
        for readout_board in self.readout_boards.values():
            for mod in readout_board.modules:
                for etroc in mod.ETROCs:
                    etroc.reset()

        logger.info(emojize(':factory:'), " Producing some test data")
        fifos[0].send_l1a(10)

        for i, fifo in enumerate(fifos):
            logger.info(emojize(':closed_mailbox_with_raised_flag:'), f" Data in FIFO {i}:")
            for x in fifos[i].pretty_read(df):
                logger.info(x)

    @property
    def ETROC_temperatures(self) -> List[dict]:
        ...

    def poke_boards(self):
        # Should we still repoke all the boards? It is possible but I am not sure if it is needed...
        ...

