"""
Initialise kicad-cli such that it has a symbolic link to `<project directory>/kicad-cli`

Prerequisites: 
- Ensure that in .env file, the variable KICAD_CLI_PATH is set to the actual location that `kicad-cli` is installed at.

"""

import os
import subprocess
import time
import glob
import kicad_netlist_processer
import file_helpers
from skidl.netlist_to_skidl import legalize_name, NetSexp, PartSexp
from pathlib import Path
import json


class KiCadInterface:
    def __init__(self):
        kicad_cli_env = os.getenv("KICAD_CLI_PATH")
        if not kicad_cli_env:
            raise RuntimeError(
                "KICAD_CLI_PATH environment variable is not set. "
                "Set it to the full path of the kicad-cli executable before using KiCadInterface."
            )

        kicad_cli_path = Path(kicad_cli_env)
        if not kicad_cli_path.exists():
            raise RuntimeError(f"KICAD_CLI_PATH points to a path that does not exist: {kicad_cli_path}")

        self.KICAD_CLI_EXECUTABLE = str(kicad_cli_path)
        self._verify_kicad_cli()

    def _verify_kicad_cli(self):
        print("Check if kicad-cli now works...")
        subprocess.run([self.KICAD_CLI_EXECUTABLE, "-h"], check=True, timeout=30)

    def export_netlist_with_kicad_cli(self, project_name: str, output_file_name: str):
        """
        Function to export .kicad_sch or .pro files to .net files using kicad-cli, so other Python scripts can use the resultant .net files.
        """
        print(f"Project schematic name: {project_name}")
        project_schematic_path = Path(project_name)
        if project_schematic_path.exists():
            print("Project exists! Creating netlist output at: ", output_file_name)
            subprocess.run(
                [self.KICAD_CLI_EXECUTABLE, "sch", "export", "netlist", "--format", "kicadsexpr", str(project_schematic_path), "--output", output_file_name],
                check=True,
                timeout=120,
            )
        else:
            raise Exception("No valid schematic")

    def export_spice_with_kicad_cli(self, project_name: str, output_file_name: str):
        """
        Function to export .kicad_sch or .pro files to .cir files using kicad-cli, so other Python scripts can use the resultant .cir files.
        """
        print(f"Project schematic name: {project_name}")
        project_schematic_path = Path(project_name)
        if project_schematic_path.exists():
            print("Project exists! Creating SPICE output at: ", output_file_name)
            subprocess.run(
                [self.KICAD_CLI_EXECUTABLE, "sch", "export", "netlist", "--format", "spice", str(project_schematic_path), "--output", output_file_name],
                check=True,
                timeout=120,
            )
        else:
            raise Exception("No valid schematic/project.")
