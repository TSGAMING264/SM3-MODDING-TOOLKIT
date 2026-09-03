from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Any

ANIM_EXTS = {".anim"}


@dataclass
class WrapFileInfo:
    path: str
    magic: str
    header_ok: bool
    archive_hash: str
    patch_table_ptr: int
    component_count: int
    component_table_ptr: int
    component_sizes: list[int]
    component_ptrs: list[int]
    notes: list[str]


@dataclass
class AnimFileInfo:
    path: str
    name: str
    size: int
    sha256: str
    magic: str
    looks_wrap: bool
    looks_anim: bool
    wrap_header_ok: bool
    wrap_archive_hash: str
    wrap_component_count: int
    wrap_component_sizes: list[int]


@dataclass
class AnimPairAnalysis:
    source: AnimFileInfo
    target: AnimFileInfo
    same_size: bool
    same_sha256: bool
    source_bigger: bool
    target_bigger: bool
    wos_extracted_file_safe: str
    wos_size_policy: str
    sm3_pack_patch_safe: str
    sm3_size_policy: str
    size_delta: int
    recommendation: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_wrap_file(path: Path) -> WrapFileInfo:
    """Best-effort parser for WOS standalone WRAP resources.

    This mirrors the open WOS library's Wrapper.wrapResourceFile layout:
    WRAP + archive hash + patch table pointer + component count + component table pointer,
    followed by component table entries of size/pointer pairs.
    It is intentionally read-only and does not rebuild files.
    """
    data = path.read_bytes()
    notes: list[str] = []
    magic = data[:4].decode("ascii", errors="replace") if len(data) >= 4 else ""
    if magic != "WRAP":
        return WrapFileInfo(
            path=str(path),
            magic=magic,
            header_ok=False,
            archive_hash="",
            patch_table_ptr=0,
            component_count=0,
            component_table_ptr=0,
            component_sizes=[],
            component_ptrs=[],
            notes=["not_a_wrap_magic"],
        )
    if len(data) < 20:
        return WrapFileInfo(str(path), magic, False, "", 0, 0, 0, [], [], ["too_small_for_wrap_header"])
    import struct
    archive_hash, patch_ptr, component_count, component_table_ptr = struct.unpack_from("<4I", data, 4)
    sizes: list[int] = []
    ptrs: list[int] = []
    header_ok = True
    if component_count <= 0 or component_count > 64:
        header_ok = False
        notes.append(f"component_count_review:{component_count}")
    table_end = component_table_ptr + max(0, component_count) * 8
    if component_table_ptr < 20 or table_end > len(data):
        header_ok = False
        notes.append("component_table_out_of_range")
    else:
        for i in range(component_count):
            size, ptr = struct.unpack_from("<2I", data, component_table_ptr + i * 8)
            sizes.append(size)
            ptrs.append(ptr)
            if ptr >= len(data):
                header_ok = False
                notes.append(f"component_{i}_ptr_out_of_range")
            elif ptr + size > len(data):
                header_ok = False
                notes.append(f"component_{i}_range_out_of_file")
    if patch_ptr >= len(data):
        header_ok = False
        notes.append("patch_table_ptr_out_of_range")
    if not notes:
        notes.append("wrap_header_parsed")
    return WrapFileInfo(
        path=str(path),
        magic=magic,
        header_ok=header_ok,
        archive_hash=f"0x{archive_hash:08X}",
        patch_table_ptr=patch_ptr,
        component_count=component_count,
        component_table_ptr=component_table_ptr,
        component_sizes=sizes,
        component_ptrs=ptrs,
        notes=notes,
    )


def anim_file_info(path: Path) -> AnimFileInfo:
    data = path.read_bytes()[:16]
    magic = data[:4].decode("ascii", errors="replace") if data else ""
    wrap = parse_wrap_file(path) if magic == "WRAP" else None
    return AnimFileInfo(
        path=str(path),
        name=path.name,
        size=path.stat().st_size,
        sha256=sha256_file(path),
        magic=magic,
        looks_wrap=magic == "WRAP",
        looks_anim=path.suffix.lower() == ".anim" or ".wrap.anim" in path.name.lower(),
        wrap_header_ok=bool(wrap.header_ok) if wrap else False,
        wrap_archive_hash=wrap.archive_hash if wrap else "",
        wrap_component_count=wrap.component_count if wrap else 0,
        wrap_component_sizes=wrap.component_sizes if wrap else [],
    )


def analyze_anim_pair(source: Path, target: Path) -> AnimPairAnalysis:
    src = anim_file_info(source)
    dst = anim_file_info(target)
    same_size = src.size == dst.size
    same_sha = src.sha256 == dst.sha256
    if same_sha:
        rec = "Source and target are already byte-identical. WOS-style swap would be a no-op unless the target filename/slot matters."
    else:
        rec = "WOS-style extracted-file swap is allowed regardless of file size: backup target, then overwrite target with full source bytes. The open WOS Python library extracts APK resources as standalone WRAP files and says PACK/APK repack is not implemented, so this tab treats WOS mode as extracted-file replacement, not pack rebuild. SM3 direct PCPACK patching is separate and still needs same-size/layout unless a real repacker is proven."
    return AnimPairAnalysis(
        source=src,
        target=dst,
        same_size=same_size,
        same_sha256=same_sha,
        source_bigger=src.size > dst.size,
        target_bigger=dst.size > src.size,
        wos_extracted_file_safe="YES_NO_SIZE_LIMIT" if src.looks_anim and dst.looks_anim and not same_sha else ("NO_OP" if same_sha else "REVIEW_EXTENSION"),
        wos_size_policy="NO_SIZE_REQUIREMENT_FULL_FILE_OVERWRITE",
        sm3_pack_patch_safe="YES_REVIEW_LAYOUT" if same_size and not same_sha else ("NO_OP" if same_sha else "NO_SIZE_CHANGE_BLOCKED"),
        sm3_size_policy="STRICT_SAME_SIZE_AND_LAYOUT_FOR_DIRECT_PCPACK_PATCH",
        size_delta=src.size - dst.size,
        recommendation=rec,
    )


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def wos_animation_swap_route(source_out: Path, replacement_in: Path, backup_dir: Path | None = None, log_dir: Path | None = None, create_backup: bool = True) -> dict:
    """Follow the WOS Toolkit AnimationSwapTab route exactly.

    WOS labels the file being overwritten as the Source / OUT animation and the
    incoming file as the Replacement / IN animation. The operation is a direct
    extracted-file replacement: optional backup of OUT, then copy full IN bytes
    over OUT. No same-size rule is used in this route.
    """
    if not source_out.exists() or not source_out.is_file():
        raise FileNotFoundError(f"Source OUT animation not found: {source_out}")
    if not replacement_in.exists() or not replacement_in.is_file():
        raise FileNotFoundError(f"Replacement IN animation not found: {replacement_in}")
    if not source_out.name.lower().endswith(".anim") or not replacement_in.name.lower().endswith(".anim"):
        raise ValueError("Both Source OUT and Replacement IN should be .anim / .wrap.anim files for this WOS route.")
    ts = timestamp()
    # WOS strings show a backups folder/backup_path route. Default there if caller did not choose one.
    backup_dir = backup_dir or (source_out.parent / "backups")
    log_dir = log_dir or backup_dir
    before = analyze_anim_pair(replacement_in, source_out)
    replacement_prefix = replacement_in.read_bytes()[:4]
    source_out_prefix = source_out.read_bytes()[:4]
    replacement_wrap = parse_wrap_file(replacement_in) if replacement_prefix == b"WRAP" else None
    source_out_wrap_before = parse_wrap_file(source_out) if source_out_prefix == b"WRAP" else None
    backup_path = None
    if create_backup:
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{source_out.name}_{ts}.bak"
        shutil.copy2(source_out, backup_path)
    # Match WOS's shutil/copy route: preserve source file bytes and metadata as much as possible.
    shutil.copy2(replacement_in, source_out)
    after = anim_file_info(source_out)
    result = {
        "mode": "WOS_TOOLKIT_ANIMATION_SWAP_ROUTE",
        "wos_tab_class": "AnimationSwapTab",
        "wos_function_route": "do_direct_swap / quick_animation_swap",
        "source_out_overwritten": str(source_out),
        "replacement_in": str(replacement_in),
        "backup_created": bool(backup_path),
        "backup": str(backup_path) if backup_path else "",
        "replacement_wrap": asdict(replacement_wrap) if replacement_wrap else None,
        "source_out_wrap_before": asdict(source_out_wrap_before) if source_out_wrap_before else None,
        "replacement_size": before.source.size,
        "source_out_old_size": before.target.size,
        "source_out_new_size": after.size,
        "replacement_sha256": before.source.sha256,
        "source_out_old_sha256": before.target.sha256,
        "source_out_new_sha256": after.sha256,
        "source_out_now_equals_replacement": after.sha256 == before.source.sha256 and after.size == before.source.size,
        "size_change_allowed_in_this_route": True,
        "size_delta_replacement_minus_old_out": before.source.size - before.target.size,
        "same_size_required": False,
        "route_note": "Follows WOS Toolkit naming: Source/OUT is overwritten, Replacement/IN is copied in. Optional backup first. No same-size requirement.",
        "sm3_pcpack_note": "Direct SM3 PCPACK patching is separate and still requires same-size/same-layout unless a real table/offset rebuild repacker is proven.",
    }
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"WOS_ANIMATION_SWAP_ROUTE_{ts}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def wos_style_extracted_file_swap(source: Path, target: Path, backup_dir: Path | None = None, log_dir: Path | None = None, create_backup: bool = True) -> dict:
    """Compatibility wrapper using the older SM3 tab wording.

    Older builds called replacement input `source` and overwritten path `target`.
    Internally route through the exact WOS naming now.
    """
    return wos_animation_swap_route(source_out=target, replacement_in=source, backup_dir=backup_dir, log_dir=log_dir, create_backup=create_backup)


