"""
SPICE simulation runner tab: convert the board's raw .cir export into a
simulation-ready netlist, run ngspice, and check whether a given net reaches
an expected steady-state voltage.
"""

import tkinter as tk
from tkinter import ttk

from backend import spice_service

from gui.errors_dialog import show_error
from gui.widgets import OutputPanel, ProgressPanel


class SpiceTab(ttk.Frame):
    def __init__(self, parent, runner, board_var):
        super().__init__(parent)
        self.runner = runner
        self.board_var = board_var

        self.force_regenerate = tk.BooleanVar(value=False)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=8, pady=8)

        self.convert_button = ttk.Button(controls, text="Convert .cir", command=self._on_convert)
        self.convert_button.pack(side=tk.LEFT)

        self.run_button = ttk.Button(controls, text="Run ngspice simulation", command=self._on_run)
        self.run_button.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Checkbutton(
            controls, text="Force regenerate", variable=self.force_regenerate
        ).pack(side=tk.LEFT, padx=(8, 0))

        check_frame = ttk.LabelFrame(self, text="Check expected voltage")
        check_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        ttk.Label(check_frame, text="Net:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.net_entry = ttk.Entry(check_frame, width=20)
        self.net_entry.grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(check_frame, text="Expected voltage:").grid(row=0, column=2, padx=4, pady=4, sticky="w")
        self.voltage_entry = ttk.Entry(check_frame, width=12)
        self.voltage_entry.grid(row=0, column=3, padx=4, pady=4)

        self.check_button = ttk.Button(check_frame, text="Check", command=self._on_check)
        self.check_button.grid(row=0, column=4, padx=4, pady=4)

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(fill=tk.X, padx=8)

        self.progress = ProgressPanel(self)
        self.progress.pack(fill=tk.X, padx=8)

        self.output = OutputPanel(self)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _board(self):
        board_name = self.board_var.get()
        if not board_name:
            self.status_label.configure(text="Select a board first.")
        return board_name

    def _set_buttons_enabled(self, enabled: bool):
        state = tk.NORMAL if enabled else tk.DISABLED
        self.convert_button.configure(state=state)
        self.run_button.configure(state=state)
        self.check_button.configure(state=state)

    def _on_convert(self):
        board_name = self._board()
        if not board_name:
            return

        self._set_buttons_enabled(False)
        self.status_label.configure(text=f"Converting '{board_name}' SPICE netlist...", style="TLabel")
        self.progress.start_busy()
        force = self.force_regenerate.get()

        def work():
            return spice_service.convert_to_simulation_ready_cir(board_name, force_regenerate=force)

        self.runner.run(
            work, on_success=self._on_converted, on_error=self._on_error,
            label=f"Converting '{board_name}' SPICE netlist...",
        )

    def _on_converted(self, cir_path):
        self._set_buttons_enabled(True)
        self.progress.stop()
        self.status_label.configure(text="Conversion complete.", style="Success.TLabel")
        self.output.set_text(f"Simulation-ready .cir written to:\n{cir_path}")

    def _on_run(self):
        board_name = self._board()
        if not board_name:
            return

        self._set_buttons_enabled(False)
        self.status_label.configure(text=f"Running ngspice simulation for '{board_name}'...", style="TLabel")
        self.progress.start_busy()
        force = self.force_regenerate.get()

        def work():
            return spice_service.run_simulation(board_name, force_regenerate_cir=force)

        self.runner.run(
            work, on_success=self._on_simulated, on_error=self._on_error,
            label=f"Running ngspice simulation for '{board_name}'...",
        )

    def _on_simulated(self, result):
        self._set_buttons_enabled(True)
        self.progress.stop()
        self.status_label.configure(text="Simulation complete.", style="Success.TLabel")

        lines = [
            f"Generated .cir: {result.cir_path}",
            f"Raw output: {result.raw_path}",
            f"ngspice log: {result.log_path}",
            f"SPICE JSON: {result.spice_json_path}",
            "",
            f"Parsed {len(result.data)} variables:",
        ]
        for idx, entry in sorted(result.data.items(), key=lambda kv: int(kv[0])):
            lines.append(f"  [{idx}] {entry['name']} ({len(entry['values'])} samples)")

        self.output.set_text("\n".join(lines))

    def _on_check(self):
        board_name = self._board()
        if not board_name:
            return

        net_name = self.net_entry.get().strip()
        expected_voltage = self.voltage_entry.get().strip()
        if not net_name or not expected_voltage:
            self.status_label.configure(text="Enter both a net name and an expected voltage.")
            return

        self._set_buttons_enabled(False)
        self.status_label.configure(text=f"Checking {net_name}...", style="TLabel")
        self.progress.start_busy()

        def work():
            return spice_service.check_expected_voltage(board_name, net_name, expected_voltage)

        self.runner.run(
            work, on_success=self._on_checked, on_error=self._on_error,
            label=f"Checking {net_name}...",
        )

    def _on_checked(self, matches):
        self._set_buttons_enabled(True)
        self.progress.stop()
        verdict = "MATCHES" if matches else "does NOT match"
        self.status_label.configure(text=f"Result: {verdict} expected voltage.", style="Success.TLabel" if matches else "TLabel")

    def _on_error(self, exc):
        self._set_buttons_enabled(True)
        self.progress.stop()
        self.status_label.configure(text="Operation failed.", style="Error.TLabel")
        show_error(self, exc, title="SPICE operation failed")
