"""
gui/styles.py - MeetingTool v2.5
CTk design tokens: dark mode, teal accent.
BaseWindow provides shared helpers for all CTkToplevel windows.
"""

import customtkinter as ctk
from tkinter import filedialog

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg":           "#1C1C1E",
    "bg_sidebar":   "#141416",
    "bg_card":      "#2C2C2E",
    "bg_input":     "#1C1C1E",
    "accent":       "#2DD4BF",
    "accent_hover": "#14B8A6",
    "accent_light": "#1A3840",
    "success":      "#4ADE80",
    "warning":      "#FBBF24",
    "error":        "#F87171",
    "text":         "#F2F2F7",
    "text_muted":   "#8E8E93",
    "border":       "#3A3A3C",
    "step_done":    "#4ADE80",
    "step_active":  "#2DD4BF",
    "step_pending": "#3A3A3C",
}

FONTS = {
    "title":    ("Segoe UI", 18, "bold"),
    "subtitle": ("Segoe UI", 12),
    "heading":  ("Segoe UI", 11, "bold"),
    "body":     ("Segoe UI", 10),
    "small":    ("Segoe UI", 9),
    "mono":     ("Consolas", 9),
    "button":   ("Segoe UI", 10, "bold"),
}

PAD = {
    "window":  20,
    "section": 12,
    "item":    8,
    "small":   4,
}


class BaseWindow(ctk.CTkToplevel):
    """Base class for all MeetingTool modal windows."""

    def __init__(self, parent, title: str, width: int = 640, height: int = 560):
        super().__init__(parent)
        self.title(f"MeetingTool - {title}")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(True, True)
        self._center(width, height)
        # On Windows, new CTkToplevel windows may appear behind the opener.
        # Fix: deiconify first tick, then force topmost briefly so Windows
        # doesn't send focus back to the parent before we're visible.
        self.after(10, self._bring_to_front)

    def _bring_to_front(self):
        """Force window visible and on top; unpin topmost after 400ms."""
        self.deiconify()
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.after(400, lambda: self.attributes("-topmost", False))

    def _center(self, width: int, height: int):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _header(self, parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["accent"], corner_radius=0)
        frame.pack(fill="x")
        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont(*FONTS["title"]),
            text_color="#000000", fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"], pady=(14, 2 if subtitle else 14))
        if subtitle:
            ctk.CTkLabel(
                frame, text=subtitle,
                font=ctk.CTkFont(*FONTS["subtitle"]),
                text_color="#0F766E", fg_color="transparent", anchor="w",
            ).pack(anchor="w", padx=PAD["window"], pady=(0, 14))
        return frame

    def _section_label(self, parent, text: str):
        frame = ctk.CTkFrame(parent, fg_color=COLORS["accent_light"], corner_radius=0)
        frame.pack(fill="x", pady=(PAD["section"], 0))
        ctk.CTkLabel(
            frame, text=text,
            font=ctk.CTkFont(*FONTS["heading"]),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"], pady=6)

    def _labeled_field(self, parent, label: str, default: str = "",
                       browse: bool = False, browse_type: str = "dir",
                       show: str = "") -> ctk.StringVar:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=0)
        frame.pack(fill="x")
        ctk.CTkLabel(
            frame, text=label,
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"], pady=(PAD["small"], 0))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(fill="x", padx=PAD["window"], pady=(2, PAD["small"]))
        row.columnconfigure(0, weight=1)

        var = ctk.StringVar(value=default)
        ctk.CTkEntry(
            row, textvariable=var, show=show,
            font=ctk.CTkFont(*FONTS["body"]),
            fg_color=COLORS["bg_input"], border_color=COLORS["border"],
            text_color=COLORS["text"],
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4 if browse else 0))

        if browse:
            def _browse():
                path = (filedialog.askdirectory(title="Select folder")
                        if browse_type == "dir"
                        else filedialog.askopenfilename(title="Select file"))
                if path:
                    var.set(path)
            ctk.CTkButton(
                row, text="Browse...", command=_browse,
                font=ctk.CTkFont(*FONTS["small"]),
                fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
                text_color=COLORS["text"], width=80, height=32, corner_radius=4,
            ).grid(row=0, column=1)
        return var

    def _radio_group(self, parent, label: str, options: list,
                     default: str = None) -> ctk.StringVar:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=0)
        frame.pack(fill="x")
        if label:
            ctk.CTkLabel(
                frame, text=label,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text"], fg_color="transparent", anchor="w",
            ).pack(anchor="w", padx=PAD["window"], pady=(PAD["small"], 0))

        var = ctk.StringVar(value=default or options[0][0])
        for value, display in options:
            ctk.CTkRadioButton(
                frame, text=display, variable=var, value=value,
                font=ctk.CTkFont(*FONTS["body"]),
                text_color=COLORS["text"],
                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"],
            ).pack(anchor="w", padx=PAD["window"] + 4, pady=2)
        ctk.CTkFrame(frame, fg_color="transparent", height=PAD["small"]).pack()
        return var

    def _primary_button(self, parent, text: str, command, width: int = 120) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=command,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            text_color="#000000", corner_radius=6, width=width, height=36,
        )

    def _secondary_button(self, parent, text: str, command, width: int = 100) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=command,
            font=ctk.CTkFont(*FONTS["button"]),
            fg_color=COLORS["bg_card"], hover_color=COLORS["border"],
            text_color=COLORS["text"], border_color=COLORS["border"],
            border_width=1, corner_radius=6, width=width, height=36,
        )

    def _divider(self, parent):
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1, corner_radius=0).pack(
            fill="x", padx=PAD["window"], pady=PAD["section"]
        )

    def _log_box(self, parent, height: int = 8) -> ctk.CTkTextbox:
        txt = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(*FONTS["mono"]),
            fg_color="#141416", text_color="#D4D4D4",
            wrap="word", height=height * 16, corner_radius=4,
        )
        txt.pack(fill="both", expand=True, padx=PAD["window"], pady=PAD["small"])
        txt.configure(state="disabled")
        return txt

    def _log_append(self, log_box: ctk.CTkTextbox, msg: str, color: str = None):
        color_map = {"ok": "#4ADE80", "warn": "#FBBF24", "err": "#F87171"}
        log_box.configure(state="normal")
        if color and color in color_map:
            tag = f"_color_{color}"
            log_box._textbox.tag_configure(tag, foreground=color_map[color])
            log_box._textbox.insert("end", msg + "\n", tag)
        else:
            log_box._textbox.insert("end", msg + "\n")
        log_box._textbox.see("end")
        log_box.configure(state="disabled")

    def _status_label(self, parent) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent, text="",
            font=ctk.CTkFont(*FONTS["small"]),
            text_color=COLORS["text_muted"], fg_color="transparent",
            anchor="w", wraplength=500,
        )
        lbl.pack(pady=(PAD["small"], 0), padx=PAD["window"], anchor="w")
        return lbl
