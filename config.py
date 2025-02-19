from typing import List, Optional, Literal, Dict, Any, Tuple, Union
from pydantic import BaseModel, Field, FilePath, DirectoryPath, IPvAnyAddress, model_validator, field_validator
from lecroy.controller import (
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
    project_directory: DirectoryPath

class RunConfig(BaseModel):
    comment: Optional[str] = Field(None, strip_whitespace=True)
    kcu_ip_address: IPvAnyAddress
    kcu_firmware_version: Optional[str] = Field(None, strip_whitespace=True)
    etroc_binary_data_directory: DirectoryPath
    num_runs: int 


class ServiceHybrid(BaseModel):
    telescope_layer: Literal['first', 'second', 'third'] = Field(..., description="Which gets hit by the beam first, second, third. ")
    readout_board_id: int
    readout_board_version: Optional[str] = Field(..., strip_whitespace=True, description="The pcb board version")
    readout_board_config: str = Field(..., strip_whitespace=True, description="This is the readoutout board configuration, called type due to naming convention in module_test_sw. The rb configs have the format: module_test_sw/configs/<type>_<version>.yaml")
    module_select: List[List[int]] = Field(..., description="modules have to be an integer due to the way the chip id is set for etrocs. See tamalero/Module.py line 57")
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
    service_hybrids: List[ServiceHybrid]
    l1a_delay: int
    offset: Union[int, Literal['auto']]
    power_mode: str = Field(..., strip_whitespace=True, description="Power mode of the etroc")
    thresholds_directory: DirectoryPath
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
        readout_boards = [sh.readout_board_id for sh in service_hybrids]
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
    
class PowerSupply(BaseModel):
    name: str = Field(..., strip_whitespace=True)
    log_path: Optional[FilePath] = None
    ip_address: Optional[IPvAnyAddress] = None

class FileProcessing(BaseModel):
    merged_data_directory: DirectoryPath
    backup_directory: DirectoryPath


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
    name: str = Field(..., alias="for")
    coupling: Coupling
    vertical_axis: VerticalAxis
    trigger: TriggerConfig = None

class Oscilliscope(BaseModel):
    # This should try to be general for any scope, i think its possible! But we will likely never have to go there...
    name: str = Field(..., strip_whitespace=True)
    ip_address: IPvAnyAddress
    binary_data_directory: DirectoryPath
    sample_rate: Tuple[SampleRate, Literal["GS/s"]] = Field((20, "GS/s"), max_length=2, min_length=2)
    horizontal_window: Tuple[HorizontalWindow, TimeUnits] = Field((50, "ns"), max_length=2, min_length=2)
    segment_display: SegmentDisplayMode
    sample_mode: SampleMode
    channels: Dict[int, ChannelConfig]
    number_of_segments: int

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


class TBConfig(BaseModel):
    test_beam: TestBeam
    run_config: RunConfig
    telescope_config: TelescopeConfig
    oscilloscope: Oscilliscope
    power_supplies: List[PowerSupply]
    file_processing: FileProcessing


# import tomllib
# with open('test_beam.toml', 'rb') as f:
#     data = tomllib.load(f)
# tb_run = TBConfig.model_validate(data)


# print(tb_run.telescope_setup)