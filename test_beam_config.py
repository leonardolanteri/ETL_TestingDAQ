from typing import List, Optional, Literal, Dict, Annotated
from pydantic import BaseModel, Field, AfterValidator, FilePath, DirectoryPath, IPvAnyAddress, model_validator
from lecroy.config import LecroyConfig as ScopeConfig

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
    num_runs: int 
    l1a_delay: int
    offset: int | Literal['auto']
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
    oscilloscope: ScopeConfig
    power_supplies: list[PowerSupply]
    file_processing: FileProcessing

import tomllib
with open('test_beam.toml', 'rb') as f:
    data = tomllib.load(f)
tb_run = Config.model_validate(data)

print(tb_run.oscilloscope)