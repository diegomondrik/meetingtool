"""
gui/settings.py - MeetingTool v2.5
Settings modal: general preferences (no API keys — Cowork flow uses subscription).
"""

import customtkinter as ctk
from tkinter import messagebox

from gui.styles import BaseWindow, COLORS, FONTS, PAD


class SettingsWindow(BaseWindow):

    def __init__(self, parent, config: dict, on_save=None):
        super().__init__(parent, "Settings", width=580, height=480)
        self.config = config
        self.on_save = on_save
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()

    def _build(self):
        self._header(self, "Settings", "Preferences.")

        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1, corner_radius=0).pack(
            fill="x", side="bottom"
        )
        footer = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        footer.pack(fill="x", side="bottom", pady=10)
        self._secondary_button(footer, "Cancel", self.destroy, width=100).pack(
            side="right", padx=8
        )
        self._primary_button(footer, "Save changes", self._save, width=130).pack(
            side="right", padx=(PAD["window"], 0)
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        self._build_prefs(scroll)

    def _build_prefs(self, parent):
        self._section_label(parent, "Installation folder")
        self._var_root = self._labeled_field(
            parent, "Projects and recordings folder",
            self.config.get("mip_root", ""),
            browse=True, browse_type="dir",
        )

        self._section_label(parent, "Default AI provider")
        self._var_provider = self._radio_group(
            parent, "",
            [("claude", "Claude"), ("chatgpt", "ChatGPT"), ("gemini", "Gemini")],
            default=self.config.get("llm_provider", "claude"),
        )
        self._var_provider.trace_add("write", self._on_provider_change)

        self._cowork_frame = ctk.CTkFrame(parent, fg_color=COLORS["accent_light"], corner_radius=0)
        self._cowork_frame.pack(fill="x")
        ctk.CTkLabel(
            self._cowork_frame, text="How do you use Claude?",
            font=ctk.CTkFont(*FONTS["body"]),
            text_color=COLORS["text"], fg_color="transparent", anchor="w",
        ).pack(anchor="w", padx=PAD["window"] + 16, pady=(PAD["item"], 0))
        self._var_cowork = ctk.StringVar(
            value="cowork" if self.config.get("cowork_mode", False) else "web"
        )
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

        if self.config.get("llm_provider", "claude") != "claude":
            self._cowork_frame.pack_forget()

        self._section_label(parent, "Default report language")
        self._var_language = self._radio_group(
            parent, "",
            [("english", "English"), ("spanish", "Spanish")],
            default=self.config.get("default_language", "english"),
        )

    def _on_provider_change(self, *args):
        if self._var_provider.get() == "claude":
            self._cowork_frame.pack(fill="x")
        else:
            self._cowork_frame.pack_forget()

    def _save(self):
        from tools.installer import _write_global_config
        provider = self._var_provider.get()
        updated = {
            **self.config,
            "mip_root":         self._var_root.get(),
            "llm_provider":     provider,
            "cowork_mode":      (self._var_cowork.get() == "cowork") if provider == "claude" else False,
            "default_language": self._var_language.get(),
        }
        _write_global_config(updated)
        if self.on_save:
            self.on_save()
        messagebox.showinfo("Saved", "Settings saved.")
        self.destroy()
