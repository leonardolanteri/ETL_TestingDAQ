This repo serves to organize the different projects used to run the module testbeams.

Firmware should have already been flashed to the KCU before using the DAQ code

```module_test_sw``` stores the top level scripts and interactions with the KCU
```ScopeHandler``` and ```TimingDAQ``` handle interactions with the oscilloscope

The ```Run_Autopilot.sh``` script in ```module_test_sw``` starts the runs and attempts to keep everything moving

