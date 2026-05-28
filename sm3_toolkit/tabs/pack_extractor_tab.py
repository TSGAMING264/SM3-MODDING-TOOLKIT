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

APP_NAME = "SM3 Beta Pack Extractor"
APP_VERSION = "v2.31 No Report Folders UI"
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


class PackExtractorTab(ttk.Frame):
    def __init__(self, parent, app_state=None) -> None:
        super().__init__(parent, style="TFrame")
        self.app_state = app_state
        self.root = self

        self.pack_var = tk.StringVar(value="")
        self.out_var = tk.StringVar(value=str(Path.cwd() / "SM3_EXTRACT_OUTPUT"))
        self.search_var = tk.StringVar(value="")
        self.force_var = tk.BooleanVar(value=True)
        self.quiet_var = tk.BooleanVar(value=False)
        self.index_var = tk.BooleanVar(value=True)
        self.apk_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Select an SM3 PCPACK and output folder.")

        self.all_rows: List[Dict[str, str]] = []
        self.preview_pack_output: Optional[Path] = None
        self.last_output_root: Optional[Path] = None
        self.last_pack_output: Optional[Path] = None
        self.running = False

        self._style()
        self._build()

    def _style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 16, "bold"))
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6, background=PANEL2, foreground=TEXT, bordercolor="#596173")
        style.map("TButton", background=[("active", ACCENT_ACTIVE), ("pressed", ACCENT_DARK)], foreground=[("active", TEXT), ("pressed", "#ffffff")])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)], foreground=[("active", TEXT)])
        style.configure("Treeview", background=TREE_BG, foreground=TEXT, fieldbackground=TREE_BG, rowheight=24, font=("Consolas", 10), bordercolor="#3f4653")
        style.configure("Treeview.Heading", background=HEADING_BG, foreground=TEXT, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", "#394150")], foreground=[("active", TEXT)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 6), font=("Segoe UI", 10, "bold"), background=PANEL2, foreground=TEXT)
        style.map("TNotebook.Tab", background=[("selected", PANEL), ("active", ACCENT_ACTIVE)], foreground=[("selected", TEXT), ("active", TEXT)])
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=TEXT, insertcolor=TEXT, bordercolor="#596173")

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        ttk.Label(top, text="SM3 PACK EXTRACTOR", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Clean beta release UI - extraction only, original packs are never modified.", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")

        notebook = ttk.Notebook(outer)
        notebook.grid(row=1, column=0, sticky="nsew")
        extractor_tab = ttk.Frame(notebook, padding=8)
        info_tab = ttk.Frame(notebook, padding=12)
        notebook.add(extractor_tab, text="Extractor")
        notebook.add(info_tab, text="Info")

        self._build_extractor_tab(extractor_tab)
        self._build_info_tab(info_tab)

    def _build_extractor_tab(self, tab: ttk.Frame) -> None:
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(5, weight=1)

        ttk.Label(tab, text="INPUT PACK / PCPACK").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.pack_var).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse", command=self.browse_pack).grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=4)

        ttk.Label(tab, text="OUTPUT FOLDER").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(tab, textvariable=self.out_var).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(tab, text="Browse", command=self.browse_out).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=4)

        opts = ttk.Frame(tab)
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 8))
        ttk.Label(opts, text="OPTIONS", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(opts, text="Force", variable=self.force_var).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(opts, text="Quiet", variable=self.quiet_var).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(opts, text="Index", variable=self.index_var).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Checkbutton(opts, text="APK", variable=self.apk_var).pack(side=tk.LEFT, padx=(0, 16))

        search = ttk.Frame(tab)
        search.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Search:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ent = ttk.Entry(search, textvariable=self.search_var)
        ent.grid(row=0, column=1, sticky="ew")
        ent.bind("<KeyRelease>", lambda _e: self.apply_filter())
        ttk.Button(search, text="Clear", command=lambda: (self.search_var.set(""), self.apply_filter())).grid(row=0, column=2, padx=(6, 0))

        columns = ("idx", "resource", "size")
        self.tree = ttk.Treeview(tab, columns=columns, show="headings", height=18)
        self.tree.heading("idx", text="Index / APK")
        self.tree.heading("resource", text="Hash.Name.Extension")
        self.tree.heading("size", text="Size")
        self.tree.column("idx", width=150, anchor="w")
        self.tree.column("resource", width=780, anchor="w")
        self.tree.column("size", width=130, anchor="e")
        self.tree.grid(row=5, column=0, columnspan=3, sticky="nsew")
        ybar = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        ybar.grid(row=5, column=3, sticky="ns")
        self.tree.configure(yscrollcommand=ybar.set)

        buttons = ttk.Frame(tab)
        buttons.grid(row=6, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Button(buttons, text="List Contents", command=self.list_contents).pack(side=tk.LEFT, padx=(0, 8))
        run_btn = tk.Button(
            buttons,
            text="EXTRACT PACK",
            command=self.run_extraction,
            bg=EXTRACT_BG,
            fg="#f4f7fb",
            activebackground=EXTRACT_PRESSED,
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=6,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground="#555A64",
            highlightcolor="#6A707A",
        )
        run_btn.bind("<Enter>", lambda _e: run_btn.configure(bg=EXTRACT_HOVER))
        run_btn.bind("<Leave>", lambda _e: run_btn.configure(bg=EXTRACT_BG))
        run_btn.bind("<ButtonPress-1>", lambda _e: run_btn.configure(bg=EXTRACT_PRESSED))
        run_btn.bind("<ButtonRelease-1>", lambda _e: run_btn.configure(bg=EXTRACT_HOVER))
        run_btn.pack(side=tk.LEFT, padx=(8, 12))
        ttk.Button(buttons, text="Open Output", command=self.open_output).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="Open Pack Folder", command=self.open_pack_browse).pack(side=tk.LEFT, padx=4)

        self.status_bar = ttk.Label(tab, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        self.status_bar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(2, 0))

        self.log_box = tk.Text(tab, height=5, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT, font=("Consolas", 9), wrap="word", selectbackground=ACCENT)
        self.log_box.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        self.log("Ready. Select an SM3 pack and click List Contents or EXTRACT PACK.")

    def _build_info_tab(self, tab: ttk.Frame) -> None:
        msg = (
            "SM3 Beta Pack Extractor\n\n"
            "This is the clean release-style beta front end for the Spider-Man 3 PC pack extractor.\n\n"
            "Main workflow:\n"
            "1. Select one .PCPACK.\n"
            "2. Select an output folder.\n"
            "3. Click List Contents to preview resources.\n"
            "4. Click EXTRACT PACK.\n"
            "5. Use Open Output or Open Pack Folder.\n\n"
            "Clean release note:\n"
            "- Only Output and Pack Browse are shown in the main workflow.\n"
            "- No report folders or report zip bundles are kept in the output.\n"
            "- Internal temporary indexes are removed after the UI reads them.\n\n"
            "Safety:\n"
            "- Original PCPACK files are never modified.\n"
            "- Force backs up/replaces only the existing extracted output folder.\n"
            "- Research/dev controls are intentionally hidden in this beta UI.\n"
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

    def browse_out(self) -> None:
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.out_var.set(p)

    def _pack(self) -> Optional[Path]:
        raw = self.pack_var.get().strip().strip('"')
        p = Path(raw) if raw else Path()
        if not raw or not p.exists():
            messagebox.showwarning("Missing pack", "Select a valid Spider-Man 3 PC pack first.")
            return None
        return p

    def _out(self) -> Optional[Path]:
        raw = self.out_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing output", "Select an output folder first.")
            return None
        return Path(raw)

    def _reports_to_rows(self, reports: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for r in read_csv_rows(reports / "OUTER_ROWS.csv"):
            name = r.get("known_name") or f"outer_type_{r.get('type_hex','')}"
            res = f"{r.get('hash','')}.{name}"
            rows.append({"idx": r.get("index", ""), "resource": res, "size": r.get("data_size", ""), "kind": "outer"})
        if self.apk_var.get():
            for r in read_csv_rows(reports / "INNER_APKF_FILES.csv"):
                name = r.get("filename") or "unnamed"
                idx = "*APK*" + (r.get("global_index") or r.get("local_index") or "")
                size = r.get("total_component_size") or r.get("combined_raw_size") or ""
                rows.append({"idx": idx, "resource": name, "size": size, "kind": "apk"})
        return rows

    def apply_filter(self) -> None:
        q = self.search_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        count = 0
        for r in self.all_rows:
            hay = " ".join(str(v) for v in r.values()).lower()
            if q and q not in hay:
                continue
            self.tree.insert("", tk.END, values=(r.get("idx", ""), r.get("resource", ""), r.get("size", "")))
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
                preview_root = out_root / "_SM3_LIST_PREVIEW"
                if preview_root.exists():
                    shutil.rmtree(preview_root, ignore_errors=True)
                data = pack.read_bytes()
                result = backend.extract_one_bytes(pack.name, data, preview_root, output_layout="smart_browse", write_payloads=False)
                self.preview_pack_output = Path(result.get("out_dir") or preview_root / pack.stem)
                self.all_rows = self._reports_to_rows(self.preview_pack_output / "00_REPORTS")
                # Public release cleanup: List Contents should not leave preview/report folders behind.
                backend.clean_release_report_artifacts(preview_root, log=lambda _m: None)
                if preview_root.exists():
                    shutil.rmtree(preview_root, ignore_errors=True)
                self.preview_pack_output = None
                self.root.after(0, self.apply_filter)
                self.log(f"[LIST] {len(self.all_rows)} entries.")
            except Exception as exc:
                self.log(traceback.format_exc())
                messagebox.showerror("List failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def run_extraction(self) -> None:
        pack = self._pack()
        out_root = self._out()
        if pack is None or out_root is None:
            return
        if self.running:
            messagebox.showinfo("Busy", "The extractor is already running.")
            return
        self.running = True
        self.log("Running extraction...")

        def task() -> None:
            try:
                out_root.mkdir(parents=True, exist_ok=True)
                self._backup_old_output(out_root, pack)
                result_root = backend.run_extract([pack], out_root, recursive=True, include_zips=False, output_layout="smart_browse", write_payloads=True, log=self.log)
                self.last_output_root = result_root
                self.last_pack_output = result_root / pack.stem
                # Read the temporary reports for the on-screen list, then remove all report folders/zips.
                self.all_rows = self._reports_to_rows(self.last_pack_output / "00_REPORTS")
                cleanup = backend.clean_release_report_artifacts(result_root, log=lambda _m: None)
                self.root.after(0, self.apply_filter)
                removed = cleanup.get("removed_count", 0) if isinstance(cleanup, dict) else 0
                self.log(f"[DONE] Extraction complete: {self.last_pack_output}")
                self.log(f"[CLEAN] Removed {removed} temporary report artifact(s).")
            except Exception as exc:
                self.log(traceback.format_exc())
                messagebox.showerror("Extraction failed", str(exc))
            finally:
                self.running = False
        threading.Thread(target=task, daemon=True).start()

    def _current_pack_output(self) -> Optional[Path]:
        return self.last_pack_output or self.preview_pack_output

    def open_output(self) -> None:
        open_path(self.last_output_root or Path(self.out_var.get().strip().strip('"')))

    def open_pack_browse(self) -> None:
        p = self._current_pack_output()
        if not p:
            self.open_output()
            return
        # Release build keeps no 00_REPORTS folder, so open the extracted pack folder directly.
        open_path(p)



