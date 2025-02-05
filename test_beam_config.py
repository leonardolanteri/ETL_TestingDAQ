from typing import List, Tuple, Optional, Literal
from typing_extensions import Annotated
from pydantic import BaseModel, Field, field_validator, AfterValidator, FilePath, DirectoryPath, IPvAnyAddress
import tomllib
from pathlib import Path

################# VALIDATORS ###################
def rb_module_select(rb_positions: list):
    for rb_pos in rb_positions:
        if len(rb_pos) > 1:
            raise ValueError("Cannot have more than one module connected in a readout board position. This pattern is to just follow module_test_sw. ")
    return rb_positions  
################################################
class TestBeam(BaseModel):
    name: str
    beam_energy: int
    project_directory: DirectoryPath

class RunConfig(BaseModel):
    comment: Optional[str] = None
    kcu_ip_address: IPvAnyAddress
    kcu_firmware_version: Optional[str] = None
    etroc_binary_data_directory: DirectoryPath
    num_runs: int #should I get rid of this????
    num_events: int
    l1a_delay: int
    offset: int
    power_mode: str

class ServiceHybrid(BaseModel):
    readout_board_name: int | str
    readout_board_version: Optional[str] = None
    module_config_name: str = Field(..., description="This is the module configuration, called type due to naming convention in module_test_sw. The module configs have the format: module_test_sw/configs/<type>_<version>.yaml")
    modules: Annotated[List[List[int]], AfterValidator(rb_module_select)] = Field(..., description="modules have to be an integer due to the way the chip id is set for etrocs. See tamalero/Module.py line 57")
    LV_psu: Optional[str] = Field(None, description="Power Supply name, should be the same name given in the power supply model (this is so it gets any needed information like IP Address)")
    HV_psu: Optional[str] = Field(None, description="Power Supply name, should be the same name given in the power supply model (this is so it gets any needed information like IP Address)")

    bias_voltage: float

class TelescopeSetup(BaseModel):
    service_hybrids: List[ServiceHybrid]
    
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
    binary_data_directory: DirectoryPath
    sample_rate: int 
    horizontal_window: int
    mcp_channel: Literal["C1", "C2", "C3", "C4"]
    clock_channel: Literal["C1", "C2", "C3", "C4"]
    trigger: float
    v_scale_2: float
    v_scale_3: float
    v_position_2: int 
    v_position_3: int 
    time_offset: int
    trigger_slope: Literal["POS", "NEG"]

class PowerSupply(BaseModel):
    name: str
    log_path: Optional[FilePath] = None
    ip_address: Optional[IPvAnyAddress] = None

class FileProcessing(BaseModel):
    merged_data_directory: DirectoryPath
    backup_directory: DirectoryPath

class Config(BaseModel):
    test_beam: TestBeam
    run_config: RunConfig
    telescope_setup: TelescopeSetup
    oscilloscope: Oscilloscope
    power_supplies: list[PowerSupply]
    file_processing: FileProcessing

# with open('test_beam.toml', 'rb') as f:
#     data = tomllib.load(f)
# tb_run = Config.model_validate(data)

# module_temp = {
#     'rb_name': 15,
#     'type': 'modulev1',
#     'modules': [[211],[],[]]
# }