def iter_anim_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower().endswith(".anim"):
            yield path


def scan_anim_folder(root: Path, limit: int | None = None) -> list[AnimFileInfo]:
    rows: list[AnimFileInfo] = []
    for idx, path in enumerate(iter_anim_files(root), 1):
        rows.append(anim_file_info(path))
        if limit and idx >= limit:
            break
    return rows


def load_final_scan_candidates(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        rows = [dict(r) for r in reader]
    # Normalize field names from both final scanner helper exports.
    normalized = []
    for r in rows:
        item = {
            "priority": r.get("priority", "REVIEW"),
            "normalized_name": r.get("normalized_name", r.get("source_a_name", "")),
            "extension": r.get("extension", ".anim"),
            "source_a_rel_path": r.get("source_a_rel_path", ""),
            "source_a_size": r.get("source_a_size", r.get("size", "")),
            "source_b_rel_path": r.get("source_b_rel_path", ""),
            "source_b_size": r.get("source_b_size", r.get("size", "")),
            "sha_status": r.get("sha_status", ""),
            "note": r.get("note", ""),
            "wos_extracted_file_verdict": "WOS_OK_FULL_FILE_COPY_NO_SIZE_LIMIT",
            "sm3_pcpack_verdict": "STRICT_REVIEW_ONLY",
        }
        normalized.append(item)
    return normalized


def write_candidates_for_new_tab(csv_path: Path, rows: list[dict]) -> None:
    fields = ["priority", "normalized_name", "extension", "source_a_rel_path", "source_a_size", "source_b_rel_path", "source_b_size", "sha_status", "wos_extracted_file_verdict", "sm3_pcpack_verdict", "note"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# SM3 character animation CSV import patch support
# ---------------------------------------------------------------------------

SM3_ANIM_TEST_DEST_KEYS = [
    "destination", "destination_anim", "source_out", "source", "out", "dest", "target", "target_anim"
]
SM3_ANIM_TEST_REPL_KEYS = [
    "replacement", "replacement_anim", "replacement_in", "in", "repl", "new_anim", "source_in"
]


def _truthy_csv_value(value: str | None, default: bool = True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "n", "off", "skip", "disabled"}


def _first_present(row: dict[str, Any], keys: list[str]) -> str:
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for k in keys:
        val = low.get(k.lower())
        if val is not None and str(val).strip():
            return str(val).strip().strip('"')
    return ""


def _resolve_anim_reference(ref: str, extracted_folder: Path, csv_base: Path | None = None, role: str = "animation", allow_extracted_lookup: bool = True) -> tuple[Path, dict[str, Any]]:
    """Resolve a CSV animation reference to a real .anim file.

    Accepted references:
    - absolute path
    - path relative to the CSV folder
    - path relative to the extracted character folder
    - bare filename / 0x hash / animation name inside the extracted folder
    """
    ref = (ref or "").strip().strip('"')
    if not ref:
        raise ValueError(f"Missing {role} animation reference in CSV row.")
    extracted_folder = Path(extracted_folder)
    csv_base = Path(csv_base) if csv_base else None
    info: dict[str, Any] = {"role": role, "requested": ref, "resolution": ""}

    raw = Path(ref)
    direct_candidates: list[Path] = []
    if raw.is_absolute():
        direct_candidates.append(raw)
    # Keep the first direct checks exactly as expected for normal CSVs.
    if csv_base:
        direct_candidates.append(csv_base / raw)
        # v5.2.78 Xbox Test fix: candidate CSVs live in
        #   RUN/00_XBOX_LAB_REPORTS/XBOX_CANDIDATE_BUILDER
        # while Xbox payloads live in
        #   RUN/02_XBOX_ANIM_EXTRACTED/ANIM
        # Some older generated CSVs used ../02_XBOX..., which points one level
        # too shallow from XBOX_CANDIDATE_BUILDER.  Try stripped-parent forms
        # against nearby parent folders before any extracted-PC lookup.
        stripped_parts = [part for part in raw.parts if part not in ("..", ".")]
        if stripped_parts:
            stripped = Path(*stripped_parts)
            for base in list(csv_base.parents[:5]):
                direct_candidates.append(base / stripped)
            for base in list(csv_base.parents[:5]):
                direct_candidates.append(base / raw)
    if allow_extracted_lookup:
        direct_candidates.append(extracted_folder / raw)
    seen_direct: set[str] = set()
    for p in direct_candidates:
        key = str(p)
        if key in seen_direct:
            continue
        seen_direct.add(key)
        if p.exists() and p.is_file() and p.name.lower().endswith(".anim"):
            info["resolution"] = "direct_or_relative_path"
            info["resolved"] = str(p)
            info["allow_extracted_lookup"] = bool(allow_extracted_lookup)
            return p, info

    if not allow_extracted_lookup:
        info["resolution"] = "FAILED_STRICT_PATH_ONLY_NO_PC_FALLBACK"
        raise ValueError(
            f"Could not resolve {role} animation from CSV reference '{ref}' as a real external/direct path. "
            "Xbox test mode blocks fallback lookup inside the PC extracted folder so missing Xbox payloads do not silently become PC animations."
        )

    wanted_hash = _parse_hex_hash_from_export_name(Path(ref))
    wanted_name = Path(ref).name.lower()
    wanted_norm = _normalized_anim_export_name(Path(ref))
    candidates = _iter_anim_files(extracted_folder)
    info["candidate_count"] = len(candidates)
    groups: list[tuple[str, list[Path]]] = []
    if wanted_hash is not None:
        groups.append(("hash_0x", [c for c in candidates if _parse_hex_hash_from_export_name(c) == wanted_hash]))
    groups.append(("exact_filename", [c for c in candidates if c.name.lower() == wanted_name]))
    groups.append(("normalized_anim_name", [c for c in candidates if _normalized_anim_export_name(c) == wanted_norm]))
    # Last resort: contains normalized name, useful for CSV rows without 0x hashes.
    if wanted_norm:
        groups.append(("contains_normalized_name", [c for c in candidates if wanted_norm in _normalized_anim_export_name(c) or _normalized_anim_export_name(c) in wanted_norm]))

    for label, group in groups:
        if group:
            group = sorted(group, key=_anim_candidate_priority)
            p = group[0]
            info.update({"resolution": label, "resolved": str(p), "match_count": len(group)})
            return p, info

    sample = []
    try:
        sample = [str(q.relative_to(extracted_folder)).replace("\\", "/") for q in sorted(candidates, key=_anim_candidate_priority)[:20]]
    except Exception:
        sample = [str(q) for q in sorted(candidates, key=_anim_candidate_priority)[:20]]
    info["resolution"] = "FAILED_NO_MATCH"
    info["sample"] = sample
    raise ValueError(f"Could not resolve {role} animation from CSV reference '{ref}'. Anim files found: {len(candidates)}")


def load_sm3_character_anim_test_csv(csv_path: Path) -> list[dict[str, Any]]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        rows = [dict(r) for r in csv.DictReader(f)]
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, 1):
        enabled = _truthy_csv_value(row.get("enabled"), True)
        dest_ref = _first_present(row, SM3_ANIM_TEST_DEST_KEYS)
        repl_ref = _first_present(row, SM3_ANIM_TEST_REPL_KEYS)
        out.append({
            "row": idx,
            "enabled": enabled,
            "mode": (row.get("mode") or "slot_preserve").strip().lower(),
            "destination": dest_ref,
            "replacement": repl_ref,
            "note": row.get("note", ""),
            "raw": row,
        })
    return out


def generate_combat_slot_preserve_test_csv(extracted_folder: Path, out_csv: Path, limit: int = 25) -> dict[str, Any]:
    """Create a starter combat->combat CSV with smaller replacements fitting larger slots."""
    extracted_folder = Path(extracted_folder)
    out_csv = Path(out_csv)
    anims = _iter_anim_files(extracted_folder)
    rows_meta = []
    for p in anims:
        norm = _normalized_anim_export_name(p)
        family = classify_wos_tweak_family(norm)
        # Combat naming in SM3 is inconsistent, so include attack/ddg/counter terms as combat-ish.
        low = norm.lower()
        combatish = family == "combat" or any(k in low for k in ["atck", "atk", "ddgcntr", "counter", "punch", "kick", "hit"])
        if combatish:
            rows_meta.append({"path": p, "norm": norm, "size": p.stat().st_size, "family": "combat"})
    # Destination bigger first, replacement smaller first.  Keep same rough naming family by prefix where possible.
    destinations = sorted(rows_meta, key=lambda r: (-int(r["size"]), str(r["norm"])))
    replacements = sorted(rows_meta, key=lambda r: (int(r["size"]), str(r["norm"])))
    written: list[dict[str, Any]] = []
    used_pairs: set[tuple[str, str]] = set()
    for d in destinations:
        for r in replacements:
            if d["path"] == r["path"]:
                continue
            if int(r["size"]) > int(d["size"]):
                continue
            key = (str(d["path"]), str(r["path"]))
            if key in used_pairs:
                continue
            # Avoid absurdly tiny replacement unless there are no options; this is only a test helper.
            if int(r["size"]) < 512:
                continue
            used_pairs.add(key)
            try:
                drel = str(d["path"].relative_to(extracted_folder)).replace("\\", "/")
            except Exception:
                drel = str(d["path"])
            try:
                rrel = str(r["path"].relative_to(extracted_folder)).replace("\\", "/")
            except Exception:
                rrel = str(r["path"])
            written.append({
                "enabled": "1",
                "mode": "slot_preserve",
                "destination": drel,
                "replacement": rrel,
                "destination_size": int(d["size"]),
                "replacement_size": int(r["size"]),
                "padding_bytes": int(d["size"]) - int(r["size"]),
                "destination_family": "combat",
                "replacement_family": "combat",
                "note": "AUTO_COMBAT_SLOT_PRESERVE_TEST_PAIR",
            })
            break
        if len(written) >= int(limit or 25):
            break
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = ["enabled", "mode", "destination", "replacement", "destination_size", "replacement_size", "padding_bytes", "destination_family", "replacement_family", "note"]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(written)
    return {"out_csv": str(out_csv), "combat_anims_found": len(rows_meta), "pairs_written": len(written)}


def character_anim_csv_auto_test_patch(
    original_pack: Path,
    extracted_folder: Path,
    csv_path: Path,
    output_root: Path,
    max_rows: int | None = None,
    allow_experimental_size_change: bool = False,
    replacement_allow_extracted_lookup: bool = True,
    block_same_destination_replacement: bool = False,
) -> dict[str, Any]:
    """Import a simple CSV and create one patched PCPACK per enabled row.

    v5.2.58 release cleanup: this is now the only visible CSV workflow.
    It uses SAFE slot-preserve by default: replacement must fit the destination
    slot exactly or be smaller, with unused slot bytes preserved safely.
    Internal work paths are forced short on Windows so PCPACKs are actually
    created and copied to the visible output folder.
    """
    original_pack = Path(original_pack)
    extracted_folder = Path(extracted_folder)
    csv_path = Path(csv_path)
    output_root = Path(output_root)
    rows = load_sm3_character_anim_test_csv(csv_path)
    if max_rows is not None and max_rows > 0:
        rows = rows[:max_rows]
    final_root = output_root / "FINAL_CHARACTER_ANIM_CSV_TEST_OUTPUT"
    final_root.mkdir(parents=True, exist_ok=True)
    csv_base = csv_path.parent
    results: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("enabled", True):
            results.append({"row": row.get("row"), "status": "SKIPPED_DISABLED"})
            continue
        try:
            dest_path, dest_resolution = _resolve_anim_reference(row.get("destination", ""), extracted_folder, csv_base, role="destination")
            repl_path, repl_resolution = _resolve_anim_reference(
                row.get("replacement", ""),
                extracted_folder,
                csv_base,
                role="replacement",
                allow_extracted_lookup=replacement_allow_extracted_lookup,
            )
            if block_same_destination_replacement:
                try:
                    same_file = dest_path.resolve() == repl_path.resolve()
                except Exception:
                    same_file = str(dest_path) == str(repl_path)
                if same_file:
                    results.append({
                        "row": row.get("row"),
                        "status": "BLOCKED_DESTINATION_EQUALS_REPLACEMENT",
                        "destination": str(dest_path),
                        "replacement": str(repl_path),
                        "destination_resolution": dest_resolution,
                        "replacement_resolution": repl_resolution,
                        "note": "Xbox test mode blocks rows where replacement resolved to the same PC destination file. Regenerate the Xbox NAS CSV or fix the replacement path.",
                    })
                    continue
            dest_info = anim_file_info(dest_path)
            repl_info = anim_file_info(repl_path)
            mode = str(row.get("mode") or "slot_preserve").lower()
            if repl_info.size > dest_info.size and not allow_experimental_size_change and "experimental" not in mode:
                results.append({
                    "row": row.get("row"),
                    "status": "BLOCKED_REPLACEMENT_BIGGER_SAFE_CSV",
                    "destination": str(dest_path),
                    "replacement": str(repl_path),
                    "destination_size": dest_info.size,
                    "replacement_size": repl_info.size,
                    "note": "Use a bigger destination slot, or manually use experimental size-change for one row.",
                })
                continue
            # v5.2.58: use extremely short temp paths and force compact internal
            # rebuild names. This fixes Windows errors where nested report paths like
            # 00_REFERENCE_REPORT_REGENERATED.../ROUTE_HANDLER_SUMMARY.txt exceeded
            # path limits before the visible PCPACK could be copied out.
            row_num = int(row.get("row") or 0)
            visible_row_info = final_root / f"ROW_{row_num:03d}_INFO"
            visible_row_info.mkdir(parents=True, exist_ok=True)
            short_run_root = Path(tempfile.gettempdir()) / "S3ACSV" / f"{datetime.now().strftime('%H%M%S')}{row_num:03d}"
            row_work_root = short_run_root / "W"
            if row_work_root.exists():
                shutil.rmtree(row_work_root, ignore_errors=True)
            row_work_root.mkdir(parents=True, exist_ok=True)
            temp_work_cleaned = False

            old_short_repack = os.environ.get("SM3_SHORT_REPACK_PATHS")
            old_short_rebuild = os.environ.get("SM3_SHORT_REBUILD_PATHS")
            os.environ["SM3_SHORT_REPACK_PATHS"] = "1"
            os.environ["SM3_SHORT_REBUILD_PATHS"] = "1"
            try:
                if repl_info.size <= dest_info.size and "experimental" not in mode:
                    one = character_anim_slot_preserve_swap(original_pack, extracted_folder, dest_path, repl_path, row_work_root)
                    action = "SAFE_SLOT_PRESERVE"
                else:
                    one = character_anim_repack_swap(original_pack, extracted_folder, dest_path, repl_path, row_work_root, allow_size_change=True)
                    action = "EXPERIMENTAL_SIZE_CHANGE"
            finally:
                if old_short_repack is None:
                    os.environ.pop("SM3_SHORT_REPACK_PATHS", None)
                else:
                    os.environ["SM3_SHORT_REPACK_PATHS"] = old_short_repack
                if old_short_rebuild is None:
                    os.environ.pop("SM3_SHORT_REBUILD_PATHS", None)
                else:
                    os.environ["SM3_SHORT_REBUILD_PATHS"] = old_short_rebuild

            nested_pack = Path(str(one.get("final_patched_pack", "")))
            if not nested_pack.exists():
                found = sorted(row_work_root.rglob("*.PCPACK"), key=lambda q: (len(str(q)), str(q).lower()))
                nested_pack = found[0] if found else nested_pack
            if not nested_pack.exists():
                raise FileNotFoundError(f"CSV row {row_num} patched internally but no final PCPACK was found in short work folder {row_work_root}")

            safe_dest_name = _normalized_anim_export_name(dest_path).replace("/", "_").replace("\\", "_")[:80] or dest_path.stem[:80]
            visible_pack = final_root / f"ROW_{row_num:03d}_{original_pack.stem}_CSVTEST_{safe_dest_name}.PCPACK"
            counter = 1
            while visible_pack.exists():
                visible_pack = final_root / f"ROW_{row_num:03d}_{original_pack.stem}_CSVTEST_{safe_dest_name}_{counter:03d}.PCPACK"
                counter += 1
            shutil.copy2(nested_pack, visible_pack)

            # Keep lightweight per-row proof in the visible output folder, but do not
            # copy the staged extracted pack/game assets back into the zip.
            row_proof = {
                "row": row.get("row"),
                "status": "PATCHED",
                "action": action,
                "destination": str(dest_path),
                "replacement": str(repl_path),
                "destination_resolution": dest_resolution,
                "replacement_resolution": repl_resolution,
                "replacement_allow_extracted_lookup": bool(replacement_allow_extracted_lookup),
                "block_same_destination_replacement": bool(block_same_destination_replacement),
                "replacement_source_kind": "STRICT_EXTERNAL_XBOX_PAYLOAD" if not replacement_allow_extracted_lookup else "NORMAL_CSV_RESOLVE",
                "destination_size": dest_info.size,
                "replacement_size": repl_info.size,
                "padding_bytes": max(0, dest_info.size - repl_info.size) if action == "SAFE_SLOT_PRESERVE" else "",
                "final_patched_pack": str(visible_pack),
                "nested_backend_pack": str(nested_pack),
                "short_temp_work_folder": str(row_work_root),
                "boot_risk": one.get("boot_risk", ""),
                "final_pack_differs_from_original": one.get("final_pack_differs_from_original", ""),
            }
            (visible_row_info / "ROW_RESULT.json").write_text(json.dumps(row_proof, indent=2), encoding="utf-8")
            try:
                shutil.rmtree(row_work_root, ignore_errors=True)
                temp_work_cleaned = True
            except Exception:
                temp_work_cleaned = False
            row_proof["temp_work_cleaned"] = temp_work_cleaned
            (visible_row_info / "ROW_RESULT.json").write_text(json.dumps(row_proof, indent=2), encoding="utf-8")

            results.append(row_proof)
        except Exception as exc:
            row_num = int(row.get("row") or 0)
            err = {"row": row.get("row"), "status": "ERROR", "error": str(exc), "destination_ref": row.get("destination", ""), "replacement_ref": row.get("replacement", "")}
            try:
                visible_row_info = final_root / f"ROW_{row_num:03d}_INFO"
                visible_row_info.mkdir(parents=True, exist_ok=True)
                (visible_row_info / "ROW_ERROR.json").write_text(json.dumps(err, indent=2), encoding="utf-8")
            except Exception:
                pass
            results.append(err)
    fields = sorted({k for r in results for k in r.keys()})
    summary_csv = final_root / "CHARACTER_ANIM_CSV_TEST_RESULTS.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    summary = {
        "mode": "SM3_CHARACTER_ANIM_CSV_SIMPLE_IMPORT_PATCH_V5_2_58",
        "original_pack": str(original_pack),
        "extracted_folder": str(extracted_folder),
        "csv_path": str(csv_path),
        "output_root": str(final_root),
        "rows_total": len(rows),
        "patched_count": sum(1 for r in results if r.get("status") == "PATCHED"),
        "blocked_count": sum(1 for r in results if str(r.get("status", "")).startswith("BLOCKED")),
        "error_count": sum(1 for r in results if r.get("status") == "ERROR"),
        "results_csv": str(summary_csv),
        "results": results,
        "notes": [
            "SIMPLE_IMPORT_CSV_THEN_PATCH_GAME_PACKS",
            "DEFAULT_SAFE_SLOT_PRESERVE_ONLY_NO_EXPERIMENTAL_SIZE_CHANGE",
            f"REPLACEMENT_ALLOW_EXTRACTED_LOOKUP={bool(replacement_allow_extracted_lookup)}",
            f"BLOCK_SAME_DESTINATION_REPLACEMENT={bool(block_same_destination_replacement)}",
            "BEST_FOR_COMBAT_TO_COMBAT_TESTING",
            "BOOT_TEST_ONE_OUTPUT_PACK_AT_A_TIME",
            "V5_2_58_SIMPLE_CSV_IMPORT_ONLY_AND_COMPACT_INTERNAL_PATHS",
        ],
    }
    summary_json = final_root / "CHARACTER_ANIM_CSV_TEST_SUMMARY.json"
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (final_root / "00_CSV_AUTO_TEST_PATCHES_ARE_HERE.txt").write_text(
        "SM3 Character Animation CSV Patch Output\n"
        "================================================\n\n"
        f"CSV: {csv_path}\n"
        f"Visible patched PCPACKs created here: {summary['patched_count']}\n"
        f"Blocked rows: {summary['blocked_count']}\n"
        f"Errors: {summary['error_count']}\n\n"
        "Test ONE patched PCPACK at a time. Backup the original character pack before boot testing.\n",
        encoding="utf-8",
    )
    return summary

