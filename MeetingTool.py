"""
MeetingTool.py — MeetingTool v2.0
===================================
Main GUI entry point. Replaces terminal interaction completely.
Double-click this file (or the desktop shortcut) to open MeetingTool.

Windows: python MeetingTool.py
Mac:     python3 MeetingTool.py
"""

import sys
import os
from pathlib import Path

# Ensure tools/ is importable regardless of where Python is invoked from
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Verify Python version before importing tkinter
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

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from gui.setup_window import SetupWindow
from gui.project_window import ProjectWindow
from gui.main_window import MainWindow


def main():
    root = tk.Tk()
    root.withdraw()  # Hide root — we use Toplevel windows

    # Check if MeetingTool is already set up
    from tools.installer import _load_global_config
    config = _load_global_config()

    if not config:
        # First time — show setup
        win = SetupWindow(root, on_complete=lambda: show_main(root))
    else:
        show_main(root)

    root.mainloop()


def show_main(root):
    from tools.installer import _load_global_config
    config = _load_global_config()
    win = MainWindow(root, config=config)


if __name__ == "__main__":
    main()
