"""
gui/next_steps_window.py - MeetingTool v2.5
Shown after extraction completes. Gives clear next steps.
CustomTkinter dark mode.
"""

import subprocess
import platform
import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path

from gui.styles import BaseWindow, COLORS, FONTS, PAD


PROVIDER_URLS = {
    "claude":  "https://claude.ai/new",
    "chatgpt": "https://chat.openai.com/",
    "gemini":  "https://gemini.google.com/app",
}

PROVIDER_NAMES = {
    "claude":  "Claude",
    "chatgpt": "ChatGPT",
    "gemini":  "Gemini",
}


def _copy_to_clipboard(widget, text: str):
    widget.clipboard_clear()
    widget.clipboard_append(text)
    widget.update()


def _open_browser(url: str):
    import webbrowser
    webbrowser.open(url)


def _open_claude_desktop():
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["start", "claude://"], shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Claude"])
        else:
            subprocess.Popen(["xdg-open", "claude://"])
    except Exception:
        messagebox.showinfo("Open Claude Desktop", "Please open Claude Desktop manually.")


class NextStepsWindow(BaseWindow):

    def __init__(self, parent, result):
        super().__init__(parent, "Next Steps", width=720, height=600)
        self.result = result
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        if result.workflow == "cowork":
            self._build_cowork()
        elif result.workflow == "web":
            self._build_web_standard()
        elif result.workflow == "two_pass":
            self._build_two_pass()

    # ── Cowork flow ───────────────────────────────────────────────────────────

    def _build_cowork(self):
        r = self.result
        self._header(
            self,
            "Files ready -- follow these steps in Cowork",
            f"{r.n_frames} frames extracted  |  transcript parsed  |  prompt ready"
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        self._section_label(scroll, "What MeetingTool prepared")
        info = ctk.CTkFrame(scroll, fg_color="transparent")
        info.pack(fill="x", padx=PAD["window"], pady=8)

        items = [
            ("imagenes_reunion\\", f"{r.n_frames} frames selected from the recording"),
            (r.transcript_txt.name if r.transcript_txt else "--", "Clean transcript text"),
        ]
        for filename, desc in items:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text="  ok", font=ctk.CTkFont(*FONTS["body"]),
                         text_color=COLORS["success"], fg_color="transparent").pack(side="left")
            ctk.CTkLabel(row, text=f"  {filename}", font=ctk.CTkFont(*FONTS["mono"]),
                         text_color=COLORS["accent"], fg_color="transparent").pack(side="left")
            ctk.CTkLabel(row, text=f"  -- {desc}", font=ctk.CTkFont(*FONTS["small"]),
                         text_color=COLORS["text_muted"], fg_color="transparent").pack(side="left")

        self._section_label(scroll, "Step 1 -- Open Claude Desktop and go to the Cowork tab")
        step1 = ctk.CTkFrame(scroll, fg_color="transparent")
        step1.pack(fill="x", padx=PAD["window"], pady=8)
        self._secondary_button(step1, "Open Claude Desktop", _open_claude_desktop, width=180).pack(anchor="w")

        self._section_label(scroll, "Step 2 -- Point Cowork to the meeting folder")
        step2 = ctk.CTkFrame(scroll, fg_color="transparent")
        step2.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step2,
            text='Click the folder selector in Cowork and navigate to this folder:',
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w", pady=(0, 6))

        folder_frame = ctk.CTkFrame(step2, fg_color=COLORS["accent_light"], corner_radius=4)
        folder_frame.pack(fill="x")
        folder_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            folder_frame, text=str(r.meeting_folder),
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).grid(row=0, column=0, padx=10, pady=6, sticky="ew")

        ctk.CTkButton(
            folder_frame, text="Copy path",
            command=lambda: _copy_to_clipboard(self, str(r.meeting_folder)),
            font=ctk.CTkFont(*FONTS["small"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", width=80, height=28, corner_radius=4,
        ).grid(row=0, column=1, padx=(4, 8), pady=4)

        self._secondary_button(
            step2, "Open meeting folder", self._open_folder, width=160
        ).pack(anchor="w", pady=(8, 0))

        self._section_label(scroll, "Step 3 -- Paste the prompt in the Cowork chat and send")
        step3 = ctk.CTkFrame(scroll, fg_color="transparent")
        step3.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step3,
            text="Start a new Cowork chat. Copy the prompt below and paste it in the chat.",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w", pady=(0, 8))

        self._copy_btn = self._primary_button(
            step3, "Copy prompt to clipboard", self._copy_cowork_prompt, width=200
        )
        self._copy_btn.pack(anchor="w")

        self._lbl_copied = ctk.CTkLabel(
            step3, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["success"], fg_color="transparent",
        )
        self._lbl_copied.pack(anchor="w", pady=(4, 0))

        self._section_label(scroll, "Step 4 -- After Cowork generates the report")
        step4 = ctk.CTkFrame(scroll, fg_color="transparent")
        step4.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step4,
            text="Cowork will read the frames and transcript from the folder\n"
                 "and generate report.md automatically.\n\n"
                 "Come back to MeetingTool and use:\n"
                 "  Open report    -- to read and review the report\n"
                 "  Export DOCX    -- when ready for client delivery",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w")

        self._footer_done()

    def _copy_cowork_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"], text="Copied"
        )
        self._lbl_copied.configure(
            text="Prompt is in your clipboard. Switch to Cowork and paste (Ctrl+V)."
        )

    # ── Web standard flow ─────────────────────────────────────────────────────

    def _build_web_standard(self):
        r             = self.result
        provider      = r.provider
        provider_name = PROVIDER_NAMES.get(provider, provider.title())
        provider_url  = PROVIDER_URLS.get(provider, "https://claude.ai/new")

        self._header(
            self,
            f"Upload files to {provider_name} to generate the report",
            f"{r.n_frames} frames selected  |  transcript ready  |  prompt ready"
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        self._section_label(scroll, f"Step 1 -- Open {provider_name} in your browser")
        step1 = ctk.CTkFrame(scroll, fg_color="transparent")
        step1.pack(fill="x", padx=PAD["window"], pady=8)
        btn_row1 = ctk.CTkFrame(step1, fg_color="transparent")
        btn_row1.pack(anchor="w")
        self._primary_button(
            btn_row1, f"Open {provider_name}",
            lambda: _open_browser(provider_url), width=150
        ).pack(side="left", padx=(0, 8))
        self._secondary_button(
            btn_row1, "Open meeting folder", self._open_folder, width=160
        ).pack(side="left")

        self._section_label(scroll, "Step 2 -- Upload these files to the chat")
        step2 = ctk.CTkFrame(scroll, fg_color="transparent")
        step2.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step2, text="Drag these files into the chat or use the attach button:",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w", pady=(0, 8))

        files_box = ctk.CTkFrame(step2, fg_color=COLORS["accent_light"], corner_radius=4)
        files_box.pack(fill="x")

        if r.transcript_txt:
            self._file_row(files_box, r.transcript_txt, "Transcript (text)")
        for fp in r.frames_chat1:
            self._file_row(files_box, fp, "Frame")

        self._section_label(scroll, "Step 3 -- Copy the prompt and paste it in the chat")
        step3 = ctk.CTkFrame(scroll, fg_color="transparent")
        step3.pack(fill="x", padx=PAD["window"], pady=8)

        self._copy_btn = self._primary_button(
            step3, "Copy prompt to clipboard", self._copy_web_prompt, width=200
        )
        self._copy_btn.pack(anchor="w")

        self._lbl_copied = ctk.CTkLabel(
            step3, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["success"], fg_color="transparent",
        )
        self._lbl_copied.pack(anchor="w", pady=(4, 0))

        self._section_label(scroll, "Step 4 -- Save the generated report")
        step4 = ctk.CTkFrame(scroll, fg_color="transparent")
        step4.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            step4,
            text=f"When {provider_name} generates the report, copy the full Markdown text\n"
                 f"and save it as:  report_{self._today()}.md\n"
                 f"in the meeting folder:\n",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", justify="left",
        ).pack(anchor="w")

        ctk.CTkLabel(
            step4, text=str(r.meeting_folder),
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            step4,
            text="\nThen come back and use Open report and Export DOCX.",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", justify="left",
        ).pack(anchor="w")

        self._footer_done()

    def _copy_web_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"], text="Copied"
        )
        self._lbl_copied.configure(
            text="Prompt copied. Paste it in the chat after uploading the files."
        )

    # ── Two-pass flow ─────────────────────────────────────────────────────────

    def _build_two_pass(self):
        r             = self.result
        provider_name = PROVIDER_NAMES.get(r.provider, r.provider.title())
        provider_url  = PROVIDER_URLS.get(r.provider, "https://claude.ai/new")

        self._header(
            self,
            "Two-pass analysis -- two separate chats",
            f"{r.n_frames} frames total  |  split in two halves  |  {provider_name}"
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        # Chat 1
        self._section_label(scroll, "Chat 1 -- First half of the meeting")
        c1 = ctk.CTkFrame(scroll, fg_color="transparent")
        c1.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            c1, text="Upload these files to a NEW chat:",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
        ).pack(anchor="w", pady=(0, 6))

        f1 = ctk.CTkFrame(c1, fg_color=COLORS["accent_light"], corner_radius=4)
        f1.pack(fill="x")

        if r.transcript_txt:
            half1 = r.meeting_folder / f"{r.transcript_txt.stem}_half1.txt"
            if half1.exists():
                self._file_row(f1, half1, "Transcript -- first half")

        for fp in r.frames_chat1:
            self._file_row(f1, fp, "Frame")

        btn_row1 = ctk.CTkFrame(c1, fg_color="transparent")
        btn_row1.pack(anchor="w", pady=(8, 0))

        self._primary_button(
            btn_row1, f"Open {provider_name} (Chat 1)",
            lambda: _open_browser(provider_url), width=200
        ).pack(side="left", padx=(0, 8))

        self._copy_btn1 = self._secondary_button(
            btn_row1, "Copy Chat 1 prompt", self._copy_chat1_prompt, width=150
        )
        self._copy_btn1.pack(side="left")

        self._lbl_copied1 = ctk.CTkLabel(
            c1, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["success"], fg_color="transparent",
        )
        self._lbl_copied1.pack(anchor="w", pady=(4, 0))

        ctk.CTkLabel(
            c1,
            text="At the end of Chat 1, the LLM will generate a handoff JSON block.\n"
                 "Copy it and save it as:  " + str(r.handoff_path or "handoff.json"),
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent", justify="left",
        ).pack(anchor="w", pady=(8, 0))

        # Chat 2
        self._section_label(scroll, "Chat 2 -- Second half + merge")
        c2 = ctk.CTkFrame(scroll, fg_color="transparent")
        c2.pack(fill="x", padx=PAD["window"], pady=8)

        ctk.CTkLabel(
            c2, text="Upload these files to a NEW chat (separate from Chat 1):",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent",
        ).pack(anchor="w", pady=(0, 6))

        f2 = ctk.CTkFrame(c2, fg_color=COLORS["accent_light"], corner_radius=4)
        f2.pack(fill="x")

        if r.handoff_path:
            ctk.CTkLabel(
                f2,
                text=f"  handoff_{self._today()}.json  -- saved after Chat 1",
                font=ctk.CTkFont(*FONTS["mono"]),
                text_color=COLORS["text_muted"], fg_color="transparent",
            ).pack(anchor="w", padx=8, pady=1)

        if r.transcript_txt:
            half2 = r.meeting_folder / f"{r.transcript_txt.stem}_half2.txt"
            if half2.exists():
                self._file_row(f2, half2, "Transcript -- second half")

        for fp in r.frames_chat2:
            self._file_row(f2, fp, "Frame")

        btn_row2 = ctk.CTkFrame(c2, fg_color="transparent")
        btn_row2.pack(anchor="w", pady=(8, 0))

        self._primary_button(
            btn_row2, f"Open {provider_name} (Chat 2)",
            lambda: _open_browser(provider_url), width=200
        ).pack(side="left", padx=(0, 8))

        self._copy_btn2 = self._secondary_button(
            btn_row2, "Copy Chat 2 prompt", self._copy_chat2_prompt, width=150
        )
        self._copy_btn2.pack(side="left")

        self._lbl_copied2 = ctk.CTkLabel(
            c2, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["success"], fg_color="transparent",
        )
        self._lbl_copied2.pack(anchor="w", pady=(4, 0))

        self._footer_done()

    def _copy_chat1_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn1.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"], text="Copied"
        )
        self._lbl_copied1.configure(text="Chat 1 prompt copied.")

    def _copy_chat2_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat2)
        self._copy_btn2.configure(
            fg_color=COLORS["success"], hover_color=COLORS["step_done"], text="Copied"
        )
        self._lbl_copied2.configure(text="Chat 2 prompt copied.")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _file_row(self, parent, file_path: Path, label: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=1)
        ctk.CTkLabel(
            row, text=f"  {file_path.name}",
            font=ctk.CTkFont(*FONTS["mono"]),
            text_color=COLORS["accent"], fg_color="transparent",
        ).pack(side="left")
        ctk.CTkLabel(
            row, text=f"  ({label})",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
        ).pack(side="left")

    def _open_folder(self):
        folder = self.result.meeting_folder
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(["explorer", str(folder)])
            elif system == "Darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            pass

    def _footer_done(self):
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1, corner_radius=0).pack(
            fill="x", side="bottom"
        )
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        footer.pack(fill="x", side="bottom", pady=12)
        self._primary_button(footer, "Done", self.destroy, width=100).pack(
            side="right", padx=PAD["window"]
        )

    def _today(self) -> str:
        from datetime import date
        return date.today().strftime("%Y%m%d")
