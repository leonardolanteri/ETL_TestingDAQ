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
        self._conn = lecroy_connection
        # This is standard for oscilliscopes (number of boxes on the screen in vert and horz direction)
        self.num_vertical_divs = 8
        self.is_trigger_channel = False

    def set_vertical_axis(self, lower_bound:float, upper_bound:float, units:Literal['V', 'MV']='V'):
        """
        Specifies the set up of the vertical axis for the oscillisope. The start and 
        stop arguments specify the range of voltage values for the vertical axis.

        Arguments
        channel: Oscillsicope channel 
        lower_bound, upper_bound: Specify the lower and upper bounds of the vertical axis
        """
        volts_div = abs(upper_bound - lower_bound) / self.num_vertical_divs
        offset = (upper_bound+lower_bound)/2
        self.set_volts_div(volts_div, units=units)
        # You want the opposite sign of offset to get correct display
        self.set_vertical_offset(-offset, units=units)

    def set_volts_div(self, volts_div:float, units:Literal['V', 'MV'] = 'V'):
        """Set volts per div for a channel"""
        self._conn.write(f"C{self.number}:VOLT_DIV {volts_div}{units}")
    
    def set_vertical_offset(self, offset:float, units:Literal['V', 'MV'] = 'V'):
        """Sets the coupling, """
        self._conn.write(f"C{self.number}:OFFSET {offset}{units}")

    def set_coupling(self, coupling:Literal['D50', 'D1M']):
        """
        https://blog.teledynelecroy.com/2020/08/how-do-you-choose-whether-to-use-50-ohm.html

        DANGER, DANGER
        However, if your input DC or RMS voltage is close to or above 5 V, DO NOT USE the 50 Ohm input to the scope!
        Inside the scope, in front of the amplifier, is a 50 Ohm resistor. 
        This resistor is capable of dissipating only 0.5 watts of power. 
        If the resistor consumes more than 0.5 watts, it will heat up too much. 
        In the extreme case, the resistor could be thermally damaged--or literally fall off the board. 
        """
        self._conn.write(f"C{self.number}:COUPLING {coupling}")

