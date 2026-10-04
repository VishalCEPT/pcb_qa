"""
Entry point for the PCB-QA desktop application.
"""

import tkinter as tk

import backend  # noqa: F401 - must be imported first so core/ is put on sys.path

from gui.app import App


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