# ---------------------------------------------------------------------------
# WOS Tweaks AnimationSwap preset support
# ---------------------------------------------------------------------------

WOS_TWEAK_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "wos_tweaks_animation_presets.json"



CHARACTER_ANIM_PACKS = {
    "CH_SPIDERMAN.PCPACK": "Spider-Man",
    "CH_BLACKSUIT.PCPACK": "Black Suit",
    "CH_PETER.PCPACK": "Peter",
    "CH_GOBLIN.PCPACK": "Goblin",
}


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except Exception:
        return False


def _iter_anim_files(root: Path) -> list[Path]:
    """Return .anim/.wrap.anim files below an extracted character folder."""
    out: list[Path] = []
    try:
        for p in root.rglob("*"):
            if p.is_file() and p.name.lower().endswith(".anim"):
                out.append(p)
    except Exception:
        pass
    return out


def _anim_candidate_priority(path: Path) -> tuple[int, int, str]:
    parts = [x.lower() for x in path.parts]
    if any("02_apkf_extracted_real_ext" in x for x in parts):
        bucket = 0
    elif any("03_apkf_components" in x for x in parts):
        bucket = 1
    else:
        bucket = 2
    return (bucket, len(str(path)), str(path).lower())


def _resolve_destination_anim_in_extract(destination_anim: Path, extracted_folder: Path) -> tuple[Path, dict[str, Any]]:
    """Resolve Source OUT to an existing ANIM slot in the selected extract.

    v5.2.50/v5.2.51 blocked when Source OUT was not literally inside the
    selected extracted character folder.  Real users often browse the same
    destination animation from a search result, previous extract, or helper
    folder.  v5.2.52 accepts that and auto-resolves by 0x hash/name as long as
    the destination slot exists inside the selected extracted folder.
    """
    info: dict[str, Any] = {
        "requested_destination_anim": str(destination_anim),
        "selected_extracted_folder": str(extracted_folder),
        "resolution_mode": "DIRECT_INSIDE_SELECTED_EXTRACT",
        "candidate_count": 0,
        "matched_by": "path_inside",
    }
    if _path_is_inside(destination_anim, extracted_folder):
        return destination_anim, info

    wanted_hash = _parse_hex_hash_from_export_name(destination_anim)
    wanted_name = destination_anim.name.lower()
    wanted_norm = _normalized_anim_export_name(destination_anim)
    candidates = _iter_anim_files(extracted_folder)
    info["candidate_count"] = len(candidates)

    exact_hash: list[Path] = []
    exact_name: list[Path] = []
    norm_name: list[Path] = []
    for c in candidates:
        if wanted_hash is not None and _parse_hex_hash_from_export_name(c) == wanted_hash:
            exact_hash.append(c)
        if c.name.lower() == wanted_name:
            exact_name.append(c)
        if _normalized_anim_export_name(c) == wanted_norm:
            norm_name.append(c)

    chosen: Path | None = None
    matched_by = ""
    for label, group in (("hash_0x", exact_hash), ("exact_filename", exact_name), ("normalized_anim_name", norm_name)):
        if group:
            group = sorted(group, key=_anim_candidate_priority)
            chosen = group[0]
            matched_by = label
            info["alternate_match_count"] = len(group)
            break

    if chosen is None:
        sample = []
        try:
            sample = [str(q.relative_to(extracted_folder)).replace("\\", "/") for q in sorted(candidates, key=_anim_candidate_priority)[:25]]
        except Exception:
            sample = [str(q) for q in sorted(candidates, key=_anim_candidate_priority)[:25]]
        info["resolution_mode"] = "FAILED_NO_MATCH_IN_SELECTED_EXTRACT"
        info["sample_anim_files_in_extract"] = sample
        raise ValueError(
            "Destination animation was not inside the selected extracted character folder, "
            "and no matching destination slot was found by hash/name. "
            "Pick the character extracted folder that contains the destination animation, "
            "or browse Source OUT from inside that selected folder. "
            f"Requested: {destination_anim.name}; anim files found in selected extract: {len(candidates)}"
        )

    info.update({
        "resolution_mode": "AUTO_RESOLVED_DESTINATION_INSIDE_SELECTED_EXTRACT",
        "matched_by": matched_by,
        "resolved_destination_anim": str(chosen),
        "resolved_destination_relative_path": str(chosen.resolve().relative_to(extracted_folder.resolve())).replace("\\", "/"),
    })
    return chosen, info