class Lecroy:
    """
    This is the manual for all of the commands:
    https://cdn.teledynelecroy.com/files/manuals/wr2_rcm_revb.pdf
    """
    def __init__(self, lecroy_connection: visa.resources.Resource, active_channels:list[int] = None):
        self._conn = lecroy_connection
        self._conn.timeout = 3000000
        self._conn.encoding = 'latin_1'
        self._conn.clear()
        # This is important to always put the scope back in the same starting place
        self.reset()

        self._conn.write('STOP') #Stops any acquisition processes
        self._conn.write("*CLS") # Clears all status registers, not sure why important?

        # This makes it so the scope just returns the number and not extra information
        self._conn.write("COMM_HEADER OFF")
        self._conn.write("BANDWIDTH_LIMIT OFF")

        self.active_channels = [1,2,3,4] if active_channels is None else active_channels
        self.channels = {chnl: Channel(chnl, self._conn) for chnl in active_channels}   
        #self._conn.write(f"DISPlay OFF")


        self.num_horizontal_divs = 10

    def set_horizontal_axis(self, bound: Literal[5,10,25,50,100,250,500,1000,2500], units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'NS') -> None:
        """
        Specifies the set up of the horizontal axis for the oscillisope. The the bound is used to make an axis symmetric about 0. 
        And can only be the accepted values ex: -25 and 25 Units
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.

        Arguments
        lower_bound, upper_bound: Specify the lower and upper bounds of the time axis

        TODO:Test the offest makes sense being trigger delay
        """
        if bound not in [5,10,25,50,100,250,500,1000,2500]:
            raise ValueError(f"The bound you chose is not one of the accepted bounds 5,10,25,50,100,250,500,1000,2500. It will not produce the expected bounds of (-{bound},{bound}){units}. ")
        time_div = 2*bound/self.num_horizontal_divs
        self.set_time_div(time_div, units=units)

    def set_time_div(self, time_div:Literal[1,2,5,10,20,50,100,200,500], units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'S'):
        """
        Set time per div for a channel. Due to some limitation by the scope, only these are allowed time_divs. If you understand please comment here!
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        if time_div not in [1,2,5,10,20,50,100,200,500]:
            raise ValueError(f"The time/div you chose is not one of the accepted time/divs 1,2,5,10,20,50,100,200,500. It will not produce the expected time/div of ({time_div}){units}/div. ")
        self._conn.write(f"TIME_DIV {time_div}{units}")
    
    def set_trigger_delay(self, delay:float, units:Literal['S', 'NS', 'US', 'MS', 'KS'] = 'S'):
        """
        Sets the time at which the trigger is to  occur in respect of the first acquired data 
        point (displayed at the left-hand edge of the screen).
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        self._conn.write(f"TRIG_DELAY {delay}{units}")

    def set_trigger_mode(self, mode: Literal['SINGLE', 'NORM', 'AUTO', 'STOP']):
        self._conn.write(f'TRIG_MODE {mode}')
    
    def set_trigger_slope(self, slope:Literal["POS", "NEG", "WINDOW"]):
        self._conn.write(f"TRIG_SLOPE {slope}")

    def set_trigger_select(self, channel:Channel, condition:Literal["EDGE"]=None, level:float=-0.1, units:Literal['V', 'MV'] = 'V'):
        """
        Select what channel to use as trigger and selects the condition that will trigger acquisition. Right now, only edge is supported
        Channel: what channel you wish to set the trigger on.
        condition: You can set how you wish the oscilliscope to trigger (ex: edge is on the pulse edge)

        The command has more options, please visit the documentation if you wish to do something more complicated.
        FIXME: If another channel is set as trigger channel, change it.
        """
        assert all(not chnl.is_trigger_channel for chnl in self.channels.values()), "For simplicity, only one channel can be desiginated as the trigger channel"
        channel.is_trigger_channel = True
        self._conn.write(f"TRIG_SELECT {condition},SR,C{channel.number}")
        self._conn.write(f'C{channel.number}:TRIG_LEVEL {level}{units}')

    def set_sample_rate(self, value):
        ...

    def set_display(self, status: Literal["ON", "OFF"]):
        """This can only be changed programmatically!"""
        self._conn.write(f"DISPlay {status}")

    def reset(self):
        """Same as hitting default on the scope."""
        self._conn.write("*RST")

    ################ ACQUISITION METHODS ######################
    def enable_sequence_mode(self, num_events: int):
        """
        Using Sequence Mode, thousands of trigger events can be stored as segments into the oscilloscope's acquisition memory 
        (the exact number depends on oscilloscope model and memory options). This is ideal when capturing many fast pulses in 
        quick succession with minimum dead time or when capturing few events separated by long time periods. The instrument 
        can capture complicated sequences of events over large time intervals in fine detail, while ignoring the uninteresting 
        periods between the events. You can also make time measurements between events on selected segments using the full 
        precision of the acquisition timebase. 

        https://www.teledynelecroy.com/doc/tutorial-sequence-mode
        """
        self._conn.write(f"SEQ ON,{num_events}")


    def __repr__(self):
        """
        The *IDN? query identifies the instrument type
        and software version. The response consists of
        four different fields providing information on the
        manufacturer, the scope model, the serial
        number and the firmware revision.
        """
        idn = self._conn.query("*IDN?").split(',')
        names = ['manufacturer', 'scope model', 'serial number', 'firmware version']
        if len(idn) != len(names):
            raise ValueError("Unexpected response format")
        return '\n'.join(f"{name} = {value}" for name, value in zip(names, idn))

rm = visa.ResourceManager("@py")
with rm.open_resource(f'TCPIP0::192.168.0.6::INSTR') as scope_conn:
    lecroy = Lecroy(scope_conn, active_channels=[2,3])
    lecroy.set_horizontal_axis(25, units='NS') # set_horizontal_axis()

    # Set up Trigger Channel
    lecroy.channels[2].set_coupling('D50')
    lecroy.channels[2].set_vertical_axis(-2,2, units='V')
    lecroy.set_trigger_select(lecroy.channels[2], condition="EDGE", level=-0.2, units='V')
    lecroy.set_trigger_mode('NORMAL')
    lecroy.set_trigger_slope('NEG')

    # Set up Channel 3
    lecroy.channels[3].set_coupling('D50')
    lecroy.channels[3].set_vertical_axis(-2,2, units='V') 

    lecroy._conn.write("DISPlay ON")






#lecroy._conn.write("GRID QUAD")

# lecroy.horizontal_axis(-25, 25, units='NS')

# lecroy.trigger_mode('NORMAL')
# lecroy.trigger_slope('NEG')
# lecroy.trigger_select(lecroy.channels[2], condition="EDGE", level=-0.2, units='V')

# START ON LINE 153