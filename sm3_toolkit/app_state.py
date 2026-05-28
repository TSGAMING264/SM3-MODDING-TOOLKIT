from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from typing import Callable

from sm3_toolkit.i18n import DEFAULT_LANGUAGE, LANGUAGE_NAMES, tr


@dataclass
class AppState:
    root: tk.Tk
    app_dir: Path
    resource_root: Path
    version: str

    def __post_init__(self) -> None:
        self.language_var = tk.StringVar(value=DEFAULT_LANGUAGE)
        self._language_listeners: list[Callable[[str], None]] = []

    def set_status(self, message: str) -> None:
        if hasattr(self.root, "toolkit_status_var"):
            self.root.toolkit_status_var.set(message)

    @property
    def language(self) -> str:
        value = self.language_var.get()
        return value if value in LANGUAGE_NAMES else DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        if language not in LANGUAGE_NAMES:
            language = DEFAULT_LANGUAGE
        self.language_var.set(language)
        for callback in list(self._language_listeners):
            callback(language)
        self.set_status(tr(language, "status_language"))

    def on_language_change(self, callback: Callable[[str], None]) -> None:
        self._language_listeners.append(callback)
        callback(self.language)
