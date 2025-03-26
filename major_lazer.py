import click
import subprocess
from config import load_config
from daq.lecroy_controller import LecroyController
from daq.etl_telescope import ETL_Telescope
from processing.cernbox_api import CERNBoxAPI
from pathlib import Path
import processing.plots as tb_plots

@click.group()
def cli():
    """Main entry point for the ETL Testing DAQ tool."""
    pass

@cli.command()
def mount_scope():
    """Mount the LeCroy scope waveform directory to the PC"""
    click.echo("Mounting the LeCroy scope...")
    TB_CONFIG = load_config(relax_validation=True)
    valid_config = (hasattr(TB_CONFIG, "oscilloscope") and \
                    hasattr(TB_CONFIG.oscilloscope, "ip_address") and \
                    hasattr(TB_CONFIG.oscilloscope, "binary_data_directory"))
    if valid_config:
        subprocess.run([
            "sudo", "mount", "-t", "cifs",
            f"//{TB_CONFIG.oscilloscope.ip_address}/Waveforms",
            str(TB_CONFIG.oscilloscope.binary_data_directory),
            "-o", "user=mothra", "uid=etl", "gid=etl", "vers=2.0"
        ])
    else:
        raise ValueError("The active config was not formatted correctly. Check oscilloscope section has ip_address and binary_data_directory")

@cli.command()
def init_etl():
    """Fire up the ETL Telescope with the configuration."""
    click.echo("Firing up the ETL Telescope with config...")
    TB_CONFIG = load_config()
    etl_telescope = ETL_Telescope(TB_CONFIG.telescope_config)

@cli.command()
def init_scope():
    """Fire up the scope with the configuration."""
    click.echo("Firing up the scope with config...")
    TB_CONFIG = load_config()
    ip = TB_CONFIG.oscilloscope.ip_address
    channels = list(TB_CONFIG.oscilloscope.channels.keys())
    with LecroyController(ip, active_channels=channels) as lecroy:
        lecroy.setup_from_config(TB_CONFIG.oscilloscope)

# @cli.command()
# def take_runs():
#     """Executes the take runs python file"""
#     click.echo("Taking runs...")
#     subprocess.run(["python", "daq/take_runs.py"])

# @cli.command()
# def watchdog():
#     """Executes the daq_watchdog python file"""
#     click.echo("Running the watchdog...")
#     subprocess.run(["python", "processing/daq_watchdog.py"])

@cli.group()
def backup():
    """Commands related to CERNBox backup."""
    pass

@backup.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path))
def push_dir(directory):
    """Push a directory to the CERNbox, it will be based off the current final archive directory"""
    click.echo("Performing WebDAV full push...")
    TB_CONFIG = load_config()

    cernbox = CERNBoxAPI()        
    # This seems fairly robust... famous last words
    remote_dir = Path(TB_CONFIG.watchdog.final_archive_directory.name) / directory.name

    cernbox.upload(
        remote_dir = remote_dir, 
        local_path  = directory
    )

# CONSOLODATE LOTS OF RUNS


@cli.group()
def plots():
    """Commands related to generating plots."""
    pass

@plots.command()
@click.argument('clock_trace_file', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
def clock_from_binary(clock_trace_file):
    """Generate clock plots."""
    click.echo("Generating clock plots...")
    tb_plots.Clock_trace_generator(clock_trace_file, Path("./"))

@plots.command()
@click.argument('mcp_trace_file', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
def mcp_from_binary(mcp_trace_file):
    """Generate MCP plots."""
    click.echo("Generating MCP plots...")
    tb_plots.MCP_trace_generator(mcp_trace_file, Path("./"))

@plots.command()
@click.argument('etroc_binary_file', type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path))
def etroc_hitmap_from_binary(etroc_binary_file):
    """Generate etroc hitmap plots."""
    click.echo("Generating etroc hitmap plot...")
    tb_plots.etroc_hitmaps_generator(etroc_binary_file, Path("./"))

if __name__ == "__main__":
    cli()