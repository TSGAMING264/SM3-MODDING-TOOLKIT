from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from sm3_toolkit import paths
from sm3_toolkit.app_state import AppState
from sm3_toolkit.i18n import LANGUAGE_NAMES, compact_tab_labels, tab_labels, tr
from sm3_toolkit.ui_localization import install_dialog_localization, translate_widget_tree
from sm3_toolkit.theme import (
    COLORS,
    THEME_NAMES,
    apply_theme,
    apply_full_theme_overrides,
    refresh_tk_widget_colors,
    restore_full_theme_overrides,
)
from sm3_toolkit.tabs.home_tab import HomeTab
from sm3_toolkit.tabs.pack_extractor_tab import PackExtractorTab
from sm3_toolkit.tabs.pcpack_rebuild_lab_tab import PCPACKRebuildLabTab
from sm3_toolkit.tabs.hex_viewer_tab import HexViewerTab
from sm3_toolkit.tabs.mat_editor_tab import MATEditorTab
from sm3_toolkit.tabs.tex_swapper_tab import TexSwapperTab
from sm3_toolkit.tabs.texture_folder_viewer_tab import TextureFolderViewerTab
from sm3_toolkit.tabs.new_animation_swapper_tab import NewAnimationSwapperTab
from sm3_toolkit.tabs.old_animation_swapper_tab import OldAnimationSwapperTab
from sm3_toolkit.tabs.sound_editor_tab import SoundEditorTab
from sm3_toolkit.tabs.model_viewer_tab import ModelViewerTab
from sm3_toolkit.tabs.how_to_use_tab import HowToUseTab
from sm3_toolkit.tabs.about_tab import AboutInfoTab


APP_NAME = "SM3 MODDING TOOLKIT"
APP_VERSION = "v5.2.196 FINAL ABOUT CREDIT"


MAIN_TAB_X_PADDING = 4
MAIN_TAB_FONT = ("Segoe UI", 10, "bold")
MAIN_TAB_COMPACT_ENGLISH = (
    "Home",
    "Pack Extractor",
    "Hex/Text",
    "Tex Swapper",
    "Tex Folder Viewer",
    "MAT Editor",
    "Model Viewer",
    "New Anim Swapper",
    "Old Anim Swapper",
    "Sound Editor",
    "PCPACK Rebuild",
    "How To Use",
    "About",
)


