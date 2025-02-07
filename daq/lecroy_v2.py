from pathlib import Path
import argparse
import os
import time
import datetime
import pyvisa as visa
import glob
import pdb
from typing import Literal

class Channel:
    def __init__(self, channel:int, lecroy_connection: visa.resources.Resource):
        self.number = channel
        self.lecroy_conn = lecroy_connection
        # This is standard for oscilliscopes (number of boxes on the screen in vert and horz direction)
        self.num_vertical_divs = 8
        self.is_trigger_channel = False

    def vertical_axis(self, lower_bound:float, upper_bound:float, units:Literal['V', 'MV']='V'):
        """
        Specifies the set up of the vertical axis for the oscillisope. The start and 
        stop arguments specify the range of voltage values for the vertical axis.

        Arguments
        channel: Oscillsicope channel 
        lower_bound, upper_bound: Specify the lower and upper bounds of the vertical axis
        """
        volts_div = (upper_bound - lower_bound) / self.num_vertical_divs
        offset = (upper_bound+lower_bound)/2
        self.volts_div(volts_div, units=units)
        self.vertical_offset(offset, units=units)

    def volts_div(self, volts_div:float, units:Literal['V', 'MV'] = 'V'):
        """Set volts per div for a channel"""
        self.lecroy_conn.write(f"C{self.number}:VOLT_DIV {volts_div}{units}")
    
    def vertical_offset(self, offset:float, units:Literal['V', 'MV'] = 'V'):
        """Sets the vertical offset"""
        self.lecroy_conn.write(f"C{self.number}:OFFSET {offset}{units}")

    def coupling(self, coupling:Literal['D50']):
        self.lecroy_conn.write(f"C{self.number}:COUPLING {coupling}")

class Lecroy:
    """
    This is the manual for all of the commands:
    https://cdn.teledynelecroy.com/files/manuals/wr2_rcm_revb.pdf
    """
    def __init__(self, ip_address: str, active_channels:list[int] = None):
        # Set Up Connection to Oscilliscope
        rm = visa.ResourceManager("@py")
        self.lecroy_conn = rm.open_resource(f'TCPIP0::{ip_address}::INSTR')
        self.lecroy_conn.timeout = 3000000
        self.lecroy_conn.encoding = 'latin_1'
        self.lecroy_conn.clear()

        self.lecroy_conn.write('STOP') #Stops any acquisition processes
        self.lecroy_conn.write("*CLS") #not sure what this does

        # This makes it so the scope just returns the number and not extra information
        self.lecroy_conn.write("COMM_HEADER OFF")
        self.lecroy_conn.write("BANDWIDTH_LIMIT OFF")

        self.active_channels = [1,2,3,4] if active_channels is None else active_channels
        self.channels = {chnl: Channel(chnl) for chnl in active_channels}        

        self.num_horizontal_divs = 10

    def horizontal_axis(self, lower_bound: float, upper_bound:float, units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'NS') -> None:
        """
        Specifies the set up of the horizontal axis for the oscillisope. The start and 
        stop arguments specify the range of time values for the horizontal axis.
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.

        Arguments
        lower_bound, upper_bound: Specify the lower and upper bounds of the time axis

        TODO: Test the offest makes sense being trigger delay
        """
        offset = (upper_bound+lower_bound)/2
        time_div = (upper_bound-lower_bound)/self.num_horizontal_divs
        self.time_div(time_div, units=units)
        self.trigger_delay(offset, units=units)

    def time_div(self, time_div:float=None, units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'S'):
        """
        Set time per div for a channel
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        self.lecroy_conn.write(f"TIME_DIV {time_div}{units}")
    
    def trigger_delay(self, delay:float, units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'S'):
        """
        Set trigger delay
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        self.lecroy_conn.write(f"TRIG_DELAY {delay}{units}")
    
    def trigger_slope(self, slope:Literal["POS", "NEG", "WINDOW"]):
        self.lecroy_conn.write(f"TRIG_SLOPE {slope}")

    def trigger_select(self, channel:Channel, trigger_type:Literal["DROP", "EDGE", "GLIT", "INTV", "STD", "SNG", "SQ", "TEQ"]=None):
        """Select what channel to use as trigger."""
        
        assert all(not chnl.is_trigger_channel for chnl in self.channels.values()), "For simplicity, only channel can be desiginated as the trigger channel"
        channel.is_trigger_channel = True
        self.lecroy_conn.write(f"TRIG_SELECT {trigger_type},SR,{channel.number}")
    
    def sample_rate(self, value):
        ...

    def __repr__(self):
        """
        The *IDN? query identifies the instrument type
        and software version. The response consists of
        four different fields providing information on the
        manufacturer, the scope model, the serial
        number and the firmware revision.
        """
        idn = self.lecroy_conn.query("*IDN?").split(',')
        names = ['manufacturer', 'scope model', 'serial number', 'firmware version']
        if len(idn) != len(names):
            raise ValueError("Unexpected response format")
        return '\n'.join(f"{name} = {value}" for name, value in zip(names, idn))


lecroy = Lecroy("192.168.0.6", active_channels=[2,3])

lecroy.channels[2].coupling(coupling='D50')
lecroy.channels[3].vertical_axis(-2,2, units='V')

lecroy.horizontal_axis(-2, 0.5, units='NS')

lecroy.trigger_select(lecroy.channels[2], trigger_type="EDGE")