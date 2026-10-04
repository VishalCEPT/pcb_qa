import json
import os
import pathlib
import shutil
import subprocess

import pytest

from backend import paths, spice_service
from backend.config import config
from backend.errors import BoardNotFoundError, MissingDependencyError, SimulationError

from test_spice_processor import make_raw


@pytest.fixture
def fake_ngspice(monkeypatch):
    """Pretend ngspice is installed; the returned dict controls what a 'run' does."""
    behaviour = {"raise": None}

    monkeypatch.setattr(spice_service.shutil, "which", lambda _exe: "/fake/ngspice")

    def fake_run(cmd, **kwargs):
        if behaviour["raise"] is not None:
            raise behaviour["raise"]
        board = behaviour["board"]
        make_raw(
            pathlib.Path(paths.spice_raw_path(board)),
            rail_values=[3.3] * 12,
            out_values=[0.5] * 12,
        )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return behaviour


def test_convert_generates_and_caches(board):
    cir_path = spice_service.convert_to_simulation_ready_cir(board)
    text = open(cir_path).read()

    assert "V_3V3 +3V3 0 DC 3.3" in text
    assert "R7 Net-_Q2-C_ 0 20k" in text
    assert ".control" in text

    mtime = os.path.getmtime(cir_path)
    assert spice_service.convert_to_simulation_ready_cir(board) == cir_path
    assert os.path.getmtime(cir_path) == mtime


@pytest.mark.parametrize("call", [
    lambda: spice_service.convert_to_simulation_ready_cir("no-such-board"),
    lambda: spice_service.run_simulation("no-such-board"),
    lambda: spice_service.check_expected_voltage("no-such-board", "+3V3", "3.3V"),
])
def test_unknown_board_raises_without_creating_directories(boards_dir, call):
    with pytest.raises(BoardNotFoundError):
        call()
    assert paths.list_boards() == ["stack-chan"]


def test_missing_ngspice(board, monkeypatch):
    monkeypatch.setattr(config, "ngspice_path", "definitely-not-ngspice-xyz")
    with pytest.raises(MissingDependencyError):
        spice_service.run_simulation(board)


def test_check_voltage_before_simulation(board):
    with pytest.raises(SimulationError):
        spice_service.check_expected_voltage(board, "+3V3", "3.3V")


def test_run_simulation_parses_and_persists(board, fake_ngspice):
    fake_ngspice["board"] = board

    result = spice_service.run_simulation(board)

    assert os.path.exists(result.spice_json_path)
    with open(result.spice_json_path) as f:
        assert json.load(f) == result.data
    assert result.data["1"]["name"] == "v(+3v3)"

    assert spice_service.check_expected_voltage(board, "+3V3", "3.3V") is True
    assert spice_service.check_expected_voltage(board, "+3V3", "5V") is False


@pytest.mark.parametrize("error", [
    subprocess.CalledProcessError(1, ["ngspice"], stderr=b"syntax error on line 4"),
    subprocess.TimeoutExpired(["ngspice"], 120),
])
def test_ngspice_failures_become_simulation_errors(board, fake_ngspice, error):
    fake_ngspice["board"] = board
    fake_ngspice["raise"] = error
    with pytest.raises(SimulationError):
        spice_service.run_simulation(board)


@pytest.mark.integration
@pytest.mark.skipif(shutil.which(config.ngspice_path) is None, reason="ngspice not on PATH")
def test_real_ngspice_simulation(board):
    result = spice_service.run_simulation(board)
    assert result.data
    assert spice_service.check_expected_voltage(board, "+3V3", "3.3V") is True
