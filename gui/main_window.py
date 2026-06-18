"""
gui/main_window.py - MeetingTool v2.5
Main hub window. Sidebar + main panel layout. CustomTkinter dark mode.
"""

import threading
import time
from pathlib import Path
from datetime import date
import customtkinter as ctk
from tkinter import messagebox, filedialog

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class MainWindow(BaseWindow):

    def __init__(self, parent, config: dict):
        super().__init__(parent, "Home", width=960, height=620)
        self.resizable(True, True)
        self.minsize(760, 500)
        self.config = config
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._analysis_running = False
        self._analysis_start = 0.0
        self._projects_data = []
        self._project_buttons = []
        self._selected_project_idx = None
        self._build()
        self._load_projects()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main_panel()

    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], corner_radius=0, width=210)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.columnconfigure(0, weight=1)
        sb.rowconfigure(3, weight=1)

        # App name
        ctk.CTkLabel(
            sb, text="MeetingTool",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(16, 0), sticky="ew")

        ctk.CTkLabel(
            sb,
            text=f"{self.config.get('llm_provider','').title()} | {self.config.get('default_language','').title()}",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        ).grid(row=1, column=0, padx=14, pady=(2, 8), sticky="ew")

        ctk.CTkLabel(
            sb, text="Projects",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        ).grid(row=2, column=0, padx=14, pady=(4, 2), sticky="ew")

        self._project_list_frame = ctk.CTkScrollableFrame(
            sb, fg_color=COLORS["bg_sidebar"], corner_radius=0,
        )
        self._project_list_frame.grid(row=3, column=0, sticky="nsew")
        self._project_list_frame.columnconfigure(0, weight=1)

        # Sidebar footer
        footer = ctk.CTkFrame(sb, fg_color=COLORS["bg_sidebar"], corner_radius=0)
        footer.grid(row=4, column=0, sticky="ew", padx=10, pady=10)
        footer.columnconfigure(0, weight=1)

        ctk.CTkButton(
            footer, text="+ New Project", command=self._new_project,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", corner_radius=6, height=32,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            footer, text="Settings", command=self._open_settings,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            border_width=1, corner_radius=6, height=32,
        ).grid(row=1, column=0, sticky="ew")

    def _build_main_panel(self):
        main = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        self._build_picker(main)
        self._build_mode_selector(main)
        self._build_button_row(main)
        self._build_status_area(main)

    def _build_picker(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=0)
        frame.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            frame, text="Meeting folder",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text"], fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"], pady=(PAD["item"], 2))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=PAD["window"], pady=(0, PAD["small"]))
        row.columnconfigure(0, weight=1)

        self._var_meeting = ctk.StringVar()
        self._var_meeting.trace_add("write", self._on_folder_change)
        ctk.CTkEntry(
            row, textvariable=self._var_meeting,
            font=ctk.CTkFont(*FONTS["body"]),
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        ctk.CTkButton(
            row, text="Browse...", command=self._browse_meeting,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            text_color=COLORS["text"], width=80, height=32, corner_radius=4,
        ).grid(row=0, column=1)

        self._lbl_video = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        )
        self._lbl_video.pack(anchor="w", padx=PAD["window"])

        self._lbl_transcript = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        )
        self._lbl_transcript.pack(anchor="w", padx=PAD["window"], pady=(0, 2))

        # Manual transcript picker (hidden by default)
        self._transcript_manual_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tr_row = ctk.CTkFrame(self._transcript_manual_frame, fg_color="transparent")
        tr_row.pack(fill="x", padx=PAD["window"], pady=(2, PAD["small"]))
        tr_row.columnconfigure(0, weight=1)
        self._var_transcript = ctk.StringVar()
        ctk.CTkEntry(
            tr_row, textvariable=self._var_transcript,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["bg_input"], border_color=COLORS["warning"],
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            tr_row, text="Browse...", command=self._browse_transcript,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            text_color=COLORS["text"], width=80, height=28, corner_radius=4,
        ).grid(row=0, column=1)

    def _build_mode_selector(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=0)
        frame.grid(row=1, column=0, sticky="ew", pady=(1, 0))

        cowork_mode = self.config.get("cowork_mode", False)
        provider    = self.config.get("llm_provider", "claude")

        if provider == "claude" and cowork_mode:
            modes = [("cowork", "Cowork (automatic)"), ("web", "Web browser")]
            default_mode = "cowork"
        else:
            modes = [
                ("web",      "Web — standard  (under 45 min)"),
                ("two_pass", "Web — two-pass  (45 min or longer)"),
            ]
            default_mode = "web"

        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=PAD["window"], pady=PAD["small"])

        ctk.CTkLabel(
            inner, text="Workflow:",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
        ).pack(side="left", padx=(0, 12))

        self._var_mode = ctk.StringVar(value=default_mode)
        for value, label in modes:
            ctk.CTkRadioButton(
                inner, text=label, variable=self._var_mode, value=value,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"],
            ).pack(side="left", padx=(0, 16))

    def _build_button_row(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"], corner_radius=0)
        frame.grid(row=2, column=0, sticky="ew", padx=PAD["window"], pady=PAD["item"])

        self._btn_analyze = ctk.CTkButton(
            frame, text="Analyze", command=self._run_analysis,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", corner_radius=6, width=100, height=34,
        )
        self._btn_analyze.pack(side="left", padx=(0, 6))

        self._btn_next_steps = ctk.CTkButton(
            frame, text="Next Steps", command=self._open_next_steps,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            border_width=1, corner_radius=6, width=100, height=34,
        )
        self._btn_next_steps.pack(side="left", padx=(0, 6))

        self._btn_open_report = ctk.CTkButton(
            frame, text="Open report", command=self._open_report,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            border_width=1, corner_radius=6, width=100, height=34,
        )
        self._btn_open_report.pack(side="left", padx=(0, 6))

        self._btn_export = ctk.CTkButton(
            frame, text="Export DOCX", command=self._export_docx,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            border_width=1, corner_radius=6, width=110, height=34,
        )
        self._btn_export.pack(side="left")

    def _build_status_area(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg"], corner_radius=0)
        frame.grid(row=3, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)

        # Status header row
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=PAD["window"], pady=(PAD["small"], 2))

        ctk.CTkLabel(
            top, text="Status",
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["text"], fg_color="transparent",
        ).pack(side="left")

        self._lbl_timer = ctk.CTkLabel(
            top, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
        )
        self._lbl_timer.pack(side="right")

        # Pipeline message label
        self._lbl_progress_msg = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        )
        self._lbl_progress_msg.grid(row=1, column=0, padx=PAD["window"], sticky="w")

        # Progress bar (hidden until analysis)
        self._progress = ctk.CTkProgressBar(
            frame,
            fg_color=COLORS["bg_card"],
            progress_color=COLORS["accent"],
            mode="indeterminate",
            height=6,
        )
        self._progress.grid(row=2, column=0, padx=PAD["window"], pady=(0, 2), sticky="ew")
        self._progress.grid_remove()

        # Log console — always visible
        self._log = ctk.CTkTextbox(
            frame,
            font=ctk.CTkFont(*FONTS["mono"]),
            fg_color=COLORS["bg_sidebar"], text_color="#D4D4D4",
            wrap="word", corner_radius=0,
        )
        self._log.grid(row=3, column=0, sticky="nsew")
        self._log.configure(state="disabled")

    # ── Project list ──────────────────────────────────────────────────────────

    def _load_projects(self):
        import json
        for w in self._project_buttons:
            w.destroy()
        self._project_buttons.clear()
        self._projects_data.clear()
        self._selected_project_idx = None

        mip_root      = Path(self.config.get("mip_root", ""))
        projects_root = mip_root / "projects"

        if not projects_root.exists():
            self._project_no_results()
            return

        row_idx = 0
        for client_dir in sorted(projects_root.iterdir()):
            if not client_dir.is_dir():
                continue
            for project_dir in sorted(client_dir.iterdir()):
                if not project_dir.is_dir():
                    continue
                cfg_path = project_dir / "mip.config.json"
                if not cfg_path.exists():
                    continue
                try:
                    with open(cfg_path) as f:
                        cfg = json.load(f)
                    label = f"{cfg.get('client','')} - {cfg.get('project','')}"
                    idx = len(self._projects_data)
                    btn = ctk.CTkButton(
                        self._project_list_frame, text=label,
                        font=ctk.CTkFont(*FONTS["small"]),
                        fg_color="transparent", hover_color=COLORS["bg_card"],
                        text_color=COLORS["text"], anchor="w",
                        corner_radius=4, height=28,
                        command=lambda i=idx: self._on_project_select(i),
                    )
                    btn.grid(row=row_idx, column=0, padx=4, pady=1, sticky="ew")
                    self._project_buttons.append(btn)
                    self._projects_data.append(cfg)
                    row_idx += 1
                except Exception:
                    pass

        if not self._projects_data:
            self._project_no_results()

    def _project_no_results(self):
        lbl = ctk.CTkLabel(
            self._project_list_frame, text="No projects yet",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        )
        lbl.grid(row=0, column=0, padx=10, pady=4, sticky="w")
        self._project_buttons.append(lbl)

    def _on_project_select(self, idx: int):
        for i, btn in enumerate(self._project_buttons):
            if isinstance(btn, ctk.CTkButton):
                if i == idx:
                    btn.configure(fg_color=COLORS["accent"], text_color="#000000")
                else:
                    btn.configure(fg_color="transparent", text_color=COLORS["text"])
        self._selected_project_idx = idx
        cfg = self._projects_data[idx]
        folder = Path(cfg.get("project_folder", ""))
        self._var_meeting.set(str(folder / f"MeetingName_{date.today().strftime('%Y%m%d')}"))

    # ── Folder detection ──────────────────────────────────────────────────────

    def _on_folder_change(self, *args):
        folder_str = self._var_meeting.get().strip()
        if not folder_str or not Path(folder_str).exists():
            self._lbl_video.configure(text="")
            self._lbl_transcript.configure(text="")
            self._transcript_manual_frame.pack_forget()
            return

        from tools.extract_frames import find_video_and_transcript
        video, transcript = find_video_and_transcript(Path(folder_str))

        if video:
            self._lbl_video.configure(
                text=f"  Video: {video.name}", text_color=COLORS["success"]
            )
        else:
            self._lbl_video.configure(
                text="  No .mp4 found", text_color=COLORS["error"]
            )

        if transcript:
            self._lbl_transcript.configure(
                text=f"  Transcript: {transcript.name}", text_color=COLORS["success"]
            )
            self._transcript_manual_frame.pack_forget()
            self._var_transcript.set("")
        else:
            self._lbl_transcript.configure(
                text="  Transcript not found - select manually:",
                text_color=COLORS["warning"]
            )
            self._transcript_manual_frame.pack(fill="x")

    def _browse_meeting(self):
        path = filedialog.askdirectory(
            title="Select meeting folder",
            initialdir=self.config.get("mip_root", str(Path.home()))
        )
        if path:
            self._var_meeting.set(path)

    def _browse_transcript(self):
        initial = self._var_meeting.get().strip() or str(Path.home())
        path = filedialog.askopenfilename(
            title="Select transcript file", initialdir=initial,
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
        )
        if path:
            self._var_transcript.set(path)
            self._lbl_transcript.configure(
                text=f"  Transcript: {Path(path).name}  (manual)",
                text_color=COLORS["success"]
            )

    # ── Progress helpers ──────────────────────────────────────────────────────

    def _start_progress(self):
        self._analysis_start = time.time()
        self._progress.grid()
        self._progress.start()
        self._tick_timer()

    def _tick_timer(self):
        if not self._analysis_running:
            return
        elapsed = int(time.time() - self._analysis_start)
        mins, secs = divmod(elapsed, 60)
        self._lbl_timer.configure(text=f"Elapsed: {mins}:{secs:02d}")
        self.after(1000, self._tick_timer)

    def _stop_progress(self, success: bool = True):
        self._analysis_running = False
        self._progress.stop()
        self._progress.grid_remove()
        self._lbl_progress_msg.configure(text="")
        if self._analysis_start:
            elapsed = int(time.time() - self._analysis_start)
            mins, secs = divmod(elapsed, 60)
            self._lbl_timer.configure(
                text=f"Finished in {mins}:{secs:02d}",
                text_color=COLORS["success"] if success else COLORS["error"],
            )

    # ── Log console helpers ───────────────────────────────────────────────────

    def _append_status(self, msg: str, color: str = None):
        color_map = {"ok": "#4ADE80", "warn": "#FBBF24", "err": "#F87171"}
        self._log.configure(state="normal")
        if color and color in color_map:
            tag = f"_clr_{color}"
            self._log._textbox.tag_configure(tag, foreground=color_map[color])
            self._log._textbox.insert("end", msg + "\n", tag)
        else:
            self._log._textbox.insert("end", msg + "\n")
        self._log._textbox.see("end")
        self._log.configure(state="disabled")
        self._log.update()

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("0.0", "end")
        self._log.configure(state="disabled")

    # ── Analyze (web / two-pass / cowork) ────────────────────────────────────

    def _run_analysis(self):
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return

        meeting_path = Path(meeting_folder)
        if not meeting_path.exists():
            if messagebox.askyesno("Folder not found", f"Create folder?\n{meeting_folder}"):
                meeting_path.mkdir(parents=True, exist_ok=True)
            else:
                return

        self._clear_log()
        self._lbl_timer.configure(text="")
        self._btn_analyze.configure(state="disabled", text="Analyzing...")
        self._analysis_running = True
        self._start_progress()
        self._append_status(f"Starting analysis: {meeting_path.name}")

        manual_transcript = self._var_transcript.get().strip() or None
        mode = self._var_mode.get()
        threading.Thread(
            target=self._do_analysis,
            args=(meeting_path, mode, manual_transcript),
            daemon=True,
        ).start()

    def _do_analysis(self, meeting_path: Path, mode: str, manual_transcript: str = None):
        import logging

        class GUIHandler(logging.Handler):
            def __init__(self, win):
                super().__init__()
                self.win = win
            def emit(self, record):
                msg   = self.format(record)
                color = "ok" if record.levelno == logging.INFO else "warn"
                self.win.after(0, lambda m=msg, c=color: self.win._append_status(m, c))

        logger  = logging.getLogger()
        handler = GUIHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            from tools.runner import run_meeting
            result = run_meeting(
                meeting_folder      = meeting_path,
                web_mode            = mode in ("web", "two_pass"),
                two_pass            = mode == "two_pass",
                single_pass         = False,
                max_frames_override = None,
                manual_transcript   = Path(manual_transcript) if manual_transcript else None,
            )
            self.after(0, lambda: self._analysis_done(result))
        except SystemExit:
            self.after(0, lambda: self._analysis_error("Analysis stopped."))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: self._analysis_error(msg))
        finally:
            logger.removeHandler(handler)

    def _analysis_done(self, result):
        self._stop_progress(success=True)
        self._btn_analyze.configure(state="normal", text="Analyze")
        self._append_status(f"  Extraction complete - {result.n_frames} frames ready", "ok")
        self._append_status("  Opening next steps...")
        from gui.next_steps_window import NextStepsWindow
        NextStepsWindow(self, result=result)

    def _analysis_error(self, msg: str):
        self._stop_progress(success=False)
        self._btn_analyze.configure(state="normal", text="Analyze")
        self._append_status(f"  Error: {msg}", "err")

    # ── Next Steps (from existing frames) ─────────────────────────────────────

    def _open_next_steps(self):
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return

        meeting_path    = Path(meeting_folder)
        frames_dir      = meeting_path / "imagenes_reunion"
        existing_frames = sorted(frames_dir.glob("frame_*.jpg")) if frames_dir.exists() else []

        from tools.runner import _merged_config
        config      = _merged_config(meeting_path)
        provider    = config.get("llm_provider", "claude")
        cowork_mode = config.get("cowork_mode", False)
        is_cowork   = provider == "claude" and cowork_mode

        if not existing_frames:
            if messagebox.askyesno("No frames found", "Run Analyze first to extract frames?"):
                self._run_analysis()
            return

        if is_cowork:
            self._append_status(f"  Using {len(existing_frames)} existing frames...")
            self._build_result_from_existing(meeting_path, existing_frames)
        else:
            answer = messagebox.askyesno(
                "Use existing frames?",
                f"Found {len(existing_frames)} frames in:\n{frames_dir}\n\nUse them?"
            )
            if answer:
                self._build_result_from_existing(meeting_path, existing_frames)
            else:
                self._run_analysis()

    def _build_result_from_existing(self, meeting_path: Path, existing_frames: list):
        from tools.runner import AnalysisResult, _merged_config
        config      = _merged_config(meeting_path)
        provider    = config.get("llm_provider", "claude")
        cowork_mode = config.get("cowork_mode", False)
        report_lang = config.get("report_language", "english")

        txt_files      = list(meeting_path.glob("*.txt"))
        transcript_txt = txt_files[0] if txt_files else None

        from tools.prompt_generator import generate_meeting_prompt
        prompt   = generate_meeting_prompt(config, report_lang)
        workflow = "cowork" if (provider == "claude" and cowork_mode) else "web"

        result = AnalysisResult(
            workflow        = workflow,
            meeting_folder  = meeting_path,
            frames_dir      = meeting_path / "imagenes_reunion",
            n_frames        = len(existing_frames),
            transcript_txt  = transcript_txt,
            report_language = report_lang,
            prompt_chat1    = prompt,
            frames_chat1    = existing_frames,
            provider        = provider,
            cowork_mode     = cowork_mode,
        )
        from gui.next_steps_window import NextStepsWindow
        NextStepsWindow(self, result=result)

    # ── Open report ───────────────────────────────────────────────────────────

    def _open_report(self):
        import subprocess, platform
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return
        meeting_path = Path(meeting_folder)
        reports = sorted(meeting_path.glob("report_*.md"), reverse=True)
        if not reports:
            messagebox.showinfo("No report", f"No report_*.md found in:\n{meeting_path}")
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

    # ── Export DOCX ───────────────────────────────────────────────────────────

    def _export_docx(self):
        meeting_folder = self._var_meeting.get().strip()
        if not meeting_folder:
            messagebox.showwarning("No folder", "Please select a meeting folder first.")
            return
        meeting_path = Path(meeting_folder)
        reports = sorted(meeting_path.glob("*.md"), reverse=True)
        if not reports:
            messagebox.showinfo("No report", f"No .md files found in:\n{meeting_path}")
            return

        report = reports[0]
        if len(reports) > 1:
            report = _MdPickerDialog(self, reports).result
            if report is None:
                return

        choice = _ExportFormatDialog(self, report.name).result
        if choice is None:
            return

        self._btn_export.configure(state="disabled", text="Exporting...")
        self._analysis_running = True
        self._start_progress()
        self._append_status(f"  Exporting {report.name}...")

        threading.Thread(
            target=self._do_export,
            args=(meeting_path, choice, report),
            daemon=True,
        ).start()

    def _do_export(self, meeting_path: Path, output_format: str, report_path: Path):
        try:
            from tools.exporter import run_export
            run_export(meeting_folder=meeting_path, output_format=output_format, report_path=report_path)
            docx_files = sorted(meeting_path.glob("*.docx"), reverse=True)
            docx_path  = docx_files[0] if docx_files else None
            self.after(0, lambda: self._export_done(docx_path, output_format, meeting_path, report_path))
        except Exception as e:
            msg = str(e)
            self.after(0, lambda: (
                self._stop_progress(success=False),
                self._btn_export.configure(state="normal", text="Export DOCX"),
                self._append_status(f"  Export error: {msg}", "err"),
            ))

    def _export_done(self, docx_path, output_format: str, meeting_path: Path, report_path: Path):
        self._stop_progress(success=True)
        self._btn_export.configure(state="normal", text="Export DOCX")
        self._append_status("  Export complete!", "ok")

        if output_format in ("docx", "both") and docx_path:
            self._append_status(f"  DOCX saved: {docx_path}")
            import platform, subprocess
            if messagebox.askyesno("Export complete", f"DOCX saved:\n{docx_path}\n\nOpen the folder?"):
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer /select,"{docx_path}"')
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", "-R", str(docx_path)])
                else:
                    subprocess.Popen(["xdg-open", str(docx_path.parent)])

        # Offer to rename frames folder
        frames_dir = meeting_path / "imagenes_reunion"
        if frames_dir.exists():
            mp4_files = list(meeting_path.glob("*.mp4"))
            if mp4_files:
                new_name = f"{mp4_files[0].stem}_{report_path.stem}"
                if messagebox.askyesno("Rename frames folder?",
                                       f"From:  imagenes_reunion\nTo:    {new_name}"):
                    try:
                        frames_dir.rename(meeting_path / new_name)
                        self._append_status(f"  Renamed to: {new_name}", "ok")
                    except Exception as exc:
                        self._append_status(f"  Could not rename: {exc}", "err")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _new_project(self):
        if hasattr(self, '_project_win') and self._project_win.winfo_exists():
            self._project_win.lift()
            self._project_win.focus_force()
            return
        from gui.project_window import ProjectWindow
        self._project_win = ProjectWindow(self, global_config=self.config, on_complete=self._load_projects)

    def _open_settings(self):
        if hasattr(self, '_settings_win') and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return
        from gui.settings import SettingsWindow
        self._settings_win = SettingsWindow(self, config=self.config, on_save=self._reload_config)

    def _reload_config(self):
        from tools.installer import _load_global_config
        self.config = _load_global_config()

    def _on_close(self):
        self.master.destroy()


