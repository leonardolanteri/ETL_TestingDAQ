# Introduction

This repo serves to organize the different projects used to run the module testbeams. It is not up to date as is getting put together as we go until it is a working product. There was a significant amount of time where versioning was not used and not all the working code from previous test beams is pushed.

## Background / Overview
Firmware should have already been flashed to the KCU before using the DAQ code

```module_test_sw``` stores the top level scripts and interactions with the KCU
```ScopeHandler``` and ```TimingDAQ``` handle interactions with the oscilloscope

The ```Run_Autopilot.sh``` script in ```module_test_sw``` starts the runs and attempts to keep everything moving

### Here is a complete view the codebase:

![tbdaq](./tbdaq.svg)

## Environment

The environment is getting built as we go so for the parts that currently work the environment can be built like:
```conda env create --file=environment.yml```

If you work on a part are pushing to the repository, please push updates to `environment.yml`, your current activated conda environemnt can be made into a yaml file like (please take care to not **overwrite** the environment file): 
```conda env export | grep -v "^prefix: " > environment.yml```

If you find a way to update the yaml instead of rewriting please share here (potentially `conda env update --name etl_testing_daq --file environment.yml --prune` works).



# Work Tracker

From the loooking at `tbdaq.drawio` the codebase can be split into two parts. The first part is all the scripts that make the `.dat` (contains all the etroc data from the KCU) and `.trc` files (contains all scope data from the oscilliscope); also there is a script (`data_dumper.py`) that converts the dat file to json but this can ultamitely be removed. The second part is to convert all these into one root file. 

*HERE ON OUT PLEASE STATE WHAT HAS BEEN WORKED ON SO PEOPLE KNOW* also explain a bit about what it does and what is implemented (and what bugs may have been introduced :)

### `ScopeHandler/Lecroy/Merging/merge_scope_etroc.py` 
This part of the script takes the scope and etroc data (from whatever is last in the nasty chain) and converts them to a final merged root file.

* Has unit tests for the merge tree function (puts big root files could be improved but is ok for now)
    * run by `python -m unit_test.test_merge_scope_etroc` in the `/home/users/hswanson13/ETL_TestingDAQ/ScopeHandler/Lecroy/Merging` directory
* Enviroment for running the script
* Clock function updated to account for faster sampling speeds. Also is faster and fully columnar.

### RecoLoop.py

Added root the environment by following instructions [here](https://indico.cern.ch/event/759388/contributions/3306849/attachments/1816254/2968550/root_conda_forge.pdf). All I did was the following to get recoLoop to work INSIDE the env:

`conda config --env --add channels conda-forge` then,
`conda install root`
