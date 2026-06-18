"""
gui/setup_window.py - MeetingTool v2.5
First-time setup wizard. CustomTkinter dark mode.
"""

import sys
import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class SetupWindow(BaseWindow):

    def __init__(self, parent, on_complete=None):
        super().__init__(parent, "Setup", width=680, height=640)
        self.on_complete = on_complete
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        self._header(
            self, "MeetingTool Setup",
            "Let's get everything ready. This takes about 2 minutes."
        )

        # Footer (anchored before scroll)
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1, corner_radius=0).pack(
            fill="x", side="bottom"
        )
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        footer.pack(fill="x", side="bottom", pady=12)

        self._status = ctk.CTkLabel(
            footer, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
            anchor="w", wraplength=460,
        )
        self._status.pack(side="left", padx=PAD["window"])

        self._btn_install = self._primary_button(
            footer, "Install MeetingTool", self._run_setup, width=160
        )
        self._btn_install.pack(side="right", padx=PAD["window"])

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)
        self._build_form(scroll)

    def _build_form(self, parent):
        self._section_label(parent, "1  Where should MeetingTool store your projects?")

        info = ctk.CTkFrame(parent, fg_color="transparent")
        info.pack(fill="x", padx=PAD["window"], pady=(4, 0))
        ctk.CTkLabel(
            info,
            text="Choose a folder. Projects, recordings, and reports will be organized here.",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
            justify="left", anchor="w",
        ).pack(anchor="w")

        default_root = str(Path.home() / "Documents" / "MeetingTool")
        self._var_root = self._labeled_field(
            parent, "Installation folder", default_root, browse=True, browse_type="dir"
        )

        self._section_label(parent, "2  Which AI tool do you use?")

        self._var_provider = self._radio_group(
            parent, "Select your AI provider:",
            [
                ("claude",   "Claude (Anthropic)"),
                ("chatgpt",  "ChatGPT (OpenAI)"),
                ("gemini",   "Gemini (Google)"),
            ],
            default="claude",
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        # Claude sub-question
        self._cowork_frame = ctk.CTkFrame(parent, fg_color=COLORS["accent_light"], corner_radius=0)
        self._cowork_frame.pack(fill="x")

        ctk.CTkLabel(
            self._cowork_frame, text="How do you use Claude?",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"] + 16, pady=(PAD["item"], 0))

        self._var_cowork = ctk.StringVar(value="cowork")
        for value, label in [
            ("cowork", "Claude Desktop with Cowork"),
            ("web",    "Web browser (claude.ai)"),
        ]:
            ctk.CTkRadioButton(
                self._cowork_frame, text=label, variable=self._var_cowork, value=value,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"],
            ).pack(anchor="w", padx=PAD["window"] + 20, pady=2)
        ctk.CTkFrame(self._cowork_frame, fg_color="transparent", height=PAD["small"]).pack()

        self._section_label(parent, "3  Default report language")

        self._var_language = self._radio_group(
            parent, "Reports will be generated in:",
            [("english", "English"), ("spanish", "Spanish")],
            default="english",
        )

        self._section_label(parent, "4  Installation log")
        self._log = self._log_box(parent, height=6)

    def _on_provider_change(self, *args):
        if self._var_provider.get() == "claude":
            self._cowork_frame.pack(fill="x")
        else:
            self._cowork_frame.pack_forget()

    def _set_status(self, msg: str, color: str = "muted"):
        colors = {
            "muted": COLORS["text_muted"],
            "ok":    COLORS["success"],
            "warn":  COLORS["warning"],
            "err":   COLORS["error"],
        }
        self._status.configure(text=msg, text_color=colors.get(color, COLORS["text_muted"]))
        self._status.update()

    def _run_setup(self):
        self._btn_install.configure(state="disabled", text="Installing...")
        self._set_status("Installing MeetingTool...", "muted")
        threading.Thread(target=self._do_setup, daemon=True).start()

    def _do_setup(self):
        from tools.installer import (
            check_python, check_ffmpeg, check_dependencies,
            create_folder_structure, generate_test_video,
            _write_global_config,
        )
        from datetime import datetime

        log = self._log
        ok_count = warn_count = 0

        def log_ok(msg):
            nonlocal ok_count; ok_count += 1
            self._log_append(log, f"  ok  {msg}", "ok")

        def log_warn(msg):
            nonlocal warn_count; warn_count += 1
            self._log_append(log, f"  warn  {msg}", "warn")

        def log_err(msg):
            self._log_append(log, f"  err  {msg}", "err")

        def log_info(msg):
            self._log_append(log, f"      {msg}")

        self._log_append(log, "Checking Python version...")
        if sys.version_info >= (3, 11):
            log_ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
        else:
            log_err(f"Python {sys.version_info.major}.{sys.version_info.minor} -- need 3.11+")
            self.after(0, lambda: self._finish_error("Python 3.11+ is required."))
            return

        self._log_append(log, "Checking ffmpeg...")
        ffmpeg_ok = check_ffmpeg()
        if ffmpeg_ok:
            log_ok("ffmpeg found")
        else:
            log_warn("ffmpeg not found -- frame extraction will not work")

        self._log_append(log, "Checking Python packages...")
        deps_ok = check_dependencies()
        if deps_ok:
            log_ok("All packages installed")
        else:
            log_warn("Some packages could not be installed automatically")

        mip_root = Path(self._var_root.get()).expanduser().resolve()
        self._log_append(log, f"Creating folders at: {mip_root}")
        if create_folder_structure(mip_root):
            log_ok("Folder structure created")
        else:
            log_err("Could not create folders")
            self.after(0, lambda: self._finish_error("Could not create folder. Check permissions."))
            return

        if ffmpeg_ok:
            self._log_append(log, "Generating test video...")
            test_path = mip_root / "tools" / "test_meeting.mp4"
            if generate_test_video(test_path):
                log_ok("Test video generated")
            else:
                log_warn("Test video generation failed -- not critical")

        provider    = self._var_provider.get()
        cowork_mode = (self._var_cowork.get() == "cowork") if provider == "claude" else False
        config = {
            "mip_version":     "2.5",
            "mip_root":        str(mip_root),
            "llm_provider":    provider,
            "cowork_mode":     cowork_mode,
            "default_language": self._var_language.get(),
            "installed_at":    datetime.now().strftime("%Y-%m-%d"),
        }
        _write_global_config(config)
        log_ok("Configuration saved")

        self._log_append(log, "Creating desktop shortcut...")
        if self._create_shortcut():
            log_ok("Desktop shortcut created")
        else:
            log_warn("Could not create shortcut -- run MeetingTool.py directly")

        self._log_append(log, "")
        self._log_append(log, "  MeetingTool installed successfully!", "ok")
        self.after(0, lambda: self._finish_success(config))

    def _create_shortcut(self) -> bool:
        import platform
        system  = platform.system()
        desktop = Path.home() / "Desktop"
        frozen  = getattr(sys, "frozen", False)
        exe     = Path(sys.executable)             # the MeetingTool.exe when frozen
        script  = Path(__file__).parent.parent / "MeetingTool.py"
        try:
            if system == "Windows":
                bat = desktop / "MeetingTool.bat"
                if frozen:
                    bat.write_text(
                        f'@echo off\nstart "" "{exe}"\n', encoding="utf-8"
                    )
                else:
                    bat.write_text(
                        f'@echo off\ncd /d "{script.parent}"\npythonw "{script}"\n',
                        encoding="utf-8"
                    )
                return bat.exists()
            elif system == "Darwin":
                sh = desktop / "MeetingTool.command"
                launch = f'"{exe}"\n' if frozen else f'cd "{script.parent}"\npython3 "{script}"\n'
                sh.write_text(f'#!/bin/bash\n{launch}', encoding="utf-8")
                sh.chmod(0o755)
                return sh.exists()
            else:
                df = desktop / "MeetingTool.desktop"
                exec_line = f'"{exe}"' if frozen else f'python3 "{script}"'
                df.write_text(
                    f'[Desktop Entry]\nType=Application\nName=MeetingTool\n'
                    f'Exec={exec_line}\nTerminal=false\n',
                    encoding="utf-8"
                )
                df.chmod(0o755)
                return df.exists()
        except Exception:
            return False

    def _finish_success(self, config):
        self._btn_install.configure(state="normal", text="Done")
        self._btn_install.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"]
        )
        self._set_status("Installation complete!", "ok")
        messagebox.showinfo(
            "MeetingTool installed",
            f"MeetingTool is ready!\n\nProjects folder:\n{config['mip_root']}\n\n"
            "Click OK to set up your first client project."
        )
        self.destroy()
        if self.on_complete:
            self.on_complete()

    def _finish_error(self, msg: str):
        self.after(0, lambda: (
            self._btn_install.configure(state="normal", text="Try again"),
            self._set_status(msg, "err"),
        ))

    def _on_close(self):
        if messagebox.askyesno("Exit", "Setup is not complete. Exit anyway?"):
            self.master.destroy()
