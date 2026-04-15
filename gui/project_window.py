"""
gui/project_window.py — MeetingTool v2.0
==========================================
New project wizard. Collects client/project info, writes project config,
generates prompt pack file, and shows clear next steps.
"""

import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class ProjectWindow(BaseWindow):

    def __init__(self, parent, global_config: dict, on_complete=None):
        super().__init__(parent, "New Project", width=660, height=640)
        self.global_config = global_config
        self.on_complete = on_complete
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()

    def _build(self):
        self._header(
            self, "New Client Project",
            "Set up a project to start analyzing meetings for a client."
        )

        # Scrollable content
        canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
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

        self._build_form(content)

        # Footer
        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")

        self._status = tk.Label(
            footer, text="",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], wraplength=480, justify="left"
        )
        self._status.pack(side="left", padx=PAD["window"])

        self._btn_create = self._primary_button(
            footer, "Create Project", self._run_create
        )
        self._btn_create.pack(side="right", padx=PAD["window"])

    def _build_form(self, parent):
        default_provider = self.global_config.get("llm_provider", "claude")
        default_language = self.global_config.get("default_language", "english")
        mip_root = Path(self.global_config.get("mip_root", ""))

        # ── Section 1: Client & project ──
        self._section_label(parent, "1  Client & project")

        self._var_client = self._labeled_field(
            parent, "Client name  (e.g. Kroger, Acme Corp)", ""
        )
        self._var_project = self._labeled_field(
            parent, "Project name  (e.g. RetailBeacon, Q2 Analysis)", ""
        )

        # ── Section 2: Project folder ──
        self._section_label(parent, "2  Where to save this project")

        info = tk.Frame(parent, bg=COLORS["bg_card"], padx=PAD["window"], pady=2)
        info.pack(fill="x")
        tk.Label(
            info,
            text="MeetingTool will create this folder automatically.",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg_card"],
            anchor="w"
        ).pack(anchor="w")

        default_project_path = str(mip_root / "projects" / "{Client}" / "{Project}")
        self._var_folder = self._labeled_field(
            parent, "Project folder", default_project_path,
            browse=True, browse_type="dir"
        )

        # Update folder path automatically when client/project names change
        def _update_folder(*args):
            client = self._var_client.get().strip().replace(" ", "_").replace("/", "-")
            project = self._var_project.get().strip().replace(" ", "_").replace("/", "-")
            if client and project:
                self._var_folder.set(str(mip_root / "projects" / client / project))
            elif client:
                self._var_folder.set(str(mip_root / "projects" / client / "{Project}"))

        self._var_client.trace_add("write", _update_folder)
        self._var_project.trace_add("write", _update_folder)

        # ── Section 3: AI tool ──
        self._section_label(parent, "3  AI tool for this project")

        provider_options = [
            ("claude",  "Claude (Anthropic)"),
            ("chatgpt", "ChatGPT (OpenAI)"),
            ("gemini",  "Gemini (Google)"),
        ]
        self._var_provider = self._radio_group(
            parent, "AI provider:", provider_options, default=default_provider
        )

        # Claude project reference field
        self._ref_frame = tk.Frame(parent, bg=COLORS["accent_light"],
                                   padx=PAD["window"] + 16, pady=PAD["item"])
        self._ref_frame.pack(fill="x")
        self._var_ref = self._labeled_field(
            self._ref_frame,
            "Claude Project name  (optional — for your reference)",
            ""
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        # ── Section 4: Language ──
        self._section_label(parent, "4  Report language for this project")

        lang_default = "1" if default_language == "english" else "2"
        self._var_language = self._radio_group(
            parent, "Generate reports in:",
            [("english", "English"), ("spanish", "Spanish")],
            default=default_language
        )

        # ── Section 5: Custom meeting types ──
        self._section_label(parent, "5  Custom meeting types  (optional)")

        info2 = tk.Frame(parent, bg=COLORS["bg_card"], padx=PAD["window"], pady=2)
        info2.pack(fill="x")
        tk.Label(
            info2,
            text="Base types always available: Discovery, Kickoff, Status, Technical.\n"
                 "Add custom types separated by commas  (e.g. retrospective, demo, training)",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg_card"],
            justify="left", anchor="w"
        ).pack(anchor="w")
        self._var_custom_types = self._labeled_field(parent, "Additional meeting types", "")

    def _on_provider_change(self, *args):
        if self._var_provider.get() == "claude":
            self._ref_frame.pack(fill="x")
        else:
            self._ref_frame.pack_forget()

    def _run_create(self):
        # Validate required fields
        client = self._var_client.get().strip()
        project = self._var_project.get().strip()

        if not client:
            messagebox.showwarning("Missing info", "Please enter a client name.")
            return
        if not project:
            messagebox.showwarning("Missing info", "Please enter a project name.")
            return

        self._btn_create.configure(state="disabled", text="Creating…")
        self._status.configure(text="Setting up project…", fg=COLORS["text_muted"])
        thread = threading.Thread(target=self._do_create, daemon=True)
        thread.start()

    def _do_create(self):
        try:
            import json
            from datetime import datetime
            from tools.prompt_generator import generate_prompt_pack
            from tools.project import _merge_configs, MEETING_TYPES_DEFAULT

            client  = self._var_client.get().strip()
            project = self._var_project.get().strip()
            provider = self._var_provider.get()
            language = self._var_language.get()
            provider_ref = self._var_ref.get().strip() if provider == "claude" else ""
            project_path = Path(self._var_folder.get()).expanduser().resolve()

            cowork_mode = self.global_config.get("cowork_mode", False)

            # Parse custom types
            custom_raw = self._var_custom_types.get().strip()
            custom_types = [
                t.strip().lower().replace(" ", "_")
                for t in custom_raw.split(",")
                if t.strip()
            ] if custom_raw else []

            # Create folder
            project_path.mkdir(parents=True, exist_ok=True)

            # Write project config
            project_config = {
                "client": client,
                "project": project,
                "llm_provider": provider,
                "llm_project_reference": provider_ref,
                "project_folder": str(project_path),
                "report_language": language,
                "meeting_types": MEETING_TYPES_DEFAULT,
                "custom_meeting_types": custom_types,
                "created_at": datetime.now().strftime("%Y-%m-%d"),
            }

            cfg_path = project_path / "mip.config.json"
            with open(cfg_path, "w") as f:
                json.dump(project_config, f, indent=2)

            # Generate and save prompt pack
            merged = _merge_configs(self.global_config, project_config)
            pack_content = generate_prompt_pack(merged)

            mip_root = Path(self.global_config.get("mip_root", ""))
            provider_folder = provider
            prompt_file = mip_root / "prompt_pack" / provider_folder / "project_instructions.md"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.write_text(pack_content, encoding="utf-8")

            self.after(0, lambda: self._finish_success(
                client, project, project_path, prompt_file,
                provider, cowork_mode
            ))

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda: (
                self._btn_create.configure(state="normal", text="Create Project"),
                self._status.configure(
                    text=f"Error: {error_msg}", fg=COLORS["error"]
                )
            ))

    def _finish_success(self, client, project, project_path,
                        prompt_file, provider, cowork_mode):
        self._btn_create.configure(state="normal", text="Done ✓")
        self._btn_create.configure(bg=COLORS["success"])
        self._status.configure(text="Project created!", fg=COLORS["success"])

        # Show next steps in a results window — closing it also closes this wizard
        ResultsWindow(
            self.master,
            client=client,
            project=project,
            project_path=project_path,
            prompt_file=prompt_file,
            provider=provider,
            cowork_mode=cowork_mode,
            on_close=self.destroy,
        )

        if self.on_complete:
            self.on_complete()