# ── Helper dialogs ─────────────────────────────────────────────────────────────

class _ExportFormatDialog(ctk.CTkToplevel):
    def __init__(self, parent, report_name: str):
        super().__init__(parent)
        self.title("MeetingTool - Export format")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)
        self.result = None
        self.grab_set()
        w, h = 360, 220
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(
            self, text=f"Export format for:\n{report_name}",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
            justify="left",
        ).pack(anchor="w", padx=20, pady=16)

        for label, value in [
            ("DOCX  (recommended)", "docx"),
            ("Markdown only",       "md"),
            ("Both",               "both"),
        ]:
            ctk.CTkButton(
                self, text=label, command=lambda v=value: self._choose(v),
                font=ctk.CTkFont(*FONTS["body"]),
                fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
                text_color=COLORS["text"], border_color=COLORS["border"],
                border_width=1, corner_radius=4, anchor="w",
            ).pack(fill="x", padx=20, pady=2)

        ctk.CTkButton(
            self, text="Cancel", command=self.destroy,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color="transparent", hover_color=COLORS["bg_card"],
            text_color=COLORS["text_muted"],
        ).pack(pady=(8, 0))
        self.wait_window()

    def _choose(self, value: str):
        self.result = value
        self.destroy()


class _MdPickerDialog(ctk.CTkToplevel):
    def __init__(self, parent, reports: list):
        super().__init__(parent)
        self.title("MeetingTool - Select report")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)
        self.result = None
        self.grab_set()
        h = min(160 + len(reports) * 46, 480)
        w = 440
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        ctk.CTkLabel(
            self, text="Multiple .md files found.\nSelect the one to export:",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w", padx=20, pady=16)

        for report in reports:
            ctk.CTkButton(
                self, text=report.name, command=lambda r=report: self._choose(r),
                font=ctk.CTkFont(*FONTS["body"]),
                fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
                text_color=COLORS["text"], border_color=COLORS["border"],
                border_width=1, corner_radius=4, anchor="w",
            ).pack(fill="x", padx=20, pady=2)

        ctk.CTkButton(
            self, text="Cancel", command=self.destroy,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color="transparent", hover_color=COLORS["bg_card"],
            text_color=COLORS["text_muted"],
        ).pack(pady=(8, 0))
        self.wait_window()

    def _choose(self, report: Path):
        self.result = report
        self.destroy()
