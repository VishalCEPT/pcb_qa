"""
Central, single-source-of-truth path resolution for the PCB-QA desktop app.

Boards live under `Boards/<board_name>/Input_Files` (source netlist, SPICE
export, schematic PDF, question bank, datasheets) and `Boards/<board_name>/Output_Files`
(generated circuit JSON, SPICE JSON, embeddings, benchmark results). This module
is the only place that knows about that layout; backend services and the GUI
should go through it rather than hardcoding paths.
"""

import glob
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARDS_DIR = os.path.join(REPO_ROOT, "Boards")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs")


def list_boards() -> list[str]:
    """Return the names of all boards that have a Boards/<name>/ directory."""
    if not os.path.isdir(BOARDS_DIR):
        return []
    return sorted(
        name for name in os.listdir(BOARDS_DIR)
        if os.path.isdir(os.path.join(BOARDS_DIR, name))
    )


def board_dir(board_name: str) -> str:
    return os.path.join(BOARDS_DIR, board_name)


def input_dir(board_name: str) -> str:
    return os.path.join(board_dir(board_name), "Input_Files")


def output_dir(board_name: str) -> str:
    path = os.path.join(board_dir(board_name), "Output_Files")
    os.makedirs(path, exist_ok=True)
    return path


def _find_one(directory: str, pattern: str) -> str | None:
    matches = sorted(glob.glob(os.path.join(directory, pattern)))
    return matches[0] if matches else None


def find_netlist_file(board_name: str) -> str | None:
    return _find_one(input_dir(board_name), "*.net")


def find_spice_file(board_name: str) -> str | None:
    return _find_one(input_dir(board_name), "*.cir")


def find_schematic_pdf(board_name: str) -> str | None:
    return _find_one(input_dir(board_name), "*.pdf")


def find_questions_file(board_name: str) -> str | None:
    return _find_one(input_dir(board_name), "*_questions.json")


def find_datasheets(board_name: str) -> list[str]:
    datasheet_dir = os.path.join(input_dir(board_name), "datasheets")
    if not os.path.isdir(datasheet_dir):
        return []
    return sorted(
        os.path.join(datasheet_dir, name)
        for name in os.listdir(datasheet_dir)
        if name.lower().endswith(".pdf")
    )


def circuit_json_path(board_name: str) -> str:
    netlist = find_netlist_file(board_name)
    base = os.path.splitext(os.path.basename(netlist))[0] if netlist else board_name
    return os.path.join(output_dir(board_name), f"{base}.json")


def spice_json_path(board_name: str) -> str:
    spice_file = find_spice_file(board_name)
    base = os.path.splitext(os.path.basename(spice_file))[0] if spice_file else board_name
    return os.path.join(output_dir(board_name), f"{base}_SPICE_circuit.json")


def generated_spice_cir_path(board_name: str) -> str:
    spice_file = find_spice_file(board_name)
    base = os.path.splitext(os.path.basename(spice_file))[0] if spice_file else board_name
    return os.path.join(output_dir(board_name), f"{base}_generated.cir")


def spice_raw_path(board_name: str) -> str:
    spice_file = find_spice_file(board_name)
    base = os.path.splitext(os.path.basename(spice_file))[0] if spice_file else board_name
    return os.path.join(output_dir(board_name), f"{base}_generated_raw.raw")


def spice_log_path(board_name: str) -> str:
    spice_file = find_spice_file(board_name)
    base = os.path.splitext(os.path.basename(spice_file))[0] if spice_file else board_name
    return os.path.join(output_dir(board_name), f"{base}_ngspice.log")


def benchmark_results_dir(board_name: str) -> str:
    path = os.path.join(output_dir(board_name), "benchmark_results")
    os.makedirs(path, exist_ok=True)
    return path
