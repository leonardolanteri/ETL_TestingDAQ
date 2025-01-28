
import sys
import numpy as np

class LecroyReader:
    def __init__(self, path, secondDigits = 3):
        """
        Followed this project, with some simplifications: 
        
        https://github.com/bennomeier/leCroyParser

        Manual With file format found here - I believe its the same for our 8104 model (hopefully...)
        https://cdn.teledynelecroy.com/files/manuals/waverunner9000-om-eng.pdf
        """

        self.path = path
        self.second_digits = 3
        with open(self.path, 'rb') as scope_file:
            self.data = scope_file.read()
    
        self.endianness = "<"

        waveSourceList = ["Channel 1", "Channel 2", "Channel 3", "Channel 4", "Unknown"]
        verticalCouplingList = ["DC50", "GND", "DC1M", "GND", "AC1M"]
        bandwidthLimitList = ["off", "on"]
        recordTypeList = ["single_sweep", "interleaved", "histogram", "graph",
                          "filter_coefficient", "complex", "extrema", "sequence_obsolete",
                          "centered_RIS", "peak_detect"]
        processingList = ["No Processing", "FIR Filter", "interpolated", "sparsed",
                          "autoscaled", "no_resulst", "rolling", "cumulative"]

        # convert the first 50 bytes to a string to find position of substring WAVEDESC
        self.posWAVEDESC      = self.data[:50].decode("ascii", "replace").index("WAVEDESC")
        self.commOrder        = self.parseInt16(34)  # big endian (>) if 0, else little
        self.endianness       = [">", "<"][self.commOrder]
        self.templateName     = self.parseString(16)
        self.commType         = self.parseInt16(32)  # encodes whether data is stored as 8 or 16bit
        self.waveDescriptor   = self.parseInt32(36)
        self.userText         = self.parseInt32(40)
        self.trigTimeArray    = self.parseInt32(48)
        self.waveArray1       = self.parseInt32(60)
        self.instrumentName   = self.parseString(76)
        self.instrumentNumber = self.parseInt32(92)
        self.waveArrayCount   = self.parseInt32(116)
        self.n_events = self.parseInt32(144) # OR another name is sequenceSegments
        self.verticalGain     = self.parseFloat(156)
        self.verticalOffset   = self.parseFloat(160)
        self.maxDACValue         = self.parseFloat(164) # used to help remove saturated signals!
        self.minDACValue         = self.parseFloat(168)
        self.nominalBits      = self.parseInt16(172)
        self.horizInterval    = self.parseFloat(176)
        # Trigger offset in time domain for 0th sweep of trigger, 
        # measured in seconds from triggers 0th data point (ie. actual trigger delay)
        self.horizOffset      = self.parseDouble(180)
        
        # after these points, the signals saturate!
        self.maxVerticalValue = self.convert_dac_value(self.maxDACValue)
        self.minVerticalValue = self.convert_dac_value(self.minDACValue)

        # 502 points for 10Gs sampling
        self.points_per_frame = int(self.waveArrayCount / self.n_events) 

        self.vertUnit   = "NOT PARSED"
        self.horUnit    = "NOT PARSED"
        self.traceLabel = "NOT PARSED"

        self.triggerTime      = self.parseTimeStamp(296, secondDigits = secondDigits)
        self.recordType       = recordTypeList[self.parseInt16(316)]
        self.processingDone   = processingList[self.parseInt16(318)]
        self.timeBase         = self.parseTimeBase(324)
        self.verticalCoupling = verticalCouplingList[self.parseInt16(326)]
        self.bandwidthLimit   = bandwidthLimitList[self.parseInt16(334)]
        self.waveSource       = waveSourceList[self.parseInt16(344)]
        self.offset           = self.posWAVEDESC + self.waveDescriptor + self.userText  

        if self.commType == 0: # data is stored in 8bit integers
            dtype = np.dtype((self.endianness + "i1", self.waveArray1))
        else:                  # 16 bit integers
            dtype = np.dtype((self.endianness + "i2", self.waveArray1 // 2))
        y = np.frombuffer(
            self.data, 
            dtype=dtype, 
            count=1, 
            #self.offset is 357 while triTimeArray is 80000, which is all the bytes needed to get the time offset information
            offset=self.offset + self.trigTimeArray
        )[0]
        # now scale the ADC values
        self.y = self.convert_dac_value(y).reshape(-1, self.points_per_frame)
        
        # For sequence waveforms, defined on page 41, https://cdn.teledynelecroy.com/files/manuals/wr2_rcm_revb.pdf :
        _, trigger_offset = self.segment_times
        self.x = trigger_offset[:,np.newaxis] + self.horizInterval * np.linspace(
            np.zeros(self.n_events),  
            np.ones(self.n_events)*(self.points_per_frame-1), 
            self.points_per_frame, 
            axis=-1) 
    
    @property
    def segment_times(self) -> tuple[np.ndarray, np.ndarray]:
        """
        From this manual, https://cdn.teledynelecroy.com/files/manuals/wr2_rcm_revb.pdf here are some excerpts:
        On page 35, Sequence Acquisition Times block (TRIGTIME),
        "This is needed for sequence acquisitions to record the exact timing information for each segment. 
        It contains the time of each trigger relative to the trigger of the first segment, 
        as well as the TIME OF THE FIRST DATA POINT OF EACH SEGMENT RELATIVE TO ITS TRIGGER."
        
        On page 271 you get an explanation of TRIGTIME ARRAY:
        "This optional time array is only present with SEQNCE waveforms.
        The following data block is repeated for each segment which makes up the acquired sequence record.
        < 0> TRIGGER_TIME: double ; for sequence acquisitions, time in seconds from first trigger to this one
        < 8> TRIGGER_OFFSET: double ; the trigger offset is in seconds from trigger to zeroth data point"
        ---------------------------------------------------------------------        
        TIMEOFFSET (BETWEEN CHANNELS) CALCULATION 
        The time offset is the difference between trigger_offset for different channels. 
        Subtracting the two arrays reveals the time difference between channel starting points.
        """

        # calleld trigger_offset in the manual
        dtype = np.dtype([('trigger_times', np.float64), ('trigger_offset', np.float64)])
        with open(self.path, 'rb') as my_file:
            my_file.seek(self.offset)
            buffer = my_file.read(self.n_events * dtype.itemsize)
        seg_times = np.frombuffer(buffer, dtype=dtype, count=self.n_events)
        trigger_times, trigger_offsets = zip(*seg_times)
        return np.array(trigger_times), np.array(trigger_offsets)

    def convert_dac_value(self, dac_val):
        """
        See vertical offset calculation in manual, byte 160
        https://cdn.teledynelecroy.com/files/manuals/waverunner9000-om-eng.pdf
        """
        return self.verticalGain * dac_val - self.verticalOffset

    def unpack(self, pos, formatSpecifier, length):
        """ a wrapper that reads binary data
        in a given position in the file, with correct endianness, and returns the parsed
        data as a tuple, according to the format specifier. """
        start = pos + self.posWAVEDESC
        return np.frombuffer(self.data[start:start + length], self.endianness + formatSpecifier, count=1)[0]

    def parseString(self, pos, length=16):
        s = self.unpack(pos, "S{}".format(length), length)
        if sys.version_info > (3, 0):
            s = s.decode('ascii')
        return s

    def parseInt16(self, pos):
        return self.unpack(pos, "u2", 2)

    def parseWord(self, pos):
        return self.unpack(pos, "i2", 2)

    def parseInt32(self, pos):
        return self.unpack(pos, "i4", 4)

    def parseFloat(self, pos):
        return self.unpack(pos, "f4", 4)

    def parseDouble(self, pos):
        return self.unpack(pos, "f8", 8)

    def parseByte(self, pos):
        return self.unpack(pos, "u1", 1)

    def parseTimeStamp(self, pos, secondDigits = 3):
        second = self.parseDouble(pos)
        minute = self.parseByte(pos + 8)
        hour = self.parseByte(pos + 9)
        day = self.parseByte(pos + 10)
        month = self.parseByte(pos + 11)
        year = self.parseWord(pos + 12)

        secondFormat = "{:0" + str(secondDigits + 3) + "." + str(secondDigits) + "f}"
        fullFormat = "{}-{:02d}-{:02d} {:02d}:{:02d}:" + secondFormat

        return fullFormat.format(year, month, day, hour, minute, second)
    
    def parseTimeBase(self, pos):
        """ time base is an integer, and encodes timing information as follows:
        0 : 1 ps  / div
        1:  2 ps / div
        2:  5 ps/div, up to 47 = 5 ks / div. 100 for external clock"""

        timeBaseNumber = self.parseInt16(pos)

        if timeBaseNumber < 48:
            unit = "pnum k"[int(timeBaseNumber / 9)]
            value = [1, 2, 5, 10, 20, 50, 100, 200, 500][timeBaseNumber % 9]
            return "{} ".format(value) + unit.strip() + "s/div"
        elif timeBaseNumber == 100:
            return "EXTERNAL"

    def __repr__(self):
        string = "Le Croy Scope Data\n"
        string += "Path: " + self.path + "\n"
        string += "Endianness: " + self.endianness + "\n"
        string += "Instrument: " + self.instrumentName + "\n"
        string += "Instrument Number: " + str(self.instrumentNumber) + "\n"
        string += "Template Name: " + self.templateName + "\n"
        string += "Channel: " + self.waveSource + "\n"
        string += "WaveArrayCount: " + str(self.waveArrayCount) + "\n"
        string += "Vertical Coupling: " + self.verticalCoupling + "\n"
        string += "Bandwidth Limit: " + self.bandwidthLimit + "\n"
        string += "Record Type: " + self.recordType + "\n"
        string += "Processing: " + self.processingDone + "\n"
        string += "TimeBase: " + self.timeBase + "\n"
        string += "TriggerTime: " + self.triggerTime + "\n"
        return string