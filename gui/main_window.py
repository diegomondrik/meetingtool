"""
gui/main_window.py — MeetingTool v2.0
=======================================
Main hub window. Shows existing projects, allows running analysis,
and accessing all MeetingTool functions.
"""

import threading
from pathlib import Path
from datetime import date
import tkinter as tk
from tkinter import messagebox, filedialog, ttk

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class MainWindow(BaseWindow):

    def __init__(self, parent, config: dict):
        super().__init__(parent, "Home", width=720, height=560)
        self.resizable(True, True)
        self.minsize(640, 480)
        self.config = config
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self._load_projects()

    def _build(self):
        # ── Header ──
        self._header(
            self, "MeetingTool",
            f"Provider: {self.config.get('llm_provider','').title()}  ·  "
            f"Language: {self.config.get('default_language','').title()}"
        )

        # ── Toolbar ──
        toolbar = tk.Frame(self, bg=COLORS["bg"], padx=PAD["window"], pady=10)
        toolbar.pack(fill="x")

        self._primary_button(
            toolbar, "+ New Project", self._new_project, width=14
        ).pack(side="left", padx=(0, 8))

        self._secondary_button(
            toolbar, "⚙ Settings", self._open_settings, width=10
        ).pack(side="left")

        tk.Label(
            toolbar,
            text="Select a project and meeting folder, then click Analyze.",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg"]
        ).pack(side="right")

        self._divider(self)

        # ── Main content: left panel (projects) + right panel (meeting) ──
        content = tk.Frame(self, bg=COLORS["bg"])
        content.pack(fill="both", expand=True, padx=PAD["window"], pady=(0, PAD["window"]))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Left: project list
        left = tk.Frame(content, bg=COLORS["bg"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        tk.Label(
            left, text="Your projects",
            font=FONTS["heading"], fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w", pady=(0, 4))

        list_frame = tk.Frame(left, bg=COLORS["bg"])
        list_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._project_list = tk.Listbox(
            list_frame,
            font=FONTS["body"],
            bg=COLORS["bg_card"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground="#FFFFFF",
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            width=28,
            yscrollcommand=scrollbar.set,
            cursor="hand2"
        )
        self._project_list.pack(fill="both", expand=True)
        scrollbar.config(command=self._project_list.yview)
        self._project_list.bind("<<ListboxSelect>>", self._on_project_select)

        # Right: meeting selection + analyze + status
        right = tk.Frame(content, bg=COLORS["bg"])
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(
            right, text="Meeting to analyze",
            font=FONTS["heading"], fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w", pady=(0, 4))

        # Meeting folder picker
        folder_frame = tk.Frame(right, bg=COLORS["bg"])
        folder_frame.pack(fill="x", pady=(0, 8))

        self._var_meeting = tk.StringVar()
        self._var_meeting.trace_add("write", self._on_folder_change)
        meeting_entry = tk.Entry(
            folder_frame, textvariable=self._var_meeting,
            font=FONTS["body"],
            bg=COLORS["bg_input"], fg=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        meeting_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 4))

        tk.Button(
            folder_frame, text="Browse…",
            font=FONTS["small"],
            bg=COLORS["border"], fg=COLORS["text"],
            relief="flat", cursor="hand2",
            padx=8, pady=4,
            command=self._browse_meeting
        ).pack(side="left")

        # ── File detection panel ──
        self._detect_frame = tk.Frame(right, bg=COLORS["bg"])
        self._detect_frame.pack(fill="x", pady=(0, 6))

        # Video detection label
        self._lbl_video = tk.Label(
            self._detect_frame, text="",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], anchor="w"
        )
        self._lbl_video.pack(anchor="w")

        # Transcript detection label + optional manual picker
        self._lbl_transcript = tk.Label(
            self._detect_frame, text="",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], anchor="w"
        )
        self._lbl_transcript.pack(anchor="w")

        # Manual transcript picker — shown only when auto-detect fails
        self._transcript_manual_frame = tk.Frame(self._detect_frame, bg=COLORS["bg"])
        self._var_transcript = tk.StringVar()
        transcript_entry = tk.Entry(
            self._transcript_manual_frame,
            textvariable=self._var_transcript,
            font=FONTS["small"],
            bg=COLORS["bg_input"], fg=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["warning"],
            highlightcolor=COLORS["accent"],
        )
        transcript_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 4))
        tk.Button(
            self._transcript_manual_frame, text="Browse…",
            font=FONTS["small"],
            bg=COLORS["border"], fg=COLORS["text"],
            relief="flat", cursor="hand2",
            padx=6, pady=3,
            command=self._browse_transcript
        ).pack(side="left")
        # Hidden by default — shown only when transcript not found
        self._transcript_manual_frame.pack_forget()

        # Mode selector
        mode_frame = tk.Frame(right, bg=COLORS["bg"])
        mode_frame.pack(fill="x", pady=(0, 8))

        cowork_mode = self.config.get("cowork_mode", False)
        provider    = self.config.get("llm_provider", "claude")

        if provider == "claude" and cowork_mode:
            modes = [("cowork", "Cowork (automatic)"), ("web", "Web browser")]
            default_mode = "cowork"
        else:
            modes = [
                ("web",      "Web browser — standard  (meetings under 45 min)"),
                ("two_pass", "Web browser — two-pass  (meetings 45 min or longer)"),
            ]
            default_mode = "web"

        tk.Label(
            mode_frame, text="Workflow:",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w", pady=(0, 4))

        self._var_mode = tk.StringVar(value=default_mode)
        for value, label in modes:
            tk.Radiobutton(
                mode_frame, text=label, variable=self._var_mode, value=value,
                font=FONTS["body"],
                bg=COLORS["bg"], fg=COLORS["text"],
                activebackground=COLORS["bg"],
                selectcolor=COLORS["accent_light"],
                relief="flat", cursor="hand2",
            ).pack(anchor="w", pady=2)

        # Action buttons row
        btn_row = tk.Frame(right, bg=COLORS["bg"])
        btn_row.pack(fill="x", pady=(8, 12))

        self._btn_analyze = self._primary_button(
            btn_row, "▶  Analyze", self._run_analysis, width=14
        )
        self._btn_analyze.pack(side="left", padx=(0, 8))

        self._btn_open_report = self._secondary_button(
            btn_row, "Open report.md", self._open_report, width=14
        )
        self._btn_open_report.pack(side="left", padx=(0, 8))

        self._btn_export = self._secondary_button(
            btn_row, "Export to DOCX", self._export_docx, width=14
        )
        self._btn_export.pack(side="left")

        # Status area
        status_header = tk.Frame(right, bg=COLORS["bg"])
        status_header.pack(fill="x", pady=(0, 4))

        tk.Label(
            status_header, text="Status",
            font=FONTS["heading"], fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(side="left")

        self._lbl_timer = tk.Label(
            status_header, text="",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg"]
        )
        self._lbl_timer.pack(side="right")

        # Progress bar — hidden until analysis starts
        self._progress = ttk.Progressbar(
            right, mode="indeterminate", length=200
        )
        self._progress.pack(fill="x", pady=(0, 6))
        self._progress.pack_forget()

        status_frame = tk.Frame(
            right, bg=COLORS["bg_card"],
            highlightthickness=1,
            highlightbackground=COLORS["border"],
        )
        status_frame.pack(fill="both", expand=True)

        self._status_text = tk.Text(
            status_frame,
            font=FONTS["body"],
            bg=COLORS["bg_card"], fg=COLORS["text"],
            relief="flat",
            state="disabled",
            wrap="word",
            padx=10, pady=8,
            cursor="arrow",
        )
        status_scroll = tk.Scrollbar(status_frame, command=self._status_text.yview)
        self._status_text.configure(yscrollcommand=status_scroll.set)
        status_scroll.pack(side="right", fill="y")
        self._status_text.pack(fill="both", expand=True)

    def _load_projects(self):
        """Populate the project list from the projects folder."""
        import json
        self._project_list.delete(0, "end")
        self._projects_data = []

        mip_root = Path(self.config.get("mip_root", ""))
        projects_root = mip_root / "projects"

        if not projects_root.exists():
            return

        for client_dir in sorted(projects_root.iterdir()):
            if not client_dir.is_dir():
                continue
            for project_dir in sorted(client_dir.iterdir()):
                if not project_dir.is_dir():
                    continue
                cfg_path = project_dir / "mip.config.json"
                if cfg_path.exists():
                    try:
                        with open(cfg_path) as f:
                            cfg = json.load(f)
                        label = f"{cfg.get('client','')} — {cfg.get('project','')}"
                        self._project_list.insert("end", label)
                        self._projects_data.append(cfg)
                    except Exception:
                        pass

        if not self._projects_data:
            self._project_list.insert("end", "(no projects yet)")

    def _on_project_select(self, event):
        """Auto-populate meeting folder when a project is selected."""
        selection = self._project_list.curselection()
        if not selection or not self._projects_data:
            return
        idx = selection[0]
        if idx >= len(self._projects_data):
            return
        project_cfg = self._projects_data[idx]
        project_folder = Path(project_cfg.get("project_folder", ""))
        self._var_meeting.set(str(project_folder / f"MeetingName_{date.today().strftime('%Y%m%d')}"))

    def _on_folder_change(self, *args):
        """Detect video and transcript when folder path changes."""
        folder_str = self._var_meeting.get().strip()
        if not folder_str:
            self._lbl_video.configure(text="")
            self._lbl_transcript.configure(text="")
            self._transcript_manual_frame.pack_forget()
            return

        folder = Path(folder_str)
        if not folder.exists():
            self._lbl_video.configure(text="")
            self._lbl_transcript.configure(text="")
            self._transcript_manual_frame.pack_forget()
            return

        from tools.extract_frames import find_video_and_transcript
        video, transcript = find_video_and_transcript(folder)

        if video:
            self._lbl_video.configure(
                text=f"  ✓  Video: {video.name}",
                fg=COLORS["success"]
            )
        else:
            self._lbl_video.configure(
                text="  ✗  No .mp4 found in this folder",
                fg=COLORS["error"]
            )

        if transcript:
            self._lbl_transcript.configure(
                text=f"  ✓  Transcript: {transcript.name}",
                fg=COLORS["success"]
            )
            self._transcript_manual_frame.pack_forget()
            self._var_transcript.set("")
        else:
            self._lbl_transcript.configure(
                text="  ⚠  Transcript not found automatically — select it manually:",
                fg=COLORS["warning"]
            )
            self._transcript_manual_frame.pack(fill="x", pady=(4, 0))

    def _browse_transcript(self):
        """Browse for a transcript DOCX file manually."""
        folder_str = self._var_meeting.get().strip()
        initial = folder_str if folder_str else str(Path.home())
        path = filedialog.askopenfilename(
            title="Select transcript file",
            initialdir=initial,
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")]
        )
        if path:
            self._var_transcript.set(path)
            self._lbl_transcript.configure(
                text=f"  ✓  Transcript: {Path(path).name}  (manual)",
                fg=COLORS["success"]
            )

    def _browse_meeting(self):
        mip_root = self.config.get("mip_root", str(Path.home()))
        path = filedialog.askdirectory(
            title="Select meeting folder",
            initialdir=mip_root
        )
        if path:
            self._var_meeting.set(path)

    def _start_progress(self):
        """Start progress bar and elapsed timer."""
        import time
        self._analysis_start = time.time()
        self._progress.pack(fill="x", pady=(0, 6), before=self._status_text.master)
        self._progress.start(12)
        self._tick_timer()

    def _tick_timer(self):
        """Update elapsed time label every second while analysis runs."""
        import time
        if not getattr(self, "_analysis_running", False):
            return
        elapsed = int(time.time() - self._analysis_start)
        mins, secs = divmod(elapsed, 60)
        self._lbl_timer.configure(
            text=f"Elapsed: {mins}:{secs:02d}",
            fg=COLORS["text_muted"]
        )
        self.after(1000, self._tick_timer)

    def _stop_progress(self, success: bool = True):
        """Stop progress bar and timer, show final elapsed time."""
        import time
        self._analysis_running = False
        self._progress.stop()
        self._progress.pack_forget()
        if hasattr(self, "_analysis_start"):
            elapsed = int(time.time() - self._analysis_start)
            mins, secs = divmod(elapsed, 60)
            color = COLORS["success"] if success else COLORS["error"]
            self._lbl_timer.configure(
                text=f"Finished in {mins}:{secs:02d}",
                fg=color
            )

    def _run_analysis(self):
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return

        meeting_path = Path(meeting_folder)
        if not meeting_path.exists():
            answer = messagebox.askyesno(
                "Folder not found",
                f"The folder doesn't exist yet:\n{meeting_folder}\n\n"
                "Create it now?"
            )
            if answer:
                meeting_path.mkdir(parents=True, exist_ok=True)
            else:
                return

        # Clear previous status
        self._status_text.configure(state="normal")
        self._status_text.delete("1.0", "end")
        self._status_text.configure(state="disabled")
        self._lbl_timer.configure(text="")

        self._btn_analyze.configure(state="disabled", text="Analyzing…")
        self._analysis_running = True
        self._start_progress()
        self._append_status(f"Starting analysis: {meeting_path.name}")

        # Pass manual transcript override if set
        manual_transcript = self._var_transcript.get().strip() or None

        mode = self._var_mode.get()
        thread = threading.Thread(
            target=self._do_analysis,
            args=(meeting_path, mode, manual_transcript),
            daemon=True
        )
        thread.start()

    def _append_status(self, msg: str, color: str = None):
        """Append a line to the status text area."""
        self._status_text.configure(state="normal")
        colors_map = {
            "ok":   COLORS["success"],
            "warn": COLORS["warning"],
            "err":  COLORS["error"],
        }
        if color and color in colors_map:
            tag = f"tag_{color}"
            self._status_text.tag_configure(tag, foreground=colors_map[color])
            self._status_text.insert("end", msg + "\n", tag)
        else:
            self._status_text.insert("end", msg + "\n")
        self._status_text.see("end")
        self._status_text.configure(state="disabled")
        self._status_text.update()

    def _do_analysis(self, meeting_path: Path, mode: str, manual_transcript: str = None):
        import logging

        class GUIHandler(logging.Handler):
            def __init__(self, window):
                super().__init__()
                self.window = window
            def emit(self, record):
                msg = self.format(record)
                color = "ok" if record.levelno == logging.INFO else "warn"
                self.window.after(0, lambda m=msg, c=color: self.window._append_status(m, c))

        logger = logging.getLogger()
        handler = GUIHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            from tools.runner import run_meeting

            web_mode = mode in ("web", "two_pass")
            two_pass = mode == "two_pass"

            result = run_meeting(
                meeting_folder      = meeting_path,
                web_mode            = web_mode,
                two_pass            = two_pass,
                single_pass         = False,
                max_frames_override = None,
                manual_transcript   = Path(manual_transcript) if manual_transcript else None,
            )

            self.after(0, lambda: self._analysis_done(result))

        except SystemExit:
            self.after(0, lambda: self._analysis_error("Analysis stopped — check the output above."))
        except Exception as e:
            self.after(0, lambda: self._analysis_error(str(e)))
        finally:
            logger.removeHandler(handler)

    def _analysis_done(self, result):
        self._stop_progress(success=True)
        self._btn_analyze.configure(state="normal", text="▶  Analyze")
        self._append_status("")
        self._append_status(f"  Extraction complete — {result.n_frames} frames ready", "ok")
        self._append_status(f"  Opening next steps…")

        # Show the next steps window
        from gui.next_steps_window import NextStepsWindow
        NextStepsWindow(self.master, result=result)

    def _analysis_error(self, msg: str):
        self._stop_progress(success=False)
        self._btn_analyze.configure(state="normal", text="▶  Analyze")
        self._append_status(f"  Error: {msg}", "err")

    def _open_report(self):
        """Open the most recent report.md in the system text editor."""
        import subprocess, platform
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return

        meeting_path = Path(meeting_folder)
        reports = sorted(meeting_path.glob("report_*.md"), reverse=True)
        if not reports:
            messagebox.showinfo(
                "No report found",
                f"No report_*.md found in:\n{meeting_path}\n\n"
                "Run Analyze first to generate the report."
            )
            return

        report = reports[0]
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(["notepad.exe", str(report)])
            elif system == "Darwin":
                subprocess.Popen(["open", "-t", str(report)])
            else:
                subprocess.Popen(["xdg-open", str(report)])
            self._append_status(f"  Opened: {report.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def _export_docx(self):
        """Export the most recent report.md to DOCX with embedded images."""
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return

        meeting_path = Path(meeting_folder)
        reports = sorted(meeting_path.glob("report_*.md"), reverse=True)
        if not reports:
            messagebox.showinfo(
                "No report found",
                f"No report_*.md found in:\n{meeting_path}\n\n"
                "Run Analyze first to generate the report."
            )
            return

        report = reports[0]

        # Count image refs to inform the user
        import re
        text = report.read_text(encoding="utf-8")
        refs  = re.findall(r'\[frame_\d+_t\d{2}-\d{2}-\d{2}\.jpg\]', text)
        n_refs = len(refs)

        # Ask format
        msg = f"Report: {report.name}\n"
        if n_refs > 3:
            msg += f"Contains {n_refs} image references — DOCX recommended.\n\n"
        else:
            msg += "\n"
        msg += "Export format:"

        choice = ExportFormatDialog(self, msg).result
        if choice is None:
            return  # cancelled

        # Run export in background thread
        self._append_status(f"  Exporting {report.name} → {choice.upper()}…")
        thread = threading.Thread(
            target=self._do_export,
            args=(meeting_path, choice),
            daemon=True
        )
        thread.start()

    def _do_export(self, meeting_path: Path, output_format: str):
        try:
            from tools.exporter import run_export
            run_export(meeting_folder=meeting_path, output_format=output_format)

            from datetime import date
            docx_path = meeting_path / f"report_{date.today().strftime('%Y%m%d')}.docx"
            self.after(0, lambda: self._export_done(docx_path, output_format))
        except Exception as e:
            self.after(0, lambda: self._append_status(f"  Export error: {e}", "err"))

    def _export_done(self, docx_path: Path, output_format: str):
        self._append_status("  Export complete!", "ok")
        if output_format in ("docx", "both"):
            self._append_status(f"  DOCX saved: {docx_path}")
            import platform, subprocess
            open_folder = messagebox.askyesno(
                "Export complete",
                f"DOCX saved:\n{docx_path}\n\nOpen the folder?"
            )
            if open_folder:
                folder = docx_path.parent
                system = platform.system()
                if system == "Windows":
                    subprocess.Popen(f'explorer /select,"{docx_path}"')
                elif system == "Darwin":
                    subprocess.Popen(["open", "-R", str(docx_path)])
                else:
                    subprocess.Popen(["xdg-open", str(folder)])

    def _new_project(self):
        from gui.project_window import ProjectWindow
        ProjectWindow(
            self.master,
            global_config=self.config,
            on_complete=self._load_projects
        )

    def _open_settings(self):
        SettingsWindow(self.master, config=self.config, on_save=self._reload_config)

    def _reload_config(self):
        from tools.installer import _load_global_config
        self.config = _load_global_config()

    def _on_close(self):
        self.master.destroy()


class ExportFormatDialog(tk.Toplevel):
    """Simple dialog asking the user to choose export format."""

    def __init__(self, parent, message: str):
        super().__init__(parent)
        self.title("MeetingTool — Export format")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.result = None
        self.grab_set()

        # Center
        self.update_idletasks()
        w, h = 380, 220
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(
            self, text=message,
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg"],
            justify="left", wraplength=340, padx=20, pady=16
        ).pack(anchor="w")

        btn_frame = tk.Frame(self, bg=COLORS["bg"], padx=20, pady=8)
        btn_frame.pack(fill="x")

        for label, value in [
            ("DOCX  (recommended)", "docx"),
            ("Markdown only",       "md"),
            ("Both",                "both"),
        ]:
            tk.Button(
                btn_frame, text=label,
                font=FONTS["body"],
                bg=COLORS["bg_card"], fg=COLORS["text"],
                relief="flat", cursor="hand2",
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                padx=12, pady=6, anchor="w",
                command=lambda v=value: self._choose(v)
            ).pack(fill="x", pady=2)

        tk.Button(
            btn_frame, text="Cancel",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], relief="flat", cursor="hand2",
            command=self.destroy
        ).pack(pady=(8, 0))

        self.wait_window()

    def _choose(self, value: str):
        self.result = value
        self.destroy()


class SettingsWindow(BaseWindow):
    """Simple settings window to update global config."""

    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent, "Settings", width=540, height=500)
        self.config = config
        self.on_save = on_save
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()

    def _build(self):
        self._header(self, "Settings", "Update your MeetingTool preferences.")

        # ── Footer FIRST — anchors to bottom before canvas takes remaining space ──
        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")

        self._secondary_button(footer, "Cancel", self.destroy).pack(
            side="right", padx=8
        )
        self._primary_button(footer, "Save changes", self._save).pack(
            side="right", padx=(PAD["window"], 0)
        )

        tk.Frame(self, bg=COLORS["border"], height=1).pack(
            fill="x", side="bottom"
        )

        # ── Scrollable content AFTER footer (fills remaining space) ──
        canvas = tk.Canvas(self, bg=COLORS["bg_card"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["bg_card"])
        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._section_label(content, "Installation folder")
        self._var_root = self._labeled_field(
            content, "Projects and recordings folder",
            self.config.get("mip_root", ""),
            browse=True, browse_type="dir"
        )

        self._section_label(content, "Default AI provider")
        self._var_provider = self._radio_group(
            content, "",
            [("claude", "Claude"), ("chatgpt", "ChatGPT"), ("gemini", "Gemini")],
            default=self.config.get("llm_provider", "claude")
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        # Cowork sub-option — shown only when Claude is selected
        self._cowork_frame = tk.Frame(
            content, bg=COLORS["accent_light"],
            padx=PAD["window"] + 16, pady=PAD["item"]
        )
        self._cowork_frame.pack(fill="x")

        tk.Label(
            self._cowork_frame,
            text="How do you use Claude?",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["accent_light"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))

        self._var_cowork = self._radio_group(
            self._cowork_frame, "",
            [
                ("cowork", "Claude Desktop with Cowork"),
                ("web",    "Web browser (claude.ai)"),
            ],
            default="cowork" if self.config.get("cowork_mode", False) else "web"
        )

        if self.config.get("llm_provider", "claude") != "claude":
            self._cowork_frame.pack_forget()

        self._section_label(content, "Default report language")
        self._var_language = self._radio_group(
            content, "",
            [("english", "English"), ("spanish", "Spanish")],
            default=self.config.get("default_language", "english")
        )

    def _on_close(self):
        """Ask user to save before closing if they press X."""
        if messagebox.askyesno(
            "Save changes?",
            "Do you want to save your changes before closing?"
        ):
            self._save()
        else:
            self.destroy()

    def _on_provider_change(self, *args):
        if self._var_provider.get() == "claude":
            self._cowork_frame.pack(fill="x")
        else:
            self._cowork_frame.pack_forget()

    def _save(self):
        from tools.installer import _write_global_config
        provider = self._var_provider.get()
        cowork_mode = (
            self._var_cowork.get() == "cowork"
            if provider == "claude"
            else False
        )
        updated = {
            **self.config,
            "mip_root":         self._var_root.get(),
            "llm_provider":     provider,
            "cowork_mode":      cowork_mode,
            "default_language": self._var_language.get(),
        }
        _write_global_config(updated)
        if self.on_save:
            self.on_save()
        messagebox.showinfo("Saved", "Settings saved successfully.")
        self.destroy()
