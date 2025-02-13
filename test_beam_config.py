from typing import List, Optional, Literal, Dict, Annotated, Any, Tuple
from pydantic import BaseModel, Field, AfterValidator, FilePath, DirectoryPath, IPvAnyAddress, model_validator
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
    HorizontalWindow
)

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


class Trigger(BaseModel):
    mode: TriggerMode
    condition: TriggerCondition
    level: float
    unit: VoltageUnits

class VerticalAxis(BaseModel):
    lower: float = Field(..., alias='min')
    upper: float = Field(..., alias='max')
    unit: VoltageUnits

    # Write a validator that ensure lower is less than upper
    @model_validator(mode='after')
    def lower_less_upper(self):
        if self.lower > self.upper:
            raise ValueError("Min value needs to be less than max value")
        return self

class ChannelConfig(BaseModel):
    name: str = Field(..., alias="for")
    coupling: Coupling
    vertical_axis: VerticalAxis
    trigger: Trigger = None

class Oscilliscope(BaseModel):
    name: str
    ip_address: IPvAnyAddress
    binary_data_directory: DirectoryPath
    sample_rate: Tuple[SampleRate, Literal["GS/s"]] = Field((20, "GS/s"), max_length=2, min_length=2)
    horizontal_window: Tuple[HorizontalWindow, TimeUnits] = Field((50, "ns"), max_length=2, min_length=2)
    segment_display: SegmentDisplayMode
    sample_mode: SampleMode
    channels: Dict[int, ChannelConfig]

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
            raise ValueError(f"There must be exactly one trigger channel specified. You have specified {len(trigger_channels)}")
        return self



class TBConfig(BaseModel):
    test_beam: TestBeam
    run_config: RunConfig
    telescope_setup: TelescopeSetup
    oscilloscope: Oscilliscope
    power_supplies: list[PowerSupply]
    file_processing: FileProcessing

# import tomllib
# with open('test_beam.toml', 'rb') as f:
#     data = tomllib.load(f)
# tb_run = Config.model_validate(data)

# print(tb_run.oscilloscope)