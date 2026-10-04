"""
Tkinter application shell: a Notebook with the four PCB-QA tabs, backed by an
AsyncRunner so every backend call (board loading, SPICE simulation, Gemini
Q&A, benchmark runs) happens off the UI thread. root.report_callback_exception
is overridden as a last-resort safety net so a bug anywhere in a tab shows a
dialog instead of silently killing the Tk mainloop.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from backend import board_service
from backend.async_runner import AsyncRunner
from backend.config import reload_config

from gui.benchmark_tab import BenchmarkTab
from gui.board_tab import BoardTab
from gui.qa_tab import QATab
from gui.spice_tab import SpiceTab


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PCB-QA Desktop")
        self.root.geometry("1000x700")

        self._apply_theme()

        self.runner = AsyncRunner(root, on_busy_change=self._set_busy)
        self.board_var = tk.StringVar()

        self._build_board_selector()

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.board_tab = BoardTab(notebook, self.runner, self.board_var)
        self.spice_tab = SpiceTab(notebook, self.runner, self.board_var)
        self.qa_tab = QATab(notebook, self.runner, self.board_var)
        self.benchmark_tab = BenchmarkTab(notebook, self.runner, self.board_var)

        notebook.add(self.board_tab, text="Board")
        notebook.add(self.spice_tab, text="SPICE Simulation")
        notebook.add(self.qa_tab, text="Q&A")
        notebook.add(self.benchmark_tab, text="Benchmark")

        self._build_status_bar()

        root.report_callback_exception = self._on_uncaught_exception

    def _apply_theme(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")

        style.configure("Success.TLabel", foreground="#1a7f37")
        style.configure("Error.TLabel", foreground="#c0392b")

    def _build_status_bar(self):
        bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_bar_label = ttk.Label(bar, text="Ready", padding=(8, 2))
        self.status_bar_label.pack(side=tk.LEFT)

    def _set_busy(self, is_busy: bool, label: str):
        self.status_bar_label.configure(text=f"Working: {label}" if is_busy else "Ready")

        state = tk.DISABLED if is_busy else "readonly"
        self.board_combo.configure(state=state)
        self.reload_button.configure(state=tk.DISABLED if is_busy else tk.NORMAL)

    def _build_board_selector(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(frame, text="Board:").pack(side=tk.LEFT)

        self.board_combo = ttk.Combobox(frame, textvariable=self.board_var, state="readonly", width=30)
        self.board_combo.pack(side=tk.LEFT, padx=(4, 0))

        self.no_boards_label = ttk.Label(frame, text="")
        self.no_boards_label.pack(side=tk.LEFT, padx=(8, 0))

        self.reload_button = ttk.Button(frame, text="Reload .env / boards", command=self._on_reload)
        self.reload_button.pack(side=tk.RIGHT)

        self._refresh_boards()

    def _refresh_boards(self):
        boards = board_service.list_boards()
        self.board_combo.configure(values=boards)
        if self.board_var.get() not in boards:
            self.board_var.set(boards[0] if boards else "")
        self.no_boards_label.configure(text="" if boards else "(no boards found under Boards/)")

    def _on_reload(self):
        cfg = reload_config()
        self._refresh_boards()
        messagebox.showinfo(
            "Configuration reloaded",
            f"GEMINI_API_KEY: {'set' if cfg.gemini_api_key else 'NOT set'}\n"
            f"GEMINI_MODEL: {cfg.gemini_model}\n"
            f"NGSPICE_PATH: {cfg.ngspice_path}",
        )

    def _on_uncaught_exception(self, exc_type, exc_value, exc_tb):
        messagebox.showerror("Unexpected error", f"{exc_type.__name__}: {exc_value}")
