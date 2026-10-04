"""
Board / project loader tab: pick a board, load its netlist into circuit JSON
(cached under Boards/<board>/Output_Files/), and show a summary of what was
found and parsed.
"""

import tkinter as tk
from tkinter import ttk

from backend import board_service

from gui.errors_dialog import show_error
from gui.widgets import OutputPanel, ProgressPanel


class BoardTab(ttk.Frame):
    def __init__(self, parent, runner, board_var):
        super().__init__(parent)
        self.runner = runner
        self.board_var = board_var

        self.force_regenerate = tk.BooleanVar(value=False)

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=8, pady=8)

        self.load_button = ttk.Button(controls, text="Load board", command=self._on_load)
        self.load_button.pack(side=tk.LEFT)

        ttk.Checkbutton(
            controls, text="Force regenerate", variable=self.force_regenerate
        ).pack(side=tk.LEFT, padx=(8, 0))

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(fill=tk.X, padx=8)

        self.progress = ProgressPanel(self)
        self.progress.pack(fill=tk.X, padx=8)

        self.output = OutputPanel(self)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _on_load(self):
        board_name = self.board_var.get()
        if not board_name:
            self.status_label.configure(text="Select a board first.")
            return

        self.load_button.configure(state=tk.DISABLED)
        self.status_label.configure(text=f"Loading '{board_name}'...", style="TLabel")
        self.progress.start_busy()
        force = self.force_regenerate.get()

        def work():
            summary = board_service.get_board_summary(board_name)
            circuit = board_service.load_or_generate_circuit(board_name, force_regenerate=force)
            return summary, circuit

        self.runner.run(work, on_success=self._on_loaded, on_error=self._on_error, label=f"Loading '{board_name}'...")

    def _on_loaded(self, payload):
        summary, circuit = payload
        self.load_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text=f"Loaded '{circuit.board_name}'.", style="Success.TLabel")

        lines = [
            f"Board: {summary.name}",
            f"Netlist: {summary.netlist_path}",
            f"SPICE file: {summary.spice_path}",
            f"Schematic PDF: {summary.schematic_pdf_path}",
            f"Questions file: {summary.questions_path}",
            f"Datasheets: {len(summary.datasheets)}",
            "",
            f"Components: {circuit.component_count}",
            f"Nets: {circuit.net_count}",
            f"Subcircuits: {circuit.subcircuit_count}",
            f"Components with a passive pin on GND: {', '.join(circuit.gnd_passive_pin_refs)}",
            "",
            f"Circuit JSON cached at: {circuit.circuit_json_path}",
        ]
        self.output.set_text("\n".join(lines))

    def _on_error(self, exc):
        self.load_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text="Load failed.", style="Error.TLabel")
        show_error(self, exc, title="Board load failed")
