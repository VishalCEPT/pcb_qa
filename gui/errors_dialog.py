"""
Friendly error reporting for backend failures surfaced in the GUI.
"""

from tkinter import messagebox

from backend.errors import BackendError


def show_error(parent, exc: Exception, title: str = "Error"):
    if isinstance(exc, BackendError):
        messagebox.showerror(title, str(exc), parent=parent)
    else:
        messagebox.showerror(title, f"Unexpected error: {exc}", parent=parent)
