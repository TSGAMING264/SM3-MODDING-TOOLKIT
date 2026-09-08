from __future__ import annotations

import csv
import json
import queue
import re
import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sm3_toolkit.services.anim_decoder_service import (
    DecodeError as AnimDecodeError,
    SM3AnimPoseDecoder,
    export_result_csv as export_anim_decode_csv,
    export_result_json as export_anim_decode_json,
    export_animation_csv as export_anim_timeline_csv,
    export_animation_json as export_anim_timeline_json,
    export_blender_animation_json as export_anim_blender_json,
    classify_sm3_skeleton_source,
    find_matching_askl,
    find_matching_skeleton_source,
    validate_matching_sm3_askl_path,
    validate_matching_sm3_skeleton_source_path,
    find_parent_apkf_for_anim,
    format_summary as format_anim_decode_summary,
    format_animation_summary as format_anim_timeline_summary,
    inspect_anim_header,
    read_anim_payload,
)

from sm3_toolkit.services.anim_codec_service import (
    AnimCodecError,
    decode_anim as codec_decode_anim,
    decoded_to_json_dict as codec_decoded_to_json_dict,
    encode_frames_into_template as codec_encode_frames_into_template,
    inspect_text as codec_inspect_text,
    load_json as codec_load_json,
    write_frames_csv as codec_write_frames_csv,
)

from sm3_toolkit.services.anim_editor_service import (
    AnimNamedProfileEditor,
    AnimRawTrackEditor,
    AnimScalarEditor,
    grouped_bindings as editor_grouped_bindings,
)

from sm3_toolkit.services.anim_mod_output_service import (
    build_anim_mod_loader_output,
    build_anim_swap_xesm3_output,
    build_wrap_anim_xesm3_output,
    inspect_anim_identity as inspect_mod_output_anim_identity,
)

from sm3_toolkit.services.wrap_output_service import (
    inspect_wrap_bytes,
    rebuild_wrap_from_shell_components,
    rebuild_wrap_anim_from_shell,
    find_matching_wrap_resource,
    read_wrap_anim_resource_hash,
)

from sm3_toolkit.services.spiderman_named_profile_service import (
    NamedProfileError,
    build_named_track_map,
    describe_track as describe_spiderman_named_track,
    export_named_track_map_csv,
    export_named_track_map_json,
    inspect_anim_identity as inspect_named_profile_anim_identity,
    has_builtin_profile,
    identify_character,
    profile_display_name,
)

from sm3_toolkit.services.new_animation_swapper_service import (
    character_anim_csv_auto_test_patch,
    character_anim_slot_preserve_swap,
    character_anim_repack_swap,
)
from sm3_toolkit.sm3_pack_guard import WRONG_GAME_GUARD_MESSAGE, looks_like_wrong_game_or_unsupported_sm3_path, wrong_game_detail
from sm3_toolkit.theme import COLORS
from sm3_toolkit.widgets import open_path

# Starter reference list based on user notes/WOS Toolkit-style labels.
# This is a helper only: names can vary by pack/dump and may not be perfectly accurate.
KNOWN_SM3_SPIDERMAN_ANIMS = [
    ("Dive / Fall", "sm2divefall", "movement", "May need dump verification"),
    ("Idle", "smcidlrlx", "idle", "May need dump verification"),
    ("Jump Launch", "sm3jmplnch", "jump", "Seen in blue-text/runtime notes"),
    ("Jump Land", "sm3jmpchgland", "jump", "Seen in blue-text/runtime notes"),
    ("Jog To Run", "sm2jog_to_run_red_meta_anim", "run", "Starter alias; verify in dump"),
    ("Run Jump", "smrrunjmplnch", "jump", "Starter alias; verify in dump"),
    ("Double Jump", "sm3jumpdoublejump", "jump", "Starter alias; verify in dump"),
    ("Holding Swing", "sm2swing_idle_seated_meta", "swing", "Starter alias; verify in dump"),
    ("Swing Intro A", "smrswingrintroa", "swing", "Starter alias; verify in dump"),
    ("Forward To Swing", "sm3swgrintroe", "swing", "Seen in blue-text/runtime notes"),
    ("Floor Bounce Jump", "smrbncjmplnch", "jump", "Starter alias; verify in dump"),
    ("Swing Left Intro", "sm2swing_left_intro_red", "swing", "Starter alias; verify in dump"),
    ("Double Jump With Webs", "smrjmpdoublewebf4s", "jump", "Starter alias; verify in dump"),
    ("Swing To Idle", "sm3swgrun2idle", "swing", "Starter alias; verify in dump"),
    ("Swing Lean Left", "smrswinglintroa", "swing", "Starter alias; verify in dump"),
    ("Swing Lean Right", "smrswingrintroa", "swing", "Starter alias; verify in dump"),
    ("Web Dash", "smrrziprintrob", "web zip", "Starter alias; verify in dump"),
    ("Swing Dangle Idle", "sm2swing_idle_dangle_meta", "swing", "Starter alias; verify in dump"),
    ("Block", "sm2block_red_meta_anim", "combat", "Starter alias; verify in dump"),
    ("Low Swing Left", "smrswgrls45r_low", "swing", "Starter alias; verify in dump"),
    ("Low Swing Right", "smrswgrlsb", "swing", "Starter alias; verify in dump"),
    ("Swing Dive Upper", "smrswgmidrlsv3", "swing", "Starter alias; verify in dump"),
    ("Slow Swing 270", "sm3slowswing270", "swing", "Seen in blue-text/runtime notes"),
    ("Slow Swing 360", "sm3slowswing360", "swing", "Seen in blue-text/runtime notes"),
    ("Vertical Web Zip", "smrvertwebzip", "web zip", "Starter alias; verify in dump"),
    ("Right Punch", "smrrightpunch", "combat", "Starter alias; verify in dump"),
    ("Left Punch", "smrleftpunch", "combat", "Starter alias; verify in dump"),
    ("Right Cross Punch", "smrrightcrosspunch", "combat", "Starter alias; verify in dump"),
    ("Right Spin Punch", "smrrightspinpunch", "combat", "Starter alias; verify in dump"),
    ("Kick Ender", "smrkickender", "combat", "Starter alias; verify in dump"),
    ("Uppercut", "smruppercut", "combat", "Starter alias; verify in dump"),
    ("Black Suit Right Punch", "smbrightpunch_nc", "combat", "Black suit; verify pack"),
    ("Black Suit Left Punch", "smbleftpunch", "combat", "Black suit; verify pack"),
    ("Black Suit Stomp", "smbstomp_nc", "combat", "Black suit; verify pack"),
    ("Black Suit Ichor Exploder", "smbichorchestexploder", "combat", "Black suit; verify pack"),
    ("Black Suit Right Elbow", "smbrightelbow", "combat", "Black suit; verify pack"),
    ("Black Suit Backhand Ender", "smbbackhandender", "combat", "Black suit; verify pack"),
    ("Black Suit Air Charge Attack", "smb2ichor_air_charge_attack", "combat", "Black suit; verify pack"),
    ("Black Suit Ichor Summon", "smbichorsummon_03", "combat", "Black suit; verify pack"),
    ("Black Suit Idle Tap Forward", "smbidle_tapforward", "idle", "Black suit; verify pack"),
]



def _clean_anim_display_name(path: Path) -> tuple[str, str]:
    name = path.name
    stem = path.stem
    hash_text = ""
    m = re.match(r"^(0x[0-9A-Fa-f]{8})[._-](.+)$", stem)
    if m:
        hash_text = m.group(1).upper().replace("0X", "0x")
        stem = m.group(2)
    if stem.lower().endswith(".wrap"):
        stem = stem[:-5]
    return hash_text, stem


def _guess_anim_family(anim_name: str) -> str:
    low = anim_name.lower()
    if any(k in low for k in ("atck", "atk", "punch", "kick", "combo", "counter", "ddg", "dodge", "hit", "webstrike")):
        return "combat"
    if any(k in low for k in ("swg", "swing", "slowswing", "webswing")):
        return "swing"
    if any(k in low for k in ("jmp", "jump", "land", "fall", "dive")):
        return "jump"
    if any(k in low for k in ("idle", "idl", "tap")):
        return "idle"
    if any(k in low for k in ("wall", "crawl", "climb")):
        return "wall"
    if any(k in low for k in ("zip", "webzip", "web_zip", "rzip")):
        return "web zip"
    if any(k in low for k in ("run", "jog", "walk", "sprint")):
        return "movement"
    return "unknown"