# ---------------------------------------------------------------------------
# SM3 character APKF size-changing ANIM repack (experimental)
# ---------------------------------------------------------------------------

def _align_sm3(pos: int, align: int) -> int:
    align = int(align or 1) & 0xFFFFFF
    if align <= 1:
        return pos
    return (pos + align - 1) & ~(align - 1)


def _parse_hex_hash_from_export_name(path: Path) -> int | None:
    import re
    m = re.search(r"0x([0-9A-Fa-f]{8})", path.name)
    if not m:
        return None
    try:
        return int(m.group(1), 16)
    except Exception:
        return None


def _normalized_anim_export_name(path: Path) -> str:
    name = path.name.lower()
    if name.startswith("0x") and "." in name:
        name = name.split(".", 1)[1]
    for suffix in (".wrap.anim", ".anim"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace(" ", "_")


def _find_apkf_file_for_export(apkf, export_path: Path):
    wanted_hash = _parse_hex_hash_from_export_name(export_path)
    wanted_name = _normalized_anim_export_name(export_path)
    best = None
    for f in apkf.files:
        if (f.file_type or "").upper() != "ANIM":
            continue
        if wanted_hash is not None and int(f.filename_hash) == int(wanted_hash):
            return f
        fn = str(f.filename or "").lower().replace(" ", "_")
        if wanted_name and (wanted_name == fn or wanted_name in fn or fn in wanted_name):
            best = f
    return best


def _file_type_header_by_type(apkf) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for h in apkf.file_type_headers:
        out[str(h.get("file_type") or "").upper()] = h
    return out


def _rebuild_apkf_with_one_anim_replaced(apkf_data: bytes, destination_export: Path, replacement_data: bytes) -> tuple[bytes, dict[str, Any]]:
    """Rebuild one APKF archive after replacing one ANIM with any byte size.

    This is intentionally narrow for v5.2.52: one existing ANIM slot in a known
    character pack. It keeps all file records/names/order/component tables and
    only updates component sizes/data offsets plus the chosen file header size.
    """
    import struct
    from sm3_toolkit.services.pack_extract_service import APKFArchive

    apkf = APKFArchive(apkf_data, label="character_size_change_apkf")
    target = _find_apkf_file_for_export(apkf, destination_export)
    if target is None:
        raise ValueError(f"Could not match destination animation inside APKF: {destination_export.name}")
    if (target.file_type or "").upper() != "ANIM":
        raise ValueError("Destination is not an ANIM entry in the character APKF.")
    if len(target.component_sizes) != 1:
        raise ValueError("Different-size ANIM repack currently supports ANIM entries with one component only.")

    original_size = int(target.component_sizes[0])
    new_size = len(replacement_data)
    delta = new_size - original_size

    comp_count = len(apkf.component_headers)
    if comp_count < 1:
        raise ValueError("APKF has no component headers.")
    first_base = min(c.base_data_address for c in apkf.component_headers)
    prefix = bytearray(apkf_data[:first_base])

    # Update the selected file header's component size. For ANIM, n_active=1,
    # so size0 starts directly after filename pointer + hash.
    size_field_off = target.file_header_offset + 8
    if size_field_off + 4 > len(prefix):
        raise ValueError("Selected ANIM file-header size field is outside the immutable APKF header prefix.")
    struct.pack_into("<I", prefix, size_field_off, new_size)

    type_headers = _file_type_header_by_type(apkf)
    comp_buffers: list[bytearray] = [bytearray() for _ in range(comp_count)]
    comp_cursors = [0 for _ in range(comp_count)]
    per_file_actions: list[dict[str, Any]] = []

    for f in apkf.files:
        ftype = str(f.file_type or "").upper()
        aligns = list(type_headers.get(ftype, {}).get("component_alignments") or [])
        for ci, comp_size in enumerate(f.component_sizes):
            if ci >= comp_count:
                raise ValueError(f"File {f.filename} references missing component {ci}.")
            align = aligns[ci] if ci < len(aligns) else 1
            write_pos = _align_sm3(max(0, comp_cursors[ci] - 1), align)
            buf = comp_buffers[ci]
            if len(buf) < write_pos:
                buf.extend(b"\x00" * (write_pos - len(buf)))
            if f.global_index == target.global_index and ci == 0:
                blob = replacement_data
                action = "REPLACED_ANIM_COMPONENT0_SIZE_CHANGE"
            else:
                s, e = f.component_offsets[ci]
                blob = apkf_data[s:e]
                action = "PRESERVED_ORIGINAL_COMPONENT"
                if len(blob) != int(comp_size):
                    # Parser clamps bad offsets; this should not happen for known character packs.
                    raise ValueError(f"Component length mismatch while rebuilding {f.filename}: {len(blob)} != {comp_size}")
            buf.extend(blob)
            comp_cursors[ci] = write_pos + len(blob)
            if f.global_index == target.global_index:
                per_file_actions.append({
                    "file_global_index": f.global_index,
                    "file_type": f.file_type,
                    "filename": f.filename,
                    "component": ci,
                    "action": action,
                    "old_size": original_size if ci == 0 else comp_size,
                    "new_size": len(blob),
                    "write_pos": write_pos,
                    "alignment": align,
                })

    # Lay out component data sections. Component 0 keeps its original base; later
    # components move if earlier component sizes change. Update data_size and
    # data_offset fields in the component table.
    new_component_bases: list[int] = []
    cursor_abs = first_base
    for ci, c in enumerate(apkf.component_headers):
        if ci == 0:
            base = c.base_data_address
        else:
            base = _align_sm3(cursor_abs, c.field2 or 1)
        new_component_bases.append(base)
        data_size = len(comp_buffers[ci])
        struct.pack_into("<I", prefix, c.offset + 16, data_size)
        new_data_offset = base - (c.offset + 20)
        if new_data_offset < 0:
            raise ValueError("Computed negative component data offset while rebuilding APKF.")
        struct.pack_into("<I", prefix, c.offset + 20, new_data_offset)
        cursor_abs = base + data_size

    orig_last_end = max((e for f in apkf.files for _s, e in f.component_offsets), default=first_base)
    trailing = apkf_data[orig_last_end:]
    out = bytearray(prefix)
    for ci, buf in enumerate(comp_buffers):
        base = new_component_bases[ci]
        if len(out) < base:
            out.extend(b"\x00" * (base - len(out)))
        out.extend(buf)
    out.extend(trailing)

    meta = {
        "matched_destination_filename": target.filename,
        "matched_destination_hash": f"0x{int(target.filename_hash):08X}",
        "destination_global_index": target.global_index,
        "old_anim_size": original_size,
        "new_anim_size": new_size,
        "size_delta": delta,
        "old_apkf_size": len(apkf_data),
        "new_apkf_size": len(out),
        "apkf_size_delta": len(out) - len(apkf_data),
        "component_bases_before": [c.base_data_address for c in apkf.component_headers],
        "component_bases_after": new_component_bases,
        "component_sizes_after": [len(b) for b in comp_buffers],
        "target_actions": per_file_actions,
    }
    return bytes(out), meta


def _rebuild_character_pcpack_with_size_changed_anim(original_pack: Path, destination_anim: Path, replacement_anim: Path, output_root: Path) -> dict[str, Any]:
    """Experimental character-only size-changing ANIM repack.

    Supports the common character route where the real type36 APKF payload is the
    last major payload in the PCPACK. It rebuilds that APKF and updates the outer
    row's data_size. This is for CH_SPIDERMAN/CH_BLACKSUIT/CH_PETER/CH_GOBLIN only.
    """
    import struct
    from sm3_toolkit.services.pack_extract_service import probe_pack_bytes

    original_pack = Path(original_pack)
    data = original_pack.read_bytes()
    probe = probe_pack_bytes(original_pack.name, data)
    type36_rows = [r for r in probe.outer_rows if r.type_id == 0x36 and data[r.data_offset:r.data_offset + 4] == b"APKF" and r.data_size > 0x28]
    if len(type36_rows) != 1:
        raise ValueError(f"Expected exactly one real type36/APKF row for character repack, found {len(type36_rows)}.")
    row = type36_rows[0]
    old_start = row.data_offset
    old_end = row.data_offset + row.data_size
    if any(r.data_offset > old_start and r.data_offset < old_end for r in probe.outer_rows):
        raise ValueError("Outer rows overlap the type36/APKF payload; size-changing character repack blocked.")
    later_rows = [r for r in probe.outer_rows if r.data_offset >= old_end]
    # Character packs normally have only tiny trailing padding after the final APKF.
    # If a real row begins after APKF, shifting offsets is not implemented yet.
    if later_rows:
        raise ValueError("Type36/APKF is not the final outer payload; shifting later outer rows is not enabled.")

    old_apkf = data[old_start:old_end]
    new_apkf, meta = _rebuild_apkf_with_one_anim_replaced(old_apkf, destination_anim, replacement_anim.read_bytes())
    trailing = data[old_end:]
    rebuilt = bytearray()
    rebuilt.extend(data[:old_start])
    rebuilt.extend(new_apkf)
    rebuilt.extend(trailing)
    # Update outer table row size field for the type36/APKF payload.
    struct.pack_into("<I", rebuilt, row.table_offset + 12, len(new_apkf))

    final_root = output_root / "FINAL_CHARACTER_ANIM_REPACK_OUTPUT"
    final_root.mkdir(parents=True, exist_ok=True)
    safe_dest = destination_anim.stem.replace(".", "_")[:80]
    final_name = f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_SIZECHANGE_{safe_dest}.PCPACK"
    final_path = final_root / final_name
    counter = 1
    while final_path.exists():
        final_path = final_root / f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_SIZECHANGE_{safe_dest}_{counter:03d}.PCPACK"
        counter += 1
    final_path.write_bytes(bytes(rebuilt))

    rebuilt_probe = probe_pack_bytes(final_path.name, bytes(rebuilt))
    report = {
        "mode": "SM3_CHARACTER_ANIM_SIZE_CHANGE_REPACK_V5_2_52_EXPERIMENTAL",
        "original_pack": str(original_pack),
        "destination_anim": str(destination_anim),
        "replacement_anim": str(replacement_anim),
        "final_patched_pack": str(final_path),
        "original_pack_size": len(data),
        "rebuilt_pack_size": len(rebuilt),
        "pack_size_delta": len(rebuilt) - len(data),
        "original_route": probe.route,
        "rebuilt_route": rebuilt_probe.route,
        "same_route_after_rebuild": probe.route == rebuilt_probe.route,
        "outer_row_count_before": len(probe.outer_rows),
        "outer_row_count_after": len(rebuilt_probe.outer_rows),
        "same_outer_row_count": len(probe.outer_rows) == len(rebuilt_probe.outer_rows),
        "type36_table_offset": f"0x{row.table_offset:X}",
        "type36_payload_offset": f"0x{old_start:X}",
        "old_type36_size": row.data_size,
        "new_type36_size": len(new_apkf),
        "type36_size_delta": len(new_apkf) - row.data_size,
        "apkf_rebuild": meta,
        "sha256_original": sha256_file(original_pack),
        "sha256_rebuilt": sha256_file(final_path),
        "notes": [
            "EXPERIMENTAL_DIFFERENT_SIZE_ANIM_REPACK",
            "CHARACTER_PACKS_ONLY",
            "DESTINATION_SLOT_MUST_ALREADY_EXIST",
            "REBUILDS_TYPE36_APKF_AND_UPDATES_OUTER_ROW_SIZE",
            "DOES_NOT_INJECT_NEW_ANIMATION_NAMES",
            "SAME_BONES_OR_SPIDERMAN_FAMILY_IS_USER_TEST_RULE_NOT_AUTOMATICALLY_PROVEN",
            "BOOT_TEST_REQUIRED",
        ],
    }
    log_path = final_root / f"CHARACTER_ANIM_SIZE_CHANGE_REPACK_LOG_{original_pack.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (final_root / "00_PATCHED_CHARACTER_ANIM_PACK_IS_HERE.txt").write_text(
        "SM3 Character Animation Size-Change Repack Output\n"
        "================================================\n\n"
        f"Final patched PCPACK: {final_path}\n"
        f"Pack size delta: {report['pack_size_delta']}\n"
        f"Destination animation: {destination_anim.name}\n"
        f"Replacement animation: {replacement_anim.name}\n"
        "\nThis is experimental. Backup the original pack before boot testing.\n",
        encoding="utf-8",
    )
    report["log_path"] = str(log_path)
    return report



