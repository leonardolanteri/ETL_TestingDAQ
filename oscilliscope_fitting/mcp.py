import subprocess
import uproot
import os
import awkward as ak

class Dat2RootFit:
    """
    Dat2Root does not actually convert binary dat files to root, name is just legacy

    This takes in a waveform, converts it to root file, then processes it using the compiled C++ file from TimingDAQ library
    (will try to remove one day, all it does it perform fits on the MCP signal, and clock too but we do not use it because it is not reliable)

    This context managers handles the deletion and creation of the files in case any bugs happen along the way!
    """
    def __init__(self, mcp_waveform: ak.Array, dat2root_path: str = None, config_path: str = None):
        self.mcp_waveform = mcp_waveform

        # keep input and output files in linux designated /tmp/ directory
        self.input_path = "/tmp/input_dat2root_temp.root"
        self.output_path = "/tmp/output_dat2root_temp.root"
        self.dat2root_path = "oscilliscope_fitting/NetScopeStandalone_Dat2Root_MCP_FITTER" if dat2root_path is None else dat2root_path
        self.config_path = "oscilliscope_fitting/LecroyScope_v12.config" if config_path is None else config_path

    def __enter__(self):
        # convert to root file for dat2root
        self._convert_to_root(self.input_path)
        # run dat2root
        self._run_dat2root()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # delete both files
        if os.path.exists(self.input_path):
            os.remove(self.input_path)
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

    def _convert_to_root(self, path: str) -> None:
        with uproot.recreate(path) as file:
            file["pulse"] = self.mcp_waveform  # "mytree" is the name of the TTree

    def _run_dat2root(self) -> None:
        """
        Creates root file from lecroy scope, does fitting on the MCP signal.
        """
        # /home/etl/Test_Stand/ETL_TestingDAQ/TimingDAQ/config/LecroyScope_v12.config
        # Construct the command
        DattorootCmd = (
            f'{self.dat2root_path} '
            f'--correctForTimeOffsets --input_file={self.input_path} '
            f'--output_file={self.output_path} --config={self.config_path} --save_meas'
        )
        subprocess.run(DattorootCmd, shell=True, check=True)

    def output(self) -> ak.Array:
        with uproot.open(self.output_path) as file:
            tree = file["pulse"]
            data = tree.arrays(library="np")
        return data

def fit(mcp_waveform: ak.Array, **kwargs) -> ak.Array:
    with Dat2RootFit(mcp_waveform, **kwargs) as fit_manager:
        fit_data = fit_manager.output()

        # take the fields you want and just return those

        return fit_data