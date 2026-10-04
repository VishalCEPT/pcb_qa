"""
Small reusable Tkinter widgets shared across the PCB-QA GUI tabs.
"""

import tkinter as tk
from tkinter import scrolledtext, ttk


class OutputPanel(scrolledtext.ScrolledText):
    """A read-only scrollable text area for displaying backend results."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("wrap", tk.WORD)
        kwargs.setdefault("state", tk.DISABLED)
        kwargs.setdefault("height", 20)
        super().__init__(parent, **kwargs)

    def set_text(self, text: str):
        self.configure(state=tk.NORMAL)
        self.delete("1.0", tk.END)
        self.insert(tk.END, text)
        self.configure(state=tk.DISABLED)

    def append_text(self, text: str):
        self.configure(state=tk.NORMAL)
        self.insert(tk.END, text)
        self.see(tk.END)
        self.configure(state=tk.DISABLED)


class ProgressPanel(ttk.Frame):
    """
    A progress bar that stays hidden until an operation starts. Supports an
    indeterminate "busy" mode for opaque single-step operations and a
    determinate N/total mode for operations that can report real progress.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bar = ttk.Progressbar(self, mode="indeterminate")

    def start_busy(self):
        self.bar.configure(mode="indeterminate")
        self.bar.pack(fill=tk.X, pady=(4, 0))
        self.bar.start(12)

    def start_determinate(self, total: int):
        self.bar.stop()
        self.bar.configure(mode="determinate", maximum=max(total, 1), value=0)
        self.bar.pack(fill=tk.X, pady=(4, 0))

    def set_progress(self, value: int):
        self.bar.configure(value=value)

    def stop(self):
        self.bar.stop()
        self.bar.pack_forget()
