from __future__ import annotations

import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.services.pcpack_rebuild_service import (
    run_no_change_rebuild_test,
    create_no_change_workspace,
    rebuild_no_change,
    rebuild_from_full_extract_tex_safe,
    verify_patched_pcpack,
    write_current_branch_rebuild_report,
    RebuildLabResult,
    PatchedPackReviewResult,
    FullExtractRebuildResult,
    detect_extracted_pack_folder,
    _looks_like_reportless_payload_extract,
)
from sm3_toolkit.sm3_pack_guard import WRONG_GAME_GUARD_MESSAGE, looks_like_wrong_game_or_unsupported_sm3_path, wrong_game_detail
from sm3_toolkit.theme import COLORS, refresh_tk_widget_colors
from sm3_toolkit.widgets import open_path


class PCPACKRebuildLabTab(ttk.Frame):
    """PCPACK Rebuild Lab - release UI with layout-faithful Repack Engine V2 backend."""

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=12)
        self.app_state = app_state
        self.pack_var = tk.StringVar()
        self.output_var = tk.StringVar(value="")
        self.extracted_folder_var = tk.StringVar()
        self.patched_pack_var = tk.StringVar()
        self.workspace_var = tk.StringVar()
        self.status_var = tk.StringVar(value="PCPACK Rebuild Lab ready. Release Mode.")
        self.last_result: RebuildLabResult | PatchedPackReviewResult | FullExtractRebuildResult | None = None
        self.running = False
        self._apply_rebuild_lab_styles()
        self._build()
        if self.app_state is not None:
            try:
                self.app_state.on_theme_change(lambda _theme: self._on_global_theme_changed())
            except Exception:
                pass

    def _apply_rebuild_lab_styles(self):
        """Match the rest of the toolkit and keep controls readable.

        v5.2.29 used a separate high-contrast palette that could render poorly on
        some Windows ttk themes. v5.2.30 uses the toolkit's normal dark palette
        and reliable tk.Entry/tk.Button widgets inside this tab only.
        """
        self.rebuild_colors = {
            "card": COLORS["panel"],
            "field": COLORS["field"],
            "text": COLORS["fg"],
            "muted": COLORS["muted"],
            "button": COLORS["button"],
            "button_hover": COLORS["button_hover"],
            "button_pressed": COLORS["button_pressed"],
            "accent": COLORS["accent"],
            "accent_hover": COLORS["accent_hover"],
            "accent_pressed": COLORS["accent_pressed"],
        }
        style = ttk.Style(self)
        style.configure("RebuildCard.TFrame", background=COLORS["panel"])
        style.configure("RebuildBody.TFrame", background=COLORS["bg"])
        style.configure("RebuildTitle.TLabel", background=COLORS["panel"], foreground=COLORS["fg"], font=("Segoe UI", 11, "bold"))
        style.configure("RebuildLabel.TLabel", background=COLORS["panel"], foreground=COLORS["fg"], font=("Segoe UI", 10))
        style.configure("RebuildHelp.TLabel", background=COLORS["panel"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("RebuildStatus.TLabel", background=COLORS["panel"], foreground=COLORS["fg"], font=("Segoe UI", 9))

    def _on_global_theme_changed(self) -> None:
        """Refresh custom tk controls after the global theme changes."""
        try:
            self._apply_rebuild_lab_styles()
        except Exception:
            pass
        try:
            refresh_tk_widget_colors(self)
        except Exception:
            pass

    def _entry(self, parent, variable: tk.StringVar) -> tk.Entry:
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            relief="solid",
            bd=1,
            highlightthickness=1,
            highlightbackground=COLORS.get("border", "#4B5563"),
            highlightcolor=COLORS.get("accent", "#6B7280"),
            font=("Segoe UI", 10),
        )
        return entry

    def _button(self, parent, text: str, command, accent: bool = False) -> tk.Button:
        if accent:
            bg = COLORS["accent"]
            active = COLORS["accent_hover"]
        else:
            bg = COLORS["button"]
            active = COLORS["button_hover"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=COLORS["fg"],
            activebackground=active,
            activeforeground=COLORS["fg"],
            relief="flat",
            bd=0,
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold" if accent else "normal"),
            cursor="hand2",
        )

    def _build(self):
        """Release-oriented Rebuild Lab UI.

        v5.2.94 keeps the step-based rebuild/verify workflow, but hides the
        older workspace/dev controls from the normal release UI. Those controls
        are preserved in code and documented as dev-build options for later.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="Body.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="PCPACK Rebuild Lab — Release Mode", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Rebuild a clean extracted pack into a new PCPACK. Original game packs are never modified.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        setup = ttk.Frame(self, style="RebuildCard.TFrame", padding=10)
        setup.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        setup.columnconfigure(1, weight=1)
        setup.columnconfigure(4, weight=1)

        ttk.Label(setup, text="1) Clean original PCPACK", style="RebuildLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.pack_var).grid(row=0, column=1, sticky="ew", padx=4, pady=5)
        self._button(setup, "Browse PCPACK", self.browse_pack).grid(row=0, column=2, sticky="ew", padx=4, pady=5)

        ttk.Label(setup, text="2) Clean extracted pack folder", style="RebuildLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._entry(setup, self.extracted_folder_var).grid(row=1, column=1, sticky="ew", padx=4, pady=5)
        self._button(setup, "Browse Extracted", self.browse_extracted_folder).grid(row=1, column=2, sticky="ew", padx=4, pady=5)
        self._button(setup, "Check / Auto-Find", self.check_extracted_folder).grid(row=1, column=3, sticky="ew", padx=4, pady=5)

        ttk.Label(setup, text="3) Output folder", style="RebuildLabel.TLabel").grid(row=0, column=3, sticky="w", padx=(14, 4), pady=4)
        self._entry(setup, self.output_var).grid(row=0, column=4, sticky="ew", padx=4, pady=5)
        self._button(setup, "Browse Output", self.browse_output).grid(row=0, column=5, sticky="ew", padx=4, pady=5)

        ttk.Label(setup, text="4) PCPACK to verify", style="RebuildLabel.TLabel").grid(row=1, column=4, sticky="w", padx=(14, 4), pady=4)
        self._entry(setup, self.patched_pack_var).grid(row=1, column=5, sticky="ew", padx=4, pady=5)
        self._button(setup, "Browse Verify Pack", self.browse_patched_pack).grid(row=1, column=6, sticky="ew", padx=4, pady=5)

        action_bar = ttk.Frame(setup, style="RebuildCard.TFrame")
        action_bar.grid(row=2, column=0, columnspan=7, sticky="ew", pady=(8, 0))
        for col in range(5):
            action_bar.columnconfigure(col, weight=1, uniform="release_rebuild_actions")
        self._button(action_bar, "1) CHECK / AUTO-FIND", self.check_extracted_folder).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._button(action_bar, "2) NO-CHANGE CONTROL", self.run_no_change_test, accent=True).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self._button(action_bar, "3) REBUILD EXTRACTED PACK", self.rebuild_full_extract_tex_safe, accent=True).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        self._button(action_bar, "4) VERIFY PCPACK", self.verify_patched_pack, accent=True).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        self._button(action_bar, "Open Output", self.open_output_folder).grid(row=0, column=4, sticky="ew", padx=4, pady=4)

        ttk.Label(
            setup,
            text=(
                "Release workflow: pick the clean original PCPACK, pick the extracted pack folder, "
                "choose output, then rebuild/verify a new PCPACK. The original is never edited."
            ),
            style="RebuildHelp.TLabel",
            wraplength=1200,
        ).grid(row=3, column=0, columnspan=7, sticky="w", padx=4, pady=(5, 0))

        self.pages = ttk.Notebook(self)
        self.pages.grid(row=2, column=0, sticky="nsew")

        # ------------------------------------------------------------------
        # Release rebuild page
        # ------------------------------------------------------------------
        release_page = ttk.Frame(self.pages, style="Body.TFrame", padding=10)
        release_page.columnconfigure(0, weight=1)
        self.pages.add(release_page, text="Release Rebuild")

        release_card = ttk.Frame(release_page, style="RebuildCard.TFrame", padding=12)
        release_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(release_card, text="What this page is for", style="RebuildTitle.TLabel").pack(anchor="w")
        ttk.Label(
            release_card,
            text=(
                "Use this page to rebuild a clean extracted pack into a new PCPACK. "
                "For release testing, run a no-change control first, then rebuild and verify the output."
            ),
            style="RebuildHelp.TLabel",
            wraplength=1150,
        ).pack(anchor="w", pady=(4, 0))

        steps = ttk.Frame(release_page, style="RebuildCard.TFrame", padding=12)
        steps.grid(row=1, column=0, sticky="ew")
        steps.columnconfigure(0, weight=1)
        ttk.Label(steps, text="Recommended order", style="RebuildTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        text = (
            "1. Check / Auto-Find the extracted folder.\n"
            "2. Run NO-CHANGE CONTROL if you want a clean route proof.\n"
            "3. Run REBUILD EXTRACTED PACK to create a new PCPACK.\n"
            "4. Use VERIFY PCPACK for a structure/review check.\n"
            "5. Boot-test one output at a time after backing up the original."
        )
        ttk.Label(steps, text=text, style="RebuildHelp.TLabel", wraplength=1150, justify="left").grid(row=1, column=0, sticky="w")

        # ------------------------------------------------------------------
        # Verify page
        # ------------------------------------------------------------------
        verify_page = ttk.Frame(self.pages, style="Body.TFrame", padding=10)
        verify_page.columnconfigure(0, weight=1)
        self.pages.add(verify_page, text="Verify / Review")
        verify_card = ttk.Frame(verify_page, style="RebuildCard.TFrame", padding=12)
        verify_card.grid(row=0, column=0, sticky="ew")
        verify_card.columnconfigure(1, weight=1)
        ttk.Label(verify_card, text="Verify a rebuilt or patched PCPACK", style="RebuildTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        ttk.Label(verify_card, text="Clean original PCPACK", style="RebuildLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._entry(verify_card, self.pack_var).grid(row=1, column=1, sticky="ew", padx=4, pady=5)
        self._button(verify_card, "Browse Original", self.browse_pack).grid(row=1, column=2, sticky="ew", padx=4, pady=5)
        ttk.Label(verify_card, text="Rebuilt / patched PCPACK", style="RebuildLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self._entry(verify_card, self.patched_pack_var).grid(row=2, column=1, sticky="ew", padx=4, pady=5)
        self._button(verify_card, "Browse Verify Pack", self.browse_patched_pack).grid(row=2, column=2, sticky="ew", padx=4, pady=5)
        self._button(verify_card, "VERIFY PCPACK", self.verify_patched_pack, accent=True).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4))
        self._button(verify_card, "Open Review Output", self.open_workspace).grid(row=3, column=2, sticky="ew", padx=4, pady=(8, 4))
        ttk.Label(
            verify_card,
            text="Verify does not prove an edit is game-compatible; it checks structure, route, size/row/marker changes, and writes review reports for troubleshooting.",
            style="RebuildHelp.TLabel",
            wraplength=1100,
        ).grid(row=4, column=0, columnspan=3, sticky="w", padx=4, pady=(8, 0))

        # ------------------------------------------------------------------
        # Advanced/dev controls are preserved as methods below, but hidden from
        # the normal release UI. See DEV_TABS_SAVED_FOR_LATER.txt.

        # ------------------------------------------------------------------
        # Log page
        # ------------------------------------------------------------------
        log_page = ttk.Frame(self.pages, style="Body.TFrame", padding=10)
        log_page.columnconfigure(0, weight=1)
        log_page.rowconfigure(1, weight=1)
        self.pages.add(log_page, text="Log / Troubleshoot")
        log_bar = ttk.Frame(log_page, style="RebuildCard.TFrame", padding=8)
        log_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(log_bar, text="Release troubleshooting log", style="RebuildTitle.TLabel").pack(side="left")
        self._button(log_bar, "Clear Log", self.clear_log).pack(side="right")
        body = ttk.Frame(log_page, style="Body.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.log_text = tk.Text(
            body,
            bg=self.rebuild_colors["field"],
            fg=self.rebuild_colors["text"],
            insertbackground=self.rebuild_colors["text"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(body, orient="vertical", command=self.log_text.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=ybar.set)

        footer = ttk.Frame(self, style="RebuildCard.TFrame", padding=8)
        footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var, style="RebuildStatus.TLabel").pack(anchor="w")
        self.log("Ready. Release flow: 1) original PCPACK, 2) extracted folder, 3) output, then rebuild/verify. Original PCPACKs are never modified.")

    def browse_pack(self):
        path = filedialog.askopenfilename(
            title="Select original SM3 PCPACK",
            filetypes=[("SM3 PCPACK", "*.PCPACK *.pcpack"), ("All files", "*.*")],
        )
        if path:
            self.pack_var.set(path)

    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Rebuild Lab output folder")
        if folder:
            self.output_var.set(folder)

    def browse_extracted_folder(self):
        folder = filedialog.askdirectory(title="Select extracted SM3 pack folder or parent output root")
        if folder:
            self.extracted_folder_var.set(folder)
            # Try to auto-resolve immediately, but keep the selected folder if it is not a Pack Extractor output yet.
            try:
                self.check_extracted_folder(show_popup=False)
            except Exception:
                pass

    def check_extracted_folder(self, show_popup: bool = True):
        raw = self.extracted_folder_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning(
                "Missing extracted folder",
                "Choose the extracted SM3 pack folder. The rebuild engine accepts 02_APKF_EXTRACTED_REAL_EXT / 05_TEX_DDS_EXPORT / 06_MOD_LOADER_READY layouts. INNER_APKF_FILES.csv is optional and is not required to build.",
            )
            return
        selected = Path(raw)
        pack_path = None
        pack_raw = self.pack_var.get().strip().strip('"')
        if pack_raw and Path(pack_raw).exists() and Path(pack_raw).is_file():
            pack_path = Path(pack_raw)
        try:
            detection = detect_extracted_pack_folder(selected, pack_path)
            self.extracted_folder_var.set(detection.resolved_folder)
            self.log(f"Extracted folder OK: {detection.resolved_folder}")
            self.log("Rebuild map source: clean original PCPACK (direct parse; CSV not required)")
            if detection.inner_csv:
                self.log(f"Optional legacy CSV found: {detection.inner_csv}")
            if detection.candidate_count > 1:
                self.log(f"Auto-find candidates: {detection.candidate_count}; chose best match for original pack.")
            for note in detection.notes:
                self.log(f"- {note}")
            if show_popup:
                messagebox.showinfo("Extracted folder found", f"Using:\n{detection.resolved_folder}\n\nRebuild map:\nDirectly parsed from the clean original PCPACK.\nCSV is optional.")
        except Exception as exc:
            self.log(f"Extracted folder problem: {exc}")
            if show_popup:
                messagebox.showerror("Extracted folder problem", str(exc))

    def browse_patched_pack(self):
        path = filedialog.askopenfilename(
            title="Select patched PCPACK output to review",
            filetypes=[("SM3 PCPACK", "*.PCPACK *.pcpack"), ("All files", "*.*")],
        )
        if path:
            self.patched_pack_var.set(path)

    def _pack(self) -> Path | None:
        path = Path(self.pack_var.get().strip().strip('"'))
        if not path.exists() or not path.is_file():
            messagebox.showwarning("Missing PCPACK", "Choose a valid original PCPACK first.")
            return None
        if looks_like_wrong_game_or_unsupported_sm3_path(path):
            self.log(wrong_game_detail(path))
            messagebox.showerror("SM3 pack route not recognized", WRONG_GAME_GUARD_MESSAGE)
            return None
        return path

    def _patched_pack(self) -> Path | None:
        path = Path(self.patched_pack_var.get().strip().strip('"'))
        if not path.exists() or not path.is_file():
            messagebox.showwarning("Missing rebuilt/patched PCPACK", "Choose a valid rebuilt/patched PCPACK output to review first.")
            return None
        return path

    def _extracted_folder(self) -> Path | None:
        raw = self.extracted_folder_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing extracted folder", "Choose the extracted SM3 pack folder first. CSV reports are optional; the build map comes directly from the clean original PCPACK.")
            return None
        folder = Path(raw)
        if not folder.exists() or not folder.is_dir():
            messagebox.showwarning("Missing extracted folder", "The extracted pack folder does not exist.")
            return None
        return folder

    def _out(self) -> Path | None:
        raw = self.output_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing output", "Choose an output folder first.")
            return None
        out = Path(raw)
        out.mkdir(parents=True, exist_ok=True)
        return out

    def _workspace(self) -> Path | None:
        raw = self.workspace_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing workspace", "Create or choose a rebuild workspace first.")
            return None
        ws = Path(raw)
        if not ws.exists() or not ws.is_dir():
            messagebox.showwarning("Missing workspace", "Workspace folder does not exist.")
            return None
        return ws

    def log(self, message: str):
        self.log_text.insert("end", str(message) + "\n")
        self.log_text.see("end")
        self.status_var.set(str(message))
        if self.app_state:
            try:
                self.app_state.set_status(str(message))
            except Exception:
                pass
        self.update_idletasks()

    def clear_log(self):
        self.log_text.delete("1.0", "end")
        self.status_var.set("Log cleared.")

    def run_no_change_test(self):
        if self.running:
            messagebox.showinfo("Busy", "Rebuild Lab is already running.")
            return
        pack = self._pack()
        out = self._out()
        if pack is None or out is None:
            return
        self.running = True
        self.log("Starting no-change rebuild test...")

        def task():
            try:
                result = run_no_change_rebuild_test(pack, out)
                self.last_result = result
                self.after(0, lambda: self.workspace_var.set(result.workspace))
                self.after(0, lambda: self._log_result(result))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Rebuild Lab failed", str(exc)))
                self.after(0, lambda: self.log(f"ERROR: {exc}"))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def rebuild_full_extract_tex_safe(self):
        if self.running:
            messagebox.showinfo("Busy", "Rebuild Lab is already running.")
            return
        pack = self._pack()
        extracted = self._extracted_folder()
        out = self._out()
        if pack is None or extracted is None or out is None:
            return
        try:
            detection = detect_extracted_pack_folder(extracted, pack)
            extracted = Path(detection.resolved_folder)
            self.extracted_folder_var.set(str(extracted))
            self.log(f"Auto-detected extracted pack folder: {extracted}")
            self.log("Rebuild map: direct clean-PCPACK parse (CSV not required).")
            if detection.inner_csv:
                self.log(f"Optional legacy CSV found: {detection.inner_csv}")
        except Exception as exc:
            messagebox.showerror("Full extract folder not ready", str(exc))
            self.log(f"ERROR: {exc}")
            return
        self.running = True
        self.log("Starting full extracted-folder rebuild with layout-faithful Repack Engine V2...")

        def task():
            try:
                result = rebuild_from_full_extract_tex_safe(pack, extracted, out)
                self.last_result = result
                self.after(0, lambda: self.workspace_var.set(result.workspace))
                self.after(0, lambda: self.patched_pack_var.set(result.rebuilt_pack))
                self.after(0, lambda: self._log_full_extract_result(result))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Full extract rebuild failed", str(exc)))
                self.after(0, lambda: self.log(f"ERROR: {exc}"))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def verify_patched_pack(self):
        if self.running:
            messagebox.showinfo("Busy", "Rebuild Lab is already running.")
            return
        pack = self._pack()
        patched = self._patched_pack()
        out = self._out()
        if pack is None or patched is None or out is None:
            return
        self.running = True
        self.log("Starting patched PCPACK review against clean original...")

        def task():
            try:
                result = verify_patched_pcpack(pack, patched, out)
                self.last_result = result
                self.after(0, lambda: self.workspace_var.set(result.review_workspace))
                self.after(0, lambda: self._log_patched_review(result))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Patched PCPACK review failed", str(exc)))
                self.after(0, lambda: self.log(f"ERROR: {exc}"))
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def write_branch_report(self):
        out = self._out()
        if out is None:
            return
        try:
            folder = write_current_branch_rebuild_report(out)
            self.workspace_var.set(str(folder))
            self.log(f"Current branch report written: {folder}")
            self.log("Report says v5.2.40 editor-safe Tex Swapper supersedes the mixed old branch handoff notes.")
        except Exception as exc:
            messagebox.showerror("Report failed", str(exc))
            self.log(f"ERROR: {exc}")

    def create_workspace_only(self):
        pack = self._pack()
        out = self._out()
        if pack is None or out is None:
            return
        try:
            ws = create_no_change_workspace(pack, out)
            self.workspace_var.set(str(ws))
            self.log(f"Workspace created: {ws}")
            self.log("No rebuilt PCPACK written yet. Click Rebuild Existing Workspace next.")
        except Exception as exc:
            messagebox.showerror("Workspace failed", str(exc))
            self.log(f"ERROR: {exc}")

    def rebuild_existing_workspace(self):
        ws = self._workspace()
        if ws is None:
            return
        try:
            result = rebuild_no_change(ws)
            self.last_result = result
            self._log_result(result)
        except Exception as exc:
            messagebox.showerror("Rebuild failed", str(exc))
            self.log(f"ERROR: {exc}")

    def _log_result(self, result: RebuildLabResult):
        self.log("=" * 72)
        self.log(f"Rebuild verdict: {result.verdict}")
        self.log(f"Route: {result.route}")
        self.log(f"Original size: {result.original_size:,}")
        self.log(f"Rebuilt size: {result.rebuilt_size:,}")
        self.log(f"Byte-identical: {result.byte_identical}")
        self.log(f"Outer rows: {result.outer_rows}")
        self.log(f"hsam/APKF markers: {result.hsam_markers}/{result.apkf_markers}")
        self.log(f"Rebuilt PCPACK: {result.rebuilt_pack}")
        self.log("Reports: 00_REBUILD_METADATA / REBUILD_VERDICT.txt")
        self.log("Next proof: user boot test. Do not enable edits until no-change boots.")

    def _log_full_extract_result(self, result: FullExtractRebuildResult):
        self.log("=" * 72)
        self.log(f"Full extract rebuild verdict: {result.verdict}")
        self.log(f"Route: {result.route}")
        self.log(f"Original size: {result.original_size:,}")
        self.log(f"Rebuilt size: {result.rebuilt_size:,}")
        self.log(f"Byte-identical: {result.byte_identical}")
        self.log(f"Resources seen/replaced: {result.resources_seen}/{result.resources_replaced}")
        self.log(f"TEX seen/replaced/preserved: {result.tex_rows_seen}/{result.tex_payloads_replaced}/{result.tex_preserved}")
        self.log(f"Blocked: {result.blocked_count}")
        self.log(f"Rebuilt PCPACK: {result.rebuilt_pack}")
        self.log("Reports: 00_FULL_EXTRACT_REBUILD_REPORTS / FULL_EXTRACT_REBUILD_VERDICT.txt")
        if result.blocked_count:
            self.log("Inspect FULL_EXTRACT_BLOCKED_SIZE_OR_MAPPING_CHANGES.csv before boot testing.")
        else:
            self.log("Next proof: backup original and boot/load test rebuilt pack in-game.")

    def _log_patched_review(self, result: PatchedPackReviewResult):
        self.log("=" * 72)
        self.log(f"Patched PCPACK review verdict: {result.verdict}")
        self.log(f"Original: {result.original_pack_name}")
        self.log(f"Patched: {result.patched_pack_name}")
        self.log(f"Original route: {result.original_route}")
        self.log(f"Patched route: {result.patched_route}")
        self.log(f"Same size: {result.same_size} ({result.original_size:,} -> {result.patched_size:,})")
        self.log(f"Same outer row count: {result.same_outer_row_count} ({result.original_outer_rows} -> {result.patched_outer_rows})")
        self.log(f"Same marker counts: {result.same_marker_counts}")
        self.log(f"First 4096 header bytes identical: {result.header_4096_identical}")
        self.log(f"Byte-identical: {result.byte_identical} (real texture patches should usually be False)")
        self.log(f"Review workspace: {result.review_workspace}")
        self.log("Reports: 00_PATCHED_REBUILD_REVIEW / PATCHED_PCPACK_REVIEW_VERDICT.txt")
        self.log("Next proof: backup original and boot/load test the patched pack in-game.")

    def open_output_folder(self):
        out = self._out()
        if out is not None:
            open_path(out)

    def open_workspace(self):
        ws = self._workspace()
        if ws is not None:
            open_path(ws)

    def open_rebuilt_pack(self):
        if isinstance(self.last_result, RebuildLabResult) and Path(self.last_result.rebuilt_pack).exists():
            open_path(Path(self.last_result.rebuilt_pack).parent)
            return
        if isinstance(self.last_result, FullExtractRebuildResult) and Path(self.last_result.rebuilt_pack).exists():
            open_path(Path(self.last_result.rebuilt_pack).parent)
            return
        if isinstance(self.last_result, PatchedPackReviewResult):
            open_path(Path(self.last_result.review_workspace))
            return
        ws = self._workspace()
        if ws is None:
            return
        out_dir = ws / "02_REBUILD_OUTPUT"
        if out_dir.exists():
            open_path(out_dir)
        else:
            messagebox.showinfo("No rebuilt output", "Run Rebuild Existing Workspace first.")
