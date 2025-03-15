from __future__ import annotations

import pyvisa as visa
from typing import Literal, List
from pydantic import validate_call, ConfigDict
import logging

logger = logging.getLogger(__name__)

SegmentDisplayMode = Literal["Adjacent","Overlay","Waterfall","Perspective","Mosaic"]
VoltageUnits = Literal["V", "MV"]
Coupling = Literal['A1M', 'D1M', 'D50', 'GND']
FileFormat = Literal['Binary', 'ACII', 'Excel', 'MATLAB', 'MathCad']
TimeUnits = Literal['S', 'NS', 'US', 'MS', 'KS']
TriggerMode = Literal['SINGLE', 'NORM', 'AUTO', 'STOP']
HorizontalWindow = Literal[5,10,25,50,100,250,500,1000,2500]
TimeDiv = Literal[1,2,5,10,20,50,100,200,500]
TriggerSlope = Literal["POS", "NEG", "WINDOW"]
SampleMode = Literal[0, "RealTime", "Sequence", "RIS"]
SampleRate = Literal[10,20]
TriggerCondition = Literal["EDGE"]

class Channel:
    def __init__(self, channel:int, lecroy_connection: visa.resources.Resource):
        self.number = channel
        self._conn = lecroy_connection
        # This is standard for oscilliscopes (number of boxes on the screen in vert and horz direction)
        self.num_vertical_divs = 8

    @validate_call # makes sure units of the right type!
    def set_vertical_axis(self, lower_bound:float, upper_bound:float, units:VoltageUnits='V'):
        """
        Specifies the set up of the vertical axis for the oscillisope. The start and 
        stop arguments specify the range of VoltageUnits values for the vertical axis.

        Arguments
        channel: Oscillsicope channel 
        lower_bound, upper_bound: Specify the lower and upper bounds of the vertical axis
        """
        volts_div = abs(upper_bound - lower_bound) / self.num_vertical_divs
        offset = (upper_bound+lower_bound)/2
        self.set_volts_div(volts_div, units=units)
        # You want the opposite sign of offset to get correct display
        self.set_vertical_offset(-offset, units=units)

    @validate_call
    def set_volts_div(self, volts_div:float, units:VoltageUnits = 'V'):
        """Set volts per div for a channel"""
        self._conn.write(f"C{self.number}:VOLT_DIV {volts_div}{units}")
    
    @validate_call
    def set_vertical_offset(self, offset:float, units:VoltageUnits = 'V'):
        """Sets the coupling, """
        self._conn.write(f"C{self.number}:OFFSET {offset}{units}")
    
    @validate_call
    def set_coupling(self, coupling:Coupling):
        """
        https://blog.teledynelecroy.com/2020/08/how-do-you-choose-whether-to-use-50-ohm.html

        DANGER, DANGER
        However, if your input DC or RMS VoltageUnits is close to or above 5 V, DO NOT USE the 50 Ohm input to the scope!
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

    @validate_call
    def save(self, run_number:int=0, file_format:FileFormat='Binary'):
        """ Saves the aquired waveforms displayed on the screen."""
        self._conn.write(rf"""vbs app.SaveRecall.Waveform.SaveSource = "C{self.number}" """)
        self._conn.write(rf"""vbs app.SaveRecall.Waveform.WaveFormat = "{file_format}" """)
        self._conn.write(rf"""vbs 'app.SaveRecall.Waveform.TraceTitle = "Trace{run_number}"' """)
        self._conn.write(r"""vbs 'app.SaveRecall.Waveform.SaveFile' """)
        logger.info(f"Saved waveform for run {run_number} on channel {self.number}")


class LecroyController:
    """
    ---------------------------------------------------------------
    WARNING: This CLASS METHODS NEED A MASSIVE REFACTOR FOR BETTER NAMESPACE
    - add querying
    - change from Set methods to properties with setters defined
    ----------------------------------------------------------------
    This is the manual for all of the commands:
    https://cdn.teledynelecroy.com/files/manuals/maui-remote-control-and-automation-manual.pdf 

    Page 4-3 (or 99 in pdf) shows the app strucutre for commands

    EVEN BETTER is to go on the scope, in the XStream Browser (on the homepage), and you can see ALL
    the available methods :))
    """
    def __init__(self, ip_address: str, active_channels:List[int] = None):
        self.rm = visa.ResourceManager("@py")
        self.ip_address = ip_address
        self.num_horizontal_divs = 10
        self._conn = None
        self.active_channel_numbers = active_channels if active_channels is not None else []

    def __enter__(self) -> LecroyController:
        self._conn = self.rm.open_resource(f'TCPIP0::{self.ip_address}::INSTR')
                # Timeout = will wait X ms for operatioins to complete, see page 2-15
        self._conn.timeout = 60*60*1e3 # 1 hour
        self._conn.encoding = 'latin_1'
        # Clears out the buffers on the scope listing the commands sent to it and also responses sent from it. 
        self._conn.clear()
        # This makes it so the scope just returns the number and not extra information
        self.stop_acquistion()
        self._conn.write("*CLS") # clears status registers

        self._conn.write("COMM_HEADER OFF")
        self._conn.write("BANDWIDTH_LIMIT OFF")
        # This is important to always put the scope back in the same starting place, makes the program STATELESS
        self.reset()
        # Recommended by documentation page 2-16 in maui-remote control manual
        setup_wait = self.wait_til_idle(5) 
        logger.info(f"Scope reset to defualt settings complete: {setup_wait}")
        # this is just good to stop any previous acquisitions, unlikely but to be safe!

        self.channels = {
            1: Channel(1, self._conn),
            2: Channel(2, self._conn),
            3: Channel(3, self._conn),
            4: Channel(4, self._conn)
        }

        self.active_channels: List[Channel] = []
        for chnl in self.channels.values():
            if chnl.number in self.active_channel_numbers:
                self.active_channels.append(chnl)
                chnl.show()
            else:
                chnl.hide()
        self.set_active_channels(len(self.active_channels))

        #self._conn.write(f"DISPlay OFF")
        self.trigger_channel: Channel = None
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type == KeyboardInterrupt:
            print("\n")
            logger.warning("****************** READ ME ******************")
            logger.warning("If running a scope acquisioin and you Cntrl-C'ed out of it")
            logger.warning("Please manually stop the scope or wait for the acquisition to finish on the scope before.")
            logger.warning("Otherwise you will get connection error to the scope!")
            logger.warning("****************** READ ME ******************")
            print("\n")

        if self._conn is not None:
            self._conn.close()
        self.rm.close()

    @validate_call
    def set_horizontal_window(self, bound: HorizontalWindow, units:TimeUnits = 'NS') -> None:
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

    @validate_call
    def set_time_div(self, time_div:TimeDiv, units:TimeUnits = 'S'):
        """
        Set time per div for a channel. Due to some limitation by the scope, only these are allowed time_divs. If you understand please comment here!
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        if time_div not in [1,2,5,10,20,50,100,200,500]:
            raise ValueError(f"The time/div you chose is not one of the accepted time/divs 1,2,5,10,20,50,100,200,500. It will not produce the expected time/div of ({time_div}){units}/div. ")
        self._conn.write(f"TIME_DIV {time_div}{units}")
    
    @validate_call
    def set_trigger_delay(self, delay:float, units:TimeUnits = 'S'):
        """
        Sets the time at which the trigger is to  occur in respect of the first acquired data 
        point (displayed at the left-hand edge of the screen).
        NS for nanoseconds, US for microseconds, MS for milliseconds, S for seconds, or KS for kiloseconds.
        """
        self._conn.write(f"TRIG_DELAY {delay}{units}")

    @validate_call
    def set_trigger_mode(self, mode: TriggerMode):
        """
        ## Auto
        which triggers the oscilloscope after a set time, even if the trigger conditions are not met.
        ## Normal 
        Which triggers the oscilloscope each time a signal is present that meets the trigger conditions.
        ## Single 
        The first press readies the oscilloscope to trigger. The second press arms and triggers the oscilloscope once (single-shot acquisition) when the input signal meets the trigger conditions.
        ## Stop 
        Stop prevents the scope from triggering on a signal
        """
        self._conn.write(rf"""vbs 'app.acquisition.triggermode = "{mode.upper()}" ' """)
    
    @validate_call
    def set_trigger_slope(self, slope:TriggerSlope):
        if self.trigger_channel is None:
            raise ValueError("Please set the trigger channel using the trigger select method before setting the trigger slope!")
        self._conn.write(f"C{self.trigger_channel.number}:TRIG_SLOPE {slope}")

    @validate_call(config=ConfigDict(arbitrary_types_allowed=True))
    def set_trigger_select(self, channel:Channel, condition:TriggerCondition=None, level:float=-0.1, units:VoltageUnits = 'V'):
        """
        Select what channel to use as trigger and selects the condition that will trigger acquisition. Right now, only edge is supported
        Channel: what channel you wish to set the trigger on.
        condition: You can set how you wish the oscilliscope to trigger (ex: edge is on the pulse edge)

        The command has more options, please visit the documentation if you wish to do something more complicated.
        """
        self.trigger_channel = channel
        self._conn.write(f"TRIG_SELECT {condition},SR,C{channel.number}")
        self._conn.write(f'C{channel.number}:TRIG_LEVEL {level}{units}')

    @validate_call
    def set_active_channels(self, n_active_channels: int):
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.ActiveChannels = "{n_active_channels}"' """)

    @validate_call
    def set_sample_rate(self, gigasamples_per_second:SampleRate):
        # need to make condition for nactive channels for the set rate!
        n_active_channels = self._conn.query(rf"""vbs? 'return=app.Acquisition.Horizontal.ActiveChannels' """)
        if n_active_channels.strip() != '2' and gigasamples_per_second==20:
            raise ValueError(f"Can only set 20GS/s if there only two active channels, you have: {n_active_channels}. You can set that with a method.")
        if set(self.active_channel_numbers) != set([2,3]) and gigasamples_per_second==20:
            raise ValueError(f"20 GS/s mode can only be applied for using channels 2 and 3. See page 46 for more information on how the channels actually combine to allow for this upsampling: https://cdn.teledynelecroy.com/files/manuals/waverunner-8000-operators-manual.pdf")
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.Maximize = "FixedSampleRate"' """)
        self._conn.write(rf"""vbs 'app.Acquisition.Horizontal.SampleRate = "{gigasamples_per_second} GS/s"' """)

    @validate_call
    def set_display(self, status: Literal["ON", "OFF"]):
        """This can only be changed programmatically!"""
        self._conn.write(f"DISPlay {status}")

    @validate_call
    def set_sample_mode(self, mode: SampleMode):
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

    @validate_call
    def set_number_of_segments(self, num_segments: int):
        """
        Sets the number of segments for sequence mode.
        """
        self.is_sequence_mode()
        self._conn.write(fr"""vbs app.Acquisition.Horizontal.NumSegments = "{num_segments}" """)
    
    @validate_call
    def set_segment_display(self, mode: SegmentDisplayMode):
        """Options to view the segments on the display."""
        self.is_sequence_mode()
        self._conn.write(fr"""vbs app.Display.SegmentMode = "{mode}" """)

    @validate_call
    def sequence_timeout(self, seconds: int, disable_timeout:bool=False):
        """Following valid trigger of first segment, use sequence timout to automatically interrupt the sequence acquisition if the timout value is exceeded without a valid trigger."""
        self.is_sequence_mode()
        if disable_timeout:
            self._conn.write(fr"""vbs app.Acquisition.Horizontal.SequenceTimoutEnable = "{not disable_timeout}" """)
        else:
            self._conn.write(fr"""vbs app.Acquisition.Horizontal.SequenceTimeout = "{seconds}" """)

    def stop_acquistion(self):
        return self._conn.write("STOP")
    
    def do_acquisition(self):
        """
        Following routine on page 185 or 6-17, this method start the acquisition and wait for it to complete.

        WARNING: **Only tested for sequence sample mode!!** but might be general
        For single acquisitions, there are better methods in the manual!
        """ 
        logger.info("<<<<< STARTING SCOPE ACQUISITION >>>>>>")
        self.stop_acquistion()
        self._conn.write("*CLS") # clear status regisers
        self._conn.write("*TRG") # executes arm command, Group Execute Trigger
        self._conn.write("WAIT") # wait for acquistion to complete, can accept a timeout command
        # When you try to send *OPC? command it won't read it until acquisition is complete because of the wait command!
        # Important because we want to program to hang while we do acquisition, so *OPC? is needed to get that behavior
        self._conn.query("*OPC?") # Operation Complete Query, always returns 1
        logger.info("<<<<< SCOPE ACQUISITION FINISHED >>>>>>")

    def reset(self):
        """
        Same as hitting default on the scope.
        """
        self._conn.write("*RST")

    @validate_call
    def wait_til_idle(self, timeout:int):
        """
        This will wait until the application is idle or until specified timeout
        Units: Seconds
        """
        response = self._conn.query(rf"""vbs? 'return=app.WaitUntilIdle({timeout})' """)
        if isinstance(response, str) and response.strip() != '1':
            raise TimeoutError("Timedout, still not sure about this method, COME ON MAN!")
        return True

    
    def setup_from_config(self, scope_config) -> None:
        """
        Takes the configs and sets up and setups up the oscilliscope based on the config values
        """
        from config import Oscilloscope as OscilloscopeConfig
        from config import TriggerConfig, ChannelConfig
        def setup_trigger(chnl_num:int, trigger_config: TriggerConfig):
            """Sets up trigger channel based on trigger config"""
            self.set_trigger_mode(trigger_config.mode)
            self.set_trigger_select(
                self.channels[chnl_num], 
                condition=trigger_config.condition, 
                level=trigger_config.level, 
                units=trigger_config.units)
            self.set_trigger_slope(trigger_config.slope) 

        def setup_channel(chnl_num: int, channel_config: ChannelConfig):
            """Sets up a channel based on the config"""
            vertical_axis = channel_config.vertical_axis
            self.channels[chnl_num].set_vertical_axis(
                vertical_axis.lower,
                vertical_axis.upper, 
                units=vertical_axis.units)
            self.channels[chnl_num].set_coupling(channel_config.coupling)

        self.set_sample_rate(scope_config.sample_rate[0]) #take first elem because second is the units...
        horz_window, units = scope_config.horizontal_window
        self.set_horizontal_window(horz_window, units=units)
        self.set_sample_mode(scope_config.sample_mode)
        self.set_number_of_segments(scope_config.number_of_segments)
        self.set_segment_display(scope_config.segment_display) 

        for chnl_num, chnl_config in scope_config.channels.items():
            setup_channel(chnl_num, chnl_config)
            if chnl_config.trigger is not None:
                setup_trigger(chnl_num, chnl_config.trigger)

        # Needed for some reason after setup, it seems to begin triggering, stops when calling do_acquisition again though
        self.stop_acquistion() 

    def __repr__(self):
        """
        The *IDN? query identifies the instrument type and software version. The response consists of four different fields providing information on the manufacturer, the scope model, the serial number and the firmware revision.
        """
        idn = self._conn.query("*IDN?").split(',')
        names = ['manufacturer', 'scope model', 'serial number', 'firmware version']
        if len(idn) != len(names):
            raise ValueError("Unexpected response format")
        return '\n'.join(f"{name} = {value}" for name, value in zip(names, idn))

