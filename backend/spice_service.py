"""
SPICE netlist conversion + ngspice simulation facade.

Wraps core.kicad_spice_circuit_processer.KiCadSPICECircuitProcesser behind a
small API the GUI can call without knowing about raw .cir text munging,
ngspice subprocess invocation, or the ASCII .raw parsing format. Converted
.cir files and simulation results are cached under
Boards/<board_name>/Output_Files/ and reused unless force_regenerate is set.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field

import kicad_spice_circuit_processer as spice_module

from backend import paths
from backend.config import config
from backend.errors import BoardFileMissingError, BoardNotFoundError, MissingDependencyError, SimulationError


def _require_board(board_name: str) -> None:
    """
    Raise before any path.* helper that auto-creates Output_Files/ runs, so a
    typo'd or nonexistent board name never leaves stray directories on disk
    instead of a clean error.
    """
    if board_name not in paths.list_boards():
        raise BoardNotFoundError(f"No board named '{board_name}' under {paths.BOARDS_DIR}")


@dataclass
class SimulationResult:
    board_name: str
    cir_path: str
    raw_path: str
    log_path: str
    spice_json_path: str
    data: dict = field(default_factory=dict)


def _output_base(board_name: str) -> str:
    spice_file = paths.find_spice_file(board_name)
    base = os.path.splitext(os.path.basename(spice_file))[0]
    return f"{base}_generated"


def _get_processor(board_name: str) -> spice_module.KiCadSPICECircuitProcesser:
    spice_file = paths.find_spice_file(board_name)
    if spice_file is None:
        raise BoardFileMissingError(f"Board '{board_name}' has no .cir file under {paths.input_dir(board_name)}")
    return spice_module.KiCadSPICECircuitProcesser(
        spice_circuit_path=spice_file,
        output_dir=paths.output_dir(board_name),
        project_name=None,
        output_file=paths.spice_json_path(board_name),
    )


def convert_to_simulation_ready_cir(board_name: str, force_regenerate: bool = False) -> str:
    """
    Convert the board's raw KiCad SPICE export into a simulation-ready .cir:
    GND -> 0, LED model synthesis, DC sources added for power-rail nets
    (e.g. +3V3), and a .control block that runs a transient analysis and
    writes an ASCII .raw file. Cached on disk; returns the .cir path.
    """
    _require_board(board_name)
    cir_path = paths.generated_spice_cir_path(board_name)
    if not force_regenerate and os.path.exists(cir_path):
        return cir_path

    processor = _get_processor(board_name)
    try:
        processor.convert_project_spice_to_circuit(_output_base(board_name))
    except (ValueError, OSError) as exc:
        raise SimulationError(f"Could not convert '{board_name}' SPICE netlist: {exc}") from exc
    return cir_path


def run_simulation(board_name: str, force_regenerate_cir: bool = False) -> SimulationResult:
    """
    Convert (if needed) and run ngspice on the board's simulation-ready .cir,
    parse the resulting .raw file, and cache it as SPICE JSON so
    check_expected_voltage() can read it back without re-simulating.
    """
    _require_board(board_name)
    cir_path = convert_to_simulation_ready_cir(board_name, force_regenerate=force_regenerate_cir)
    raw_path = paths.spice_raw_path(board_name)
    log_path = paths.spice_log_path(board_name)
    json_path = paths.spice_json_path(board_name)

    if shutil.which(config.ngspice_path) is None:
        raise MissingDependencyError(
            f"ngspice executable ('{config.ngspice_path}') not found on PATH. "
            "Install ngspice and ensure it's on PATH, or set NGSPICE_PATH in .env."
        )

    processor = _get_processor(board_name)

    try:
        data = processor.run_ngspice_simulation(
            input_spice_path=cir_path,
            output_spice_logs=log_path,
            output_raw_path=raw_path,
            ngspice_executable=config.ngspice_path,
        )
    except subprocess.TimeoutExpired as exc:
        raise SimulationError(f"ngspice simulation for '{board_name}' timed out after {exc.timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise SimulationError(
            f"ngspice simulation for '{board_name}' failed (exit code {exc.returncode}): "
            f"{stderr or 'see log at ' + log_path}"
        ) from exc
    except RuntimeError as exc:
        raise SimulationError(f"ngspice simulation for '{board_name}' did not complete: {exc}") from exc
    except Exception as exc:
        raise SimulationError(f"Failed to parse ngspice output for '{board_name}': {exc}") from exc

    return SimulationResult(
        board_name=board_name,
        cir_path=cir_path,
        raw_path=raw_path,
        log_path=log_path,
        spice_json_path=json_path,
        data=data,
    )


def check_expected_voltage(board_name: str, net_name: str, expected_voltage: str, tolerance: float = 0.05) -> bool:
    """
    Check whether a net's simulated steady-state voltage matches an expected
    value. Requires run_simulation() to have produced (or previously cached)
    SPICE JSON for this board.
    """
    _require_board(board_name)
    json_path = paths.spice_json_path(board_name)
    if not os.path.exists(json_path):
        raise SimulationError(f"No simulation results found for '{board_name}'. Run the simulation first.")

    processor = _get_processor(board_name)
    return processor.check_steady_state_average_matches_expected_voltage(
        spice_json_file=json_path,
        net_name=net_name,
        expected_voltage=expected_voltage,
        tolerance=tolerance,
    )
