from typing import List, Tuple, Optional
from typing_extensions import Annotated
from pydantic import BaseModel, Field, field_validator, AfterValidator
import tomllib

def rb_module_select(rb_positions: list):
    for rb_pos in rb_positions:
        if len(rb_pos) > 1:
            raise ValueError("Cannot have more than one module connected in a readout board position. This pattern is to just follow module_test_sw. ")
    return rb_positions  

class KCU(BaseModel):
    ip_address: str
    firmware_version: Optional[str] = None

class ReadoutBoard(BaseModel):
    rb_name: int | str
    type: str = Field(..., description="This is the module configuration, called type due to naming convention in module_test_sw. The module configs have the format: module_test_sw/configs/<config>_<version>.yaml")
    modules: Annotated[List[List[int]], AfterValidator(rb_module_select)] = Field(..., description="modules have to be an integer due to the way the chip id is set for etrocs. See tamalero/Module.py line 57")
    psu_name: Optional[str] = Field(None, description="Power Supply name, should be the same name given in the power supply model (this is so it gets any needed information like IP Address)")
    l1a_delay: int
    offset: int
    power_mode: str

class TelescopeSetup(BaseModel):
    readout_board_version: Optional[str] = None
    readout_board: List[ReadoutBoard]
    
    def to_telescope_config_yaml(self):
        """
        Put in the format for module_test_sw/telescope.py
        Format is: module_test_sw/configs/telescope_{args.configuration}.yaml

        This will need power supply name to put it in this format:
        # psu = [["192.168.0.25", "ch1"], ["192.168.0.25", "ch2"]] # power-up
        # psu_channels = [9, 1.2, 3.3]
        """
        ...

class Oscilloscope(BaseModel):
    name: str
    binary_data_path: str
    sample_rate: int 
    horizontal_window: int
    mcp_channel: str
    clock_channel: str
    trigger: float
    v_scale_2: float
    v_scale_3: float
    v_position_2: int 
    v_position_3: int 
    time_offset: int
    trigger_slope: str

class HighVoltage(BaseModel):
    name: str

class PowerSupplies(BaseModel):
    high_voltage: List[HighVoltage]

class FileProcessing(BaseModel):
    merged_etroc_scope_path: str
    backup_path: str

class TestBeamConfig(BaseModel):
    test_beam_name: str
    beam_energy: int
    num_events: int
    num_runs: int
    run_group_tag: Optional[str] = None
    project_path: str
    etroc_binary_data_path: str

    kcu: KCU
    telescope_setup: TelescopeSetup
    oscilloscope: Oscilloscope
    power_supplies: PowerSupplies
    file_processing: FileProcessing

with open('test_beam.toml', 'rb') as f:
    data = tomllib.load(f)
tb_run = TestBeamConfig.model_validate(data)

# module_temp = {
#     'rb_name': 15,
#     'type': 'modulev1',
#     'modules': [[211],[],[]]
# }
