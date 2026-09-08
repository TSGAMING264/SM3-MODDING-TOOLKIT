#!/usr/bin/env python3
"""
SM3 Beta Pack Extractor - clean release-style extractor UI for Spider-Man 3 PC.
Created by TSGAMING264.

This standalone beta intentionally hides research/dev controls.
It uses the proven pack extraction backend, but presents a WOS-Toolkit-style flow:
select pack -> list contents -> run extraction -> open output.

Safety: extraction only. Original PCPACKs are never modified.
"""
from __future__ import annotations

import csv
import os
import shutil
import sys
import threading
import traceback
import webbrowser
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception as exc:  # pragma: no cover
    print("Tkinter is required.", exc)
    raise

from sm3_toolkit.services import pack_extract_service as backend
from sm3_toolkit.services import wrap_extract_service as wrap_backend
from sm3_toolkit.services import apkf_reference_dump_service as ref_backend
from sm3_toolkit.services import apkf_clean_database_service as clean_db_backend
from sm3_toolkit.services import xbox_pack_extract_service as xbox_backend
from sm3_toolkit.sm3_pack_guard import (
    WRONG_GAME_GUARD_MESSAGE,
    exception_suggests_wrong_game,
    looks_like_wrong_game_or_unsupported_sm3_path,
    wrong_game_detail,
)
from sm3_toolkit.theme import COLORS

APP_NAME = "SM3 Beta Pack Extractor"
APP_VERSION = "v2.45 WRAP Buttons / MOD LOADER READY #2"
# Megacity Tool dark-mode inspired palette.
BG = "#15171c"
PANEL = "#1f232b"
PANEL2 = "#1b1e25"
ENTRY_BG = "#232832"
TREE_BG = "#20242c"
HEADING_BG = "#2b303a"
TEXT = "#f2f4f8"
MUTED = "#c7ccd6"
ACCENT = "#4A4E57"
ACCENT_DARK = "#30343B"
ACCENT_ACTIVE = "#3A3D45"
# Main extraction button uses a neutral charcoal style so it does not stand out as bright blue.
EXTRACT_BG = "#30343B"
EXTRACT_HOVER = "#3A3D45"
EXTRACT_PRESSED = "#23262C"
WARN = "#AFC0D6"


def open_path(path: Path) -> None:
    try:
        if not path:
            return
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(Path(path).resolve().as_uri())
    except Exception as exc:
        messagebox.showerror("Open failed", str(exc))


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.DictReader(f))


def friendly_family(file_type: str, name: str = "") -> str:
    ft = (file_type or "").upper()
    low = (name or "").lower()
    if ft == "TEX" or low.endswith(".tex"):
        return "Textures"
    if ft in {"MESH", "SKEL", "MORH"} or low.endswith((".mesh", ".skel", ".morh")):
        return "Models"
    if ft == "MAT" or low.endswith(".mat"):
        return "Materials"
    if ft in {"ANIM", "ASKL", "SANM"} or low.endswith((".anim", ".askl", ".sanm")):
        return "Animations"
    if ft in {"AEPS", "FX", "FONT", "CVX"}:
        return "Data / Effects"
    if "voice" in low or "audio" in low or "sound" in low or ".fsb" in low or ".fev" in low:
        return "Audio / Voice"
    if ft:
        return ft.title()
    return "Outer / Review"


def friendly_pack_kind(route: str) -> str:
    route = (route or "").upper()
    if "VOICE" in route or "TYPE35" in route:
        return "Voice / Audio Pack"
    if "COMPACT" in route:
        return "Compact Header Pack"
    if "STUB" in route or "OUTER" in route:
        return "Outer Payload Pack"
    if "NORMAL" in route:
        return "Normal Resource Pack"
    if route:
        return "Review Needed Pack"
    return "Unknown / Review Pack"


