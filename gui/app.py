"""
gui/app.py - MeetingTool v2.5
CTk root + launch entry point.
"""

import customtkinter as ctk


def run():
    root = ctk.CTk()
    root.update()    # CTk on Windows: render once before withdraw so Toplevels work
    root.withdraw()

    from tools.installer import _load_global_config
    config = _load_global_config()

    if not config:
        from gui.setup_window import SetupWindow
        SetupWindow(root, on_complete=lambda: _show_main(root))
    else:
        _show_main(root)

    root.mainloop()


def _show_main(root):
    from tools.installer import _load_global_config
    from gui.main_window import MainWindow
    config = _load_global_config()
    MainWindow(root, config=config)
