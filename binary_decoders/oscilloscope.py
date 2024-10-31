import struct  #struct unpack result - tuple
import numpy as np
from ROOT import TTree, TFile
import time
import optparse
import argparse
import os

#### Memory addresses #####
WAVEDESC=11
aTEMPLATE_NAME		= WAVEDESC+ 16
aCOMM_TYPE			= WAVEDESC+ 32
aCOMM_ORDER			= WAVEDESC+ 34
aWAVE_DESCRIPTOR	= WAVEDESC+ 36	# length of the descriptor block
aUSER_TEXT			= WAVEDESC+ 40	# length of the usertext block
aTRIGTIME_ARRAY     = WAVEDESC+ 48
aWAVE_ARRAY_1		= WAVEDESC+ 60	# length (in Byte) of the sample array
aINSTRUMENT_NAME	= WAVEDESC+ 76
aINSTRUMENT_NUMBER  = WAVEDESC+ 92
aTRACE_LABEL		= WAVEDESC+ 96
aWAVE_ARRAY_COUNT	= WAVEDESC+ 116
aPNTS_PER_SECREEN   = WAVEDESC+ 120
aFIRST_VALID_PNT    = WAVEDESC+ 124
aLAST_VALID_PNT     = WAVEDESC+ 128
aSEGMENT_INDEX      = WAVEDESC+ 140
aSUBARRAY_COUNT     = WAVEDESC+ 144
aNOM_SUBARRAY_COUNT = WAVEDESC+ 174
aVERTICAL_GAIN		= WAVEDESC+ 156
aVERTICAL_OFFSET	= WAVEDESC+ 160
aNOMINAL_BITS		= WAVEDESC+ 172
aHORIZ_INTERVAL     = WAVEDESC+ 176
aHORIZ_OFFSET		= WAVEDESC+ 180
aVERTUNIT			= WAVEDESC+ 196
aHORUNIT			= WAVEDESC+ 244
aTRIGGER_TIME		= WAVEDESC+ 296
aACQ_DURATION       = WAVEDESC+ 312
aRECORD_TYPE		= WAVEDESC+ 316
aPROCESSING_DONE	= WAVEDESC+ 318
aTIMEBASE			= WAVEDESC+ 324
aVERT_COUPLING		= WAVEDESC+ 326
aPROBE_ATT			= WAVEDESC+ 328
aFIXED_VERT_GAIN	= WAVEDESC+ 332
aBANDWIDTH_LIMIT	= WAVEDESC+ 334
aVERTICAL_VERNIER	= WAVEDESC+ 336
aACQ_VERT_OFFSET	= WAVEDESC+ 340
aWAVE_SOURCE		= WAVEDESC+ 344

def get_waveform_block_offset(filepath_in):
    my_file = open(filepath_in, 'rb')

    my_file.seek(aUSER_TEXT)
    USER_TEXT = struct.unpack('i',my_file.read(4))#ReadLong(fid, aUSER_TEXT);
    my_file.seek(aTRIGTIME_ARRAY)
    TRIGTIME_ARRAY = struct.unpack('i',my_file.read(4))
    my_file.seek(aWAVE_DESCRIPTOR)
    WAVE_DESCRIPTOR = struct.unpack('i',my_file.read(4))

    offset = WAVEDESC + WAVE_DESCRIPTOR[0] + USER_TEXT[0] #+ TRIGTIME_ARRAY[0]
    full_offset = WAVEDESC + WAVE_DESCRIPTOR[0] + USER_TEXT[0] + TRIGTIME_ARRAY[0]
    my_file.close()
    return offset,full_offset


def get_configuration(filepath_in):
    my_file = open(filepath_in, 'rb')
    my_file.seek(aVERTICAL_GAIN)
    vertical_gain = struct.unpack('f',my_file.read(4))[0]
    my_file.seek(aVERTICAL_OFFSET)
    vertical_offset = struct.unpack('f',my_file.read(4))[0]
    my_file.seek(aHORIZ_INTERVAL)
    horizontal_interval = struct.unpack('f',my_file.read(4))[0]
    my_file.seek(aSUBARRAY_COUNT)
    nsegments      = struct.unpack('i',my_file.read(4))[0]
    my_file.seek(aWAVE_ARRAY_COUNT)
    WAVE_ARRAY_COUNT    = struct.unpack('i',my_file.read(4))[0]
    points_per_frame = int(WAVE_ARRAY_COUNT / nsegments)
    my_file.close()
    return {
        'nsegments': nsegments,
        'points_per_frame': points_per_frame,
        'horizontal_interval': horizontal_interval,
        'vertical_gain': vertical_gain,
        'vertical_offset': vertical_offset
    }