def scan_pc_animation_slots(extracted_folder: Path) -> list[dict[str, object]]:
    """Scan an extracted SM3 character folder for PC destination animation slots.

    This intentionally stays conservative and file-based. It does not decode ANIM curves;
    it builds the practical destination-slot library needed for New Animation Swapper.
    """
    extracted_folder = Path(extracted_folder)
    if not extracted_folder.exists() or not extracted_folder.is_dir():
        raise FileNotFoundError(f"2) Extracted character folder not found: {extracted_folder}")
    anims = []
    for path in extracted_folder.rglob("*.anim"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(extracted_folder).as_posix()
        except Exception:
            rel = path.as_posix()
        hash_text, anim_name = _clean_anim_display_name(path)
        low_rel = rel.lower()
        priority = 0 if "/02_apkf_extracted_real_ext/" in f"/{low_rel}" else 1
        anims.append({
            "path": str(path),
            "relative": rel,
            "filename": path.name,
            "hash": hash_text,
            "name": anim_name,
            "family": _guess_anim_family(anim_name),
            "size": path.stat().st_size,
            "priority": priority,
        })
    # Full Pack Extractor output can contain the same resource in both
    # 02_APKF_EXTRACTED_REAL_EXT and 06_MOD_LOADER_READY. Keep one canonical
    # destination row per resource, preferring the real extracted resource copy.
    deduped: dict[str, dict[str, object]] = {}
    for row in anims:
        hash_text = str(row.get("hash") or "").strip().lower()
        key = hash_text if hash_text else str(row.get("filename") or "").lower()
        current = deduped.get(key)
        if current is None or int(row.get("priority", 9)) < int(current.get("priority", 9)):
            deduped[key] = row
    anims = list(deduped.values())
    anims.sort(key=lambda r: (int(r.get("priority", 9)), str(r.get("family", "")), str(r.get("name", "")).lower(), str(r.get("filename", "")).lower()))
    return anims


class NewAnimationSwapperTab(ttk.Frame):
    """Release-clean New Animation Swapper UI.

    v5.2.141 makes the normal swap workflow WoS-style and unrestricted:
    TARGET OUT -> REPLACEMENT IN -> XESM3 MOD. The Toolkit does not block a pair based on
    ASKL, version, size, track count, or layout. The runtime-proven guided Motion Editor stays intact.
    Legacy PCPACK/NAS pages are removed from the New Animation Swapper UI.
    """

    def __init__(self, parent, app_state=None):
        super().__init__(parent, style="Body.TFrame", padding=12)
        self.app_state = app_state
        self.character_pack_var = tk.StringVar()
        self.extracted_character_folder_var = tk.StringVar()
        self.source_file_var = tk.StringVar()
        self.target_file_var = tk.StringVar()
        self.character_test_csv_var = tk.StringVar()
        self.out_dir_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="New Animation Swapper ready. Use Animation Swapper for replacements or Motion Editor for motion edits.")
        self.known_search_var = tk.StringVar()
        self.destination_search_var = tk.StringVar()
        # v5.2.141 — unrestricted WoS-style guided XESM3 animation swapper.
        self.swap_target_search_var = tk.StringVar()
        self.swap_replacement_search_var = tk.StringVar()
        self.swap_mod_name_var = tk.StringVar(value="SM3 ANIM Swap")
        self.swap_compatibility_var = tk.StringVar(value="Freedom mode: the Toolkit will not block the selected pair.")
        self.swap_build_status_var = tk.StringVar(value="Ready — XESM3 leaves the original PCPACK untouched.")
        self._last_guided_swap_output = None
        self._csv_rows_preview: list[dict] = []
        self._pc_dest_rows: list[dict[str, object]] = []

        # TEMP v5.2.129 NAS all-frames / ASKL folder-scan decoder state (Blender bridge retained as advanced export).
        self.decoder_anim_var = tk.StringVar()
        self.decoder_askl_var = tk.StringVar()
        self.decoder_frame_var = tk.IntVar(value=28)
        self.decoder_status_var = tk.StringVar(value="Select an ANIM, then select an ASKL file or choose a folder to scan.")
        self._decoder_last_decoder = None
        self._decoder_last_result = None
        self._decoder_last_animation = None
        self._decoder_last_anim_path = None
        self._decoder_all_frames_busy = False
        self._decoder_worker_queue = queue.Queue()

        # TEMP v5.2.122 — integrated reversible scalar ANIM codec/rebuilder.
        self.codec_json_var = tk.StringVar()
        self.codec_rebuilt_var = tk.StringVar()
        self.codec_auto_codecs_var = tk.BooleanVar(value=True)
        self.codec_allow_resize_var = tk.BooleanVar(value=False)
        # v5.2.193 — guided Motion Editor restores the v182 arbitrary-size
        # loose ANIM rebuild automatically when an edit no longer fits the
        # original compressed payload.  The legacy codec checkbox remains
        # independent for direct codec/rebuilder use.
        self.editor_auto_grow_var = tk.BooleanVar(value=True)
        self.codec_status_var = tk.StringVar(
            value="Select an ANIM, run ROUNDTRIP, then decode to editable JSON."
        )
        self._codec_last_decoded = None

        # TEMP v5.2.129 — simplified quick motion editor + ASKL-aware advanced mapping.
        self.editor_frame_var = tk.IntVar(value=0)
        self.editor_range_start_var = tk.IntVar(value=0)
        self.editor_range_end_var = tk.IntVar(value=0)
        self.editor_field_var = tk.StringVar()
        self.editor_element_var = tk.StringVar()
        self.editor_component_var = tk.StringVar()
        self.editor_track_var = tk.StringVar(value="-")
        self.editor_current_raw_var = tk.StringVar(value="-")
        self.editor_scale_var = tk.StringVar(value="-")
        self.editor_scaled_var = tk.StringVar(value="-")
        self.editor_new_raw_var = tk.StringVar()
        self.editor_delta_var = tk.StringVar(value="1000")
        self.editor_quick_track_var = tk.StringVar(value="0")
        self.editor_status_var = tk.StringVar(
            value="Guided mode: follow Steps 1-7 from top to bottom."
        )
        self.editor_skeleton_status_var = tk.StringVar(
            value="Skeleton: select an ANIM first. Spider-Man / Black Suit / Peter share built-in 0xCFB154CD; Player Goblin WRAP.ASKL is auto-detected."
        )
        self.editor_selection_summary_var = tk.StringVar(
            value="Nothing selected yet — load/map the animation first."
        )
        self.editor_range_summary_var = tk.StringVar(value="Frame range: not loaded yet.")
        self.editor_review_var = tk.StringVar(value="No edits applied yet.")
        self.editor_advanced_visible = False
        self._anim_editor = None
        self._editor_grouped = {}
        self._editor_element_label_to_key = {}
        self._editor_component_to_binding = {}

        # v5.2.138 — one-click XESM3 ANIM output state.
        self.anim_mod_output_anim_var = tk.StringVar()
        self.anim_mod_name_var = tk.StringVar(value="SM3 ANIM Mod")
        self.anim_mod_status_var = tk.StringVar(
            value="Select a rebuilt ANIM, extracted pack folder, output folder, then BUILD XESM3 MOD."
        )

        # v5.2.131 — runtime-reconstructed CH_SPIDERMAN 0xCFB154CD named profile.
        self.named_profile_anim_var = tk.StringVar()
        self.named_profile_search_var = tk.StringVar()
        self.named_profile_status_var = tk.StringVar(
            value="0xCFB154CD ch_spiderman named profile ready — 85 runtime nodes."
        )
        self._named_profile_rows = []

        self._build()
        # v5.2.138 release cleanup: keep the proven Motion Editor and add the
        # XESM3 output page, but do not expose character-specific/dev research pages.
        self._build_anim_mod_output_page()

    def _build(self):
        """Build a compact release UI.

        v5.2.73 remodel: visible buttons and fields are numbered in the exact use order.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self, style="Body.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="New Animation Swapper — XESM3 Guided Workflow",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text=(
                "Two simple jobs: Animation Swapper replaces one ANIM with another; Motion Editor changes motion inside an ANIM. "
                "XESM3 is the normal install route. The New Animation Swapper does not enforce compatibility restrictions."
            ),
            style="Muted.TLabel",
            wraplength=1000,
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        setup = ttk.Frame(self, style="Card.TFrame", padding=10)
        setup.grid(row=1, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        setup.columnconfigure(4, weight=1)

        ttk.Label(setup, text="Extracted SM3 pack folder", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(setup, textvariable=self.extracted_character_folder_var).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(setup, text="Browse + Scan ANIMs", command=self.browse_extracted_character_folder).grid(row=0, column=2, sticky="ew", padx=4, pady=3)

        ttk.Label(setup, text="Output folder", style="CardLabel.TLabel").grid(row=0, column=3, sticky="w", padx=(14, 4), pady=3)
        ttk.Entry(setup, textvariable=self.out_dir_var).grid(row=0, column=4, sticky="ew", padx=4, pady=3)
        out_buttons = ttk.Frame(setup, style="Card.TFrame")
        out_buttons.grid(row=0, column=5, sticky="ew", padx=4, pady=3)
        ttk.Button(out_buttons, text="Browse Output", command=self.browse_out_dir).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(out_buttons, text="Open", command=self.open_output).pack(side="left", fill="x", expand=True, padx=(3, 0))

        ttk.Label(
            setup,
            text="For a normal XESM3 swap: choose the ANIM to swap OUT, choose the ANIM to swap IN, then build the mod. No compatibility gate or slot-size math.",
            style="Muted.TLabel",
            wraplength=1000,
        ).grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(5, 0))

        self.workbook = ttk.Notebook(self)
        self.workbook.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self._build_guided_animation_swapper_page()

        # ------------------------------------------------------------------
        # PC Destination Slot Library — Steps 4 and 5 page
        # ------------------------------------------------------------------
        pc_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        pc_page.columnconfigure(1, weight=1)
        pc_page.rowconfigure(3, weight=1)
        self.workbook.add(pc_page, text="Legacy PC Slots (Optional)")
        self.legacy_pc_page = pc_page
        self.workbook.hide(pc_page)

        ttk.Label(pc_page, text="PC Destination Slot Library — Steps 4 and 5", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(
            pc_page,
            text="4) Scan the extracted character folder. 5) Send the selected PC destination slot into Source OUT.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 6))
        ttk.Label(pc_page, text="Search:", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(pc_page, textvariable=self.destination_search_var).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(pc_page, text="4) SCAN PC ANIMATIONS", command=self.scan_pc_destination_slots).grid(row=2, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(pc_page, text="5) USE SELECTED AS SOURCE OUT", command=self.use_selected_destination_as_source).grid(row=2, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(pc_page, text="Clear", command=self.clear_destination_search).grid(row=2, column=4, sticky="ew", padx=4, pady=4)
        self.destination_search_var.trace_add("write", lambda *_: self.refresh_destination_tree())

        dest_tree_frame = ttk.Frame(pc_page, style="Body.TFrame")
        dest_tree_frame.grid(row=3, column=0, columnspan=5, sticky="nsew", padx=4, pady=(4, 0))
        dest_tree_frame.columnconfigure(0, weight=1)
        dest_tree_frame.rowconfigure(0, weight=1)
        dest_cols = ("name", "hash", "size", "family", "relative")
        self.destination_tree = ttk.Treeview(dest_tree_frame, columns=dest_cols, show="headings", height=13)
        for col, width in (("name", 240), ("hash", 110), ("size", 80), ("family", 100), ("relative", 540)):
            self.destination_tree.heading(col, text=col.title())
            self.destination_tree.column(col, width=width, anchor="w")
        self.destination_tree.grid(row=0, column=0, sticky="nsew")
        dest_scroll = ttk.Scrollbar(dest_tree_frame, orient="vertical", command=self.destination_tree.yview)
        dest_scroll.grid(row=0, column=1, sticky="ns")
        self.destination_tree.configure(yscrollcommand=dest_scroll.set)
        self.destination_tree.bind("<Double-1>", lambda _e: self.use_selected_destination_as_source())

        # ------------------------------------------------------------------
        # Manual one-off patch page
        # ------------------------------------------------------------------
        manual_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        manual_page.columnconfigure(1, weight=1)
        manual_page.columnconfigure(4, weight=1)
        self.workbook.add(manual_page, text="Legacy PCPACK (Optional)")
        self.legacy_manual_page = manual_page
        self.workbook.hide(manual_page)

        ttk.Label(manual_page, text="LEGACY PCPACK SLOT-PRESERVE — OPTIONAL", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 6))
        ttk.Label(
            manual_page,
            text="Optional legacy route only. Normal XESM3 swaps should use the Animation Swapper tab. This route still requires a clean original PCPACK and still blocks donors that do not fit the stock slot.",
            style="Muted.TLabel", wraplength=980,
        ).grid(row=1, column=0, columnspan=5, sticky="w", padx=4, pady=(0, 8))
        ttk.Label(manual_page, text="Original character PCPACK", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(manual_page, textvariable=self.character_pack_var).grid(row=4, column=1, sticky="ew", padx=4, pady=6)
        ttk.Button(manual_page, text="Browse Original PCPACK", command=self.browse_character_pack).grid(row=4, column=2, sticky="ew", padx=4, pady=6)

        ttk.Label(manual_page, text="5) Source animation OUT / destination slot", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(manual_page, textvariable=self.source_file_var).grid(row=2, column=1, sticky="ew", padx=4, pady=6)
        ttk.Button(manual_page, text="5A) Browse Source OUT", command=self.browse_source_file).grid(row=2, column=2, sticky="ew", padx=4, pady=6)

        ttk.Label(manual_page, text="6) Replacement animation IN", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(manual_page, textvariable=self.target_file_var).grid(row=3, column=1, sticky="ew", padx=4, pady=6)
        ttk.Button(manual_page, text="6A) Browse Replacement IN", command=self.browse_target_file).grid(row=3, column=2, sticky="ew", padx=4, pady=6)

        manual_buttons = ttk.Frame(manual_page, style="Card.TFrame")
        manual_buttons.grid(row=2, column=3, rowspan=2, sticky="nsew", padx=(14, 4), pady=6)
        ttk.Button(
            manual_buttons,
            text="7) PREVIEW MANUAL PAIR SAFETY",
            command=self.preview_manual_pair_safety,
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            manual_buttons,
            text="8) BUILD NAS CSV FROM MANUAL PAIR",
            command=self.build_nas_csv_from_manual_pair,
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            manual_buttons,
            text="ALT 1) SAFE SLOT-PRESERVE -> WRITE PCPACK",
            command=self.sm3_character_slot_preserve_threaded,
            style="Accent.TButton",
        ).pack(fill="x", pady=(0, 8))
        ttk.Button(
            manual_buttons,
            text="RECOMMENDED) SEND REBUILT ANIM TO XESM3 OUTPUT",
            command=self.prepare_xesm3_mod_from_replacement,
        ).pack(fill="x")
        ttk.Label(
            manual_page,
            text=(
                "Safe slot-preserve is the legacy PCPACK route and blocks bigger replacements. "
                "The old experimental size-change PCPACK button is hidden from the release UI. "
                "For rebuilt/larger loose ANIM files, use XESM3 Mod Output instead."
            ),
            style="CardLabel.TLabel",
            wraplength=500,
        ).grid(row=2, column=4, rowspan=2, sticky="w", padx=8, pady=6)

        # ------------------------------------------------------------------
        # 8) NAS CSV page
        # ------------------------------------------------------------------
        csv_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        csv_page.columnconfigure(0, weight=1)
        csv_page.rowconfigure(2, weight=1)
        self.workbook.add(csv_page, text="Batch / NAS CSV (Optional)")
        self.legacy_csv_page = csv_page
        self.workbook.hide(csv_page)

        ttk.Label(csv_page, text="BATCH / NAS CSV — OPTIONAL", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(
            csv_page,
            text="Optional batch / legacy PCPACK workflow. Import a NAS CSV only when you intentionally want batch slot-preserve patching.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", padx=4, pady=(0, 6))
        csv_controls = ttk.Frame(csv_page, style="Card.TFrame", padding=6)
        csv_controls.grid(row=2, column=0, sticky="ew", padx=4, pady=(2, 6))
        csv_controls.columnconfigure(1, weight=1)
        ttk.Label(csv_controls, text="Original PCPACK", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(csv_controls, textvariable=self.character_pack_var).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(csv_controls, text="Browse", command=self.browse_character_pack).grid(row=0, column=2, sticky="ew", padx=4, pady=3)
        ttk.Label(csv_controls, text="NAS CSV", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(csv_controls, textvariable=self.character_test_csv_var).grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        ttk.Button(csv_controls, text="Import CSV", command=self.browse_character_test_csv).grid(row=1, column=2, sticky="ew", padx=4, pady=3)
        ttk.Button(csv_controls, text="PATCH PCPACK FROM NAS CSV", command=self.sm3_character_csv_auto_test_threaded, style="Accent.TButton").grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(6, 3))

        csv_tree_frame = ttk.Frame(csv_page, style="Body.TFrame")
        csv_tree_frame.grid(row=3, column=0, sticky="nsew", padx=4)
        csv_tree_frame.columnconfigure(0, weight=1)
        csv_tree_frame.rowconfigure(0, weight=1)
        columns = ("enabled", "destination", "replacement", "mode", "note")
        self.csv_tree = ttk.Treeview(csv_tree_frame, columns=columns, show="headings", height=13)
        for col, width in (("enabled", 70), ("destination", 310), ("replacement", 310), ("mode", 120), ("note", 360)):
            self.csv_tree.heading(col, text=col.replace("_", " ").title())
            self.csv_tree.column(col, width=width, anchor="w")
        self.csv_tree.grid(row=0, column=0, sticky="nsew")
        csv_scroll = ttk.Scrollbar(csv_tree_frame, orient="vertical", command=self.csv_tree.yview)
        csv_scroll.grid(row=0, column=1, sticky="ns")
        self.csv_tree.configure(yscrollcommand=csv_scroll.set)

        # ------------------------------------------------------------------
        # Known animation helper page
        # ------------------------------------------------------------------
        known_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        known_page.columnconfigure(1, weight=1)
        known_page.rowconfigure(3, weight=1)
        # v5.2.138 release: unverified starter-name helper remains internal, not shown.

        ttk.Label(
            known_page,
            text="Known Spider-Man Animations (SM3 starter list — may not be accurate)",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(
            known_page,
            text="Helper list only. Verify every name in your extracted dump before using it in a CSV.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(0, 6))
        ttk.Label(known_page, text="Search:", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=(4, 6), pady=4)
        ttk.Entry(known_page, textvariable=self.known_search_var).grid(row=2, column=1, sticky="ew", padx=(0, 6), pady=4)
        ttk.Button(known_page, text="Clear", command=self.clear_known_search).grid(row=2, column=2, sticky="ew", padx=4, pady=4)
        self.known_search_var.trace_add("write", lambda *_: self.refresh_known_anims())
        known_frame = ttk.Frame(known_page, style="Body.TFrame")
        known_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=4, pady=(4, 0))
        known_frame.columnconfigure(0, weight=1)
        known_frame.rowconfigure(0, weight=1)
        known_columns = ("label", "anim", "family", "note")
        self.known_tree = ttk.Treeview(known_frame, columns=known_columns, show="headings", height=13)
        for col, width in (("label", 220), ("anim", 330), ("family", 100), ("note", 420)):
            self.known_tree.heading(col, text=col.title())
            self.known_tree.column(col, width=width, anchor="w")
        self.known_tree.grid(row=0, column=0, sticky="nsew")
        known_scroll = ttk.Scrollbar(known_frame, orient="vertical", command=self.known_tree.yview)
        known_scroll.grid(row=0, column=1, sticky="ns")
        self.known_tree.configure(yscrollcommand=known_scroll.set)
        self.refresh_known_anims()

        # ------------------------------------------------------------------
        # TEMP v5.2.126 — Offline ANIM Decoder + named-bone pose reconstruction
        # ------------------------------------------------------------------
        decoder_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        decoder_page.columnconfigure(1, weight=1)
        decoder_page.rowconfigure(9, weight=1)
        # v5.2.138 release: decoder research UI remains internal, not shown.

        ttk.Label(
            decoder_page,
            text="Offline SM3 ANIM Decoder / Inspector — TEMP DEV",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(
            decoder_page,
            text=(
                "Read-only decoder for extracted PC ANIM v0x20116 + matching ASKL. "
                "This page does not modify PCPACK/APKF files and does not run the animation swapper."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 8))

        ttk.Label(decoder_page, text="ANIM", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(decoder_page, textvariable=self.decoder_anim_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Browse ANIM", command=self.browse_decoder_anim).grid(row=2, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Use Source OUT", command=self.use_source_out_for_decoder).grid(row=2, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Use Replacement IN", command=self.use_replacement_in_for_decoder).grid(row=2, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(decoder_page, text="ASKL / Skeleton", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(decoder_page, textvariable=self.decoder_askl_var).grid(row=3, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Select ASKL File", command=self.browse_decoder_askl).grid(row=3, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Select Folder + Scan", command=self.select_decoder_askl_folder).grid(row=3, column=4, columnspan=2, sticky="ew", padx=4, pady=4)

        ttk.Label(decoder_page, text="Frame", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.decoder_frame_spin = ttk.Spinbox(decoder_page, from_=0, to=99999, textvariable=self.decoder_frame_var, width=12)
        self.decoder_frame_spin.grid(row=4, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(decoder_page, text="DECODE FRAME", command=self.decode_anim_frame, style="Accent.TButton").grid(row=4, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Export JSON", command=self.export_decoder_json).grid(row=4, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Export CSV", command=self.export_decoder_csv).grid(row=4, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(decoder_page, text="Clear", command=self.clear_decoder_output).grid(row=4, column=5, sticky="ew", padx=4, pady=4)

        ttk.Button(
            decoder_page,
            text="DECODE ALL FRAMES",
            command=self.decode_anim_all_frames,
            style="Accent.TButton",
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(
            decoder_page,
            text="Export Animation JSON",
            command=self.export_decoder_animation_json,
        ).grid(row=5, column=2, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(
            decoder_page,
            text="Export Animation CSV",
            command=self.export_decoder_animation_csv,
        ).grid(row=5, column=4, columnspan=2, sticky="ew", padx=4, pady=4)

        ttk.Button(
            decoder_page,
            text="Advanced: Export Blender Bridge JSON",
            command=self.export_decoder_blender_json,
            ).grid(row=6, column=0, columnspan=6, sticky="ew", padx=4, pady=(6, 4))

        ttk.Label(
            decoder_page,
            textvariable=self.decoder_status_var,
            style="CardLabel.TLabel",
        ).grid(row=7, column=0, columnspan=6, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(
            decoder_page,
            text=(
                "Recovered path: compressed integer tracks -> ASKL per-element scale -> named bones -> final local rotations. "
                "Raw SM3 quaternions stay untouched and the named-bone pose decoder remains available for inspection. "
                "Blender Bridge export is retained only as an advanced compatibility export; the current focus is the in-toolkit ANIM Motion Editor."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=8, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 6))

        decoder_text_frame = ttk.Frame(decoder_page, style="Body.TFrame")
        decoder_text_frame.grid(row=9, column=0, columnspan=6, sticky="nsew", padx=4, pady=(2, 0))
        decoder_text_frame.columnconfigure(0, weight=1)
        decoder_text_frame.rowconfigure(0, weight=1)
        self.decoder_text = tk.Text(
            decoder_text_frame,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="none",
            font=("Consolas", 10),
            height=20,
        )
        self.decoder_text.grid(row=0, column=0, sticky="nsew")
        decoder_y = ttk.Scrollbar(decoder_text_frame, orient="vertical", command=self.decoder_text.yview)
        decoder_y.grid(row=0, column=1, sticky="ns")
        decoder_x = ttk.Scrollbar(decoder_text_frame, orient="horizontal", command=self.decoder_text.xview)
        decoder_x.grid(row=1, column=0, sticky="ew")
        self.decoder_text.configure(yscrollcommand=decoder_y.set, xscrollcommand=decoder_x.set, state="disabled")

        # ------------------------------------------------------------------
        # TEMP v5.2.122 — NAS reversible scalar ANIM codec / template rebuilder
        # ------------------------------------------------------------------
        codec_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        codec_page.columnconfigure(1, weight=1)
        codec_page.rowconfigure(9, weight=1)
        # v5.2.138 release: codec/rebuilder research UI remains internal, not shown.
        self.codec_page = codec_page

        ttk.Label(
            codec_page,
            text="NAS ANIM Codec / Rebuilder — TEMP DEV",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 4))
        ttk.Label(
            codec_page,
            text=(
                "Reversible compressed-scalar codec for loose SM3 ANIM v0x20116. "
                "ROUNDTRIP proves untouched files bit-identical. DECODE writes editable JSON. "
                "BUILD re-encodes edited scalar frames. Normal mode preserves the original template size. "
                "EXPERIMENTAL arbitrary-size mode grows a loose ANIM, shifts its metadata tail, and rewrites the proven local pointer tokens for NativeANIM testing."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 8))

        ttk.Label(codec_page, text="ANIM template", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(codec_page, textvariable=self.decoder_anim_var).grid(row=2, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(codec_page, text="Browse ANIM", command=self.browse_decoder_anim).grid(row=2, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(codec_page, text="Use Source OUT", command=self.use_source_out_for_codec).grid(row=2, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(codec_page, text="Use Replacement IN", command=self.use_replacement_in_for_codec).grid(row=2, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(codec_page, text="Editable JSON", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(codec_page, textvariable=self.codec_json_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Button(codec_page, text="Browse JSON", command=self.browse_codec_json).grid(row=3, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(codec_page, text="Open JSON", command=self.open_codec_json).grid(row=3, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(codec_page, text="Rebuilt ANIM", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(codec_page, textvariable=self.codec_rebuilt_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Checkbutton(
            codec_page,
            text="Auto-select compression descriptors",
            variable=self.codec_auto_codecs_var,
        ).grid(row=4, column=4, sticky="w", padx=4, pady=4)
        ttk.Button(codec_page, text="Open Rebuilt Folder", command=self.open_codec_rebuilt).grid(row=4, column=5, sticky="ew", padx=4, pady=4)

        ttk.Checkbutton(
            codec_page,
            text="EXPERIMENTAL: allow larger loose ANIM (resize + relocate local tokens)",
            variable=self.codec_allow_resize_var,
        ).grid(row=5, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 4))

        codec_actions = ttk.Frame(codec_page, style="Body.TFrame")
        codec_actions.grid(row=6, column=0, columnspan=6, sticky="ew", padx=4, pady=(6, 4))
        codec_actions.columnconfigure(0, weight=1)
        codec_actions.columnconfigure(1, weight=1)
        codec_actions.columnconfigure(2, weight=1)
        ttk.Button(
            codec_actions,
            text="1) BIT-IDENTICAL ROUNDTRIP TEST",
            command=self.codec_roundtrip_test,
            style="Accent.TButton",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            codec_actions,
            text="2) DECODE TO EDITABLE JSON",
            command=self.codec_decode_to_json,
            style="Accent.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            codec_actions,
            text="3) BUILD EDITED ANIM",
            command=self.codec_build_edited_anim,
            style="Accent.TButton",
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Label(
            codec_page,
            textvariable=self.codec_status_var,
            style="CardLabel.TLabel",
        ).grid(row=7, column=0, columnspan=6, sticky="w", padx=4, pady=(4, 2))
        ttk.Label(
            codec_page,
            text=(
                "The ASKL-aware ANIM Decoder page remains the named-bone inspection view. "
                "This Codec page owns exact compressed integers and re-encoding. "
                "Do not treat flat track numbers as bone names until the ASKL mapping is applied."
            ),
            style="Muted.TLabel",
            wraplength=1180,
        ).grid(row=8, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 6))

        codec_text_frame = ttk.Frame(codec_page, style="Body.TFrame")
        codec_text_frame.grid(row=9, column=0, columnspan=6, sticky="nsew", padx=4, pady=(2, 0))
        codec_text_frame.columnconfigure(0, weight=1)
        codec_text_frame.rowconfigure(0, weight=1)
        self.codec_text = tk.Text(
            codec_text_frame,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="none",
            font=("Consolas", 10),
            height=20,
        )
        self.codec_text.grid(row=0, column=0, sticky="nsew")
        codec_y = ttk.Scrollbar(codec_text_frame, orient="vertical", command=self.codec_text.yview)
        codec_y.grid(row=0, column=1, sticky="ns")
        codec_x = ttk.Scrollbar(codec_text_frame, orient="horizontal", command=self.codec_text.xview)
        codec_x.grid(row=1, column=0, sticky="ew")
        self.codec_text.configure(yscrollcommand=codec_y.set, xscrollcommand=codec_x.set, state="disabled")

        # ------------------------------------------------------------------
        # v5.2.139 — GUIDED Motion Editor
        # ------------------------------------------------------------------
        # The codec/editor backend is unchanged. The release UI now leads normal
        # users through one numbered path and keeps raw-track/JSON controls under
        # an explicit Advanced disclosure.
        editor_host = ttk.Frame(self.workbook, style="Body.TFrame")
        editor_host.columnconfigure(0, weight=1)
        editor_host.rowconfigure(0, weight=1)
        self.workbook.add(editor_host, text="ANIM Motion Editor")
        self.motion_editor_page = editor_host
        self.editor_page = editor_host

        editor_canvas = tk.Canvas(
            editor_host,
            bg=COLORS["bg"],
            highlightthickness=0,
            borderwidth=0,
        )
        editor_scroll = ttk.Scrollbar(editor_host, orient="vertical", command=editor_canvas.yview)
        editor_canvas.configure(yscrollcommand=editor_scroll.set)
        editor_canvas.grid(row=0, column=0, sticky="nsew")
        editor_scroll.grid(row=0, column=1, sticky="ns")

        editor_page = ttk.Frame(editor_canvas, style="Body.TFrame", padding=(8, 6))
        editor_window = editor_canvas.create_window((0, 0), window=editor_page, anchor="nw")
        editor_page.columnconfigure(0, weight=1)

        def _editor_sync_scrollregion(_event=None):
            editor_canvas.configure(scrollregion=editor_canvas.bbox("all"))

        def _editor_fit_width(event):
            editor_canvas.itemconfigure(editor_window, width=max(1, event.width))

        def _editor_wheel(event):
            delta = -1 if event.delta > 0 else 1
            editor_canvas.yview_scroll(delta * 3, "units")

        editor_page.bind("<Configure>", _editor_sync_scrollregion)
        editor_canvas.bind("<Configure>", _editor_fit_width)
        editor_canvas.bind("<Enter>", lambda _e: editor_canvas.bind_all("<MouseWheel>", _editor_wheel))
        editor_canvas.bind("<Leave>", lambda _e: editor_canvas.unbind_all("<MouseWheel>"))
        self.editor_canvas = editor_canvas

        ttk.Label(
            editor_page,
            text="ANIM Motion Editor — GUIDED MODE",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 3))
        ttk.Label(
            editor_page,
            text=(
                "Follow Steps 1-7 from top to bottom. Normal editing uses named Motion / Bone / Axis controls and one frame-range Apply button. "
                "Raw track numbers, JSON and single-frame codec controls are still available under Advanced Controls."
            ),
            style="Muted.TLabel",
            wraplength=1120,
        ).grid(row=1, column=0, sticky="w", padx=4, pady=(0, 8))

        # STEP 1 -----------------------------------------------------------------
        step1 = ttk.LabelFrame(editor_page, text="STEP 1 — SELECT ANIMATION", padding=(10, 8))
        step1.grid(row=2, column=0, sticky="ew", padx=4, pady=5)
        step1.columnconfigure(1, weight=1)
        ttk.Label(step1, text="ANIM / WRAP.ANIM file", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(step1, textvariable=self.decoder_anim_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(step1, text="1A) BROWSE ANIM", command=self.browse_decoder_anim, style="Accent.TButton").grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(step1, text="Use Source OUT", command=self.use_source_out_for_editor).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        ttk.Label(step1, textvariable=self.editor_skeleton_status_var, style="Muted.TLabel", wraplength=1040).grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 0))

        # STEP 2 -----------------------------------------------------------------
        step2 = ttk.LabelFrame(editor_page, text="STEP 2 — LOAD / MAP THE ANIMATION", padding=(10, 8))
        step2.grid(row=3, column=0, sticky="ew", padx=4, pady=5)
        for col in range(4):
            step2.columnconfigure(col, weight=1)

        # The normal route gets full visual priority.  v5.2.191 placed two ASKL
        # fallback actions beside this button with identical visual weight, which
        # made them look like duplicate required steps.  Keep the same commands,
        # but separate them clearly as optional recovery tools.
        ttk.Button(
            step2,
            text="2) START FRESH + AUTO-MAP CHARACTER / ASKL",
            command=self.editor_guided_load_map,
            style="Accent.TButton",
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=4, pady=(4, 5))
        ttk.Label(
            step2,
            text=(
                "NORMAL ROUTE: use the button above first. Spider-Man, Black Suit and Peter use the built-in "
                "0xCFB154CD named profile. Player Goblin uses 0x900E49A5 with sibling .wrap.askl auto-discovery "
                "and a built-in named fallback."
            ),
            style="Muted.TLabel", wraplength=1040,
        ).grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(0, 6))

        askl_fallback = ttk.LabelFrame(
            step2,
            text="OPTIONAL ASKL FALLBACK — ONLY IF AUTO-MAP FAILS / OTHER CHARACTERS",
            padding=(8, 6),
        )
        askl_fallback.grid(row=2, column=0, columnspan=4, sticky="ew", padx=4, pady=(2, 5))
        askl_fallback.columnconfigure(0, weight=1)
        askl_fallback.columnconfigure(1, weight=1)
        ttk.Button(
            askl_fallback,
            text="PICK ONE EXACT ASKL / WRAP.ASKL FILE",
            command=self.browse_decoder_askl,
        ).grid(row=0, column=0, sticky="ew", padx=(2, 5), pady=3)
        ttk.Button(
            askl_fallback,
            text="AUTO-FIND MATCHING ASKL IN A FOLDER",
            command=self.select_decoder_askl_folder,
        ).grid(row=0, column=1, sticky="ew", padx=(5, 2), pady=3)
        ttk.Label(
            askl_fallback,
            text="Use this when you already know the exact skeleton file.",
            style="Muted.TLabel", wraplength=500,
        ).grid(row=1, column=0, sticky="w", padx=3, pady=(0, 2))
        ttk.Label(
            askl_fallback,
            text="Use this to scan a character / MOD LOADER READY folder and match the animation's ASKL hash automatically.",
            style="Muted.TLabel", wraplength=500,
        ).grid(row=1, column=1, sticky="w", padx=3, pady=(0, 2))

        ttk.Label(step2, textvariable=self.editor_status_var, style="CardLabel.TLabel", wraplength=1040).grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=(5, 0))

        # STEP 3 -----------------------------------------------------------------
        step3 = ttk.LabelFrame(editor_page, text="STEP 3 — CHOOSE WHAT TO EDIT", padding=(10, 8))
        step3.grid(row=4, column=0, sticky="ew", padx=4, pady=5)
        step3.columnconfigure(1, weight=1)
        step3.columnconfigure(3, weight=1)
        step3.columnconfigure(5, weight=1)
        ttk.Label(step3, text="Motion Type", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.editor_field_combo = ttk.Combobox(step3, textvariable=self.editor_field_var, state="readonly", width=24)
        self.editor_field_combo.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.editor_field_combo.bind("<<ComboboxSelected>>", self._editor_on_field_selected)
        ttk.Label(step3, text="Bone / Element", style="CardLabel.TLabel").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.editor_element_combo = ttk.Combobox(step3, textvariable=self.editor_element_var, state="readonly", width=34)
        self.editor_element_combo.grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        self.editor_element_combo.bind("<<ComboboxSelected>>", self._editor_on_element_selected)
        ttk.Label(step3, text="Axis / Component", style="CardLabel.TLabel").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.editor_component_combo = ttk.Combobox(step3, textvariable=self.editor_component_var, state="readonly", width=14)
        self.editor_component_combo.grid(row=0, column=5, sticky="ew", padx=4, pady=4)
        self.editor_component_combo.bind("<<ComboboxSelected>>", lambda _e: self._editor_refresh_value())
        ttk.Label(step3, textvariable=self.editor_selection_summary_var, style="Muted.TLabel", wraplength=1040).grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(3, 0))

        # STEP 4 -----------------------------------------------------------------
        step4 = ttk.LabelFrame(editor_page, text="STEP 4 — CHOOSE FRAME RANGE", padding=(10, 8))
        step4.grid(row=5, column=0, sticky="ew", padx=4, pady=5)
        step4.columnconfigure(1, weight=1)
        step4.columnconfigure(3, weight=1)
        ttk.Label(step4, text="Start Frame", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.editor_quick_range_start_spin = ttk.Spinbox(step4, from_=0, to=0, textvariable=self.editor_range_start_var, width=12, command=self._editor_update_range_summary)
        self.editor_quick_range_start_spin.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(step4, text="End Frame", style="CardLabel.TLabel").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.editor_quick_range_end_spin = ttk.Spinbox(step4, from_=0, to=0, textvariable=self.editor_range_end_var, width=12, command=self._editor_update_range_summary)
        self.editor_quick_range_end_spin.grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        for spin in (self.editor_quick_range_start_spin, self.editor_quick_range_end_spin):
            spin.bind("<Return>", lambda _e: self._editor_update_range_summary())
            spin.bind("<FocusOut>", lambda _e: self._editor_update_range_summary())
        # Preserve backend widget attribute names without creating a second range workflow.
        self.editor_range_start_spin = self.editor_quick_range_start_spin
        self.editor_range_end_spin = self.editor_quick_range_end_spin
        ttk.Label(step4, textvariable=self.editor_range_summary_var, style="Muted.TLabel").grid(row=1, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 0))

        # STEP 5 -----------------------------------------------------------------
        step5 = ttk.LabelFrame(editor_page, text="STEP 5 — ENTER CHANGE + APPLY", padding=(10, 8))
        step5.grid(row=6, column=0, sticky="ew", padx=4, pady=5)
        step5.columnconfigure(1, weight=1)
        step5.columnconfigure(2, weight=2)
        ttk.Label(step5, text="Change Amount (Delta)", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(step5, textvariable=self.editor_delta_var, width=18).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(
            step5,
            text="5) APPLY CHANGE TO SELECTED FRAME RANGE",
            command=self.editor_guided_apply_range,
            style="Accent.TButton",
        ).grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        ttk.Label(
            step5,
            text="One button intentionally handles the selected range. Single-frame raw editing is Advanced-only to prevent accidental frame-0 edits.",
            style="Muted.TLabel", wraplength=1040,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=(2, 0))

        # STEP 6 -----------------------------------------------------------------
        step6 = ttk.LabelFrame(editor_page, text="STEP 6 — REVIEW + BUILD / VERIFY", padding=(10, 8))
        step6.grid(row=7, column=0, sticky="ew", padx=4, pady=5)
        step6.columnconfigure(0, weight=1)
        step6.columnconfigure(1, weight=1)
        ttk.Label(step6, textvariable=self.editor_review_var, style="CardLabel.TLabel", wraplength=1040).grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 6))
        ttk.Button(step6, text="RESET / START FRESH", command=self.editor_guided_load_map).grid(row=1, column=0, sticky="ew", padx=(4, 6), pady=4)
        ttk.Button(step6, text="6) BUILD + VERIFY ANIMATION", command=self.editor_build_anim, style="Accent.TButton").grid(row=1, column=1, sticky="ew", padx=(6, 4), pady=4)
        ttk.Checkbutton(
            step6,
            text="AUTO-GROW edited ANIM if compressed payload needs more room (recommended)",
            variable=self.editor_auto_grow_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 1))
        ttk.Label(
            step6,
            text="Restored v182 codec capability: when required, Motion Editor grows the loose ANIM payload, relocates proven local pointer tokens, then re-decodes every edited scalar for verification.",
            style="Muted.TLabel", wraplength=1040,
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(1, 2))

        # STEP 7 -----------------------------------------------------------------
        step7 = ttk.LabelFrame(editor_page, text="STEP 7 — CHOOSE OUTPUT", padding=(10, 8))
        step7.grid(row=8, column=0, sticky="ew", padx=4, pady=5)
        for col in range(3):
            step7.columnconfigure(col, weight=1)
        ttk.Label(
            step7,
            text=(
                "After Step 6 passes verification, choose a direct classic .ANIM, a NativeWRAP .WRAP.ANIM, "
                "or continue to XESM3 Mod Output. These output choices work for every Motion Editor character profile."
            ),
            style="Muted.TLabel", wraplength=1040,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=4, pady=(2, 5))
        ttk.Button(
            step7, text="7A) SAVE CLASSIC .ANIM", command=self.editor_export_classic_anim
        ).grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(
            step7, text="7B) SAVE WRAP.ANIM", command=self.editor_export_wrap_anim, style="Accent.TButton"
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(
            step7, text="7C) GO TO XESM3 MOD OUTPUT", command=self.editor_open_xesm3_output
        ).grid(row=1, column=2, sticky="ew", padx=4, pady=4)

        # ADVANCED ---------------------------------------------------------------
        advanced_toggle_row = ttk.Frame(editor_page, style="Body.TFrame")
        advanced_toggle_row.grid(row=9, column=0, sticky="ew", padx=4, pady=(8, 3))
        advanced_toggle_row.columnconfigure(0, weight=1)
        self.editor_advanced_toggle_btn = ttk.Button(advanced_toggle_row, text="▶ ADVANCED CONTROLS (OPTIONAL)", command=self.editor_toggle_advanced)
        self.editor_advanced_toggle_btn.grid(row=0, column=0, sticky="ew")

        ttk.Label(
            advanced_toggle_row,
            text="Optional steps: A1 choose ASKL only if auto-map fails → A2 load/edit JSON if needed → A3 choose technical track/frame → A4 inspect raw/scaled values → A5 SET/ADD precise value → A6 Build + Verify. Standard mods do not need this.",
            style="Muted.TLabel", wraplength=1040,
        ).grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))

        advanced = ttk.LabelFrame(editor_page, text="ADVANCED CONTROLS (OPTIONAL) — RAW / JSON / SINGLE FRAME", padding=(10, 8))
        advanced.grid(row=10, column=0, sticky="ew", padx=4, pady=(2, 6))
        advanced.columnconfigure(1, weight=1)
        advanced.columnconfigure(3, weight=1)
        self.editor_advanced_frame = advanced

        ttk.Label(advanced, text="A1) ASKL / Skeleton (if auto-map fails)", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.decoder_askl_var).grid(row=0, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="Pick Exact ASKL File", command=self.browse_decoder_askl).grid(row=0, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="Auto-Find in Folder", command=self.select_decoder_askl_folder).grid(row=0, column=4, sticky="ew", padx=4, pady=4)

        ttk.Label(advanced, text="A2) Editable JSON (optional)", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.codec_json_var).grid(row=1, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="Browse JSON", command=self.browse_codec_json).grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="Open JSON", command=self.open_codec_json).grid(row=1, column=4, sticky="ew", padx=4, pady=4)

        ttk.Button(advanced, text="A2) LOAD / MAP USING CURRENT JSON", command=self.editor_load_map).grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="SAVE EDITED JSON", command=self.editor_save_json).grid(row=2, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="A6) BUILD + VERIFY EDITED ANIM", command=self.editor_build_anim).grid(row=2, column=3, columnspan=2, sticky="ew", padx=4, pady=4)

        ttk.Separator(advanced, orient="horizontal").grid(row=3, column=0, columnspan=5, sticky="ew", padx=4, pady=7)
        ttk.Label(advanced, text="A3) Technical Track", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        self.editor_quick_track_spin = ttk.Spinbox(advanced, from_=0, to=0, textvariable=self.editor_quick_track_var, width=10, command=self.editor_quick_select_track)
        self.editor_quick_track_spin.grid(row=4, column=1, sticky="ew", padx=4, pady=4)
        self.editor_quick_track_spin.bind("<Return>", lambda _e: self.editor_quick_select_track())
        ttk.Button(advanced, text="SELECT TRACK", command=self.editor_quick_select_track).grid(row=4, column=2, sticky="ew", padx=4, pady=4)
        ttk.Label(advanced, text="Current Frame", style="CardLabel.TLabel").grid(row=4, column=3, sticky="e", padx=4, pady=4)
        self.editor_frame_spin = ttk.Spinbox(advanced, from_=0, to=0, textvariable=self.editor_frame_var, width=10, command=self._editor_refresh_value)
        self.editor_frame_spin.grid(row=4, column=4, sticky="ew", padx=4, pady=4)
        self.editor_quick_frame_spin = self.editor_frame_spin

        ttk.Label(advanced, text="A4) Current raw", style="CardLabel.TLabel").grid(row=5, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_current_raw_var, state="readonly").grid(row=5, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(advanced, text="ASKL scale", style="CardLabel.TLabel").grid(row=5, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_scale_var, state="readonly").grid(row=5, column=3, sticky="ew", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_track_var, state="readonly", width=10).grid(row=5, column=4, sticky="ew", padx=4, pady=4)

        ttk.Label(advanced, text="Pre-postprocess float", style="CardLabel.TLabel").grid(row=6, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_scaled_var, state="readonly").grid(row=6, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(advanced, text="New raw value", style="CardLabel.TLabel").grid(row=6, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_new_raw_var).grid(row=6, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="A5) SET THIS FRAME", command=self.editor_set_current_frame).grid(row=6, column=4, sticky="ew", padx=4, pady=4)

        ttk.Label(advanced, text="Delta", style="CardLabel.TLabel").grid(row=7, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(advanced, textvariable=self.editor_delta_var).grid(row=7, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="A5) ADD DELTA THIS FRAME", command=self.editor_add_delta_current).grid(row=7, column=2, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="REFRESH VALUE", command=self._editor_refresh_value).grid(row=7, column=3, columnspan=2, sticky="ew", padx=4, pady=4)

        ttk.Separator(advanced, orient="horizontal").grid(row=8, column=0, columnspan=5, sticky="ew", padx=4, pady=7)
        ttk.Label(advanced, text="A6) v182 Codec / Rebuild Options", style="CardLabel.TLabel").grid(row=9, column=0, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(advanced, text="Auto-select compression descriptors", variable=self.codec_auto_codecs_var).grid(row=9, column=1, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(advanced, text="Auto-grow + relocate if needed", variable=self.editor_auto_grow_var).grid(row=9, column=2, sticky="w", padx=4, pady=4)
        ttk.Button(advanced, text="BIT-IDENTICAL ROUNDTRIP", command=self.codec_roundtrip_test).grid(row=9, column=3, sticky="ew", padx=4, pady=4)
        ttk.Button(advanced, text="DECODE TO EDITABLE JSON", command=self.codec_decode_to_json).grid(row=9, column=4, sticky="ew", padx=4, pady=4)

        editor_text_frame = ttk.Frame(advanced, style="Body.TFrame")
        editor_text_frame.grid(row=10, column=0, columnspan=5, sticky="nsew", padx=4, pady=(6, 0))
        editor_text_frame.columnconfigure(0, weight=1)
        self.editor_text = tk.Text(
            editor_text_frame,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            height=7,
        )
        self.editor_text.grid(row=0, column=0, sticky="nsew")
        editor_y = ttk.Scrollbar(editor_text_frame, orient="vertical", command=self.editor_text.yview)
        editor_y.grid(row=0, column=1, sticky="ns")
        self.editor_text.configure(yscrollcommand=editor_y.set, state="disabled")
        advanced.grid_remove()

        # ------------------------------------------------------------------
        # Log page
        # ------------------------------------------------------------------
        log_page = ttk.Frame(self.workbook, style="Body.TFrame", padding=8)
        log_page.columnconfigure(0, weight=1)
        log_page.rowconfigure(0, weight=1)
        self.workbook.add(log_page, text="Log / Troubleshoot")
        self.log_text = tk.Text(
            log_page,
            bg=COLORS["field"],
            fg=COLORS["fg"],
            insertbackground=COLORS["fg"],
            selectbackground=COLORS["select"],
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            height=14,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(log_page, orient="vertical", command=self.log_text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=yscroll.set)

        self._remove_legacy_new_swapper_pages()

        footer = ttk.Frame(self, style="Card.TFrame", padding=8)
        footer.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(footer, textvariable=self.status_var, style="CardLabel.TLabel").pack(anchor="w")
        self.log("Ready. Animation Swapper = replace an ANIM. Motion Editor = edit motion inside an ANIM.")

    def _build_guided_animation_swapper_page(self):
        """v5.2.141 unrestricted WoS-style target-out -> replacement-in -> XESM3 workflow."""
        page_host = ttk.Frame(self.workbook, style="Body.TFrame")
        page_host.rowconfigure(0, weight=1)
        page_host.columnconfigure(0, weight=1)
        page_canvas = tk.Canvas(
            page_host,
            highlightthickness=0,
            borderwidth=0,
            background=COLORS.get("bg", "#17191F"),
        )
        page_scroll = ttk.Scrollbar(page_host, orient="vertical", command=page_canvas.yview)
        page_canvas.configure(yscrollcommand=page_scroll.set)
        page_canvas.grid(row=0, column=0, sticky="nsew")
        page_scroll.grid(row=0, column=1, sticky="ns")
        page = ttk.Frame(page_canvas, style="Body.TFrame", padding=8)
        page.columnconfigure(0, weight=1)
        page.columnconfigure(1, weight=1)
        page.rowconfigure(2, weight=1)
        page_window = page_canvas.create_window((0, 0), window=page, anchor="nw")

        def _sync_guided_page(_event=None):
            try:
                page_canvas.itemconfigure(page_window, width=max(1, page_canvas.winfo_width()))
                page_canvas.configure(scrollregion=page_canvas.bbox("all"))
            except Exception:
                pass

        page.bind("<Configure>", _sync_guided_page, add="+")
        page_canvas.bind("<Configure>", _sync_guided_page, add="+")
        self.workbook.add(page_host, text="Animation Swapper")
        self.guided_swap_page = page_host

        ttk.Label(page, text="ANIMATION SWAPPER — WoS-STYLE SWAP OUT → SWAP IN → XESM3", style="SectionTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 4)
        )
        ttk.Label(
            page,
            text=(
                "Use this when you want one animation to play in place of another. Choose the animation file to SWAP OUT, then choose the animation file to SWAP IN. "
                "The Toolkit will package the pair exactly as selected and will not block it for ASKL, size, version, track-count, or layout differences. Original PCPACK files are not modified."
            ),
            style="Muted.TLabel", wraplength=1000,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 8))

        step1 = ttk.LabelFrame(page, text="STEP 1 — CHOOSE ANIMATION FILE TO SWAP OUT", padding=(8, 7))
        step1.grid(row=2, column=0, sticky="nsew", padx=(4, 5), pady=4)
        step1.columnconfigure(0, weight=1)
        step1.rowconfigure(3, weight=1)
        target_top = ttk.Frame(step1, style="Body.TFrame")
        target_top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        target_top.columnconfigure(1, weight=1)
        ttk.Label(target_top, text="Search", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Entry(target_top, textvariable=self.swap_target_search_var).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(target_top, text="Browse Swap-Out ANIM", command=self.browse_swap_target).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(target_top, text="Scan", command=self.scan_pc_destination_slots).grid(row=0, column=3, sticky="ew", padx=(4, 0))
        self.swap_target_search_var.trace_add("write", lambda *_: self.refresh_swap_target_tree())
        ttk.Entry(step1, textvariable=self.source_file_var, state="readonly").grid(row=1, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(step1, text="Double-click an extracted animation below, select it, or browse the exact .anim / .wrap.anim file you want to swap OUT.", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 4))
        target_frame = ttk.Frame(step1, style="Body.TFrame")
        target_frame.grid(row=3, column=0, sticky="nsew")
        target_frame.columnconfigure(0, weight=1); target_frame.rowconfigure(0, weight=1)
        cols = ("name", "hash", "family", "size")
        self.swap_target_tree = ttk.Treeview(target_frame, columns=cols, show="headings", height=11)
        for col, width in (("name", 250), ("hash", 105), ("family", 90), ("size", 80)):
            self.swap_target_tree.heading(col, text=col.title())
            self.swap_target_tree.column(col, width=width, anchor="w")
        self.swap_target_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(target_frame, orient="vertical", command=self.swap_target_tree.yview)
        sb.grid(row=0, column=1, sticky="ns"); self.swap_target_tree.configure(yscrollcommand=sb.set)
        self.swap_target_tree.bind("<Double-1>", lambda _e: self.use_selected_swap_target())
        ttk.Button(step1, text="1) USE SELECTED AS SWAP-OUT ANIM", command=self.use_selected_swap_target, style="Accent.TButton").grid(row=4, column=0, sticky="ew", pady=(6, 0))

        step2 = ttk.LabelFrame(page, text="STEP 2 — CHOOSE ANIMATION FILE TO SWAP IN", padding=(8, 7))
        step2.grid(row=2, column=1, sticky="nsew", padx=(5, 4), pady=4)
        step2.columnconfigure(0, weight=1); step2.rowconfigure(3, weight=1)
        repl_top = ttk.Frame(step2, style="Body.TFrame")
        repl_top.grid(row=0, column=0, sticky="ew", pady=(0, 4)); repl_top.columnconfigure(1, weight=1)
        ttk.Label(repl_top, text="Search", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Entry(repl_top, textvariable=self.swap_replacement_search_var).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(repl_top, text="Browse Swap-In ANIM", command=self.browse_swap_replacement).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.swap_replacement_search_var.trace_add("write", lambda *_: self.refresh_swap_replacement_tree())
        ttk.Entry(step2, textvariable=self.target_file_var, state="readonly").grid(row=1, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(step2, text="Double-click an extracted animation below, select it, or browse any .anim / .wrap.anim file you want to swap IN. The Toolkit will not block your choice.", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 4))
        repl_frame = ttk.Frame(step2, style="Body.TFrame")
        repl_frame.grid(row=3, column=0, sticky="nsew"); repl_frame.columnconfigure(0, weight=1); repl_frame.rowconfigure(0, weight=1)
        self.swap_replacement_tree = ttk.Treeview(repl_frame, columns=cols, show="headings", height=11)
        for col, width in (("name", 250), ("hash", 105), ("family", 90), ("size", 80)):
            self.swap_replacement_tree.heading(col, text=col.title())
            self.swap_replacement_tree.column(col, width=width, anchor="w")
        self.swap_replacement_tree.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(repl_frame, orient="vertical", command=self.swap_replacement_tree.yview)
        sb2.grid(row=0, column=1, sticky="ns"); self.swap_replacement_tree.configure(yscrollcommand=sb2.set)
        self.swap_replacement_tree.bind("<Double-1>", lambda _e: self.use_selected_swap_replacement())
        ttk.Button(step2, text="2) USE SELECTED AS SWAP-IN ANIM", command=self.use_selected_swap_replacement, style="Accent.TButton").grid(row=4, column=0, sticky="ew", pady=(6, 0))

        freedom = ttk.LabelFrame(page, text="FREEDOM MODE — NO COMPATIBILITY GATE", padding=(8, 7))
        freedom.grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        freedom.columnconfigure(0, weight=1)
        ttk.Label(
            freedom,
            text=(
                "The Toolkit will not block the selected pair. It copies the full SWAP-IN ANIM bytes under the SWAP-OUT target resource path. "
                "This gives modders WoS-style freedom. A truly incompatible animation can still fail, be ignored, animate incorrectly, or crash at runtime, so testing is the user's choice."
            ),
            style="Muted.TLabel", wraplength=980,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=4)

        step3 = ttk.LabelFrame(page, text="STEP 3 — NAME + OUTPUT", padding=(8, 7))
        step3.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        step3.columnconfigure(1, weight=1); step3.columnconfigure(4, weight=1)
        ttk.Label(step3, text="Mod name", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(step3, textvariable=self.swap_mod_name_var).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(step3, text="Output folder", style="CardLabel.TLabel").grid(row=0, column=2, sticky="e", padx=(12, 4), pady=4)
        ttk.Entry(step3, textvariable=self.out_dir_var).grid(row=0, column=3, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Button(step3, text="Browse", command=self.browse_out_dir).grid(row=0, column=5, sticky="ew", padx=4, pady=4)

        step4 = ttk.LabelFrame(page, text="STEP 4 — CREATE XESM3 ANIMATION MOD", padding=(8, 7))
        step4.grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        step4.columnconfigure(0, weight=1)
        ttk.Button(step4, text="4A) CREATE XESM3 .ANIM SWAP MOD", command=self.build_guided_xesm3_anim_swap).grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(step4, text="4B) CREATE WRAP.ANIM SWAP MOD", command=self.build_guided_wrap_anim_swap, style="Accent.TButton").grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        ttk.Button(step4, text="Open Last Mod", command=self.open_guided_swap_output).grid(row=0, column=1, rowspan=2, sticky="nsew", padx=4, pady=4)
        ttk.Label(step4, textvariable=self.swap_build_status_var, style="Muted.TLabel", wraplength=1080).grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=(2, 4))

    def _swap_tree_path(self, tree):
        selected = tree.selection()
        if not selected:
            return None
        tags = tree.item(selected[0], "tags") or []
        if not tags:
            return None
        path = Path(tags[0])
        return path if path.is_file() else None

    def _refresh_swap_tree(self, tree, query: str):
        if tree is None:
            return
        query = (query or "").strip().lower()
        for item in tree.get_children():
            tree.delete(item)
        for row in self._pc_dest_rows:
            hay = f"{row.get('name','')} {row.get('hash','')} {row.get('family','')} {row.get('relative','')}".lower()
            if query and query not in hay:
                continue
            tree.insert("", "end", values=(row.get("name", ""), row.get("hash", ""), row.get("family", ""), row.get("size", "")), tags=(str(row.get("path", "")),))

    def refresh_swap_target_tree(self):
        self._refresh_swap_tree(getattr(self, "swap_target_tree", None), self.swap_target_search_var.get())

    def refresh_swap_replacement_tree(self):
        self._refresh_swap_tree(getattr(self, "swap_replacement_tree", None), self.swap_replacement_search_var.get())

    def use_selected_swap_target(self):
        path = self._swap_tree_path(getattr(self, "swap_target_tree", None))
        if not path:
            messagebox.showinfo("Select target", "Choose the animation you want to REPLACE first.")
            return
        self.source_file_var.set(str(path))
        self.swap_build_status_var.set(f"Target selected: {path.name}")

    def use_selected_swap_replacement(self):
        path = self._swap_tree_path(getattr(self, "swap_replacement_tree", None))
        if not path:
            messagebox.showinfo("Select replacement", "Choose the animation you want to USE as the replacement first.")
            return
        self.target_file_var.set(str(path))
        self.swap_build_status_var.set(f"Replacement selected: {path.name}")

    def _auto_detect_extracted_root_from_target(self, path: Path) -> None:
        """Best-effort convenience: locate a nearby extraction catalog from a browsed target ANIM."""
        cur = path.parent
        for _ in range(10):
            if (cur / "filelist.apkf.txt").is_file() or (cur / "06_MOD_LOADER_READY" / "filelist.apkf.txt").is_file():
                self.extracted_character_folder_var.set(str(cur))
                try:
                    self.scan_pc_destination_slots()
                except Exception:
                    pass
                return
            if cur.parent == cur:
                break
            cur = cur.parent

    def browse_swap_target(self):
        path = filedialog.askopenfilename(title="Select animation file to SWAP OUT", filetypes=[("SM3 ANIM / WRAP.ANIM", "*.anim"), ("All files", "*.*")])
        if path:
            p = Path(path)
            self.source_file_var.set(path)
            self.swap_build_status_var.set(f"Swap-out animation selected: {p.name}")
            self._auto_detect_extracted_root_from_target(p)

    def browse_swap_replacement(self):
        path = filedialog.askopenfilename(title="Select replacement / donor SM3 ANIM", filetypes=[("SM3 ANIM / WRAP.ANIM", "*.anim"), ("All files", "*.*")])
        if path:
            self.target_file_var.set(path)
            self.swap_build_status_var.set(f"Replacement selected: {Path(path).name}")

    def update_swap_compatibility(self, show_message: bool = False):
        """v5.2.141 compatibility gate removed. Kept as a non-blocking legacy API shim."""
        target = Path(self.source_file_var.get().strip().strip('"'))
        donor = Path(self.target_file_var.get().strip().strip('"'))
        if not target.is_file() or not donor.is_file():
            text = "Choose both a SWAP-OUT and SWAP-IN animation. No compatibility gate will be applied."
        else:
            text = (
                f"FREEDOM MODE ✅ — {target.name} ← {donor.name}. "
                "The Toolkit will not block this pair for ASKL, version, size, track count, or layout."
            )
        self.swap_compatibility_var.set(text)
        if show_message:
            messagebox.showinfo("ANIM Swapper Freedom Mode", text)
        return True

    def build_guided_xesm3_anim_swap(self):
        try:
            target = Path(self.source_file_var.get().strip().strip('"'))
            donor = Path(self.target_file_var.get().strip().strip('"'))
            extracted = Path(self.extracted_character_folder_var.get().strip().strip('"'))
            out_raw = self.out_dir_var.get().strip().strip('"')
            if not target.is_file():
                raise FileNotFoundError("STEP 1: choose a valid target animation first.")
            if not donor.is_file():
                raise FileNotFoundError("STEP 2: choose a valid replacement animation first.")
            if not extracted.is_dir():
                raise FileNotFoundError("Choose the extracted SM3 pack folder so the toolkit can resolve the target PACK/APKF owner.")
            if not out_raw:
                raise FileNotFoundError("STEP 3: choose an output folder first.")
            out = Path(out_raw); out.mkdir(parents=True, exist_ok=True)
            result = build_anim_swap_xesm3_output(
                target_anim=target,
                donor_anim=donor,
                extracted_pack_root=extracted,
                output_root=out,
                mod_name=self.swap_mod_name_var.get(),
                make_zip=True,
            )
            self._last_guided_swap_output = Path(result.mod_root)
            self.swap_build_status_var.set(
                f"BUILD PASS ✅ — {result.identity.resource_name} now uses donor 0x{result.donor_hash:08X}. Ready ZIP: {Path(result.zip_path).name}"
            )
            self.log(
                f"Guided XESM3 ANIM swap PASS: target 0x{result.target_hash:08X} <- donor 0x{result.donor_hash:08X} -> "
                f"{result.identity.pack}/{result.identity.archive}/{result.identity.target_filename}"
            )
            try:
                open_path(Path(result.mod_root))
            except Exception:
                pass
            messagebox.showinfo(
                "XESM3 ANIM Swap Build PASS",
                f"Target: 0x{result.target_hash:08X} {result.identity.resource_name}\n"
                f"Replacement donor: 0x{result.donor_hash:08X}\n"
                f"Target ASKL metadata: 0x{result.askl_hash:08X}\n"
                "Toolkit compatibility gate: OFF (freedom mode)\n\n"
                f"Ready ZIP:\n{result.zip_path}\n\n"
                f"Enable with:\n[EnabledMods]\n{result.mod_name}=100"
            )
        except Exception as exc:
            self.swap_build_status_var.set(f"BUILD FAILED — {exc}")
            messagebox.showerror("Create XESM3 animation swap", str(exc))
            self.log(f"Guided XESM3 ANIM swap failed: {exc}")

    def build_guided_wrap_anim_swap(self):
        """v5.2.184 WRAP button: target <- donor NativeWRAP animation mod."""
        try:
            target = Path(self.source_file_var.get().strip().strip('"'))
            donor = Path(self.target_file_var.get().strip().strip('"'))
            extracted = Path(self.extracted_character_folder_var.get().strip().strip('"'))
            out_raw = self.out_dir_var.get().strip().strip('"')
            if not target.is_file():
                raise FileNotFoundError("STEP 1: choose a valid target animation first.")
            if not donor.is_file():
                raise FileNotFoundError("STEP 2: choose a valid replacement animation first.")
            if not extracted.is_dir():
                raise FileNotFoundError("Choose the MOD LOADER READY extracted pack folder containing WRAP_EXTRACTS.")
            if not out_raw:
                raise FileNotFoundError("STEP 3: choose an output folder first.")
            out = Path(out_raw); out.mkdir(parents=True, exist_ok=True)
            result = build_wrap_anim_xesm3_output(
                target_anim=target,
                donor_anim=donor,
                extracted_pack_root=extracted,
                output_root=out,
                mod_name=self.swap_mod_name_var.get(),
                make_zip=True,
            )
            self._last_guided_swap_output = Path(result.mod_root)
            self.swap_build_status_var.set(
                f"WRAP BUILD PASS ✅ — target 0x{result.target_hash:08X} | {result.donor_mode} | {Path(result.zip_path).name}"
            )
            self.log(
                f"Guided WRAP.ANIM swap PASS: target 0x{result.target_hash:08X} <- donor 0x{result.donor_hash:08X} -> "
                f"{result.pack}/{result.archive}/{Path(result.output_wrap_anim).name}"
            )
            try:
                open_path(Path(result.mod_root))
            except Exception:
                pass
        except Exception as exc:
            self.swap_build_status_var.set(f"WRAP BUILD FAILED — {exc}")
            messagebox.showerror("WRAP.ANIM Swap", str(exc))
            self.log(f"Guided WRAP.ANIM swap failed: {exc}")

    def open_guided_swap_output(self):
        path = self._last_guided_swap_output
        if path and Path(path).exists():
            open_path(Path(path))
        else:
            self.open_output()

    def _remove_legacy_new_swapper_pages(self):
        """Remove legacy PC Slots / PCPACK / NAS pages from the New Animation Swapper notebook.

        Their backend/source remains in this development tree for preservation, but v5.2.141
        intentionally exposes only the new swapper, Motion Editor, XESM3 output, and troubleshoot UI.
        The separate Old Animation Swapper tab is not changed here.
        """
        for page in (
            getattr(self, "legacy_pc_page", None),
            getattr(self, "legacy_manual_page", None),
            getattr(self, "legacy_csv_page", None),
        ):
            if page is not None:
                try:
                    self.workbook.forget(page)
                except Exception:
                    pass

    def _build_optional_tools_page_legacy_internal(self):
        page = ttk.Frame(self.workbook, style="Body.TFrame", padding=10)
        page.columnconfigure(0, weight=1)
        self.workbook.add(page, text="Optional / Advanced Tools")
        self.optional_tools_page = page
        ttk.Label(page, text="OPTIONAL / ADVANCED ANIMATION TOOLS", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(
            page,
            text=(
                "You do NOT need these for normal XESM3 animation swaps or normal Motion Editor edits. "
                "They are preserved for legacy PCPACK slot-preserve work, NAS batch CSV work, and troubleshooting/research."
            ), style="Muted.TLabel", wraplength=1080,
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))
        box = ttk.LabelFrame(page, text="OPTIONAL WORKFLOWS", padding=(10, 8))
        box.grid(row=2, column=0, sticky="ew"); box.columnconfigure(0, weight=1)
        ttk.Label(box, text="A1) Legacy PC Slots — old destination-slot browser (the new Animation Swapper already includes search).", style="CardLabel.TLabel").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Button(box, text="OPEN LEGACY PC SLOTS", command=lambda: self._show_optional_workbook_page(self.legacy_pc_page, "Legacy PC Slots (Optional)")).grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(box, text="A2) Legacy PCPACK — safe slot-preserve patching when you intentionally do not want XESM3.", style="CardLabel.TLabel").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Button(box, text="OPEN LEGACY PCPACK", command=lambda: self._show_optional_workbook_page(self.legacy_manual_page, "Legacy PCPACK (Optional)")).grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(box, text="A3) Batch / NAS CSV — batch legacy slot-preserve swaps from CSV.", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Button(box, text="OPEN BATCH / NAS CSV", command=lambda: self._show_optional_workbook_page(self.legacy_csv_page, "Batch / NAS CSV (Optional)")).grid(row=2, column=1, sticky="ew", padx=4, pady=4)
        ttk.Button(box, text="HIDE OPTIONAL LEGACY TABS", command=self._hide_optional_workbook_pages).grid(row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=(8, 4))

    def _show_optional_workbook_page(self, page, label: str):
        try:
            self.workbook.add(page, text=label)
        except tk.TclError:
            pass
        try:
            self.workbook.select(page)
        except Exception:
            pass

    def _hide_optional_workbook_pages(self):
        for page in (getattr(self, "legacy_pc_page", None), getattr(self, "legacy_manual_page", None), getattr(self, "legacy_csv_page", None)):
            if page is not None:
                try:
                    self.workbook.hide(page)
                except Exception:
                    pass
        try:
            self.workbook.select(self.optional_tools_page)
        except Exception:
            pass

    def scan_pc_destination_slots(self):
        try:
            folder = self._extracted_character_folder()
            rows = scan_pc_animation_slots(folder)
            self._pc_dest_rows = rows
            self.refresh_destination_tree()
            self.refresh_swap_target_tree()
            self.refresh_swap_replacement_tree()
            self.swap_build_status_var.set(f"Scan complete — {len(rows)} unique ANIM resources found in {folder.name}.")
            self.log(f"Scanned PC destination animation slots: {len(rows)} found in {folder.name}.")
        except Exception as exc:
            messagebox.showerror("Scan PC animations failed", str(exc))
            self.log(f"Scan PC animations failed: {exc}")

    def refresh_destination_tree(self):
        if not hasattr(self, "destination_tree"):
            return
        query = self.destination_search_var.get().strip().lower()
        for item in self.destination_tree.get_children():
            self.destination_tree.delete(item)
        for row in self._pc_dest_rows:
            hay = f"{row.get('name','')} {row.get('hash','')} {row.get('family','')} {row.get('relative','')}".lower()
            if query and query not in hay:
                continue
            self.destination_tree.insert(
                "",
                "end",
                values=(row.get("name", ""), row.get("hash", ""), row.get("size", ""), row.get("family", ""), row.get("relative", "")),
                tags=(str(row.get("path", "")),),
            )

    def clear_destination_search(self):
        self.destination_search_var.set("")
        self.refresh_destination_tree()

    def use_selected_destination_as_source(self):
        if not hasattr(self, "destination_tree"):
            return
        selected = self.destination_tree.selection()
        if not selected:
            messagebox.showinfo("No animation selected", "Select a PC destination animation row first.")
            return
        item = selected[0]
        tags = self.destination_tree.item(item, "tags") or []
        path = Path(tags[0]) if tags else None
        if not path or not path.exists():
            vals = self.destination_tree.item(item, "values") or []
            name = vals[0] if vals else "selected animation"
            messagebox.showwarning("Missing selected file", f"Could not resolve file path for {name}.")
            return
        self.source_file_var.set(str(path))
        self.log(f"Set Source OUT from PC Destination Slot Library — Steps 4 and 5: {path.name}")


    def refresh_known_anims(self):
        if not hasattr(self, "known_tree"):
            return
        query = self.known_search_var.get().strip().lower()
        for item in self.known_tree.get_children():
            self.known_tree.delete(item)
        for label, anim, family, note in KNOWN_SM3_SPIDERMAN_ANIMS:
            hay = f"{label} {anim} {family} {note}".lower()
            if query and query not in hay:
                continue
            self.known_tree.insert("", "end", values=(label, anim, family, note))

    def clear_known_search(self):
        self.known_search_var.set("")
        self.refresh_known_anims()

    def browse_character_pack(self):
        path = filedialog.askopenfilename(
            title="Select clean original character PCPACK",
            filetypes=[("SM3 character packs", "CH_SPIDERMAN.PCPACK CH_BLACKSUIT.PCPACK CH_PETER.PCPACK CH_GOBLIN.PCPACK"), ("PCPACK", "*.PCPACK"), ("All files", "*.*")],
        )
        if path:
            self.character_pack_var.set(path)

    def browse_extracted_character_folder(self):
        path = filedialog.askdirectory(title="Select extracted character pack folder")
        if path:
            self.extracted_character_folder_var.set(path)
            try:
                self.scan_pc_destination_slots()
            except Exception:
                pass

    def browse_character_test_csv(self):
        path = filedialog.askopenfilename(
            title="Import 8) NAS CSV (New Animation Swapper CSV)",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self.character_test_csv_var.set(path)
            self.preview_csv(Path(path))

    def browse_out_dir(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.out_dir_var.set(path)



    def _manual_pair_safety_report(self) -> dict[str, object]:
        destination_anim = self._source_path()
        replacement_anim = self._target_path()
        if not destination_anim.exists() or not destination_anim.is_file():
            raise FileNotFoundError(f"Source OUT / destination animation not found: {destination_anim}")
        if not replacement_anim.exists() or not replacement_anim.is_file():
            raise FileNotFoundError(f"Replacement IN animation not found: {replacement_anim}")
        d_hash, d_name = _clean_anim_display_name(destination_anim)
        r_hash, r_name = _clean_anim_display_name(replacement_anim)
        d_family = _guess_anim_family(d_name)
        r_family = _guess_anim_family(r_name)
        d_size = destination_anim.stat().st_size
        r_size = replacement_anim.stat().st_size
        same_family = d_family == r_family and d_family != "unknown"
        if r_size > d_size:
            safety = "BLOCKED_SAFE_MODE_REPLACEMENT_BIGGER"
            enabled = "0"
            mode = "blocked_bigger_than_destination"
        elif same_family:
            safety = "SAFE_SLOT_PRESERVE_SAME_FAMILY"
            enabled = "1"
            mode = "slot_preserve"
        elif d_family == "unknown" or r_family == "unknown":
            safety = "REVIEW_UNKNOWN_FAMILY_SLOT_PRESERVE_SIZE_OK"
            enabled = "1"
            mode = "slot_preserve"
        else:
            safety = "RISKY_CROSS_FAMILY_SLOT_PRESERVE_SIZE_OK"
            enabled = "1"
            mode = "slot_preserve"
        return {
            "destination_path": str(destination_anim),
            "replacement_path": str(replacement_anim),
            "destination_name": d_name,
            "replacement_name": r_name,
            "destination_hash": d_hash,
            "replacement_hash": r_hash,
            "destination_family": d_family,
            "replacement_family": r_family,
            "destination_size": d_size,
            "replacement_size": r_size,
            "padding_bytes": max(0, d_size - r_size),
            "size_delta": r_size - d_size,
            "safety": safety,
            "enabled": enabled,
            "mode": mode,
        }

    def preview_manual_pair_safety(self):
        try:
            report = self._manual_pair_safety_report()
            msg = (
                f"Destination: {report['destination_name']}\n"
                f"Replacement: {report['replacement_name']}\n\n"
                f"Destination size: {report['destination_size']} bytes\n"
                f"Replacement size: {report['replacement_size']} bytes\n"
                f"Unused slot room if safe: {report['padding_bytes']} bytes\n\n"
                f"Destination family: {report['destination_family']}\n"
                f"Replacement family: {report['replacement_family']}\n\n"
                f"Safety: {report['safety']}"
            )
            self.log(f"Manual pair safety: {report.get('safety')} | destination {report.get('destination_name')} ({report.get('destination_size')} bytes) | replacement {report.get('replacement_name')} ({report.get('replacement_size')} bytes).")
            messagebox.showinfo("Manual pair safety preview", msg)
        except Exception as exc:
            messagebox.showerror("Preview manual pair failed", str(exc))
            self.log(f"Preview manual pair failed: {exc}")

    def build_nas_csv_from_manual_pair(self):
        try:
            report = self._manual_pair_safety_report()
            out_base = self._out_dir()
            if out_base is None:
                return
            out_root = out_base / "NAS_CSV_FROM_MANUAL_PAIR"
            out_root.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(report.get("destination_name") or "manual_pair"))[:80]
            csv_path = out_root / f"NAS_MANUAL_PAIR_{safe_name}.csv"
            counter = 1
            while csv_path.exists():
                csv_path = out_root / f"NAS_MANUAL_PAIR_{safe_name}_{counter:03d}.csv"
                counter += 1
            note = (
                f"manual_pair_builder; safety={report['safety']}; "
                f"dest_family={report['destination_family']}; repl_family={report['replacement_family']}; "
                f"dest_size={report['destination_size']}; repl_size={report['replacement_size']}; padding={report['padding_bytes']}"
            )
            with csv_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["enabled", "mode", "destination", "replacement", "note"])
                writer.writeheader()
                writer.writerow({
                    "enabled": report["enabled"],
                    "mode": report["mode"],
                    "destination": report["destination_path"],
                    "replacement": report["replacement_path"],
                    "note": note,
                })
            self.character_test_csv_var.set(str(csv_path))
            self.preview_csv(csv_path)
            self._show_optional_workbook_page(self.legacy_csv_page, "Batch / NAS CSV (Optional)")
            self.log(f"Built NAS CSV from manual pair: {csv_path.name}")
            self.log(f"Safety: {report.get('safety')} | padding: {report.get('padding_bytes')} bytes.")
            try:
                open_path(csv_path.parent)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Build 8) NAS CSV from manual pair failed", str(exc))
            self.log(f"Build 8) NAS CSV from manual pair failed: {exc}")

    def browse_source_file(self):
        path = filedialog.askopenfilename(
            title="Select Source OUT / destination animation slot",
            filetypes=[("Animation / WRAP.ANIM files", "*.anim"), ("All files", "*.*")],
        )
        if path:
            self.source_file_var.set(path)

    def browse_target_file(self):
        path = filedialog.askopenfilename(
            title="Select Replacement IN animation",
            filetypes=[("Animation / WRAP.ANIM files", "*.anim"), ("All files", "*.*")],
        )
        if path:
            self.target_file_var.set(path)

    def sm3_character_slot_preserve_threaded(self):
        threading.Thread(target=self.sm3_character_slot_preserve_swap, daemon=True).start()

    def sm3_character_slot_preserve_swap(self):
        try:
            original_pack = self._character_pack_path()
            extracted_folder = self._extracted_character_folder()
            destination_anim = self._source_path()
            replacement_anim = self._target_path()
            out = self._out_dir()
            if original_pack is None:
                return
            if out is None:
                return
            if not original_pack.exists():
                messagebox.showwarning("Missing original pack", "Select the clean original character PCPACK first.")
                return
            if not extracted_folder.exists():
                messagebox.showwarning("Missing extracted folder", "Select the extracted character pack folder first.")
                return
            if not destination_anim.exists() or not replacement_anim.exists():
                messagebox.showwarning("Missing animation files", "Select Source OUT/destination .anim and Replacement IN .anim first.")
                return
            dsz = destination_anim.stat().st_size
            rsz = replacement_anim.stat().st_size
            if rsz > dsz:
                messagebox.showwarning(
                    "Replacement is bigger",
                    f"SAFE slot-preserve blocks bigger replacements.\n\nDestination slot: {dsz} bytes\nReplacement: {rsz} bytes\n\nBigger replacements are intentionally blocked by the safe PCPACK route. Use a rebuilt loose ANIM with XESM3 Mod Output instead.",
                )
                return
            msg = (
                "SAFE slot-preserve keeps the destination slot size unchanged.\n\n"
                f"Destination slot: {dsz} bytes\nReplacement: {rsz} bytes\n\n"
                "Best tests are same-family animations: combat->combat, swing->swing, jump->jump, idle->idle.\n\nContinue?"
            )
            if not messagebox.askyesno("Confirm safe slot-preserve character animation patch", msg):
                return
            self.log("Running SAFE slot-preserve SM3 character animation patch...")
            result = character_anim_slot_preserve_swap(
                original_pack=original_pack,
                extracted_folder=extracted_folder,
                destination_anim=destination_anim,
                replacement_anim=replacement_anim,
                output_root=out,
            )
            self.log("SAFE slot-preserve character animation patch complete.")
            final_pack = Path(str(result.get('final_patched_pack') or '')).name
            if final_pack:
                self.log(f"Patched PCPACK written: {final_pack}")
            try:
                open_path(Path(result.get("final_patched_pack", "")).parent)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Safe slot-preserve animation patch failed", str(exc))
            self.log(f"Safe slot-preserve animation patch failed: {exc}")

    def sm3_character_repack_threaded(self):
        threading.Thread(target=self.sm3_character_repack_swap, daemon=True).start()

    def sm3_character_repack_swap(self):
        try:
            original_pack = self._character_pack_path()
            extracted_folder = self._extracted_character_folder()
            destination_anim = self._source_path()
            replacement_anim = self._target_path()
            out = self._out_dir()
            if original_pack is None:
                return
            if out is None:
                return
            if not original_pack.exists():
                messagebox.showwarning("Missing original pack", "Select the clean original character PCPACK first.")
                return
            if not extracted_folder.exists():
                messagebox.showwarning("Missing extracted folder", "Select the extracted character pack folder first.")
                return
            if not destination_anim.exists() or not replacement_anim.exists():
                messagebox.showwarning("Missing animation files", "Select Source OUT/destination .anim and Replacement IN .anim first.")
                return
            dsz = destination_anim.stat().st_size
            rsz = replacement_anim.stat().st_size
            msg = (
                "ALT 2) EXPERIMENTAL SIZE-CHANGE REPACK can grow/shrink the character pack and may fail boot if the pick is bad.\n\n"
                f"Destination slot: {dsz} bytes\nReplacement: {rsz} bytes\nSize delta: {rsz-dsz:+} bytes\n\n"
                "Use this mainly after safe slot-preserve tests, and only for animations Spider-Man / the same character skeleton can likely use.\n\nContinue?"
            )
            if not messagebox.askyesno("Confirm experimental SM3 character repack", msg):
                return
            self.log("Running EXPERIMENTAL SM3 character animation size-change repack...")
            result = character_anim_repack_swap(
                original_pack=original_pack,
                extracted_folder=extracted_folder,
                destination_anim=destination_anim,
                replacement_anim=replacement_anim,
                output_root=out,
                allow_size_change=True,
            )
            self.log("Experimental SM3 character animation repack complete.")
            final_pack = Path(str(result.get('final_patched_pack') or '')).name
            if final_pack:
                self.log(f"Patched PCPACK written: {final_pack}")
            try:
                open_path(Path(result.get("final_patched_pack", "")).parent)
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("Experimental SM3 character repack failed", str(exc))
            self.log(f"Experimental SM3 character repack failed: {exc}")

    # ------------------------------------------------------------------
    # TEMP v5.2.122 — NAS reversible scalar ANIM codec / template rebuilder
    # ------------------------------------------------------------------

    def _codec_anim_path(self) -> Path:
        raw = self.decoder_anim_var.get().strip().strip('"')
        if not raw:
            raise AnimCodecError("Select an extracted SM3 .anim or .wrap.anim first.")
        path = Path(raw)
        if not path.exists() or not path.is_file():
            raise AnimCodecError(f"ANIM file not found: {path}")
        return path

    def _codec_output_dirs(self, anim_path: Path) -> tuple[Path, Path, Path]:
        raw_out = self.out_dir_var.get().strip().strip('"')
        base = Path(raw_out) if raw_out else anim_path.parent / "NAS_ANIM_CODEC_OUTPUT"
        root = base / "NAS_ANIM_CODEC" if raw_out else base
        edited = root / "edited"
        rebuilt = root / "rebuilt"
        reports = root / "reports"
        for folder in (edited, rebuilt, reports):
            folder.mkdir(parents=True, exist_ok=True)
        return edited, rebuilt, reports

    def _set_codec_text(self, text: str):
        if not hasattr(self, "codec_text"):
            return
        self.codec_text.configure(state="normal")
        self.codec_text.delete("1.0", "end")
        self.codec_text.insert("1.0", str(text))
        self.codec_text.configure(state="disabled")

    def use_source_out_for_codec(self):
        path = self._source_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("NAS ANIM Codec", "Select a valid Source OUT animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.codec_page)

    def use_replacement_in_for_codec(self):
        path = self._target_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("NAS ANIM Codec", "Select a valid Replacement IN animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.codec_page)

    def browse_codec_json(self):
        start = self.codec_json_var.get().strip().strip('"')
        initial = str(Path(start).parent) if start and Path(start).exists() else None
        path = filedialog.askopenfilename(
            title="Select SM3 ANIM editable JSON",
            initialdir=initial,
            filetypes=[("SM3 ANIM Codec JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.codec_json_var.set(path)
            self.codec_status_var.set(f"Editable JSON selected: {Path(path).name}")

    def open_codec_json(self):
        raw = self.codec_json_var.get().strip().strip('"')
        if not raw:
            messagebox.showinfo("NAS ANIM Codec", "Decode an ANIM or select an editable JSON first.")
            return
        path = Path(raw)
        if not path.exists():
            messagebox.showwarning("NAS ANIM Codec", f"JSON file not found:\n{path}")
            return
        open_path(path)

    def open_codec_rebuilt(self):
        raw = self.codec_rebuilt_var.get().strip().strip('"')
        if raw and Path(raw).exists():
            open_path(Path(raw).parent)
            return
        try:
            anim_path = self._codec_anim_path()
            _edited, rebuilt, _reports = self._codec_output_dirs(anim_path)
            open_path(rebuilt)
        except Exception as exc:
            messagebox.showwarning("NAS ANIM Codec", str(exc))

    def codec_roundtrip_test(self):
        try:
            anim_path = self._codec_anim_path()
            data = read_anim_payload(anim_path)
            decoded = codec_decode_anim(data)
            rebuilt, info = codec_encode_frames_into_template(data, decoded, auto_codecs=False)
            if rebuilt != data:
                first = next((i for i, (a, b) in enumerate(zip(data, rebuilt)) if a != b), None)
                if first is None and len(data) != len(rebuilt):
                    detail = f"size differs: {len(data)} != {len(rebuilt)}"
                else:
                    detail = f"first byte difference at 0x{int(first or 0):X}"
                raise AnimCodecError(f"Bit-identical roundtrip FAILED ({detail}).")
            self._codec_last_decoded = decoded
            summary = codec_inspect_text(decoded, str(anim_path))
            summary += (
                "\n\nROUNDTRIP PASS — entire .anim is bit-identical"
                f"\nbits_written={info['bits_written']}"
                f" capacity_bits={info['capacity_bits']}"
                f" free_bits={info['free_bits']}"
            )
            self._set_codec_text(summary)
            self.codec_status_var.set(
                f"ROUNDTRIP PASS: {anim_path.name} — {decoded.header.frame_count} frames, "
                f"{decoded.header.compressed_track_count} tracks, {info['free_bits']} free bits."
            )
            self.log(f"NAS Codec roundtrip PASS: {anim_path.name} — whole file bit-identical.")
        except Exception as exc:
            self.codec_status_var.set("ROUNDTRIP FAILED")
            messagebox.showerror("NAS ANIM Codec", str(exc))
            self.log(f"NAS Codec roundtrip failed: {exc}")

    def codec_decode_to_json(self):
        try:
            anim_path = self._codec_anim_path()
            decoded = codec_decode_anim(read_anim_payload(anim_path))
            edited, _rebuilt, reports = self._codec_output_dirs(anim_path)
            json_path = edited / f"{anim_path.name}.json"
            csv_path = reports / f"{anim_path.name}.frames.csv"
            json_path.write_text(
                json.dumps(codec_decoded_to_json_dict(decoded, str(anim_path)), indent=2),
                encoding="utf-8",
            )
            codec_write_frames_csv(decoded, csv_path)
            self.codec_json_var.set(str(json_path))
            self._codec_last_decoded = decoded
            summary = codec_inspect_text(decoded, str(anim_path))
            summary += f"\n\nEditable JSON: {json_path}\nFrame CSV: {csv_path}"
            self._set_codec_text(summary)
            self.codec_status_var.set(
                f"Decoded {decoded.header.frame_count} frames x {decoded.header.compressed_track_count} tracks to {json_path.name}."
            )
            self.log(f"NAS Codec decoded editable JSON: {json_path.name}")
        except Exception as exc:
            self.codec_status_var.set("Decode to editable JSON failed.")
            messagebox.showerror("NAS ANIM Codec", str(exc))
            self.log(f"NAS Codec JSON decode failed: {exc}")

    def codec_build_edited_anim(self, motion_editor_auto_grow: bool = False):
        """Build edited scalar frames back into an ANIM template.

        Direct legacy codec use keeps its explicit resize checkbox behavior.
        Guided Motion Editor may request an automatic retry with the proven
        arbitrary-size loose-resource relocator when (and only when) the
        recompressed bitstream exceeds the original payload capacity.
        """
        self.codec_rebuilt_var.set("")
        try:
            anim_path = self._codec_anim_path()
            raw_json = self.codec_json_var.get().strip().strip('"')
            if not raw_json:
                raise AnimCodecError("Decode to editable JSON first or select an SM3_ANIM_CODEC_JSON_V1 file.")
            json_path = Path(raw_json)
            if not json_path.exists() or not json_path.is_file():
                raise AnimCodecError(f"Editable JSON not found: {json_path}")
            obj = codec_load_json(json_path)
            template = read_anim_payload(anim_path)
            explicit_resize = bool(self.codec_allow_resize_var.get())
            auto_grow_retry = False
            try:
                rebuilt_bytes, info = codec_encode_frames_into_template(
                    template, obj,
                    auto_codecs=bool(self.codec_auto_codecs_var.get()),
                    allow_arbitrary_size=explicit_resize,
                )
            except AnimCodecError as first_exc:
                capacity_error = (
                    "encoded bitstream requires" in str(first_exc)
                    and "template payload has only" in str(first_exc)
                )
                if not (motion_editor_auto_grow and capacity_error and not explicit_resize):
                    raise
                rebuilt_bytes, info = codec_encode_frames_into_template(
                    template, obj,
                    auto_codecs=bool(self.codec_auto_codecs_var.get()),
                    allow_arbitrary_size=True,
                )
                auto_grow_retry = True
                self.log(
                    "NAS Motion Editor AUTO-GROW: fixed-size payload was too small; "
                    f"rebuilt loose ANIM with relocated local tokens ({info.get('size_delta_bytes', 0):+} bytes)."
                )
            verify = codec_decode_anim(rebuilt_bytes)
            requested_frames = [[int(v) for v in row] for row in obj["frames"]]
            if verify.frames != requested_frames:
                raise AnimCodecError("Rebuilt ANIM decoded, but scalar frames do not match the editable JSON.")
            _edited, rebuilt_dir, reports = self._codec_output_dirs(anim_path)
            base_name = anim_path.name[:-10] if anim_path.name.lower().endswith(".wrap.anim") else anim_path.stem
            out_path = rebuilt_dir / f"{base_name}_EDITED.anim"
            out_path.write_bytes(rebuilt_bytes)
            report = {
                "status": "PASS",
                "template": str(anim_path),
                "editable_json": str(json_path),
                "output": str(out_path),
                "frame_count": verify.header.frame_count,
                "compressed_track_count": verify.header.compressed_track_count,
                "bits_written": info["bits_written"],
                "capacity_bits": info["capacity_bits"],
                "free_bits": info["free_bits"],
                "auto_codecs": info["auto_codecs"],
                "allow_arbitrary_size": info.get("allow_arbitrary_size", False),
                "motion_editor_auto_grow_retry": auto_grow_retry,
                "rebuild_mode": info.get("rebuild_mode", "TEMPLATE_SIZE"),
                "resized": info.get("resized", False),
                "size_delta_bytes": info.get("size_delta_bytes", 0),
                "old_file_size": info.get("old_file_size", len(template)),
                "new_file_size": info.get("new_file_size", len(rebuilt_bytes)),
                "relocated_known_tokens": info.get("relocated_known_tokens", 0),
                "verification": "re-decoded scalar frames exactly match requested JSON",
            }
            report_path = reports / f"{anim_path.stem}_EDITED.build.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            self.codec_rebuilt_var.set(str(out_path))
            summary = codec_inspect_text(verify, str(out_path))
            summary += (
                "\n\nENCODE PASS — re-decoded scalar frames match editable JSON"
                f"\nOutput: {out_path}"
                f"\nbits_written={info['bits_written']} capacity_bits={info['capacity_bits']} free_bits={info['free_bits']}"
                f"\nrebuild_mode={info.get('rebuild_mode')} resized={info.get('resized')} size_delta_bytes={info.get('size_delta_bytes')}"
                f"\nold_file_size={info.get('old_file_size')} new_file_size={info.get('new_file_size')} relocated_known_tokens={info.get('relocated_known_tokens')}"
                "\nNOTE: ARBITRARY_SIZE_LOOSE is an experimental loose-resource rebuild for NativeANIM testing; generic size-changing PCPACK/APKF reconstruction remains separate."
            )
            self._set_codec_text(summary)
            mode = info.get("rebuild_mode", "TEMPLATE_SIZE")
            grow_note = " | AUTO-GROW USED" if auto_grow_retry else ""
            self.codec_status_var.set(
                f"BUILD PASS [{mode}]{grow_note}: {out_path.name} — size {info.get('old_file_size')} -> {info.get('new_file_size')} bytes; {info['free_bits']} free bits."
            )
            self.log(f"NAS Codec build PASS: {out_path.name}; scalar frames verified after re-decode.")
            return True
        except Exception as exc:
            self.codec_status_var.set("Build edited ANIM failed.")
            messagebox.showerror("NAS ANIM Codec", str(exc))
            self.log(f"NAS Codec build failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # TEMP v5.2.129 — quick motion edit + ASKL file/folder scan + T4 HSAM fallback
    # ------------------------------------------------------------------

    def _set_editor_text(self, text: str):
        if not hasattr(self, "editor_text"):
            return
        self.editor_text.configure(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", str(text))
        self.editor_text.configure(state="disabled")

    def use_source_out_for_editor(self):
        path = self._source_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("NAS Motion Editor", "Select a valid Source OUT animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.editor_page)

    def use_replacement_in_for_editor(self):
        path = self._target_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("NAS Motion Editor", "Select a valid Replacement IN animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.editor_page)

    def _editor_select_track_index(self, track_index: int):
        """Select a flat compressed track and synchronize the Advanced mapping UI."""
        editor = self._anim_editor
        if editor is None:
            raise AnimCodecError("Load/map the Motion Editor first.")
        track_index = int(track_index)
        binding = editor.binding_by_track.get(track_index)
        if binding is None:
            raise AnimCodecError(f"track {track_index} outside 0..{editor.track_count - 1}")

        self.editor_quick_track_var.set(str(track_index))
        self.editor_field_var.set(binding.field_name)
        self._editor_populate_elements()

        wanted_key = binding.element_key
        wanted_label = None
        for label, key in self._editor_element_label_to_key.items():
            if key == wanted_key:
                wanted_label = label
                break
        if wanted_label is not None:
            self.editor_element_var.set(wanted_label)
            self._editor_populate_components()

        if binding.component_name in self._editor_component_to_binding:
            self.editor_component_var.set(binding.component_name)
        self._editor_refresh_value()
        return binding

    def editor_quick_select_track(self, quiet: bool = False):
        try:
            track = int(str(self.editor_quick_track_var.get()).strip(), 0)
            binding = self._editor_select_track_index(track)
            self.editor_status_var.set(
                f"Quick track {binding.track_index} selected — {binding.field_name} / {binding.element_label} / {binding.component_name}."
            )
            return True
        except Exception as exc:
            if not quiet:
                messagebox.showerror("NAS Motion Editor", str(exc))
            return False

    def editor_quick_add_delta_current(self):
        if not self.editor_quick_select_track():
            return
        self.editor_add_delta_current()

    def editor_quick_add_delta_range(self):
        if not self.editor_quick_select_track():
            return
        self.editor_add_delta_range()

    def editor_quick_alternate_delta_range(self):
        """DEV stress edit used to force compressed-stream growth for v5.2.129 testing."""
        if not self.editor_quick_select_track():
            return
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None or binding is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor and select a track first.")
            return
        try:
            start = int(self.editor_range_start_var.get())
            end = int(self.editor_range_end_var.get())
            delta = abs(int(self.editor_delta_var.get().strip(), 0))
            lo, hi = min(start, end), max(start, end)
            if delta == 0:
                raise AnimCodecError("Delta must be nonzero for the oversize stress test.")
            changes = []
            for fi in range(lo, hi + 1):
                signed = -delta if ((fi - lo) & 1) == 0 else delta
                old, new = editor.set_value(
                    fi, binding.track_index,
                    int(editor.value(fi, binding.track_index)) + signed,
                    note="NAS GUI DEV OVERSIZE ALTERNATE +/- DELTA",
                )
                changes.append((fi, old, new))
            self._editor_refresh_value()
            self.codec_allow_resize_var.set(True)
            self.editor_status_var.set(
                f"OVERSIZE STRESS EDIT: frames {lo}-{hi}, track {binding.track_index}, alternating +/-{delta}. "
                "Experimental larger-ANIM rebuild enabled; now SAVE + BUILD."
            )
            self.log(
                f"NAS Motion Editor OVERSIZE STRESS frames={lo}-{hi} track={binding.track_index} delta=+/-{delta}"
            )
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))

    def _editor_selected_binding(self):
        component = self.editor_component_var.get().strip()
        return self._editor_component_to_binding.get(component)

    # v5.2.139 guided Motion Editor helpers ---------------------------------
    def editor_toggle_advanced(self):
        self.editor_advanced_visible = not bool(self.editor_advanced_visible)
        if self.editor_advanced_visible:
            self.editor_advanced_frame.grid()
            self.editor_advanced_toggle_btn.configure(text="▼ HIDE ADVANCED CONTROLS (OPTIONAL)")
        else:
            self.editor_advanced_frame.grid_remove()
            self.editor_advanced_toggle_btn.configure(text="▶ ADVANCED CONTROLS (OPTIONAL)")
        try:
            self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox("all"))
        except Exception:
            pass

    def _editor_update_range_summary(self):
        try:
            start = int(self.editor_range_start_var.get())
            end = int(self.editor_range_end_var.get())
            lo, hi = min(start, end), max(start, end)
            count = hi - lo + 1
            editor = self._anim_editor
            if editor is not None:
                last = max(0, editor.frame_count - 1)
                if lo < 0 or hi > last:
                    self.editor_range_summary_var.set(
                        f"Frame range {lo}-{hi} is outside this animation (valid 0-{last})."
                    )
                    return False
            self.editor_range_summary_var.set(f"Editing frames {lo}-{hi} ({count} frame{'s' if count != 1 else ''}).")
            return True
        except Exception:
            self.editor_range_summary_var.set("Enter valid whole-number Start and End frames.")
            return False

    def editor_guided_load_map(self):
        """Normal-user path: always rebuild editable JSON fresh from the selected ANIM."""
        raw = self.decoder_anim_var.get().strip().strip('"')
        if not raw or not Path(raw).is_file():
            messagebox.showwarning("ANIM Motion Editor", "STEP 1: Select a valid .anim or .wrap.anim file first.")
            return
        # Avoid silently reopening an edited JSON from an earlier attempt.
        self.codec_json_var.set("")
        self.codec_rebuilt_var.set("")
        self._anim_editor = None
        self.editor_review_var.set("No edits applied yet.")
        self.editor_load_map()
        if self._anim_editor is not None:
            self._editor_update_range_summary()
            self.editor_review_var.set(
                "Animation loaded fresh from the selected ANIM / WRAP.ANIM. Choose Motion / Bone / Axis, then choose a frame range."
            )

    def editor_guided_apply_range(self):
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None:
            messagebox.showwarning("ANIM Motion Editor", "STEP 2: Load / map the animation first.")
            return
        if binding is None:
            messagebox.showwarning("ANIM Motion Editor", "STEP 3: Choose a Motion Type, Bone / Element, and Axis / Component first.")
            return
        if not self._editor_update_range_summary():
            messagebox.showwarning("ANIM Motion Editor", "STEP 4: Enter a valid frame range first.")
            return
        try:
            start = int(self.editor_range_start_var.get())
            end = int(self.editor_range_end_var.get())
            delta = int(self.editor_delta_var.get().strip(), 0)
            if delta == 0:
                raise AnimCodecError("Change Amount cannot be 0. Use a positive or negative whole number.")
            changes = editor.add_delta(
                start,
                end,
                binding.track_index,
                delta,
                note="NAS GUI GUIDED APPLY RANGE",
            )
            lo, hi = min(start, end), max(start, end)
            bone = binding.bone_name or (
                f"bone_{binding.bone_index}" if binding.bone_index is not None else binding.element_label
            )
            self._editor_refresh_value()
            self.editor_review_var.set(
                f"PENDING EDIT — {binding.field_name} / {bone} / {binding.component_name} | "
                f"frames {lo}-{hi} | change {delta:+d} | {len(changes)} frames changed."
            )
            self.editor_status_var.set(
                f"STEP 5 PASS: applied {delta:+d} to {binding.field_name} / {bone} / {binding.component_name}, frames {lo}-{hi}."
            )
            self.log(
                f"NAS Guided Motion Edit frames={lo}-{hi} track={binding.track_index} "
                f"{binding.field_name}/{bone}/{binding.component_name} delta={delta:+d}"
            )
        except Exception as exc:
            messagebox.showerror("ANIM Motion Editor", str(exc))

    def _editor_verified_rebuilt_path(self) -> Path:
        raw = self.codec_rebuilt_var.get().strip().strip('"')
        if not raw or not Path(raw).is_file():
            raise AnimCodecError("STEP 6 must pass first. Build + Verify the edited animation before exporting.")
        rebuilt = Path(raw)
        source_raw = self.decoder_anim_var.get().strip().strip('"')
        if not source_raw or not Path(source_raw).is_file():
            raise AnimCodecError("The original Motion Editor ANIM / WRAP.ANIM source is no longer available.")
        source = Path(source_raw)
        source_header = inspect_anim_header(source)
        rebuilt_header = inspect_anim_header(rebuilt)
        if rebuilt_header.resource_hash != source_header.resource_hash:
            raise AnimCodecError(
                f"Edited ANIM resource hash changed unexpectedly: source=0x{source_header.resource_hash:08X} "
                f"rebuilt=0x{rebuilt_header.resource_hash:08X}."
            )
        if rebuilt_header.askl_hash != source_header.askl_hash:
            raise AnimCodecError(
                f"Edited ANIM ASKL hash changed unexpectedly: source=0x{source_header.askl_hash:08X} "
                f"rebuilt=0x{rebuilt_header.askl_hash:08X}."
            )
        return rebuilt

    def editor_export_classic_anim(self):
        """Save the verified Motion Editor result as a classic loose .anim."""
        try:
            rebuilt = self._editor_verified_rebuilt_path()
            source = Path(self.decoder_anim_var.get().strip().strip('"'))
            header = inspect_anim_header(rebuilt)
            if source.name.lower().endswith('.wrap.anim'):
                default_name = source.name[:-10] + '.anim'
            elif source.name.lower().endswith('.anim'):
                default_name = source.name
            else:
                default_name = f"0x{header.resource_hash:08X}.edited.anim"
            out = filedialog.asksaveasfilename(
                title="Save Motion Editor Classic .ANIM",
                initialfile=default_name,
                defaultextension=".anim",
                filetypes=[("SM3 Classic ANIM", "*.anim"), ("All files", "*.*")],
            )
            if not out:
                return
            dst = Path(out)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rebuilt, dst)
            verify = inspect_anim_header(dst)
            if verify.resource_hash != header.resource_hash or verify.askl_hash != header.askl_hash:
                raise AnimCodecError("Classic ANIM post-write identity verification failed.")
            self.editor_status_var.set(
                f"CLASSIC OUTPUT PASS: {dst.name} — 0x{verify.resource_hash:08X} / ASKL 0x{verify.askl_hash:08X}."
            )
            self.editor_review_var.set(
                f"CLASSIC .ANIM SAVED ✅ — {dst.name}. Motion edit and resource/skeleton identity verified."
            )
            self.log(f"Motion Editor CLASSIC .ANIM PASS: {dst}")
            messagebox.showinfo("Motion Editor Classic Output", f"Classic .ANIM saved successfully:\n\n{dst}")
        except Exception as exc:
            messagebox.showerror("Motion Editor Classic Output", str(exc))
            self.log(f"Motion Editor Classic output failed: {exc}")

    def _editor_find_wrap_shell(self, source: Path, resource_hash: int) -> Path:
        if source.name.lower().endswith('.wrap.anim'):
            return source

        roots = []
        extracted = self.extracted_character_folder_var.get().strip().strip('"')
        if extracted and Path(extracted).exists():
            roots.append(Path(extracted))
        # Search nearby old/raw and MOD LOADER READY sibling structures.
        roots.append(source.parent)
        roots.extend(list(source.parents)[:6])
        seen = set()
        for root in roots:
            key = str(root.resolve()) if root.exists() else str(root)
            if key in seen or not root.exists():
                continue
            seen.add(key)
            try:
                return find_matching_wrap_resource(root, resource_hash, 'anim')
            except Exception:
                pass

        chosen = filedialog.askopenfilename(
            title=f"Select original WRAP.ANIM shell for 0x{resource_hash:08X}",
            initialdir=str(source.parent),
            filetypes=[("SM3 NativeWRAP ANIM", "*.wrap.anim"), ("All files", "*.*")],
        )
        if not chosen:
            raise AnimCodecError(
                f"No matching original .wrap.anim shell was found for 0x{resource_hash:08X}. "
                "Run MOD LOADER READY or select the matching WRAP.ANIM manually."
            )
        return Path(chosen)

    def editor_export_wrap_anim(self):
        """Save the verified Motion Editor result inside the original NativeWRAP shell."""
        try:
            rebuilt = self._editor_verified_rebuilt_path()
            source = Path(self.decoder_anim_var.get().strip().strip('"'))
            header = inspect_anim_header(rebuilt)
            shell_path = self._editor_find_wrap_shell(source, header.resource_hash)
            shell = shell_path.read_bytes()
            info = inspect_wrap_bytes(shell)
            if info.component_count < 1:
                raise AnimCodecError("Selected WRAP.ANIM shell contains no ANIM component.")

            # ANIM-specific rebuild is required for arbitrary-size Motion Editor
            # output because payload growth shifts metadata-tail pointer fields.
            # It also works for same-size edits and verifies a byte-exact
            # WRAP -> canonical ANIM roundtrip before returning.
            wrapped, stats = rebuild_wrap_anim_from_shell(shell, rebuilt.read_bytes())
            inner_hash = read_wrap_anim_resource_hash(wrapped)
            if inner_hash != header.resource_hash:
                raise AnimCodecError(
                    f"WRAP.ANIM inner identity verification failed: inner=0x{inner_hash:08X} "
                    f"expected=0x{header.resource_hash:08X}."
                )
            final_info = inspect_wrap_bytes(wrapped)
            if final_info.archive_hash != info.archive_hash:
                raise AnimCodecError("WRAP.ANIM parent archive identity changed unexpectedly.")

            if shell_path.name.lower().endswith('.wrap.anim'):
                default_name = shell_path.name
            else:
                default_name = f"0x{header.resource_hash:08X}.edited.wrap.anim"
            out = filedialog.asksaveasfilename(
                title="Save Motion Editor WRAP.ANIM",
                initialfile=default_name,
                defaultextension=".wrap.anim",
                filetypes=[("SM3 NativeWRAP ANIM", "*.wrap.anim"), ("All files", "*.*")],
            )
            if not out:
                return
            dst = Path(out)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(wrapped)
            verify_bytes = dst.read_bytes()
            if read_wrap_anim_resource_hash(verify_bytes) != header.resource_hash:
                raise AnimCodecError("WRAP.ANIM post-write inner hash verification failed.")
            verify_info = inspect_wrap_bytes(verify_bytes)
            if verify_info.archive_hash != info.archive_hash:
                raise AnimCodecError("WRAP.ANIM post-write archive identity verification failed.")
            self.editor_status_var.set(
                f"WRAP OUTPUT PASS: {dst.name} — inner 0x{header.resource_hash:08X} / archive 0x{verify_info.archive_hash:08X}."
            )
            self.editor_review_var.set(
                f"WRAP.ANIM SAVED ✅ — {dst.name}. Motion edit, inner ANIM identity, and WRAP ownership verified."
            )
            self.log(
                f"Motion Editor WRAP.ANIM PASS: {dst}; internal={stats.get('internal_patches', 0)} "
                f"external={stats.get('external_patches', 0)} global={stats.get('global_patches', 0)}"
            )
            messagebox.showinfo("Motion Editor WRAP Output", f"NativeWRAP .ANIM saved successfully:\n\n{dst}")
        except Exception as exc:
            messagebox.showerror("Motion Editor WRAP Output", str(exc))
            self.log(f"Motion Editor WRAP output failed: {exc}")

    def editor_open_xesm3_output(self):
        raw = self.anim_mod_output_anim_var.get().strip().strip('"')
        if not raw or not Path(raw).is_file():
            messagebox.showwarning(
                "ANIM Motion Editor",
                "STEP 6 must pass first. Build + Verify the edited animation before creating the XESM3 mod.",
            )
            return
        try:
            self.workbook.select(self.anim_mod_output_page)
            self.anim_mod_status_var.set(f"Verified Motion Editor ANIM ready: {Path(raw).name}")
        except Exception as exc:
            messagebox.showerror("ANIM Motion Editor", str(exc))

    def editor_load_map(self):
        try:
            anim_path = Path(self.decoder_anim_var.get().strip().strip('"'))
            if not anim_path.is_file():
                raise AnimDecodeError("Select a valid extracted .anim or .wrap.anim file.")
            header = inspect_anim_header(anim_path)
            parent_apkf = find_parent_apkf_for_anim(anim_path)
            parent_data = parent_apkf.read_bytes() if parent_apkf is not None else None

            # v5.2.191 character-aware Motion Editor mapping.
            # Spider-Man, Black Suit and Peter share 0xCFB154CD. Other known
            # characters first use their real raw/WRAP ASKL from MOD LOADER
            # READY; Player Goblin also has a named built-in fallback.
            skeleton_raw = self.decoder_askl_var.get().strip().strip('"')
            skeleton_path = None
            source_kind = ""
            character_label = identify_character(anim_path, header.askl_hash)

            if skeleton_raw and Path(skeleton_raw).is_file():
                skeleton_path = validate_matching_sm3_skeleton_source_path(anim_path, Path(skeleton_raw))
                source_kind = classify_sm3_skeleton_source(anim_path, skeleton_path)
            else:
                # The shared Spider-Man family profile is authoritative and
                # does not need a serialized ASKL in CH_SPIDERMAN/BLACKSUIT/PETER.
                if int(header.askl_hash) != 0xCFB154CD:
                    found = self._auto_find_decoder_askl(quiet=True)
                    if found is not None and Path(found).is_file():
                        skeleton_path = validate_matching_sm3_skeleton_source_path(anim_path, Path(found))
                        source_kind = classify_sm3_skeleton_source(anim_path, skeleton_path)

                if skeleton_path is None:
                    if has_builtin_profile(header.askl_hash):
                        source_kind = f"BUILTIN_NAMED_PROFILE_{int(header.askl_hash):08X}"
                    else:
                        raise AnimDecodeError(
                            f"No matching skeleton was found automatically for {character_label} / "
                            f"0x{int(header.askl_hash):08X}. Use the OPTIONAL ASKL FALLBACK: pick an exact ASKL file or auto-find one in a folder. "
                            "MOD LOADER READY .wrap.askl files are supported directly."
                        )

            raw_json = self.codec_json_var.get().strip().strip('"')
            json_path = Path(raw_json) if raw_json else None
            if json_path is None or not json_path.exists():
                decoded = codec_decode_anim(read_anim_payload(anim_path))
                edited, _rebuilt, _reports = self._codec_output_dirs(anim_path)
                json_path = edited / f"{anim_path.name}.json"
                json_path.write_text(
                    json.dumps(codec_decoded_to_json_dict(decoded, str(anim_path)), indent=2) + "\n",
                    encoding="utf-8",
                )
                self.codec_json_var.set(str(json_path))

            obj = codec_load_json(json_path)
            decoder = None
            if source_kind.startswith("BUILTIN_NAMED_PROFILE_"):
                named_rows = build_named_track_map(read_anim_payload(anim_path))
                editor = AnimNamedProfileEditor(obj, header, named_rows)
                mode_name = f"{character_label} BUILT-IN NAMED PROFILE"
            elif source_kind in ("RAW_ASKL", "WRAP_ASKL"):
                decoder = SM3AnimPoseDecoder(read_anim_payload(anim_path), skeleton_path.read_bytes(), parent_data)
                editor = AnimScalarEditor(obj, decoder)
                mode_name = f"ASKL-AWARE / {source_kind}"
            else:
                # If only exact-hash outer T4 HSAM is available, retain the
                # proven RAW_TRACKS editing/build path. Parsed raw/WRAP ASKL
                # candidates above get full named field/bone mapping.
                editor = AnimRawTrackEditor(obj, header)
                mode_name = "SM3 T4 HSAM / RAW-TRACK FALLBACK"

            self._anim_editor = editor
            self._decoder_last_decoder = decoder
            self._editor_grouped = editor_grouped_bindings(editor.bindings)

            last_frame = max(0, editor.frame_count - 1)
            for spin in (
                self.editor_frame_spin, self.editor_range_start_spin, self.editor_range_end_spin,
                self.editor_quick_frame_spin, self.editor_quick_range_start_spin, self.editor_quick_range_end_spin,
            ):
                spin.configure(to=last_frame)
            self.editor_quick_track_spin.configure(to=max(0, editor.track_count - 1))
            if int(self.editor_frame_var.get()) > last_frame:
                self.editor_frame_var.set(last_frame)
            self.editor_range_start_var.set(0)
            self.editor_range_end_var.set(last_frame)

            # Capture a track queued by the Named Tracks page BEFORE the first
            # Advanced UI refresh (which otherwise selects the first component).
            try:
                requested_track = int(str(self.editor_quick_track_var.get()).strip(), 0)
            except Exception:
                requested_track = 0

            fields = list(self._editor_grouped.keys())
            self.editor_field_combo.configure(values=fields)
            if not fields:
                raise AnimCodecError("Motion editor produced no editable compressed tracks.")
            self.editor_field_var.set(fields[0])
            self._editor_populate_elements()
            # Preserve the queued track instead of resetting Quick Motion to 0.
            if requested_track < 0 or requested_track >= editor.track_count:
                requested_track = 0
            self.editor_quick_track_var.set(str(requested_track))
            self._editor_select_track_index(requested_track)

            named = sum(1 for b in editor.bindings if b.bone_index is not None)
            resolved = sum(1 for b in editor.bindings if b.bone_name)
            parent_note = parent_apkf.name if parent_apkf is not None else "not found"
            if decoder is not None:
                self.editor_status_var.set(
                    f"MAP PASS: {editor.frame_count} frames / {editor.track_count} tracks / {named} bone-mapped scalars."
                )
                detail = (
                    "ASKL-AWARE MOTION MAP PASS\n"
                    f"ANIM: {anim_path.name}\n"
                    f"Skeleton source: {skeleton_path.name}\n"
                    f"ASKL hash: 0x{decoder.anim.askl_hash:08X}\n"
                    f"ASKL input: {decoder.askl_input.container}"
                    + (f" component={decoder.askl_input.component_index}" if decoder.askl_input.component_index is not None else "")
                    + "\n"
                    f"Editable JSON: {json_path}\n"
                    f"Frames: {editor.frame_count}\n"
                    f"Compressed scalar tracks: {editor.track_count}\n"
                    f"Bone-mapped scalar tracks: {named}\n"
                    f"Resolved bone-name scalar tracks: {resolved}\n"
                    f"Parent APKF for names: {parent_note}\n\n"
                    "Editing rule: values are signed compressed integers. ASKL scale is shown for context. "
                    "FK_QUATERNION is normalized by the game after scaling.\n"
                    "Use SET for an exact raw value or ADD DELTA for a controlled visible change. SAVE JSON before leaving the editor."
                )
            elif source_kind.startswith("BUILTIN_NAMED_PROFILE_"):
                profile_name = profile_display_name(header.askl_hash)
                self.editor_status_var.set(
                    f"NAMED PROFILE MAP PASS: {character_label} — {editor.frame_count} frames / {editor.track_count} tracks / {resolved} named scalars."
                )
                detail = (
                    "BUILT-IN CHARACTER NAMED MOTION MAP PASS\n"
                    f"Character: {character_label}\n"
                    f"ANIM: {anim_path.name}\n"
                    f"Skeleton profile: {profile_name}\n"
                    f"ASKL hash: 0x{int(header.askl_hash):08X}\n"
                    "Serialized ASKL file: not required for this profile-backed fallback path\n"
                    f"Editable JSON: {json_path}\n"
                    f"Frames: {editor.frame_count}\n"
                    f"Compressed scalar tracks: {editor.track_count}\n"
                    f"Bone-mapped scalar tracks: {named}\n"
                    f"Resolved bone-name scalar tracks: {resolved}\n\n"
                    "Editing rule: values remain exact signed compressed integers. Per-element profile scales are shown for context. "
                    "Build verification still uses decode -> encode -> re-decode."
                )
            else:
                self.editor_status_var.set(
                    f"SOURCE PASS / RAW TRACK MODE: {editor.frame_count} frames / {editor.track_count} tracks."
                )
                detail = (
                    "SM3 SKELETON SOURCE DETECTION PASS\n"
                    f"ANIM: {anim_path.name}\n"
                    f"Required skeleton hash: 0x{header.askl_hash:08X}\n"
                    f"Detected SM3 source: {skeleton_path.name}\n"
                    "Source kind: exact-hash outer T4 HSAM\n"
                    f"Editable JSON: {json_path}\n"
                    f"Frames: {editor.frame_count}\n"
                    f"Compressed scalar tracks: {editor.track_count}\n\n"
                    "IMPORTANT: no parseable ASKL resource was selected/found for named mapping, so this exact-hash T4 HSAM is being used only as provenance. "
                    "The editor remains fully usable in RAW_TRACKS mode with the proven decode/edit/encode/re-decode verification path. "
                    "Named field/bone mapping activates automatically when a matching raw or WRAP ASKL is selected or found by folder scan."
                )
            self._set_editor_text(detail)
            skeleton_label = skeleton_path.name if skeleton_path is not None else f"built-in 0x{int(header.askl_hash):08X} profile"
            if source_kind.startswith("BUILTIN_NAMED_PROFILE_"):
                self.editor_skeleton_status_var.set(
                    f"Skeleton: {character_label} / 0x{int(header.askl_hash):08X} — built-in named profile ✅"
                )
            elif skeleton_path is not None:
                self.editor_skeleton_status_var.set(
                    f"Skeleton: {character_label} / {skeleton_path.name} — {source_kind} match verified ✅"
                )
            self._editor_update_range_summary()
            self.log(
                f"NAS Motion Editor {mode_name} PASS: {anim_path.name}; {editor.frame_count} frames, "
                f"{editor.track_count} editable scalar tracks; skeleton={skeleton_label}."
            )
        except Exception as exc:
            self._anim_editor = None
            self.editor_status_var.set("Motion editor map failed.")
            messagebox.showerror("NAS Motion Editor", str(exc))
            self.log(f"NAS Motion Editor map failed: {exc}")

    def _editor_populate_elements(self):
        field = self.editor_field_var.get().strip()
        groups = self._editor_grouped.get(field, {})
        labels = []
        label_to_key = {}
        for key, bindings in groups.items():
            if not bindings:
                continue
            label = bindings[0].element_label
            # Keep label unique even if a malformed skeleton repeats a name.
            unique = label
            if unique in label_to_key:
                unique = f"{label}  [{key}]"
            labels.append(unique)
            label_to_key[unique] = key
        self._editor_element_label_to_key = label_to_key
        self.editor_element_combo.configure(values=labels)
        if labels:
            self.editor_element_var.set(labels[0])
            self._editor_populate_components()
        else:
            self.editor_element_var.set("")
            self.editor_component_var.set("")
            self.editor_component_combo.configure(values=[])
            self._editor_component_to_binding = {}
            self._editor_refresh_value()

    def _editor_populate_components(self):
        field = self.editor_field_var.get().strip()
        label = self.editor_element_var.get().strip()
        key = self._editor_element_label_to_key.get(label)
        bindings = self._editor_grouped.get(field, {}).get(key, []) if key else []
        component_map = {b.component_name: b for b in bindings}
        self._editor_component_to_binding = component_map
        names = list(component_map.keys())
        self.editor_component_combo.configure(values=names)
        if names:
            self.editor_component_var.set(names[0])
        else:
            self.editor_component_var.set("")
        self._editor_refresh_value()

    def _editor_on_field_selected(self, _event=None):
        self._editor_populate_elements()

    def _editor_on_element_selected(self, _event=None):
        self._editor_populate_components()

    def _editor_refresh_value(self):
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None or binding is None:
            self.editor_track_var.set("-")
            self.editor_current_raw_var.set("-")
            self.editor_scale_var.set("-")
            self.editor_scaled_var.set("-")
            return
        try:
            frame = int(self.editor_frame_var.get())
            raw = editor.value(frame, binding.track_index)
            scaled = editor.approximate_scaled_value(frame, binding.track_index)
            self.editor_track_var.set(str(binding.track_index))
            self.editor_quick_track_var.set(str(binding.track_index))
            self.editor_current_raw_var.set(str(raw))
            self.editor_new_raw_var.set(str(raw))
            self.editor_scale_var.set("-" if binding.scale is None else f"{binding.scale:.9g}")
            self.editor_scaled_var.set("-" if scaled is None else f"{scaled:.9g}")
            bone = binding.bone_name or (f"bone_{binding.bone_index}" if binding.bone_index is not None else binding.element_label)
            self.editor_selection_summary_var.set(
                f"Selected: {binding.field_name} / {bone} / {binding.component_name}  •  Technical Track {binding.track_index}"
            )
            self.editor_status_var.set(
                f"Selection ready — {binding.field_name} / {bone} / {binding.component_name}. Now choose the frame range in Step 4."
            )
        except Exception as exc:
            self.editor_status_var.set(f"Value refresh failed: {exc}")

    def editor_set_current_frame(self):
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None or binding is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor and select a field/bone/component first.")
            return
        try:
            frame = int(self.editor_frame_var.get())
            new_value = int(self.editor_new_raw_var.get().strip(), 0)
            old, new = editor.set_value(frame, binding.track_index, new_value, note="NAS GUI SET THIS FRAME")
            self._editor_refresh_value()
            self.editor_status_var.set(
                f"EDITED frame {frame}, track {binding.track_index}: {old} -> {new}. Save JSON when ready."
            )
            self.log(f"NAS Motion Editor SET frame={frame} track={binding.track_index} {old}->{new}")
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))

    def editor_add_delta_current(self):
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None or binding is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor and select a field/bone/component first.")
            return
        try:
            frame = int(self.editor_frame_var.get())
            delta = int(self.editor_delta_var.get().strip(), 0)
            changes = editor.add_delta(frame, frame, binding.track_index, delta, note="NAS GUI ADD DELTA THIS FRAME")
            _fi, old, new = changes[0]
            self._editor_refresh_value()
            self.editor_status_var.set(
                f"EDITED frame {frame}, track {binding.track_index}: {old} -> {new} (delta {delta:+d})."
            )
            self.log(f"NAS Motion Editor DELTA frame={frame} track={binding.track_index} delta={delta:+d}")
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))

    def editor_add_delta_range(self):
        editor = self._anim_editor
        binding = self._editor_selected_binding()
        if editor is None or binding is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor and select a field/bone/component first.")
            return
        try:
            start = int(self.editor_range_start_var.get())
            end = int(self.editor_range_end_var.get())
            delta = int(self.editor_delta_var.get().strip(), 0)
            changes = editor.add_delta(start, end, binding.track_index, delta, note="NAS GUI ADD DELTA TO RANGE")
            lo = min(start, end)
            hi = max(start, end)
            self._editor_refresh_value()
            self.editor_status_var.set(
                f"EDITED frames {lo}-{hi}, track {binding.track_index}: delta {delta:+d} across {len(changes)} frames."
            )
            self.log(
                f"NAS Motion Editor RANGE DELTA frames={lo}-{hi} track={binding.track_index} delta={delta:+d}"
            )
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))

    def editor_save_json(self):
        editor = self._anim_editor
        if editor is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor first.")
            return False
        raw = self.codec_json_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("NAS Motion Editor", "No editable JSON path is selected.")
            return False
        try:
            path = Path(raw)
            editor.save(path)
            self.editor_status_var.set(f"SAVED: {path.name}")
            self.log(f"NAS Motion Editor saved editable JSON: {path.name}")
            return True
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))
            return False

    def editor_build_anim(self):
        if self._anim_editor is None:
            messagebox.showwarning("NAS Motion Editor", "Load/map the editor first.")
            return
        try:
            if not self.editor_save_json():
                return
            if not self.codec_build_edited_anim(
                motion_editor_auto_grow=bool(self.editor_auto_grow_var.get())
            ):
                self.editor_status_var.set("BUILD FAILED — see NAS Codec status/log.")
                return
            if self.codec_rebuilt_var.get().strip():
                rebuilt_path = Path(self.codec_rebuilt_var.get().strip().strip('"'))
                self.editor_status_var.set(
                    f"BUILD PASS: {rebuilt_path.name} — verified by NAS re-decode. Ready for Classic, WRAP, or XESM3 output."
                )
                if rebuilt_path.is_file():
                    self.anim_mod_output_anim_var.set(str(rebuilt_path))
                    self.anim_mod_status_var.set(
                        f"Motion Editor BUILD PASS ready for output: {rebuilt_path.name}"
                    )
                    self.editor_review_var.set(
                        f"BUILD + VERIFY PASS ✅ — {rebuilt_path.name} is ready for Step 7 Classic / WRAP / XESM3 output."
                    )
        except Exception as exc:
            messagebox.showerror("NAS Motion Editor", str(exc))

    # ------------------------------------------------------------------
    # TEMP v5.2.119 — NAS offline ANIM Decoder / all-frame named-bone timeline
    # ------------------------------------------------------------------

    def _set_decoder_anim_path(self, path: Path, try_askl: bool = True):
        path = Path(path)
        self.decoder_anim_var.set(str(path))
        try:
            header = inspect_anim_header(path)
            max_frame = max(0, int(header.sample_count) - 1)
            try:
                self.decoder_frame_spin.configure(to=max_frame)
            except Exception:
                pass
            if int(self.decoder_frame_var.get()) > max_frame:
                self.decoder_frame_var.set(max_frame)
            # Never silently carry a skeleton from the previous ANIM. v5.2.128
            # makes the second step explicit: select a file OR select a folder to scan.
            current = self.decoder_askl_var.get().strip().strip('"')
            if current:
                try:
                    validate_matching_sm3_skeleton_source_path(path, Path(current))
                except Exception:
                    self.decoder_askl_var.set("")
            self.decoder_status_var.set(
                f"ANIM 0x{header.resource_hash:08X} loaded from {'WRAP.ANIM' if path.name.lower().endswith('.wrap.anim') else 'ANIM'} — {header.sample_count} samples, expects skeleton 0x{header.askl_hash:08X}. Use the optional ASKL fallback: pick an exact ASKL / WRAP.ASKL or auto-find one in a folder."
            )
            character_label = identify_character(path, header.askl_hash)
            if int(header.askl_hash) == 0xCFB154CD:
                self.editor_skeleton_status_var.set(
                    f"Animation: 0x{header.resource_hash:08X} • {header.sample_count} frames • {character_label} shared 0xCFB154CD profile detected automatically ✅"
                )
            elif has_builtin_profile(header.askl_hash):
                self.editor_skeleton_status_var.set(
                    f"Animation: 0x{header.resource_hash:08X} • {header.sample_count} frames • {character_label} 0x{header.askl_hash:08X}. WRAP.ASKL auto-map preferred; built-in named fallback available ✅"
                )
            else:
                self.editor_skeleton_status_var.set(
                    f"Animation: 0x{header.resource_hash:08X} • {header.sample_count} frames • needs matching skeleton 0x{header.askl_hash:08X}. Use Step 2 ASKL buttons."
                )
            if try_askl:
                self._auto_find_decoder_askl(quiet=True)
        except Exception as exc:
            self.decoder_status_var.set(f"ANIM selected; header parse failed: {exc}")

    def browse_decoder_anim(self):
        path = filedialog.askopenfilename(
            title="Select extracted SM3 ANIM / WRAP.ANIM",
            filetypes=[("SM3 ANIM / WRAP.ANIM", "*.anim *.wrap.anim"), ("All files", "*.*")],
        )
        if path:
            self._set_decoder_anim_path(Path(path), try_askl=False)

    def browse_decoder_askl(self):
        path = filedialog.askopenfilename(
            title="Select matching ASKL / skeleton source",
            filetypes=[("ASKL / WRAP.ASKL / Skeleton", "*.askl *.wrap.askl *.hsam"), ("ASKL / WRAP.ASKL", "*.askl *.wrap.askl"), ("Outer T4 HSAM", "*.hsam"), ("All files", "*.*")],
        )
        if path:
            try:
                raw_anim = self.decoder_anim_var.get().strip().strip('"')
                if not raw_anim:
                    raise AnimDecodeError("Select the ANIM first so NAS can verify the referenced skeleton hash.")
                checked = validate_matching_sm3_skeleton_source_path(Path(raw_anim), Path(path))
                kind = classify_sm3_skeleton_source(Path(raw_anim), checked)
                self.decoder_askl_var.set(str(checked))
                if kind == "RAW_ASKL":
                    label = "RAW ASKL"
                elif kind == "WRAP_ASKL":
                    label = "WRAP ASKL"
                else:
                    label = "T4 HSAM / RAW_TRACK fallback"
                self.decoder_status_var.set(f"MATCH PASS — {label}: {checked.name}")
            except Exception as exc:
                self.decoder_askl_var.set("")
                messagebox.showerror("ANIM Decoder", str(exc))

    def select_decoder_askl_folder(self):
        raw_anim = self.decoder_anim_var.get().strip().strip('"')
        if not raw_anim or not Path(raw_anim).is_file():
            messagebox.showwarning("ANIM Decoder", "Select the ANIM first, then choose the folder containing ASKL files.")
            return
        anim_path = Path(raw_anim)
        initial = anim_path.parent if anim_path.parent.is_dir() else None
        folder = filedialog.askdirectory(
            title="Select folder to scan for matching ASKL / skeleton",
            initialdir=str(initial) if initial else None,
        )
        if not folder:
            return
        self.decoder_status_var.set(f"Scanning {Path(folder).name} for matching skeleton...")
        try:
            found = find_matching_skeleton_source(anim_path, Path(folder))
            if found is None:
                header = inspect_anim_header(anim_path)
                raise AnimDecodeError(
                    f"No parseable skeleton matching 0x{header.askl_hash:08X} was found under:\n{folder}\n\n"
                    "NAS scanned raw ASKL, WRAP ASKL, and exact-hash T4 HSAM candidates."
                )
            kind = classify_sm3_skeleton_source(anim_path, found)
            self.decoder_askl_var.set(str(found))
            label = {"RAW_ASKL": "RAW ASKL", "WRAP_ASKL": "WRAP ASKL", "SM3_T4_HSAM": "T4 HSAM / RAW_TRACK fallback"}.get(kind, kind)
            self.decoder_status_var.set(f"FOLDER SCAN MATCH PASS — {label}: {found.name}")
            self.log(f"NAS skeleton folder scan PASS: {anim_path.name} -> {found.name} ({kind}) from {folder}")
        except Exception as exc:
            self.decoder_askl_var.set("")
            messagebox.showerror("ANIM Decoder", str(exc))
            self.log(f"NAS skeleton folder scan failed: {exc}")

    def use_source_out_for_decoder(self):
        path = self._source_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("ANIM Decoder", "Select a valid Source OUT animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.decoder_text.master.master)

    def use_replacement_in_for_decoder(self):
        path = self._target_path()
        if not path.exists() or not path.is_file():
            messagebox.showwarning("ANIM Decoder", "Select a valid Replacement IN animation first.")
            return
        self._set_decoder_anim_path(path, try_askl=False)
        self.workbook.select(self.decoder_text.master.master)

    def _auto_find_decoder_askl(self, quiet: bool = False) -> Path | None:
        raw_anim = self.decoder_anim_var.get().strip().strip('"')
        if not raw_anim:
            if not quiet:
                messagebox.showwarning("ANIM Decoder", "Select an ANIM first.")
            return None
        anim_path = Path(raw_anim)
        raw_root = self.extracted_character_folder_var.get().strip().strip('"')
        search_roots: list[Path] = []

        # v5.2.190: MOD LOADER READY / WRAP_EXTRACTS is now a first-class
        # Motion Editor source.  Search the owning O#### archive first so an
        # ANIM folder can resolve its sibling ASKL folder automatically, then
        # widen to WRAP_EXTRACTS if needed.
        wrap_owner = None
        wrap_root = None
        for parent in [anim_path.parent, *anim_path.parents]:
            if re.match(r"^O\d+\.0x[0-9A-Fa-f]{8}\.T[0-9A-Fa-f]+\.apkf$", parent.name, flags=re.IGNORECASE):
                wrap_owner = parent
            if parent.name.upper() == "WRAP_EXTRACTS":
                wrap_root = parent
                break
        if wrap_owner is not None and wrap_owner.is_dir():
            search_roots.append(wrap_owner)
        if wrap_root is not None and wrap_root.is_dir() and wrap_root not in search_roots:
            search_roots.append(wrap_root)

        # Legacy convenience auto-find retained for internal calls. v5.2.128
        # validates candidates by parsed contents instead of WOS/SM3 path names.
        pack_root = None
        for parent in [anim_path.parent, *anim_path.parents]:
            if parent.name.upper() == "02_APKF_EXTRACTED_REAL_EXT":
                pack_root = parent.parent
                break
            if (parent / "02_APKF_EXTRACTED_REAL_EXT").is_dir():
                pack_root = parent
                break
        if pack_root is not None:
            search_roots.append(pack_root)

            # Cross-pack references are possible. If the pack lives under an
            # explicitly named collection folder, it may be searched too.
            for ancestor in pack_root.parents:
                if ancestor.name.lower() == "sm3":
                    if ancestor not in search_roots:
                        search_roots.append(ancestor)
                    break

        # Allow the user's explicit extraction folder as a second search root.
        # Matching is based on parsed skeleton hash/layout, not provenance words.
        if raw_root:
            p = Path(raw_root)
            if p.exists() and p.is_dir() and p not in search_roots:
                search_roots.append(p)

        if not search_roots and anim_path.parent.is_dir():
            search_roots.append(anim_path.parent)
        last_error = None
        for root in search_roots:
            try:
                found = find_matching_skeleton_source(anim_path, root)
                if found:
                    self.decoder_askl_var.set(str(found))
                    header = inspect_anim_header(anim_path)
                    kind = classify_sm3_skeleton_source(anim_path, found)
                    if kind in ("RAW_ASKL", "WRAP_ASKL"):
                        self.decoder_status_var.set(
                            f"Matched {kind} 0x{header.askl_hash:08X}: {found.name}"
                        )
                    else:
                        self.decoder_status_var.set(
                            f"Matched T4 HSAM skeleton source 0x{header.askl_hash:08X}: {found.name} — raw-track editor fallback active."
                        )
                    return found
            except Exception as exc:
                last_error = exc
        try:
            header = inspect_anim_header(anim_path)
            message = f"No SM3 skeleton source for 0x{header.askl_hash:08X} was found. NAS checked exact raw ASKL first, then exact-hash outer T4 HSAM. raw ASKL, WRAP ASKL, and exact-hash T4 HSAM are content-checked."
        except Exception:
            message = "No matching ASKL was found."
        if last_error:
            message += f" Last scan error: {last_error}"
        self.decoder_status_var.set(message)
        if not quiet:
            messagebox.showwarning("ANIM Decoder", message)
        return None

    def auto_find_decoder_askl(self):
        self._auto_find_decoder_askl(quiet=False)

    def decode_anim_frame(self):
        try:
            anim_path = Path(self.decoder_anim_var.get().strip().strip('"'))
            askl_path = Path(self.decoder_askl_var.get().strip().strip('"'))
            if not anim_path.exists() or not anim_path.is_file():
                raise AnimDecodeError("Select a valid extracted .anim or .wrap.anim file.")
            if not askl_path.exists() or not askl_path.is_file():
                raise AnimDecodeError("After selecting ANIM, use the optional ASKL fallback: pick the exact file or auto-find it in a folder.")
            parent_apkf = find_parent_apkf_for_anim(anim_path)
            parent_data = parent_apkf.read_bytes() if parent_apkf is not None else None
            if classify_sm3_skeleton_source(anim_path, askl_path) not in ("RAW_ASKL", "WRAP_ASKL"):
                raise AnimDecodeError(
                    "The named-bone ANIM Decoder needs a parseable ASKL resource (raw or WRAP). "
                    "The selected source is only a T4 HSAM, so use ANIM Motion Editor RAW_TRACKS mode or select/scan a folder containing the matching ASKL."
                )
            askl_path = validate_matching_sm3_askl_path(anim_path, askl_path)
            decoder = SM3AnimPoseDecoder(read_anim_payload(anim_path), askl_path.read_bytes(), parent_data)
            frame = int(self.decoder_frame_var.get())
            result = decoder.decode_frame(frame)
            summary = format_anim_decode_summary(decoder, result)
            self._decoder_last_decoder = decoder
            self._decoder_last_result = result
            self.decoder_text.configure(state="normal")
            self.decoder_text.delete("1.0", "end")
            self.decoder_text.insert("1.0", summary)
            self.decoder_text.configure(state="disabled")
            if result.golden_checks:
                verdict = "GOLDEN FRAME 28 PASS" if result.golden_checks.get("pass") else "GOLDEN FRAME 28 FAIL"
                self.decoder_status_var.set(
                    f"Decoded frame {frame}: {result.consumed_scalar_count} scalars — {verdict}."
                )
            else:
                self.decoder_status_var.set(
                    f"Decoded frame {frame}: {result.consumed_scalar_count}/{result.compressed_track_count} scalars, cursor local 0x{result.cursor_byte_offset:X} bit {result.cursor_bit_offset}."
                )
            parent_note = f" parent={parent_apkf.name}" if parent_apkf is not None else " parent APKF=not found"
            self.log(
                f"ANIM Decoder: {anim_path.name} frame {frame} decoded with {result.consumed_scalar_count} compressed scalars;{parent_note}."
            )
        except Exception as exc:
            self.decoder_status_var.set("Decode failed.")
            messagebox.showerror("SM3 ANIM Decoder", str(exc))
            self.log(f"ANIM Decoder failed: {exc}")

    def _resolve_decoder_paths(self):
        anim_path = Path(self.decoder_anim_var.get().strip().strip('"'))
        askl_path = Path(self.decoder_askl_var.get().strip().strip('"'))
        if not anim_path.exists() or not anim_path.is_file():
            raise AnimDecodeError("Select a valid extracted .anim or .wrap.anim file.")
        if not askl_path.exists() or not askl_path.is_file():
            raise AnimDecodeError("After selecting ANIM, use the optional ASKL fallback: pick the exact file or auto-find it in a folder.")
        parent_apkf = find_parent_apkf_for_anim(anim_path)
        return anim_path, askl_path, parent_apkf

    def decode_anim_all_frames(self):
        if self._decoder_all_frames_busy:
            messagebox.showinfo("SM3 ANIM Decoder", "All-frame decode is already running.")
            return
        try:
            anim_path, askl_path, parent_apkf = self._resolve_decoder_paths()
        except Exception as exc:
            messagebox.showerror("SM3 ANIM Decoder", str(exc))
            return

        self._decoder_all_frames_busy = True
        self.decoder_status_var.set(f"Decoding all frames from {anim_path.name}...")
        self.log(f"ANIM Decoder: starting all-frame decode for {anim_path.name}.")

        while True:
            try:
                self._decoder_worker_queue.get_nowait()
            except queue.Empty:
                break

        def worker():
            try:
                parent_data = parent_apkf.read_bytes() if parent_apkf is not None else None
                if classify_sm3_skeleton_source(anim_path, askl_path) not in ("RAW_ASKL", "WRAP_ASKL"):
                    raise AnimDecodeError(
                        "DECODE ALL FRAMES named-bone mode needs a parseable raw/WRAP ASKL. "
                        "The selected T4 HSAM is only the RAW_TRACKS fallback; select an ASKL file or scan a folder for one."
                    )
                askl_path = validate_matching_sm3_askl_path(anim_path, askl_path)
                decoder = SM3AnimPoseDecoder(read_anim_payload(anim_path), askl_path.read_bytes(), parent_data)
                animation = decoder.decode_all_frames()
                summary = format_anim_timeline_summary(decoder, animation)
                self._decoder_worker_queue.put((
                    "ok", decoder, animation, summary, anim_path, parent_apkf
                ))
            except Exception as exc:
                self._decoder_worker_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, self._poll_decode_anim_all_frames)

    def _poll_decode_anim_all_frames(self):
        try:
            item = self._decoder_worker_queue.get_nowait()
        except queue.Empty:
            if self._decoder_all_frames_busy:
                self.after(50, self._poll_decode_anim_all_frames)
            return
        if not item:
            return
        if item[0] == "ok":
            _, decoder, animation, summary, anim_path, parent_apkf = item
            self._finish_decode_anim_all_frames(decoder, animation, summary, anim_path, parent_apkf)
        else:
            self._fail_decode_anim_all_frames(item[1])

    def _finish_decode_anim_all_frames(self, decoder, animation, summary, anim_path, parent_apkf):
        self._decoder_all_frames_busy = False
        self._decoder_last_decoder = decoder
        self._decoder_last_animation = animation
        self._decoder_last_anim_path = Path(anim_path)
        self.decoder_text.configure(state="normal")
        self.decoder_text.delete("1.0", "end")
        self.decoder_text.insert("1.0", summary)
        self.decoder_text.configure(state="disabled")
        self.decoder_status_var.set(
            f"Decoded all {animation.sample_count} frames -> {len(animation.bone_rows)} named-bone timeline rows."
        )
        parent_note = f" parent={parent_apkf.name}" if parent_apkf is not None else " parent APKF=not found"
        self.log(
            f"ANIM Decoder: {anim_path.name} all {animation.sample_count} frames decoded; "
            f"{len(animation.bone_rows)} bone rows;{parent_note}."
        )

    def _fail_decode_anim_all_frames(self, exc):
        self._decoder_all_frames_busy = False
        self.decoder_status_var.set("All-frame decode failed.")
        messagebox.showerror("SM3 ANIM Decoder", str(exc))
        self.log(f"ANIM Decoder all-frame decode failed: {exc}")

    def export_decoder_blender_json(self):
        result = self._decoder_last_animation
        if result is None:
            messagebox.showwarning("SM3 ANIM Decoder", "Run DECODE ALL FRAMES first.")
            return
        stem = "SM3_ANIMATION"
        if self._decoder_last_anim_path is not None:
            stem = self._decoder_last_anim_path.stem
        path = filedialog.asksaveasfilename(
            title="Export Blender Bridge animation JSON (SM3 local space)",
            defaultextension=".json",
            initialfile=f"{stem}.blender_anim.json",
            filetypes=[("Blender Bridge JSON", "*.json"), ("JSON", "*.json")],
        )
        if path:
            export_anim_blender_json(result, path)
            flips = sum(1 for row in result.bone_rows if row.blender_quaternion_flipped)
            transitions = sum(
                1 for row in result.bone_rows
                if row.blender_quaternion_raw_dot_previous is not None
                and row.blender_quaternion_raw_dot_previous < 0.0
            )
            self.decoder_status_var.set(
                f"Saved {Path(path).name} — {transitions} raw hemisphere transitions, {flips} sign-adjusted keys."
            )
            self.log(
                f"ANIM Decoder: exported Blender Bridge JSON {Path(path).name}; "
                f"SM3-local coordinates; {transitions} raw transitions, {flips} sign-adjusted keys."
            )

    def export_decoder_animation_json(self):
        result = self._decoder_last_animation
        if result is None:
            messagebox.showwarning("SM3 ANIM Decoder", "Run DECODE ALL FRAMES first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export full named-bone animation JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if path:
            export_anim_timeline_json(result, path)
            self.decoder_status_var.set(f"Saved {Path(path).name}")

    def export_decoder_animation_csv(self):
        result = self._decoder_last_animation
        if result is None:
            messagebox.showwarning("SM3 ANIM Decoder", "Run DECODE ALL FRAMES first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export full named-bone animation CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if path:
            export_anim_timeline_csv(result, path)
            self.decoder_status_var.set(f"Saved {Path(path).name}")

    def export_decoder_json(self):
        result = self._decoder_last_result
        if result is None:
            messagebox.showwarning("SM3 ANIM Decoder", "Decode a frame first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export decoded frame JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if path:
            export_anim_decode_json(result, path)
            self.decoder_status_var.set(f"Saved {Path(path).name}")

    def export_decoder_csv(self):
        result = self._decoder_last_result
        if result is None:
            messagebox.showwarning("SM3 ANIM Decoder", "Decode a frame first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export decoded frame CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if path:
            export_anim_decode_csv(result, path)
            self.decoder_status_var.set(f"Saved {Path(path).name}")

    def clear_decoder_output(self):
        self._decoder_last_decoder = None
        self._decoder_last_result = None
        self._decoder_last_animation = None
        self._decoder_last_anim_path = None
        self.decoder_text.configure(state="normal")
        self.decoder_text.delete("1.0", "end")
        self.decoder_text.configure(state="disabled")
        self.decoder_status_var.set("Decoder output cleared.")

    def preview_csv(self, path: Path):
        self._csv_rows_preview = []
        self.csv_tree.delete(*self.csv_tree.get_children())
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._csv_rows_preview.append(row)
            destination_keys = ("destination", "destination_anim", "source_out", "source", "out", "dest", "target", "target_anim")
            replacement_keys = ("replacement", "replacement_anim", "replacement_in", "in", "repl", "new_anim", "source_in")
            for idx, row in enumerate(self._csv_rows_preview[:50], start=1):
                def first(keys):
                    for key in keys:
                        val = row.get(key)
                        if val:
                            return val
                    return ""
                enabled = row.get("enabled", "1")
                mode = row.get("mode", "slot_preserve") or "slot_preserve"
                self.csv_tree.insert(
                    "",
                    "end",
                    values=(enabled, first(destination_keys), first(replacement_keys), mode, row.get("note", "")),
                )
            self.log(f"Imported CSV preview: {path.name} ({len(self._csv_rows_preview)} rows).")
        except Exception as exc:
            messagebox.showerror("CSV import failed", str(exc))
            self.log(f"CSV import failed: {exc}")

    def sm3_character_csv_auto_test_threaded(self):
        threading.Thread(target=self.sm3_character_csv_auto_test, daemon=True).start()

    def sm3_character_csv_auto_test(self):
        try:
            original_pack = self._character_pack_path()
            extracted_folder = self._extracted_character_folder()
            csv_path = self._character_test_csv_path()
            out = self._out_dir()
            if original_pack is None:
                return
            if out is None:
                return
            if not original_pack.exists():
                messagebox.showwarning("Missing original pack", "Select the clean original character PCPACK first.")
                return
            if not extracted_folder.exists():
                messagebox.showwarning("Missing extracted folder", "Select the extracted character pack folder first.")
                return
            if not csv_path.exists():
                messagebox.showwarning("Missing CSV", "Import/select a SM3 character animation CSV first.")
                return
            msg = (
                "This will create one visible patched PCPACK per enabled CSV row.\n\n"
                "Safe slot-preserve only: replacement must fit the selected destination slot.\n\n"
                "Bigger replacements are blocked. Boot-test one output pack at a time. Continue?"
            )
            if not messagebox.askyesno("Patch game packs from CSV", msg):
                return
            self.log("Patching game packs from imported CSV...")
            result = character_anim_csv_auto_test_patch(
                original_pack=original_pack,
                extracted_folder=extracted_folder,
                csv_path=csv_path,
                output_root=out,
                max_rows=None,
                allow_experimental_size_change=False,
            )
            self.log("NAS CSV patch run complete.")
            self.log(f"Patched packs: {result.get('patched_count')}  Blocked: {result.get('blocked_count')}  Errors: {result.get('error_count')}")
            out_hint = result.get('output_root') or result.get('output_folder') or ''
            if out_hint:
                self.log(f"Output folder: {Path(str(out_hint)).name}")
            try:
                open_path(Path(result.get("output_root", "")))
            except Exception:
                pass
        except Exception as exc:
            messagebox.showerror("8) NAS CSV patch failed", str(exc))
            self.log(f"8) NAS CSV patch failed: {exc}")

    def _character_pack_path(self) -> Path | None:
        path = Path(self.character_pack_var.get().strip().strip('"'))
        if path.exists() and path.is_file() and looks_like_wrong_game_or_unsupported_sm3_path(path):
            self.log(wrong_game_detail(path))
            messagebox.showerror("SM3 pack route not recognized", WRONG_GAME_GUARD_MESSAGE)
            return None
        return path

    def _extracted_character_folder(self) -> Path:
        return Path(self.extracted_character_folder_var.get().strip().strip('"'))

    def _character_test_csv_path(self) -> Path:
        return Path(self.character_test_csv_var.get().strip().strip('"'))

    def _source_path(self) -> Path:
        return Path(self.source_file_var.get().strip().strip('"'))

    def _target_path(self) -> Path:
        return Path(self.target_file_var.get().strip().strip('"'))

    def _out_dir(self) -> Path | None:
        raw = self.out_dir_var.get().strip().strip('"')
        if not raw:
            messagebox.showwarning("Missing output folder", "Choose an output folder first.")
            return None
        return Path(raw)

    def open_output(self):
        out = self._out_dir()
        if out and out.exists():
            open_path(out)
        else:
            messagebox.showinfo("No output", "Choose or create an output folder first.")

    def _release_log_line(self, text: str) -> str:
        line = str(text)
        # Keep release logs useful but not scary: no giant JSON dumps or Python tracebacks in the visible tab.
        if line.strip().startswith("{") or line.strip().startswith("["):
            return "Detailed report was written to the output folder."
        if "Traceback (most recent call last)" in line:
            return "An internal error occurred. Check the output folder and try again."
        return line

    def log(self, text: str):
        self.log_text.insert("end", self._release_log_line(text) + "\n")
        self.log_text.see("end")
        self.status_var.set(str(text))
        try:
            if self.app_state:
                self.app_state.set_status(str(text))
        except Exception:
            pass
        self.update_idletasks()

    def clear_log(self):
        self.log_text.delete("1.0", "end")
        self.status_var.set("Log cleared.")

    # v5.2.130 ONE-CLICK ANIM MOD OUTPUT
    def _build_anim_mod_output_page(self):
        """Add a no-guessing XESM3 ANIM mod output page without altering NAS editor state."""
        if not hasattr(self, "workbook"):
            return
        page = ttk.Frame(self.workbook, style="Body.TFrame", padding=10)
        page.columnconfigure(1, weight=1)
        page.columnconfigure(4, weight=1)
        page.rowconfigure(8, weight=1)
        self.workbook.insert(self.workbook.index(self.motion_editor_page) + 1, page, text="XESM3 Mod Output")
        self.anim_mod_output_page = page

        ttk.Label(page, text="ONE-CLICK XESM3 ANIM MOD OUTPUT", style="SectionTitle.TLabel").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 4))
        ttk.Label(
            page,
            text="Use this page for rebuilt ANIMs that KEEP their original resource identity, such as Motion Editor output. For target <- donor animation replacement, use the new Animation Swapper tab; it handles the target identity and donor motion automatically.",
            style="Muted.TLabel", wraplength=1120,
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(0, 10))

        ttk.Label(page, text="1) Rebuilt ANIM / WRAP.ANIM", style="CardLabel.TLabel").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(page, textvariable=self.anim_mod_output_anim_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Button(page, text="Browse ANIM", command=self.browse_anim_mod_output_anim).grid(row=2, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(page, text="Use Rebuilt / Replacement IN", command=self.use_replacement_in_for_mod_output).grid(row=2, column=5, sticky="ew", padx=4, pady=4)

        ttk.Label(page, text="2) MOD LOADER READY / extracted pack folder", style="CardLabel.TLabel").grid(row=3, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(page, textvariable=self.extracted_character_folder_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=4, pady=4)
        ttk.Button(page, text="Browse Owner Folder", command=self.browse_extracted_character_folder).grid(row=3, column=4, columnspan=2, sticky="ew", padx=4, pady=4)

        ttk.Label(page, text="3) Mod name", style="CardLabel.TLabel").grid(row=4, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(page, textvariable=self.anim_mod_name_var).grid(row=4, column=1, columnspan=2, sticky="ew", padx=4, pady=4)
        ttk.Label(page, text="Output folder", style="CardLabel.TLabel").grid(row=4, column=3, sticky="e", padx=4, pady=4)
        ttk.Entry(page, textvariable=self.out_dir_var).grid(row=4, column=4, sticky="ew", padx=4, pady=4)
        ttk.Button(page, text="Browse Output", command=self.browse_out_dir).grid(row=4, column=5, sticky="ew", padx=4, pady=4)

        ttk.Button(
            page, text="4A) BUILD ONE-CLICK .ANIM MOD", command=self.build_one_click_anim_mod,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4, pady=(10, 4))
        ttk.Button(
            page, text="4B) BUILD ONE-CLICK WRAP.ANIM MOD", command=self.build_one_click_wrap_anim_mod,
            style="Accent.TButton",
        ).grid(row=5, column=2, columnspan=3, sticky="ew", padx=4, pady=(10, 4))
        ttk.Button(page, text="Open Output", command=self.open_anim_mod_output).grid(row=5, column=5, sticky="ew", padx=4, pady=(10, 4))

        ttk.Label(page, textvariable=self.anim_mod_status_var, style="Muted.TLabel", wraplength=1120).grid(row=6, column=0, columnspan=6, sticky="w", padx=4, pady=(4, 8))
        ttk.Label(
            page,
            text="Example resolved route: <Mod Name>/CH_SPIDERMAN/_O0069.0xCFB154CD.T36.apkf/0x295C54BA.sm3jmpsprint.anim",
            style="Muted.TLabel", wraplength=1120,
        ).grid(row=7, column=0, columnspan=6, sticky="w", padx=4, pady=(0, 6))
        self.anim_mod_report = tk.Text(page, height=12, wrap="word", bg=COLORS["panel"], fg=COLORS.get("fg", "#F2F2F2"), insertbackground=COLORS.get("fg", "#F2F2F2"), relief="flat", bd=0)
        self.anim_mod_report.grid(row=8, column=0, columnspan=6, sticky="nsew", padx=4, pady=4)

    def prepare_xesm3_mod_from_replacement(self):
        """Send the current Replacement IN/rebuilt ANIM to the release XESM3 output page."""
        path = Path(self.target_file_var.get().strip().strip('"'))
        if not path.is_file():
            messagebox.showwarning("XESM3 Mod Output", "Select a valid Replacement IN / rebuilt ANIM first.")
            return
        self.anim_mod_output_anim_var.set(str(path))
        self.anim_mod_status_var.set(f"Using Replacement IN / rebuilt ANIM: {path.name}")
        try:
            self.workbook.select(self.anim_mod_output_page)
        except Exception:
            pass

    def browse_anim_mod_output_anim(self):
        path = filedialog.askopenfilename(title="Select rebuilt ANIM / WRAP.ANIM", filetypes=[("SM3 ANIM / WRAP.ANIM", "*.anim"), ("All files", "*.*")])
        if path:
            self.anim_mod_output_anim_var.set(path)
            try:
                p = Path(path)
                if p.name.lower().endswith('.wrap.anim'):
                    m = re.search(r'0x([0-9A-Fa-f]{8})', p.name)
                    h = int(m.group(1), 16) if m else 0
                    self.anim_mod_status_var.set(f"WRAP.ANIM 0x{h:08X} selected — {p.stat().st_size} bytes. Use the WRAP button.")
                else:
                    h, _v, a = inspect_mod_output_anim_identity(p)
                    self.anim_mod_status_var.set(f"ANIM 0x{h:08X} selected — ASKL 0x{a:08X}, {p.stat().st_size} bytes.")
            except Exception as exc:
                self.anim_mod_status_var.set(str(exc))

    def use_replacement_in_for_mod_output(self):
        path = Path(self.target_file_var.get().strip().strip('"'))
        if not path.is_file():
            messagebox.showwarning("XESM3 Mod Output", "Select a valid Replacement IN / rebuilt ANIM first.")
            return
        self.anim_mod_output_anim_var.set(str(path))
        self.anim_mod_status_var.set(f"Using Replacement IN: {path.name}")

    def build_one_click_anim_mod(self):
        try:
            anim = Path(self.anim_mod_output_anim_var.get().strip().strip('"'))
            extracted = Path(self.extracted_character_folder_var.get().strip().strip('"'))
            out_raw = self.out_dir_var.get().strip().strip('"')
            if not anim.is_file():
                raise FileNotFoundError("Select the rebuilt .anim first.")
            if not extracted.is_dir():
                raise FileNotFoundError("Select the extracted pack folder containing 06_MOD_LOADER_READY/filelist.apkf.txt.")
            if not out_raw:
                raise FileNotFoundError("Choose an output folder first.")
            out = Path(out_raw)
            out.mkdir(parents=True, exist_ok=True)
            result = build_anim_mod_loader_output(
                rebuilt_anim=anim,
                extracted_pack_root=extracted,
                output_root=out,
                mod_name=self.anim_mod_name_var.get(),
                make_zip=True,
            )
            ident = result.identity
            text = (
                "ONE-CLICK ANIM MOD BUILD PASS\n"
                "=============================\n\n"
                f"Source: {Path(result.source_anim).name}\n"
                f"Source size: {result.source_size} bytes\n"
                f"Resource: 0x{result.source_hash:08X} {ident.resource_name}\n"
                f"Pack: {ident.pack}\n"
                f"APKF owner: {ident.archive}\n"
                f"Target: {ident.target_filename}\n"
                f"Output ANIM: {result.output_anim}\n"
                f"XESM3 mod folder: {result.mod_root}\n"
                f"Ready ZIP: {result.zip_path}\n\n"
                "Target hash and copied ANIM identity verified.\n"
            )
            self.anim_mod_report.delete("1.0", "end")
            self.anim_mod_report.insert("1.0", text)
            self.anim_mod_status_var.set(f"BUILD PASS — {ident.pack}/{ident.archive}/{ident.target_filename}")
            self.log(f"XESM3 Mod Output PASS: 0x{result.source_hash:08X} -> {ident.pack}/{ident.archive}/{ident.target_filename}")
            self._last_anim_mod_output = Path(result.mod_root)
            try:
                open_path(Path(result.mod_root))
            except Exception:
                pass
        except Exception as exc:
            self.anim_mod_status_var.set(f"BUILD FAILED — {exc}")
            messagebox.showerror("XESM3 Mod Output", str(exc))
            self.log(f"XESM3 Mod Output failed: {exc}")

    def build_one_click_wrap_anim_mod(self):
        """v5.2.184 WRAP button for rebuilt/same-identity ANIM output."""
        try:
            anim = Path(self.anim_mod_output_anim_var.get().strip().strip('"'))
            extracted = Path(self.extracted_character_folder_var.get().strip().strip('"'))
            out_raw = self.out_dir_var.get().strip().strip('"')
            if not anim.is_file():
                raise FileNotFoundError("Select the rebuilt .anim or .wrap.anim first.")
            if not extracted.is_dir():
                raise FileNotFoundError("Select Slot 2: the MOD LOADER READY / extracted pack folder containing WRAP_EXTRACTS.")
            if not out_raw:
                raise FileNotFoundError("Choose an output folder first.")
            out = Path(out_raw); out.mkdir(parents=True, exist_ok=True)
            result = build_wrap_anim_xesm3_output(
                target_anim=anim,
                donor_anim=anim,
                extracted_pack_root=extracted,
                output_root=out,
                mod_name=self.anim_mod_name_var.get(),
                make_zip=True,
            )
            self._last_anim_mod_output = Path(result.mod_root)
            self.anim_mod_status_var.set(
                f"WRAP BUILD PASS — 0x{result.target_hash:08X} | {result.donor_mode} | {Path(result.zip_path).name}"
            )
            text = (
                "ONE-CLICK WRAP.ANIM MOD BUILD PASS\n"
                "==================================\n\n"
                f"Source: {anim.name}\n"
                f"Target hash: 0x{result.target_hash:08X}\n"
                f"Owner: {result.pack}/{result.archive}\n"
                f"Output: {result.output_wrap_anim}\n"
                f"Donor mode: {result.donor_mode}\n"
                f"Ready ZIP: {result.zip_path}\n"
            )
            self.anim_mod_report.delete("1.0", "end")
            self.anim_mod_report.insert("1.0", text)
            self.log(f"One-click WRAP.ANIM output PASS: {result.output_wrap_anim}")
            try:
                open_path(Path(result.mod_root))
            except Exception:
                pass
        except Exception as exc:
            self.anim_mod_status_var.set(f"WRAP BUILD FAILED — {exc}")
            messagebox.showerror("WRAP.ANIM Mod Output", str(exc))
            self.log(f"WRAP.ANIM Mod Output failed: {exc}")

    def open_anim_mod_output(self):
        path = getattr(self, "_last_anim_mod_output", None)
        if path and Path(path).exists():
            open_path(Path(path))
            return
        out_raw = self.out_dir_var.get().strip().strip('"')
        if out_raw and Path(out_raw).exists():
            open_path(Path(out_raw))
        else:
            messagebox.showinfo("XESM3 Mod Output", "Build a mod or choose an output folder first.")

    # v5.2.131 CH_SPIDERMAN NAMED PROFILE UI
    def _build_named_profile_page(self):
        if not hasattr(self, "workbook"):
            return
        page=ttk.Frame(self.workbook,style="Body.TFrame",padding=10)
        page.columnconfigure(1,weight=1); page.columnconfigure(4,weight=1); page.rowconfigure(7,weight=1)
        self.workbook.add(page,text="Character Named Tracks")
        self.named_profile_page=page
        ttk.Label(page,text="BUILT-IN CHARACTER NAMED MOTION TRACK MAP",style="SectionTitle.TLabel").grid(row=0,column=0,columnspan=6,sticky="w",pady=(0,4))
        ttk.Label(page,text="Built-in named profiles: Spider-Man / Black Suit / Peter share 0xCFB154CD; Player Goblin uses 0x900E49A5. Converts compressed RAW TRACK numbers into FK field + real bone + component. .anim and .wrap.anim are supported.",style="Muted.TLabel",wraplength=1120).grid(row=1,column=0,columnspan=6,sticky="w",pady=(0,8))
        ttk.Label(page,text="ANIM",style="CardLabel.TLabel").grid(row=2,column=0,sticky="w",padx=4,pady=4)
        ttk.Entry(page,textvariable=self.named_profile_anim_var).grid(row=2,column=1,columnspan=3,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="Browse ANIM",command=self.browse_named_profile_anim).grid(row=2,column=4,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="Use Decoder ANIM",command=self.use_decoder_anim_for_named_profile).grid(row=2,column=5,sticky="ew",padx=4,pady=4)
        ttk.Label(page,text="Search",style="CardLabel.TLabel").grid(row=3,column=0,sticky="w",padx=4,pady=4)
        ttk.Entry(page,textvariable=self.named_profile_search_var).grid(row=3,column=1,columnspan=2,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="BUILD NAMED TRACK MAP",command=self.build_spiderman_named_track_map,style="Accent.TButton").grid(row=3,column=3,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="SEND SELECTED TRACK TO QUICK EDITOR",command=self.send_named_track_to_quick_editor).grid(row=3,column=4,columnspan=2,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="Export CSV",command=self.export_spiderman_named_track_csv).grid(row=4,column=3,sticky="ew",padx=4,pady=4)
        ttk.Button(page,text="Export JSON",command=self.export_spiderman_named_track_json).grid(row=4,column=4,sticky="ew",padx=4,pady=4)
        ttk.Label(page,textvariable=self.named_profile_status_var,style="CardLabel.TLabel",wraplength=1120).grid(row=5,column=0,columnspan=6,sticky="w",padx=4,pady=(4,6))
        cols=("track","field","element","bone_index","bone","component","source")
        self.named_profile_tree=ttk.Treeview(page,columns=cols,show="headings",height=18)
        widths={"track":70,"field":180,"element":70,"bone_index":80,"bone":260,"component":90,"source":230}
        for col in cols:
            self.named_profile_tree.heading(col,text=col.replace("_"," ").title()); self.named_profile_tree.column(col,width=widths[col],anchor="w")
        self.named_profile_tree.grid(row=7,column=0,columnspan=5,sticky="nsew",padx=(4,0),pady=4)
        ys=ttk.Scrollbar(page,orient="vertical",command=self.named_profile_tree.yview); ys.grid(row=7,column=5,sticky="ns",padx=(0,4),pady=4); self.named_profile_tree.configure(yscrollcommand=ys.set)
        self.named_profile_tree.bind("<Double-1>",lambda _e:self.send_named_track_to_quick_editor())
        self.named_profile_search_var.trace_add("write",lambda *_:self.refresh_spiderman_named_track_tree())

    def browse_named_profile_anim(self):
        path=filedialog.askopenfilename(title="Select SM3 Character ANIM / WRAP.ANIM",filetypes=[("SM3 ANIM / WRAP.ANIM","*.anim *.wrap.anim"),("All files","*.*")])
        if path:
            self.named_profile_anim_var.set(path); self._named_profile_rows=[]
            try:
                payload = read_anim_payload(Path(path))
                h,a,_v,t=inspect_named_profile_anim_identity(payload)
                if has_builtin_profile(a):
                    label = identify_character(path, a)
                    self.named_profile_status_var.set(f"ANIM 0x{h:08X} — {label} / 0x{a:08X} PROFILE MATCH — {t} compressed tracks. Click BUILD NAMED TRACK MAP.")
                else:
                    self.named_profile_status_var.set(f"ANIM 0x{h:08X} expects ASKL 0x{a:08X}; no built-in named profile exists for this skeleton.")
            except Exception as exc: self.named_profile_status_var.set(str(exc))

    def use_decoder_anim_for_named_profile(self):
        raw=self.decoder_anim_var.get().strip().strip('"') if hasattr(self,'decoder_anim_var') else ''
        if not raw or not Path(raw).is_file(): messagebox.showwarning("Character Named Tracks","Select an ANIM / WRAP.ANIM on the decoder/editor first."); return
        self.named_profile_anim_var.set(raw); self.build_spiderman_named_track_map()

    def build_spiderman_named_track_map(self):
        try:
            path=Path(self.named_profile_anim_var.get().strip().strip('"'))
            if not path.is_file(): raise FileNotFoundError("Select a valid .anim or .wrap.anim first.")
            payload = read_anim_payload(path)
            _h, askl_hash, _v, _t = inspect_named_profile_anim_identity(payload)
            rows=build_named_track_map(payload); self._named_profile_rows=list(rows); self.refresh_spiderman_named_track_tree()
            label = identify_character(path, askl_hash)
            self.named_profile_status_var.set(f"NAMED PROFILE PASS — {label} / 0x{askl_hash:08X} — {len(rows)} compressed tracks mapped.")
            if hasattr(self,'log'): self.log(f"Character Named Track Map PASS: {label} {path.name} -> {len(rows)} tracks")
        except Exception as exc:
            self.named_profile_status_var.set(f"NAMED PROFILE FAILED — {exc}"); messagebox.showerror("Character Named Tracks",str(exc))

    def refresh_spiderman_named_track_tree(self):
        if not hasattr(self,'named_profile_tree'): return
        q=self.named_profile_search_var.get().strip().lower()
        for item in self.named_profile_tree.get_children(): self.named_profile_tree.delete(item)
        for row in self._named_profile_rows:
            hay=f"{row.track_index} {row.field_name} {row.element_index} {row.bone_index} {row.bone_name} {row.component_name} {row.source}".lower()
            if q and q not in hay: continue
            self.named_profile_tree.insert('', 'end', values=(row.track_index,row.field_name,row.element_index,'' if row.bone_index is None else row.bone_index,row.bone_name,row.component_name,row.source))

    def _selected_spiderman_named_track(self):
        sel=self.named_profile_tree.selection() if hasattr(self,'named_profile_tree') else ()
        if not sel: return None
        vals=self.named_profile_tree.item(sel[0],'values')
        if not vals: return None
        ti=int(vals[0]);
        for row in self._named_profile_rows:
            if row.track_index==ti: return row
        return None

    def send_named_track_to_quick_editor(self):
        row = self._selected_spiderman_named_track()
        if row is None:
            messagebox.showinfo("Character Named Tracks", "Select a track row first.")
            return
        named = f"Track {row.track_index}: {row.field_name} / {row.bone_name} / {row.component_name}"
        if not hasattr(self, 'editor_quick_track_var'):
            self.named_profile_status_var.set(
                "NAMED TRACK SELECTED — " + named + ". This source toolkit has no Quick Motion Editor control to receive it."
            )
            return

        # Carry the same ANIM into the Motion Editor and queue the exact track.
        raw_anim = self.named_profile_anim_var.get().strip().strip('"')
        if raw_anim and Path(raw_anim).is_file():
            self.decoder_anim_var.set(raw_anim)
        self.editor_quick_track_var.set(str(row.track_index))

        if self._anim_editor is not None:
            self.editor_quick_select_track(quiet=True)
            self.editor_status_var.set("CFB154CD NAMED: " + named)
            self.named_profile_status_var.set("SENT TO QUICK EDITOR — " + named)
        else:
            self.editor_status_var.set(
                "CFB154CD NAMED TRACK QUEUED: " + named + " — click 1) LOAD / MAP EDITOR."
            )
            self.named_profile_status_var.set(
                "QUEUED FOR QUICK EDITOR — " + named + " — Motion Editor opened; click 1) LOAD / MAP EDITOR."
            )
        try:
            self.workbook.select(self.editor_page)
        except Exception:
            pass

    def export_spiderman_named_track_csv(self):
        if not self._named_profile_rows: self.build_spiderman_named_track_map()
        if not self._named_profile_rows: return
        path=filedialog.asksaveasfilename(title="Export named track map CSV",defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if path: export_named_track_map_csv(Path(path),self._named_profile_rows); self.named_profile_status_var.set(f"CSV exported: {Path(path).name}")

    def export_spiderman_named_track_json(self):
        if not self._named_profile_rows: self.build_spiderman_named_track_map()
        if not self._named_profile_rows: return
        anim=Path(self.named_profile_anim_var.get().strip().strip('"'))
        path=filedialog.asksaveasfilename(title="Export named track map JSON",defaultextension=".json",filetypes=[("JSON","*.json")])
        if path: export_named_track_map_json(Path(path),anim.read_bytes(),self._named_profile_rows); self.named_profile_status_var.set(f"JSON exported: {Path(path).name}")
