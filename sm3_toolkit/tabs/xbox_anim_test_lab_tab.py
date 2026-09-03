from __future__ import annotations

import csv
from collections import Counter
import hashlib
import json
import re
import shutil
import threading
import traceback
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.services.new_animation_swapper_service import character_anim_csv_auto_test_patch
from sm3_toolkit.services import xbox_pack_extract_service as xbox_backend
from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path


class XboxAnimTestLabTab(ttk.Frame):
    """Temporary Xbox->PC animation test workflow.

    This tab is intentionally marked TEMP/DEV so it can be removed later. It
    wraps the proven New Animation Swapper NAS CSV patch backend but keeps the
    Xbox candidate test flow separate from the release UI while we validate
    Xbox source animations in-game.
    """

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=12)
        self.app_state = app_state
        self.original_pack_var = tk.StringVar()
        self.extracted_folder_var = tk.StringVar()
        self.nas_csv_var = tk.StringVar()
        self.clip_pc_slot_var = tk.StringVar()
        self.clip_xbox_anim_var = tk.StringVar()
        self.compare_xbox_source_var = tk.StringVar()
        self.compare_character_only_var = tk.BooleanVar(value=True)
        self.compare_candidates_per_xbox_var = tk.StringVar(value="3")
        self.out_dir_var = tk.StringVar(value="")
        self.max_rows_var = tk.StringVar(value="5")
        self.status_var = tk.StringVar(value="Temporary Xbox animation test lab ready. Strict Xbox replacement path mode is ON.")
        self._preview_rows: list[dict[str, str]] = []
        self._last_summary: dict | None = None
        self._running = False
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self, style="Body.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="Xbox Animation Test Lab (TEMP)",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Temporary test tab: Xbox .anim files are Replacement IN source only. "
                "PC destination slots are required. Final output is a new PC PCPACK. Remove this tab after the Xbox workflow is proven."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        setup = ttk.Frame(self, style="Card.TFrame", padding=10)
        setup.grid(row=1, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        setup.columnconfigure(4, weight=1)

        ttk.Label(setup, text="1) Original PC character PCPACK", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(setup, textvariable=self.original_pack_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(setup, text="Browse Pack", command=self.browse_original_pack).grid(row=0, column=2, sticky="ew", padx=4, pady=4)

        ttk.Label(setup, text="2) Extracted PC character folder", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(setup, textvariable=self.extracted_folder_var).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(setup, text="Browse Extracted", command=self.browse_extracted_folder).grid(row=1, column=2, sticky="ew", padx=4, pady=4)

        ttk.Label(setup, text="3) Xbox candidate NAS CSV", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(setup, textvariable=self.nas_csv_var).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(setup, text="Import Test NAS CSV", command=self.browse_nas_csv).grid(row=2, column=2, sticky="ew", padx=4, pady=4)

        ttk.Label(setup, text="4) Test output folder", style="CardLabel.TLabel").grid(row=0, column=3, sticky="w", padx=(14, 4), pady=4)
        ttk.Entry(setup, textvariable=self.out_dir_var).grid(row=0, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(setup, text="Browse Output", command=self.browse_output).grid(row=0, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(setup, text="Max rows", style="CardLabel.TLabel").grid(row=1, column=3, sticky="w", padx=(14, 4), pady=4)
        ttk.Entry(setup, textvariable=self.max_rows_var, width=10).grid(row=1, column=4, sticky="w", padx=4, pady=4)
        ttk.Label(setup, text="Start small. Test one patched PCPACK at a time.", style="Muted.TLabel").grid(row=1, column=5, sticky="w", padx=4, pady=4)

        buttons = ttk.Frame(setup, style="Card.TFrame")
        buttons.grid(row=3, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="5) Preview Test CSV", command=self.preview_csv).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="6) RUN SAFE XBOX TEST PATCHES", command=self.run_safe_test_threaded, style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(buttons, text="Open Output", command=self.open_output).pack(side="left", padx=6)
        ttk.Button(buttons, text="Open Results", command=self.open_results).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear Log", command=self.clear_log).pack(side="left", padx=6)

        ttk.Label(
            setup,
            text=(
                "Safe test mode only: same-size replacements copy directly; smaller replacements are padded; "
                "bigger replacements stay blocked. Original PC/Xbox packs are never modified."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=4, column=0, columnspan=6, sticky="w", padx=4, pady=(8, 0))

        workbook = ttk.Notebook(self)
        workbook.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

        preview_page = ttk.Frame(workbook, style="Body.TFrame", padding=8)
        preview_page.columnconfigure(0, weight=1)
        preview_page.rowconfigure(1, weight=1)
        workbook.add(preview_page, text="Test CSV Preview")
        ttk.Label(preview_page, text="Xbox Candidate NAS CSV Preview", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        preview_cols = ("enabled", "mode", "destination", "replacement", "note")
        self.preview_tree = ttk.Treeview(preview_page, columns=preview_cols, show="headings", height=14)
        for col, width in (("enabled", 70), ("mode", 120), ("destination", 310), ("replacement", 360), ("note", 420)):
            self.preview_tree.heading(col, text=col.title())
            self.preview_tree.column(col, width=width, anchor="w")
        self.preview_tree.grid(row=1, column=0, sticky="nsew")
        pv_scroll = ttk.Scrollbar(preview_page, orient="vertical", command=self.preview_tree.yview)
        pv_scroll.grid(row=1, column=1, sticky="ns")
        self.preview_tree.configure(yscrollcommand=pv_scroll.set)

        clip_page = ttk.Frame(workbook, style="Body.TFrame", padding=8)
        clip_page.columnconfigure(1, weight=1)
        clip_page.columnconfigure(4, weight=1)
        clip_page.rowconfigure(5, weight=1)
        workbook.add(clip_page, text="Clip Proof Lab")
        ttk.Label(clip_page, text="Xbox Clip Proof Lab", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        ttk.Label(
            clip_page,
            text=(
                "Goal: keep the PC slot identity/name/hash, but inject a different Xbox animation clip as the bytes. "
                "This proves whether the PC engine can play the Xbox clip data before we try harder Xbox-only name/resource work."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(0, 8))

        ttk.Label(clip_page, text="A) PC destination slot / Source OUT", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(clip_page, textvariable=self.clip_pc_slot_var).grid(row=2, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
        ttk.Button(clip_page, text="Browse PC Slot", command=self.browse_clip_pc_slot).grid(row=2, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(clip_page, text="B) Xbox clip / Replacement IN", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(clip_page, textvariable=self.clip_xbox_anim_var).grid(row=3, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
        ttk.Button(clip_page, text="Browse Xbox Clip", command=self.browse_clip_xbox_anim).grid(row=3, column=5, sticky="ew", padx=4, pady=4)

        clip_buttons = ttk.Frame(clip_page, style="Body.TFrame")
        clip_buttons.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(6, 8))
        ttk.Button(clip_buttons, text="1) ANALYZE CLIP PAIR", command=self.analyze_clip_pair).pack(side="left", padx=(0, 6))
        ttk.Button(clip_buttons, text="2) BUILD ONE-ROW CLIP NAS CSV", command=self.build_clip_proof_nas_csv).pack(side="left", padx=6)
        ttk.Button(clip_buttons, text="3) RUN ONE CLIP PROOF PATCH", command=self.run_clip_proof_threaded, style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(clip_buttons, text="Open Clip Lab Output", command=self.open_clip_lab_output).pack(side="left", padx=6)

        clip_cols = ("field", "pc_destination", "xbox_replacement", "verdict")
        self.clip_tree = ttk.Treeview(clip_page, columns=clip_cols, show="headings", height=13)
        for col, width in (("field", 220), ("pc_destination", 330), ("xbox_replacement", 330), ("verdict", 520)):
            self.clip_tree.heading(col, text=col.replace("_", " ").title())
            self.clip_tree.column(col, width=width, anchor="w")
        self.clip_tree.grid(row=5, column=0, columnspan=6, sticky="nsew")
        clip_scroll = ttk.Scrollbar(clip_page, orient="vertical", command=self.clip_tree.yview)
        clip_scroll.grid(row=5, column=6, sticky="ns")
        self.clip_tree.configure(yscrollcommand=clip_scroll.set)

        compare_page = ttk.Frame(workbook, style="Body.TFrame", padding=8)
        compare_page.columnconfigure(1, weight=1)
        compare_page.columnconfigure(4, weight=1)
        compare_page.rowconfigure(6, weight=1)
        workbook.add(compare_page, text="Xbox vs PC Missing")
        ttk.Label(compare_page, text="Xbox Character Pack Folder vs PC Character Pack Folder", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        ttk.Label(
            compare_page,
            text=(
                "Select an Xbox source folder/CSV with the debug/character Xbox packs and a PC folder containing extracted PC character packs. "
                "The compare finds Xbox clips not present in the PC resources and builds slot-injection NAS tests for Clip Proof Lab."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(0, 8))

        ttk.Label(compare_page, text="Xbox source folder / XBOX_ANIM_LIBRARY.csv / Xbox Lab run", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(compare_page, textvariable=self.compare_xbox_source_var).grid(row=2, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
        ttk.Button(compare_page, text="Browse Xbox Source", command=self.browse_compare_xbox_source).grid(row=2, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(compare_page, text="PC character folder root / one extracted PC character folder", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(compare_page, textvariable=self.extracted_folder_var).grid(row=3, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
        ttk.Button(compare_page, text="Browse PC Character Root", command=self.browse_extracted_folder).grid(row=3, column=5, sticky="ew", padx=4, pady=4)

        opts = ttk.Frame(compare_page, style="Body.TFrame")
        opts.grid(row=4, column=0, columnspan=6, sticky="ew", pady=(4, 8))
        ttk.Checkbutton(opts, text="Xbox character packs only (CH_*)", variable=self.compare_character_only_var).pack(side="left", padx=(0, 10))
        ttk.Label(opts, text="Candidates per Xbox-only clip:", style="CardLabel.TLabel").pack(side="left", padx=(0, 4))
        ttk.Entry(opts, textvariable=self.compare_candidates_per_xbox_var, width=8).pack(side="left", padx=(0, 12))
        ttk.Button(opts, text="1) RUN 4-CHAR XBOX VS PC COMPARE", command=self.scan_xbox_vs_pc_missing).pack(side="left", padx=(0, 6))
        ttk.Button(opts, text="2) BUILD XBOX-ONLY TEST NAS CSV", command=self.scan_xbox_vs_pc_missing).pack(side="left", padx=6)
        ttk.Button(opts, text="Open Compare Output", command=self.open_compare_output).pack(side="left", padx=6)

        compare_cols = ("report", "count", "details")
        self.compare_tree = ttk.Treeview(compare_page, columns=compare_cols, show="headings", height=13)
        for col, width in (("report", 300), ("count", 120), ("details", 780)):
            self.compare_tree.heading(col, text=col.title())
            self.compare_tree.column(col, width=width, anchor="w")
        self.compare_tree.grid(row=6, column=0, columnspan=6, sticky="nsew")
        compare_scroll = ttk.Scrollbar(compare_page, orient="vertical", command=self.compare_tree.yview)
        compare_scroll.grid(row=6, column=6, sticky="ns")
        self.compare_tree.configure(yscrollcommand=compare_scroll.set)

        results_page = ttk.Frame(workbook, style="Body.TFrame", padding=8)
        results_page.columnconfigure(0, weight=1)
        results_page.rowconfigure(1, weight=1)
        workbook.add(results_page, text="Patch Results")
        ttk.Label(results_page, text="Xbox Test Patch Results", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        result_cols = ("row", "status", "destination_size", "replacement_size", "replacement_source_kind", "final_patched_pack")
        self.results_tree = ttk.Treeview(results_page, columns=result_cols, show="headings", height=14)
        for col, width in (("row", 60), ("status", 220), ("destination_size", 110), ("replacement_size", 120), ("replacement_source_kind", 190), ("final_patched_pack", 620)):
            self.results_tree.heading(col, text=col.replace("_", " ").title())
            self.results_tree.column(col, width=width, anchor="w")
        self.results_tree.grid(row=1, column=0, sticky="nsew")
        rs_scroll = ttk.Scrollbar(results_page, orient="vertical", command=self.results_tree.yview)
        rs_scroll.grid(row=1, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=rs_scroll.set)

        log_page = ttk.Frame(workbook, style="Body.TFrame", padding=8)
        log_page.columnconfigure(0, weight=1)
        log_page.rowconfigure(0, weight=1)
        workbook.add(log_page, text="Log")
        self.log_text = tk.Text(
            log_page,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_page, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        footer = ttk.Frame(self, style="Card.TFrame", padding=8)
        footer.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var, style="CardLabel.TLabel").pack(anchor="w")
        self.log("Xbox Animation Test Lab ready. TEMP tab for Xbox->PC candidate testing only.")

    # ------------------------------------------------------------------
    # Xbox Clip Proof Lab helpers
    # ------------------------------------------------------------------

    def browse_clip_pc_slot(self) -> None:
        path = filedialog.askopenfilename(title="Select PC destination .anim slot", filetypes=[("Animation", "*.anim"), ("All files", "*.*")])
        if path:
            self.clip_pc_slot_var.set(path)

    def browse_clip_xbox_anim(self) -> None:
        path = filedialog.askopenfilename(title="Select Xbox replacement .anim clip", filetypes=[("Animation", "*.anim"), ("All files", "*.*")])
        if path:
            self.clip_xbox_anim_var.set(path)

    def _clip_pc_slot(self) -> Path:
        p = Path(self.clip_pc_slot_var.get().strip().strip('"'))
        if not p.exists() or not p.is_file():
            raise FileNotFoundError("Select a valid PC destination .anim slot first.")
        return p

    def _clip_xbox_anim(self) -> Path:
        p = Path(self.clip_xbox_anim_var.get().strip().strip('"'))
        if not p.exists() or not p.is_file():
            raise FileNotFoundError("Select a valid Xbox replacement .anim clip first.")
        return p

    @staticmethod
    def _file_sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _anim_key(path: Path) -> str:
        stem = path.name
        if stem.lower().endswith(".anim"):
            stem = stem[:-5]
        stem = re.sub(r"^\d+_", "", stem)
        stem = re.sub(r"^0x[0-9A-Fa-f]{8}[._-]", "", stem)
        return re.sub(r"[^a-z0-9]+", "", stem.lower())

    @staticmethod
    def _anim_hash(path: Path) -> str:
        m = re.search(r"0x[0-9A-Fa-f]{8}", path.name)
        return m.group(0).upper().replace("0X", "0x") if m else ""

    @staticmethod
    def _family_guess(name: str) -> str:
        low = name.lower()
        if any(k in low for k in ("atck", "atk", "punch", "kick", "combo", "counter", "ddg", "dodge", "hit", "webstrike")):
            return "combat"
        if any(k in low for k in ("swg", "swing", "slowswing", "webswing")):
            return "swing/web"
        if any(k in low for k in ("jmp", "jump", "land", "fall", "dive")):
            return "jump/fall"
        if any(k in low for k in ("wall", "crawl", "climb")):
            return "wall/crawl"
        if any(k in low for k in ("idle", "idl", "tap")):
            return "idle"
        if any(k in low for k in ("run", "walk", "sprint", "jog")):
            return "movement"
        return "unknown"

    def _clip_info(self, path: Path) -> dict:
        data = path.read_bytes()
        key = self._anim_key(path)
        return {
            "path": str(path),
            "name": path.name,
            "key": key,
            "hash": self._anim_hash(path),
            "family": self._family_guess(key),
            "size": len(data),
            "sha256": self._file_sha256(path),
            "magic_hex": data[:16].hex(" ").upper(),
            "magic_ascii": "".join(chr(b) if 32 <= b <= 126 else "." for b in data[:16]),
            "trailing_zero_bytes": len(data) - len(data.rstrip(b"\x00")),
            "looks_xbox_payload": "YES" if any(part.lower() in {"02_xbox_anim_extracted", "xbox_anim_extracted", "anim"} for part in path.parts) and "xbox" in str(path).lower() else ("YES" if "xbox" in str(path).lower() else "REVIEW"),
        }

    def _pc_anim_name_set(self) -> set[str]:
        try:
            root = self._extracted()
        except Exception:
            return set()
        out: set[str] = set()
        try:
            for p in root.rglob("*.anim"):
                if p.is_file():
                    out.add(self._anim_key(p))
        except Exception:
            pass
        return out

    def _clip_pair_report(self) -> dict:
        pc = self._clip_info(self._clip_pc_slot())
        xb = self._clip_info(self._clip_xbox_anim())
        pc_names = self._pc_anim_name_set()
        same_file = False
        try:
            same_file = Path(pc["path"]).resolve() == Path(xb["path"]).resolve()
        except Exception:
            same_file = pc["path"] == xb["path"]
        same_sha = pc["sha256"] == xb["sha256"]
        xbox_only_vs_pc_extract = xb["key"] not in pc_names if pc_names else "UNKNOWN_NO_PC_EXTRACT_SCAN"
        if same_file or same_sha:
            verdict = "BLOCKED_NO_OP_DESTINATION_EQUALS_REPLACEMENT_OR_SAME_BYTES"
            enabled = "0"
        elif int(xb["size"]) > int(pc["size"]):
            verdict = "BLOCKED_SAFE_MODE_XBOX_CLIP_BIGGER_THAN_PC_SLOT"
            enabled = "0"
        elif xbox_only_vs_pc_extract is True:
            verdict = "XBOX_ONLY_CLIP_FITS_PC_SLOT_SAFE_SIZE_TEST"
            enabled = "1"
        else:
            verdict = "XBOX_CLIP_FITS_PC_SLOT_SAFE_SIZE_TEST"
            enabled = "1"
        return {
            "mode": "XBOX_CLIP_PROOF_LAB_v5_2_79",
            "pc_destination": pc,
            "xbox_replacement": xb,
            "same_path_or_file": same_file,
            "same_sha256": same_sha,
            "xbox_only_vs_selected_pc_extract": xbox_only_vs_pc_extract,
            "size_delta_xbox_minus_pc": int(xb["size"]) - int(pc["size"]),
            "padding_bytes_if_safe": max(0, int(pc["size"]) - int(xb["size"])),
            "enabled_for_safe_csv": enabled,
            "verdict": verdict,
            "rule": "PC slot identity is preserved; Xbox clip bytes are Replacement IN only; original PC/Xbox packs are never modified.",
        }

    def analyze_clip_pair(self) -> dict | None:
        try:
            report = self._clip_pair_report()
            self.clip_tree.delete(*self.clip_tree.get_children())
            pc = report["pc_destination"]
            xb = report["xbox_replacement"]
            rows = [
                ("name", pc["name"], xb["name"], "PC slot name stays; Xbox clip bytes replace data"),
                ("normalized key", pc["key"], xb["key"], "Xbox-only? " + str(report["xbox_only_vs_selected_pc_extract"])),
                ("hash", pc["hash"], xb["hash"], "hash/name does not need to match for clip injection test"),
                ("family", pc["family"], xb["family"], "same family is lower risk; cross-family is higher risk"),
                ("size", pc["size"], xb["size"], f"delta={report['size_delta_xbox_minus_pc']} padding={report['padding_bytes_if_safe']}"),
                ("sha256", pc["sha256"][:16], xb["sha256"][:16], "same bytes blocked as no-op"),
                ("magic/first16", pc["magic_hex"], xb["magic_hex"], "quick clip/header comparison"),
                ("verdict", "", "", report["verdict"]),
            ]
            for row in rows:
                self.clip_tree.insert("", "end", values=row)
            out = self._clip_lab_output_dir()
            out.mkdir(parents=True, exist_ok=True)
            (out / "LAST_CLIP_PAIR_ANALYSIS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.status_var.set(f"Clip pair analysis: {report['verdict']}")
            self.log(f"Clip pair analysis: {report['verdict']}")
            return report
        except Exception as exc:
            messagebox.showerror("Clip pair analysis failed", str(exc))
            self.log(f"Clip pair analysis failed: {exc}")
            return None

    def _clip_lab_output_dir(self) -> Path:
        return self._out_dir() / "XBOX_CLIP_PROOF_LAB"

    def _destination_ref_for_clip_csv(self, pc_slot: Path) -> str:
        try:
            return str(pc_slot.resolve().relative_to(self._extracted().resolve())).replace("\\", "/")
        except Exception:
            return str(pc_slot)

    def build_clip_proof_nas_csv(self) -> Path | None:
        report = self.analyze_clip_pair()
        if not report:
            return None
        out = self._clip_lab_output_dir()
        out.mkdir(parents=True, exist_ok=True)
        pc_path = Path(report["pc_destination"]["path"])
        xb_path = Path(report["xbox_replacement"]["path"])
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", report["pc_destination"]["key"] or pc_path.stem)[:80]
        csv_path = out / f"CLIP_PROOF_{safe_name}.csv"
        counter = 1
        while csv_path.exists():
            csv_path = out / f"CLIP_PROOF_{safe_name}_{counter:03d}.csv"
            counter += 1
        row = {
            "enabled": report["enabled_for_safe_csv"],
            "mode": "slot_preserve",
            "destination": self._destination_ref_for_clip_csv(pc_path),
            "replacement": str(xb_path),
            "note": (
                f"XBOX_CLIP_PROOF_LAB; verdict={report['verdict']}; "
                f"pc_slot={report['pc_destination']['name']}; xbox_clip={report['xbox_replacement']['name']}; "
                f"xbox_only_vs_pc={report['xbox_only_vs_selected_pc_extract']}; "
                f"padding={report['padding_bytes_if_safe']}"
            ),
            "pc_size": report["pc_destination"]["size"],
            "xbox_size": report["xbox_replacement"]["size"],
            "xbox_only_vs_pc": report["xbox_only_vs_selected_pc_extract"],
            "verdict": report["verdict"],
        }
        fields = ["enabled", "mode", "destination", "replacement", "note", "pc_size", "xbox_size", "xbox_only_vs_pc", "verdict"]
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerow(row)
        self.nas_csv_var.set(str(csv_path))
        self.preview_csv()
        (out / "LAST_CLIP_PROOF_NAS_CSV.txt").write_text(str(csv_path), encoding="utf-8")
        self.log(f"Built one-row clip proof NAS CSV: {csv_path}")
        return csv_path

    def run_clip_proof_threaded(self) -> None:
        if self._running:
            messagebox.showinfo("Busy", "Xbox test patch is already running.")
            return
        csv_path = self.build_clip_proof_nas_csv()
        if not csv_path:
            return
        self._running = True
        self.status_var.set("Running one clip proof patch...")
        self.log("Starting one clip proof patch run...")

        def task() -> None:
            try:
                summary = character_anim_csv_auto_test_patch(
                    original_pack=self._pack(),
                    extracted_folder=self._extracted(),
                    csv_path=csv_path,
                    output_root=self._out_dir(),
                    max_rows=1,
                    allow_experimental_size_change=False,
                    replacement_allow_extracted_lookup=False,
                    block_same_destination_replacement=True,
                )
                self._write_xbox_test_alias_reports(summary)
                clip_out = self._clip_lab_output_dir()
                clip_out.mkdir(parents=True, exist_ok=True)
                (clip_out / "CLIP_PROOF_PATCH_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                self.after(0, lambda: self.apply_summary(summary))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Clip proof patch failed", str(exc)))
                self.log(f"Clip proof patch failed: {exc}")
                self.status_var.set("Clip proof patch failed.")
            finally:
                self._running = False
        threading.Thread(target=task, daemon=True).start()

    def open_clip_lab_output(self) -> None:
        try:
            open_path(self._clip_lab_output_dir())
        except Exception as exc:
            messagebox.showerror("Open Clip Lab output failed", str(exc))

    # ------------------------------------------------------------------
    # Xbox vs PC Missing Animation Scanner
    # ------------------------------------------------------------------

    @staticmethod
    def _anim_key_text(text: str) -> str:
        raw = Path(str(text or "").replace("\\", "/")).name
        if raw.lower().endswith(".anim"):
            raw = raw[:-5]
        raw = re.sub(r"^\d+_", "", raw)
        raw = re.sub(r"^0x[0-9A-Fa-f]{8}[._-]", "", raw)
        return re.sub(r"[^a-z0-9]+", "", raw.lower())

    @staticmethod
    def _character_hint_from_path(path_text: str) -> str:
        parts = str(path_text or "").replace("\\", "/").split("/")
        for part in reversed(parts):
            up = part.upper()
            if up.startswith("CH_") or "CH_SPIDERMAN" in up or "CH_BLACKSUIT" in up or "CH_PETER" in up or "GOBLIN" in up or "RVBBLACK" in up:
                return part
        return "UNKNOWN"

    @staticmethod
    def _looks_like_xbox_lab_folder(path: Path) -> bool:
        p = Path(path)
        return (p / "00_XBOX_EXTRACT_REPORTS").exists() or (p / "02_XBOX_ANIM_EXTRACTED").exists() or "XBOX_ANIM_EXTRACT" in p.name.upper()

    @staticmethod
    def _looks_like_pc_extract_folder(path: Path) -> bool:
        p = Path(path)
        if not p.exists() or not p.is_dir():
            return False
        return (p / "02_APKF_EXTRACTED_REAL_EXT").exists() or any(x.name.upper().startswith("CH_") and x.is_dir() for x in p.iterdir()) if p.exists() else False

    @staticmethod
    def _safe_int_text(value: object) -> int:
        try:
            return int(str(value or "0"))
        except Exception:
            return 0

    @staticmethod
    def _csv_write(path: Path, rows: list[dict], fields: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def browse_compare_xbox_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Xbox source ZIP, XBOX_ANIM_LIBRARY.csv, or cancel to choose Xbox source folder",
            filetypes=[("Xbox source / report", "*.zip *.csv *.XEPACK *.xepack *.XEAPK *.xeapk"), ("All files", "*.*")],
        )
        if not path:
            folder = filedialog.askdirectory(title="Select Xbox source folder, Xbox Lab run folder, or 02_XBOX_ANIM_EXTRACTED folder")
            if folder:
                path = folder
        if path:
            self.compare_xbox_source_var.set(path)

    def _compare_output_dir(self) -> Path:
        out = self._out_dir() / "XBOX_PC_CHARACTER_COMPARE"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _compare_auto_extract_root(self, label: str) -> Path:
        # v5.2.83: keep auto Xbox extraction OUTSIDE the verbose compare folder.
        # This prevents Windows path-length/WinError 3 payload write failures and
        # keeps replacement payloads available for the generated NAS CSV.
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label or "X")[:24]
        out = self._out_dir() / f"_X_{safe}"
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _compare_write_failure_report(self, exc: Exception, stage: str) -> None:
        out = self._compare_output_dir()
        data = {
            "mode": "SM3_XBOX_PC_COMPARE_FAILURE_v5_2_83",
            "stage": stage,
            "xbox_source": self.compare_xbox_source_var.get(),
            "pc_extracted_folder_or_root": self.extracted_folder_var.get(),
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "rule": "A complete compare run must create XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip. If only XBOX_ANIM_EXTRACT_*.zip exists, compare did not complete.",
        }
        (out / "COMPARE_FAILED_READ_THIS.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        (out / "COMPARE_FAILED_READ_THIS.txt").write_text(
            "Xbox vs PC Compare failed before final compare reports were created.\n"
            "============================================================\n\n"
            f"Stage: {stage}\n"
            f"Xbox source: {self.compare_xbox_source_var.get()}\n"
            f"PC source: {self.extracted_folder_var.get()}\n"
            f"Error: {exc}\n\n"
            "If you only see XBOX_ANIM_EXTRACT_*.zip, Xbox auto-extraction worked but the compare step failed or did not run.\n"
            "The fixed workflow should create XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip when the compare is complete.\n",
            encoding="utf-8",
        )
        failure_zip = out / "XBOX_PC_CHARACTER_COMPARE_FAILED_SEND_TO_GPT.zip"
        with zipfile.ZipFile(failure_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("COMPARE_FAILED_READ_THIS.txt", "COMPARE_FAILED_READ_THIS.json"):
                f = out / name
                if f.exists():
                    z.write(f, f.name)

    def _unpack_compare_zip(self, zip_path: Path, label: str) -> Path:
        dest = self._compare_output_dir() / f"_AUTO_UNPACK_{label}"
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest)
        return dest

    def _compare_candidates_per_xbox(self) -> int:
        raw = self.compare_candidates_per_xbox_var.get().strip() or "3"
        try:
            return max(1, min(20, int(raw)))
        except Exception:
            return 3

    def _resolve_xbox_library_csv_or_folder(self) -> tuple[Path, Path | None]:
        src = Path(self.compare_xbox_source_var.get().strip().strip('"'))
        if not src.exists():
            raise FileNotFoundError("Select an Xbox source folder, source zip, XBOX_ANIM_LIBRARY.csv, Xbox Lab run folder, or extracted Xbox anim folder first.")
        if src.is_file():
            low = src.name.lower()
            if low.endswith(".csv"):
                run_root = src.parent.parent if src.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
                self.log(f"Using Xbox compare CSV directly: {src}")
                return src, run_root
            if low.endswith(".zip"):
                # ZIP may be an already-created XBOX_ANIM_EXTRACT_*.zip or a raw Xbox source pack zip.
                unpacked = self._unpack_compare_zip(src, "XBOX_SOURCE_ZIP")
                csvs = list(unpacked.rglob("XBOX_ANIM_LIBRARY.csv"))
                if csvs:
                    candidate = csvs[0]
                    run_root = candidate.parent.parent if candidate.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
                    self.log(f"Using XBOX_ANIM_LIBRARY.csv from selected Xbox zip: {candidate}")
                    return candidate, run_root
                auto_root = self._compare_auto_extract_root("ZIP")
                result = xbox_backend.extract_xbox_animations(src, auto_root, log=self.log, compact_paths=True)
                csv_path = Path(str(result.get("reports", {}).get("xbox_anim_library_csv", "")))
                if not csv_path.exists():
                    raise FileNotFoundError("Xbox source zip auto-extraction finished but XBOX_ANIM_LIBRARY.csv was not created.")
                run_root = csv_path.parent.parent if csv_path.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
                self.log(f"Auto-extracted Xbox source zip for compare: {csv_path}")
                return csv_path, run_root
            # Single raw XEPACK/XEAPK source files are accepted through the extractor backend.
            if low.endswith((".xepack", ".xeapk")):
                auto_root = self._compare_auto_extract_root("ONEPACK")
                result = xbox_backend.extract_xbox_animations(src, auto_root, log=self.log, compact_paths=True)
                csv_path = Path(str(result.get("reports", {}).get("xbox_anim_library_csv", "")))
                if not csv_path.exists():
                    raise FileNotFoundError("Xbox single-pack extraction finished but XBOX_ANIM_LIBRARY.csv was not created.")
                run_root = csv_path.parent.parent if csv_path.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
                self.log(f"Auto-extracted Xbox single pack for compare: {csv_path}")
                return csv_path, run_root
            raise ValueError("Xbox source file must be XBOX_ANIM_LIBRARY.csv, XBOX_ANIM_EXTRACT_*.zip, Xbox source ZIP, or an Xbox/XE pack.")

        # Prefer an existing lab report CSV under a selected run/output folder.
        for candidate in [src / "00_XBOX_EXTRACT_REPORTS" / "XBOX_ANIM_LIBRARY.csv"] + list(src.rglob("XBOX_ANIM_LIBRARY.csv")):
            if candidate.exists():
                run_root = candidate.parent.parent if candidate.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
                self.log(f"Using existing Xbox library CSV for compare: {candidate}")
                return candidate, run_root

        # If the selected Xbox source folder contains raw Xbox/XE packs, auto-extract into the compare output.
        # v5.2.82: compare is not considered complete until XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip is written.
        pack_inputs = xbox_backend.discover_xbox_pack_inputs(src)
        if pack_inputs:
            auto_root = self._compare_auto_extract_root("SRC")
            result = xbox_backend.extract_xbox_animations(src, auto_root, log=self.log, compact_paths=True)
            csv_path = Path(str(result.get("reports", {}).get("xbox_anim_library_csv", "")))
            if not csv_path.exists():
                raise FileNotFoundError("Auto Xbox source extraction finished but XBOX_ANIM_LIBRARY.csv was not created.")
            run_root = csv_path.parent.parent if csv_path.parent.name == "00_XBOX_EXTRACT_REPORTS" else None
            self.log(f"Auto-extracted Xbox source folder for compare: {csv_path}")
            return csv_path, run_root

        # No CSV or packs; scan .anim files directly from folder.
        self.log(f"Using Xbox .anim folder scan fallback for compare: {src}")
        return src, None

    def _load_xbox_anim_rows_for_compare(self) -> tuple[list[dict], Path | None]:
        source, run_root = self._resolve_xbox_library_csv_or_folder()
        rows: list[dict] = []
        char_only = bool(self.compare_character_only_var.get())
        if source.is_file() and source.suffix.lower() == ".csv":
            with source.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pack = Path(str(row.get("parsed_candidate") or row.get("source_input") or "").replace("\\", "/")).name
                    pack_up = pack.upper()
                    if char_only and not (pack_up.startswith("CH_") or "_CH_" in pack_up or "CH_" in pack_up):
                        continue
                    name = str(row.get("name") or row.get("safe_name") or "")
                    key = self._anim_key_text(name)
                    if not key:
                        continue
                    payload_rel = str(row.get("payload_relpath") or "").strip()
                    payload_abs = ""
                    if payload_rel:
                        p = Path(payload_rel)
                        if p.is_absolute():
                            payload_abs = str(p)
                        elif run_root:
                            payload_abs = str((run_root / p).resolve())
                    rows.append({
                        "xbox_name": name,
                        "xbox_key": key,
                        "xbox_hash": row.get("hash", ""),
                        "xbox_size": str(row.get("size", "")),
                        "xbox_family": row.get("family_guess", self._family_guess(key)),
                        "xbox_risk_hint": row.get("risk_hint", ""),
                        "source_pack": pack,
                        "source_character": self._character_hint_from_path(pack),
                        "payload_relpath": payload_rel,
                        "payload_abs_path": payload_abs,
                        "payload_sha1": row.get("payload_sha1", ""),
                        "source_apkf_label": row.get("source_apkf_label", ""),
                    })
            return rows, run_root
        # Folder scan fallback for already-extracted Xbox .anim folders.
        folder = source
        for p in sorted(folder.rglob("*.anim"), key=lambda x: str(x).lower()):
            key = self._anim_key_text(p.name)
            if not key:
                continue
            try:
                rel = str(p.relative_to(folder)).replace("\\", "/")
            except Exception:
                rel = str(p)
            source_char = self._character_hint_from_path(rel)
            rows.append({
                "xbox_name": p.stem,
                "xbox_key": key,
                "xbox_hash": self._anim_hash(p),
                "xbox_size": str(p.stat().st_size),
                "xbox_family": self._family_guess(key),
                "xbox_risk_hint": "FOLDER_SCAN",
                "source_pack": source_char if source_char != "UNKNOWN" else folder.name,
                "source_character": source_char,
                "payload_relpath": rel,
                "payload_abs_path": str(p.resolve()),
                "payload_sha1": "",
                "source_apkf_label": "FOLDER_SCAN",
            })
        return rows, folder

    def _resolve_pc_compare_root(self) -> Path:
        raw = Path(self.extracted_folder_var.get().strip().strip('"'))
        if not raw.exists():
            raise FileNotFoundError("Select a PC extracted character folder, PC extracted character root, or extracted PC character zip first.")
        if raw.is_file():
            if raw.suffix.lower() != ".zip":
                raise ValueError("PC compare source file must be an extracted PC character zip. Raw PCPACKs must be extracted with Pack Extractor first.")
            root = self._unpack_compare_zip(raw, "PC_CHARACTER_ZIP")
            # If the zip contains one top folder, use the unpack root; recursive scan handles either way.
            self.log(f"Unpacked PC character zip for compare: {root}")
            return root
        return raw

    def _load_pc_anim_rows_for_compare(self) -> list[dict]:
        root = self._resolve_pc_compare_root()
        if self._looks_like_xbox_lab_folder(root):
            raise ValueError(
                "The PC field looks like an Xbox Lab output folder. Select a PC character extract folder, "
                "or a folder containing extracted PC character folders such as CH_SPIDERMAN / CH_BLACKSUIT / CH_PETER / CH_GOBLIN."
            )
        rows: list[dict] = []
        for p in sorted(root.rglob("*.anim"), key=lambda x: str(x).lower()):
            key = self._anim_key_text(p.name)
            if not key:
                continue
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except Exception:
                rel = str(p)
            source_char = self._character_hint_from_path(rel)
            rows.append({
                "pc_name": p.stem,
                "pc_key": key,
                "pc_hash": self._anim_hash(p),
                "pc_size": str(p.stat().st_size),
                "pc_family": self._family_guess(key),
                "pc_relpath": rel,
                "pc_abs_path": str(p.resolve()),
                "pc_character": source_char,
            })
        if not rows:
            raise FileNotFoundError(
                "No PC .anim files found. Select an extracted PC character folder/root. "
                "If you selected a raw PCPACK folder, extract those PCPACKs first with Pack Extractor."
            )
        self.log(f"Loaded PC compare rows: {len(rows)} from {root}")
        return rows

    def scan_xbox_vs_pc_missing(self) -> dict | None:
        try:
            xbox_rows, run_root = self._load_xbox_anim_rows_for_compare()
            pc_rows = self._load_pc_anim_rows_for_compare()
            out = self._compare_output_dir()
            pc_by_key: dict[str, list[dict]] = {}
            for row in pc_rows:
                pc_by_key.setdefault(row["pc_key"], []).append(row)
            xbox_by_key: dict[str, list[dict]] = {}
            for row in xbox_rows:
                xbox_by_key.setdefault(row["xbox_key"], []).append(row)

            xbox_missing_all = [r for r in xbox_rows if r["xbox_key"] not in pc_by_key]
            xbox_present = []
            for r in xbox_rows:
                if r["xbox_key"] in pc_by_key:
                    pc = pc_by_key[r["xbox_key"]][0]
                    merged = dict(r)
                    merged.update({"pc_relpath": pc.get("pc_relpath", ""), "pc_size": pc.get("pc_size", ""), "pc_family": pc.get("pc_family", ""), "pc_character": pc.get("pc_character", "")})
                    xbox_present.append(merged)
            pc_only = [r for r in pc_rows if r["pc_key"] not in xbox_by_key]

            def _risk_score(r: dict) -> tuple:
                risk = {"SAFE_FIRST": 0, "MEDIUM_RISK": 1, "HIGH_RISK": 2, "UNKNOWN": 3}.get(str(r.get("xbox_risk_hint") or "UNKNOWN"), 4)
                fam = 1 if str(r.get("xbox_family") or "unknown") == "unknown" else 0
                pack = 0 if str(r.get("source_pack") or "").upper().startswith("CH_") or "CH_" in str(r.get("source_pack") or "").upper() else 1
                try:
                    size = int(str(r.get("xbox_size") or 0))
                except Exception:
                    size = 0
                return (risk, pack, fam, size, str(r.get("xbox_key") or ""))

            xbox_missing_best: list[dict] = []
            for key, group in sorted({k: v for k, v in xbox_by_key.items() if k not in pc_by_key}.items()):
                best = sorted(group, key=_risk_score)[0].copy()
                best["duplicate_xbox_rows_for_name"] = str(len(group))
                best["all_source_packs_for_name"] = " | ".join(sorted({str(g.get("source_pack") or "") for g in group})[:12])
                xbox_missing_best.append(best)

            candidates: list[dict] = []
            nas_rows: list[dict] = []
            missing_payload_blocked: list[dict] = []
            per_xbox = self._compare_candidates_per_xbox()
            for xb in xbox_missing_best:
                payload_abs = str(xb.get("payload_abs_path") or "").strip()
                if not payload_abs or not Path(payload_abs).exists():
                    blocked = dict(xb)
                    blocked["candidate_status"] = "BLOCKED_NO_XBOX_PAYLOAD_PATH"
                    blocked["block_reason"] = "Xbox row has no exported payload path; cannot build a real Replacement IN. Re-run v5.2.83 compare/auto-extract or use a folder with extracted Xbox .anim payloads."
                    missing_payload_blocked.append(blocked)
                    continue
                try:
                    xb_size = int(str(xb.get("xbox_size") or 0))
                except Exception:
                    xb_size = 0
                xb_family = str(xb.get("xbox_family") or "unknown")
                fits = []
                for pc in pc_rows:
                    try:
                        pc_size = int(str(pc.get("pc_size") or 0))
                    except Exception:
                        pc_size = 0
                    if pc_size < xb_size:
                        continue
                    same_family = (xb_family != "unknown" and xb_family == str(pc.get("pc_family") or "unknown"))
                    # Prefer same-family fits. If none exist, fallback to any fit is handled later.
                    if same_family:
                        fit = dict(xb)
                        fit.update({
                            "candidate_status": "XBOX_ONLY_SAME_FAMILY_FITS_PC_SLOT",
                            "pc_relpath": pc.get("pc_relpath", ""),
                            "pc_character": pc.get("pc_character", ""),
                            "pc_name": pc.get("pc_name", ""),
                            "pc_key": pc.get("pc_key", ""),
                            "pc_size": pc.get("pc_size", ""),
                            "pc_family": pc.get("pc_family", ""),
                            "padding_bytes": str(pc_size - xb_size),
                        })
                        fits.append(fit)
                if not fits:
                    for pc in pc_rows:
                        try:
                            pc_size = int(str(pc.get("pc_size") or 0))
                        except Exception:
                            pc_size = 0
                        if pc_size >= xb_size:
                            fit = dict(xb)
                            fit.update({
                                "candidate_status": "XBOX_ONLY_CROSS_FAMILY_SIZE_FITS_REVIEW",
                                "pc_relpath": pc.get("pc_relpath", ""),
                                "pc_character": pc.get("pc_character", ""),
                                "pc_name": pc.get("pc_name", ""),
                                "pc_key": pc.get("pc_key", ""),
                                "pc_size": pc.get("pc_size", ""),
                                "pc_family": pc.get("pc_family", ""),
                                "padding_bytes": str(pc_size - xb_size),
                            })
                            fits.append(fit)
                fits.sort(key=lambda r: (0 if r["candidate_status"].startswith("XBOX_ONLY_SAME") else 1, int(str(r.get("padding_bytes") or 0))))
                for fit in fits[:per_xbox]:
                    candidates.append(fit)
                    if len([n for n in nas_rows if n.get("xbox_key") == xb.get("xbox_key")]) == 0:
                        nas_rows.append({
                            "enabled": "1",
                            "mode": "slot_preserve",
                            "destination": fit.get("pc_relpath", ""),
                            "replacement": fit.get("payload_abs_path", ""),
                            "note": f"XBOX_ONLY_CLIP_TEST; xbox={fit.get('xbox_name')}; pc_slot={fit.get('pc_name')}; status={fit.get('candidate_status')}; padding={fit.get('padding_bytes')}",
                            "source_character": fit.get("source_character", ""),
                            "xbox_key": fit.get("xbox_key", ""),
                            "xbox_name": fit.get("xbox_name", ""),
                            "pc_character": fit.get("pc_character", ""),
                            "pc_slot": fit.get("pc_relpath", ""),
                            "pc_size": fit.get("pc_size", ""),
                            "xbox_size": fit.get("xbox_size", ""),
                            "pc_family": fit.get("pc_family", ""),
                            "xbox_family": fit.get("xbox_family", ""),
                            "source_pack": fit.get("source_pack", ""),
                            "candidate_status": fit.get("candidate_status", ""),
                        })

            xbox_fields = ["source_character", "xbox_name", "xbox_key", "xbox_hash", "xbox_size", "xbox_family", "xbox_risk_hint", "source_pack", "payload_relpath", "payload_abs_path", "payload_sha1", "source_apkf_label", "duplicate_xbox_rows_for_name", "all_source_packs_for_name"]
            present_fields = xbox_fields + ["pc_character", "pc_relpath", "pc_size", "pc_family"]
            pc_fields = ["pc_character", "pc_name", "pc_key", "pc_hash", "pc_size", "pc_family", "pc_relpath", "pc_abs_path"]
            cand_fields = ["candidate_status", "source_character", "xbox_name", "xbox_key", "xbox_hash", "xbox_size", "xbox_family", "source_pack", "payload_relpath", "payload_abs_path", "pc_character", "pc_name", "pc_key", "pc_size", "pc_family", "pc_relpath", "padding_bytes", "xbox_risk_hint"]
            blocked_payload_fields = ["candidate_status", "block_reason", "source_character", "xbox_name", "xbox_key", "xbox_hash", "xbox_size", "xbox_family", "xbox_risk_hint", "source_pack", "payload_relpath", "payload_abs_path", "source_apkf_label"]
            nas_fields = ["enabled", "mode", "destination", "replacement", "note", "source_character", "xbox_key", "xbox_name", "pc_character", "pc_slot", "pc_size", "xbox_size", "pc_family", "xbox_family", "source_pack", "candidate_status"]

            def _counter_rows(counter: Counter, key_name: str) -> list[dict]:
                return [{key_name: str(k), "count": int(v)} for k, v in counter.most_common()]

            xbox_character_counts = Counter(str(r.get("source_character") or "UNKNOWN") for r in xbox_rows)
            pc_character_counts = Counter(str(r.get("pc_character") or "UNKNOWN") for r in pc_rows)
            xbox_only_character_counts = Counter(str(r.get("source_character") or "UNKNOWN") for r in xbox_missing_all)
            xbox_best_character_counts = Counter(str(r.get("source_character") or "UNKNOWN") for r in xbox_missing_best)
            self._csv_write(out / "XBOX_SOURCE_CHARACTER_COUNTS.csv", _counter_rows(xbox_character_counts, "source_character"), ["source_character", "count"])
            self._csv_write(out / "PC_CHARACTER_FOLDER_COUNTS.csv", _counter_rows(pc_character_counts, "pc_character"), ["pc_character", "count"])
            self._csv_write(out / "XBOX_ONLY_BY_SOURCE_CHARACTER_COUNTS.csv", _counter_rows(xbox_only_character_counts, "source_character"), ["source_character", "count"])
            self._csv_write(out / "XBOX_ONLY_BEST_BY_SOURCE_CHARACTER_COUNTS.csv", _counter_rows(xbox_best_character_counts, "source_character"), ["source_character", "count"])

            self._csv_write(out / "XBOX_ANIMS_NOT_PRESENT_IN_PC_ALL_ROWS.csv", xbox_missing_all, xbox_fields)
            self._csv_write(out / "XBOX_ANIMS_NOT_PRESENT_IN_PC_BEST_SOURCE.csv", xbox_missing_best, xbox_fields)
            self._csv_write(out / "XBOX_ANIMS_PRESENT_IN_PC.csv", xbox_present, present_fields)
            self._csv_write(out / "PC_ANIMS_NOT_PRESENT_IN_XBOX.csv", pc_only, pc_fields)
            self._csv_write(out / "XBOX_ONLY_CLIP_TEST_CANDIDATES.csv", candidates, cand_fields)
            self._csv_write(out / "XBOX_ONLY_NO_PAYLOAD_BLOCKED.csv", missing_payload_blocked, blocked_payload_fields)
            self._csv_write(out / "XBOX_ONLY_CLIP_TEST_CANDIDATES_NAS.csv", nas_rows, nas_fields)
            if missing_payload_blocked and not nas_rows:
                (out / "COMPARE_PAYLOADS_MISSING_READ_THIS.txt").write_text(
                    "Xbox-vs-PC compare found Xbox-only names, but no usable Xbox payload paths were exported.\n"
                    "The NAS CSV is intentionally empty/blocked because replacement paths would be blank.\n\n"
                    "Fix: re-run compare with v5.2.83 or newer, which uses short compact auto-extract paths, or select an Xbox Lab run/folder that contains real extracted .anim payload files.\n",
                    encoding="utf-8",
                )

            summary = {
                "mode": "SM3_XBOX_SOURCE_FOLDER_VS_PC_CHARACTER_FOLDER_COMPARE_v5_2_83_PAYLOAD_PATH_FIX",
                "xbox_source": self.compare_xbox_source_var.get(),
                "pc_extracted_folder_or_root": self.extracted_folder_var.get(),
                "character_packs_only": bool(self.compare_character_only_var.get()),
                "xbox_source_characters": sorted({str(r.get("source_character") or "UNKNOWN") for r in xbox_rows}),
                "pc_source_characters": sorted({str(r.get("pc_character") or "UNKNOWN") for r in pc_rows}),
                "xbox_rows_scanned": len(xbox_rows),
                "xbox_unique_names": len(xbox_by_key),
                "pc_rows_scanned": len(pc_rows),
                "pc_unique_names": len(pc_by_key),
                "xbox_only_all_rows": len(xbox_missing_all),
                "xbox_only_unique_best_sources": len(xbox_missing_best),
                "xbox_present_in_pc_rows": len(xbox_present),
                "pc_only_rows": len(pc_only),
                "xbox_only_clip_test_candidates": len(candidates),
                "xbox_only_missing_payload_blocked": len(missing_payload_blocked),
                "xbox_only_clip_test_nas_rows": len(nas_rows),
                "xbox_payload_rows_loaded": sum(1 for r in xbox_rows if str(r.get("payload_abs_path") or "").strip()),
                "output_folder": str(out),
                "reports": {
                    "xbox_only_all_rows": str(out / "XBOX_ANIMS_NOT_PRESENT_IN_PC_ALL_ROWS.csv"),
                    "xbox_only_best_source": str(out / "XBOX_ANIMS_NOT_PRESENT_IN_PC_BEST_SOURCE.csv"),
                    "xbox_present_in_pc": str(out / "XBOX_ANIMS_PRESENT_IN_PC.csv"),
                    "pc_only": str(out / "PC_ANIMS_NOT_PRESENT_IN_XBOX.csv"),
                    "clip_test_candidates": str(out / "XBOX_ONLY_CLIP_TEST_CANDIDATES.csv"),
                    "blocked_no_payload": str(out / "XBOX_ONLY_NO_PAYLOAD_BLOCKED.csv"),
                    "clip_test_nas": str(out / "XBOX_ONLY_CLIP_TEST_CANDIDATES_NAS.csv"),
                    "xbox_source_character_counts": str(out / "XBOX_SOURCE_CHARACTER_COUNTS.csv"),
                    "pc_character_folder_counts": str(out / "PC_CHARACTER_FOLDER_COUNTS.csv"),
                    "xbox_only_by_source_character_counts": str(out / "XBOX_ONLY_BY_SOURCE_CHARACTER_COUNTS.csv"),
                },
                "rule": "Xbox-only clips are still Replacement IN source only. The NAS CSV injects them into existing PC slots for Clip Proof testing; it does not add new Xbox animation names to PC.",
            }
            (out / "XBOX_PC_CHARACTER_COMPARE_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            (out / "XBOX_PC_CHARACTER_COMPARE_SUMMARY.txt").write_text(
                "Xbox vs PC Character Animation Compare\n"
                "=======================================\n\n"
                f"Xbox rows scanned: {len(xbox_rows)}\n"
                f"Xbox unique names: {len(xbox_by_key)}\n"
                f"PC rows scanned: {len(pc_rows)}\n"
                f"PC unique names: {len(pc_by_key)}\n"
                f"Xbox-only rows: {len(xbox_missing_all)}\n"
                f"Xbox-only unique/best sources: {len(xbox_missing_best)}\n"
                f"Xbox-only clip test candidates: {len(candidates)}\n"
                f"Xbox-only NAS rows: {len(nas_rows)}\n\n"
                "Rule: this finds Xbox animation names/clips not present in PC and builds slot-injection test candidates.\n",
                encoding="utf-8",
            )

            bundle = out / "XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip"
            with __import__("zipfile").ZipFile(bundle, "w", __import__("zipfile").ZIP_DEFLATED) as z:
                for f in sorted(out.rglob("*")):
                    if f.is_file() and f.resolve() != bundle.resolve():
                        z.write(f, f.relative_to(out).as_posix())
            summary["reports"]["send_to_gpt_bundle"] = str(bundle)
            # v5.2.82: make final compare output impossible to confuse with the auto Xbox extract zip.
            top_bundle = self._out_dir() / "OPEN_ME_XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip"
            try:
                shutil.copy2(bundle, top_bundle)
                summary["reports"]["top_level_compare_bundle_copy"] = str(top_bundle)
            except Exception:
                pass
            (out / "00_COMPARE_DONE_OPEN_THIS.txt").write_text(
                "Xbox vs PC compare completed successfully.\n"
                "Open XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip or the top-level OPEN_ME_XBOX_PC_CHARACTER_COMPARE_SEND_TO_GPT.zip.\n"
                "Do not judge the run by XBOX_ANIM_EXTRACT_*.zip alone; that is only the Xbox auto-extract step.\n",
                encoding="utf-8",
            )
            (out / "XBOX_PC_CHARACTER_COMPARE_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

            if hasattr(self, "compare_tree"):
                self.compare_tree.delete(*self.compare_tree.get_children())
                rows = [
                    ("Xbox rows scanned", len(xbox_rows), "raw Xbox animation rows after optional character-pack filter"),
                    ("Xbox source characters", len({str(r.get("source_character") or "UNKNOWN") for r in xbox_rows}), "character/debug pack hints from Xbox source"),
                    ("PC source characters", len({str(r.get("pc_character") or "UNKNOWN") for r in pc_rows}), "character folders detected in PC root"),
                    ("Xbox unique names", len(xbox_by_key), "normalized Xbox animation names"),
                    ("PC rows scanned", len(pc_rows), "PC .anim rows from selected extracted folder"),
                    ("PC unique names", len(pc_by_key), "normalized PC animation names"),
                    ("Xbox-only all rows", len(xbox_missing_all), "Xbox rows whose normalized name is not in selected PC extract"),
                    ("Xbox-only best sources", len(xbox_missing_best), "one best source row per Xbox-only animation name"),
                    ("Xbox-only test candidates", len(candidates), "existing PC slots that can fit Xbox-only clips by size"),
                    ("Xbox-only no-payload blocked", len(missing_payload_blocked), "Xbox-only rows blocked because no real .anim payload path exists"),
                    ("Xbox payload rows loaded", sum(1 for r in xbox_rows if str(r.get("payload_abs_path") or "").strip()), "rows with real Replacement IN payload paths"),
                    ("Xbox-only NAS rows", len(nas_rows), "first candidate per Xbox-only clip for safe slot-preserve testing"),
                ]
                for row in rows:
                    self.compare_tree.insert("", "end", values=row)
            if missing_payload_blocked and not nas_rows:
                self.status_var.set(f"Compare done but payloads missing: {len(missing_payload_blocked)} Xbox-only rows blocked, 0 NAS rows.")
            else:
                self.status_var.set(f"Xbox vs PC compare done: {len(xbox_missing_best)} Xbox-only names, {len(nas_rows)} NAS rows.")
            self.log(f"Xbox vs PC compare reports written: {out}")
            return summary
        except Exception as exc:
            self._compare_write_failure_report(exc, stage="scan_xbox_vs_pc_missing")
            messagebox.showerror("Xbox vs PC compare failed", str(exc))
            self.log(f"Xbox vs PC compare failed: {exc}")
            return None

    def open_compare_output(self) -> None:
        try:
            open_path(self._compare_output_dir())
        except Exception as exc:
            messagebox.showerror("Open compare output failed", str(exc))

    def browse_original_pack(self) -> None:
        path = filedialog.askopenfilename(title="Select original PC character PCPACK", filetypes=[("PCPACK", "*.PCPACK *.pcpack"), ("All files", "*.*")])
        if path:
            self.original_pack_var.set(path)

    def browse_extracted_folder(self) -> None:
        path = filedialog.askopenfilename(
            title="Select PC extracted character ZIP, or cancel to choose PC character folder/root",
            filetypes=[("Extracted PC character zip", "*.zip"), ("All files", "*.*")],
        )
        if not path:
            path = filedialog.askdirectory(title="Select extracted PC character folder or PC character root")
        if path:
            self.extracted_folder_var.set(path)

    def browse_nas_csv(self) -> None:
        path = filedialog.askopenfilename(title="Select Xbox candidate NAS CSV", filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if path:
            self.nas_csv_var.set(path)
            self.preview_csv()

    def browse_output(self) -> None:
        path = filedialog.askdirectory(title="Select Xbox test output folder")
        if path:
            self.out_dir_var.set(path)

    def _pack(self) -> Path:
        path = Path(self.original_pack_var.get().strip().strip('"'))
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Select a valid original PC character PCPACK first.")
        return path

    def _extracted(self) -> Path:
        path = Path(self.extracted_folder_var.get().strip().strip('"'))
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError("Select a valid extracted PC character folder first.")
        return path

    def _csv(self) -> Path:
        path = Path(self.nas_csv_var.get().strip().strip('"'))
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Select a valid Xbox candidate NAS CSV first.")
        return path

    def _out_dir(self) -> Path:
        path = Path(self.out_dir_var.get().strip().strip('"'))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _max_rows(self) -> int | None:
        raw = self.max_rows_var.get().strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except Exception:
            raise ValueError("Max rows must be a number, or blank for all rows.")
        return value if value > 0 else None

    def preview_csv(self) -> None:
        try:
            csv_path = self._csv()
            rows: list[dict[str, str]] = []
            with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=1):
                    row = {str(k or "").strip(): str(v or "") for k, v in row.items()}
                    row["_row"] = str(i)
                    rows.append(row)
            self._preview_rows = rows
            self.preview_tree.delete(*self.preview_tree.get_children())
            for row in rows[:500]:
                self.preview_tree.insert(
                    "",
                    "end",
                    values=(
                        row.get("enabled", ""),
                        row.get("mode", ""),
                        row.get("destination", ""),
                        row.get("replacement", ""),
                        row.get("note", ""),
                    ),
                )
            enabled = sum(1 for r in rows if str(r.get("enabled", "1")).strip().lower() not in {"0", "false", "no", "disabled", "skip"})
            self.status_var.set(f"Preview loaded: {len(rows)} rows, {enabled} enabled. Start with max rows 1-5.")
            self.log(f"Previewed Xbox test NAS CSV: {csv_path} | rows={len(rows)} enabled={enabled}")
        except Exception as exc:
            messagebox.showerror("Preview failed", str(exc))
            self.log(f"Preview failed: {exc}")

    def run_safe_test_threaded(self) -> None:
        if self._running:
            messagebox.showinfo("Busy", "Xbox test patch is already running.")
            return
        self._running = True
        self.status_var.set("Running safe Xbox test patches...")
        self.log("Starting Xbox safe test patch run...")

        def task() -> None:
            try:
                summary = character_anim_csv_auto_test_patch(
                    original_pack=self._pack(),
                    extracted_folder=self._extracted(),
                    csv_path=self._csv(),
                    output_root=self._out_dir(),
                    max_rows=self._max_rows(),
                    allow_experimental_size_change=False,
                    replacement_allow_extracted_lookup=False,
                    block_same_destination_replacement=True,
                )
                self._write_xbox_test_alias_reports(summary)
                self.after(0, lambda: self.apply_summary(summary))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Xbox test patch failed", str(exc)))
                self.log(f"Xbox test patch failed: {exc}")
                self.status_var.set("Xbox test patch failed.")
            finally:
                self._running = False
        threading.Thread(target=task, daemon=True).start()

    def _write_xbox_test_alias_reports(self, summary: dict) -> None:
        try:
            out_root = Path(str(summary.get("output_root") or ""))
            if out_root.exists():
                (out_root / "XBOX_TEST_TAB_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
                results_csv = Path(str(summary.get("results_csv") or ""))
                if results_csv.exists():
                    shutil.copy2(results_csv, out_root / "XBOX_NAS_PATCH_RESULTS.csv")
                (out_root / "00_XBOX_TEST_TAB_README.txt").write_text(
                    "Xbox Animation Test Lab Output\n"
                    "==============================\n\n"
                    "This was created by the temporary Xbox Animation Test Lab tab.\n"
                    "Test one patched PCPACK at a time in-game.\n"
                    "Xbox animations were used as Replacement IN source only.\n"
                    "PC destination slots were preserved.\n",
                    encoding="utf-8",
                )
        except Exception as exc:
            self.log(f"Could not write Xbox test alias reports: {exc}")

    def apply_summary(self, summary: dict) -> None:
        self._last_summary = summary
        self.results_tree.delete(*self.results_tree.get_children())
        for row in summary.get("results", []):
            self.results_tree.insert(
                "",
                "end",
                values=(
                    row.get("row", ""),
                    row.get("status", ""),
                    row.get("destination_size", ""),
                    row.get("replacement_size", ""),
                    row.get("replacement_source_kind", ""),
                    row.get("final_patched_pack", ""),
                ),
            )
        msg = f"Done: patched {summary.get('patched_count')} | blocked {summary.get('blocked_count')} | errors {summary.get('error_count')}"
        self.status_var.set(msg)
        self.log(msg)
        self.log(f"Output: {summary.get('output_root')}")
        try:
            open_path(Path(str(summary.get("output_root") or "")))
        except Exception:
            pass

    def open_output(self) -> None:
        try:
            open_path(self._out_dir())
        except Exception as exc:
            messagebox.showerror("Open output failed", str(exc))

    def open_results(self) -> None:
        if self._last_summary and self._last_summary.get("output_root"):
            open_path(Path(str(self._last_summary["output_root"])))
            return
        self.open_output()

    def clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def log(self, msg: str) -> None:
        try:
            self.log_text.insert("end", str(msg) + "\n")
            self.log_text.see("end")
        except Exception:
            pass