def get_segment_times(filepath_in, offset,nsegments):
    my_file = open(filepath_in, 'rb')
    trigger_times = []
    horizontal_offsets = []

    my_file.seek(offset)
    for i_event in range(nsegments):
        trigger_times.append(struct.unpack('d',my_file.read(8))[0])
        horizontal_offsets.append(struct.unpack('d',my_file.read(8))[0])
    
    my_file.close()
    return trigger_times,horizontal_offsets

def get_vertical_array(filepath_in, full_offset, points_per_frame, vertical_gain, vertical_offset, event_number):
    my_file = open(filepath_in, 'rb')

    starting_position = full_offset + 2*points_per_frame*event_number
    my_file.seek(starting_position)
    binary_y_data = my_file.read(2*points_per_frame)
    y_axis_raw = struct.unpack("<"+str(points_per_frame)+"h", binary_y_data)
    y_axis = [vertical_gain*y - vertical_offset for y in y_axis_raw]

    my_file.close()
    return y_axis

def calc_horizontal_array(points_per_frame, horizontal_interval, horizontal_offset):
    x_axis = horizontal_offset + horizontal_interval * np.linspace(0, points_per_frame-1, points_per_frame)
    return x_axis

def converter(trig_chnl_trc_path: str,  clock_chnl_trc_path: str):
    active_chan=2#20GS/s

    trigger_config = get_configuration(trig_chnl_trc_path)
    clock_config = get_configuration(clock_chnl_trc_path)

    vertical_gains = [trigger_config['vertical_gain'], clock_config['vertical_gain']]
    vertical_offsets = [trigger_config['vertical_offset'], clock_config['vertical_offset']]

    nsegments = clock_config['nsegments']
    points_per_frame = clock_config['points_per_frame']
    horizontal_interval = clock_config['horizontal_interval']

    print(f"Number of segments: {nsegments}")
    print(f"Points per segment: {points_per_frame}")
    print(f"Horizontal interval: {horizontal_interval}")

    # for ichan in range(nchanactive_chan):
    for ichan in range(active_chan):#20GS/s
        print("Channel %i"%ichan)
        print("\t vertical_gain %0.3f" % vertical_gains[ichan])
        print("\t vertical offset %0.3f" % vertical_offsets[ichan])

    ### find beginning of trigger time block and y-axis block
    offset, full_offset = get_waveform_block_offset(trig_chnl_trc_path)
    #print "offset is ",offset

    ## get event times and offsets
    trigger_times, horizontal_offsets = get_segment_times(trig_chnl_trc_path, offset, nsegments)
    trigger_times2, horizontal_offsets2 = get_segment_times(clock_chnl_trc_path, offset, nsegments)

    start = time.time()
    outRoot = TFile(outputFile, "RECREATE")
    outTree = TTree("pulse","pulse")

    i_evt = np.zeros(1,dtype=np.dtype("u4"))
    segment_time = np.zeros(1,dtype=np.dtype("f"))
    channel = np.zeros([active_chan, points_per_frame],dtype=np.float32)
    time_array = np.zeros([1, points_per_frame],dtype=np.float32)
    time_offsets = np.zeros(active_chan,dtype=np.dtype("f"))

    outTree.Branch('i_evt',i_evt,'i_evt/i')
    outTree.Branch('segment_time',segment_time,'segment_time/F')
    outTree.Branch('channel', channel, 'channel[%i][%i]/F' %(active_chan,points_per_frame) )#20GS/s
    outTree.Branch('time', time_array, 'time[1]['+str(points_per_frame)+']/F' )
    outTree.Branch('timeoffsets', time_offsets, 'timeoffsets[8]/F')

    for i in range(nsegments):
        if i%1000==0:
            print("Processing event %i" % i)
        channel[0] = get_vertical_array(inputFiles[0], full_offset,points_per_frame, vertical_gains[0], vertical_offsets[0], i)
        channel[1] = get_vertical_array(inputFiles[1], full_offset,points_per_frame, vertical_gains[1], vertical_offsets[1], i)

        time_array[0]    = calc_horizontal_array(points_per_frame, horizontal_interval, horizontal_offsets[i])
        i_evt[0]   = i
        segment_time[0] = trigger_times[i]
        time_offsets[0] = horizontal_offsets[i] -horizontal_offsets[i]
        time_offsets[1] = horizontal_offsets2[i]-horizontal_offsets[i]
        outTree.Fill()

    print("done filling the tree")
    outRoot.cd()
    outTree.Write()
    outRoot.Close()
    final = time.time()
    print("\nFilling tree took %i seconds." %(final-start))
    print("\nFull script duration: %0.f s"%(final-initial))