def character_anim_slot_preserve_swap(
    original_pack: Path,
    extracted_folder: Path,
    destination_anim: Path,
    replacement_anim: Path,
    output_root: Path,
) -> dict[str, Any]:
    """SM3 character animation slot-preserve repack route.

    This is the safer Spider-Man 3 version of the PCSSB audio-slot lesson:
    do not make the container bigger and do not move later offsets.  Replacement
    ANIM bytes must be the same size or smaller than the existing destination
    slot. Smaller replacements are expanded to the exact original destination
    slot size, then the proven full-extract
    rebuild backend writes a same-size PCPACK.

    It does not add new animation slots and it does not prove skeleton/bone/state
    compatibility; those remain user test rules.
    """
    from sm3_toolkit.services.pcpack_rebuild_service import rebuild_from_full_extract_tex_safe

    original_pack = Path(original_pack)
    extracted_folder = Path(extracted_folder)
    destination_anim = Path(destination_anim)
    replacement_anim = Path(replacement_anim)
    output_root = Path(output_root)

    if not original_pack.exists() or not original_pack.is_file():
        raise FileNotFoundError(f"Original character PCPACK not found: {original_pack}")
    pack_name = original_pack.name.upper()
    if pack_name not in CHARACTER_ANIM_PACKS:
        allowed = ", ".join(CHARACTER_ANIM_PACKS)
        raise ValueError(f"Release character animation slot-preserve route only supports: {allowed}")
    if not extracted_folder.exists() or not extracted_folder.is_dir():
        raise FileNotFoundError(f"Extracted character pack folder not found: {extracted_folder}")
    if not destination_anim.exists() or not destination_anim.is_file():
        raise FileNotFoundError(f"Destination animation to replace not found: {destination_anim}")
    if not replacement_anim.exists() or not replacement_anim.is_file():
        raise FileNotFoundError(f"Replacement animation not found: {replacement_anim}")
    if not destination_anim.name.lower().endswith(".anim") or not replacement_anim.name.lower().endswith(".anim"):
        raise ValueError("Both destination and replacement files must be .anim / .wrap.anim files.")

    requested_destination_anim = destination_anim
    destination_anim, destination_resolution = _resolve_destination_anim_in_extract(destination_anim, extracted_folder)

    dest_info = anim_file_info(destination_anim)
    repl_info = anim_file_info(replacement_anim)
    if repl_info.size > dest_info.size:
        raise ValueError(
            "Slot-preserve animation patch blocks bigger replacements because it must not grow the PCPACK/APKF slot. "
            f"Destination={dest_info.size} bytes, Replacement={repl_info.size} bytes. "
            "Choose a destination slot that is the same size or bigger, or use the experimental size-change route."
        )

    ts = timestamp()
    output_root.mkdir(parents=True, exist_ok=True)
    short_paths = os.environ.get("SM3_SHORT_REPACK_PATHS") == "1" or len(str(output_root)) > 90
    final_root = output_root / ("O" if short_paths else "FINAL_CHARACTER_ANIM_REPACK_OUTPUT")
    final_root.mkdir(parents=True, exist_ok=True)
    staging_parent = final_root / (f"S{ts[-6:]}" if short_paths else f"STG_{ts}")
    staged_extract = staging_parent / extracted_folder.name
    if staged_extract.exists():
        shutil.rmtree(staged_extract)
    shutil.copytree(extracted_folder, staged_extract)

    rel_dest = destination_anim.resolve().relative_to(extracted_folder.resolve())
    staged_dest = staged_extract / rel_dest
    before_sha = sha256_file(staged_dest)
    replacement_bytes = replacement_anim.read_bytes()
    padding_len = dest_info.size - len(replacement_bytes)
    padded_bytes = replacement_bytes + (b"\x00" * padding_len)
    staged_dest.write_bytes(padded_bytes)
    after_sha = sha256_file(staged_dest)

    rebuild_result = rebuild_from_full_extract_tex_safe(original_pack, staged_extract, final_root)
    rebuilt_path = Path(rebuild_result.rebuilt_pack)
    safe_dest = destination_anim.stem.replace(".", "_")[:80]
    final_name = f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_SLOTPRESERVE_{safe_dest}.PCPACK"
    final_path = final_root / final_name
    counter = 1
    while final_path.exists():
        final_path = final_root / f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_SLOTPRESERVE_{safe_dest}_{counter:03d}.PCPACK"
        counter += 1
    shutil.copy2(rebuilt_path, final_path)

    final_sha = sha256_file(final_path)
    original_sha = sha256_file(original_pack)
    final_carries_slot_change = final_sha != original_sha

    dest_family = classify_wos_tweak_family(_normalized_anim_export_name(destination_anim))
    repl_family = classify_wos_tweak_family(_normalized_anim_export_name(replacement_anim))
    if dest_family == "other" or repl_family == "other":
        boot_risk = "REVIEW_UNKNOWN_ANIM_FAMILY_BOOT_TEST_REQUIRED"
    elif dest_family == repl_family:
        boot_risk = "LOWER_RISK_SAME_ANIM_FAMILY_BOOT_TEST_REQUIRED"
    else:
        boot_risk = "HIGH_RISK_CROSS_FAMILY_BOOT_MAY_FAIL"

    result = {
        "mode": "SM3_CHARACTER_ANIM_SLOT_PRESERVE_REPACK_V5_2_54",
        "slot_preserve_method": "replacement_bytes_plus_00_padding_to_original_destination_size",
        "pcssb_audio_mod_lesson": "do_not_grow_container_or_move_later_offsets",
        "character_pack": original_pack.name,
        "character_label": CHARACTER_ANIM_PACKS[pack_name],
        "original_pack": str(original_pack),
        "extracted_folder": str(extracted_folder),
        "staged_extracted_folder": str(staged_extract),
        "requested_destination_anim": str(requested_destination_anim),
        "destination_anim_replaced": str(destination_anim),
        "destination_anim_relative_path": str(rel_dest).replace("\\", "/"),
        "destination_resolution": destination_resolution,
        "replacement_anim": str(replacement_anim),
        "destination_size": dest_info.size,
        "replacement_size": repl_info.size,
        "padding_00_bytes_added": padding_len,
        "same_size": dest_info.size == repl_info.size,
        "replacement_was_smaller_or_equal": True,
        "destination_sha256_before": before_sha,
        "replacement_sha256": repl_info.sha256,
        "padded_replacement_sha256": after_sha,
        "stage_replacement_applied": after_sha != before_sha,
        "destination_family_guess": dest_family,
        "replacement_family_guess": repl_family,
        "boot_risk": boot_risk,
        "rebuild_verdict": rebuild_result.verdict,
        "rebuilt_pack_from_rebuild_lab": rebuild_result.rebuilt_pack,
        "final_patched_pack": str(final_path),
        "blocked_count": rebuild_result.blocked_count,
        "byte_identical_after_rebuild": rebuild_result.byte_identical,
        "final_pack_sha256": final_sha,
        "original_pack_sha256": original_sha,
        "final_pack_differs_from_original": final_carries_slot_change,
        "slot_preserve_final_verification": "PASS_FINAL_PACK_CHANGED" if final_carries_slot_change else "REVIEW_FINAL_PACK_STILL_BYTE_IDENTICAL",
        "notes": [
            "NO_NEW_TAB_ROUTE_INSIDE_NEW_ANIMATION_SWAPPER",
            "ONLY_4_CHARACTER_PACKS_SUPPORTED_IN_RELEASE_ROUTE",
            "DESTINATION_ANIM_MUST_ALREADY_EXIST_IN_EXTRACTED_PACK",
            "SAFE_SLOT_PRESERVE_DOES_NOT_GROW_APKF_OR_PCPACK",
            "SAME_SIZE_OR_SMALLER_REPLACEMENT_ONLY",
            "SMALLER_REPLACEMENT_PADDED_WITH_00_BYTES",
            "SKELETON_BONE_STATE_COMPATIBILITY_NOT_AUTOMATICALLY_PROVEN",
            "BOOT_TEST_USER_REQUIRED",
            "V5_2_54_VERIFIES_FINAL_PACK_DIFFERS_FROM_ORIGINAL_FOR_REAL_PATCH",
        ],
    }
    log_path = final_root / f"CHARACTER_ANIM_SLOT_PRESERVE_REPACK_LOG_{original_pack.stem}_{ts}.json"
    log_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (final_root / "00_PATCHED_CHARACTER_ANIM_PACK_IS_HERE.txt").write_text(
        "SM3 Character Animation Slot-Preserve Repack Output\n"
        "=================================================\n\n"
        f"Final patched PCPACK: {final_path}\n"
        f"Pack: {original_pack.name}\n"
        f"Destination animation: {destination_anim.name}\n"
        f"Replacement animation: {replacement_anim.name}\n"
        f"Destination slot size: {dest_info.size}\n"
        f"Replacement size: {repl_info.size}\n"
        f"Unused slot bytes: {padding_len}\n"
        f"Boot risk: {boot_risk}\n"
        f"Final pack differs from original: {final_carries_slot_change}\n"
        "\nBackup your original character PCPACK before game testing.\n",
        encoding="utf-8",
    )
    result["log_path"] = str(log_path)
    result["marker_path"] = str(final_root / "00_PATCHED_CHARACTER_ANIM_PACK_IS_HERE.txt")
    return result

