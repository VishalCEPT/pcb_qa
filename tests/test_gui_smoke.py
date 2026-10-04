import gc
import shutil
import tkinter as tk

import pytest

from backend.config import config
from gui import app as app_module
from gui.app import App

from conftest import pump_until


@pytest.fixture
def app(tk_root, boards_dir, monkeypatch):
    shown = []
    monkeypatch.setattr(app_module.messagebox, "showinfo", lambda *a, **_k: shown.append(a))
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda *a, **_k: shown.append(a))
    window = tk.Toplevel(tk_root)
    window.withdraw()
    application = App(window)
    application.dialogs = shown
    yield application
    window.destroy()
    del application
    # Collect the window's Tk variables here on the main thread; otherwise a
    # later GC pass inside an AsyncRunner worker thread trips Tk's thread check.
    gc.collect()


def test_app_builds_all_tabs_and_selects_board(app):
    notebook_tabs = [app.root.nametowidget(t) for t in app.board_tab.master.tabs()]
    assert notebook_tabs == [app.board_tab, app.spice_tab, app.qa_tab, app.benchmark_tab]
    assert app.board_var.get() == "stack-chan"


def test_board_tab_loads_board(app):
    app.board_tab._on_load()
    assert pump_until(app.root, lambda: "Loaded" in app.board_tab.status_label.cget("text"))
    assert "33" in app.board_tab.output.get("1.0", tk.END)


def test_spice_tab_reports_missing_ngspice_without_crashing(app, monkeypatch):
    errors = []
    monkeypatch.setattr(config, "ngspice_path", "definitely-not-ngspice-xyz")
    monkeypatch.setattr("gui.spice_tab.show_error", lambda _parent, exc, title="": errors.append(exc))

    app.spice_tab._on_run()
    assert pump_until(app.root, lambda: errors)

    assert "ngspice" in str(errors[0])
    assert app.spice_tab.status_label.cget("text") == "Operation failed."


@pytest.mark.integration
@pytest.mark.skipif(shutil.which(config.ngspice_path) is None, reason="ngspice not on PATH")
def test_spice_tab_runs_real_simulation_and_checks_voltage(app):
    app.spice_tab._on_run()
    assert pump_until(app.root, lambda: app.spice_tab.status_label.cget("text") == "Simulation complete.", timeout=60.0)
    assert "Parsed" in app.spice_tab.output.get("1.0", tk.END)

    app.spice_tab.net_entry.insert(0, "+3V3")
    app.spice_tab.voltage_entry.insert(0, "3.3V")
    app.spice_tab._on_check()
    assert pump_until(app.root, lambda: "Result:" in app.spice_tab.status_label.cget("text"))
    assert app.spice_tab.status_label.cget("text") == "Result: MATCHES expected voltage."


def test_benchmark_tab_runs_through_real_async_runner(app, monkeypatch):
    # Regression test: an earlier version passed on_question=report directly
    # (report() takes 1 positional arg) instead of wrapping the 2-arg
    # on_question(result, total) callback, so every real benchmark run raised
    # a TypeError on the first question. benchmark_service tests alone don't
    # catch this since they never go through AsyncRunner/ProgressPanel.
    from backend import benchmark_service
    prompt_strategies = benchmark_service.prompt_strategies
    monkeypatch.setattr(prompt_strategies, "answer_with_circuit_json", lambda _q, _c: "YES")

    app.benchmark_tab.strategy_var.set("circuit_json")
    app.benchmark_tab.limit_entry.delete(0, tk.END)
    app.benchmark_tab.limit_entry.insert(0, "2")
    app.benchmark_tab._on_run()

    assert pump_until(app.root, lambda: app.benchmark_tab.status_label.cget("text") == "Benchmark complete.")
    assert not app.dialogs
    assert "Accuracy:" in app.benchmark_tab.output.get("1.0", tk.END)


def test_reload_refreshes_board_list(app, boards_dir):
    (boards_dir / "new-board" / "Input_Files").mkdir(parents=True)
    app._on_reload()

    assert list(app.board_combo.cget("values")) == ["new-board", "stack-chan"]
    assert app.board_var.get() == "stack-chan"
    assert app.dialogs and "Configuration reloaded" in app.dialogs[-1][0]
