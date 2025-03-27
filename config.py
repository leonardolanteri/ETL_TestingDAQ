from typing import List, Optional, Literal, Dict, Any, Tuple, Union
from pydantic import BaseModel, Field, FilePath, DirectoryPath, IPvAnyAddress, model_validator, field_validator, computed_field, ValidationError
from pathlib import Path
from daq.lecroy_controller import (
    # if you had another scope you could duck type these units :)
    SegmentDisplayMode,
    SampleMode,
    Coupling,
    TriggerMode,
    VoltageUnits,
    TimeUnits,
    TriggerCondition,
    SampleRate,
    HorizontalWindow,
    TriggerSlope
)

def all_unique(array: list) -> bool:
    "Returns true if all the elements in an array are unique"
    return len(array) == len(set(array))

def get_modules(rb_positions: List[List[int]]) -> List[int]:
    modules = []
    for rb_pos in rb_positions:
        modules += rb_pos # could contain nothing, multiple modules
    return modules

################# VALIDATORS ###################

################################################
class TestBeam(BaseModel):
    name: str = Field(..., strip_whitespace=True, description="Title of this test beam, ex March DESY 2025")
    beam_energy: int
    project_directory: DirectoryPath = Field(..., description="This should be the directory where ETL_TestingDAQ lives.")
    
class RunConfig(BaseModel):
    comment: Optional[str] = Field(None, strip_whitespace=True)
    num_runs: int
    run_log_directory: DirectoryPath = Field(..., description="Directory containing the run logs, each log corresponds to a series/group of runs")

class ServiceHybrid(BaseModel):
    telescope_layer: Literal['first', 'second', 'third'] = Field(..., description="Which gets hit by the beam first, second, third. ")
    readout_board_name: str = Field(None, strip_whitespace=True, description="The neame of the readout board")
    rb: Literal[0,1,2] = Field(..., description="This is the same rb in module_test_sw corresponds to how the rb is connected to the KCU. 1 and 2 mean via the firely while 0 means via SFP cages.")
    readout_board_version: Optional[str] = Field(..., strip_whitespace=True, description="The pcb board version")
    readout_board_config: str = Field(..., strip_whitespace=True, description="This is the readoutout board configuration, called type due to naming convention in module_test_sw. The rb configs have the format: module_test_sw/configs/<type>_<version>.yaml")
    module_select: List[List[int]] = Field(..., description="EX: [[110],[],[]] : modules have to be an integer due to the way the chip id is set for etrocs. See tamalero/Module.py line 57. ")
    LV_psu: Optional[str] = Field(None, strip_whitespace=True, description="Power Supply name, should be the same name given in the power supply model (this is so it gets any needed information like IP Address)")
    HV_psu: Optional[str] = Field(None, strip_whitespace=True, description="Power Supply name, should be the same name given in the power supply model (this is so it gets any needed information like IP Address)")
    bias_voltage: float

    @field_validator('module_select', mode='after')
    def check_single_module_selected(rb_positions: list):
        """Logic for handling the format [[110], [], []], checks only 1 module is connected to rb"""
        if len(get_modules(rb_positions)) != 1:
            raise ValueError(f"COME ON MAN! Only a single module can be selected for test beam. You selected: {rb_positions}")
        return rb_positions
    
    #lowercase and strip
    @field_validator('telescope_layer',mode='before')
    @classmethod
    def lowercase_n_strip(cls, layer:Any) -> Any:
        if isinstance(layer, str):
            layer = layer.strip().lower()
        return layer
    
class TelescopeConfig(BaseModel):
    kcu_ip_address: IPvAnyAddress
    kcu_firmware_version: Optional[str] = Field(None, strip_whitespace=True)
    service_hybrids: List[ServiceHybrid]
    l1a_delay: int
    offset: Union[int, Literal['auto']]
    power_mode: Literal['default','low', 'medium','high'] = Field(..., strip_whitespace=True, description="Power mode of the etroc, they are 'i4','i3','i2','i1' respectively.")
    etroc_binary_data_directory: DirectoryPath

    @field_validator('service_hybrids', mode='after')
    @classmethod
    def layers_are_unique(cls, service_hybrids: List[ServiceHybrid]) -> List[ServiceHybrid]:
        layers = [sh.telescope_layer for sh in service_hybrids]
        if not all_unique(layers):
            raise ValueError(f"COME ON MAN! You cant have multiple service hybrids in the same layer! You gave: {layers} which has a duplicate.")
        return service_hybrids

    @field_validator('service_hybrids', mode='after')
    @classmethod
    def readout_boards_are_unique(cls, service_hybrids: List[ServiceHybrid]) -> List[ServiceHybrid]:
        readout_boards = [sh.rb for sh in service_hybrids]
        if not all_unique(readout_boards):
            raise ValueError(f"COME ON MAN! Detected multiple readout boards with the same name, they should be unique! Your input: {readout_boards}")
        return service_hybrids

    @field_validator('service_hybrids', mode='after')
    @classmethod
    def modules_are_unique(cls, service_hybrids: List[ServiceHybrid]) -> List[ServiceHybrid]:
        modules = []
        for sh in service_hybrids:
            modules += get_modules(sh.module_select)
        if not all_unique(modules):
            raise ValueError(f"COME ON MAN! Duplicate modules detected in the configuration file. {modules}")
        return service_hybrids
    
    @computed_field
    @property
    def rbs(self) -> List[int]:
        rbs = []
        for sh in self.service_hybrids:
            rbs.append(sh.rb)
        
        if not rbs:
            raise ValidationError("No readout boards provided")
        return rbs

