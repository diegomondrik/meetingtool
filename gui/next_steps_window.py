"""
gui/next_steps_window.py — MeetingTool v2.0
=============================================
Shown after extraction completes. Gives the user clear next steps:
  - Cowork: copies prompt to clipboard, offers to open Claude Desktop
  - Web: shows upload checklist, copies prompt to clipboard,
         offers to open the correct LLM in the browser
  - Two-pass: step-by-step Chat 1 → handoff → Chat 2 flow
"""

import subprocess
import platform
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from gui.styles import BaseWindow, COLORS, FONTS, PAD


# ── Provider browser URLs ─────────────────────────────────────────────────────

PROVIDER_URLS = {
    "claude":   "https://claude.ai/new",
    "chatgpt":  "https://chat.openai.com/",
    "gemini":   "https://gemini.google.com/app",
}

PROVIDER_NAMES = {
    "claude":   "Claude",
    "chatgpt":  "ChatGPT",
    "gemini":   "Gemini",
}


# ── Clipboard helper ──────────────────────────────────────────────────────────

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
        messagebox.showinfo(
            "Open Claude Desktop",
            "Please open Claude Desktop manually and switch to Cowork."
        )


# ── Main next steps window ────────────────────────────────────────────────────

class NextStepsWindow(BaseWindow):

    def __init__(self, parent, result):
        """
        result: AnalysisResult from runner.py
        """
        super().__init__(parent, "Next Steps", width=700, height=580)
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
            "Files ready — follow these steps in Cowork",
            f"{r.n_frames} frames extracted  ·  transcript parsed  ·  prompt ready"
        )

        content = tk.Frame(self, bg=COLORS["bg_card"])
        content.pack(fill="both", expand=True)

        # ── What was prepared ──
        self._section_label(content, "What MeetingTool prepared")

        info = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        info.pack(fill="x")

        items = [
            ("imagenes_reunion\\", f"{r.n_frames} frames selected from the recording"),
            (r.transcript_txt.name if r.transcript_txt else "—", "Clean transcript text"),
        ]
        for filename, desc in items:
            row = tk.Frame(info, bg=COLORS["bg_card"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text="  ✓", font=FONTS["body"],
                     fg=COLORS["success"], bg=COLORS["bg_card"]).pack(side="left")
            tk.Label(row, text=f"  {filename}", font=FONTS["mono"],
                     fg=COLORS["accent"], bg=COLORS["bg_card"]).pack(side="left")
            tk.Label(row, text=f"  — {desc}", font=FONTS["small"],
                     fg=COLORS["text_muted"], bg=COLORS["bg_card"]).pack(side="left")

        # ── Step 1 ──
        self._section_label(content, "Step 1 — Open Claude Desktop and go to the Cowork tab")

        step1 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step1.pack(fill="x")

        self._secondary_button(
            step1, "Open Claude Desktop", _open_claude_desktop, width=20
        ).pack(anchor="w")

        # ── Step 2 ──
        self._section_label(content, "Step 2 — Point Cowork to the meeting folder")

        step2 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step2.pack(fill="x")

        tk.Label(
            step2,
            text='Click the folder selector below the Cowork chat input\n'
                 '(the button that says "Work in a project" or shows a folder icon).\n'
                 'Navigate to and select this folder:',
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w", pady=(0, 6))

        folder_frame = tk.Frame(step2, bg=COLORS["accent_light"], padx=10, pady=8)
        folder_frame.pack(fill="x")

        tk.Label(
            folder_frame,
            text=str(r.meeting_folder),
            font=FONTS["mono"], fg=COLORS["accent"], bg=COLORS["accent_light"]
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            folder_frame, text="Copy path",
            font=FONTS["small"],
            bg=COLORS["accent"], fg="#FFFFFF",
            relief="flat", cursor="hand2",
            padx=8, pady=2,
            command=lambda: _copy_to_clipboard(self, str(r.meeting_folder))
        ).pack(side="right", padx=(8, 0))

        self._secondary_button(
            step2, "Open meeting folder", self._open_folder, width=18
        ).pack(anchor="w", pady=(8, 0))

        # ── Step 3 ──
        self._section_label(content, "Step 3 — Paste the prompt in the Cowork chat and send")

        step3 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step3.pack(fill="x")

        tk.Label(
            step3,
            text="Start a new Cowork chat (or use an existing one).\n"
                 "Click below to copy the analysis prompt, then paste it\n"
                 "into the Cowork chat input and press Enter.",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w", pady=(0, 8))

        self._copy_btn = self._primary_button(
            step3, "Copy prompt to clipboard", self._copy_cowork_prompt, width=24
        )
        self._copy_btn.pack(anchor="w")

        self._lbl_copied = tk.Label(
            step3, text="",
            font=FONTS["small"], fg=COLORS["success"], bg=COLORS["bg_card"]
        )
        self._lbl_copied.pack(anchor="w", pady=(4, 0))

        # ── Step 4 ──
        self._section_label(content, "Step 4 — After Cowork generates the report")

        step4 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step4.pack(fill="x")

        tk.Label(
            step4,
            text="Cowork will read the frames and transcript from the folder\n"
                 "and generate report.md automatically.\n\n"
                 "Come back to MeetingTool and use:\n"
                 "  Open report.md  — to read and review the report\n"
                 "  Export to DOCX  — when ready for client delivery",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w")

        # Footer
        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")
        self._primary_button(footer, "Done", self.destroy, width=10).pack(
            side="right", padx=PAD["window"]
        )

    def _copy_cowork_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn.configure(bg=COLORS["success"], text="Copied ✓")
        self._lbl_copied.configure(
            text="Prompt is in your clipboard. Switch to Cowork and paste (Ctrl+V)."
        )

    # ── Web standard flow ─────────────────────────────────────────────────────

    def _build_web_standard(self):
        r = self.result
        provider      = r.provider
        provider_name = PROVIDER_NAMES.get(provider, provider.title())
        provider_url  = PROVIDER_URLS.get(provider, "https://claude.ai/new")

        self._header(
            self,
            f"Upload files to {provider_name} to generate the report",
            f"{r.n_frames} frames selected  ·  transcript ready  ·  prompt ready"
        )

        # Scrollable content
        canvas = tk.Canvas(self, bg=COLORS["bg_card"], highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["bg_card"])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # ── Step 1: Open LLM ──
        self._section_label(content, f"Step 1 — Open {provider_name} in your browser")

        step1 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step1.pack(fill="x")

        btn_row1 = tk.Frame(step1, bg=COLORS["bg_card"])
        btn_row1.pack(anchor="w")

        self._primary_button(
            btn_row1, f"Open {provider_name}",
            lambda: _open_browser(provider_url), width=18
        ).pack(side="left", padx=(0, 8))

        self._secondary_button(
            btn_row1, "Open meeting folder", self._open_folder, width=18
        ).pack(side="left")

        # ── Step 2: Upload files ──
        self._section_label(content, "Step 2 — Upload these files to the chat")

        step2 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step2.pack(fill="x")

        tk.Label(
            step2,
            text="Upload all of these files by dragging them into the chat or using the attach button:",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w", pady=(0, 8))

        files_frame = tk.Frame(step2, bg=COLORS["accent_light"], padx=10, pady=8)
        files_frame.pack(fill="x")

        # Transcript
        if r.transcript_txt:
            self._file_row(files_frame, r.transcript_txt, "Transcript (text)")

        # Frames
        for fp in r.frames_chat1:
            self._file_row(files_frame, fp, "Frame")

        # ── Step 3: Paste prompt ──
        self._section_label(content, "Step 3 — Copy the prompt and paste it in the chat")

        step3 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step3.pack(fill="x")

        self._copy_btn = self._primary_button(
            step3, "Copy prompt to clipboard", self._copy_web_prompt, width=24
        )
        self._copy_btn.pack(anchor="w")

        self._lbl_copied = tk.Label(
            step3, text="",
            font=FONTS["small"], fg=COLORS["success"], bg=COLORS["bg_card"]
        )
        self._lbl_copied.pack(anchor="w", pady=(4, 0))

        # ── Step 4: Save report ──
        self._section_label(content, "Step 4 — Save the generated report")

        step4 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        step4.pack(fill="x")

        tk.Label(
            step4,
            text=f"When {provider_name} generates the report, copy the full Markdown text\n"
                 f"and save it as:  report_{self._today()}.md\n"
                 f"in the meeting folder:\n",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w")

        folder_lbl = tk.Label(
            step4,
            text=str(r.meeting_folder),
            font=FONTS["mono"], fg=COLORS["accent"], bg=COLORS["bg_card"]
        )
        folder_lbl.pack(anchor="w")

        tk.Label(
            step4,
            text="\nThen come back and use Open report.md and Export to DOCX.",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w")

        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")
        self._primary_button(footer, "Done", self.destroy, width=10).pack(
            side="right", padx=PAD["window"]
        )

    def _copy_web_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn.configure(bg=COLORS["success"], text="Copied ✓")
        self._lbl_copied.configure(
            text="Prompt copied. Paste it in the chat after uploading the files."
        )

    # ── Two-pass flow ─────────────────────────────────────────────────────────

    def _build_two_pass(self):
        r = self.result
        provider_name = PROVIDER_NAMES.get(r.provider, r.provider.title())
        provider_url  = PROVIDER_URLS.get(r.provider, "https://claude.ai/new")

        self._header(
            self,
            "Two-pass analysis — two separate chats",
            f"{r.n_frames} frames total  ·  split in two halves  ·  {provider_name}"
        )

        canvas = tk.Canvas(self, bg=COLORS["bg_card"], highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        content = tk.Frame(canvas, bg=COLORS["bg_card"])
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # ── Chat 1 ──
        self._section_label(content, f"Chat 1 — First half of the meeting")

        c1 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        c1.pack(fill="x")

        tk.Label(
            c1, text="Upload these files to a NEW chat:",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 6))

        f1 = tk.Frame(c1, bg=COLORS["accent_light"], padx=10, pady=8)
        f1.pack(fill="x")

        if r.transcript_txt:
            half1 = r.meeting_folder / f"{r.transcript_txt.stem}_half1.txt"
            if half1.exists():
                self._file_row(f1, half1, "Transcript — first half")

        for fp in r.frames_chat1:
            self._file_row(f1, fp, "Frame")

        btn_row1 = tk.Frame(c1, bg=COLORS["bg_card"])
        btn_row1.pack(anchor="w", pady=(8, 0))

        self._primary_button(
            btn_row1, f"Open {provider_name} (Chat 1)",
            lambda: _open_browser(provider_url), width=22
        ).pack(side="left", padx=(0, 8))

        self._copy_btn1 = self._secondary_button(
            btn_row1, "Copy Chat 1 prompt", self._copy_chat1_prompt, width=18
        )
        self._copy_btn1.pack(side="left")

        self._lbl_copied1 = tk.Label(
            c1, text="",
            font=FONTS["small"], fg=COLORS["success"], bg=COLORS["bg_card"]
        )
        self._lbl_copied1.pack(anchor="w", pady=(4, 0))

        tk.Label(
            c1,
            text="At the end of Chat 1, the LLM will generate a handoff JSON block.\n"
                 "Copy that block and save it using: File → Save handoff (coming soon)\n"
                 "or paste it into:  " + str(r.handoff_path or "handoff.json"),
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["bg_card"],
            justify="left"
        ).pack(anchor="w", pady=(8, 0))

        # ── Chat 2 ──
        self._section_label(content, "Chat 2 — Second half + merge")

        c2 = tk.Frame(content, bg=COLORS["bg_card"], padx=PAD["window"], pady=8)
        c2.pack(fill="x")

        tk.Label(
            c2, text="Upload these files to a NEW chat (separate from Chat 1):",
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"]
        ).pack(anchor="w", pady=(0, 6))

        f2 = tk.Frame(c2, bg=COLORS["accent_light"], padx=10, pady=8)
        f2.pack(fill="x")

        if r.handoff_path:
            tk.Label(
                f2,
                text=f"  handoff_{self._today()}.json  — saved after Chat 1",
                font=FONTS["mono"], fg=COLORS["text_muted"], bg=COLORS["accent_light"]
            ).pack(anchor="w", pady=1)

        if r.transcript_txt:
            half2 = r.meeting_folder / f"{r.transcript_txt.stem}_half2.txt"
            if half2.exists():
                self._file_row(f2, half2, "Transcript — second half")

        for fp in r.frames_chat2:
            self._file_row(f2, fp, "Frame")

        btn_row2 = tk.Frame(c2, bg=COLORS["bg_card"])
        btn_row2.pack(anchor="w", pady=(8, 0))

        self._primary_button(
            btn_row2, f"Open {provider_name} (Chat 2)",
            lambda: _open_browser(provider_url), width=22
        ).pack(side="left", padx=(0, 8))

        self._copy_btn2 = self._secondary_button(
            btn_row2, "Copy Chat 2 prompt", self._copy_chat2_prompt, width=18
        )
        self._copy_btn2.pack(side="left")

        self._lbl_copied2 = tk.Label(
            c2, text="",
            font=FONTS["small"], fg=COLORS["success"], bg=COLORS["bg_card"]
        )
        self._lbl_copied2.pack(anchor="w", pady=(4, 0))

        footer = tk.Frame(self, bg=COLORS["bg"], pady=12)
        footer.pack(fill="x", side="bottom")
        self._primary_button(footer, "Done", self.destroy, width=10).pack(
            side="right", padx=PAD["window"]
        )

    def _copy_chat1_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat1)
        self._copy_btn1.configure(bg=COLORS["success"], text="Copied ✓")
        self._lbl_copied1.configure(text="Chat 1 prompt copied to clipboard.")

    def _copy_chat2_prompt(self):
        _copy_to_clipboard(self, self.result.prompt_chat2)
        self._copy_btn2.configure(bg=COLORS["success"], text="Copied ✓")
        self._lbl_copied2.configure(text="Chat 2 prompt copied to clipboard.")

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _file_row(self, parent, file_path: Path, label: str):
        row = tk.Frame(parent, bg=COLORS["accent_light"])
        row.pack(fill="x", pady=1)
        tk.Label(
            row, text=f"  {file_path.name}",
            font=FONTS["mono"], fg=COLORS["accent"], bg=COLORS["accent_light"]
        ).pack(side="left")
        tk.Label(
            row, text=f"  ({label})",
            font=FONTS["small"], fg=COLORS["text_muted"], bg=COLORS["accent_light"]
        ).pack(side="left")

    def _open_folder(self):
        folder = self.result.meeting_folder
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.Popen(f'explorer "{folder}"')
            elif system == "Darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception:
            pass

    def _today(self) -> str:
        from datetime import date
        return date.today().strftime("%Y%m%d")
