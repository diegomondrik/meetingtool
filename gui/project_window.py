"""
gui/project_window.py - MeetingTool v2.5
New project wizard. CustomTkinter dark mode.
"""

import threading
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class ProjectWindow(BaseWindow):

    def __init__(self, parent, global_config: dict, on_complete=None):
        super().__init__(parent, "New Project", width=680, height=660)
        self.global_config = global_config
        self.on_complete   = on_complete
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()

    def _build(self):
        self._header(
            self, "New Client Project",
            "Set up a project to start analyzing meetings for a client."
        )

        # Footer
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

        self._btn_create = self._primary_button(
            footer, "Create Project", self._run_create, width=140
        )
        self._btn_create.pack(side="right", padx=PAD["window"])

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)
        self._build_form(scroll)

    def _build_form(self, parent):
        default_provider = self.global_config.get("llm_provider", "claude")
        default_language = self.global_config.get("default_language", "english")
        mip_root         = Path(self.global_config.get("mip_root", ""))

        self._section_label(parent, "1  Client & project")
        self._var_client  = self._labeled_field(parent, "Client name  (e.g. Kroger)", "")
        self._var_project = self._labeled_field(parent, "Project name  (e.g. RetailBeacon)", "")

        self._section_label(parent, "2  Where to save this project")

        info = ctk.CTkFrame(parent, fg_color="transparent")
        info.pack(fill="x", padx=PAD["window"], pady=(4, 0))
        ctk.CTkLabel(
            info, text="MeetingTool will create this folder automatically.",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", anchor="w",
        ).pack(anchor="w")

        self._var_folder = self._labeled_field(
            parent, "Project folder",
            str(mip_root / "projects" / "{Client}" / "{Project}"),
            browse=True, browse_type="dir",
        )

        def _update_folder(*args):
            client  = self._var_client.get().strip().replace(" ", "_").replace("/", "-")
            project = self._var_project.get().strip().replace(" ", "_").replace("/", "-")
            if client and project:
                self._var_folder.set(str(mip_root / "projects" / client / project))
            elif client:
                self._var_folder.set(str(mip_root / "projects" / client / "{Project}"))

        self._var_client.trace_add("write", _update_folder)
        self._var_project.trace_add("write", _update_folder)

        self._section_label(parent, "3  AI tool for this project")
        self._var_provider = self._radio_group(
            parent, "AI provider:",
            [("claude", "Claude (Anthropic)"), ("chatgpt", "ChatGPT (OpenAI)"), ("gemini", "Gemini (Google)")],
            default=default_provider,
        )

        # Claude project reference (hidden for other providers)
        self._ref_frame = ctk.CTkFrame(parent, fg_color=COLORS["accent_light"], corner_radius=0)
        self._ref_frame.pack(fill="x")
        self._var_ref = self._labeled_field(
            self._ref_frame,
            "Claude Project name  (optional -- for your reference)", ""
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        self._section_label(parent, "4  Report language for this project")
        self._var_language = self._radio_group(
            parent, "Generate reports in:",
            [("english", "English"), ("spanish", "Spanish")],
            default=default_language,
        )

        self._section_label(parent, "5  Custom meeting types  (optional)")

        info2 = ctk.CTkFrame(parent, fg_color="transparent")
        info2.pack(fill="x", padx=PAD["window"], pady=(4, 0))
        ctk.CTkLabel(
            info2,
            text="Base types always available: Discovery, Kickoff, Status, Technical.\n"
                 "Add custom types separated by commas  (e.g. retrospective, demo)",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
            justify="left", anchor="w",
        ).pack(anchor="w")
        self._var_custom_types = self._labeled_field(parent, "Additional meeting types", "")

    def _on_provider_change(self, *args):
        if self._var_provider.get() == "claude":
            self._ref_frame.pack(fill="x")
        else:
            self._ref_frame.pack_forget()

    def _run_create(self):
        client  = self._var_client.get().strip()
        project = self._var_project.get().strip()
        if not client:
            messagebox.showwarning("Missing info", "Please enter a client name.")
            return
        if not project:
            messagebox.showwarning("Missing info", "Please enter a project name.")
            return

        provider     = self._var_provider.get()
        language     = self._var_language.get()
        provider_ref = self._var_ref.get().strip() if provider == "claude" else ""
        folder_str   = self._var_folder.get()
        custom_raw   = self._var_custom_types.get().strip()

        self._btn_create.configure(state="disabled", text="Creating...")
        self._status.configure(text="Setting up project...", text_color=COLORS["text_muted"])

        params = dict(
            client=client, project=project, provider=provider,
            language=language, provider_ref=provider_ref,
            folder_str=folder_str, custom_raw=custom_raw,
        )
        threading.Thread(target=self._do_create, args=(params,), daemon=True).start()

    def _do_create(self, params: dict):
        import json
        from datetime import datetime
        from tools.prompt_generator import generate_prompt_pack
        from tools.project import _merge_configs, MEETING_TYPES_DEFAULT

        try:
            client       = params["client"]
            project      = params["project"]
            provider     = params["provider"]
            language     = params["language"]
            provider_ref = params["provider_ref"]
            project_path = Path(params["folder_str"]).expanduser().resolve()
            custom_raw   = params["custom_raw"]
            cowork_mode  = self.global_config.get("cowork_mode", False)

            custom_types = [
                t.strip().lower().replace(" ", "_")
                for t in custom_raw.split(",")
                if t.strip()
            ] if custom_raw else []

            project_path.mkdir(parents=True, exist_ok=True)

            project_config = {
                "client":                 client,
                "project":                project,
                "llm_provider":           provider,
                "llm_project_reference":  provider_ref,
                "project_folder":         str(project_path),
                "report_language":        language,
                "meeting_types":          MEETING_TYPES_DEFAULT,
                "custom_meeting_types":   custom_types,
                "created_at":             datetime.now().strftime("%Y-%m-%d"),
            }

            with open(project_path / "mip.config.json", "w") as f:
                json.dump(project_config, f, indent=2)

            merged      = _merge_configs(self.global_config, project_config)
            pack_content = generate_prompt_pack(merged)

            mip_root    = Path(self.global_config.get("mip_root", ""))
            prompt_file = mip_root / "prompt_pack" / provider / "project_instructions.md"
            prompt_file.parent.mkdir(parents=True, exist_ok=True)
            prompt_file.write_text(pack_content, encoding="utf-8")

            self.after(0, lambda: self._finish_success(
                client, project, project_path, prompt_file, provider, cowork_mode
            ))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: (
                self._btn_create.configure(state="normal", text="Create Project"),
                self._status.configure(text=f"Error: {err}", text_color=COLORS["error"]),
            ))

    def _finish_success(self, client, project, project_path, prompt_file, provider, cowork_mode):
        self._btn_create.configure(state="normal", text="Done")
        self._btn_create.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"]
        )
        self._status.configure(text="Project created!", text_color=COLORS["success"])

        ResultsWindow(
            self,
            client=client, project=project,
            project_path=project_path, prompt_file=prompt_file,
            provider=provider, cowork_mode=cowork_mode,
            on_close=self.destroy,
        )
        if self.on_complete:
            self.on_complete()


