"""
Benchmark & evaluation dashboard tab: run the board's question bank through
one of the prompt-engineering strategies and show the scored results.
"""

import tkinter as tk
from tkinter import ttk

from backend import benchmark_service

from gui.errors_dialog import show_error
from gui.widgets import OutputPanel, ProgressPanel


class BenchmarkTab(ttk.Frame):
    def __init__(self, parent, runner, board_var):
        super().__init__(parent)
        self.runner = runner
        self.board_var = board_var

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(controls, text="Strategy:").pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar()
        strategy_combo = ttk.Combobox(
            controls,
            textvariable=self.strategy_var,
            values=benchmark_service.list_strategies(),
            state="readonly",
            width=20,
        )
        strategy_combo.pack(side=tk.LEFT, padx=(4, 8))
        strategy_combo.current(0)

        ttk.Label(controls, text="Limit:").pack(side=tk.LEFT)
        self.limit_entry = ttk.Entry(controls, width=6)
        self.limit_entry.insert(0, "5")
        self.limit_entry.pack(side=tk.LEFT, padx=(4, 8))

        self.run_button = ttk.Button(controls, text="Run benchmark", command=self._on_run)
        self.run_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(fill=tk.X, padx=8)

        self.progress = ProgressPanel(self)
        self.progress.pack(fill=tk.X, padx=8)

        self.output = OutputPanel(self)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _on_run(self):
        board_name = self.board_var.get()
        strategy = self.strategy_var.get()

        if not board_name:
            self.status_label.configure(text="Select a board first.")
            return

        limit_text = self.limit_entry.get().strip()
        try:
            limit = int(limit_text) if limit_text else None
        except ValueError:
            self.status_label.configure(text="Limit must be a whole number.")
            return

        self.run_button.configure(state=tk.DISABLED)
        self.status_label.configure(text=f"Running '{strategy}' benchmark for '{board_name}'...", style="TLabel")
        self._seen = 0
        self.progress.start_busy()
        self.output.set_text("Per-question results:\n")

        def work(report):
            return benchmark_service.run_benchmark(
                board_name, strategy, limit=limit,
                on_question=lambda result, total: report((result, total)),
            )

        self.runner.run(
            work, on_success=self._on_done, on_error=self._on_error,
            on_progress=self._on_question, label=f"Running '{strategy}' benchmark for '{board_name}'...",
        )

    def _on_question(self, payload):
        result, total = payload
        self._seen += 1
        if self._seen == 1:
            self.progress.start_determinate(total)
        self.progress.set_progress(self._seen)
        self.status_label.configure(text=f"Question {self._seen} of {total}...", style="TLabel")

        mark = "OK" if result.correct else "X "
        self.output.append_text(
            f"  [{mark}] Q{result.question_number}: expected={result.expected} "
            f"predicted={result.predicted}  {result.question}\n"
        )

    def _on_done(self, report):
        self.run_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text="Benchmark complete.", style="Success.TLabel")

        lines = [
            f"Strategy: {report.strategy}",
            f"Accuracy: {report.accuracy:.2f}",
            f"Precision: {report.precision:.2f}",
            f"Recall: {report.recall:.2f}",
            f"F1: {report.f1:.2f}",
            f"Confusion matrix (rows/cols = YES, NO): {report.confusion}",
            f"Results saved to: {report.results_path}",
            "",
            "Per-question results:",
        ]
        for r in report.results:
            mark = "OK" if r.correct else "X "
            lines.append(f"  [{mark}] Q{r.question_number}: expected={r.expected} predicted={r.predicted}  {r.question}")

        self.output.set_text("\n".join(lines))

    def _on_error(self, exc):
        self.run_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text="Benchmark failed.", style="Error.TLabel")
        show_error(self, exc, title="Benchmark failed")
