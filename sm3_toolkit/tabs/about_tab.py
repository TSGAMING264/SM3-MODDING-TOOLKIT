from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from sm3_toolkit import paths
from sm3_toolkit.i18n import tr
from sm3_toolkit.theme import COLORS


class AboutInfoTab(ttk.Frame):
    """About / Info page with TSGAMING264 profile image and restored v5.0 content."""

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=16)
        self.app_state = app_state
        self.profile_image = None
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="SM3 MODDING TOOLKIT", style="SectionTitle.TLabel").pack(anchor="w")

        top_card = ttk.Frame(self, style="Panel.TFrame", padding=12)
        top_card.pack(fill="x", pady=(6, 12))

        image_frame = ttk.Frame(top_card, style="Panel.TFrame")
        image_frame.pack(side="left", padx=(0, 14), anchor="n")
        try:
            if paths.TSGAMING264_PROFILE_IMAGE.exists():
                self.profile_image = tk.PhotoImage(file=str(paths.TSGAMING264_PROFILE_IMAGE))
                ttk.Label(image_frame, image=self.profile_image, style="Panel.TLabel").pack(anchor="nw")
        except Exception:
            self.profile_image = None

        text_frame = ttk.Frame(top_card, style="Panel.TFrame")
        text_frame.pack(side="left", fill="x", expand=True, anchor="n")
        ttk.Label(text_frame, text="Created by TSGAMING264", style="SectionTitle.TLabel").pack(anchor="w")
        self.subtitle_label = ttk.Label(
            text_frame,
            text="",
            style="Muted.TLabel",
            wraplength=900,
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        self.info = scrolledtext.ScrolledText(
            self,
            height=24,
            wrap="word",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.info.pack(fill="both", expand=True)
        if self.app_state:
            self.app_state.on_language_change(self._apply_language)
        else:
            self._apply_language("English")

    def _apply_language(self, language: str) -> None:
        self.subtitle_label.configure(text=tr(language, "about_subtitle"))
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", tr(language, "about_body"))
        self.info.configure(state="disabled")
