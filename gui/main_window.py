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
from tkinter import messagebox, filedialog

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

        # Analyze button
        self._btn_analyze = self._primary_button(
            right, "▶  Analyze Meeting", self._run_analysis, width=22
        )
        self._btn_analyze.pack(anchor="w", pady=(8, 12))

        # Status area — plain text, no black box
        tk.Label(
            right, text="Status",
            font=FONTS["heading"], fg=COLORS["text"], bg=COLORS["bg"]
        ).pack(anchor="w", pady=(0, 4))

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

    def _browse_meeting(self):
        mip_root = self.config.get("mip_root", str(Path.home()))
        path = filedialog.askdirectory(
            title="Select meeting folder",
            initialdir=mip_root
        )
        if path:
            self._var_meeting.set(path)

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

        self._btn_analyze.configure(state="disabled", text="Analyzing…")
        self._append_status(f"Starting analysis: {meeting_path.name}")

        mode = self._var_mode.get()
        thread = threading.Thread(
            target=self._do_analysis,
            args=(meeting_path, mode),
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

    def _do_analysis(self, meeting_path: Path, mode: str):
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

            run_meeting(
                meeting_folder=meeting_path,
                web_mode=web_mode,
                two_pass=two_pass,
                single_pass=False,
                max_frames_override=None,
            )

            self.after(0, lambda: self._analysis_done(meeting_path, web_mode))

        except SystemExit:
            self.after(0, lambda: self._analysis_error("Analysis stopped — check the output above."))
        except Exception as e:
            self.after(0, lambda: self._analysis_error(str(e)))
        finally:
            logger.removeHandler(handler)

    def _analysis_done(self, meeting_path: Path, web_mode: bool):
        self._btn_analyze.configure(state="normal", text="▶  Analyze Meeting")
        self._append_status("")
        self._append_status("  Analysis complete!", "ok")

        if not web_mode:
            self._append_status(
                f"  Cowork can now read the files in:\n  {meeting_path}", "ok"
            )
        else:
            self._append_status(
                "  Upload the files listed above to your AI chat,\n"
                "  then paste the prompt pack to generate the report.",
                "ok"
            )

    def _analysis_error(self, msg: str):
        self._btn_analyze.configure(state="normal", text="▶  Analyze Meeting")
        self._append_status(f"  Error: {msg}", "err")

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


class SettingsWindow(BaseWindow):
    """Simple settings window to update global config."""

    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent, "Settings", width=540, height=480)
        self.config = config
        self.on_save = on_save
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()

    def _build(self):
        self._header(self, "Settings", "Update your MeetingTool preferences.")

        # Scrollable content
        canvas = tk.Canvas(self, bg=COLORS["bg_card"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["bg_card"])
        content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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

        self._section_label(content, "Default report language")
        self._var_language = self._radio_group(
            content, "",
            [("english", "English"), ("spanish", "Spanish")],
            default=self.config.get("default_language", "english")
        )

        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")

        self._secondary_button(footer, "Cancel", self.destroy).pack(
            side="right", padx=8
        )
        self._primary_button(footer, "Save", self._save).pack(
            side="right", padx=(PAD["window"], 0)
        )

    def _save(self):
        from tools.installer import _write_global_config
        updated = {
            **self.config,
            "mip_root": self._var_root.get(),
            "llm_provider": self._var_provider.get(),
            "default_language": self._var_language.get(),
        }
        _write_global_config(updated)
        if self.on_save:
            self.on_save()
        messagebox.showinfo("Saved", "Settings saved successfully.")
        self.destroy()