def character_anim_repack_swap(
    original_pack: Path,
    extracted_folder: Path,
    destination_anim: Path,
    replacement_anim: Path,
    output_root: Path,
    allow_size_change: bool = False,
) -> dict[str, Any]:
    """SM3 character-pack animation repack route.

    This is the no-new-tab route for the New Animation Swapper. It uses the
    proven Pack Extractor -> full extracted folder -> PCPACK Rebuild Lab backend,
    but limits the public route to the four character packs.

    v5.2.52 supports two paths:
    - same-size/same-layout path uses the proven full-extract overlay rebuild.
    - different-size ANIM path uses an experimental character-only APKF rebuild
      for the four character packs. It replaces an existing slot; it does not add
      new animation names.
    """
    from sm3_toolkit.services.pcpack_rebuild_service import rebuild_from_full_extract_tex_safe

    original_pack = Path(original_pack)
    extracted_folder = Path(extracted_folder)
    destination_anim = Path(destination_anim)
    replacement_anim = Path(replacement_anim)
    output_root = Path(output_root)

    if not original_pack.exists() or not original_pack.is_file():
        raise FileNotFoundError(f"Original character PCPACK not found: {original_pack}")
    pack_name = original_pack.name.upper()
    if pack_name not in CHARACTER_ANIM_PACKS:
        allowed = ", ".join(CHARACTER_ANIM_PACKS)
        raise ValueError(f"Release character animation repack only supports: {allowed}")
    if not extracted_folder.exists() or not extracted_folder.is_dir():
        raise FileNotFoundError(f"Extracted character pack folder not found: {extracted_folder}")
    if not destination_anim.exists() or not destination_anim.is_file():
        raise FileNotFoundError(f"Destination animation to replace not found: {destination_anim}")
    if not replacement_anim.exists() or not replacement_anim.is_file():
        raise FileNotFoundError(f"Replacement animation not found: {replacement_anim}")
    if not destination_anim.name.lower().endswith(".anim") or not replacement_anim.name.lower().endswith(".anim"):
        raise ValueError("Both destination and replacement files must be .anim / .wrap.anim files.")

    requested_destination_anim = destination_anim
    destination_anim, destination_resolution = _resolve_destination_anim_in_extract(destination_anim, extracted_folder)

    dest_info = anim_file_info(destination_anim)
    repl_info = anim_file_info(replacement_anim)
    same_size = dest_info.size == repl_info.size
    same_component_layout = (
        dest_info.looks_wrap
        and repl_info.looks_wrap
        and dest_info.wrap_header_ok
        and repl_info.wrap_header_ok
        and dest_info.wrap_component_count == repl_info.wrap_component_count
        and dest_info.wrap_component_sizes == repl_info.wrap_component_sizes
    )
    if not same_size and allow_size_change:
        result = _rebuild_character_pcpack_with_size_changed_anim(
            original_pack=original_pack,
            destination_anim=destination_anim,
            replacement_anim=replacement_anim,
            output_root=output_root,
        )
        result.update({
            "character_pack": original_pack.name,
            "character_label": CHARACTER_ANIM_PACKS[pack_name],
            "extracted_folder": str(extracted_folder),
            "requested_destination_anim": str(requested_destination_anim),
            "resolved_destination_anim": str(destination_anim),
            "destination_resolution": destination_resolution,
            "destination_size": dest_info.size,
            "replacement_size": repl_info.size,
            "same_size": False,
            "same_wrap_component_layout": same_component_layout,
            "stage_replacement_applied": True,
            "rebuild_verdict": "EXPERIMENTAL_SIZE_CHANGE_CHARACTER_ANIM_REPACK_BOOT_TEST_REQUIRED",
            "blocked_count": 0,
            "byte_identical_after_rebuild": False,
        })
        return result
    if not same_size and not allow_size_change:
        raise ValueError(
            "Different-size animation replacement needs the experimental character APKF rebuild route. "
            f"Destination={dest_info.size} bytes, Replacement={repl_info.size} bytes. "
            "Use the size-change route from the New Animation Swapper button in v5.2.52+."
        )
    if same_size and dest_info.looks_wrap and repl_info.looks_wrap and not same_component_layout:
        raise ValueError(
            "Same byte size, but WRAP component layout differs. Blocked for now to avoid character-pack crashes."
        )

    ts = timestamp()
    output_root.mkdir(parents=True, exist_ok=True)
    final_root = output_root / "FINAL_CHARACTER_ANIM_REPACK_OUTPUT"
    final_root.mkdir(parents=True, exist_ok=True)
    staging_parent = final_root / f"00_STAGE_{original_pack.stem}_{ts}"
    staged_extract = staging_parent / extracted_folder.name
    if staged_extract.exists():
        shutil.rmtree(staged_extract)
    shutil.copytree(extracted_folder, staged_extract)

    rel_dest = destination_anim.resolve().relative_to(extracted_folder.resolve())
    staged_dest = staged_extract / rel_dest
    before_sha = sha256_file(staged_dest)
    shutil.copy2(replacement_anim, staged_dest)
    after_sha = sha256_file(staged_dest)

    rebuild_result = rebuild_from_full_extract_tex_safe(original_pack, staged_extract, final_root)
    rebuilt_path = Path(rebuild_result.rebuilt_pack)
    final_name = f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_{destination_anim.stem}.PCPACK"
    final_path = final_root / final_name
    counter = 1
    while final_path.exists():
        final_path = final_root / f"{original_pack.stem}_PATCHED_CHARACTER_ANIM_{destination_anim.stem}_{counter:03d}.PCPACK"
        counter += 1
    shutil.copy2(rebuilt_path, final_path)

    result = {
        "mode": "SM3_CHARACTER_ANIM_REPACK_SWAP_V5_2_52",
        "character_pack": original_pack.name,
        "character_label": CHARACTER_ANIM_PACKS[pack_name],
        "original_pack": str(original_pack),
        "extracted_folder": str(extracted_folder),
        "staged_extracted_folder": str(staged_extract),
        "requested_destination_anim": str(requested_destination_anim),
        "destination_anim_replaced": str(destination_anim),
        "destination_anim_relative_path": str(rel_dest).replace("\\", "/"),
        "destination_resolution": destination_resolution,
        "replacement_anim": str(replacement_anim),
        "destination_size": dest_info.size,
        "replacement_size": repl_info.size,
        "same_size": same_size,
        "same_wrap_component_layout": same_component_layout,
        "destination_sha256_before": before_sha,
        "replacement_sha256": repl_info.sha256,
        "destination_sha256_after_stage": after_sha,
        "stage_replacement_applied": after_sha == repl_info.sha256,
        "rebuild_verdict": rebuild_result.verdict,
        "rebuilt_pack_from_rebuild_lab": rebuild_result.rebuilt_pack,
        "final_patched_pack": str(final_path),
        "blocked_count": rebuild_result.blocked_count,
        "byte_identical_after_rebuild": rebuild_result.byte_identical,
        "notes": [
            "NO_NEW_TAB_ROUTE_INSIDE_NEW_ANIMATION_SWAPPER",
            "ONLY_4_CHARACTER_PACKS_SUPPORTED_IN_RELEASE_ROUTE",
            "DESTINATION_ANIM_MUST_ALREADY_EXIST_IN_EXTRACTED_PACK",
            "SAME_SIZE_SAME_LAYOUT_FIRST_FOR_PROVEN_PATH",
            "DIFFERENT_SIZE_ANIM_REPACK_EXPERIMENTAL_CHARACTER_APKF_ROUTE_ENABLED",
            "ORIGINAL_PCPACK_NOT_MODIFIED",
            "BOOT_TEST_USER_REQUIRED",
        ],
    }
    log_path = final_root / f"CHARACTER_ANIM_REPACK_LOG_{original_pack.stem}_{ts}.json"
    log_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    (final_root / "00_PATCHED_CHARACTER_ANIM_PACK_IS_HERE.txt").write_text(
        "SM3 Character Animation Repack Output\n"
        "====================================\n\n"
        f"Final patched PCPACK: {final_path}\n"
        f"Pack: {original_pack.name}\n"
        f"Destination animation: {destination_anim.name}\n"
        f"Replacement animation: {replacement_anim.name}\n"
        f"Rebuild verdict: {rebuild_result.verdict}\n"
        "\nBackup your original character PCPACK before game testing.\n",
        encoding="utf-8",
    )
    result["log_path"] = str(log_path)
    result["marker_path"] = str(final_root / "00_PATCHED_CHARACTER_ANIM_PACK_IS_HERE.txt")
    return result