class ResultsWindow(BaseWindow):
    """Shows next steps after project creation."""

    def __init__(self, parent, client, project, project_path,
                 prompt_file, provider, cowork_mode, on_close=None):
        super().__init__(parent, "Project Ready", width=680, height=560)
        self._on_close = on_close
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build(client, project, project_path,
                    prompt_file, provider, cowork_mode)

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()

    def _build(self, client, project, project_path,
               prompt_file, provider, cowork_mode):

        self._header(
            self,
            f"Project ready: {client} — {project}",
            "Follow these steps before analyzing your first meeting."
        )

        content = tk.Frame(self, bg=COLORS["bg_card"])
        content.pack(fill="both", expand=True, padx=0, pady=0)

        # ── Step 1: Configure AI ──
        self._section_label(content, "Step 1 — Configure your AI tool  (once per project)")

        step1 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step1.pack(fill="x")

        if provider == "claude":
            instructions = (
                "1. Go to claude.ai → Projects → New Project\n"
                f"2. Name it:  {client} — {project}\n"
                "3. Open Project Instructions\n"
                "4. Open the file below, copy everything, and paste it into Project Instructions:"
            )
        elif provider == "chatgpt":
            instructions = (
                "At the start of each analysis session:\n"
                "Open the file below, copy everything, and paste it as\n"
                "the first message in your ChatGPT conversation:"
            )
        else:
            instructions = (
                "At the start of each analysis session:\n"
                "Open the file below, copy everything, and paste it as\n"
                "the System Instruction in Gemini Advanced:"
            )

        tk.Label(
            step1, text=instructions,
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left", anchor="w"
        ).pack(anchor="w")

        # File path — clickable to open in explorer
        file_frame = tk.Frame(step1, bg=COLORS["accent_light"], padx=8, pady=6)
        file_frame.pack(fill="x", pady=(8, 0))

        tk.Label(
            file_frame, text=str(prompt_file),
            font=FONTS["mono"], fg=COLORS["accent"], bg=COLORS["accent_light"],
            anchor="w", cursor="hand2"
        ).pack(side="left", fill="x", expand=True)

        def _open_folder():
            import subprocess, platform
            folder = prompt_file.parent
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{prompt_file}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", str(prompt_file)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])

        tk.Button(
            file_frame, text="Open folder",
            font=FONTS["small"],
            bg=COLORS["accent"], fg="#FFFFFF",
            relief="flat", cursor="hand2",
            padx=8, pady=2,
            command=_open_folder
        ).pack(side="right", padx=(8, 0))

        # ── Step 2: Add a meeting ──
        self._section_label(content, "Step 2 — Add a meeting to analyze")

        step2 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step2.pack(fill="x")

        tk.Label(
            step2,
            text="Create a subfolder inside your project folder.\n"
                 "Name it after the meeting:  MeetingName_YYYYMMDD\n"
                 "Place the Teams recording (.mp4) and transcript (.docx) inside it.",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left", anchor="w"
        ).pack(anchor="w")

        folder_frame = tk.Frame(step2, bg=COLORS["accent_light"], padx=8, pady=6)
        folder_frame.pack(fill="x", pady=(8, 0))

        tk.Label(
            folder_frame, text=str(project_path),
            font=FONTS["mono"], fg=COLORS["accent"], bg=COLORS["accent_light"],
            anchor="w"
        ).pack(side="left", fill="x", expand=True)

        def _open_project():
            import subprocess, platform
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{project_path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(project_path)])
            else:
                subprocess.Popen(["xdg-open", str(project_path)])

        tk.Button(
            folder_frame, text="Open folder",
            font=FONTS["small"],
            bg=COLORS["accent"], fg="#FFFFFF",
            relief="flat", cursor="hand2",
            padx=8, pady=2,
            command=_open_project
        ).pack(side="right", padx=(8, 0))

        # ── Step 3: Process ──
        self._section_label(content, "Step 3 — Process the meeting")

        step3 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step3.pack(fill="x")

        if cowork_mode:
            run_instruction = (
                "Open MeetingTool, select your meeting folder, and click Analyze.\n"
                "Cowork will extract frames and generate the report automatically."
            )
        else:
            run_instruction = (
                "Open MeetingTool, select your meeting folder, and click Analyze.\n"
                "MeetingTool will prepare the files and tell you what to upload\n"
                "to your AI chat to generate the report."
            )

        tk.Label(
            step3, text=run_instruction,
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left", anchor="w"
        ).pack(anchor="w")

        # ── Footer ──
        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")

        self._primary_button(
            footer, "Got it — open MeetingTool", self._close
        ).pack(side="right", padx=PAD["window"])
