"""
gui/setup_window.py — MeetingTool v2.0
========================================
First-time setup wizard. Collects configuration, verifies environment,
creates folder structure, writes mip.config.json.
"""

import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class SetupWindow(BaseWindow):

    def __init__(self, parent, on_complete=None):
        super().__init__(parent, "Setup", width=660, height=620)
        self.on_complete = on_complete
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        # ── Header ──
        self._header(
            self, "MeetingTool Setup",
            "Let's get everything ready. This takes about 2 minutes."
        )

        # ── Scrollable content area ──
        canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._scroll_frame = tk.Frame(canvas, bg=COLORS["bg_card"])

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_form(self._scroll_frame)

        # ── Footer ──
        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")

        self._status = tk.Label(
            footer, text="",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], wraplength=500, justify="left"
        )
        self._status.pack(side="left", padx=PAD["window"])

        self._btn_install = self._primary_button(
            footer, "Install MeetingTool", self._run_setup
        )
        self._btn_install.pack(side="right", padx=PAD["window"])

    def _build_form(self, parent):
        # ── Section 1: Where to install ──
        self._section_label(parent, "1  Where should MeetingTool store your projects?")

        info = tk.Frame(parent, bg=COLORS["bg_card"], padx=PAD["window"], pady=4)
        info.pack(fill="x")
        tk.Label(
            info,
            text="Choose a folder on your computer. This is where your client projects,\n"
                 "meeting recordings, and reports will be organized.",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg_card"],
            justify="left", anchor="w"
        ).pack(anchor="w")

        default_root = str(Path.home() / "Documents" / "MeetingTool")
        self._var_root = self._labeled_field(
            parent, "Installation folder", default_root,
            browse=True, browse_type="dir"
        )

        # ── Section 2: AI tool ──
        self._section_label(parent, "2  Which AI tool do you use?")

        self._var_provider = self._radio_group(
            parent,
            "Select your AI provider:",
            [
                ("claude",   "Claude (Anthropic)"),
                ("chatgpt",  "ChatGPT (OpenAI)"),
                ("gemini",   "Gemini (Google)"),
            ],
            default="claude"
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        # ── Claude mode sub-question (shown only when Claude is selected) ──
        self._cowork_frame = tk.Frame(parent, bg=COLORS["accent_light"],
                                      padx=PAD["window"] + 16, pady=PAD["item"])
        self._cowork_frame.pack(fill="x")

        tk.Label(
            self._cowork_frame,
            text="How do you use Claude?",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["accent_light"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))

        self._var_cowork = self._radio_group(
            self._cowork_frame,
            "",
            [
                ("cowork",  "Claude Desktop with Cowork"),
                ("web",     "Web browser (claude.ai)"),
            ],
            default="cowork"
        )

        # ── Section 3: Language ──
        self._section_label(parent, "3  Default report language")

        self._var_language = self._radio_group(
            parent,
            "Reports will be generated in:",
            [
                ("english", "English"),
                ("spanish", "Spanish"),
            ],
            default="english"
        )

        # ── Section 4: Log area ──
        self._section_label(parent, "4  Installation log")
        self._log = self._log_box(parent, height=6)

    def _on_provider_change(self, *args):
        """Show/hide the Cowork sub-question based on provider selection."""
        if self._var_provider.get() == "claude":
            self._cowork_frame.pack(fill="x")
        else:
            self._cowork_frame.pack_forget()

    def _set_status(self, msg: str, color: str = "muted"):
        colors = {
            "muted":   COLORS["text_muted"],
            "ok":      COLORS["success"],
            "warn":    COLORS["warning"],
            "err":     COLORS["error"],
        }
        self._status.configure(text=msg, fg=colors.get(color, COLORS["text_muted"]))
        self._status.update()

    def _run_setup(self):
        """Run setup in a background thread to keep the UI responsive."""
        self._btn_install.configure(state="disabled", text="Installing…")
        self._set_status("Installing MeetingTool…", "muted")
        thread = threading.Thread(target=self._do_setup, daemon=True)
        thread.start()

    def _do_setup(self):
        """Actual setup logic — runs in background thread."""
        from tools.installer import (
            check_python, check_ffmpeg, check_dependencies,
            create_folder_structure, generate_test_video,
            _write_global_config
        )
        from datetime import datetime

        log = self._log
        ok_count = 0
        warn_count = 0

        def log_ok(msg):
            nonlocal ok_count
            ok_count += 1
            self._log_append(log, f"  ✓  {msg}", "ok")

        def log_warn(msg):
            nonlocal warn_count
            warn_count += 1
            self._log_append(log, f"  ⚠  {msg}", "warn")

        def log_err(msg):
            self._log_append(log, f"  ✗  {msg}", "err")

        def log_info(msg):
            self._log_append(log, f"      {msg}")

        # Step 1: Python
        self._log_append(log, "Checking Python version…")
        if sys.version_info >= (3, 11):
            log_ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        else:
            log_err(f"Python {sys.version_info.major}.{sys.version_info.minor} — need 3.11+")
            self._finish_error("Python 3.11+ is required. Download from https://python.org")
            return

        # Step 2: ffmpeg
        self._log_append(log, "Checking ffmpeg…")
        ffmpeg_ok = check_ffmpeg()
        if ffmpeg_ok:
            log_ok("ffmpeg found")
        else:
            log_warn("ffmpeg not found — frame extraction will not work")
            log_info("Install from: https://ffmpeg.org/download.html")

        # Step 3: Dependencies
        self._log_append(log, "Checking Python packages…")
        deps_ok = check_dependencies()
        if deps_ok:
            log_ok("All packages installed")
        else:
            log_warn("Some packages could not be installed automatically")

        # Step 4: Folder structure
        mip_root = Path(self._var_root.get()).expanduser().resolve()
        self._log_append(log, f"Creating folders at: {mip_root}")
        if create_folder_structure(mip_root):
            log_ok("Folder structure created")
        else:
            log_err("Could not create folders — check permissions")
            self._finish_error("Could not create the installation folder. Check permissions.")
            return

        # Step 5: Test video
        if ffmpeg_ok:
            self._log_append(log, "Generating test video…")
            test_path = mip_root / "tools" / "test_meeting.mp4"
            if generate_test_video(test_path):
                log_ok("Test video generated")
            else:
                log_warn("Test video generation failed — not critical")

        # Step 6: Write config
        provider = self._var_provider.get()
        cowork_mode = (
            self._var_cowork.get() == "cowork"
            if provider == "claude"
            else False
        )

        config = {
            "mip_version": "2.0",
            "mip_root": str(mip_root),
            "llm_provider": provider,
            "cowork_mode": cowork_mode,
            "default_language": self._var_language.get(),
            "installed_at": datetime.now().strftime("%Y-%m-%d"),
        }
        _write_global_config(config)
        log_ok("Configuration saved")

        # ── Create desktop shortcut ──
        self._log_append(log, "Creating desktop shortcut…")
        shortcut_ok = self._create_shortcut()
        if shortcut_ok:
            log_ok("Desktop shortcut created — 'MeetingTool' on your desktop")
        else:
            log_warn("Could not create desktop shortcut — you can still run MeetingTool.py directly")

        # ── Done ──
        self._log_append(log, "")
        self._log_append(log, "  MeetingTool installed successfully!", "ok")

        self.after(0, self._finish_success, config)

    def _create_shortcut(self) -> bool:
        """Create a desktop shortcut to MeetingTool.py."""
        import platform
        system = platform.system()
        desktop = Path.home() / "Desktop"
        script = Path(__file__).parent.parent / "MeetingTool.py"

        try:
            if system == "Windows":
                bat = desktop / "MeetingTool.bat"
                bat.write_text(
                    f'@echo off\n'
                    f'cd /d "{script.parent}"\n'
                    f'pythonw "{script}"\n',
                    encoding="utf-8"
                )
                return bat.exists()
            elif system == "Darwin":
                sh = desktop / "MeetingTool.command"
                sh.write_text(
                    f'#!/bin/bash\n'
                    f'cd "{script.parent}"\n'
                    f'python3 "{script}"\n',
                    encoding="utf-8"
                )
                sh.chmod(0o755)
                return sh.exists()
            else:
                # Linux .desktop file
                desktop_file = desktop / "MeetingTool.desktop"
                desktop_file.write_text(
                    f'[Desktop Entry]\n'
                    f'Type=Application\n'
                    f'Name=MeetingTool\n'
                    f'Exec=python3 "{script}"\n'
                    f'Terminal=false\n',
                    encoding="utf-8"
                )
                desktop_file.chmod(0o755)
                return desktop_file.exists()
        except Exception:
            return False

    def _finish_success(self, config):
        self._btn_install.configure(state="normal", text="Done ✓")
        self._btn_install.configure(bg=COLORS["success"])
        self._set_status("Installation complete!", "ok")

        messagebox.showinfo(
            "MeetingTool installed",
            f"MeetingTool is ready!\n\n"
            f"Projects folder:\n{config['mip_root']}\n\n"
            f"A shortcut has been added to your desktop.\n\n"
            f"Click OK to set up your first client project."
        )

        self.destroy()
        if self.on_complete:
            self.on_complete()

    def _finish_error(self, msg: str):
        self.after(0, lambda: (
            self._btn_install.configure(state="normal", text="Try again"),
            self._set_status(msg, "err")
        ))

    def _on_close(self):
        if messagebox.askyesno("Exit", "Setup is not complete. Exit anyway?"):
            self.master.destroy()