class PackExtractorTab(ttk.Frame):
    def __init__(self, parent, app_state=None) -> None:
        super().__init__(parent, style="TFrame")
        self.app_state = app_state
        self.root = self

        self.pack_var = tk.StringVar(value="")
        self.out_var = tk.StringVar(value="")
        self.search_var = tk.StringVar(value="")
        self.force_var = tk.BooleanVar(value=True)
        self.quiet_var = tk.BooleanVar(value=False)
        self.index_var = tk.BooleanVar(value=True)
        self.apk_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Select one SM3 PC pack. MOD LOADER READY is the WRAP extraction route.")
        self.xbox_input_var = tk.StringVar(value="")
        self.xbox_out_var = tk.StringVar(value="")
        self.xbox_pc_compare_var = tk.StringVar(value="")
        self.xbox_status_var = tk.StringVar(value="EXPERIMENTAL: select ONE Xbox/XE pack only. Dev compare/report routes are hidden in the public release page.")
        self.xbox_lab_input_var = tk.StringVar(value="")
        self.xbox_lab_out_var = tk.StringVar(value="")
        self.xbox_lab_pc_slots_var = tk.StringVar(value="")
        self.xbox_lab_status_var = tk.StringVar(value="Xbox Lab is a dev option for full Xbox pack/folder scans and candidate building.")

        self.all_rows: List[Dict[str, str]] = []
        self.xbox_rows: List[Dict[str, str]] = []
        self.last_xbox_output_root: Optional[Path] = None
        self.last_xbox_lab_output_root: Optional[Path] = None
        self.preview_pack_output: Optional[Path] = None
        self.last_output_root: Optional[Path] = None
        self.last_pack_output: Optional[Path] = None
        self.last_catalog_scan_root: Optional[Path] = None
        self.last_reference_dump_root: Optional[Path] = None
        self.last_clean_database_root: Optional[Path] = None
        self.last_extract_mode = ""
        self.running = False

        self._style()
        self._build()
        if self.app_state is not None:
            try:
                self.app_state.on_theme_change(lambda _theme: self._on_global_theme_changed())
            except Exception:
                pass

    def _on_global_theme_changed(self) -> None:
        self._style()
        try:
            self.log_box.configure(
                bg=COLORS["field"],
                fg=COLORS["fg"],
                insertbackground=COLORS["fg"],
                selectbackground=COLORS["select"],
            )
        except Exception:
            pass

    def _style(self) -> None:
        style = ttk.Style()
        bg = COLORS.get("bg", BG)
        panel = COLORS.get("panel", PANEL)
        panel2 = COLORS.get("panel2", PANEL2)
        field = COLORS.get("field", ENTRY_BG)
        fg = COLORS.get("fg", TEXT)
        muted = COLORS.get("muted", MUTED)
        accent = COLORS.get("accent", ACCENT)
        accent_hover = COLORS.get("accent_hover", ACCENT_ACTIVE)
        accent_pressed = COLORS.get("accent_pressed", ACCENT_DARK)
        brand = COLORS.get("brand", fg)
        border = COLORS.get("border", "#596173")
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=bg, foreground=brand, font=("Segoe UI", 16, "bold"))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6, background=COLORS.get("button", panel2), foreground=fg, bordercolor=border)
        style.map("TButton", background=[("active", COLORS.get("button_hover", accent_hover)), ("pressed", COLORS.get("button_pressed", accent_pressed))], foreground=[("active", fg), ("pressed", fg)])
        style.configure("TCheckbutton", background=bg, foreground=fg, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", bg)], foreground=[("active", fg)])
        style.configure("Treeview", background=field, foreground=fg, fieldbackground=field, rowheight=24, font=("Consolas", 10), bordercolor=border)
        style.configure("Treeview.Heading", background=panel, foreground=fg, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", COLORS.get("select", accent))], foreground=[("selected", fg)])
        style.map("Treeview.Heading", background=[("active", panel2)], foreground=[("active", fg)])
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), font=("Segoe UI", 10, "bold"), background=panel2, foreground=muted)
        style.map("TNotebook.Tab", background=[("selected", panel), ("active", COLORS.get("button_hover", accent_hover))], foreground=[("selected", fg), ("active", fg)])
        style.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg, bordercolor=border)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="SM3 PACK EXTRACTOR", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Release extractor - one pack at a time, clean folders only. No CSV/report folder is needed for normal use or release output.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew")
        extractor_tab = ttk.Frame(notebook, padding=8)
        xbox_tab = ttk.Frame(notebook, padding=8)
        info_tab = ttk.Frame(notebook, padding=12)
        notebook.add(extractor_tab, text="PC Extractor")
        notebook.add(xbox_tab, text="Xbox Extractor (Experimental)")
        notebook.add(info_tab, text="Info")

        self._build_extractor_tab(extractor_tab)
        self._build_xbox_tab(xbox_tab)
        # Xbox Lab / candidate / compare code is preserved in source as a dev tool,
        # but it is not added to the normal release tab bar.
        self._build_info_tab(info_tab)

    def _build_extractor_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(4, weight=1)

        ttk.Label(tab, text="INPUT PACK").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.pack_var).grid(row=0, column=1, sticky="ew", pady=4)
        input_buttons = ttk.Frame(tab)
        input_buttons.grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=4)
        ttk.Button(input_buttons, text="Browse Pack", command=self.browse_pack).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Label(tab, text="OUTPUT FOLDER").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.out_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse", command=self.browse_out).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=4)

        # Public release extraction is intentionally simple: one input pack, one output
        # folder, and two explicit extraction routes. Research/dev controls are not
        # exposed on this page.
        self.force_var.set(True)
        self.quiet_var.set(False)
        self.index_var.set(True)
        self.apk_var.set(True)

        search = ttk.Frame(tab)
        search.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 6))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ent = ttk.Entry(search, textvariable=self.search_var)
        ent.grid(row=0, column=1, sticky="ew")
        ent.bind("<KeyRelease>", lambda _e: self.apply_filter())
        ttk.Button(search, text="Clear", command=lambda: (self.search_var.set(""), self.apply_filter())).grid(row=0, column=2, padx=(6, 0))

        route_note = ttk.Frame(tab)
        route_note.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(
            route_note,
            text="MOD LOADER READY = ownership-preserving WRAP extraction.  CLASSIC = normal extracted folders.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT)

        # WOS Toolkit-style filename-first listing. Because the release extractor
        # handles one pack at a time, repeating the pack name on every row wastes
        # horizontal space. Keep the exact SM3 hash/name/extension together as the
        # primary field, then show native resource type/source separately.
        columns = ("idx", "size", "filename", "type", "source")
        self.tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        self.tree.heading("idx", text="Index")
        self.tree.heading("size", text="Size")
        self.tree.heading("filename", text="File Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("source", text="Source")
        self.tree.column("idx", width=105, anchor="w", stretch=False)
        self.tree.column("size", width=110, anchor="e", stretch=False)
        self.tree.column("filename", width=760, anchor="w", stretch=True)
        self.tree.column("type", width=100, anchor="center", stretch=False)
        self.tree.column("source", width=95, anchor="center", stretch=False)
        self.tree.grid(row=4, column=0, columnspan=3, sticky="nsew")
        ybar = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        ybar.grid(row=4, column=3, sticky="ns")
        self.tree.configure(yscrollcommand=ybar.set)

        buttons = ttk.Frame(tab)
        buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=10)
        # v5.2.186: final user-requested release order and visible numbering.
        # LIST CONTENTS is #1, MOD LOADER READY is #2, CLASSIC EXTRACT is #3.
        ttk.Button(buttons, text="1) LIST CONTENTS", command=self.list_contents).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="2) MOD LOADER READY",
            command=self.run_mod_loader_ready_extraction,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text="3) CLASSIC EXTRACT",
            command=self.run_classic_extraction,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(buttons, text="Open Output", command=self.open_output).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Open Extracted Pack", command=self.open_pack_browse).pack(side=tk.LEFT, padx=4)

        self.status_bar = ttk.Label(tab, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status_bar.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(2, 0))

        self.log_box = tk.Text(tab, height=5, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT, font=("Consolas", 9), wrap="word", selectbackground=ACCENT)
        self.log_box.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.log("Ready. LIST CONTENTS is #1, MOD LOADER READY is #2 and performs ownership-preserving WRAP extraction, CLASSIC EXTRACT is #3.")

    def _build_xbox_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)

        ttk.Label(tab, text="XBOX / XE SOURCE PACK (EXPERIMENTAL - ONE PACK ONLY)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.xbox_input_var).grid(row=0, column=1, sticky="ew", pady=4)
        xb_in = ttk.Frame(tab)
        xb_in.grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=4)
        ttk.Button(xb_in, text="Browse One Xbox Pack", command=self.browse_xbox_pack).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Label(tab, text="OUTPUT FOLDER").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.xbox_out_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse Output", command=self.browse_xbox_out).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=4)

        ttk.Label(
            tab,
            text=(
                "EXPERIMENTAL RELEASE OPTION: one Xbox/XE pack at a time only. No folders or ZIP batch input here. "
                "It extracts/lists Xbox animation payloads as source files. It never patches Xbox packs or proves PC boot compatibility."
            ),
            style="Muted.TLabel",
            wraplength=980,
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 8))

        xb_buttons = ttk.Frame(tab)
        xb_buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Button(xb_buttons, text="1) EXPERIMENTAL EXTRACT ONE XBOX PACK", command=self.run_xbox_extraction).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(xb_buttons, text="Open Xbox Output", command=self.open_xbox_output).pack(side=tk.LEFT, padx=4)
        ttk.Button(xb_buttons, text="Open Extracted ANIM Folder", command=self.open_xbox_anim_folder).pack(side=tk.LEFT, padx=4)

        columns = ("status", "name", "hash", "size", "family", "payload")
        self.xbox_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16)
        for col, label, width in (
            ("status", "Status", 150),
            ("name", "Animation Name", 320),
            ("hash", "Hash", 120),
            ("size", "Size", 90),
            ("family", "Family", 120),
            ("payload", "Extracted Payload", 430),
        ):
            self.xbox_tree.heading(col, text=label)
            self.xbox_tree.column(col, width=width, anchor="w")
        self.xbox_tree.grid(row=5, column=0, columnspan=3, sticky="nsew")
        xb_y = ttk.Scrollbar(tab, orient="vertical", command=self.xbox_tree.yview)
        xb_y.grid(row=5, column=3, sticky="ns")
        self.xbox_tree.configure(yscrollcommand=xb_y.set)

        self.xbox_status_bar = ttk.Label(tab, textvariable=self.xbox_status_var, relief=tk.SUNKEN, anchor="w")
        self.xbox_status_bar.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def browse_xbox_pack(self) -> None:
        p = filedialog.askopenfilename(
            title="Select ONE Xbox/XE source pack (experimental)",
            filetypes=[("Xbox/XE source packs", "*.XEPACK *.xepack *.XEAPK *.xeapk"), ("All files", "*.*")],
        )
        if p:
            self.xbox_input_var.set(p)

    def browse_xbox_folder(self) -> None:
        p = filedialog.askdirectory(title="Select Xbox source folder")
        if p:
            self.xbox_input_var.set(p)

    def browse_xbox_out(self) -> None:
        p = filedialog.askdirectory(title="Select Xbox extract output folder")
        if p:
            self.xbox_out_var.set(p)

    def browse_xbox_pc_compare_folder(self) -> None:
        p = filedialog.askdirectory(title="Select PC extracted character folder for one-pack compare")
        if p:
            self.xbox_pc_compare_var.set(p)

    def _xbox_pc_compare_folder(self) -> Optional[Path]:
        raw = self.xbox_pc_compare_var.get().strip().strip('"')
        if not raw:
            return None
        p = Path(raw)
        if not p.exists() or not p.is_dir():
            messagebox.showwarning("Missing PC folder", "Select a valid PC extracted character folder for the optional compare.")
            return None
        return p

    def _show_wrong_game_guard(self, pack: Path | None = None, exc: BaseException | None = None) -> None:
        self.log(wrong_game_detail(pack))
        if exc is not None:
            self.log(f"Guard reason: {exc}")
        self.status_var.set("SM3 pack route not recognized.")
        messagebox.showerror("SM3 pack route not recognized", WRONG_GAME_GUARD_MESSAGE)

    @staticmethod
    def _anim_name_key_from_any(value: str) -> str:
        import re
        raw = Path(str(value or '').replace('\\', '/')).name
        raw = re.sub(r'^\d+_', '', raw)
        raw = re.sub(r'^0x[0-9A-Fa-f]{8}[._-]', '', raw)
        if raw.lower().endswith('.anim'):
            raw = raw[:-5]
        return raw.lower().strip()

    def _write_csv_report(self, path: Path, rows: List[Dict[str, str]], fields: List[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

    def _xbox_input(self) -> Optional[Path]:
        raw = self.xbox_input_var.get().strip().strip('"')
        p = Path(raw) if raw else Path()
        if not raw or not p.exists():
            messagebox.showwarning("Missing Xbox input", "Select one Xbox/XE source pack first.")
            return None
        if p.is_dir():
            messagebox.showwarning(
                "Xbox extractor is single-pack only",
                "Release Xbox Extractor is experimental and only accepts ONE .XEPACK/.XEAPK file at a time. Xbox folders are saved for dev tools later.",
            )
            return None
        if p.suffix.lower() == ".zip":
            messagebox.showwarning(
                "Xbox extractor is single-pack only",
                "Release Xbox Extractor is experimental and does not accept ZIP/batch input. Extract or pick one .XEPACK/.XEAPK file instead.",
            )
            return None
        if p.suffix.lower() not in {".xepack", ".xeapk"}:
            messagebox.showwarning(
                "Unsupported Xbox pack type",
                "Select one .XEPACK or .XEAPK file. Other Xbox lab inputs are dev/research-only and hidden from release mode.",
            )
            return None
        return p

    def _xbox_out(self) -> Optional[Path]:
        raw = self.xbox_out_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing Xbox output", "Select an output folder for Xbox extraction first.")
            return None
        return Path(raw)

    def run_xbox_extraction(self) -> None:
        src = self._xbox_input()
        out = self._xbox_out()
        if src is None or out is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return
        self.running = True
        self.log("Running experimental single-pack Xbox animation extraction...")
        self.xbox_status_var.set("Running experimental single-pack Xbox extraction...")

        def task() -> None:
            try:
                out.mkdir(parents=True, exist_ok=True)
                result = xbox_backend.extract_xbox_animations(src, out, log=self.log)
                self.last_xbox_output_root = Path(result.get("output_root") or out)
                csv_path = Path(result.get("reports", {}).get("xbox_anim_library_csv", ""))
                self.xbox_rows = read_csv_rows(csv_path) if csv_path.exists() else []
                self.root.after(0, self.apply_xbox_rows)
                msg = f"[XBOX DONE] listed {result.get('anim_rows')} animations, extracted {result.get('anim_payloads_extracted')} payload(s), name-only {result.get('name_only_rows')}."
                self.xbox_status_var.set(msg)
                self.log(msg)
            except Exception as exc:
                self.log(traceback.format_exc())
                messagebox.showerror("Xbox extraction failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def compare_one_xbox_pack_to_pc_folder(self) -> None:
        src = self._xbox_input()
        out = self._xbox_out()
        pc_folder = self._xbox_pc_compare_folder()
        if src is None or out is None or pc_folder is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return
        self.running = True
        self.log("Running one-pack Xbox-vs-PC animation name compare...")
        self.xbox_status_var.set("Running one-pack Xbox-vs-PC compare...")

        def task() -> None:
            try:
                out.mkdir(parents=True, exist_ok=True)
                # Ensure we have a current one-pack extraction/library first.
                result = xbox_backend.extract_xbox_animations(src, out, log=self.log)
                self.last_xbox_output_root = Path(result.get("output_root") or out)
                csv_path = Path(result.get("reports", {}).get("xbox_anim_library_csv", ""))
                self.xbox_rows = read_csv_rows(csv_path) if csv_path.exists() else []

                compare_root = self.last_xbox_output_root / "00_XBOX_ONE_PACK_COMPARE"
                compare_root.mkdir(parents=True, exist_ok=True)
                pc_slots = xbox_backend.scan_pc_anim_slots(pc_folder) if hasattr(xbox_backend, 'scan_pc_anim_slots') else []

                xbox_by_name: Dict[str, List[Dict[str, str]]] = {}
                for r in self.xbox_rows:
                    key = self._anim_name_key_from_any(r.get("name") or r.get("safe_name") or r.get("payload_relpath") or "")
                    if key:
                        xbox_by_name.setdefault(key, []).append(r)
                pc_by_name: Dict[str, List[Dict[str, str]]] = {}
                for r in pc_slots:
                    key = str(r.get("pc_name") or self._anim_name_key_from_any(r.get("pc_relpath", "")))
                    if key:
                        pc_by_name.setdefault(key, []).append({k: str(v) for k, v in r.items()})

                xbox_names = set(xbox_by_name)
                pc_names = set(pc_by_name)
                xbox_only_names = sorted(xbox_names - pc_names)
                pc_only_names = sorted(pc_names - xbox_names)
                overlap_names = sorted(xbox_names & pc_names)

                xbox_only_rows: List[Dict[str, str]] = []
                for name in xbox_only_names:
                    for r in xbox_by_name[name]:
                        xbox_only_rows.append({
                            "name_key": name,
                            "xbox_name": r.get("name", ""),
                            "hash": r.get("hash", ""),
                            "size": r.get("size", ""),
                            "family_guess": r.get("family_guess", ""),
                            "status": r.get("status", ""),
                            "payload_relpath": r.get("payload_relpath", ""),
                            "note": "Xbox animation name not found in selected PC extracted character folder",
                        })
                pc_only_rows: List[Dict[str, str]] = []
                for name in pc_only_names:
                    for r in pc_by_name[name]:
                        pc_only_rows.append({
                            "name_key": name,
                            "pc_name": r.get("pc_name", ""),
                            "pc_hash": r.get("pc_hash", ""),
                            "pc_size": r.get("pc_size", ""),
                            "pc_family": r.get("pc_family", ""),
                            "pc_relpath": r.get("pc_relpath", ""),
                            "note": "PC animation name not found in selected one-pack Xbox extraction",
                        })
                overlap_rows: List[Dict[str, str]] = []
                for name in overlap_names:
                    overlap_rows.append({
                        "name_key": name,
                        "xbox_row_count": str(len(xbox_by_name[name])),
                        "pc_row_count": str(len(pc_by_name[name])),
                        "note": "Animation name appears in both Xbox pack and PC folder",
                    })

                self._write_csv_report(compare_root / "XBOX_ANIMS_NOT_ON_PC.csv", xbox_only_rows, ["name_key", "xbox_name", "hash", "size", "family_guess", "status", "payload_relpath", "note"])
                self._write_csv_report(compare_root / "PC_ONLY_ANIMS_NOT_IN_XBOX_PACK.csv", pc_only_rows, ["name_key", "pc_name", "pc_hash", "pc_size", "pc_family", "pc_relpath", "note"])
                self._write_csv_report(compare_root / "XBOX_PC_NAME_OVERLAP.csv", overlap_rows, ["name_key", "xbox_row_count", "pc_row_count", "note"])
                summary = {
                    "mode": "SM3_RELEASE_XBOX_ONE_PACK_VS_PC_COMPARE_v5_2_84",
                    "xbox_input": str(src),
                    "pc_extracted_character_folder": str(pc_folder),
                    "output_root": str(compare_root),
                    "xbox_rows": len(self.xbox_rows),
                    "xbox_unique_names": len(xbox_names),
                    "pc_rows": len(pc_slots),
                    "pc_unique_names": len(pc_names),
                    "xbox_not_on_pc_unique_names": len(xbox_only_names),
                    "pc_only_unique_names": len(pc_only_names),
                    "overlap_unique_names": len(overlap_names),
                    "reports": {
                        "xbox_not_on_pc": str(compare_root / "XBOX_ANIMS_NOT_ON_PC.csv"),
                        "pc_only": str(compare_root / "PC_ONLY_ANIMS_NOT_IN_XBOX_PACK.csv"),
                        "overlap": str(compare_root / "XBOX_PC_NAME_OVERLAP.csv"),
                    },
                    "rules": [
                        "This is an experimental one-pack compare only.",
                        "Xbox animations are source-only.",
                        "This compare does not patch Xbox or PC packs.",
                    ],
                }
                (compare_root / "XBOX_ONE_PACK_VS_PC_COMPARE_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                (compare_root / "XBOX_ONE_PACK_VS_PC_COMPARE_SUMMARY.txt").write_text(
                    "SM3 Xbox One-Pack vs PC Animation Name Compare\n"
                    "================================================\n\n"
                    f"Xbox input: {src}\n"
                    f"PC folder: {pc_folder}\n"
                    f"Xbox rows: {len(self.xbox_rows)}\n"
                    f"Xbox unique names: {len(xbox_names)}\n"
                    f"PC rows: {len(pc_slots)}\n"
                    f"PC unique names: {len(pc_names)}\n"
                    f"Xbox names not on PC: {len(xbox_only_names)}\n"
                    f"PC-only names not in Xbox pack: {len(pc_only_names)}\n"
                    f"Overlap names: {len(overlap_names)}\n\n"
                    "Reports:\n"
                    "- XBOX_ANIMS_NOT_ON_PC.csv\n"
                    "- PC_ONLY_ANIMS_NOT_IN_XBOX_PACK.csv\n"
                    "- XBOX_PC_NAME_OVERLAP.csv\n",
                    encoding="utf-8",
                )
                self.root.after(0, self.apply_xbox_rows)
                msg = f"[XBOX COMPARE DONE] Xbox-only names {len(xbox_only_names)} | PC-only names {len(pc_only_names)} | overlap {len(overlap_names)}."
                self.xbox_status_var.set(msg)
                self.log(msg)
                self.log(f"One-pack compare reports: {compare_root}")
            except Exception as exc:
                self.log(traceback.format_exc())
                messagebox.showerror("Xbox one-pack compare failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def apply_xbox_rows(self) -> None:
        if not hasattr(self, "xbox_tree"):
            return
        self.xbox_tree.delete(*self.xbox_tree.get_children())
        for r in self.xbox_rows:
            self.xbox_tree.insert(
                "",
                tk.END,
                values=(
                    r.get("status", ""),
                    r.get("name", ""),
                    r.get("hash", ""),
                    r.get("size", ""),
                    r.get("family_guess", ""),
                    r.get("payload_relpath", ""),
                ),
            )
        self.xbox_status_var.set(f"Showing {len(self.xbox_rows)} Xbox animation row(s).")

    def open_xbox_onepack_compare_reports(self) -> None:
        root = self.last_xbox_output_root
        if root:
            p = root / "00_XBOX_ONE_PACK_COMPARE"
            if p.exists():
                open_path(p)
                return
        self.open_xbox_output()

    def open_xbox_output(self) -> None:
        raw = self.xbox_out_var.get().strip().strip('"')
        if not self.last_xbox_output_root and not raw:
            messagebox.showinfo("No Xbox output folder", "Choose an Xbox output folder first.")
            return
        open_path(self.last_xbox_output_root or Path(raw))

    def open_xbox_anim_folder(self) -> None:
        root = self.last_xbox_output_root
        if root:
            p = root / "02_XBOX_ANIM_EXTRACTED" / "ANIM"
            if p.exists():
                open_path(p)
                return
        self.open_xbox_output()


    def _build_xbox_lab_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)

        ttk.Label(tab, text="XBOX LAB INPUT (DEV)").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.xbox_lab_input_var).grid(row=0, column=1, sticky="ew", pady=4)
        lab_in = ttk.Frame(tab)
        lab_in.grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=4)
        ttk.Button(lab_in, text="Browse Xbox Zip/Pack", command=self.browse_xbox_lab_pack).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(lab_in, text="Browse Xbox Folder", command=self.browse_xbox_lab_folder).pack(side=tk.LEFT)

        ttk.Label(tab, text="LAB OUTPUT FOLDER").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.xbox_lab_out_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse Output", command=self.browse_xbox_lab_out).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=4)

        ttk.Label(tab, text="PC EXTRACTED CHARACTER FOLDER (OPTIONAL)").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.xbox_lab_pc_slots_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse PC Slots", command=self.browse_xbox_lab_pc_slots).grid(row=2, column=2, sticky="ew", padx=(6, 0), pady=4)

        ttk.Label(
            tab,
            text=(
                "DEV OPTION: scan all Xbox/XE packs from a zip or folder, extract source-only animation payloads, "
                "and build candidate reports. If a PC extracted character folder is selected, the lab also builds "
                "same-name PC-slot matches and a safe NAS CSV for New Animation Swapper. This never patches Xbox packs."
            ),
            style="Muted.TLabel",
            wraplength=1000,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 8))

        lab_buttons = ttk.Frame(tab)
        lab_buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Button(lab_buttons, text="RUN XBOX LAB FULL SCAN (DEV)", command=self.run_xbox_lab_scan).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(lab_buttons, text="BUILD XBOX CANDIDATES / NAS CSV", command=self.build_xbox_lab_candidates).pack(side=tk.LEFT, padx=4)
        ttk.Button(lab_buttons, text="Open Lab Output", command=self.open_xbox_lab_output).pack(side=tk.LEFT, padx=4)
        ttk.Button(lab_buttons, text="Open Lab Reports", command=self.open_xbox_lab_reports).pack(side=tk.LEFT, padx=4)
        ttk.Button(lab_buttons, text="Open Candidate Reports", command=self.open_xbox_candidate_reports).pack(side=tk.LEFT, padx=4)
        ttk.Button(lab_buttons, text="Open Send-To-GPT Bundle", command=self.open_xbox_lab_bundle).pack(side=tk.LEFT, padx=4)

        columns = ("kind", "item", "count", "extra")
        self.xbox_lab_tree = ttk.Treeview(tab, columns=columns, show="headings", height=16)
        for col, label, width in (
            ("kind", "Report", 150),
            ("item", "Item", 520),
            ("count", "Count", 100),
            ("extra", "Extra", 430),
        ):
            self.xbox_lab_tree.heading(col, text=label)
            self.xbox_lab_tree.column(col, width=width, anchor="w")
        self.xbox_lab_tree.grid(row=5, column=0, columnspan=3, sticky="nsew")
        lab_y = ttk.Scrollbar(tab, orient="vertical", command=self.xbox_lab_tree.yview)
        lab_y.grid(row=5, column=3, sticky="ns")
        self.xbox_lab_tree.configure(yscrollcommand=lab_y.set)

        self.xbox_lab_status_bar = ttk.Label(tab, textvariable=self.xbox_lab_status_var, relief=tk.SUNKEN, anchor="w")
        self.xbox_lab_status_bar.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    def browse_xbox_lab_pack(self) -> None:
        p = filedialog.askopenfilename(
            title="Select Xbox/XE source pack or source zip for Xbox Lab",
            filetypes=[("Xbox/XE source packs", "*.XEPACK *.xepack *.XEAPK *.xeapk *.zip *.bin *.dat"), ("All files", "*.*")],
        )
        if p:
            self.xbox_lab_input_var.set(p)

    def browse_xbox_lab_folder(self) -> None:
        p = filedialog.askdirectory(title="Select Xbox source folder for Xbox Lab")
        if p:
            self.xbox_lab_input_var.set(p)

    def browse_xbox_lab_out(self) -> None:
        p = filedialog.askdirectory(title="Select Xbox Lab output folder")
        if p:
            self.xbox_lab_out_var.set(p)

    def browse_xbox_lab_pc_slots(self) -> None:
        p = filedialog.askdirectory(title="Select PC extracted character folder for Xbox candidate matching")
        if p:
            self.xbox_lab_pc_slots_var.set(p)

    def _xbox_lab_pc_slots(self) -> Optional[Path]:
        raw = self.xbox_lab_pc_slots_var.get().strip().strip('"')
        if not raw:
            return None
        p = Path(raw)
        if not p.exists():
            messagebox.showwarning("Missing PC slots folder", "The selected PC extracted character folder does not exist.")
            return None
        return p

    def _xbox_lab_input(self) -> Optional[Path]:
        raw = self.xbox_lab_input_var.get().strip().strip('"')
        p = Path(raw) if raw else Path()
        if not raw or not p.exists():
            messagebox.showwarning("Missing Xbox Lab input", "Select an Xbox/XE source zip, pack, or folder first.")
            return None
        return p

    def _xbox_lab_out(self) -> Optional[Path]:
        raw = self.xbox_lab_out_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing Xbox Lab output", "Select an output folder for Xbox Lab first.")
            return None
        return Path(raw)

    def run_xbox_lab_scan(self) -> None:
        src = self._xbox_lab_input()
        out = self._xbox_lab_out()
        if src is None or out is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor/lab is already running.")
            return
        self.running = True
        self.log("Running Xbox Lab full scan (dev option)...")
        self.xbox_lab_status_var.set("Running Xbox Lab full scan...")

        def task() -> None:
            try:
                out.mkdir(parents=True, exist_ok=True)
                result = xbox_backend.run_xbox_lab_scan(src, out, log=self.log, pc_slots_folder=self._xbox_lab_pc_slots())
                self.last_xbox_lab_output_root = Path(result.get("output_root") or out)
                self.root.after(0, lambda: self.apply_xbox_lab_summary(result))
                msg = (
                    f"[XBOX LAB DONE] rows {result.get('anim_rows')} | payloads {result.get('payload_rows')} | "
                    f"packs {result.get('extract_summary', {}).get('packs_parsed')} | duplicate names {result.get('duplicate_name_groups')}"
                )
                self.xbox_lab_status_var.set(msg)
                self.log(msg)
            except Exception as exc:
                self.log(traceback.format_exc())
                messagebox.showerror("Xbox Lab scan failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def apply_xbox_lab_summary(self, result: Dict[str, object]) -> None:
        if not hasattr(self, "xbox_lab_tree"):
            return
        self.xbox_lab_tree.delete(*self.xbox_lab_tree.get_children())
        self.xbox_lab_tree.insert("", tk.END, values=("summary", "animation rows", result.get("anim_rows"), "all Xbox Lab rows"))
        self.xbox_lab_tree.insert("", tk.END, values=("summary", "payload rows", result.get("payload_rows"), "usable source .anim payloads"))
        self.xbox_lab_tree.insert("", tk.END, values=("summary", "name-only/no-payload", result.get("name_only_or_no_payload_rows"), "research only"))
        self.xbox_lab_tree.insert("", tk.END, values=("summary", "duplicate name groups", result.get("duplicate_name_groups"), "names seen across multiple packs"))
        cand = result.get("candidate_builder", {}) if isinstance(result.get("candidate_builder", {}), dict) else {}
        if cand:
            self.xbox_lab_tree.insert("", tk.END, values=("candidate", "SAFE_FIRST candidates", cand.get("safe_first_candidates"), "best early Xbox source rows"))
            self.xbox_lab_tree.insert("", tk.END, values=("candidate", "character-pack candidates", cand.get("character_pack_candidates"), "CH_* source rows"))
            self.xbox_lab_tree.insert("", tk.END, values=("candidate", "PC same-name matches", cand.get("pc_same_name_match_candidates"), "requires optional PC folder"))
            self.xbox_lab_tree.insert("", tk.END, values=("candidate", "safe NAS rows", cand.get("safe_nas_rows"), "import into New Animation Swapper"))
        for family, count in sorted(dict(result.get("family_counts", {})).items(), key=lambda kv: str(kv[0])):
            self.xbox_lab_tree.insert("", tk.END, values=("family", family, count, ""))
        for status, count in sorted(dict(result.get("status_counts", {})).items(), key=lambda kv: str(kv[0])):
            self.xbox_lab_tree.insert("", tk.END, values=("status", status, count, ""))
        self.xbox_lab_status_var.set(f"Xbox Lab reports written under {result.get('reports', {}).get('lab_root', '')}")


    def _latest_xbox_lab_run_root(self) -> Optional[Path]:
        if self.last_xbox_lab_output_root and self.last_xbox_lab_output_root.exists():
            return self.last_xbox_lab_output_root
        out = Path(self.xbox_lab_out_var.get().strip().strip('"'))
        if out.exists():
            runs = sorted([p for p in out.glob("XBOX_ANIM_EXTRACT_*") if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
            if runs:
                self.last_xbox_lab_output_root = runs[0]
                return runs[0]
        return None

    def build_xbox_lab_candidates(self) -> None:
        root = self._latest_xbox_lab_run_root()
        if not root:
            messagebox.showwarning("No Xbox Lab run", "Run Xbox Lab first, or choose an output folder containing an XBOX_ANIM_EXTRACT_* lab run.")
            return
        try:
            result = xbox_backend.build_xbox_candidate_reports(root, pc_slots_folder=self._xbox_lab_pc_slots(), log=self.log)
            self.apply_xbox_candidate_summary(result)
            self.xbox_lab_status_var.set(f"Xbox candidate reports written: {result.get('reports', {}).get('candidate_root', '')}")
            self.log(f"[XBOX CANDIDATES] safe NAS rows {result.get('safe_nas_rows')} | PC matches {result.get('pc_same_name_match_candidates')} | SAFE_FIRST {result.get('safe_first_candidates')}")
        except Exception as exc:
            self.log(traceback.format_exc())
            messagebox.showerror("Xbox candidate build failed", str(exc))

    def apply_xbox_candidate_summary(self, result: Dict[str, object]) -> None:
        if not hasattr(self, "xbox_lab_tree"):
            return
        self.xbox_lab_tree.insert("", tk.END, values=("candidate", "SAFE_FIRST candidates", result.get("safe_first_candidates"), "best early Xbox source rows"))
        self.xbox_lab_tree.insert("", tk.END, values=("candidate", "character-pack candidates", result.get("character_pack_candidates"), "CH_* source rows"))
        self.xbox_lab_tree.insert("", tk.END, values=("candidate", "duplicate-name best sources", result.get("duplicate_name_best_sources"), "one recommended source per duplicated name"))
        self.xbox_lab_tree.insert("", tk.END, values=("candidate", "PC same-name matches", result.get("pc_same_name_match_candidates"), "requires optional PC folder"))
        self.xbox_lab_tree.insert("", tk.END, values=("candidate", "safe NAS rows", result.get("safe_nas_rows"), "import into New Animation Swapper"))

    def open_xbox_candidate_reports(self) -> None:
        root = self._latest_xbox_lab_run_root()
        if root:
            p = root / "00_XBOX_LAB_REPORTS" / "XBOX_CANDIDATE_BUILDER"
            if p.exists():
                open_path(p)
                return
        self.open_xbox_lab_reports()

    def open_xbox_lab_output(self) -> None:
        open_path(self.last_xbox_lab_output_root or Path(self.xbox_lab_out_var.get().strip().strip('"')))

    def open_xbox_lab_reports(self) -> None:
        root = self.last_xbox_lab_output_root
        if root:
            p = root / "00_XBOX_LAB_REPORTS"
            if p.exists():
                open_path(p)
                return
        self.open_xbox_lab_output()

    def open_xbox_lab_bundle(self) -> None:
        root = self.last_xbox_lab_output_root
        if root:
            p = root / "00_XBOX_LAB_REPORTS" / "XBOX_LAB_SEND_TO_GPT_REPORT_BUNDLE.zip"
            if p.exists():
                open_path(p)
                return
        self.open_xbox_lab_reports()

    def _build_info_tab(self, tab: ttk.Frame) -> None:
        msg = (
            "SM3 Pack Extractor - Clean Release Flow\n\n"
            "The PC Extractor has two separate output routes. The button name MOD LOADER READY is retained for compatibility, but it now performs native WRAP extraction.\n\n"
            "MOD LOADER READY - #2 WRAP ROUTE:\n"
            "- Extracts ownership-preserving standalone .wrap resources from the selected SM3 pack.\n"
            "- Keeps the real SM3 O#### / outer hash / T## APKF hierarchy.\n"
            "- Writes WRAP_EXTRACTS and _SM3_WRAP_EXTRACT_MANIFEST.json.\n"
            "- Intended for xeSM3/exWoS-style loose-resource mod workflows.\n\n"
            "CLASSIC EXTRACT:\n"
            "- Extracts the normal SM3 browsing/editing folders.\n"
            "- Use this for ordinary extracted resource work and toolkit workflows.\n\n"
            "Main workflow:\n"
            "1. Select one .PCPACK/.PCAPK/.APKF file.\n"
            "2. Select an output folder.\n"
            "3. Click MOD LOADER READY (#2) for WRAP extraction.\n"
            "4. LIST CONTENTS is #1; MOD LOADER READY is #2; CLASSIC EXTRACT remains #3.\n"
            "5. Use Open Output or Open Extracted Pack.\n\n"
            "Release rules:\n"
            "- One pack at a time.\n"
            "- Original pack files are never modified.\n"
            "- Temporary working files are cleaned automatically.\n\n"
            "Xbox Extractor (Experimental):\n"
            "- One Xbox/XE pack at a time.\n"
            "- Source-only extraction; it does not patch Xbox or PC packs.\n\n"
            "Safety:\n"
            "- Back up original files before testing rebuilt or patched packs.\n"
            "- Test one rebuilt/patched PCPACK at a time.\n"
        )
        tk.Message(tab, text=msg, width=900, bg=BG, fg=TEXT, font=("Segoe UI", 11)).pack(anchor="nw")

    def log(self, text: str) -> None:
        self.status_var.set(text)
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        if not self.quiet_var.get():
            self.root.update_idletasks()

    def browse_pack(self) -> None:
        p = filedialog.askopenfilename(title="Select Spider-Man 3 PC pack", filetypes=[("Spider-Man 3 packs", "*.PCPACK *.pcpack *.PCAPK *.pcapk *.APKF *.apkf"), ("All files", "*.*")])
        if p:
            self.pack_var.set(p)

    def browse_folder(self) -> None:
        p = filedialog.askdirectory(title="Select folder of Spider-Man 3 PC packs")
        if p:
            self.pack_var.set(p)

    def browse_out(self) -> None:
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.out_var.set(p)

    def _pack(self) -> Optional[Path]:
        raw = self.pack_var.get().strip().strip('"')
        p = Path(raw) if raw else Path()
        if not raw or not p.exists():
            messagebox.showwarning("Missing input", "Select one valid Spider-Man 3 PC pack first.")
            return None
        if p.is_dir():
            messagebox.showwarning(
                "Single-pack release extractor",
                "Pack Extractor works with one pack at a time. Select a single .PCPACK/.PCAPK/.APKF file, not a folder."
            )
            return None
        return p

    def _out(self) -> Optional[Path]:
        raw = self.out_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing output", "Select an output folder first.")
            return None
        return Path(raw)

    @staticmethod
    def _display_resource_filename(hash_value: str, name: str, extension: str, fallback_type: str = "") -> str:
        """Return the readable SM3 filename used by the extractor.

        Mirrors the useful WOS Toolkit presentation idea: keep resource identity in
        one filename-shaped string instead of splitting the hash away from the name.
        SM3 remains SM3-native (no .wrap naming is introduced).
        """
        h = (hash_value or "").strip()
        n = (name or "").strip()
        ext = (extension or "").strip()
        if ext and not ext.startswith("."):
            ext = "." + ext
        if n and ext and n.lower().endswith(ext.lower()):
            ext = ""
        if h and n:
            return f"{h}.{n}{ext}"
        if h:
            return f"{h}{ext or ('.' + fallback_type.lower() if fallback_type else '')}"
        if n:
            return f"{n}{ext}"
        return "unnamed" + (ext or ('.' + fallback_type.lower() if fallback_type else ''))

    @staticmethod
    def _outer_extension_from_row(row: Dict[str, str]) -> str:
        # Conservative display-only mapping for outer SM3 pack records. These are
        # the same families already recognized by the extraction backend.
        t = str(row.get("type_dec") or "").strip()
        if t == "36":
            return ".apkf"
        if t in {"3", "4"}:
            return ".hsam"
        return ".bin"

    def _reports_to_rows(self, reports: Path, pack_name: str = "") -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for r in read_csv_rows(reports / "OUTER_ROWS.csv"):
            known = (r.get("known_name") or "").strip()
            ftype = "T" + str(r.get("type_dec") or r.get("type_hex") or "?").strip()
            ext = self._outer_extension_from_row(r)
            # Do not invent a human-readable name when SM3 has not resolved one.
            # WOS likewise falls back to hash + extension when actualFilename is absent.
            filename = self._display_resource_filename(r.get("hash", ""), known, ext, fallback_type="bin")
            size = r.get("data_size_dec") or r.get("data_size", "")
            rows.append({
                "pack": pack_name,
                "idx": str(r.get("index", "")),
                "size": size,
                "filename": filename,
                "type": ftype,
                "source": "PACK",
                "family": friendly_family("", known),
                "resource": filename,
                "kind": "outer",
            })
        if self.apk_var.get():
            for r in read_csv_rows(reports / "INNER_APKF_FILES.csv"):
                name = (r.get("filename") or r.get("resource_name") or "").strip()
                ftype = (r.get("file_type") or r.get("resource_type") or "").upper().strip()
                ext = (r.get("extension") or r.get("resource_extension") or ("." + ftype.lower() if ftype else "")).strip()
                hash_value = (r.get("filename_hash") or r.get("resource_hash") or "").strip()
                filename = self._display_resource_filename(hash_value, name, ext, fallback_type=ftype)
                number = r.get("global_index") or r.get("local_index") or ""
                idx = f"*APK* {number}"
                size = r.get("total_component_size") or r.get("combined_raw_size") or ""
                rows.append({
                    "pack": pack_name,
                    "idx": idx,
                    "size": size,
                    "filename": filename,
                    "type": ftype,
                    "source": "APKF",
                    "family": friendly_family(ftype, name),
                    "resource": filename,
                    "kind": "apk",
                    "file_type": ftype,
                })
        return rows

    def _rows_from_preview_root(self, root: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        master = root / "00_MASTER_REPORTS" / "MASTER_EXTRACT_SUMMARY.csv"
        if master.exists():
            for m in read_csv_rows(master):
                out_dir = Path(str(m.get("out_dir") or ""))
                pack_name = str(m.get("pack") or out_dir.name or "")
                reports = out_dir / "00_REPORTS"
                rows.extend(self._reports_to_rows(reports, pack_name=pack_name))
        else:
            for pack_dir in sorted([p for p in root.iterdir() if p.is_dir() and p.name != "00_MASTER_REPORTS"], key=lambda p: p.name.lower()):
                rows.extend(self._reports_to_rows(pack_dir / "00_REPORTS", pack_name=pack_dir.name))
        return rows

    def _summary_text(self, rows: List[Dict[str, str]]) -> str:
        from collections import Counter
        fam = Counter(str(r.get("family") or "Review") for r in rows)
        if not fam:
            return "No extractable resources found."
        preferred = ["Textures", "Models", "Materials", "Animations", "Audio / Voice", "Data / Effects", "Outer / Review"]
        parts = [f"{k}: {fam[k]}" for k in preferred if fam.get(k)]
        parts.extend(f"{k}: {v}" for k, v in sorted(fam.items()) if k not in preferred)
        return " | ".join(parts)

    def apply_filter(self) -> None:
        q = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        count = 0
        for r in self.all_rows:
            hay = " ".join(str(v) for v in r.values()).lower()
            if q and q not in hay:
                continue
            self.tree.insert("", tk.END, values=(r.get("idx", ""), r.get("size", ""), r.get("filename", r.get("resource", "")), r.get("type", r.get("file_type", "")), r.get("source", "")))
            count += 1
        self.status_var.set(f"Showing {count} of {len(self.all_rows)} resources")

    def _backup_old_output(self, out_root: Path, pack: Path) -> None:
        pack_out = out_root / pack.stem
        if not self.force_var.get() or not pack_out.exists():
            return
        backups = out_root / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backups / f"{pack.stem}_output_{ts}"
        shutil.move(str(pack_out), str(dest))
        self.log(f"Old output backed up: {dest}")

    def list_contents(self) -> None:
        pack = self._pack()
        out_root = self._out()
        if pack is None or out_root is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return
        self.running = True
        self.log("Listing pack contents...")

        def task() -> None:
            try:
                if looks_like_wrong_game_or_unsupported_sm3_path(pack):
                    self.root.after(0, lambda: self._show_wrong_game_guard(pack))
                    return
                preview_root = out_root / "_SM3_LIST_PREVIEW"
                if preview_root.exists():
                    shutil.rmtree(preview_root, ignore_errors=True)
                data = pack.read_bytes()
                result = backend.extract_one_bytes(pack.name, data, preview_root, output_layout="smart_browse", write_payloads=False)
                self.preview_pack_output = Path(result.get("out_dir") or preview_root / pack.stem)
                self.all_rows = self._reports_to_rows(self.preview_pack_output / "00_REPORTS", pack_name=pack.name)
                summary = self._summary_text(self.all_rows)
                # Public release cleanup: List Contents should not leave preview/report folders behind.
                backend.clean_release_report_artifacts(preview_root, log=lambda _m: None)
                if preview_root.exists():
                    shutil.rmtree(preview_root, ignore_errors=True)
                self.preview_pack_output = None
                self.root.after(0, self.apply_filter)
                self.log(f"[LIST] {len(self.all_rows)} entries. {summary}")
            except Exception as exc:
                self.log(traceback.format_exc())
                if exception_suggests_wrong_game(exc):
                    self.root.after(0, lambda exc=exc: self._show_wrong_game_guard(pack, exc))
                else:
                    messagebox.showerror("List failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def scan_game_pack_folder(self) -> None:
        """Temporary whole-game metadata scan used to build SM3 master file lists."""
        if self.running:
            messagebox.showinfo("Busy", "The extractor/scanner is already running.")
            return
        src = filedialog.askdirectory(title="Select Spider-Man 3 game PACKS folder")
        if not src:
            return
        pack_folder = Path(src)

        out_raw = self.out_var.get().strip().strip('"')
        if out_raw:
            out_root = Path(out_raw)
        else:
            picked = filedialog.askdirectory(title="Select output folder for temporary SM3 pack scan data")
            if not picked:
                return
            out_root = Path(picked)
            self.out_var.set(str(out_root))

        self.running = True
        self.status_var.set("TEMP full-pack scan running... this may take a while on the complete game packs folder.")
        self.log(f"[TEMP PACK SCAN] Source folder: {pack_folder}")
        self.log(f"[TEMP PACK SCAN] Output folder: {out_root}")
        self.log("[TEMP PACK SCAN] Reading metadata only; source packs will not be modified and resource payloads will not be extracted.")

        def task() -> None:
            try:
                result = backend.scan_game_pack_folder_for_catalogs(
                    pack_folder,
                    out_root,
                    recursive=True,
                    log=self.log,
                )
                self.last_catalog_scan_root = Path(str(result.get("scan_root") or out_root))
                msg = (
                    f"TEMP pack scan complete: {result.get('packs_processed', 0)} pack(s), "
                    f"{result.get('outer_rows', 0)} outer row(s), "
                    f"{result.get('apkf_archives', 0)} APKF archive(s), "
                    f"{result.get('apkf_resources', 0)} APKF resource(s)."
                )
                self.status_var.set(msg)
                self.log(f"[TEMP PACK SCAN] {msg}")
                self.log(f"[TEMP PACK SCAN] filelist.txt + filelist.apkf.txt: {self.last_catalog_scan_root}")
                self.root.after(0, lambda: messagebox.showinfo(
                    "SM3 pack scan complete",
                    msg + "\n\nGenerated:\n- filelist.txt\n- filelist.apkf.txt\n- filelist.apkf.paths.txt\n- supporting CSV/JSON scan data",
                ))
            except Exception as exc:
                self.log(traceback.format_exc())
                self.status_var.set("TEMP full-pack scan failed. See log.")
                self.root.after(0, lambda exc=exc: messagebox.showerror("SM3 pack scan failed", str(exc)))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def open_catalog_scan(self) -> None:
        if self.last_catalog_scan_root and self.last_catalog_scan_root.exists():
            open_path(self.last_catalog_scan_root)
            return
        raw = self.out_var.get().strip().strip('"')
        if not raw:
            messagebox.showinfo("No scan data", "Run TEMP: SCAN GAME PACK FOLDER first.")
            return
        out_root = Path(raw)
        scans = []
        try:
            scans = sorted(
                [p for p in out_root.glob("SM3_FULL_PACK_SCAN_*") if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            scans = []
        if not scans:
            messagebox.showinfo("No scan data", "No SM3_FULL_PACK_SCAN_* folder was found in the selected output folder.")
            return
        self.last_catalog_scan_root = scans[0]
        open_path(scans[0])

    def scan_all_apkf_references(self) -> None:
        """TEMP whole-game APKF/material scan. Input is a PACK FOLDER, not one pack."""
        if self.running:
            messagebox.showinfo("Busy", "The extractor/scanner is already running.")
            return

        src = filedialog.askdirectory(title="Select Spider-Man 3 PACKS FOLDER for TEMP full APKF scan")
        if not src:
            return
        pack_folder = Path(src)

        out_raw = self.out_var.get().strip().strip('"')
        if out_raw:
            out_root = Path(out_raw)
        else:
            picked = filedialog.askdirectory(title="Select output folder for TEMP full APKF scan data")
            if not picked:
                return
            out_root = Path(picked)
            self.out_var.set(str(out_root))

        self.running = True
        self.status_var.set("TEMP CLEAN full APKF scan running from pack 1... old scans will not be reused.")
        self.log(f"[TEMP FULL APKF SCAN] PACK FOLDER: {pack_folder}")
        self.log(f"[TEMP FULL APKF SCAN] CHOOSE OUTPUT: {out_root}")
        self.log("[TEMP FULL APKF SCAN] CLEAN START: scanning every .PCPACK/.PCAPK/.APKF recursively from pack 1. Old scans are not reused.")

        def task() -> None:
            try:
                result = ref_backend.scan_pack_folder_references(
                    pack_folder,
                    out_root,
                    recursive=True,
                    log=self.log,
                )
                self.last_reference_dump_root = Path(str(result.get("scan_root") or out_root))
                db_root = str(result.get("database_root") or "")
                if db_root:
                    self.last_clean_database_root = Path(db_root)
                msg = (
                    f"TEMP clean APKF scan complete: {result.get('packs_processed', 0)}/"
                    f"{result.get('packs_discovered', 0)} pack(s), "
                    f"{result.get('apkf_archives', 0)} APKF archive(s), "
                    f"{result.get('pointer_relocations', 0)} relocation(s), "
                    f"{result.get('mesh_to_internal_mat_pointers', 0)} raw MESH->MAT row(s), "
                    f"{result.get('clean_mesh_to_mat_rows', 0)} clean MESH->MAT row(s), "
                    f"{result.get('clean_mat_to_tex_rows', 0)} clean MAT->TEX row(s)."
                )
                self.status_var.set(msg)
                self.log(f"[TEMP FULL APKF SCAN] {msg}")
                self.log(f"[TEMP FULL APKF SCAN] OUTPUT: {self.last_reference_dump_root}")
                output_text = str(self.last_reference_dump_root)
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "TEMP full APKF scan complete",
                        msg
                        + "\n\nAll output is under CHOOSE OUTPUT."
                        + "\n\nOpen CLEAN_DATABASE first. Raw MASTER_CSV is preserved for research."
                        + f"\n\n{output_text}",
                    ),
                )
            except Exception as exc:
                self.log(traceback.format_exc())
                self.status_var.set("TEMP full APKF pack-folder scan failed. See log.")
                self.root.after(0, lambda exc=exc: messagebox.showerror("TEMP full APKF scan failed", str(exc)))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def build_clean_database_existing(self) -> None:
        """TEMP v5.2.116: build production-oriented DBs from an existing completed full scan."""
        if self.running:
            messagebox.showinfo("Busy", "The extractor/scanner is already running.")
            return

        src = filedialog.askdirectory(
            title="Select completed TEMP_APKF_FULL_PACK_SCAN_* folder"
        )
        if not src:
            return
        scan_root = Path(src)
        if not (scan_root / "MASTER_CSV").exists():
            messagebox.showerror(
                "Not a completed full scan",
                "The selected folder does not contain MASTER_CSV.\n\n"
                "Select the TEMP_APKF_FULL_PACK_SCAN_* folder itself.",
            )
            return

        self.running = True
        self.status_var.set("Building v5.2.116 CLEAN_DATABASE from existing scan...")
        self.log(f"[116 CLEAN DB] Existing scan: {scan_root}")

        def task() -> None:
            try:
                result = clean_db_backend.build_clean_database(scan_root, log=self.log)
                self.last_reference_dump_root = scan_root
                self.last_clean_database_root = Path(str(result.get("database_root") or scan_root))
                msg = (
                    f"116 CLEAN_DATABASE complete: "
                    f"{result.get('mesh_to_mat_rows', 0)} MESH->MAT, "
                    f"{result.get('mat_to_tex_rows', 0)} MAT->TEX, "
                    f"{result.get('unique_resources', 0)} unique resources, "
                    f"{result.get('marker_reference_rows', 0)} marker refs isolated."
                )
                self.status_var.set(msg)
                self.log(f"[116 CLEAN DB] {msg}")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "v5.2.116 clean database complete",
                        msg
                        + "\n\nOPEN THIS FIRST:\n"
                        + str(self.last_clean_database_root)
                        + "\n\nRaw MASTER_CSV was not modified.",
                    ),
                )
            except Exception as exc:
                self.log(traceback.format_exc())
                self.status_var.set("v5.2.116 clean database build failed. See log.")
                self.root.after(
                    0,
                    lambda exc=exc: messagebox.showerror(
                        "v5.2.116 clean database build failed", str(exc)
                    ),
                )
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def open_clean_database(self) -> None:
        if self.last_clean_database_root and self.last_clean_database_root.exists():
            open_path(self.last_clean_database_root)
            return

        scan_root = None
        if self.last_reference_dump_root and self.last_reference_dump_root.exists():
            scan_root = self.last_reference_dump_root
        else:
            raw_out = self.out_var.get().strip().strip('"')
            if raw_out:
                out_root = Path(raw_out)
                try:
                    scans = sorted(
                        (p for p in out_root.glob("TEMP_APKF_FULL_PACK_SCAN_*") if p.is_dir()),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True,
                    )
                except Exception:
                    scans = []
                if scans:
                    scan_root = scans[0]

        if scan_root:
            try:
                dbs = sorted(
                    (p for p in scan_root.glob("CLEAN_DATABASE*") if p.is_dir() and not p.name.endswith("_BUILDING")),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            except Exception:
                dbs = []
            if dbs:
                self.last_clean_database_root = dbs[0]
                open_path(dbs[0])
                return

        messagebox.showinfo(
            "No clean database",
            "Run the full v5.2.116 scan or use:\n"
            "TEMP: BUILD 116 CLEAN DB FROM EXISTING SCAN",
        )

    def dump_apkf_references(self) -> None:
        """TEMP selected-pack APKF reference dump using the existing Choose Output field."""
        pack = self._pack()
        out_root = self._out()
        if pack is None or out_root is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor/scanner is already running.")
            return
        self.running = True
        self.status_var.set("TEMP APKF reference dump running on selected pack...")
        self.log(f"[TEMP APKF REF] Selected pack: {pack}")
        self.log(f"[TEMP APKF REF] CHOOSE OUTPUT: {out_root}")
        self.log("[TEMP APKF REF] No game files will be modified. Output will be written under the selected output folder.")

        def task() -> None:
            try:
                if looks_like_wrong_game_or_unsupported_sm3_path(pack):
                    self.root.after(0, lambda: self._show_wrong_game_guard(pack))
                    return
                result = ref_backend.dump_selected_pack_references(pack, out_root, log=self.log)
                self.last_reference_dump_root = Path(str(result.get("output_root") or out_root))
                msg = (
                    f"TEMP APKF analysis complete: {result.get('pointer_relocations', 0)} pointer relocation(s), "
                    f"{result.get('internal_mat_pointers', 0)} internal MAT pointer(s), "
                    f"{result.get('mesh_to_internal_mat_pointers', 0)} MESH->MAT row(s), "
                    f"{result.get('spiderman_mat_candidates', 0)} Spider-Man candidate row(s)."
                )
                self.status_var.set(msg)
                self.log(f"[TEMP APKF REF] {msg}")
                self.log(f"[TEMP APKF REF] OUTPUT: {self.last_reference_dump_root}")
                output_text = str(self.last_reference_dump_root)
                self.root.after(0, lambda: messagebox.showinfo(
                    "TEMP APKF reference dump complete",
                    msg + "\n\nOUTPUT WRITTEN TO CHOOSE OUTPUT:\n" + output_text +
                    "\n\nOpen first:\n- SPIDERMAN_MAT_MATCH_CANDIDATES.csv\n- MESH_TO_MAT_INTERNAL_POINTERS.csv\n- RESOURCE_RECORDS.csv\n- SUMMARY.txt",
                ))
            except Exception as exc:
                self.log(traceback.format_exc())
                self.status_var.set("TEMP APKF reference dump failed. See log.")
                self.root.after(0, lambda exc=exc: messagebox.showerror("TEMP APKF reference dump failed", str(exc)))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def open_reference_dump(self) -> None:
        if self.last_reference_dump_root and self.last_reference_dump_root.exists():
            open_path(self.last_reference_dump_root)
            return

        raw_out = self.out_var.get().strip().strip('"')
        if not raw_out:
            messagebox.showinfo(
                "No reference scan",
                "Choose OUTPUT FOLDER, then run TEMP: SELECT PACK FOLDER + SCAN + BUILD CLEAN DB.",
            )
            return

        out_root = Path(raw_out)
        # Prefer the newest whole-folder scan.
        try:
            scans = sorted(
                (p for p in out_root.glob('TEMP_APKF_FULL_PACK_SCAN_*') if p.is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            scans = []
        if scans:
            self.last_reference_dump_root = scans[0]
            open_path(scans[0])
            return

        # Backward-compatible selected-pack TEMP dump fallback.
        raw_pack = self.pack_var.get().strip().strip('"')
        if raw_pack:
            candidate = out_root / f"TEMP_APKF_REFERENCE_DUMP_{Path(raw_pack).stem}"
            if candidate.exists():
                self.last_reference_dump_root = candidate
                open_path(candidate)
                return

        messagebox.showinfo(
            "No reference scan",
            f"No TEMP_APKF_FULL_PACK_SCAN_* folder was found under:\n{out_root}",
        )

    def run_classic_extraction(self) -> None:
        self._run_extraction_mode("classic")

    def run_mod_loader_ready_extraction(self) -> None:
        """Public button name retained; v5.2.184 keeps it on WRAP extraction."""
        self._run_wrap_extraction()

    def _run_wrap_extraction(self) -> None:
        pack = self._pack()
        out_root = self._out()
        if pack is None or out_root is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return

        self.running = True
        self.last_extract_mode = "wrap"
        self.log("Running MOD LOADER READY WRAP extraction...")

        def task() -> None:
            try:
                if looks_like_wrong_game_or_unsupported_sm3_path(pack):
                    self.root.after(0, lambda: self._show_wrong_game_guard(pack))
                    return
                out_root.mkdir(parents=True, exist_ok=True)
                self._backup_old_output(out_root, pack)

                result = wrap_backend.run_wrap_extract(pack, out_root, log=self.log)
                self.last_output_root = out_root
                self.last_pack_output = Path(result["pack_root"])
                wrap_root = Path(result["wrap_root"])
                manifest = result.get("manifest", {}) if isinstance(result, dict) else {}

                # Keep the on-screen list useful without creating Classic report folders.
                self.all_rows = []
                for row in manifest.get("resources", []):
                    if not isinstance(row, dict) or row.get("status") != "OK":
                        continue
                    ftype = str(row.get("resource_type") or "").upper()
                    name = str(row.get("resource_name") or "")
                    h = str(row.get("resource_hash") or "")
                    ext = "." + ftype.lower() if ftype else ""
                    filename = self._display_resource_filename(h, name, ".wrap" + ext, fallback_type=ftype)
                    self.all_rows.append({
                        "pack": pack.name,
                        "idx": f"O{int(row.get('archive_index') or 0):04d}",
                        "size": str(row.get("wrap_size") or ""),
                        "filename": filename,
                        "type": ftype,
                        "source": "WRAP",
                        "family": friendly_family(ftype, name),
                        "resource": filename,
                        "kind": "wrap",
                        "file_type": ftype,
                    })
                self.root.after(0, self.apply_filter)

                written = int(manifest.get("wraps_written") or 0)
                skipped = int(manifest.get("resources_skipped") or 0)
                archive_errors = int(manifest.get("archive_parse_errors") or 0)
                self.log(f"[DONE] MOD LOADER READY WRAP extraction complete: {wrap_root}")
                self.log(
                    f"[WRAP SUMMARY] {written} WRAP resource(s) | skipped {skipped} | "
                    f"archive errors {archive_errors} | unresolved {manifest.get('unresolved_pointer_targets', 0)}"
                )
            except Exception as exc:
                self.log(traceback.format_exc())
                if exception_suggests_wrong_game(exc):
                    self.root.after(0, lambda exc=exc: self._show_wrong_game_guard(pack, exc))
                else:
                    self.root.after(0, lambda exc=exc: messagebox.showerror("WRAP extraction failed", str(exc)))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    # Backward-compatible internal alias: old callers now use the Classic route.
    def run_extraction(self) -> None:
        self.run_classic_extraction()

    def _run_extraction_mode(self, mode: str) -> None:
        pack = self._pack()
        out_root = self._out()
        if pack is None or out_root is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return
        if mode not in {"classic", "mod_loader_ready"}:
            raise ValueError(f"Unknown extraction mode: {mode}")

        self.running = True
        self.last_extract_mode = mode
        label = "CLASSIC" if mode == "classic" else "MOD LOADER READY"
        self.log(f"Running {label} extraction...")

        def task() -> None:
            try:
                if looks_like_wrong_game_or_unsupported_sm3_path(pack):
                    self.root.after(0, lambda: self._show_wrong_game_guard(pack))
                    return
                out_root.mkdir(parents=True, exist_ok=True)
                self._backup_old_output(out_root, pack)

                mod_only = mode == "mod_loader_ready"
                result_root = backend.run_extract(
                    [pack],
                    out_root,
                    recursive=False,
                    include_zips=False,
                    output_layout="smart_browse",
                    write_payloads=True,
                    create_mod_loader_ready=mod_only,
                    mod_loader_ready_only=mod_only,
                    log=self.log,
                )
                self.last_output_root = result_root
                self.last_pack_output = result_root / pack.stem

                # Read temporary metadata for the on-screen resource list before release cleanup.
                self.all_rows = self._reports_to_rows(self.last_pack_output / "00_REPORTS", pack_name=pack.name)
                summary = self._summary_text(self.all_rows)
                cleanup = backend.clean_release_report_artifacts(result_root, log=lambda _m: None)
                self.root.after(0, self.apply_filter)
                removed = cleanup.get("removed_count", 0) if isinstance(cleanup, dict) else 0

                if mode == "classic":
                    # Classic intentionally contains the old extraction folders and never 06.
                    ml_root = self.last_pack_output / "06_MOD_LOADER_READY"
                    if ml_root.exists():
                        shutil.rmtree(ml_root, ignore_errors=True)
                    tex_note = backend.write_tex_dds_release_notes(self.last_pack_output)
                    self.log(f"[DONE] CLASSIC extraction complete: {self.last_pack_output}")
                    if tex_note.get("tex_dds_note_written"):
                        self.log(f"[TEXTURES] {tex_note.get('dds_count')} raw DDS preview file(s). Use Tex Swapper for edit-ready texture modding.")
                else:
                    ml_root = self.last_pack_output / "06_MOD_LOADER_READY"
                    self.log(f"[DONE] MOD LOADER READY extraction complete: {ml_root if ml_root.exists() else self.last_pack_output}")
                    if ml_root.exists():
                        self.log("[MOD LOADER READY] Only the 06_MOD_LOADER_READY ownership output was kept.")
                    else:
                        self.log("[MOD LOADER READY] No ownership output was produced; this pack may not contain parsed inner APKF resources.")

                self.log(f"[SUMMARY] {len(self.all_rows)} listed resources. {summary}")
                self.log(f"[CLEAN RELEASE] Removed {removed} temporary report artifact(s).")
            except Exception as exc:
                self.log(traceback.format_exc())
                if exception_suggests_wrong_game(exc):
                    self.root.after(0, lambda exc=exc: self._show_wrong_game_guard(pack, exc))
                else:
                    self.root.after(0, lambda exc=exc: messagebox.showerror("Extraction failed", str(exc)))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def _current_pack_output(self) -> Optional[Path]:
        return self.last_pack_output or self.preview_pack_output

    def _family_counts(self) -> Dict[str, int]:
        from collections import Counter
        fam = Counter(str(r.get("family") or "Review") for r in self.all_rows)
        return dict(sorted(fam.items(), key=lambda kv: kv[0].lower()))

    def open_output(self) -> None:
        raw = self.out_var.get().strip().strip('"')
        if not self.last_output_root and not raw:
            messagebox.showinfo("No output folder", "Choose an output folder first.")
            return
        open_path(self.last_output_root or Path(raw))

    def open_pack_browse(self) -> None:
        p = self._current_pack_output()
        if not p:
            self.open_output()
            return
        # MOD LOADER READY now means WRAP extraction; open WRAP_EXTRACTS directly.
        if self.last_extract_mode == "wrap":
            wr = p / "WRAP_EXTRACTS"
            if wr.exists():
                open_path(wr)
                return
        # Backward-compatible fallback for any older in-process mod-loader run.
        if self.last_extract_mode == "mod_loader_ready":
            ml = p / "06_MOD_LOADER_READY"
            if ml.exists():
                open_path(ml)
                return
        open_path(p)