if __name__ == '__main__':
    ...

    # rm = visa.ResourceManager("@py")
    # with rm.open_resource(f'TCPIP0::192.168.0.6::INSTR') as scope_conn:
    #     lecroy = LecroyController(scope_conn, active_channels=[2,3])
    #     lecroy.set_sample_rate(20)

    #     # Set up Trigger Channel
    #     lecroy.channels[2].set_coupling('D50')
    #     lecroy.channels[2].set_vertical_axis(-2,2, units='V')
    #     lecroy.set_trigger_mode('NORM')
    #     lecroy.set_trigger_select(lecroy.channels[2], condition="EDGE", level=-0.2, units='V')
    #     lecroy.set_trigger_slope('NEG')
    #     lecroy.set_horizontal_window(25, units='NS')

    #     # Set up Channel 3
    #     lecroy.channels[3].set_coupling('D50')
    #     lecroy.channels[3].set_vertical_axis(-2,2, units='V') 

    #     lecroy.set_sample_mode("Sequence")
    #     lecroy.set_number_of_segments(5000)
    #     lecroy.set_segment_display("Overlay")

    #     # Sequence Mode Acquisition Routine (184 or 6-16) or (185 or 6-17)
    #     acq_time = time.perf_counter()
    #     lecroy.stop_acquistion()
    #     lecroy.do_acquisition()
    #     print("acq complete", time.perf_counter()-acq_time)

    #     save_time = time.perf_counter()
    #     for channel in lecroy.active_channels:
    #         channel.save(run_number=111)
    #     print("save complete", time.perf_counter()-save_time)