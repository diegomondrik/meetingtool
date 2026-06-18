"""
MeetingTool.py - MeetingTool v2.5
Main entry point. Double-click or run from terminal.

Windows: python MeetingTool.py
Mac:     python3 MeetingTool.py
"""

import sys
from pathlib import Path

# When frozen by PyInstaller, modules are bundled and PyInstaller manages
# imports; BASE_DIR points to the folder holding the executable. In dev,
# add the package root to sys.path so `gui`/`tools` import as top-level.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent.resolve()
else:
    BASE_DIR = Path(__file__).parent.resolve()
    sys.path.insert(0, str(BASE_DIR))

if sys.version_info < (3, 11):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Python version error",
            f"MeetingTool requires Python 3.11 or higher.\n\n"
            f"Your version: {sys.version_info.major}.{sys.version_info.minor}\n\n"
            "Download Python 3.11+ from https://python.org"
        )
        root.destroy()
    except Exception:
        print(f"ERROR: Python 3.11+ required. Found {sys.version_info.major}.{sys.version_info.minor}")
    sys.exit(1)

from gui.app import run

if __name__ == "__main__":
    run()
