import os
import shutil
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import backend  # noqa: E402,F401 - puts core/ on sys.path
from backend import paths  # noqa: E402

REAL_BOARD = "stack-chan"
REAL_INPUT_DIR = os.path.join(REPO_ROOT, "Boards", REAL_BOARD, "Input_Files")


@pytest.fixture
def boards_dir(tmp_path, monkeypatch):
    """An isolated Boards/ dir containing a copy of stack-chan's inputs only."""
    boards = tmp_path / "Boards"
    shutil.copytree(REAL_INPUT_DIR, boards / REAL_BOARD / "Input_Files")
    monkeypatch.setattr(paths, "BOARDS_DIR", str(boards))
    return boards


@pytest.fixture
def board(boards_dir):
    return REAL_BOARD


@pytest.fixture(scope="session")
def tk_root():
    # One Tk for the whole session: repeatedly creating Tk() in one process is
    # flaky on Windows venvs ("Can't find a usable tk.tcl").
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"No Tk display available: {exc}")
    root.withdraw()
    yield root
    root.destroy()


def pump_until(root, predicate, timeout=10.0):
    import time

    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def allow_tmp_boards(boards_dir, monkeypatch):
    """Let ToolCaller's path confinement accept files under the temp Boards/ dir."""
    from tool_caller import ToolCaller

    monkeypatch.setattr(ToolCaller, "_ALLOWED_ROOT_DIRS", [os.path.realpath(str(boards_dir))])
    return boards_dir