class SM3ToolsApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.toolkit_status_var = tk.StringVar(value=f"{APP_NAME} ready.")
        self.full_theme_var = tk.BooleanVar(value=False)
        self.root.full_theme_var = self.full_theme_var
        self.app_state = AppState(root=root, app_dir=paths.APP_DIR, resource_root=paths.RESOURCE_ROOT, version=APP_VERSION)
        install_dialog_localization(lambda: self.app_state.language)
        self._configure_root()
        apply_theme(root, self.app_state.theme)
        self._build_ui()

    def _configure_root(self) -> None:
        self.root.title(APP_NAME)
        # Release UI sizing: fit the current display/work area instead of forcing
        # a 1250x760 minimum that can fall behind the Windows taskbar or DPI scaling.
        try:
            screen_w = int(self.root.winfo_screenwidth())
            screen_h = int(self.root.winfo_screenheight())
        except Exception:
            screen_w, screen_h = 1500, 920
        min_w = min(1100, max(900, screen_w - 40))
        min_h = min(650, max(560, screen_h - 100))
        start_w = min(1500, max(min_w, screen_w - 20))
        start_h = min(920, max(min_h, screen_h - 80))
        self.root.geometry(f"{start_w}x{start_h}")
        self.root.minsize(min_w, min_h)
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

    def _configure_main_notebook_style(self) -> None:
        """Keep only the main app tabs compact; nested notebooks keep their own styles."""
        style = ttk.Style(self.root)
        style.configure(
            "Main.TNotebook",
            background=COLORS["bg"],
            borderwidth=0,
        )
        style.configure(
            "Main.TNotebook.Tab",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            padding=(MAIN_TAB_X_PADDING, 7),
            font=MAIN_TAB_FONT,
        )
        style.map(
            "Main.TNotebook.Tab",
            background=[("selected", COLORS["panel2"]), ("active", COLORS["button"])],
            foreground=[("selected", COLORS["fg"]), ("active", COLORS["fg"])],
        )

    def _compact_tab_labels(self, language: str, full_labels: list[str]) -> list[str]:
        if language == "English":
            return list(MAIN_TAB_COMPACT_ENGLISH)
        # Hand-authored native short labels; never chop a translated word in half.
        native = compact_tab_labels(language)
        return native if native else list(full_labels)

    def _tab_labels_fit(self, labels: list[str], available_width: int) -> bool:
        if available_width <= 1:
            return False
        try:
            font_spec = ttk.Style(self.root).lookup("Main.TNotebook.Tab", "font") or MAIN_TAB_FONT
            tab_font = tkfont.Font(root=self.root, font=font_spec)
            # 2*x padding plus a small allowance for the native tab border/separator.
            required = sum(tab_font.measure(str(label)) + (MAIN_TAB_X_PADDING * 2) + 2 for label in labels)
            return required <= max(1, available_width - 4)
        except Exception:
            return False

    def _refresh_main_tab_headers(self) -> None:
        if not hasattr(self, "tabs"):
            return
        language = self.app_state.language_var.get()
        full_labels = list(tab_labels(language))
        compact_labels = self._compact_tab_labels(language, full_labels)
        try:
            width = int(self.tabs.winfo_width())
        except Exception:
            width = 0
        labels = full_labels if self._tab_labels_fit(full_labels, width) else compact_labels
        for index, label in enumerate(labels):
            if index < self.tabs.index("end"):
                self.tabs.tab(index, text=label)

    def _schedule_main_tab_refresh(self, _event=None) -> None:
        pending = getattr(self, "_main_tab_resize_job", None)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
        self._main_tab_resize_job = self.root.after(60, self._refresh_main_tab_headers)

    def _build_ui(self) -> None:
        self.root_frame = ttk.Frame(self.root, style="Root.TFrame")
        root_frame = self.root_frame
        root_frame.pack(fill="both", expand=True)

        header = ttk.Frame(root_frame, style="Header.TFrame", padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.header_meta_label = ttk.Label(header, text="", style="HeaderMeta.TLabel")
        self.header_meta_label.grid(row=1, column=0, sticky="w", pady=(3, 0))
        # FULL THEME is opt-in. Off keeps the established theme behavior; on
        # pushes the selected palette through nested/custom controls too.
        self.full_theme_check = ttk.Checkbutton(
            header,
            text="FULL THEME",
            variable=self.full_theme_var,
            command=self._toggle_full_theme,
            style="Header.TCheckbutton",
        )
        self.full_theme_check.grid(row=0, column=1, sticky="e", padx=(8, 10))

        self.theme_label = ttk.Label(header, text="Theme:", style="HeaderMeta.TLabel")
        self.theme_label.grid(row=0, column=2, sticky="e", padx=(4, 6))
        theme_box = ttk.Combobox(
            header,
            textvariable=self.app_state.theme_var,
            values=THEME_NAMES,
            state="readonly",
            width=12,
        )
        theme_box.grid(row=0, column=3, sticky="e")
        theme_box.bind("<<ComboboxSelected>>", lambda _event: self.app_state.set_theme(self.app_state.theme_var.get()))
        self.language_label = ttk.Label(header, text="", style="HeaderMeta.TLabel")
        self.language_label.grid(row=0, column=4, sticky="e", padx=(12, 6))
        language_box = ttk.Combobox(
            header,
            textvariable=self.app_state.language_var,
            values=LANGUAGE_NAMES,
            state="readonly",
            width=18,
        )
        language_box.grid(row=0, column=5, sticky="e")
        language_box.bind("<<ComboboxSelected>>", lambda _event: self.app_state.set_language(self.app_state.language_var.get()))
        # Version/build info is kept in About / Info. Do not show test/update labels in the release header.
        header.columnconfigure(0, weight=1)


        self._configure_main_notebook_style()
        self.tabs = ttk.Notebook(root_frame, style="Main.TNotebook")
        self.tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self.tabs.add(HomeTab(self.tabs, self.app_state), text="Home")
        self.tabs.add(PackExtractorTab(self.tabs, self.app_state), text="Pack Extractor")
        self.tabs.add(HexViewerTab(self.tabs, self.app_state), text="Hex/Text")
        self.tabs.add(TexSwapperTab(self.tabs, self.app_state), text="Tex Swapper")
        self.tabs.add(TextureFolderViewerTab(self.tabs, self.app_state), text="Texture Folder Viewer")
        self.tabs.add(MATEditorTab(self.tabs, self.app_state), text="MAT Editor")
        self.tabs.add(ModelViewerTab(self.tabs, self.app_state), text="Model Viewer")
        self.tabs.add(NewAnimationSwapperTab(self.tabs, self.app_state), text="New Animation Swapper")
        self.tabs.add(OldAnimationSwapperTab(self.tabs, self.app_state), text="Old Animation Swapper")
        self.tabs.add(SoundEditorTab(self.tabs, self.app_state), text="Sound Editor")
        self.tabs.add(PCPACKRebuildLabTab(self.tabs, self.app_state), text="PCPACK Rebuild Lab")
        self.tabs.add(HowToUseTab(self.tabs, self.app_state), text="How To Use")
        self.tabs.add(AboutInfoTab(self.tabs, self.app_state), text="About / Info")
        self.tabs.select(0)
        self.tabs.bind("<Configure>", self._schedule_main_tab_refresh, add="+")
        self.root.after_idle(self._refresh_main_tab_headers)
        self.app_state.on_language_change(self._apply_language)
        self.app_state.on_theme_change(self._apply_theme)

        footer = ttk.Frame(root_frame, style="Header.TFrame", padding=(10, 7))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.root.toolkit_status_var, style="Status.TLabel").pack(side="left", fill="x", expand=True)

        # Any dialog or late-created control is localized when it maps into view.
        # Debouncing prevents startup from doing redundant full-tree scans.
        self.root.bind_all("<Map>", self._schedule_language_refresh, add="+")

    def _schedule_language_refresh(self, _event=None) -> None:
        # English is the protected/default UI. Do not run the localization tree
        # unless the user explicitly selected another language.
        if self.app_state.language == "English":
            return
        pending = getattr(self, "_language_refresh_job", None)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except Exception:
                pass
        self._language_refresh_job = self.root.after(80, lambda: translate_widget_tree(self.root, self.app_state.language))

    def _apply_theme(self, theme: str) -> None:
        # Normal path is unchanged from previous releases.
        apply_theme(self.root, theme)
        self._configure_main_notebook_style()
        try:
            refresh_tk_widget_colors(self.root)
        except Exception:
            pass
        try:
            self.root.configure(bg=COLORS["bg"])
        except Exception:
            pass

        # Optional full-window pass. The overlay is reversible and never changes
        # extraction/editor/model/audio logic.
        if bool(self.full_theme_var.get()):
            try:
                apply_full_theme_overrides(self.root)
            except Exception:
                pass
        self.root.after_idle(self._refresh_main_tab_headers)

    def _toggle_full_theme(self) -> None:
        theme = self.app_state.theme
        if bool(self.full_theme_var.get()):
            # Re-run the current theme once so every tab listener has current
            # palette values before the full overlay is applied.
            self.app_state.set_theme(theme)
            self.app_state.set_status(f"FULL THEME enabled — {theme} applied to the whole toolkit.")
        else:
            try:
                restore_full_theme_overrides(self.root)
            except Exception:
                pass
            # Reapply through the established/OG theme path after restoring the
            # temporary widget styles.
            self.app_state.set_theme(theme)
            self.app_state.set_status(f"FULL THEME disabled — original theme flow restored ({theme}).")

    def _apply_language(self, language: str) -> None:
        self.header_meta_label.configure(text=tr(language, "header_meta"))
        self.language_label.configure(text=tr(language, "language_label") + ":")
        try:
            self.theme_label.configure(text=tr(language, "theme_label") + ":")
        except Exception:
            pass
        try:
            self.full_theme_check.configure(text=tr(language, "full_theme_label"))
        except Exception:
            pass
        self._refresh_main_tab_headers()
        translate_widget_tree(self.root, language)
        # Show the active language status immediately. English is the hard startup default.
        self.app_state.set_status(tr(language, "status_language"))


def main() -> None:
    root = tk.Tk()
    SM3ToolsApp(root)
    root.mainloop()
