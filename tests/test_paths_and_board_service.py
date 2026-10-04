import os

import pytest

from backend import board_service, paths
from backend.errors import BoardNotFoundError


def test_list_boards_only_lists_directories(boards_dir):
    (boards_dir / "stray_file.txt").write_text("x")
    assert paths.list_boards() == ["stack-chan"]


def test_find_input_files(board):
    assert paths.find_netlist_file(board).endswith("m5-pantilt.net")
    assert paths.find_spice_file(board).endswith("m5-pantilt.cir")
    assert paths.find_schematic_pdf(board).endswith("m5-pantilt.pdf")
    assert paths.find_questions_file(board).endswith("m5-pantilt_60_questions.json")
    assert [os.path.basename(p) for p in paths.find_datasheets(board)] == [
        "Q1.pdf", "Q2.pdf", "Q2_auto_test.pdf", "U1.pdf",
    ]


def test_input_lookups_do_not_create_directories(boards_dir):
    assert paths.find_netlist_file("ghost") is None
    assert paths.find_datasheets("ghost") == []
    assert not (boards_dir / "ghost").exists()


def test_board_summary(board):
    summary = board_service.get_board_summary(board)
    assert summary.name == board
    assert summary.netlist_path and summary.spice_path and summary.questions_path
    assert len(summary.datasheets) == 4


def test_unknown_board_raises_without_creating_directories(boards_dir):
    with pytest.raises(BoardNotFoundError):
        board_service.load_or_generate_circuit("no-such-board")
    assert paths.list_boards() == ["stack-chan"]


def test_load_or_generate_circuit_generates_and_caches(board):
    first = board_service.load_or_generate_circuit(board)

    assert os.path.exists(first.circuit_json_path)
    assert first.component_count == 33
    assert first.net_count == 40
    assert "R15" in first.gnd_passive_pin_refs  # R15: Net-_U1-B_ -> GND
    assert "R1" not in first.gnd_passive_pin_refs  # R1: +3V3 -> /TXD2

    mtime = os.path.getmtime(first.circuit_json_path)
    second = board_service.load_or_generate_circuit(board)
    assert os.path.getmtime(second.circuit_json_path) == mtime
    assert second.circuit == first.circuit


def test_force_regenerate_rewrites_cache(board):
    first = board_service.load_or_generate_circuit(board)
    with open(first.circuit_json_path, "w", encoding="utf-8") as f:
        f.write('{"components": {}, "nets": {}, "subcircuits": []}')

    assert board_service.load_or_generate_circuit(board).component_count == 0
    assert board_service.load_or_generate_circuit(board, force_regenerate=True).component_count == 33