def classify_wos_tweak_family(*names: str) -> str:
    low = " ".join(n or "" for n in names).lower()
    if any(k in low for k in ["smb", "bs3", "black", "ichor"]):
        return "black_suit"
    if any(k in low for k in ["punch", "kick", "uppercut", "stomp", "backhand", "elbow", "exploder", "charge_attac", "rightcross", "spinpunch"]):
        return "combat"
    if any(k in low for k in ["swg", "swing", "poleswing", "rls", "rintro", "lintro", "swing2hang", "hang2swing", "dangle", "seated"]):
        return "swing"
    if any(k in low for k in ["webzip", "vertweb", "zip", "webidl", "webclimb"]):
        return "web_zip"
    if any(k in low for k in ["hang", "wall", "grind", "climb", "jumpoff"]):
        return "wall_hang"
    if any(k in low for k in ["jump", "jmp", "bounce", "jmplnch", "jumpdouble", "backflip"]):
        return "jump"
    if any(k in low for k in ["fall", "dive", "flail"]):
        return "dive_fall"
    if any(k in low for k in ["idle", "idl", "fidgit", "fidget", "relax", "introidl", "ppidl", "webidl", "lndloop"]):
        return "idle"
    return "other"


def parse_wos_tweaks_text(text: str, preset_name: str = "Imported WOS Tweaks") -> list[dict]:
    rows: list[dict] = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        offset, source_out, replacement_in = parts[:3]
        family = classify_wos_tweak_family(source_out, replacement_in)
        rows.append({
            "preset": preset_name,
            "line": line_no,
            "offset": offset,
            "source_out": source_out,
            "replacement_in": replacement_in,
            "family": family,
            "wos_route": "SOURCE_OUT_NAME_REPLACED_BY_REPLACEMENT_IN_NAME",
            "sm3_note": "Name reference only until matching extracted files/PCPACK slots are selected.",
        })
    return rows


