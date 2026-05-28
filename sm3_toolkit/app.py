from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from sm3_toolkit import paths
from sm3_toolkit.app_state import AppState
from sm3_toolkit.i18n import LANGUAGE_NAMES, tab_labels, tr
from sm3_toolkit.theme import COLORS, apply_theme
from sm3_toolkit.tabs.home_tab import HomeTab
from sm3_toolkit.tabs.pack_extractor_tab import PackExtractorTab
from sm3_toolkit.tabs.hex_viewer_tab import HexViewerTab
from sm3_toolkit.tabs.tex_swapper_tab import TexSwapperTab
from sm3_toolkit.tabs.texture_folder_viewer_tab import TextureFolderViewerTab
from sm3_toolkit.tabs.old_animation_swapper_tab import OldAnimationSwapperTab
from sm3_toolkit.tabs.how_to_use_tab import HowToUseTab
from sm3_toolkit.tabs.about_tab import AboutInfoTab


APP_NAME = "SM3 MODDING TOOLKIT"
APP_VERSION = "v5.2.13 Release Candidate"


class SM3ToolsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.toolkit_status_var = tk.StringVar(value=f"{APP_NAME} ready.")
        self.app_state = AppState(root=root, app_dir=paths.APP_DIR, resource_root=paths.RESOURCE_ROOT, version=APP_VERSION)
        self._configure_root()
        apply_theme(root)
        self._build_ui()

    def _configure_root(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry("1500x920")
        self.root.minsize(1250, 760)
        self.root.configure(bg=COLORS["bg"])
        try:
            if paths.APP_ICON_PATH.exists():
                self.root.iconbitmap(default=str(paths.APP_ICON_PATH))
        except Exception:
            pass
        # Give the integrated toolkit more horizontal room on Windows so large tabs and tables are visible.
        try:
            self.root.state("zoomed")
        except Exception:
            pass

    def _build_ui(self) -> None:
        root_frame = ttk.Frame(self.root, style="Root.TFrame")
        root_frame.pack(fill="both", expand=True)

        header = ttk.Frame(root_frame, style="Header.TFrame", padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.header_meta_label = ttk.Label(header, text="", style="HeaderMeta.TLabel")
        self.header_meta_label.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.language_label = ttk.Label(header, text="", style="HeaderMeta.TLabel")
        self.language_label.grid(row=0, column=1, sticky="e", padx=(12, 6))
        language_box = ttk.Combobox(
            header,
            textvariable=self.app_state.language_var,
            values=LANGUAGE_NAMES,
            state="readonly",
            width=14,
        )
        language_box.grid(row=0, column=2, sticky="e")
        language_box.bind("<<ComboboxSelected>>", lambda _event: self.app_state.set_language(self.app_state.language_var.get()))
        # Version/build info is kept in About / Info. Do not show test/update labels in the release header.
        header.columnconfigure(0, weight=1)

        self.tabs = ttk.Notebook(root_frame)
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.tabs.add(HomeTab(self.tabs, self.app_state), text="Home")
        self.tabs.add(PackExtractorTab(self.tabs, self.app_state), text="Pack Extractor")
        self.tabs.add(HexViewerTab(self.tabs, self.app_state), text="Hex Viewer")
        self.tabs.add(TexSwapperTab(self.tabs, self.app_state), text="Tex Swapper")
        self.tabs.add(TextureFolderViewerTab(self.tabs, self.app_state), text="Texture Folder Viewer")
        self.tabs.add(OldAnimationSwapperTab(self.tabs, self.app_state), text="Old Animation Swapper")
        self.tabs.add(HowToUseTab(self.tabs, self.app_state), text="How To Use")
        self.tabs.add(AboutInfoTab(self.tabs, self.app_state), text="About / Info")
        self.tabs.select(0)
        self.app_state.on_language_change(self._apply_language)

        footer = ttk.Frame(root_frame, style="Header.TFrame", padding=(10, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.root.toolkit_status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)

    def _apply_language(self, language: str) -> None:
        self.header_meta_label.configure(text=tr(language, "header_meta"))
        self.language_label.configure(text=tr(language, "language_label") + ":")
        for index, label in enumerate(tab_labels(language)):
            if index < self.tabs.index("end"):
                self.tabs.tab(index, text=label)


def main() -> None:
    root = tk.Tk()
    SM3ToolsApp(root)
    root.mainloop()
