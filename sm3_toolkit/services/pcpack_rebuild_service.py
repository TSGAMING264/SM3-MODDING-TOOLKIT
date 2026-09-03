from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import struct
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sm3_toolkit.services.pack_extract_service import (
    probe_pack_bytes,
    clean_name,
    apkf_slices_from_probe,
    extract_apkf_archive,
)


REBUILD_LAB_VERSION = "v1.0_LAYOUT_FAITHFUL_REPACK_ENGINE_V2"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys or ["empty"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@dataclass
class RebuildLabResult:
    verdict: str
    original_pack_name: str
    original_size: int
    rebuilt_size: int
    original_sha256: str
    rebuilt_sha256: str
    byte_identical: bool
    workspace: str
    rebuilt_pack: str
    route: str
    outer_rows: int
    hsam_markers: int
    apkf_markers: int
    notes: List[str]


@dataclass
class PatchedPackReviewResult:
    verdict: str
    original_pack_name: str
    patched_pack_name: str
    original_size: int
    patched_size: int
    original_sha256: str
    patched_sha256: str
    byte_identical: bool
    same_size: bool
    same_route: bool
    same_outer_row_count: bool
    same_marker_counts: bool
    header_4096_identical: bool
    review_workspace: str
    original_route: str
    patched_route: str
    original_outer_rows: int
    patched_outer_rows: int
    original_hsam_markers: int
    patched_hsam_markers: int
    original_apkf_markers: int
    patched_apkf_markers: int
    notes: List[str]


@dataclass
class FullExtractRebuildResult:
    verdict: str
    original_pack_name: str
    original_size: int
    rebuilt_size: int
    original_sha256: str
    rebuilt_sha256: str
    byte_identical: bool
    workspace: str
    extracted_folder: str
    rebuilt_pack: str
    route: str
    resources_seen: int
    resources_replaced: int
    tex_rows_seen: int
    tex_payloads_replaced: int
    tex_preserved: int
    blocked_count: int
    notes: List[str]


@dataclass
class ExtractedFolderDetection:
    selected_folder: str
    resolved_folder: str
    inner_csv: str
    candidate_count: int
    status: str
    notes: List[str]


KEEP_THE_MESSES_TEXT = """PCPACK Rebuild Lab v0.3 - KEEP THE MESSES RULES
================================================

This lab now has three safe purposes:
1. No-change rebuild control proof.
2. Full extracted-folder rebuild with TEX-safe rules.
3. Review rebuilt/patched PCPACK output against the clean original.

Rules:
- Do not clean unknown bytes.
- Do not reorder resources.
- Do not rename resources automatically.
- Do not normalize folders into a new structure.
- Do not delete tiny stubs.
- Do not remove padding/alignment.
- Do not remove unknown bytes.
- Do not edit original PCPACK.
- Rebuild output must be a new copy.

Current truth:
- Older send-off reports may mention v5.2.33/v0.1 because they came from multiple branches.
- The current texture-proven branch is v5.2.40 Paint.NET/GIMP editor-safe Tex Swapper.
- MEGACITY patched PCPACK and CH_SPIDERMAN patched PCPACK both boot-tested fine by the user.
- Single-file editor-safe CH_SPIDERMAN patch also boot-tested fine.

v0.3 modes:
- Raw-preserving no-change rebuild control.
- Full extract-folder rebuild that overlays only same-size known ranges back into the original byte stream.
- TEX-safe rebuild: preserve original TEX unless a safe same-size DDS/component payload replacement is found.
- Rebuilt/patched PCPACK review/comparison against the clean original pack.

Still blocked:
- Do not enable arbitrary size-changing resource rebuild here.
- Do not rebuild animation/resources with changed sizes until table/offset update logic is proven.
- Do not raw-rebuild TEX from broken editor output. TEX must be preserved or replaced through safe same-size component/DDS payload rules.
"""


BOOT_TEST_NOTES = """Rebuild Boot Test Notes
=======================

What PASS means here:
- The tool wrote a rebuilt no-change PCPACK copy.
- The rebuilt copy is byte-identical to the original.
- The detected SM3 route/table metadata was preserved in reports.

What the user still needs to test:
- Put the rebuilt copy in the game pack location using a backup-safe method.
- Launch the game.
- Confirm the target pack loads without crashing.

Do not test edited/size-changing rebuilds yet.
The no-change control is still the first proof step. v0.3 also adds full extracted-folder rebuild review.
"""


HEADER_PRESERVE_RULES = """PCPACK Rebuild Lab - Header Preservation Rules
=============================================

The rebuild route must follow the same header the game expects.
For no-change rebuild controls this means:
- Preserve the full original byte stream.
- Preserve the PCPACK beginning/header region exactly.
- Preserve marker positions, outer rows, padding, unknown bytes, tiny stubs, and order.
- Do not regenerate or normalize headers.
- Do not clean/compact the pack.

For current Tex Swapper patched PCPACK review this means:
- The original pack stays untouched.
- The patched output should preserve route family, marker counts, table shape, and size when doing same-size DDS replacement.
- Texture bytes may differ; byte-identical is NOT expected after a real texture patch.
- Header/beginning regions should remain byte-identical unless a proven table field had to change.

If a future rebuild mode changes resource sizes, it must update only known size/offset fields while preserving every unknown/header byte that is not proven safe to change.
"""


CURRENT_BRANCH_REPORT_TEXT = """PCPACK Rebuild Lab - Current Branch Truth Report
================================================

This report intentionally replaces the mixed old send-off notes from multiple branches.

Latest verified texture branch:
- v5.2.40 Paint.NET / GIMP editor-safe Tex Swapper tested source.

Confirmed in-game/user tests:
- MEGACITY patched PCPACK from final folder reimport loaded in-game.
- CH_SPIDERMAN patched PCPACK from folder editor-safe reimport loaded in-game.
- CH_SPIDERMAN single-file editor-safe patch loaded in-game.

What this means for PCPACK Rebuild Lab:
- No-change rebuild remains the control test. It should be byte-identical.
- Real texture patched packs are not byte-identical because texture payloads changed.
- A full extracted-folder rebuild should be reviewed against the clean original for route, marker counts, table row shape, size, header preservation, and texture actions.
- Texture problems from older full rebuild attempts should be handled by preserving original TEX or patching only safe same-size DDS/component payloads.
- The final proof is still an in-game boot/load test.

Do not regress to older mixed-branch instructions:
- v5.2.33 header-lock notes are useful history, not the latest texture workflow.
- Old GIMP normalizer-only workflow is superseded by editor-safe rebuild.
- Old manual copy patch / old test patch / old manual options routes are removed from current visible Tex Swapper workflow.
"""


def marker_rows(data: bytes) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for marker in (b"hsam", b"APKF", b"mash"):
        pos = 0
        count = 0
        while count < 4096:
            idx = data.find(marker, pos)
            if idx < 0:
                break
            rows.append({"marker": marker.decode("ascii", "replace"), "offset_hex": f"0x{idx:X}", "offset_dec": idx})
            pos = idx + 1
            count += 1
    return sorted(rows, key=lambda r: int(r["offset_dec"]))


def _small_diff_summary(a: bytes, b: bytes, limit: int = 200) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    min_len = min(len(a), len(b))
    for i in range(min_len):
        if a[i] != b[i]:
            rows.append({"offset_dec": i, "offset_hex": f"0x{i:X}", "original_byte": f"{a[i]:02X}", "rebuilt_byte": f"{b[i]:02X}"})
            if len(rows) >= limit:
                return rows
    if len(a) != len(b):
        rows.append({"offset_dec": min_len, "offset_hex": f"0x{min_len:X}", "original_byte": "EOF" if len(a) <= min_len else f"{a[min_len]:02X}", "rebuilt_byte": "EOF" if len(b) <= min_len else f"{b[min_len]:02X}"})
    return rows


def create_no_change_workspace(original_pack: Path, output_root: Path) -> Path:
    """Create a raw-preserving no-change rebuild workspace.

    This is intentionally conservative. It does not rewrite tables yet. It stores
    original bytes and structure reports, then v0.1 rebuild concatenates/copies
    those preserved bytes back into a new PCPACK copy. This proves the UI/workflow,
    backup discipline, report discipline, and boot-test handoff before any edit
    or size-changing code is enabled.
    """
    original_pack = Path(original_pack)
    output_root = Path(output_root)
    if not original_pack.exists() or not original_pack.is_file():
        raise FileNotFoundError(f"Original PCPACK not found: {original_pack}")
    data = original_pack.read_bytes()
    probe = probe_pack_bytes(original_pack.name, data)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = output_root / f"{original_pack.stem}_REBUILD_LAB_{timestamp}"
    meta_dir = workspace / "00_REBUILD_METADATA"
    preserved_dir = workspace / "01_RAW_PRESERVED_DO_NOT_EDIT"
    rebuild_dir = workspace / "02_REBUILD_OUTPUT"
    for d in (meta_dir, preserved_dir, rebuild_dir):
        d.mkdir(parents=True, exist_ok=True)

    preserved_original = preserved_dir / f"{original_pack.name}.original_bytes.preserve"
    preserved_original.write_bytes(data)

    write_json(meta_dir / "PACK_PROBE.json", probe.to_dict())
    write_csv(meta_dir / "OUTER_ROWS.csv", [r.to_dict() for r in probe.outer_rows])
    write_csv(meta_dir / "MARKER_OFFSETS.csv", marker_rows(data))
    (meta_dir / "KEEP_THE_MESSES_RULES.txt").write_text(KEEP_THE_MESSES_TEXT, encoding="utf-8")
    (meta_dir / "REBUILD_BOOT_TEST_NOTES.txt").write_text(BOOT_TEST_NOTES, encoding="utf-8")
    (meta_dir / "REBUILD_HEADER_PRESERVE_RULES.txt").write_text(HEADER_PRESERVE_RULES, encoding="utf-8")
    manifest = {
        "rebuild_lab_version": REBUILD_LAB_VERSION,
        "mode": "NO_CHANGE_RAW_PRESERVING_REBUILD",
        "original_pack_name": original_pack.name,
        "original_size": len(data),
        "original_sha256": hashlib.sha256(data).hexdigest(),
        "preserved_original_relative_path": preserved_original.relative_to(workspace).as_posix(),
        "route": probe.route,
        "detection": probe.detection,
        "outer_rows": len(probe.outer_rows),
        "hsam_marker_count": len(probe.hsam_offsets),
        "apkf_marker_count": len(probe.apkf_offsets),
        "created_at": timestamp,
        "rules": [
            "keep_messes",
            "preserve_unknown_bytes",
            "preserve_padding_alignment",
            "preserve_tiny_stubs",
            "do_not_edit_original",
            "no_change_rebuild_only",
            "preserve_original_header_bytes",
            "do_not_regenerate_pack_header",
        ],
    }
    write_json(meta_dir / "WORKSPACE_MANIFEST.json", manifest)
    return workspace


def rebuild_no_change(workspace: Path) -> RebuildLabResult:
    workspace = Path(workspace)
    manifest_path = workspace / "00_REBUILD_METADATA" / "WORKSPACE_MANIFEST.json"
    if not manifest_path.exists():
        raise FileNotFoundError("WORKSPACE_MANIFEST.json not found. Create a rebuild workspace first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preserved = workspace / manifest["preserved_original_relative_path"]
    if not preserved.exists():
        raise FileNotFoundError("Preserved original bytes file is missing from workspace.")
    data = preserved.read_bytes()
    out_dir = workspace / "02_REBUILD_OUTPUT"
    out_dir.mkdir(parents=True, exist_ok=True)
    rebuilt_name = f"{Path(manifest['original_pack_name']).stem}_REBUILT_NO_CHANGE.PCPACK"
    rebuilt = out_dir / rebuilt_name
    rebuilt.write_bytes(data)
    return compare_rebuilt(workspace, rebuilt)


def compare_rebuilt(workspace: Path, rebuilt_pack: Path) -> RebuildLabResult:
    workspace = Path(workspace)
    rebuilt_pack = Path(rebuilt_pack)
    manifest = json.loads((workspace / "00_REBUILD_METADATA" / "WORKSPACE_MANIFEST.json").read_text(encoding="utf-8"))
    original_bytes = (workspace / manifest["preserved_original_relative_path"]).read_bytes()
    rebuilt_bytes = rebuilt_pack.read_bytes()
    original_sha = hashlib.sha256(original_bytes).hexdigest()
    rebuilt_sha = hashlib.sha256(rebuilt_bytes).hexdigest()
    byte_identical = original_bytes == rebuilt_bytes
    verdict = "PASS" if byte_identical else "FAIL"
    notes = [
        "NO_CHANGE_REBUILD_ONLY",
        "UNKNOWN_BYTES_PRESERVED",
        "PADDING_ALIGNMENT_PRESERVED",
        "RESOURCE_ORDER_PRESERVED_BY_RAW_COPY",
        "TINY_STUBS_PRESERVED_BY_RAW_COPY",
        "BOOT_TEST_USER_REQUIRED",
    ]
    result = RebuildLabResult(
        verdict=verdict,
        original_pack_name=manifest["original_pack_name"],
        original_size=len(original_bytes),
        rebuilt_size=len(rebuilt_bytes),
        original_sha256=original_sha,
        rebuilt_sha256=rebuilt_sha,
        byte_identical=byte_identical,
        workspace=str(workspace),
        rebuilt_pack=str(rebuilt_pack),
        route=manifest.get("route", ""),
        outer_rows=int(manifest.get("outer_rows", 0)),
        hsam_markers=int(manifest.get("hsam_marker_count", 0)),
        apkf_markers=int(manifest.get("apkf_marker_count", 0)),
        notes=notes,
    )
    reports = workspace / "00_REBUILD_METADATA"
    write_json(reports / "REBUILD_VERDICT.json", asdict(result))
    verdict_txt = [
        "PCPACK Rebuild Lab v0.1 Verdict",
        "=================================",
        "",
        f"Verdict: {result.verdict}",
        f"Original pack: {result.original_pack_name}",
        f"Route: {result.route}",
        f"Original size: {result.original_size}",
        f"Rebuilt size: {result.rebuilt_size}",
        f"Byte-identical: {result.byte_identical}",
        f"Original SHA256: {result.original_sha256}",
        f"Rebuilt SHA256: {result.rebuilt_sha256}",
        f"Outer rows: {result.outer_rows}",
        f"hsam markers: {result.hsam_markers}",
        f"APKF markers: {result.apkf_markers}",
        "",
        "KEEP THE MESSES STATUS:",
        "- Unknown bytes preserved by raw-preserving no-change rebuild.",
        "- PCPACK header/beginning bytes preserved exactly; no header regeneration.",
        "- Padding/alignment preserved by raw-preserving no-change rebuild.",
        "- Tiny stubs preserved by raw-preserving no-change rebuild.",
        "- Resource order preserved by raw-preserving no-change rebuild.",
        "",
        "Next required proof:",
        "- User boot test with rebuilt PCPACK copy.",
        "- Do not enable edited/size-changing rebuild until no-change copy boots.",
    ]
    (reports / "REBUILD_VERDICT.txt").write_text("\n".join(verdict_txt) + "\n", encoding="utf-8")
    struct_rows = [{
        "check": "size_match",
        "status": "PASS" if result.original_size == result.rebuilt_size else "FAIL",
        "original": result.original_size,
        "rebuilt": result.rebuilt_size,
    }, {
        "check": "sha256_match",
        "status": "PASS" if result.original_sha256 == result.rebuilt_sha256 else "FAIL",
        "original": result.original_sha256,
        "rebuilt": result.rebuilt_sha256,
    }, {
        "check": "byte_identical",
        "status": "PASS" if result.byte_identical else "FAIL",
        "original": result.byte_identical,
        "rebuilt": result.byte_identical,
    }]
    write_csv(reports / "ORIGINAL_VS_REBUILT_STRUCTURE.csv", struct_rows)
    diff_rows = _small_diff_summary(original_bytes, rebuilt_bytes)
    write_csv(reports / "ORIGINAL_VS_REBUILT_FIRST_DIFFS.csv", diff_rows, fieldnames=["offset_dec", "offset_hex", "original_byte", "rebuilt_byte"])
    offset_rows = []
    probe = probe_pack_bytes(result.original_pack_name, original_bytes)
    for r in probe.outer_rows:
        offset_rows.append({
            "index": r.index,
            "hash": f"0x{r.hash_value:08X}",
            "type_hex": f"0x{r.type_id:X}",
            "data_offset": r.data_offset,
            "data_size": r.data_size,
            "data_end": r.end,
            "status": "PASS" if 0 <= r.data_offset <= r.end <= len(original_bytes) else "FAIL",
            "note": "outer row range valid in original/rebuilt byte-identical copy",
        })
    write_csv(reports / "OFFSET_VALIDATION.csv", offset_rows)
    preserved_rows = [{"item": "unknown_bytes", "status": "PRESERVED_RAW"}, {"item": "padding_alignment", "status": "PRESERVED_RAW"}, {"item": "tiny_stubs", "status": "PRESERVED_RAW"}, {"item": "resource_order", "status": "PRESERVED_RAW"}, {"item": "pcpack_header", "status": "PRESERVED_RAW"}]
    write_csv(reports / "PRESERVED_UNKNOWN_BYTES_SUMMARY.csv", preserved_rows)
    header_rows = []
    for size in (64, 128, 256, 512, 1024, 4096):
        original_header = original_bytes[:min(size, len(original_bytes))]
        rebuilt_header = rebuilt_bytes[:min(size, len(rebuilt_bytes))]
        header_rows.append({
            "header_region_bytes": size,
            "compared_bytes": len(original_header),
            "original_sha256": hashlib.sha256(original_header).hexdigest(),
            "rebuilt_sha256": hashlib.sha256(rebuilt_header).hexdigest(),
            "byte_identical": original_header == rebuilt_header,
            "status": "PASS" if original_header == rebuilt_header else "FAIL",
            "note": "PCPACK header/beginning region preserved exactly; do not regenerate/normalize headers",
        })
    write_csv(reports / "PCPACK_HEADER_PRESERVATION.csv", header_rows)
    (reports / "REBUILD_HEADER_PRESERVE_RULES.txt").write_text(HEADER_PRESERVE_RULES, encoding="utf-8")
    (reports / "CURRENT_BRANCH_TRUTH_REPORT.txt").write_text(CURRENT_BRANCH_REPORT_TEXT, encoding="utf-8")
    return result


def _header_compare_rows(original_bytes: bytes, other_bytes: bytes) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for size in (64, 128, 256, 512, 1024, 2048, 4096, 8192):
        compared = min(size, len(original_bytes), len(other_bytes))
        a = original_bytes[:compared]
        b = other_bytes[:compared]
        rows.append({
            "header_region_bytes": size,
            "compared_bytes": compared,
            "original_sha256": hashlib.sha256(a).hexdigest(),
            "other_sha256": hashlib.sha256(b).hexdigest(),
            "byte_identical": a == b,
            "status": "PASS" if a == b else "REVIEW",
            "note": "For texture-only same-size patches, header/beginning bytes should normally remain unchanged.",
        })
    return rows


def _marker_count_map(data: bytes) -> Dict[str, int]:
    return {
        "hsam": data.count(b"hsam"),
        "APKF": data.count(b"APKF"),
        "mash": data.count(b"mash"),
    }


def write_current_branch_rebuild_report(output_root: Path) -> Path:
    output_root = Path(output_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = output_root / f"PCPACK_REBUILD_CURRENT_BRANCH_REPORT_{timestamp}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "CURRENT_BRANCH_TRUTH_REPORT.txt").write_text(CURRENT_BRANCH_REPORT_TEXT, encoding="utf-8")
    write_json(folder / "CURRENT_BRANCH_TRUTH_REPORT.json", {
        "rebuild_lab_version": REBUILD_LAB_VERSION,
        "latest_texture_branch": "v5.2.40 Paint.NET/GIMP editor-safe Tex Swapper",
        "old_sendoff_status": "mixed_branch_history_only",
        "confirmed_tests": [
            "MEGACITY patched PCPACK boot-tested fine",
            "CH_SPIDERMAN folder patched PCPACK boot-tested fine",
            "CH_SPIDERMAN single-file editor-safe patch boot-tested fine",
        ],
        "safe_next_step": "Use Verify Patched PCPACK Output against the clean original before boot-testing a full pack rebuild.",
    })
    return folder


def verify_patched_pcpack(original_pack: Path, patched_pack: Path, output_root: Path) -> PatchedPackReviewResult:
    original_pack = Path(original_pack)
    patched_pack = Path(patched_pack)
    output_root = Path(output_root)
    if not original_pack.exists() or not original_pack.is_file():
        raise FileNotFoundError(f"Original PCPACK not found: {original_pack}")
    if not patched_pack.exists() or not patched_pack.is_file():
        raise FileNotFoundError(f"Patched PCPACK not found: {patched_pack}")
    original_bytes = original_pack.read_bytes()
    patched_bytes = patched_pack.read_bytes()
    original_probe = probe_pack_bytes(original_pack.name, original_bytes)
    patched_probe = probe_pack_bytes(patched_pack.name, patched_bytes)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    workspace = output_root / f"{original_pack.stem}_PATCHED_PCPACK_REVIEW_{timestamp}"
    reports = workspace / "00_PATCHED_REBUILD_REVIEW"
    reports.mkdir(parents=True, exist_ok=True)

    original_sha = hashlib.sha256(original_bytes).hexdigest()
    patched_sha = hashlib.sha256(patched_bytes).hexdigest()
    same_size = len(original_bytes) == len(patched_bytes)
    byte_identical = original_bytes == patched_bytes
    same_route = original_probe.route == patched_probe.route
    same_outer_count = len(original_probe.outer_rows) == len(patched_probe.outer_rows)
    original_markers = _marker_count_map(original_bytes)
    patched_markers = _marker_count_map(patched_bytes)
    same_marker_counts = original_markers == patched_markers
    header_rows = _header_compare_rows(original_bytes, patched_bytes)
    header_4096_identical = next((bool(r["byte_identical"]) for r in header_rows if r["header_region_bytes"] == 4096), False)

    if byte_identical:
        verdict = "PASS_NO_CHANGE_OR_NO_EDITS_DETECTED"
    elif same_size and same_route and same_outer_count and same_marker_counts and header_4096_identical:
        verdict = "PASS_PATCHED_PCPACK_BOOT_TEST_CANDIDATE"
    else:
        verdict = "REVIEW_BEFORE_BOOT_TEST"

    notes = [
        "CURRENT_BRANCH_V5_2_40_TEXTURE_FLOW",
        "ORIGINAL_PACK_NOT_MODIFIED",
        "TEXTURE_PATCHES_ARE_NOT_EXPECTED_TO_BE_BYTE_IDENTICAL",
        "BOOT_TEST_USER_REQUIRED",
    ]
    if not same_size:
        notes.append("SIZE_CHANGED_REVIEW_TABLE_OFFSET_LOGIC_REQUIRED")
    if not header_4096_identical:
        notes.append("HEADER_REGION_CHANGED_REVIEW_REQUIRED")

    result = PatchedPackReviewResult(
        verdict=verdict,
        original_pack_name=original_pack.name,
        patched_pack_name=patched_pack.name,
        original_size=len(original_bytes),
        patched_size=len(patched_bytes),
        original_sha256=original_sha,
        patched_sha256=patched_sha,
        byte_identical=byte_identical,
        same_size=same_size,
        same_route=same_route,
        same_outer_row_count=same_outer_count,
        same_marker_counts=same_marker_counts,
        header_4096_identical=header_4096_identical,
        review_workspace=str(workspace),
        original_route=original_probe.route,
        patched_route=patched_probe.route,
        original_outer_rows=len(original_probe.outer_rows),
        patched_outer_rows=len(patched_probe.outer_rows),
        original_hsam_markers=original_markers["hsam"],
        patched_hsam_markers=patched_markers["hsam"],
        original_apkf_markers=original_markers["APKF"],
        patched_apkf_markers=patched_markers["APKF"],
        notes=notes,
    )

    write_json(reports / "ORIGINAL_PACK_PROBE.json", original_probe.to_dict())
    write_json(reports / "PATCHED_PACK_PROBE.json", patched_probe.to_dict())
    write_json(reports / "PATCHED_PCPACK_REVIEW_VERDICT.json", asdict(result))
    (reports / "CURRENT_BRANCH_TRUTH_REPORT.txt").write_text(CURRENT_BRANCH_REPORT_TEXT, encoding="utf-8")
    (reports / "KEEP_THE_MESSES_RULES.txt").write_text(KEEP_THE_MESSES_TEXT, encoding="utf-8")
    (reports / "REBUILD_HEADER_PRESERVE_RULES.txt").write_text(HEADER_PRESERVE_RULES, encoding="utf-8")
    write_csv(reports / "HEADER_REGION_COMPARISON.csv", header_rows)
    write_csv(reports / "FIRST_BYTE_DIFFS_ORIGINAL_VS_PATCHED.csv", _small_diff_summary(original_bytes, patched_bytes, limit=500), fieldnames=["offset_dec", "offset_hex", "original_byte", "rebuilt_byte"])
    write_csv(reports / "MARKER_COUNT_COMPARISON.csv", [
        {"marker": k, "original_count": original_markers[k], "patched_count": patched_markers[k], "status": "PASS" if original_markers[k] == patched_markers[k] else "REVIEW"}
        for k in ("hsam", "APKF", "mash")
    ])
    write_csv(reports / "ROUTE_STRUCTURE_COMPARISON.csv", [{
        "check": "route", "original": original_probe.route, "patched": patched_probe.route, "status": "PASS" if same_route else "REVIEW"
    }, {
        "check": "pack_size", "original": len(original_bytes), "patched": len(patched_bytes), "status": "PASS" if same_size else "REVIEW"
    }, {
        "check": "outer_row_count", "original": len(original_probe.outer_rows), "patched": len(patched_probe.outer_rows), "status": "PASS" if same_outer_count else "REVIEW"
    }, {
        "check": "byte_identical", "original": byte_identical, "patched": byte_identical, "status": "INFO" if not byte_identical else "PASS"
    }])
    outer_rows = []
    max_rows = max(len(original_probe.outer_rows), len(patched_probe.outer_rows))
    for i in range(max_rows):
        o = original_probe.outer_rows[i] if i < len(original_probe.outer_rows) else None
        p = patched_probe.outer_rows[i] if i < len(patched_probe.outer_rows) else None
        outer_rows.append({
            "index": i,
            "original_hash": f"0x{o.hash_value:08X}" if o else "MISSING",
            "patched_hash": f"0x{p.hash_value:08X}" if p else "MISSING",
            "original_type": f"0x{o.type_id:X}" if o else "MISSING",
            "patched_type": f"0x{p.type_id:X}" if p else "MISSING",
            "original_offset": o.data_offset if o else "MISSING",
            "patched_offset": p.data_offset if p else "MISSING",
            "original_size": o.data_size if o else "MISSING",
            "patched_size": p.data_size if p else "MISSING",
            "status": "PASS" if o and p and o.hash_value == p.hash_value and o.type_id == p.type_id and o.data_offset == p.data_offset and o.data_size == p.data_size else "REVIEW",
        })
    write_csv(reports / "OUTER_ROW_SHAPE_COMPARISON.csv", outer_rows)

    verdict_txt = [
        "PCPACK Rebuild Lab v0.2 - Patched PCPACK Review",
        "=================================================",
        "",
        f"Verdict: {result.verdict}",
        f"Original: {result.original_pack_name}",
        f"Patched: {result.patched_pack_name}",
        f"Original size: {result.original_size}",
        f"Patched size: {result.patched_size}",
        f"Same size: {result.same_size}",
        f"Same route: {result.same_route} ({result.original_route} -> {result.patched_route})",
        f"Same outer row count: {result.same_outer_row_count}",
        f"Same marker counts: {result.same_marker_counts}",
        f"First 4096 header bytes identical: {result.header_4096_identical}",
        f"Byte-identical: {result.byte_identical}",
        "",
        "Meaning:",
        "- PASS_PATCHED_PCPACK_BOOT_TEST_CANDIDATE means the patched pack looks structurally safe for a boot/load test.",
        "- REVIEW_BEFORE_BOOT_TEST means inspect reports before replacing a game pack.",
        "- Real texture patches are not expected to be byte-identical.",
        "",
        "Next step:",
        "- Backup the original pack, rename/copy the patched pack into place, and test in-game.",
    ]
    (reports / "PATCHED_PCPACK_REVIEW_VERDICT.txt").write_text("\n".join(verdict_txt) + "\n", encoding="utf-8")
    return result



def _parse_int_maybe(value: Any) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except Exception:
        return None


def _row_component_ranges(row: Dict[str, Any], pack_size: int) -> List[Tuple[int, int, int]]:
    ranges: List[Tuple[int, int, int]] = []
    for ci in range(16):
        start = _parse_int_maybe(row.get(f"component{ci}_absolute_start_in_pcpack"))
        end = _parse_int_maybe(row.get(f"component{ci}_absolute_end_in_pcpack"))
        if start is None or end is None:
            continue
        if 0 <= start <= end <= pack_size:
            ranges.append((ci, start, end))
    return ranges


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _try_read_existing_file(path: Path) -> Tuple[Optional[bytes], str]:
    """Read a replacement payload defensively.

    Reportless/manual extracts can contain only a subset of payload files. The regenerated
    reference CSV may point at a reference extraction candidate that was not written, or a
    same-named manual file may be missing. A missing optional payload must never crash a
    whole-pack rebuild; the safe behavior is to preserve the original bytes and log why.
    """
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None, "replacement_file_missing_at_read_time"
        return p.read_bytes(), "OK"
    except Exception as exc:
        return None, f"replacement_file_read_failed:{type(exc).__name__}:{exc}"


_FILE_INDEX_CACHE: Dict[str, Dict[str, List[Path]]] = {}


def _build_file_index(root: Path) -> Dict[str, List[Path]]:
    """Build a lowercase filename -> paths index for large reportless extract folders.

    The user may manually zip only 01/02/05 payload folders and omit 00_REPORTS.
    In that case a regenerated reference report from the original pack points at a
    temporary reference extraction, but the rebuild should prefer the user's chosen
    extracted folder when a same-named file exists.
    """
    root = Path(root)
    key = str(root.resolve()) if root.exists() else str(root)
    cached = _FILE_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    idx: Dict[str, List[Path]] = {}
    try:
        for q in root.rglob("*"):
            try:
                if q.is_file():
                    idx.setdefault(q.name.lower(), []).append(q)
            except OSError:
                continue
    except OSError:
        pass
    for paths in idx.values():
        paths.sort(key=lambda x: (len(str(x)), str(x).lower()))
    _FILE_INDEX_CACHE[key] = idx
    return idx


def _find_file_by_basename(root: Path, name: str) -> Optional[Path]:
    if not name:
        return None
    hits = _build_file_index(root).get(name.lower()) or []
    for h in hits:
        if h.is_file():
            return h
    return None


def _case_insensitive_inner_csvs(root: Path, limit: int = 250) -> List[Path]:
    root = Path(root)
    hits: List[Path] = []
    direct = [
        root / "00_REPORTS" / "INNER_APKF_FILES.csv",
        root / "INNER_APKF_FILES.csv",
    ]
    for p in direct:
        if p.exists() and p.is_file():
            hits.append(p)
    try:
        for p in root.rglob("*"):
            if len(hits) >= limit:
                break
            try:
                if p.is_file() and p.name.lower() == "inner_apkf_files.csv":
                    if p not in hits:
                        hits.append(p)
            except OSError:
                continue
    except OSError:
        pass
    # Stable, shortest paths first so a direct selected pack folder wins over deep junk.
    return sorted(hits, key=lambda q: (len(q.parts), str(q).lower()))


def _candidate_score_for_pack(csv_path: Path, selected_folder: Path, original_pack: Optional[Path]) -> int:
    score = 0
    p = Path(csv_path)
    if p == selected_folder / "00_REPORTS" / "INNER_APKF_FILES.csv":
        score += 1000
    if p == selected_folder / "INNER_APKF_FILES.csv":
        score += 900
    if p.parent.name.upper() == "00_REPORTS":
        score += 100
    if original_pack is not None:
        stem = original_pack.stem.lower()
        text = str(p).replace("\\", "/").lower()
        # Prefer the CSV under the selected pack's own folder when the user selects a master output root.
        if stem in text:
            score += 500
        # Stronger score if an ancestor folder itself starts with the pack name.
        for ancestor in p.parents:
            name = ancestor.name.lower()
            if name == stem or name.startswith(stem + "_") or name.startswith(stem + "-"):
                score += 250
                break
    return score


def _case_insensitive_ownership_manifests(root: Path, limit: int = 250) -> List[Path]:
    """Find Mod Loader Ready ownership manifests without making them mandatory.

    v5.2.149: the repack engine no longer depends on INNER_APKF_FILES.csv.  The
    ownership manifest is useful for resolving the selected per-pack folder, while the
    authoritative component map is parsed directly from the clean original PCPACK.
    """
    root = Path(root)
    hits: List[Path] = []
    direct = [
        root / "06_MOD_LOADER_READY" / "ownership_manifest.json",
        root / "ownership_manifest.json",
    ]
    for q in direct:
        if q.exists() and q.is_file():
            hits.append(q)
    try:
        for q in root.rglob("*"):
            if len(hits) >= limit:
                break
            try:
                if q.is_file() and q.name.lower() == "ownership_manifest.json" and q not in hits:
                    hits.append(q)
            except OSError:
                continue
    except OSError:
        pass
    return sorted(hits, key=lambda q: (len(q.parts), str(q).lower()))


def _manifest_pack_name(path: Path) -> str:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return str(data.get("source_pack") or "").strip()
    except Exception:
        return ""


def _manifest_resolved_pack_root(path: Path) -> Path:
    p = Path(path)
    # Normal extractor layout: <PACK>/06_MOD_LOADER_READY/ownership_manifest.json
    if p.parent.name.upper() == "06_MOD_LOADER_READY":
        return p.parent.parent
    return p.parent


def _reference_rows_from_pack_bytes(display_name: str, data: bytes, scratch_root: Path) -> List[Dict[str, Any]]:
    """Build the authoritative owner/component map directly from PCPACK bytes.

    This intentionally bypasses CSV input.  CSV files remain optional reports only; a
    missing/stale/broken INNER_APKF_FILES.csv can never stop a valid same-size rebuild.
    """
    scratch_root = Path(scratch_root)
    scratch_root.mkdir(parents=True, exist_ok=True)
    probe = probe_pack_bytes(display_name, data)
    rows: List[Dict[str, Any]] = []
    slices, _filtered = apkf_slices_from_probe(data, probe)
    pack_name = clean_name(Path(display_name).stem, "PACK")
    for source_slice in slices:
        parsed, _actions, _summary, error = extract_apkf_archive(
            source_slice.payload,
            label=source_slice.label,
            absolute_base=source_slice.absolute_base,
            out_root=scratch_root,
            output_layout="smart_browse",
            max_inner_mb=4096,
            write_payloads=False,
            source_pack_name=pack_name,
            source_pack_path=display_name,
            source_slice=source_slice,
            create_mod_loader_ready=False,
        )
        if error:
            raise ValueError(f"Could not parse owning APKF {source_slice.label}: {error}")
        rows.extend(parsed)

    # Tell resolver whether a flat 02_APKF_EXTRACTED_REAL_EXT filename is globally unique.
    # Unique flat files are the normal edit target; duplicate hash/type instances must use
    # owner-specific copies so one edit cannot accidentally target the wrong APKF.
    counts: Dict[Tuple[str, str], int] = {}
    for row in rows:
        ftype = str(row.get("file_type") or row.get("resource_type") or "").upper()
        h = str(row.get("filename_hash") or row.get("resource_hash") or row.get("hash") or "").upper()
        counts[(ftype, h)] = counts.get((ftype, h), 0) + 1
    for row in rows:
        ftype = str(row.get("file_type") or row.get("resource_type") or "").upper()
        h = str(row.get("filename_hash") or row.get("resource_hash") or row.get("hash") or "").upper()
        row["_same_hash_type_owner_count"] = counts.get((ftype, h), 1)
        row["_reference_map_source"] = "DIRECT_ORIGINAL_PCPACK_PARSE"
    return rows


def detect_extracted_pack_folder(extracted_folder: Path, original_pack: Optional[Path] = None) -> ExtractedFolderDetection:
    """Resolve the actual per-pack payload folder; CSV is never required.

    Priority:
    1) matching ownership_manifest.json (best modern extractor evidence),
    2) a directly selected payload folder,
    3) a nested pack-named payload folder,
    4) legacy INNER_APKF_FILES.csv only as a folder-location hint.

    The rebuild component map itself is always parsed directly from the clean original
    PCPACK, so CSV problems cannot block the build.
    """
    selected = Path(extracted_folder)
    if not selected.exists() or not selected.is_dir():
        raise FileNotFoundError(f"Extracted folder not found: {selected}")

    expected_stem = original_pack.stem.lower() if original_pack is not None else ""
    manifests = _case_insensitive_ownership_manifests(selected)
    manifest_matches: List[Path] = []
    for m in manifests:
        pack_name = _manifest_pack_name(m).lower()
        if not expected_stem or not pack_name or pack_name == expected_stem:
            manifest_matches.append(m)
    if manifest_matches:
        chosen = sorted(
            manifest_matches,
            key=lambda m: (0 if _manifest_pack_name(m).lower() == expected_stem and expected_stem else 1, len(m.parts), str(m).lower()),
        )[0]
        resolved = _manifest_resolved_pack_root(chosen)
        csvs = _case_insensitive_inner_csvs(resolved)
        optional_csv = str(csvs[0]) if csvs else ""
        notes = [
            "ownership_manifest.json found and matched",
            "CSV is optional and is not used as rebuild authority",
            "owner/component map will be parsed directly from the clean original PCPACK",
        ]
        return ExtractedFolderDetection(
            selected_folder=str(selected),
            resolved_folder=str(resolved),
            inner_csv=optional_csv,
            candidate_count=len(manifest_matches),
            status="OWNERSHIP_MANIFEST_FOUND_CSV_OPTIONAL",
            notes=notes,
        )

    if _looks_like_reportless_payload_extract(selected):
        csvs = _case_insensitive_inner_csvs(selected)
        return ExtractedFolderDetection(
            selected_folder=str(selected),
            resolved_folder=str(selected),
            inner_csv=str(csvs[0]) if csvs else "",
            candidate_count=len(csvs),
            status="PAYLOAD_FOLDER_FOUND_CSV_OPTIONAL",
            notes=[
                "payload extraction folders found",
                "CSV is optional and will not block rebuild",
                "owner/component map will be parsed directly from the clean original PCPACK",
            ],
        )

    # If the user selected a master output root, prefer a nested folder named for the pack.
    if expected_stem:
        nested: List[Path] = []
        try:
            for q in selected.rglob("*"):
                if q.is_dir() and q.name.lower() == expected_stem and _looks_like_reportless_payload_extract(q):
                    nested.append(q)
        except OSError:
            nested = []
        if nested:
            resolved = sorted(nested, key=lambda q: (len(q.parts), str(q).lower()))[0]
            csvs = _case_insensitive_inner_csvs(resolved)
            return ExtractedFolderDetection(
                selected_folder=str(selected),
                resolved_folder=str(resolved),
                inner_csv=str(csvs[0]) if csvs else "",
                candidate_count=len(nested),
                status="NESTED_PAYLOAD_FOLDER_FOUND_CSV_OPTIONAL",
                notes=[
                    "nested pack payload folder auto-detected",
                    "CSV is optional and will not block rebuild",
                    "owner/component map will be parsed directly from the clean original PCPACK",
                ],
            )

    # Legacy report folders can still help us locate an older extract, but their CSV data is
    # never trusted as the authoritative rebuild map in v5.2.149.
    csvs = _case_insensitive_inner_csvs(selected)
    if csvs:
        scored = sorted(
            csvs,
            key=lambda p: (_candidate_score_for_pack(p, selected, original_pack), -len(p.parts), str(p).lower()),
            reverse=True,
        )
        chosen = scored[0]
        resolved = chosen.parent.parent if chosen.parent.name.upper() == "00_REPORTS" else chosen.parent
        return ExtractedFolderDetection(
            selected_folder=str(selected),
            resolved_folder=str(resolved),
            inner_csv=str(chosen),
            candidate_count=len(csvs),
            status="LEGACY_CSV_FOLDER_HINT_ONLY",
            notes=[
                "legacy INNER_APKF_FILES.csv used only to locate the extracted pack folder",
                "CSV contents are NOT used as rebuild authority",
                "owner/component map will be parsed directly from the clean original PCPACK",
            ],
        )

    raise FileNotFoundError(
        "Could not find an extracted SM3 payload folder. Select the pack folder containing "
        "02_APKF_EXTRACTED_REAL_EXT, 05_TEX_DDS_EXPORT, or 06_MOD_LOADER_READY. "
        "INNER_APKF_FILES.csv is not required."
    )

def _find_inner_rows_csv(extracted_folder: Path, original_pack: Optional[Path] = None) -> Path:
    return Path(detect_extracted_pack_folder(extracted_folder, original_pack).inner_csv)


def _row_identity_candidates(row: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return normalized hash/name/extension hints for reportless extracted-file recovery."""
    h = str(row.get("filename_hash", "") or row.get("hash", "") or "").strip()
    if h and not h.lower().startswith("0x"):
        try:
            h = f"0x{int(h):08X}"
        except Exception:
            pass
    h = h.lower().replace("0x", "")
    name = clean_name(str(row.get("filename", "") or row.get("asset", "") or "").strip(), "resource").lower()
    ext = str(row.get("extension", "") or "").strip().lower()
    if not ext:
        ftype = str(row.get("file_type", "") or row.get("type", "") or "").upper()
        ext_map = {"ANIM": ".anim", "TEX": ".tex", "MESH": ".mesh", "MAT": ".mat", "SKEL": ".skel", "ASKL": ".askl", "SANM": ".sanm", "MORH": ".morh"}
        ext = ext_map.get(ftype, "")
    return h, name, ext


def _find_file_by_row_identity(row: Dict[str, Any], extracted_folder: Path) -> Optional[Path]:
    """Recover a payload path when regenerated/reference reports have no real_ext_file.

    Release Pack Extractor output can be intentionally reportless. When Rebuild Lab regenerates
    INNER_APKF_FILES.csv from the clean original pack with write_payloads=False, rows can have
    an empty real_ext_file. For ANIM repack, the staged extract still contains the changed file
    under 02_APKF_EXTRACTED_REAL_EXT, so recover by hash/name/extension instead of preserving
    original bytes.
    """
    hash_text, target_name, ext = _row_identity_candidates(row)
    if not hash_text and not target_name:
        return None
    candidates: List[Tuple[int, int, str, Path]] = []
    for paths in _build_file_index(extracted_folder).values():
        for q in paths:
            if not q.is_file():
                continue
            low_name = q.name.lower()
            low_path = str(q).replace("\\", "/").lower()
            if ext and not low_name.endswith(ext):
                continue
            hash_hit = bool(hash_text and hash_text in low_name.replace("0x", ""))
            name_hit = bool(target_name and target_name in low_name)
            if not (hash_hit or name_hit):
                continue
            preferred_folder = 0 if "/02_apkf_extracted_real_ext/" in low_path else 1
            # Hash matches are stronger than name-only matches; exact basename/name is strongest.
            match_score = 0 if hash_hit else 2
            if target_name and low_name.startswith((f"0x{hash_text}.{target_name}", f"{hash_text}.{target_name}")):
                match_score = -1
            candidates.append((preferred_folder, match_score, str(q).lower(), q))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], len(item[2]), item[2]))
    return candidates[0][3]


def _resolve_exported_path(row: Dict[str, Any], extracted_folder: Path, key: str) -> Optional[Path]:
    raw = str(row.get(key, "") or "").strip().strip('"')
    name = Path(raw.replace("\\", "/")).name if raw else ""
    # Reportless fallback rows are generated from a temporary reference extraction.
    # Prefer a same-named file inside the user's selected extraction folder first.
    if str(row.get("_prefer_selected_extract_folder") or "") == "1" and name:
        selected_hit = _find_file_by_basename(extracted_folder, name)
        if selected_hit and selected_hit.is_file():
            return selected_hit
    if raw:
        p = Path(raw)
        if p.exists() and p.is_file():
            return p
    # Sanitized reports may contain placeholders; recover by filename under selected extract folder.
    if name:
        selected_hit = _find_file_by_basename(extracted_folder, name)
        if selected_hit and selected_hit.is_file():
            return selected_hit
    # v0.8: release/reportless rebuild rows can have empty real_ext_file. Recover the
    # staged resource by 0x hash/name/extension so animation slot-preserve changes are
    # carried into the final PCPACK instead of producing a byte-identical original pack.
    return _find_file_by_row_identity(row, extracted_folder)


def _hash_name(row: Dict[str, Any]) -> str:
    h = str(row.get("filename_hash", "") or row.get("hash", "") or "").strip()
    if h and not h.lower().startswith("0x"):
        try:
            h = f"0x{int(h):08X}"
        except Exception:
            pass
    name = str(row.get("filename", "") or row.get("asset", "") or "").strip()
    return f"{h}.{clean_name(name, 'resource')}"


def _find_candidate_dds(row: Dict[str, Any], extracted_folder: Path) -> Optional[Path]:
    direct = _resolve_exported_path(row, extracted_folder, "tex_dds_export_file")
    if direct and direct.suffix.lower() == ".dds":
        return direct
    stem = _hash_name(row).lower()
    target_name = stem.split(".", 1)[-1].lower() if "." in stem else stem
    hash_text = str(row.get("filename_hash", "") or "").lower().replace("0x", "")

    # v0.7 performance fix: do not rglob for every TEX row. The file index is
    # built once per selected extract folder, then reused for all lookups. This
    # matters for MEGACITY where there can be 1k+ DDS candidates.
    all_paths: List[Path] = []
    for paths in _build_file_index(extracted_folder).values():
        for q in paths:
            if q.suffix.lower() == ".dds":
                all_paths.append(q)
    candidates = []
    for q in all_paths:
        low = q.name.lower()
        if hash_text and hash_text in low:
            candidates.append(q)
        elif target_name and target_name in low:
            candidates.append(q)
    return sorted(candidates, key=lambda q: (0 if hash_text and hash_text in q.name.lower() else 1, len(str(q)), str(q).lower()))[0] if candidates else None


def _canonical_texture_format(value: Any) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    aliases = {
        "BC1": "DXT1", "BC1_UNORM": "DXT1", "BC1_UNORM_SRGB": "DXT1", "DXT1/BC1": "DXT1", "DXT1_BC1": "DXT1",
        "DXT2": "DXT3", "BC2": "DXT3", "BC2_UNORM": "DXT3", "BC2_UNORM_SRGB": "DXT3", "DXT2/DXT3": "DXT3", "DXT3/BC2": "DXT3", "DXT3_BC2": "DXT3",
        "DXT4": "DXT5", "BC3": "DXT5", "BC3_UNORM": "DXT5", "BC3_UNORM_SRGB": "DXT5", "DXT4/DXT5": "DXT5", "DXT5/BC3": "DXT5", "DXT5_BC3": "DXT5",
        "ATI1": "BC4", "BC4U": "BC4", "BC4_UNORM": "BC4", "BC4_SNORM": "BC4",
        "ATI2": "BC5", "BC5U": "BC5", "BC5_UNORM": "BC5", "BC5_SNORM": "BC5",
        "R8": "L8", "R8_UNORM": "L8", "GRAY": "L8", "GREY": "L8", "L8/R8": "L8", "L8(50)": "L8", "L8 (50)": "L8",
        "RGBA32": "BGRA32", "BGRA/RGBA": "BGRA32", "BGRA32/A8R8G8B8(21)": "BGRA32", "BGRA32/A8R8G8B8 (21)": "BGRA32",
    }
    return aliases.get(text, text)


def _parse_dds_payload(path: Path) -> Tuple[Dict[str, Any], bytes]:
    """Parse DDS using the same safety concepts as the proven Tex Swapper route.

    This parser is intentionally metadata-only: it never converts pixels. It accepts the
    common SM3 target formats plus DX10/BC family labels so the Rebuild Lab can validate a
    candidate without weakening the target contract.
    """
    b = Path(path).read_bytes()
    if len(b) < 128 or b[:4] != b"DDS ":
        raise ValueError("not a DDS file")
    if struct.unpack_from("<I", b, 4)[0] != 124:
        raise ValueError("DDS header size is not 124 bytes")
    height = struct.unpack_from("<I", b, 12)[0]
    width = struct.unpack_from("<I", b, 16)[0]
    mips = struct.unpack_from("<I", b, 28)[0] or 1
    pf_flags = struct.unpack_from("<I", b, 80)[0]
    fourcc = b[84:88]
    rgbbits = struct.unpack_from("<I", b, 88)[0]
    header_size = 148 if fourcc == b"DX10" else 128
    if len(b) < header_size:
        raise ValueError("DDS DX10 header is truncated")

    fmt = "UNKNOWN"
    dxgi = None
    if fourcc in (b"DXT1", b"DXT2", b"DXT3", b"DXT4", b"DXT5"):
        fmt = _canonical_texture_format(fourcc.decode("ascii"))
    elif fourcc in (b"ATI1", b"BC4U", b"BC4S"):
        fmt = "BC4"
    elif fourcc in (b"ATI2", b"BC5U", b"BC5S"):
        fmt = "BC5"
    elif fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", b, 128)[0]
        dxgi_map = {
            28: "BGRA32", 29: "BGRA32",
            61: "L8",
            71: "DXT1", 72: "DXT1",
            74: "DXT3", 75: "DXT3",
            77: "DXT5", 78: "DXT5",
            80: "BC4", 81: "BC4",
            83: "BC5", 84: "BC5",
            95: "BC6H", 96: "BC6H",
            98: "BC7", 99: "BC7",
        }
        fmt = dxgi_map.get(dxgi, f"DXGI_{dxgi}")
    elif rgbbits == 32:
        fmt = "BGRA32"
    elif rgbbits == 8 or (pf_flags & 0x20000):
        fmt = "L8"

    payload = b[header_size:]
    return {
        "width": width,
        "height": height,
        "mips": mips,
        "format_kind": _canonical_texture_format(fmt),
        "header_size": header_size,
        "payload_size": len(payload),
        "fourcc": fourcc.decode("ascii", "replace"),
        "dxgi_format": dxgi,
    }, payload

def _tex_payload_expected(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "width": _parse_int_maybe(row.get("tex_width") or row.get("width")) or 0,
        "height": _parse_int_maybe(row.get("tex_height") or row.get("height")) or 0,
        "mips": _parse_int_maybe(row.get("tex_mips") or row.get("mips")) or 1,
        "format_kind": str(row.get("tex_format_guess") or row.get("format_kind") or row.get("tex_format") or "").replace("/BC1", "").replace("/BC3", "").strip(),
        "component1_size": None,
    }


def _looks_like_reportless_payload_extract(root: Path) -> bool:
    root = Path(root)
    checks = [
        root / "02_APKF_EXTRACTED_REAL_EXT",
        root / "05_TEX_DDS_EXPORT",
        root / "01_OUTER_PAYLOADS",
    ]
    if any(c.exists() and c.is_dir() for c in checks):
        return True
    try:
        for p in root.rglob("02_APKF_EXTRACTED_REAL_EXT"):
            if p.is_dir():
                return True
    except OSError:
        pass
    return False


def _mark_reportless_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        nr = dict(r)
        nr["_prefer_selected_extract_folder"] = "1"
        if nr.get("real_ext_file"):
            nr["real_ext_file_reference_from_original_pack"] = nr.get("real_ext_file", "")
        if nr.get("tex_dds_export_file"):
            nr["tex_dds_export_file_reference_from_original_pack"] = nr.get("tex_dds_export_file", "")
        out.append(nr)
    return out




def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row_owner_key(row: Dict[str, Any]) -> str:
    """Stable identity for one resource inside one owning APKF.

    Do not identify a resource by hash/name alone: SM3 legitimately duplicates resources
    across different APKFs. The extractor already records enough ownership metadata to keep
    those instances separate during rebuild.
    """
    def keep_zero(value: Any) -> str:
        return "" if value is None else str(value)

    parts = [
        keep_zero(row.get("source_apkf_absolute_base")),
        str(row.get("source_archive_folder") or row.get("parent_apkf_name") or ""),
        keep_zero(row.get("parent_outer_index")),
        str(row.get("parent_outer_hash") or row.get("parent_apkf_hash") or ""),
        keep_zero(row.get("parent_outer_type")),
        keep_zero(row.get("global_index")),
        str(row.get("file_type") or row.get("resource_type") or row.get("type") or "").upper(),
        str(row.get("filename_hash") or row.get("resource_hash") or row.get("hash") or "").upper(),
    ]
    return "|".join(parts)


def _row_owner_report(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "owner_key": _row_owner_key(row),
        "source_apkf_absolute_base": row.get("source_apkf_absolute_base", ""),
        "source_archive_folder": row.get("source_archive_folder", ""),
        "parent_outer_index": row.get("parent_outer_index", ""),
        "parent_outer_hash": row.get("parent_outer_hash", row.get("parent_apkf_hash", "")),
        "parent_outer_type": row.get("parent_outer_type", ""),
        "global_index": row.get("global_index", ""),
        "file_type": str(row.get("file_type") or row.get("resource_type") or row.get("type") or "").upper(),
        "filename_hash": row.get("filename_hash", row.get("resource_hash", row.get("hash", ""))),
        "filename": row.get("filename", row.get("resource_name", row.get("asset", ""))),
    }


def _combined_original_bytes(original_bytes: bytes, ranges: List[Tuple[int, int, int]]) -> bytes:
    return b"".join(original_bytes[s:e] for _ci, s, e in ranges)


def _dedupe_paths(paths: List[Path]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for p in paths:
        try:
            key = str(Path(p).resolve()).lower()
        except Exception:
            key = str(Path(p)).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(p))
    return out


def _identity_file_candidates(row: Dict[str, Any], extracted_folder: Path, suffix: str = "") -> List[Path]:
    """Resolve extracted candidates by strongest available identity first.

    A real SM3 filename hash is stronger than the readable asset name.  The old fallback
    mixed hash and substring-name hits, so `itm_meleeicon_material` also matched
    `itm_meleeicon_material01` and could create false ambiguity in an untouched extract.
    If any exact hash-named candidates exist, only those are returned.  Name matching is
    used only when the row genuinely has no usable hash-named candidate.
    """
    hash_text, target_name, ext = _row_identity_candidates(row)
    wanted_suffix = suffix.lower() if suffix else ext.lower()
    hash_candidates: List[Path] = []
    name_candidates: List[Path] = []
    hash_text = str(hash_text or "").lower().replace("0x", "")
    hash_token = f"0x{hash_text}" if hash_text else ""
    for paths in _build_file_index(extracted_folder).values():
        for q in paths:
            if not q.is_file():
                continue
            low = q.name.lower()
            if wanted_suffix and not low.endswith(wanted_suffix):
                continue
            # Extractor/resource filenames are standardized as 0xXXXXXXXX.<name>.<ext>.
            # Require the full 8-digit token instead of arbitrary substring overlap.
            if hash_token and hash_token in low:
                hash_candidates.append(q)
                continue
            if target_name and target_name in low:
                name_candidates.append(q)
    if hash_candidates:
        return _dedupe_paths(hash_candidates)
    return _dedupe_paths(name_candidates)


def _all_candidate_files_identical(candidates: List[Path]) -> bool:
    candidates = _dedupe_paths(candidates)
    if len(candidates) < 2:
        return bool(candidates)
    try:
        first_size = candidates[0].stat().st_size
        first_sha = sha256_file(candidates[0])
        for q in candidates[1:]:
            if q.stat().st_size != first_size or sha256_file(q) != first_sha:
                return False
        return True
    except OSError:
        return False


def _resolve_owner_aware_path(row: Dict[str, Any], extracted_folder: Path, key: str, suffix: str = "") -> Tuple[Optional[Path], str, int]:
    """Resolve a replacement deterministically without treating harmless copies as errors.

    The main editable extraction (02_APKF_EXTRACTED_REAL_EXT) wins when hash/type is unique
    in the pack.  Duplicate resource identities require an owner-specific archive copy.
    Multiple physical copies are harmless when their bytes are identical.
    """
    root = Path(extracted_folder)
    raw = str(row.get(key, "") or "").strip().strip('"')
    basename = Path(raw.replace("\\", "/")).name if raw else ""
    candidates: List[Path] = []
    if basename:
        candidates.extend(_build_file_index(root).get(basename.lower()) or [])
    if not candidates:
        candidates.extend(_identity_file_candidates(row, root, suffix=suffix))
    if raw:
        direct = Path(raw)
        if direct.exists() and direct.is_file() and (not suffix or direct.suffix.lower() == suffix.lower()):
            candidates.append(direct)
    candidates = [q for q in _dedupe_paths(candidates) if q.is_file() and (not suffix or q.suffix.lower() == suffix.lower())]
    if not candidates:
        return None, "NOT_FOUND", 0

    duplicate_owner_count = _parse_int_maybe(row.get("_same_hash_type_owner_count")) or 1
    editor_hits = [q for q in candidates if "/02_apkf_extracted_real_ext/" in str(q).replace("\\", "/").lower()]
    if duplicate_owner_count <= 1:
        if len(editor_hits) == 1:
            return editor_hits[0], "PRIMARY_EXTRACTED_REAL_EXT", len(candidates)
        if len(editor_hits) > 1 and _all_candidate_files_identical(editor_hits):
            return sorted(editor_hits, key=lambda q: (len(str(q)), str(q).lower()))[0], "PRIMARY_IDENTICAL_EXTRACT_COPIES", len(candidates)

    archive = str(row.get("source_archive_folder") or "").strip().lower()
    if archive:
        owner_hits = [q for q in candidates if f"/{archive}/" in str(q).replace("\\", "/").lower()]
        if len(owner_hits) == 1:
            return owner_hits[0], "OWNER_SPECIFIC", len(candidates)
        if len(owner_hits) > 1:
            if _all_candidate_files_identical(owner_hits):
                pick = sorted(owner_hits, key=lambda q: (len(str(q)), str(q).lower()))[0]
                return pick, "OWNER_SPECIFIC_IDENTICAL_COPIES", len(candidates)
            return None, "AMBIGUOUS_OWNER_SPECIFIC", len(owner_hits)

    if len(candidates) == 1:
        return candidates[0], "UNIQUE_FLAT", 1
    if _all_candidate_files_identical(candidates):
        pick = sorted(candidates, key=lambda q: (len(str(q)), str(q).lower()))[0]
        return pick, "IDENTICAL_DUPLICATE_COPIES", len(candidates)
    return None, "AMBIGUOUS_MULTIPLE_CANDIDATES", len(candidates)

def _candidate_dds_owner_aware(row: Dict[str, Any], extracted_folder: Path) -> Tuple[Optional[Path], str, int]:
    direct, status, count = _resolve_owner_aware_path(row, extracted_folder, "tex_dds_export_file", suffix=".dds")
    if direct is not None or status.startswith("AMBIGUOUS"):
        return direct, status, count
    # Some reportless folders have no tex_dds_export_file value. Recover by hash/name, but
    # still require an unambiguous or owner-specific result.
    candidates = _identity_file_candidates(row, extracted_folder, suffix=".dds")
    if not candidates:
        return None, "NOT_FOUND", 0
    archive = str(row.get("source_archive_folder") or "").strip().lower()
    if archive:
        owner_hits = [q for q in candidates if f"/{archive}/" in str(q).replace("\\", "/").lower()]
        if len(owner_hits) == 1:
            return owner_hits[0], "OWNER_SPECIFIC_IDENTITY", len(candidates)
        if len(owner_hits) > 1:
            if _all_candidate_files_identical(owner_hits):
                pick = sorted(owner_hits, key=lambda q: (len(str(q)), str(q).lower()))[0]
                return pick, "OWNER_SPECIFIC_IDENTICAL_DDS_COPIES", len(candidates)
            return None, "AMBIGUOUS_OWNER_SPECIFIC", len(owner_hits)
    if len(candidates) == 1:
        return candidates[0], "UNIQUE_IDENTITY", 1
    if _all_candidate_files_identical(candidates):
        pick = sorted(candidates, key=lambda q: (len(str(q)), str(q).lower()))[0]
        return pick, "IDENTICAL_DDS_COPIES", len(candidates)
    return None, "AMBIGUOUS_MULTIPLE_CANDIDATES", len(candidates)


def _expected_tex_format(row: Dict[str, Any]) -> str:
    raw = row.get("tex_format_guess") or row.get("format_kind") or row.get("tex_format") or ""
    return _canonical_texture_format(str(raw).replace("/BC1", "").replace("/BC2", "").replace("/BC3", ""))


def _tex_format_from_sm3_raw(fmt_raw: int) -> str:
    """Canonicalize the format value stored in the original SM3 TEX component0."""
    fmt_raw = int(fmt_raw) & 0xFFFFFFFF
    if fmt_raw == 21:
        return "BGRA32"
    if fmt_raw == 50:
        return "L8"
    try:
        raw = struct.pack("<I", fmt_raw)
        if all(32 <= b < 127 for b in raw):
            return _canonical_texture_format(raw.decode("ascii", errors="replace"))
    except Exception:
        pass
    return _canonical_texture_format(f"0x{fmt_raw:08X}")


def _tex_expected_from_original_component0(
    original_bytes: bytes,
    ranges: List[Tuple[int, int, int]],
    row: Dict[str, Any],
) -> Dict[str, Any]:
    """Read the TEX contract from the clean PCPACK itself, not old inferred CSV metadata.

    The modern Tex Swapper proved the native SM3 component0/IMG descriptor fields at
    offsets 0x18/0x1C/0x24/0x28.  Regenerated legacy reports can conservatively infer a
    single mip or labels such as DXT5_BC3, which is useful for browsing but is not strong
    enough to reject a rebuild.  The original component0 is the authoritative target.
    """
    fallback = _tex_payload_expected(row)
    comp0 = next(((s, e) for ci, s, e in ranges if ci == 0), None)
    if not comp0:
        fallback["source"] = "REPORT_FALLBACK_NO_COMPONENT0"
        fallback["format_kind"] = _expected_tex_format(row)
        return fallback
    start, end = comp0
    blob = original_bytes[start:end]
    if len(blob) < 0x2C:
        fallback["source"] = "REPORT_FALLBACK_SHORT_COMPONENT0"
        fallback["format_kind"] = _expected_tex_format(row)
        return fallback
    try:
        width = struct.unpack_from("<I", blob, 0x18)[0]
        height = struct.unpack_from("<I", blob, 0x1C)[0]
        mips = struct.unpack_from("<I", blob, 0x24)[0] or 1
        fmt_raw = struct.unpack_from("<I", blob, 0x28)[0]
        if not (0 < width <= 16384 and 0 < height <= 16384 and 0 < mips <= 32):
            raise ValueError("implausible native TEX descriptor")
        return {
            "width": width,
            "height": height,
            "mips": mips,
            "format_kind": _tex_format_from_sm3_raw(fmt_raw),
            "format_raw": fmt_raw,
            "component1_size": None,
            "source": "ORIGINAL_PCPACK_COMPONENT0",
        }
    except Exception:
        fallback["source"] = "REPORT_FALLBACK_COMPONENT0_PARSE_FAILED"
        fallback["format_kind"] = _expected_tex_format(row)
        return fallback


def _plan_report_row(plan: Dict[str, Any], status: str = "PLANNED") -> Dict[str, Any]:
    return {
        "row_index": plan.get("row_index"),
        "status": status,
        "resource": plan.get("resource"),
        "file_type": plan.get("file_type"),
        "owner_key": plan.get("owner_key"),
        "source_path": plan.get("source_path", ""),
        "source_resolution": plan.get("source_resolution", ""),
        "original_sha256": plan.get("original_sha256", ""),
        "replacement_sha256": plan.get("replacement_sha256", ""),
        "write_count": len(plan.get("writes") or []),
        "bytes_to_write": sum(w[2] - w[1] for w in plan.get("writes") or []),
        "component_ranges": " | ".join(f"c{ci}:0x{s:X}-0x{e:X}" for ci, s, e, _blob in plan.get("writes") or []),
    }


def _build_repack_v2_plan(original_bytes: bytes, rows: List[Dict[str, Any]], extracted_folder: Path) -> Dict[str, Any]:
    """Build the complete changed-resource plan before touching a PCPACK byte."""
    root = Path(extracted_folder)
    plans: List[Dict[str, Any]] = []
    resource_actions: List[Dict[str, Any]] = []
    tex_actions: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    source_usage: Dict[str, List[Dict[str, Any]]] = {}
    tex_seen = 0
    tex_preserved = 0

    for idx, row in enumerate(rows):
        ftype = str(row.get("file_type", "") or row.get("resource_type", "") or row.get("type", "") or "").upper()
        ranges = _row_component_ranges(row, len(original_bytes))
        label = _hash_name(row)
        owner = _row_owner_key(row)
        owner_info = _row_owner_report(row)
        if not ranges:
            blocked.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "reason": "no_valid_component_ranges_in_report"})
            continue

        if ftype == "TEX":
            tex_seen += 1
            comp1 = next(((ci, s, e) for ci, s, e in ranges if ci == 1), None)
            if not comp1:
                tex_preserved += 1
                tex_actions.append({"row_index": idx, "resource": label, **owner_info, "action": "PRESERVE_ORIGINAL_TEX", "reason": "no_component1_range"})
                continue
            ci, start, end = comp1
            original_payload = original_bytes[start:end]
            dds, resolve_status, candidate_count = _candidate_dds_owner_aware(row, root)
            if dds is None:
                tex_preserved += 1
                reason = "no_safe_dds_payload_found" if resolve_status == "NOT_FOUND" else resolve_status.lower()
                if resolve_status.startswith("AMBIGUOUS"):
                    blocked.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "reason": reason, "candidate_count": candidate_count})
                else:
                    tex_actions.append({"row_index": idx, "resource": label, **owner_info, "action": "PRESERVE_ORIGINAL_TEX", "reason": reason})
                continue
            try:
                info, payload = _parse_dds_payload(dds)
            except Exception as exc:
                tex_preserved += 1
                tex_actions.append({"row_index": idx, "resource": label, **owner_info, "dds": str(dds), "action": "PRESERVE_ORIGINAL_TEX", "reason": f"dds_parse_failed:{exc}"})
                continue

            # An untouched exported DDS is never a rebuild problem. Older browse reports can
            # disagree on DXT2/3 vs DXT4/5 labels even when the actual payload is byte-exact.
            # Compare payload bytes first; only validate metadata when a real edit exists.
            if payload == original_payload:
                tex_preserved += 1
                usage_key = str(dds.resolve()).lower()
                source_usage.setdefault(usage_key, []).append({
                    "row_index": idx, "owner_key": owner, "resource": label, "file_type": ftype,
                    "source_path": str(dds), "source_resolution": resolve_status,
                    "original_sha256": _sha256_bytes(original_payload), "replacement_sha256": _sha256_bytes(payload),
                    "changed": False,
                })
                tex_actions.append({"row_index": idx, "resource": label, **owner_info, "dds": str(dds), "action": "PRESERVE_ORIGINAL_TEX", "reason": "dds_payload_byte_identical_to_original", "source_resolution": resolve_status})
                continue

            expected = _tex_expected_from_original_component0(original_bytes, ranges, row)
            problems: List[str] = []
            if expected.get("width") and info["width"] != expected["width"]:
                problems.append(f"width {info['width']} != {expected['width']}")
            if expected.get("height") and info["height"] != expected["height"]:
                problems.append(f"height {info['height']} != {expected['height']}")
            if expected.get("mips") and info["mips"] != expected["mips"]:
                problems.append(f"mips {info['mips']} != {expected['mips']}")
            expected_fmt = _canonical_texture_format(expected.get("format_kind"))
            actual_fmt = _canonical_texture_format(info.get("format_kind"))
            if expected_fmt and expected_fmt != actual_fmt:
                problems.append(f"format {actual_fmt} != {expected_fmt}")
            if len(payload) != (end - start):
                problems.append(f"payload {len(payload)} != component1 {end-start}")
            if problems:
                tex_preserved += 1
                blocked.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "dds": str(dds), "reason": "; ".join(problems)})
                continue

            usage_key = str(dds.resolve()).lower()
            source_usage.setdefault(usage_key, []).append({
                "row_index": idx, "owner_key": owner, "resource": label, "file_type": ftype,
                "source_path": str(dds), "source_resolution": resolve_status,
                "original_sha256": _sha256_bytes(original_payload), "replacement_sha256": _sha256_bytes(payload),
                "changed": True,
            })
            plan = {
                "row_index": idx, "resource": label, "file_type": ftype, "owner_key": owner,
                "source_path": str(dds), "source_resolution": resolve_status,
                "original_sha256": _sha256_bytes(original_payload), "replacement_sha256": _sha256_bytes(payload),
                "writes": [(ci, start, end, payload)], "kind": "TEX_DDS_COMPONENT1",
            }
            plans.append(plan)
            tex_actions.append({"row_index": idx, "resource": label, **owner_info, "dds": str(dds), "action": "PLAN_TEX_COMPONENT1_REPLACEMENT", "component1_start": f"0x{start:X}", "component1_end": f"0x{end:X}", "payload_size": len(payload), "source_resolution": resolve_status})
            continue

        real, resolve_status, candidate_count = _resolve_owner_aware_path(row, root, "real_ext_file")
        if real is None:
            if resolve_status.startswith("AMBIGUOUS"):
                blocked.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "reason": resolve_status.lower(), "candidate_count": candidate_count})
            else:
                resource_actions.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "action": "PRESERVE_ORIGINAL", "reason": "real_ext_file_missing"})
            continue
        data, read_status = _try_read_existing_file(real)
        if data is None:
            resource_actions.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "file": str(real), "action": "PRESERVE_ORIGINAL", "reason": read_status})
            continue
        original_combined = _combined_original_bytes(original_bytes, ranges)
        expected_size = len(original_combined)
        if len(data) != expected_size:
            blocked.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "file": str(real), "reason": f"size_changed {len(data)} != {expected_size}; generic size-changing rebuild still blocked"})
            continue

        usage_key = str(real.resolve()).lower()
        source_usage.setdefault(usage_key, []).append({
            "row_index": idx, "owner_key": owner, "resource": label, "file_type": ftype,
            "source_path": str(real), "source_resolution": resolve_status,
            "original_sha256": _sha256_bytes(original_combined), "replacement_sha256": _sha256_bytes(data),
            "changed": data != original_combined,
        })
        if data == original_combined:
            resource_actions.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "file": str(real), "action": "PRESERVE_ORIGINAL", "reason": "extracted_file_byte_identical_to_original", "source_resolution": resolve_status})
            continue

        writes = []
        pos = 0
        for ci, s, e in ranges:
            n = e - s
            writes.append((ci, s, e, data[pos:pos+n]))
            pos += n
        plan = {
            "row_index": idx, "resource": label, "file_type": ftype, "owner_key": owner,
            "source_path": str(real), "source_resolution": resolve_status,
            "original_sha256": _sha256_bytes(original_combined), "replacement_sha256": _sha256_bytes(data),
            "writes": writes, "kind": "RESOURCE_COMPONENTS",
        }
        plans.append(plan)
        resource_actions.append({"row_index": idx, "resource": label, "file_type": ftype, **owner_info, "file": str(real), "action": "PLAN_CHANGED_RESOURCE", "bytes": len(data), "source_resolution": resolve_status})

    blocked_rows = {int(b["row_index"]) for b in blocked if str(b.get("row_index", "")).isdigit()}

    # If one flat export file is shared by multiple owners whose ORIGINAL bytes differ,
    # a changed file cannot tell us which owner was intended. Never guess.
    for usage_path, uses in source_usage.items():
        changed_uses = [u for u in uses if u.get("changed")]
        owner_keys = {u.get("owner_key") for u in uses}
        original_hashes = {u.get("original_sha256") for u in uses}
        if changed_uses and len(owner_keys) > 1 and len(original_hashes) > 1:
            for u in changed_uses:
                ri = int(u["row_index"])
                if ri not in blocked_rows:
                    blocked.append({
                        "row_index": ri, "resource": u.get("resource"), "file_type": u.get("file_type"),
                        "owner_key": u.get("owner_key"), "file": u.get("source_path"),
                        "reason": "ambiguous_shared_flat_export_across_owners_with_different_original_bytes; owner-specific extracted path required",
                    })
                    blocked_rows.add(ri)

    plans = [p for p in plans if int(p["row_index"]) not in blocked_rows]

    # Duplicate owner identities must agree exactly. If not, the map itself is unsafe.
    by_owner: Dict[str, List[Dict[str, Any]]] = {}
    for plan in plans:
        by_owner.setdefault(plan["owner_key"], []).append(plan)
    for owner_key, same_owner in by_owner.items():
        if len(same_owner) <= 1:
            continue
        signatures = {
            tuple((ci, s, e, _sha256_bytes(blob)) for ci, s, e, blob in p["writes"])
            for p in same_owner
        }
        if len(signatures) > 1:
            for plan in same_owner:
                ri = int(plan["row_index"])
                blocked.append({"row_index": ri, "resource": plan["resource"], "file_type": plan["file_type"], "owner_key": owner_key, "reason": "duplicate_owner_identity_with_conflicting_write_plan"})
                blocked_rows.add(ri)
        else:
            # Exact duplicate metadata row: keep the first deterministic plan only.
            for duplicate in same_owner[1:]:
                duplicate["dedupe_exact_owner_plan"] = True

    plans = [p for p in plans if int(p["row_index"]) not in blocked_rows and not p.get("dedupe_exact_owner_plan")]

    # Preflight every component write and reject partial overlaps before changing bytes.
    write_refs: List[Tuple[int, int, int, int, bytes]] = []
    for plan in plans:
        for ci, s, e, blob in plan["writes"]:
            write_refs.append((s, e, int(plan["row_index"]), ci, blob))
    write_refs.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    conflict_rows = set()
    active: List[Tuple[int, int, int, int, bytes]] = []
    for cur in write_refs:
        s, e, ri, ci, blob = cur
        active = [a for a in active if a[1] > s]
        for prev in active:
            ps, pe, pri, pci, pblob = prev
            if s < pe and ps < e:
                exact_same_write = s == ps and e == pe and blob == pblob
                if not exact_same_write:
                    conflict_rows.update((ri, pri))
        active.append(cur)
    if conflict_rows:
        for plan in plans:
            ri = int(plan["row_index"])
            if ri in conflict_rows:
                blocked.append({"row_index": ri, "resource": plan["resource"], "file_type": plan["file_type"], "owner_key": plan["owner_key"], "reason": "planned_component_range_overlaps_another_changed_resource"})
                blocked_rows.add(ri)
    plans = [p for p in plans if int(p["row_index"]) not in blocked_rows]

    # Build one deterministic unique write list. Exact same range+bytes is harmless and is
    # emitted once even if two identical metadata rows describe it.
    unique_writes: List[Tuple[int, int, bytes, int, int]] = []
    seen_write = set()
    for plan in sorted(plans, key=lambda p: (min(w[1] for w in p["writes"]), p["owner_key"], p["row_index"])):
        for ci, s, e, blob in plan["writes"]:
            sig = (s, e, _sha256_bytes(blob))
            if sig in seen_write:
                continue
            seen_write.add(sig)
            unique_writes.append((s, e, blob, int(plan["row_index"]), ci))
    unique_writes.sort(key=lambda w: (w[0], w[1], w[3], w[4]))

    usage_rows: List[Dict[str, Any]] = []
    for _path, uses in sorted(source_usage.items()):
        for u in uses:
            usage_rows.append(dict(u))

    return {
        "plans": plans,
        "unique_writes": unique_writes,
        "resource_actions": resource_actions,
        "tex_actions": tex_actions,
        "blocked": blocked,
        "source_usage": usage_rows,
        "tex_seen": tex_seen,
        "tex_preserved": tex_preserved,
    }


def _apply_unique_writes(original_bytes: bytes, unique_writes: List[Tuple[int, int, bytes, int, int]]) -> bytes:
    rebuilt = bytearray(original_bytes)
    for start, end, blob, _row_index, _ci in unique_writes:
        if len(blob) != end - start:
            raise ValueError(f"Internal rebuild plan size mismatch at 0x{start:X}-0x{end:X}")
        rebuilt[start:end] = blob
    return bytes(rebuilt)


def _verify_planned_ranges_only(original_bytes: bytes, rebuilt_bytes: bytes, unique_writes: List[Tuple[int, int, bytes, int, int]]) -> Dict[str, Any]:
    if len(original_bytes) != len(rebuilt_bytes):
        return {"same_size": False, "planned_writes_match": False, "outside_planned_ranges_identical": False, "first_unexpected_diff": "size_changed"}
    cursor = 0
    first_unexpected = ""
    planned_match = True
    outside_same = True
    for start, end, blob, _ri, _ci in sorted(unique_writes, key=lambda w: (w[0], w[1])):
        if original_bytes[cursor:start] != rebuilt_bytes[cursor:start]:
            outside_same = False
            if not first_unexpected:
                for off in range(cursor, start):
                    if original_bytes[off] != rebuilt_bytes[off]:
                        first_unexpected = f"0x{off:X}"
                        break
        if rebuilt_bytes[start:end] != blob:
            planned_match = False
        cursor = max(cursor, end)
    if original_bytes[cursor:] != rebuilt_bytes[cursor:]:
        outside_same = False
        if not first_unexpected:
            for off in range(cursor, len(original_bytes)):
                if original_bytes[off] != rebuilt_bytes[off]:
                    first_unexpected = f"0x{off:X}"
                    break
    return {
        "same_size": True,
        "planned_writes_match": planned_match,
        "outside_planned_ranges_identical": outside_same,
        "first_unexpected_diff": first_unexpected,
    }


def _inner_structure_signature(row: Dict[str, Any]) -> Tuple[Any, ...]:
    comp_count = _parse_int_maybe(row.get("component_count")) or 0
    component_shape = []
    for ci in range(comp_count):
        component_shape.append((
            str(row.get(f"component{ci}_absolute_start_in_pcpack") or "").upper(),
            str(row.get(f"component{ci}_absolute_end_in_pcpack") or "").upper(),
            str(row.get(f"component{ci}_size") or ""),
        ))
    return (
        str(row.get("source_apkf_absolute_base") or "").upper(),
        str(row.get("source_archive_folder") or "").lower(),
        str(row.get("parent_outer_index") or ""),
        str(row.get("parent_outer_hash") or row.get("parent_apkf_hash") or "").upper(),
        str(row.get("parent_outer_type") or "").upper(),
        str(row.get("global_index") or ""),
        str(row.get("file_type") or row.get("resource_type") or row.get("type") or "").upper(),
        str(row.get("filename_hash") or row.get("resource_hash") or row.get("hash") or "").upper(),
        str(row.get("filename") or row.get("resource_name") or row.get("asset") or ""),
        comp_count,
        tuple(component_shape),
    )


def _verify_rebuilt_inner_structure(rebuilt_name: str, rebuilt_bytes: bytes, original_rows: List[Dict[str, Any]], verification_root: Path) -> Dict[str, Any]:
    """Reparse rebuilt bytes directly; no CSV is required for verification."""
    try:
        rebuilt_rows = _reference_rows_from_pack_bytes(rebuilt_name, rebuilt_bytes, verification_root / "DIRECT_REPARSE")
        original_sig = sorted((_inner_structure_signature(r) for r in original_rows), key=repr)
        rebuilt_sig = sorted((_inner_structure_signature(r) for r in rebuilt_rows), key=repr)
        same = original_sig == rebuilt_sig
        return {
            "status": "PASS" if same else "REVIEW",
            "same_inner_structure": same,
            "original_inner_rows": len(original_rows),
            "rebuilt_inner_rows": len(rebuilt_rows),
            "verification_csv": "",
            "verification_method": "DIRECT_PCPACK_PARSE_NO_CSV",
        }
    except Exception as exc:
        return {
            "status": "REVIEW",
            "same_inner_structure": False,
            "original_inner_rows": len(original_rows),
            "rebuilt_inner_rows": -1,
            "verification_csv": "",
            "verification_method": "DIRECT_PCPACK_PARSE_NO_CSV",
            "error": f"{type(exc).__name__}: {exc}",
        }

def rebuild_from_full_extract_tex_safe(original_pack: Path, extracted_folder: Path, output_root: Path) -> FullExtractRebuildResult:
    """Layout-faithful same-size PCPACK repack engine v2.

    UI/workflow is unchanged. Internally this now builds a complete owner-aware changed-file
    plan first, rejects ambiguous/overlapping mappings, writes only changed component ranges,
    preserves every byte outside those ranges, and reparses the final PCPACK to verify the
    inner APKF/resource/component structure still matches the original map.

    Generic size-changing resource repack remains intentionally blocked here.
    """
    original_pack = Path(original_pack)
    selected_extracted_folder = Path(extracted_folder)
    extracted_folder = selected_extracted_folder
    output_root = Path(output_root)
    if not original_pack.exists() or not original_pack.is_file():
        raise FileNotFoundError(f"Original PCPACK not found: {original_pack}")
    if not extracted_folder.exists() or not extracted_folder.is_dir():
        raise FileNotFoundError(f"Extracted pack folder not found: {extracted_folder}")

    original_bytes = original_pack.read_bytes()
    probe = probe_pack_bytes(original_pack.name, original_bytes)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_paths = os.environ.get("SM3_SHORT_REBUILD_PATHS") == "1" or len(str(output_root)) > 90
    workspace = output_root / (f"RB_{timestamp[-6:]}" if short_paths else f"{original_pack.stem}_FULL_EXTRACT_LAYOUT_FAITHFUL_REBUILD_{timestamp}")
    reports = workspace / ("R" if short_paths else "00_FULL_EXTRACT_REBUILD_REPORTS")
    out_dir = workspace / ("O" if short_paths else "02_REBUILD_OUTPUT")
    reports.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    detection = detect_extracted_pack_folder(extracted_folder, original_pack)
    extracted_folder = Path(detection.resolved_folder)
    # v5.2.149: CSV is deliberately NOT an input to the build. The clean original PCPACK
    # is the authority for owning APKFs, resource identity, and absolute component ranges.
    reference_root = workspace / ("REF" if short_paths else "00_DIRECT_REFERENCE_MAP_FROM_ORIGINAL_PCPACK")
    rows = _reference_rows_from_pack_bytes(original_pack.name, original_bytes, reference_root)
    reportless_fallback_used = not bool(detection.inner_csv)

    write_json(reports / "FULL_EXTRACT_FOLDER_DETECTION.json", asdict(detection))
    (reports / "FULL_EXTRACT_FOLDER_DETECTION.txt").write_text(
        "FULL EXTRACT FOLDER DETECTION\n============================\n\n"
        f"Selected folder: {detection.selected_folder}\nResolved per-pack folder: {detection.resolved_folder}\n"
        f"Optional legacy CSV: {detection.inner_csv or 'NONE / NOT REQUIRED'}\nCandidate count: {detection.candidate_count}\nStatus: {detection.status}\n"
        "Notes:\n- " + "\n- ".join(detection.notes) + "\n",
        encoding="utf-8",
    )

    plan_info = _build_repack_v2_plan(original_bytes, rows, extracted_folder)
    plans: List[Dict[str, Any]] = plan_info["plans"]
    unique_writes = plan_info["unique_writes"]
    resource_actions = plan_info["resource_actions"]
    tex_actions = plan_info["tex_actions"]
    blocked = plan_info["blocked"]
    rebuilt_bytes = _apply_unique_writes(original_bytes, unique_writes)

    rebuilt_name = f"{original_pack.stem}_REBUILT_FULL_EXTRACT_LAYOUT_FAITHFUL.PCPACK"
    rebuilt_path = out_dir / rebuilt_name
    rebuilt_path.write_bytes(rebuilt_bytes)

    rebuilt_probe = probe_pack_bytes(rebuilt_name, rebuilt_bytes)
    same_size = len(original_bytes) == len(rebuilt_bytes)
    same_route = probe.route == rebuilt_probe.route
    original_outer_shape = [(r.hash_value, r.type_id, r.data_offset, r.data_size) for r in probe.outer_rows]
    rebuilt_outer_shape = [(r.hash_value, r.type_id, r.data_offset, r.data_size) for r in rebuilt_probe.outer_rows]
    same_outer_shape = original_outer_shape == rebuilt_outer_shape
    marker_info_same = _marker_count_map(original_bytes) == _marker_count_map(rebuilt_bytes)
    header_4096_identical = original_bytes[:4096] == rebuilt_bytes[:4096]
    range_verify = _verify_planned_ranges_only(original_bytes, rebuilt_bytes, unique_writes)
    inner_verify_root = reports / "REPACK_V2_REPARSE_VERIFY"
    inner_verify = _verify_rebuilt_inner_structure(rebuilt_name, rebuilt_bytes, rows, inner_verify_root)

    applied_plan_rows = {_p["row_index"] for _p in plans}
    tex_replaced = sum(1 for p in plans if p.get("kind") == "TEX_DDS_COMPONENT1")
    resources_replaced = len(plans)
    tex_seen = int(plan_info["tex_seen"])
    tex_preserved = int(plan_info["tex_preserved"])

    structural_pass = all([
        same_size,
        same_route,
        same_outer_shape,
        bool(range_verify.get("planned_writes_match")),
        bool(range_verify.get("outside_planned_ranges_identical")),
        bool(inner_verify.get("same_inner_structure")),
    ])
    if blocked:
        verdict = "REVIEW_FULL_EXTRACT_REBUILD"
    elif not structural_pass:
        verdict = "REVIEW_FULL_EXTRACT_REBUILD"
    elif not plans:
        verdict = "PASS_NO_CHANGES_DETECTED_FULL_EXTRACT_REBUILD"
    else:
        verdict = "PASS_FULL_EXTRACT_LAYOUT_FAITHFUL_BOOT_TEST_CANDIDATE"

    result = FullExtractRebuildResult(
        verdict=verdict,
        original_pack_name=original_pack.name,
        original_size=len(original_bytes),
        rebuilt_size=len(rebuilt_bytes),
        original_sha256=_sha256_bytes(original_bytes),
        rebuilt_sha256=_sha256_bytes(rebuilt_bytes),
        byte_identical=original_bytes == rebuilt_bytes,
        workspace=str(workspace),
        extracted_folder=str(extracted_folder),
        rebuilt_pack=str(rebuilt_path),
        route=probe.route,
        resources_seen=len(rows),
        resources_replaced=resources_replaced,
        tex_rows_seen=tex_seen,
        tex_payloads_replaced=tex_replaced,
        tex_preserved=tex_preserved,
        blocked_count=len(blocked),
        notes=[
            "REPACK_ENGINE_V2_LAYOUT_FAITHFUL",
            "OWNER_AWARE_RESOURCE_IDENTITY",
            "CHANGED_FILES_ONLY",
            "COMPLETE_PREFLIGHT_PLAN_BEFORE_WRITE",
            "OVERLAP_CONFLICT_DETECTION",
            "BYTES_OUTSIDE_PLANNED_RANGES_PRESERVED",
            "INNER_APKF_STRUCTURE_REPARSED_AND_VERIFIED" if inner_verify.get("same_inner_structure") else "INNER_APKF_STRUCTURE_REPARSE_REVIEW_REQUIRED",
            "GENERIC_SIZE_CHANGE_STILL_BLOCKED",
            "CSV_INPUT_NOT_REQUIRED",
            "ORIGINAL_PACK_NOT_MODIFIED",
            "CSV_NOT_REQUIRED_DIRECT_ORIGINAL_MAP",
            "BOOT_TEST_USER_REQUIRED",
        ],
    )

    # Existing reports remain for workflow compatibility; v2 adds stronger plan/verification
    # information underneath without adding any new release UI feature.
    write_json(reports / "FULL_EXTRACT_REBUILD_VERDICT.json", asdict(result))
    write_csv(reports / "FULL_EXTRACT_RESOURCE_ACTIONS.csv", resource_actions)
    write_csv(reports / "FULL_EXTRACT_TEX_ACTIONS.csv", tex_actions)
    write_csv(reports / "FULL_EXTRACT_BLOCKED_SIZE_OR_MAPPING_CHANGES.csv", blocked)
    write_csv(reports / "REPACK_V2_CHANGED_RESOURCE_PLAN.csv", [_plan_report_row(p, "APPLIED") for p in plans])
    write_csv(reports / "REPACK_V2_SOURCE_OWNERSHIP_USAGE.csv", plan_info["source_usage"])
    verification = {
        "engine": REBUILD_LAB_VERSION,
        "same_size": same_size,
        "same_route": same_route,
        "same_outer_shape_exact": same_outer_shape,
        "marker_counts_same_info_only": marker_info_same,
        "first_4096_bytes_identical_info_only": header_4096_identical,
        **range_verify,
        **{f"inner_{k}": v for k, v in inner_verify.items()},
        "changed_resource_plans": len(plans),
        "unique_component_writes": len(unique_writes),
        "blocked_count": len(blocked),
        "structural_pass": structural_pass,
    }
    write_json(reports / "REPACK_V2_POST_BUILD_VERIFICATION.json", verification)
    write_csv(reports / "REPACK_V2_POST_BUILD_VERIFICATION.csv", [verification])
    write_csv(reports / "ROUTE_STRUCTURE_COMPARISON.csv", [
        {"check": "same_size", "status": "PASS" if same_size else "REVIEW", "original": len(original_bytes), "rebuilt": len(rebuilt_bytes)},
        {"check": "same_route", "status": "PASS" if same_route else "REVIEW", "original": probe.route, "rebuilt": rebuilt_probe.route},
        {"check": "same_outer_shape_exact", "status": "PASS" if same_outer_shape else "REVIEW", "original": len(original_outer_shape), "rebuilt": len(rebuilt_outer_shape)},
        {"check": "only_planned_ranges_changed", "status": "PASS" if range_verify.get("outside_planned_ranges_identical") else "REVIEW", "original": "all unplanned bytes", "rebuilt": "byte-identical" if range_verify.get("outside_planned_ranges_identical") else range_verify.get("first_unexpected_diff")},
        {"check": "planned_writes_match", "status": "PASS" if range_verify.get("planned_writes_match") else "REVIEW", "original": len(unique_writes), "rebuilt": len(unique_writes)},
        {"check": "inner_apkf_resource_component_structure", "status": "PASS" if inner_verify.get("same_inner_structure") else "REVIEW", "original": inner_verify.get("original_inner_rows"), "rebuilt": inner_verify.get("rebuilt_inner_rows")},
        {"check": "marker_counts_info_only", "status": "INFO", "original": json.dumps(_marker_count_map(original_bytes), sort_keys=True), "rebuilt": json.dumps(_marker_count_map(rebuilt_bytes), sort_keys=True)},
        {"check": "first_4096_info_only", "status": "INFO", "original": _sha256_bytes(original_bytes[:4096]), "rebuilt": _sha256_bytes(rebuilt_bytes[:4096])},
    ])
    write_csv(reports / "FIRST_BYTE_DIFFS_ORIGINAL_VS_REBUILT.csv", _small_diff_summary(original_bytes, rebuilt_bytes, limit=500), fieldnames=["offset_dec", "offset_hex", "original_byte", "rebuilt_byte"])
    (reports / "FULL_EXTRACT_TEX_SAFE_REBUILD_RULES.txt").write_text(
        "PCPACK REPACK ENGINE V2 - LAYOUT-FAITHFUL RULES\n"
        "===============================================\n\n"
        "The release UI is unchanged. The build engine now:\n"
        "- parses owner/resource/component identity directly from the clean original PCPACK; CSV input is not required;\n- identifies resources by owning APKF + outer identity + global index + hash/type, not hash/name alone;\n"
        "- builds and validates the complete changed-resource plan before writing;\n"
        "- writes only resources whose extracted bytes actually changed;\n"
        "- accepts harmless byte-identical duplicate extracted copies but blocks conflicting duplicates;\n- blocks ambiguous duplicate flat exports when owners contain different original bytes;\n"
        "- blocks conflicting/overlapping changed ranges;\n"
        "- preserves every byte outside planned component ranges exactly;\n"
        "- reparses the rebuilt pack and compares inner APKF/resource/component structure;\n"
        "- keeps generic size-changing rebuild disabled until offset/table relocation is proven.\n\n"
        "TEX still uses conservative target metadata checks and same-size component1 replacement.\n"
        "Original PCPACK is never modified. Final proof is still an in-game boot/load test.\n",
        encoding="utf-8",
    )
    verdict_txt = [
        "PCPACK Rebuild Lab v1.0 - Layout-Faithful Repack Engine V2",
        "===========================================================",
        "",
        f"Verdict: {result.verdict}",
        f"Original: {result.original_pack_name}",
        f"Route: {result.route}",
        f"Original size: {result.original_size}",
        f"Rebuilt size: {result.rebuilt_size}",
        f"Byte-identical: {result.byte_identical}",
        f"Resources seen: {result.resources_seen}",
        f"Changed resources applied: {result.resources_replaced}",
        f"TEX rows seen: {result.tex_rows_seen}",
        f"TEX payloads changed/applied: {result.tex_payloads_replaced}",
        f"TEX preserved: {result.tex_preserved}",
        f"Blocked: {result.blocked_count}",
        f"Only planned ranges changed: {range_verify.get('outside_planned_ranges_identical')}",
        f"Planned writes match output: {range_verify.get('planned_writes_match')}",
        f"Exact outer shape preserved: {same_outer_shape}",
        f"Inner APKF/resource/component structure preserved: {inner_verify.get('same_inner_structure')}",
        f"Rebuilt PCPACK: {result.rebuilt_pack}",
        "",
        "Meaning:",
        "- Repack Engine V2 no longer blindly rewrites every extracted resource.",
        "- It plans only real changed resources and refuses ambiguous/conflicting mappings.",
        "- PASS means the offline structural checks passed; in-game boot/load proof is still required.",
        "- Any blocked row should be reviewed before boot testing.",
    ]
    (reports / "FULL_EXTRACT_REBUILD_VERDICT.txt").write_text("\n".join(verdict_txt) + "\n", encoding="utf-8")
    return result

def run_no_change_rebuild_test(original_pack: Path, output_root: Path) -> RebuildLabResult:
    workspace = create_no_change_workspace(original_pack, output_root)
    return rebuild_no_change(workspace)


def open_workspace_from_result(result: RebuildLabResult) -> Path:
    return Path(result.workspace)
