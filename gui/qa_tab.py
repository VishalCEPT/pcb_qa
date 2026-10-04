"""
Interactive LLM Q&A tab: ask a free-form question about the selected board;
Gemini may call the SPICE/connections/datasheet tools against real board
files before answering.
"""

import tkinter as tk
from tkinter import ttk

from backend import qa_service

from gui.errors_dialog import show_error
from gui.widgets import OutputPanel, ProgressPanel


class QATab(ttk.Frame):
    def __init__(self, parent, runner, board_var):
        super().__init__(parent)
        self.runner = runner
        self.board_var = board_var

        controls = ttk.Frame(self)
        controls.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(controls, text="Question:").pack(side=tk.LEFT)
        self.question_entry = ttk.Entry(controls)
        self.question_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 8))
        self.question_entry.bind("<Return>", lambda _event: self._on_ask())

        self.ask_button = ttk.Button(controls, text="Ask", command=self._on_ask)
        self.ask_button.pack(side=tk.LEFT)

        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(fill=tk.X, padx=8)

        self.progress = ProgressPanel(self)
        self.progress.pack(fill=tk.X, padx=8)

        self.output = OutputPanel(self)
        self.output.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def _on_ask(self):
        board_name = self.board_var.get()
        question = self.question_entry.get().strip()

        if not board_name:
            self.status_label.configure(text="Select a board first.")
            return
        if not question:
            self.status_label.configure(text="Enter a question first.")
            return

        self.ask_button.configure(state=tk.DISABLED)
        self.status_label.configure(text="Asking Gemini...", style="TLabel")
        self.progress.start_busy()
        self.output.set_text("")

        def work(report):
            return qa_service.ask(board_name, question, on_tool_call=report)

        self.runner.run(
            work, on_success=self._on_answered, on_error=self._on_error,
            on_progress=self._on_tool_call, label="Asking Gemini...",
        )

    def _on_tool_call(self, call):
        self.output.append_text(f"Calling {call.name}({call.args}) -> {call.result}\n")

    def _on_answered(self, result):
        self.ask_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text="Done.", style="Success.TLabel")

        lines = ["", f"Answer:\n{result.answer}"]
        if not result.tool_calls:
            lines.insert(0, "(No tools were called.)")
        self.output.append_text("\n".join(lines))

    def _on_error(self, exc):
        self.ask_button.configure(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.configure(text="Request failed.", style="Error.TLabel")
        show_error(self, exc, title="Q&A request failed")