class ResultsWindow(BaseWindow):
    """Shows next steps after project creation."""

    def __init__(self, parent, client, project, project_path,
                 prompt_file, provider, cowork_mode, on_close=None):
        super().__init__(parent, "Project Ready", width=700, height=580)
        self._on_close = on_close
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build(client, project, project_path, prompt_file, provider, cowork_mode)

    def _close(self):
        if self._on_close:
            self._on_close()
        self.destroy()

    def _build(self, client, project, project_path, prompt_file, provider, cowork_mode):
        self._header(
            self,
            f"Project ready: {client} -- {project}",
            "Follow these steps before analyzing your first meeting."
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        # Step 1 -- configure AI
        self._section_label(scroll, "Step 1 -- Configure your AI tool  (once per project)")

        step1 = ctk.CTkFrame(scroll, fg_color="transparent")
        step1.pack(fill="x", padx=PAD["window"], pady=8)

        if provider == "claude":
            instructions = (
                f"1. Go to claude.ai > Projects > New Project\n"
                f"2. Name it:  {client} -- {project}\n"
                "3. Open Project Instructions\n"
                "4. Open the file below, copy everything, and paste into Project Instructions:"
            )
        elif provider == "chatgpt":
            instructions = (
                "At the start of each session:\n"
                "Open the file below, copy everything, and paste as the first message."
            )
        else:
            instructions = (
                "At the start of each session:\n"
                "Open the file below, copy everything, and paste as the System Instruction."
            )

        ctk.CTkLabel(
            step1, text=instructions,
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
            justify="left", anchor="w",
        ).pack(anchor="w")

        file_frame = ctk.CTkFrame(step1, fg_color=COLORS["accent_light"], corner_radius=4)
        file_frame.pack(fill="x", pady=(8, 0))
        file_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            file_frame, text=str(prompt_file),
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).grid(row=0, column=0, padx=10, pady=6, sticky="ew")

        def _open_folder():
            import subprocess, platform
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer /select,"{prompt_file}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", "-R", str(prompt_file)])
            else:
                subprocess.Popen(["xdg-open", str(prompt_file.parent)])

        ctk.CTkButton(
            file_frame, text="Open folder", command=_open_folder,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", width=90, height=28, corner_radius=4,
        ).grid(row=0, column=1, padx=(4, 8), pady=4)

        # Step 2 -- add a meeting
        self._section_label(scroll, "Step 2 -- Add a meeting to analyze")

        step2 = ctk.CTkFrame(scroll, fg_color="transparent")
        step2.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step2,
            text="Create a subfolder inside your project folder.\n"
                 "Name it:  MeetingName_YYYYMMDD\n"
                 "Place the Teams recording (.mp4) and transcript (.docx) inside it.",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
            justify="left", anchor="w",
        ).pack(anchor="w")

        folder_frame = ctk.CTkFrame(step2, fg_color=COLORS["accent_light"], corner_radius=4)
        folder_frame.pack(fill="x", pady=(8, 0))
        folder_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            folder_frame, text=str(project_path),
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).grid(row=0, column=0, padx=10, pady=6, sticky="ew")

        def _open_project():
            import subprocess, platform
            if platform.system() == "Windows":
                subprocess.Popen(f'explorer "{project_path}"')
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(project_path)])
            else:
                subprocess.Popen(["xdg-open", str(project_path)])

        ctk.CTkButton(
            folder_frame, text="Open folder", command=_open_project,
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", width=90, height=28, corner_radius=4,
        ).grid(row=0, column=1, padx=(4, 8), pady=4)

        # Step 3 -- process
        self._section_label(scroll, "Step 3 -- Process the meeting")

        step3 = ctk.CTkFrame(scroll, fg_color="transparent")
        step3.pack(fill="x", padx=PAD["window"], pady=8)

        if cowork_mode:
            run_instruction = (
                "Open MeetingTool, select your meeting folder, and click Analyze.\n"
                "Cowork will extract frames and generate the report automatically."
            )
        else:
            run_instruction = (
                "Open MeetingTool, select your meeting folder, and click Analyze.\n"
                "MeetingTool will prepare the files and guide you through the next steps."
            )

        ctk.CTkLabel(
            step3, text=run_instruction,
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
            justify="left", anchor="w",
        ).pack(anchor="w")

        # Footer
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1, corner_radius=0).pack(
            fill="x", side="bottom"
        )
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        footer.pack(fill="x", side="bottom", pady=12)
        self._primary_button(footer, "Got it -- open MeetingTool", self._close, width=190).pack(
            side="right", padx=PAD["window"]
        )
