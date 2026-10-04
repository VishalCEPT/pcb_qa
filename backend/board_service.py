"""
Board loading / netlist -> circuit JSON conversion facade.

Wraps core.hierarchical_reader + core.circuit_json + core.file_helpers behind
a small API the GUI can call without knowing about the underlying flat-module
layout, S-expression parsing, or on-disk caching scheme.
"""

from dataclasses import dataclass, field

import circuit_json as circuit_json_module
import file_helpers
import hierarchical_reader

from backend import paths
from backend.errors import BoardFileMissingError, BoardNotFoundError


@dataclass
class BoardSummary:
    name: str
    netlist_path: str | None
    spice_path: str | None
    schematic_pdf_path: str | None
    questions_path: str | None
    datasheets: list[str] = field(default_factory=list)


@dataclass
class BoardCircuit:
    board_name: str
    circuit_json_path: str
    circuit: dict
    component_count: int
    net_count: int
    subcircuit_count: int
    gnd_passive_pin_refs: list[str] = field(default_factory=list)


def list_boards() -> list[str]:
    return paths.list_boards()


def get_board_summary(board_name: str) -> BoardSummary:
    if board_name not in paths.list_boards():
        raise BoardNotFoundError(f"No board named '{board_name}' under {paths.BOARDS_DIR}")

    return BoardSummary(
        name=board_name,
        netlist_path=paths.find_netlist_file(board_name),
        spice_path=paths.find_spice_file(board_name),
        schematic_pdf_path=paths.find_schematic_pdf(board_name),
        questions_path=paths.find_questions_file(board_name),
        datasheets=paths.find_datasheets(board_name),
    )


def _count_subcircuit_totals(circuit: dict) -> tuple[int, int]:
    component_count = len(circuit.get("components", {}))
    net_count = len(circuit.get("nets", {}))
    for subcircuit in circuit.get("subcircuits", []):
        component_count += len(subcircuit.get("components", {}))
        net_count += len(subcircuit.get("nets", {}))
    return component_count, net_count


def load_or_generate_circuit(board_name: str, force_regenerate: bool = False) -> BoardCircuit:
    """
    Convert the board's KiCad netlist into circuit JSON, caching the result
    under Boards/<board_name>/Output_Files/. Reuses the cached file unless
    force_regenerate is True or no cache exists yet.
    """
    summary = get_board_summary(board_name)
    if summary.netlist_path is None:
        raise BoardFileMissingError(f"Board '{board_name}' has no .net file under {paths.input_dir(board_name)}")

    json_ops = file_helpers.JSONFileOperator()
    output_path = paths.circuit_json_path(board_name)

    if not force_regenerate:
        try:
            circuit = json_ops.read_from_json_file(output_path)
        except FileNotFoundError:
            circuit = None
    else:
        circuit = None

    if circuit is None:
        reader = hierarchical_reader.HierarchicalReader(summary.netlist_path)
        circuit = reader.generate_top_sheet_circuit()
        json_ops.write_to_json_file(circuit, output_path)

    component_count, net_count = _count_subcircuit_totals(circuit)

    cj = circuit_json_module.CircuitJSON()
    cj.top_level_circuit = circuit
    cj._initialise_component_lists()

    return BoardCircuit(
        board_name=board_name,
        circuit_json_path=output_path,
        circuit=circuit,
        component_count=component_count,
        net_count=net_count,
        subcircuit_count=len(circuit.get("subcircuits", [])),
        gnd_passive_pin_refs=cj.passive_components,
    )
