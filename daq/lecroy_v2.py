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

    def set_coupling(self, coupling:Literal['A1M', 'D1M', 'D50', 'GND']):
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

    def show(self):
        self._conn.write(rf"""vbs 'app.acquisition.C{self.number}.View=True' """)

    def hide(self):
        self._conn.write(rf"""vbs 'app.acquisition.C{self.number}.View=False' """)

class Lecroy:
    """
    ---------------------------------------------------------------
    WARNING: This CLASS METHODS NEED A MASSIVE REFACTOR
    - add querying
    - change from Set methods to properties with setters defined
    ----------------------------------------------------------------
    This is the manual for all of the commands:
    https://cdn.teledynelecroy.com/files/manuals/maui-remote-control-and-automation-manual.pdf 

    Page 4-3 (or 99 in pdf) shows the app strucutre for commands

    EVEN BETTER is to go on the scope, in the XStream Browser (on the homepage), and you can see ALL
    the available methods :))
    """
    def __init__(self, lecroy_connection: visa.resources.Resource, active_channels:list[int] = None):
        self.num_horizontal_divs = 10
        self._conn = lecroy_connection
        
        # Timeout = will wait X ms for operatioins to complete, see page 2-15
        self._conn.timeout = 5000 # millisceconds
        self._conn.encoding = 'latin_1'
        
        # Clears out the buffers on the scope listing the commands sent to it and also responses sent from it. 
        # Clear removes anything leftover from a previous use
        self._conn.clear()
        
        # This is important to always put the scope back in the same starting place, makes the program STATELESS
        self.reset()
        self.wait_til_idle(5) # recommended by documentation
        # this is just good to stop any previous acquisitions, unlikely but to be safe!
        self.stop_acquistion()
        self._conn.write("*CLS") # Clears all status registers, not sure why important?

        # This makes it so the scope just returns the number and not extra information
        self._conn.write("COMM_HEADER OFF")
        self._conn.write("BANDWIDTH_LIMIT OFF")

        self.channels = {
            1: Channel(1, self._conn),
            2: Channel(2, self._conn),
            3: Channel(3, self._conn),
            4: Channel(4, self._conn)
        }

        self.active_channel_numbers = active_channels if active_channels is not None else []
        self.active_channels = []
        for chnl in self.channels.values():
            if chnl.number in self.active_channel_numbers:
                self.active_channels.append(chnl)
                chnl.show()
            else:
                chnl.hide()
        self.set_active_channels(len(self.active_channels))

        #self._conn.write(f"DISPlay OFF")
        self.trigger_channel: Channel = None

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
        # self._conn.write(f'TRIG_MODE {mode}')
        self._conn.write(rf"""vbs 'app.acquisition.triggermode = "{mode.upper()}" ' """)
    
    def set_trigger_slope(self, slope:Literal["POS", "NEG", "WINDOW"]):
        if self.trigger_channel is None:
            raise ValueError("Please set the trigger channel using the trigger select method before setting the trigger slope!")
        self._conn.write(f"C{self.trigger_channel.number}:TRIG_SLOPE {slope}")

    def set_trigger_select(self, channel:Channel, condition:Literal["EDGE"]=None, level:float=-0.1, units:Literal['V', 'MV'] = 'V'):
        """
        Select what channel to use as trigger and selects the condition that will trigger acquisition. Right now, only edge is supported
        Channel: what channel you wish to set the trigger on.
        condition: You can set how you wish the oscilliscope to trigger (ex: edge is on the pulse edge)

        The command has more options, please visit the documentation if you wish to do something more complicated.
        """
        self.trigger_channel = channel
        self._conn.write(f"TRIG_SELECT {condition},SR,C{channel.number}")
        self._conn.write(f'C{channel.number}:TRIG_LEVEL {level}{units}')

    def set_active_channels(self, n_active_channels: int):
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.ActiveChannels = "{n_active_channels}"' """)

    def set_sample_rate(self, gigasamples_per_second: Literal[10,20]):
        # need to make condition for nactive channels for the set rate!
        n_active_channels = self._conn.query(rf"""vbs? 'return=app.Acquisition.Horizontal.ActiveChannels' """)
        if n_active_channels.strip() != '2' and gigasamples_per_second==20:
            raise ValueError(f"Can only set 20GS/s if there only two active channels, you have: {n_active_channels}. You can set that with a method.")
        if set(self.active_channel_numbers) != set([2,3]) and gigasamples_per_second==20:
            raise ValueError(f"20 GS/s mode can only be applied for using channels 2 and 3. See page 46 for more information on how the channels actually combine to allow for this upsampling: https://cdn.teledynelecroy.com/files/manuals/waverunner-8000-operators-manual.pdf")
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.Maximize = "FixedSampleRate"' """)
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.SampleRate = "{gigasamples_per_second} GS/s"' """)

    def set_display(self, status: Literal["ON", "OFF"]):
        """This can only be changed programmatically!"""
        self._conn.write(f"DISPlay {status}")

    def set_sample_mode(self, mode: Literal[0, "RealTime", "Sequence", "RIS"]):
        """
        ## Sequence Mode
        Using Sequence Mode, thousands of trigger events can be stored as segments into the oscilloscope's acquisition memory 
        (the exact number depends on oscilloscope model and memory options). This is ideal when capturing many fast pulses in 
        quick succession with minimum dead time or when capturing few events separated by long time periods. The instrument 
        can capture complicated sequences of events over large time intervals in fine detail, while ignoring the uninteresting 
        periods between the events. You can also make time measurements between events on selected segments using the full 
        precision of the acquisition timebase. 

        https://www.teledynelecroy.com/doc/tutorial-sequence-mode
        """
        self._conn.write(fr"""vbs app.Acquisition.Horizontal.SampleMode = "{mode}" """)


    def is_sequence_mode(self):
        sample_mode = self._conn.query(r"""vbs? 'return=app.Acquisition.Horizontal.SampleMode' """)
        if sample_mode.strip() != 'Sequence':
            raise ValueError("You should only set this if you are in sequence mode.")        
        return True

    def set_number_of_segments(self, num_segments):
        """
        Sets the number of segments for sequence mode.
        """
        self.is_sequence_mode()
        self._conn.write(fr"""vbs app.Acquisition.Horizontal.NumSegments = "{num_segments}" """)
    
    def set_segment_display(self, mode: Literal["Adjacent","Overlay","Waterfall","Perspective","Mosaic"]):
        """Options to view the segments on the display."""
        self.is_sequence_mode()
        self._conn.write(fr"""vbs app.Display.SegmentMode = "{mode}" """)

    def sequence_timeout(self, seconds: int, disable_timeout=False):
        """Following valid trigger of first segment, use sequence timout to automatically interrupt the sequence acquisition if the timout value is exceeded without a valid trigger."""
        self.is_sequence_mode()
        if disable_timeout:
            self._conn.write(fr"""vbs app.Acquisition.Horizontal.SequenceTimoutEnable = "{not disable_timeout}" """)
        else:
            self._conn.write(fr"""vbs app.Acquisition.Horizontal.SequenceTimeout = "{seconds}" """)

    def stop_acquistion(self):
        return self._conn.write(r"""vbs 'app.acquisition.triggermode = "stopped" ' """)
    
    def reset(self):
        """
        Same as hitting default on the scope.
        
        An equal command is:         
        self._conn.write(r\"\"\"vbs 'app.settodefaultsetup' \"\"\")
        """
        self._conn.write("*RST")

    
    def wait_til_idle(self, seconds):
        """
        This will wait until the application is idle for 5 seconds (the default unit for this command) before going on
        """
        self._conn.query(rf"""vbs? 'return=app.WaitUntilIdle({seconds})' """)

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
    
    # Set up Trigger Channel

    lecroy.channels[2].set_coupling('D50')
    lecroy.channels[2].set_vertical_axis(-2,2, units='V')
    lecroy.set_trigger_mode('NORM')
    lecroy.set_trigger_select(lecroy.channels[2], condition="EDGE", level=-0.2, units='V')
    lecroy.set_trigger_slope('NEG')
    lecroy.set_horizontal_axis(25, units='NS') # set_horizontal_axis()

    # Set up Channel 3
    lecroy.channels[3].set_coupling('D50')
    lecroy.channels[3].set_vertical_axis(-2,2, units='V') 

    #lecroy._conn.write("DISPlay ON")
    lecroy.set_sample_mode("Sequence")
    lecroy.set_segment_display("Overlay")
    lecroy.sequence_timeout(2e-9)
    lecroy.set_number_of_segments(20)
    lecroy.set_sample_rate(20)

    # Follow acuqisition steps in manual
    # Follow seq steps to left
    # then return and save data


#lecroy._conn.write("GRID QUAD")

# lecroy.horizontal_axis(-25, 25, units='NS')

# lecroy.trigger_mode('NORMAL')
# lecroy.trigger_slope('NEG')
# lecroy.trigger_select(lecroy.channels[2], condition="EDGE", level=-0.2, units='V')

# START ON LINE 153