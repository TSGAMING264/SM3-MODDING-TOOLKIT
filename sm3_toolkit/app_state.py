from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from typing import Callable

from sm3_toolkit.i18n import DEFAULT_LANGUAGE, normalize_language, tr
from sm3_toolkit.theme import DEFAULT_THEME, THEME_NAMES, theme_display_name


@dataclass
class AppState:
    root: tk.Tk
    app_dir: Path
    resource_root: Path
    version: str

    def __post_init__(self) -> None:
        self.language_var = tk.StringVar(value=DEFAULT_LANGUAGE)
        self.theme_var = tk.StringVar(value=DEFAULT_THEME)
        self._language_listeners: list[Callable[[str], None]] = []
        self._theme_listeners: list[Callable[[str], None]] = []
        # Keep the actually-applied language separate from language_var.
        # A readonly ttk.Combobox updates its StringVar before firing
        # <<ComboboxSelected>>, so language_var alone cannot tell us which
        # language the UI was previously rendered in.
        self._active_language = DEFAULT_LANGUAGE

    def set_status(self, message: str) -> None:
        if hasattr(self.root, "toolkit_status_var"):
            # Status messages are UI too. Translate the human-readable parts while
            # preserving paths, hashes and technical file-format identifiers.
            try:
                from sm3_toolkit.ui_localization import translate_ui_text
                message = translate_ui_text(self.language, message)
            except Exception:
                pass
            self.root.toolkit_status_var.set(message)

    @property
    def language(self) -> str:
        return normalize_language(self.language_var.get())

    def set_language(self, language: str) -> None:
        language = normalize_language(language)
        previous = normalize_language(getattr(self, "_active_language", DEFAULT_LANGUAGE))

        # IMPORTANT: restore the real English baselines *before* any tab listener
        # writes text for the new language. Without this, switching directly from
        # one non-English language to another can cause the localization walker to
        # mistake already-translated text for fresh English source text. That is
        # what caused the old "select the language twice" behavior.
        if previous != DEFAULT_LANGUAGE and language != previous:
            try:
                from sm3_toolkit.ui_localization import translate_widget_tree
                translate_widget_tree(self.root, DEFAULT_LANGUAGE)
            except Exception:
                pass

        self.language_var.set(language)
        self._active_language = language
        for callback in list(self._language_listeners):
            callback(language)
        self.set_status(tr(language, "status_language"))

    def on_language_change(self, callback: Callable[[str], None]) -> None:
        self._language_listeners.append(callback)
        callback(self.language)

    @property
    def theme(self) -> str:
        value = self.theme_var.get()
        return value if value in THEME_NAMES else DEFAULT_THEME

    def set_theme(self, theme: str) -> None:
        if theme not in THEME_NAMES:
            theme = DEFAULT_THEME
        self.theme_var.set(theme)
        for callback in list(self._theme_listeners):
            callback(theme)
        self.set_status(f"Theme set to {theme_display_name(theme)}.")

    def on_theme_change(self, callback: Callable[[str], None]) -> None:
        self._theme_listeners.append(callback)
        callback(self.theme)
