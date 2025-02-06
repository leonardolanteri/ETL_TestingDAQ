from pathlib import Path
import argparse
import os
import time
import datetime
import pyvisa as visa
import glob
import pdb

class RunLecroy:
    """
    This is the manual for all of the commands:
    https://cdn.teledynelecroy.com/files/manuals/wr2_rcm_revb.pdf
    """
    def __init__(self, ip_address: str):
        # Set Up Connection to Oscilliscope
        rm = visa.ResourceManager("@py")
        self.lecroy = rm.open_resource(f'TCPIP0::{ip_address}::INSTR')
        self.lecroy.timeout = 3000000
        self.lecroy.encoding = 'latin_1'
        self.lecroy.clear()

        self.lecroy.write('STOP') #Stops any acquisition processes
        self.lecroy.write("*CLS") #not sure what this does

        # This makes it so the scope just returns the number and not extra information
        self.lecroy.write("COMM_HEADER OFF")
        self.lecroy.write("BANDWIDTH_LIMIT OFF")

        # This is standard for oscilliscopes (number of boxes on the screen in vert and horz direction)
        self.num_vertical_divs = 8
        self.num_horizontal_divs = 10

    def vertical_setup(self, channel: int, lower_bound: float=-1, upper_bound: float=1) -> None:
        """
        Specifies the set up of the vertical axis for the oscillisope. The start and 
        stop arguments specify the range of voltage values for the vertical axis.

        Arguments
        channel: Oscillsicope channel 
        start: Lower bound value in Volts for the vertical axis.
        stop: Upper bound value in Volts for the vertical axis.
        """   
        volts_div = (upper_bound - lower_bound) / self.num_vertical_divs
        offset = (upper_bound+lower_bound)/2
        print(f"Setting channel {channel} to {volts_div} V/div with an offset of {offset}")
        self.lecroy.write(f"C{channel}:COUPLING D50")
        self.lecroy.write(f"C{channel}:VOLT_DIV {volts_div}V")
        self.lecroy.write(f"C{channel}:OFFSET {offset}V")

    def horizontal_setup(self, lower_bound:float=-25e-9, upper_bound: float=25e-9) -> None:
        """
        Specifies the set up of the horizontal axis for the oscillisope. The start and 
        stop arguments specify the range of time values for the horizontal axis.

        Arguments
        channel: Oscillsicope channel 
        start: Lower bound value in Seconds for the horizontal axis.
        stop: Upper bound value in Seconds for the horizontal axis.
        """
        time_div = (upper_bound-lower_bound)/self.num_horizontal_divs
        self.lecroy.write(f"TIME_DIV {time_div}S")
        self.lecroy.write(f"TRIG_DELAY")
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
        idn = self.lecroy.query("*IDN?").split(',')
        names = ['manufacturer', 'scope model', 'serial number', 'firmware version']
        if len(idn) != len(names):
            raise ValueError("Unexpected response format")
        return '\n'.join(f"{name} = {value}" for name, value in zip(names, idn))

lecroy = RunLecroy("192.168.0.6")
lecroy.vertical_setup(2, lower_bound=-2, upper_bound=0.5)
lecroy.horizontal_setup(2, -2, 0.5)