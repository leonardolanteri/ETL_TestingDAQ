### if sample rate or horizontal window is changed, TimingDAQ must be recompiled to account for new npoints.
import os
import argparse

runNumber = -1 ### -1 means use serial number
ScopeControlDir = "/home/etl/Test_Stand/ETL_TestingDAQ/daq"

def ScopeAcquisition(numEvents):
    print("\n ####################### Running the scope acquisition ##################################\n")
    ScopeCommand = (
        f'/usr/bin/python3 {ScopeControlDir}/daq/scope.py '
        f'--runNum {runNumber} '
        f'--numEvents {numEvents} '
        f'--sampleRate {sampleRate} '
        f'--horizontalWindow {horizontalWindow} '
        f'--trigCh {trigCh} '
        f'--trig {trig} '
        f'--vScale2 {vScale2} '
        f'--vScale3 {vScale3} '
        f'--vPos2 {vPos2} '
        f'--vPos3 {vPos3} '
        f'--timeoffset {timeoffset} '
        f'--trigSlope {trigSlope} '
        f'--display 1'
    )
    # ScopeCommand += ' --vScale1 %f --vScale2 %f --vScale3 %f --vScale4 %f ' % (vScale1, vScale2, vScale3, vScale4)
    # ScopeCommand += ' --vPos1 %f --vPos2 %f --vPos3 %f --vPos4 %f ' % (vPos1,vPos2, vPos3, vPos4)
    #GS/s
    # ScopeCommand += f' --vScale1 {vScale1} --vScale2 {vScale2} --vScale3 {vScale3} --vScale4 {vScale4} '
    # ScopeCommand += f' --vPos1 {vPos1} --vPos2 {vPos2} --vPos3 {vPos3} --vPos4 {vPos4} '
    # GS/s

    print(ScopeCommand)
    os.system(ScopeCommand)
            
if __name__ == "__main__":
    argParser = argparse.ArgumentParser(description = "Argument parser")
    argParser.add_argument("--force_acquisition",action="store_true")
    argParser.add_argument("--nevents",action="store")
    argParser.add_argument("--sample_rate",action="store")
    argParser.add_argument("--horizontal_window",action="store")
    argParser.add_argument("--trigger_channel",action="store")
    argParser.add_argument("--trigger",action="store")
    argParser.add_argument("--v_scale_2",action="store")
    argParser.add_argument("--v_scale_3",action="store")
    argParser.add_argument("--v_position_2",action="store")
    argParser.add_argument("--v_position_3",action="store")
    argParser.add_argument("--time_offset",action="store")
    argParser.add_argument("--trigger_slope",action="store")
    args = argParser.parse_args()

    with open(f"{ScopeControlDir}/running_ETROC_acquisition.txt") as file:
        kcu_acquisition_flag = file.read()
    
    print("kcu_acquisition_flag ",kcu_acquisition_flag)
    iteration = 0
    while kcu_acquisition_flag == "False":
        if args.force_acquisition: break
        if iteration == 0:
            print(f"Waiting for the KCU.")
        with open(f"{ScopeControlDir}/running_ETROC_acquisition.txt") as file:
            kcu_acquisition_flag = file.read()
        iteration+=1

    with open(f"{ScopeControlDir}/running_acquisition.txt", "w") as f:
        f.write("True")
        f.truncate()

    numEvents = int(args.nevents)
    sampleRate = int(args.sample_rate)
    horizontalWindow = float(args.horizontal_window)
    trigCh = str(args.trigger_channel)
    trig = float(args.trigger)
    vScale2 = float(args.v_scale_2)
    vScale3 = float(args.v_scale_3)
    vPos2 = float(args.v_position_2)
    vPos3 = float(args.v_position_3)
    timeoffset = float(args.time_offset)
    trigSlope = str(args.trigger_slope)
    
    ScopeAcquisition(numEvents)

    with open(f"{ScopeControlDir}/running_acquisition.txt", "w") as f:
        f.write("False")
        f.truncate()

    with open(f"{ScopeControlDir}/merging.txt", "w") as f:
        f.write("True")
        f.truncate()