def load_builtin_wos_tweak_presets() -> list[dict]:
    if not WOS_TWEAK_DATA_PATH.exists():
        return []
    rows = json.loads(WOS_TWEAK_DATA_PATH.read_text(encoding="utf-8"))
    for row in rows:
        row.setdefault("family", classify_wos_tweak_family(row.get("source_out", ""), row.get("replacement_in", "")))
        row.setdefault("wos_route", "SOURCE_OUT_NAME_REPLACED_BY_REPLACEMENT_IN_NAME")
        row.setdefault("sm3_note", "Name reference only until matching extracted files/PCPACK slots are selected.")
    return rows


def load_wos_tweaks_from_path(path: Path) -> list[dict]:
    rows: list[dict] = []
    if path.is_dir():
        for txt in sorted(path.glob("*.txt")):
            rows.extend(parse_wos_tweaks_text(txt.read_text(encoding="utf-8", errors="replace"), txt.stem))
        return rows
    if path.suffix.lower() == ".zip":
        import zipfile
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith("/") or not name.lower().endswith(".txt"):
                    continue
                preset = Path(name).stem
                rows.extend(parse_wos_tweaks_text(z.read(name).decode("utf-8", errors="replace"), preset))
        return rows
    return parse_wos_tweaks_text(path.read_text(encoding="utf-8", errors="replace"), path.stem)


def wos_tweak_rows_to_csv(path: Path, rows: list[dict]) -> None:
    fields = ["preset", "line", "offset", "family", "source_out", "replacement_in", "wos_route", "sm3_note"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
