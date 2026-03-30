"""
gui/styles.py — MeetingTool v2.0
==================================
Shared colors, fonts, and widget helpers for all GUI windows.
Clean, professional look that works on Windows and Mac.
"""

import tkinter as tk
from tkinter import ttk


# ── Color palette ─────────────────────────────────────────────────────────────

COLORS = {
    "bg":           "#F7F7F5",      # window background
    "bg_card":      "#FFFFFF",      # card / panel background
    "bg_input":     "#FFFFFF",      # input field background
    "accent":       "#4A6CF7",      # primary blue (buttons, highlights)
    "accent_hover": "#3A5CE5",      # button hover
    "accent_light": "#EEF1FE",      # light blue (section headers)
    "success":      "#2D9E6B",      # green (ok messages)
    "warning":      "#D97706",      # amber (warnings)
    "error":        "#DC2626",      # red (errors)
    "text":         "#1A1A1A",      # primary text
    "text_muted":   "#6B7280",      # secondary text
    "border":       "#E5E7EB",      # borders and dividers
    "step_done":    "#2D9E6B",      # completed step
    "step_active":  "#4A6CF7",      # current step
    "step_pending": "#D1D5DB",      # future step
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
    "window":  24,   # outer window padding
    "section": 16,   # between sections
    "item":    8,    # between items
    "small":   4,    # tight spacing
}


# ── Base window class ─────────────────────────────────────────────────────────

class BaseWindow(tk.Toplevel):
    """
    Base class for all MeetingTool windows.
    Handles: centering, icon, background color, close behavior.
    """

    def __init__(self, parent, title: str, width: int = 640, height: int = 560):
        super().__init__(parent)
        self.title(f"MeetingTool — {title}")
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)
        self._center(width, height)
        self.lift()
        self.focus_force()

    def _center(self, width: int, height: int):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _header(self, parent, title: str, subtitle: str = "") -> tk.Frame:
        """Render a standard window header with title and optional subtitle."""
        frame = tk.Frame(parent, bg=COLORS["accent"], padx=PAD["window"], pady=16)
        frame.pack(fill="x")
        tk.Label(
            frame, text=title,
            font=FONTS["title"], fg="#FFFFFF", bg=COLORS["accent"],
            anchor="w"
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                frame, text=subtitle,
                font=FONTS["subtitle"], fg="#C7D2FE", bg=COLORS["accent"],
                anchor="w"
            ).pack(anchor="w", pady=(2, 0))
        return frame

    def _section_label(self, parent, text: str):
        """Render a section label."""
        frame = tk.Frame(parent, bg=COLORS["accent_light"],
                         padx=PAD["window"], pady=6)
        frame.pack(fill="x", pady=(PAD["section"], 0))
        tk.Label(
            frame, text=text,
            font=FONTS["heading"], fg=COLORS["accent"], bg=COLORS["accent_light"]
        ).pack(anchor="w")

    def _labeled_field(self, parent, label: str, default: str = "",
                       width: int = 40, browse: bool = False,
                       browse_type: str = "dir") -> tk.StringVar:
        """
        Render a label + entry field row.
        Returns the StringVar bound to the entry.
        """
        frame = tk.Frame(parent, bg=COLORS["bg_card"],
                         padx=PAD["window"], pady=PAD["small"])
        frame.pack(fill="x")

        tk.Label(
            frame, text=label,
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 2))

        row = tk.Frame(frame, bg=COLORS["bg_card"])
        row.pack(fill="x")

        var = tk.StringVar(value=default)
        entry = tk.Entry(
            row, textvariable=var,
            font=FONTS["body"], width=width,
            bg=COLORS["bg_input"], fg=COLORS["text"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 4))

        if browse:
            def _browse():
                if browse_type == "dir":
                    from tkinter import filedialog
                    path = filedialog.askdirectory(title="Select folder")
                else:
                    from tkinter import filedialog
                    path = filedialog.askopenfilename(title="Select file")
                if path:
                    var.set(path)

            tk.Button(
                row, text="Browse…",
                font=FONTS["small"],
                bg=COLORS["border"], fg=COLORS["text"],
                relief="flat", cursor="hand2",
                padx=8, pady=4,
                command=_browse
            ).pack(side="left")

        return var

    def _radio_group(self, parent, label: str, options: list[tuple[str, str]],
                     default: str = None) -> tk.StringVar:
        """
        Render a label + radio button group.
        options: list of (value, display_label)
        Returns StringVar with selected value.
        """
        frame = tk.Frame(parent, bg=COLORS["bg_card"],
                         padx=PAD["window"], pady=PAD["small"])
        frame.pack(fill="x")

        tk.Label(
            frame, text=label,
            font=FONTS["body"], fg=COLORS["text"], bg=COLORS["bg_card"],
            anchor="w"
        ).pack(anchor="w", pady=(0, 4))

        var = tk.StringVar(value=default or options[0][0])

        for value, display in options:
            tk.Radiobutton(
                frame, text=display, variable=var, value=value,
                font=FONTS["body"],
                bg=COLORS["bg_card"], fg=COLORS["text"],
                activebackground=COLORS["bg_card"],
                selectcolor=COLORS["accent_light"],
                relief="flat", cursor="hand2",
            ).pack(anchor="w", pady=1)

        return var

    def _status_label(self, parent) -> tk.Label:
        """A status label for showing progress/errors."""
        lbl = tk.Label(
            parent, text="",
            font=FONTS["small"], fg=COLORS["text_muted"],
            bg=COLORS["bg"], wraplength=580, justify="left"
        )
        lbl.pack(pady=(PAD["small"], 0), padx=PAD["window"], anchor="w")
        return lbl

    def _primary_button(self, parent, text: str, command,
                        width: int = 16) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            font=FONTS["button"],
            bg=COLORS["accent"], fg="#FFFFFF",
            activebackground=COLORS["accent_hover"],
            activeforeground="#FFFFFF",
            relief="flat", cursor="hand2",
            padx=16, pady=8, width=width,
        )
        return btn

    def _secondary_button(self, parent, text: str, command,
                          width: int = 12) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            font=FONTS["button"],
            bg=COLORS["border"], fg=COLORS["text"],
            activebackground="#D1D5DB",
            relief="flat", cursor="hand2",
            padx=12, pady=8, width=width,
        )
        return btn

    def _divider(self, parent):
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(
            fill="x", padx=PAD["window"], pady=PAD["section"]
        )

    def _log_box(self, parent, height: int = 8) -> tk.Text:
        """A read-only log/output text box."""
        frame = tk.Frame(parent, bg=COLORS["bg_card"],
                         padx=PAD["window"], pady=PAD["small"])
        frame.pack(fill="both", expand=True)

        txt = tk.Text(
            frame, height=height,
            font=FONTS["mono"],
            bg="#1E1E1E", fg="#D4D4D4",
            relief="flat", state="disabled",
            wrap="word",
        )
        scroll = tk.Scrollbar(frame, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        return txt

    def _log_append(self, log_box: tk.Text, msg: str, color: str = None):
        """Append a line to the log box."""
        log_box.configure(state="normal")
        tag = None
        if color == "ok":
            tag = "ok"
            log_box.tag_configure("ok", foreground="#6CE26C")
        elif color == "warn":
            tag = "warn"
            log_box.tag_configure("warn", foreground="#F5C542")
        elif color == "err":
            tag = "err"
            log_box.tag_configure("err", foreground="#F87171")

        if tag:
            log_box.insert("end", msg + "\n", tag)
        else:
            log_box.insert("end", msg + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")
        log_box.update()