class PowerSupply(BaseModel):
    name: str = Field(..., strip_whitespace=True)
    log_path: Optional[FilePath] = None
    ip_address: Optional[IPvAnyAddress] = None

class TriggerConfig(BaseModel):
    mode: TriggerMode
    condition: TriggerCondition
    level: float
    slope: TriggerSlope
    units: VoltageUnits

class VerticalAxis(BaseModel):
    lower: float = Field(..., alias='min')
    upper: float = Field(..., alias='max')
    units: VoltageUnits

    # Write a validator that ensure lower is less than upper
    @model_validator(mode='after')
    def lower_less_upper(self):
        if self.lower > self.upper:
            raise ValueError("COME ON MAN! Min value needs to be less than max value")
        return self

class ChannelConfig(BaseModel):
    name: Literal["MCP", "Clock"] = Field(..., alias="for")
    coupling: Coupling
    vertical_axis: VerticalAxis
    trigger: TriggerConfig = None

class Oscilloscope(BaseModel):
    # This should try to be general for any scope, i think its possible! But we will likely never have to go there...
    name: str = Field(..., strip_whitespace=True)
    ip_address: IPvAnyAddress
    binary_data_directory: DirectoryPath
    sample_rate: Tuple[SampleRate, Literal["GS/s"]] = Field(..., max_length=2, min_length=2)
    horizontal_window: Tuple[HorizontalWindow, TimeUnits] = Field(..., max_length=2, min_length=2)
    segment_display: SegmentDisplayMode
    sample_mode: SampleMode
    channels: Dict[int, ChannelConfig]
    number_of_segments: int = Field(...,le = 5000)

    @model_validator(mode='before')
    @classmethod
    def convert_list_to_tuple(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if 'horizontal_window' in data and isinstance(data['horizontal_window'], list):
                data['horizontal_window'] = tuple(data['horizontal_window'])
            if 'sample_rate' in data and isinstance(data['sample_rate'], list):
                data['sample_rate'] = tuple(data['sample_rate'])
        return data

    @model_validator(mode='after')
    def single_trigger_channel(self):
        trigger_channels = [chnl for chnl in self.channels.values() if chnl.trigger is not None]
        if len(trigger_channels) != 1:
            raise ValueError(f"COME ON MAN! There must be exactly one trigger channel specified. You have specified {len(trigger_channels)}")
        return self

    @computed_field
    @property
    def mcp_channel_number(self) -> int:
        for chnl_num, chnl in self.channels.items():
            if chnl.name == "MCP":
                return chnl_num
        raise ValidationError("MCP channel not defined in the config.")
    
    @computed_field
    @property
    def clock_channel_number(self) -> int:
        for chnl_num, chnl in self.channels.items():
            if chnl.name == "Clock":
                return chnl_num
        raise ValidationError("Clock channel not defined in the config.")

class Watchdog(BaseModel):
    monitor_directory: DirectoryPath = Field(..., description="Where all the plots go")
    final_archive_directory: DirectoryPath

    ###############################################
    ###### BELOW ARE PRECOMPUTED DIRECTORIES ######
    ###### COMPUTED FROM INPUTTED DIRS ABOVE ######
    ###############################################

    def ensure_dir_exists(self, directory: DirectoryPath) -> DirectoryPath:
        directory.mkdir(exist_ok=True) # throws error if parents dont exists :)
        return directory

    @computed_field
    @property
    def final_etroc_binary_dir(self) -> Path:
        return self.ensure_dir_exists(self.final_archive_directory / "etroc_binary")

    @computed_field
    @property
    def final_scope_binary_dir(self) -> Path:
        return self.ensure_dir_exists(self.final_archive_directory / "scope_binary")
    
    @computed_field
    @property
    def final_merged_dir(self) -> Path:
        return self.ensure_dir_exists(self.final_archive_directory / "merged")

class TBConfig(BaseModel):
    test_beam: TestBeam
    run_config: RunConfig
    telescope_config: TelescopeConfig
    oscilloscope: Oscilloscope
    power_supplies: List[PowerSupply]
    watchdog: Watchdog

def load_config(relax_validation=False) -> TBConfig:
    """
    The active config should be put in the active config director, if there is more than one it throws an error.

    Implemented File Types:
    - toml
    
    Could be implemented:
    - pickle
    - json
    - yaml
    - ... anything that can be read into a python dictionary so it can be validated by pydantic
    """
    from os import environ, path
    
    if 'TEST_BEAM_BASE' not in environ:
        raise KeyError("\"Test_BEAM_BASE\" not in environment variables, did you source setup.sh?")

    active_config_dir = Path(path.expandvars("$TEST_BEAM_BASE/configs/active_config"))
    if not active_config_dir.is_dir():
        raise NotADirectoryError(f"This directory ({active_config_dir}) does not exist. The convention is all used configs are put in ETL_TestingDAQ/configs and the active config goes in ETL_TestingDAQ/configs/active_config.")

    active_configs = [c for c in active_config_dir.iterdir()]
    if len(active_configs) != 1:
        raise ValueError(f"There has to be exactly one config in the active config directory. Currently these are the configs in ETL_TestingDAQ/configs/active_config: {active_configs}")
    active_config_path = active_configs[0]

    # LOAD THE CONFIG
    if active_config_path.suffix == '.toml':
        import tomli
        with open(active_config_path, 'rb') as f:
            data = tomli.load(f)
    else:
        raise NotImplementedError(f"Sorry the file extension you provided ({active_config_path.suffix}) is not currently implemented!")
   
    if relax_validation:
        # if key is missing it wont add it but it wont run validation
        # so extra_fields are not added!
        return TBConfig.model_construct(**data)
    else:
        return TBConfig.model_validate(data)
