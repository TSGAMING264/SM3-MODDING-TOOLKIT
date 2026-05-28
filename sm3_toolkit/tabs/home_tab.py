from __future__ import annotations

from tkinter import scrolledtext, ttk

from sm3_toolkit import paths
from sm3_toolkit.i18n import tr
from sm3_toolkit.theme import COLORS


class HomeTab(ttk.Frame):
    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=16)
        self.app_state = app_state
        self._build()

    def _text_box(self, parent, text: str):
        box = scrolledtext.ScrolledText(
            parent,
            wrap="word",
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            font=("Segoe UI", 10),
        )
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.configure(state="disabled")
        return box

    def _build(self):
        self.title_label = ttk.Label(self, text="SM3 MODDING TOOLKIT", style="SectionTitle.TLabel")
        self.title_label.pack(anchor="w")
        self.byline_label = ttk.Label(self, text="Created by TSGAMING264", style="Byline.TLabel")
        self.byline_label.pack(anchor="w", pady=(4, 8))
        self.subtitle_label = ttk.Label(
            self,
            text="",
            style="Muted.TLabel",
            wraplength=1120,
        )
        self.subtitle_label.pack(anchor="w", pady=(0, 10))

        self.overview_box = self._text_box(self, "")
        if self.app_state:
            self.app_state.on_language_change(self._apply_language)
        else:
            self._apply_language("English")

    def _set_box_text(self, text: str) -> None:
        self.overview_box.configure(state="normal")
        self.overview_box.delete("1.0", "end")
        self.overview_box.insert("1.0", text)
        self.overview_box.configure(state="disabled")

    def _apply_language(self, language: str) -> None:
        self.subtitle_label.configure(text=tr(language, "home_subtitle"))
        self._set_box_text(tr(language, "home_body"))
