from typing import List, Dict, Annotated
from pydantic import BaseModel, Field, IPvAnyAddress, DirectoryPath, model_validator
from .controller import (
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

class LecroyConfig(BaseModel):
    name: str
    ip_address: IPvAnyAddress
    binary_data_directory: DirectoryPath
    sample_rate: List[SampleRate, str] = Field(20, max_length=2, min_length=2)
    horizontal_window: List[HorizontalWindow, TimeUnits] = Field(20, max_length=2, min_length=2)
    segment_display: SegmentDisplayMode
    sample_mode: SampleMode
    channels: Dict[int, ChannelConfig]

    @model_validator(mode='after')
    def single_trigger_channel(self):
        trigger_channels = [chnl for chnl in self.channels.values() if chnl.trigger is not None]
        if len(trigger_channels) != 1:
            raise ValueError(f"There must be exactly one trigger channel specified. You have specified {len(trigger_channels)}")
        return self