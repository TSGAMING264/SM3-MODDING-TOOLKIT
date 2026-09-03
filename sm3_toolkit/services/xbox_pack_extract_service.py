from __future__ import annotations

import csv
from collections import Counter, defaultdict
import json
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# Reuse the proven Old Animation Swapper SM3/X360 parser for now.
# This service keeps extraction/report behavior separate from the Old tab UI.
from sm3_toolkit.tabs.old_animation_swapper_tab import SM3Pack, clean_name, detailed_anim_safety, hex32, sha1

XBOX_EXTS = {".xepack", ".xeapk", ".xpack", ".x360", ".bin", ".dat"}
ZIP_EXTS = {".zip"}


def family_guess(name: str) -> str:
    low = (name or "").lower()
    if any(k in low for k in ["atck", "atk", "punch", "kick", "hit", "block", "uppercut", "stomp", "rage"]):
        return "combat"
    if any(k in low for k in ["swing", "swg", "web", "zip", "vertweb"]):
        return "swing/web"
    if any(k in low for k in ["jump", "jmp", "land", "fall", "dive", "launch", "lnch"]):
        return "jump/fall"
    if any(k in low for k in ["idle", "tap", "relax"]):
        return "idle"
    if any(k in low for k in ["wall", "crawl", "crch", "crouch"]):
        return "wall/crouch"
    if any(k in low for k in ["gob", "goblin", "peter", "black", "suit"]):
        return "character-specific"
    return "unknown"


def _looks_like_pack_bytes(data: bytes) -> bool:
    return len(data) >= 0x58 and data[0x30:0x34] in (b"mash", b"hsam")


def _is_candidate_pack_file(path: Path) -> bool:
    if path.suffix.lower() in ZIP_EXTS:
        return True
    if path.suffix.lower() in XBOX_EXTS:
        return True
    name = path.name.upper()
    return "XEPACK" in name or "XEAPK" in name or "XBOX" in name or name.startswith("CH_")


def discover_xbox_pack_inputs(input_path: Path) -> List[Path]:
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        return []
    out: List[Path] = []
    for p in input_path.rglob("*"):
        if p.is_file() and _is_candidate_pack_file(p):
            out.append(p)
    return sorted(out, key=lambda p: str(p).lower())


def _extract_zip_pack_members(zip_path: Path, temp_root: Path) -> List[Path]:
    out: List[Path] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                suffix = Path(name).suffix.lower()
                upper = name.upper()
                if suffix not in XBOX_EXTS and "XEPACK" not in upper and "XEAPK" not in upper and not upper.startswith("CH_"):
                    continue
                data = z.read(info)
                if not _looks_like_pack_bytes(data) and b"APKF" not in data[:0x200000]:
                    continue
                safe = clean_name(Path(name).name, "xbox_zip_member")
                target = temp_root / f"{zip_path.stem}_{safe}"
                target.write_bytes(data)
                out.append(target)
    except Exception:
        pass
    return out


def _parse_pack_candidates(input_file: Path, temp_root: Path) -> List[Tuple[Path, SM3Pack, str]]:
    candidates: List[Path] = []
    if input_file.suffix.lower() == ".zip":
        candidates.extend(_extract_zip_pack_members(input_file, temp_root))
    else:
        candidates.append(input_file)
    parsed: List[Tuple[Path, SM3Pack, str]] = []
    for p in candidates:
        try:
            pack = SM3Pack(p)
            pack.parse()
            parsed.append((p, pack, "OK"))
        except Exception as exc:
            parsed.append((p, None, f"ERROR: {exc}"))  # type: ignore[arg-type]
    return parsed


def extract_xbox_animations(input_path: Path, output_root: Path, log=None, compact_paths: bool = False) -> Dict[str, Any]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # v5.2.83: compare auto-extract can run under long Windows toolkit paths.
    # Compact mode keeps the output tree short enough that payload writes do not fail
    # with WinError 3 / path-length-style missing-directory errors.
    run_root = output_root / (f"XAE_{timestamp}" if compact_paths else f"XBOX_ANIM_EXTRACT_{timestamp}")
    reports_root = run_root / "00_XBOX_EXTRACT_REPORTS"
    anim_root = (run_root / "A") if compact_paths else (run_root / "02_XBOX_ANIM_EXTRACTED" / "ANIM")
    reports_root.mkdir(parents=True, exist_ok=True)
    anim_root.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix="sm3_xbox_extract_"))

    def write(msg: str):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    rows: List[Dict[str, Any]] = []
    pack_summaries: List[Dict[str, Any]] = []
    extracted_count = 0
    name_only_count = 0
    parse_errors: List[Dict[str, str]] = []

    inputs = discover_xbox_pack_inputs(input_path)
    if not inputs:
        raise FileNotFoundError(f"No Xbox/XE pack files found in: {input_path}")

    try:
        for input_file in inputs:
            write(f"Scanning Xbox source: {input_file}")
            for parsed_path, pack, status in _parse_pack_candidates(input_file, temp_root):
                if pack is None:
                    parse_errors.append({"input": str(input_file), "candidate": str(parsed_path), "status": status})
                    continue
                anims = [r for r in pack.resources if (r.file_type or "").upper() == "ANIM"]
                pack_summaries.append({
                    "input": str(input_file),
                    "parsed_candidate": str(parsed_path),
                    "kind": pack.kind,
                    "platform": pack.platform,
                    "resources_total": len(pack.resources),
                    "anim_count": len(anims),
                    "errors": list(pack.errors),
                    "detect_info": pack.detect_info,
                })
                for idx, entry in enumerate(anims):
                    name = clean_name(entry.display_name, f"anim_{idx:05d}")
                    hash_text = hex32(entry.filename_hash) if entry.filename_hash else "0x00000000"
                    can_export = bool(entry.component_count and entry.total_size > 0 and "STRING" not in (entry.pack_kind or "").upper())
                    rel_payload = ""
                    status_text = "NAME_ONLY_NO_PAYLOAD" if not can_export else "EXPORTED"
                    payload_sha1 = ""
                    if can_export:
                        try:
                            payload = pack.combined_blob(entry)
                            if payload:
                                if compact_paths:
                                    short_name = clean_name(name[:40], f"anim_{idx:05d}")
                                    out_name = f"{idx:05d}_{hash_text}.{short_name}.anim"
                                else:
                                    out_name = f"{idx:05d}_{hash_text}.{name}.anim"
                                out_path = anim_root / out_name
                                out_path.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    out_path.write_bytes(payload)
                                except FileNotFoundError:
                                    # Last-resort compact fallback for Windows path/path creation edge cases.
                                    fallback_root = run_root / "A"
                                    fallback_root.mkdir(parents=True, exist_ok=True)
                                    out_name = f"{idx:05d}_{hash_text}.anim"
                                    out_path = fallback_root / out_name
                                    out_path.write_bytes(payload)
                                rel_payload = str(out_path.relative_to(run_root)).replace("\\", "/")
                                payload_sha1 = sha1(payload)
                                extracted_count += 1
                            else:
                                status_text = "NO_PAYLOAD_BYTES"
                        except Exception as exc:
                            status_text = f"EXPORT_ERROR: {exc}"
                    else:
                        name_only_count += 1
                    rows.append({
                        "status": status_text,
                        "source_input": str(input_file),
                        "parsed_candidate": str(parsed_path),
                        "platform": pack.platform,
                        "pack_kind": pack.kind,
                        "resource_index": entry.global_index,
                        "name": entry.display_name,
                        "safe_name": name,
                        "hash": hash_text,
                        "size": entry.total_size,
                        "component_count": entry.component_count,
                        "component_sizes": ";".join(str(x) for x in entry.component_sizes),
                        "family_guess": family_guess(entry.display_name),
                        "risk_hint": detailed_anim_safety(entry.display_name),
                        "payload_relpath": rel_payload,
                        "payload_sha1": payload_sha1,
                        "source_apkf_label": entry.source_apkf_label,
                        "source_outer_index": entry.source_outer_index,
                        "source_outer_hash": hex32(entry.source_outer_hash) if entry.source_outer_hash else "",
                    })
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    fields = [
        "status", "source_input", "parsed_candidate", "platform", "pack_kind", "resource_index",
        "name", "safe_name", "hash", "size", "component_count", "component_sizes",
        "family_guess", "risk_hint", "payload_relpath", "payload_sha1", "source_apkf_label",
        "source_outer_index", "source_outer_hash",
    ]
    csv_path = reports_root / "XBOX_ANIM_LIBRARY.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "mode": "SM3_XBOX_ANIMATION_EXTRACTOR_v1",
        "input_path": str(input_path),
        "output_root": str(run_root),
        "compact_paths": bool(compact_paths),
        "anim_payload_root": str(anim_root),
        "inputs_scanned": len(inputs),
        "packs_parsed": len(pack_summaries),
        "anim_rows": len(rows),
        "anim_payloads_extracted": extracted_count,
        "name_only_rows": name_only_count,
        "parse_errors": parse_errors,
        "reports": {"xbox_anim_library_csv": str(csv_path)},
        "pack_summaries": pack_summaries,
        "notes": [
            "Xbox/XE packs are extracted as source animation libraries only.",
            "Do not patch Xbox packs directly.",
            "Use extracted Xbox .anim payloads as Replacement IN against existing PC destination slots.",
            "NAME_ONLY rows are for research/listing only and cannot be used as payload replacement.",
        ],
    }
    summary_path = reports_root / "XBOX_EXTRACT_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (reports_root / "XBOX_EXTRACT_README.txt").write_text(
        "SM3 Xbox Animation Extractor\n"
        "===========================\n\n"
        "This extractor is for user-provided Xbox/XE source packs or source folders.\n"
        "It extracts animation payloads as source files for SM3 PC animation testing.\n\n"
        "Rules:\n"
        "- Original Xbox/source packs are never modified.\n"
        "- Xbox animations are source replacements only.\n"
        "- Final patching still needs an existing PC destination slot.\n"
        "- NAME_ONLY rows are not usable as payload replacement.\n\n"
        f"Animations listed: {len(rows)}\n"
        f"Payloads extracted: {extracted_count}\n"
        f"Name-only rows: {name_only_count}\n",
        encoding="utf-8",
    )
    return summary


# ---------------------------------------------------------------------------
# Xbox Lab (Dev) reports
# ---------------------------------------------------------------------------

def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not Path(path).exists():
        return []
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def _write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _counter_rows(counter: Counter, key_name: str, value_name: str = "count") -> List[Dict[str, Any]]:
    return [{key_name: str(k), value_name: int(v)} for k, v in counter.most_common()]




# ---------------------------------------------------------------------------
# Xbox Candidate Builder (Dev)
# ---------------------------------------------------------------------------

_CHAR_PACK_HINTS = ("CH_SPIDERMAN", "CH_BLACKSUIT", "CH_PETER", "CH_PLAYERGOBLIN", "CH_GOBLIN", "CH_RVBBLACK", "CH_SPIDERMAN_RVB")


def _anim_key(name: str) -> str:
    """Normalize animation names for PC<->Xbox matching."""
    raw = Path(str(name or "").replace("\\", "/")).name
    raw = re.sub(r"^\d+_", "", raw)
    raw = re.sub(r"^0x[0-9A-Fa-f]{8}\.", "", raw)
    if raw.lower().endswith(".anim"):
        raw = raw[:-5]
    return clean_name(raw, "anim").lower()


def _parse_anim_hash(name: str) -> str:
    raw = Path(str(name or "").replace("\\", "/")).name
    m = re.search(r"0x[0-9A-Fa-f]{8}", raw)
    return m.group(0).upper().replace("0X", "0x") if m else ""


def _safe_int(value: Any) -> int:
    try:
        return int(str(value or "0"))
    except Exception:
        return 0


def _pack_name_from_row(row: Dict[str, str]) -> str:
    raw = str(row.get("parsed_candidate") or row.get("source_input") or "")
    return Path(raw.replace("\\", "/")).name


def _is_character_pack_name(pack_name: str) -> bool:
    up = (pack_name or "").upper()
    return any(h in up for h in _CHAR_PACK_HINTS) or up.startswith("CH_")


def _payload_abs_path(run_root: Path, row: Dict[str, str]) -> Path | None:
    rel = str(row.get("payload_relpath") or "").strip()
    if not rel:
        return None
    p = Path(rel)
    if p.is_absolute():
        return p
    return run_root / p


def scan_pc_anim_slots(pc_folder: Path) -> List[Dict[str, Any]]:
    pc_folder = Path(pc_folder)
    slots: List[Dict[str, Any]] = []
    if not pc_folder.exists():
        return slots
    for p in sorted(pc_folder.rglob("*.anim"), key=lambda x: str(x).lower()):
        try:
            rel = str(p.relative_to(pc_folder)).replace("\\", "/")
        except Exception:
            rel = str(p)
        name_key = _anim_key(p.name)
        h = _parse_anim_hash(p.name)
        size = p.stat().st_size
        slots.append({
            "pc_relpath": rel,
            "pc_abs_path": str(p),
            "pc_name": name_key,
            "pc_hash": h,
            "pc_size": size,
            "pc_family": family_guess(name_key),
        })
    return slots


def _candidate_base_fields(row: Dict[str, str], run_root: Path) -> Dict[str, Any]:
    payload_abs = _payload_abs_path(run_root, row)
    pack_name = _pack_name_from_row(row)
    return {
        "status": row.get("status", ""),
        "source_pack": pack_name,
        "source_input": row.get("source_input", ""),
        "parsed_candidate": row.get("parsed_candidate", ""),
        "name": row.get("name", ""),
        "safe_name": row.get("safe_name", ""),
        "name_key": _anim_key(row.get("name") or row.get("safe_name") or ""),
        "hash": row.get("hash", ""),
        "size": _safe_int(row.get("size")),
        "family_guess": row.get("family_guess", ""),
        "risk_hint": row.get("risk_hint", ""),
        "payload_relpath": row.get("payload_relpath", ""),
        "payload_abs_path": str(payload_abs or ""),
        "source_apkf_label": row.get("source_apkf_label", ""),
        "source_outer_index": row.get("source_outer_index", ""),
        "source_outer_hash": row.get("source_outer_hash", ""),
        "character_pack_hint": "YES" if _is_character_pack_name(pack_name) else "NO",
    }


def _candidate_sort_key(row: Dict[str, Any]) -> tuple:
    risk_score = {"SAFE_FIRST": 0, "MEDIUM_RISK": 1, "HIGH_RISK": 2, "UNKNOWN": 3}.get(str(row.get("risk_hint") or "UNKNOWN"), 4)
    char_score = 0 if str(row.get("character_pack_hint") or "") == "YES" else 1
    fam_score = 1 if str(row.get("family_guess") or "unknown") == "unknown" else 0
    return (risk_score, char_score, fam_score, str(row.get("source_pack") or ""), str(row.get("name_key") or ""), _safe_int(row.get("size")))


def _write_candidate_bundle(candidate_root: Path, run_root: Path) -> Path:
    bundle = candidate_root / "XBOX_CANDIDATE_SEND_TO_GPT_REPORT_BUNDLE.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(candidate_root.rglob("*")):
            if f.is_file() and f.resolve() != bundle.resolve():
                rel = str(f.relative_to(run_root)).replace("\\", "/")
                z.write(f, rel)
    return bundle


def build_xbox_candidate_reports(run_root: Path, pc_slots_folder: Path | None = None, log=None) -> Dict[str, Any]:
    """Build useful candidate reports/NAS CSVs from an Xbox Lab run.

    This does not change extraction bytes. Xbox animations remain source-only.
    If a PC extracted character folder is supplied, same-name PC destination slot
    matches are used to produce NAS CSV candidates for New Animation Swapper.
    """
    run_root = Path(run_root)
    if run_root.name == "00_XBOX_LAB_REPORTS":
        run_root = run_root.parent
    reports_root = run_root / "00_XBOX_EXTRACT_REPORTS"
    lab_root = run_root / "00_XBOX_LAB_REPORTS"
    candidate_root = lab_root / "XBOX_CANDIDATE_BUILDER"
    candidate_root.mkdir(parents=True, exist_ok=True)
    csv_path = reports_root / "XBOX_ANIM_LIBRARY.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"XBOX_ANIM_LIBRARY.csv not found under {reports_root}")

    rows = _read_csv_rows(csv_path)
    payload_rows = [r for r in rows if str(r.get("payload_relpath") or "").strip()]
    candidates = [_candidate_base_fields(r, run_root) for r in payload_rows]
    candidates.sort(key=_candidate_sort_key)

    fields = [
        "status", "source_pack", "character_pack_hint", "name", "safe_name", "name_key", "hash", "size",
        "family_guess", "risk_hint", "payload_relpath", "payload_abs_path", "source_apkf_label",
        "source_outer_index", "source_outer_hash", "parsed_candidate", "source_input",
    ]

    safe_first = [c for c in candidates if str(c.get("risk_hint") or "") == "SAFE_FIRST"]
    char_pack = [c for c in candidates if str(c.get("character_pack_hint") or "") == "YES"]
    _write_csv(candidate_root / "XBOX_SAFE_FIRST_CANDIDATES.csv", safe_first, fields)
    _write_csv(candidate_root / "XBOX_CHARACTER_PACK_ANIMS.csv", char_pack, fields)

    family_files = {
        "combat": "XBOX_TOP_COMBAT_CANDIDATES.csv",
        "swing/web": "XBOX_TOP_SWING_WEB_CANDIDATES.csv",
        "jump/fall": "XBOX_TOP_JUMP_FALL_CANDIDATES.csv",
        "idle": "XBOX_TOP_IDLE_CANDIDATES.csv",
        "wall/crouch": "XBOX_TOP_WALL_CROUCH_CANDIDATES.csv",
    }
    family_counts = Counter(str(c.get("family_guess") or "unknown") for c in candidates)
    for fam, fname in family_files.items():
        fam_rows = [c for c in candidates if str(c.get("family_guess") or "") == fam]
        _write_csv(candidate_root / fname, fam_rows[:5000], fields)

    # Best duplicate by name: one recommended Xbox source row per animation name.
    by_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        key = str(c.get("name_key") or "")
        if key:
            by_name[key].append(c)
    best_dupes: List[Dict[str, Any]] = []
    for key, group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        best = sorted(group, key=_candidate_sort_key)[0].copy()
        best["duplicate_row_count"] = len(group)
        best["duplicate_source_packs"] = " | ".join(sorted({str(g.get("source_pack") or "") for g in group})[:12])
        best_dupes.append(best)
    dup_fields = fields + ["duplicate_row_count", "duplicate_source_packs"]
    _write_csv(candidate_root / "XBOX_DUPLICATE_NAME_BEST_SOURCE.csv", best_dupes, dup_fields)

    pc_slots: List[Dict[str, Any]] = []
    match_rows: List[Dict[str, Any]] = []
    nas_rows: List[Dict[str, Any]] = []
    pc_folder = Path(pc_slots_folder) if pc_slots_folder else None
    if pc_folder and pc_folder.exists():
        pc_slots = scan_pc_anim_slots(pc_folder)
        by_pc_name: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for pc in pc_slots:
            by_pc_name[str(pc.get("pc_name") or "")].append(pc)
        # For each PC destination slot, choose the best matching Xbox source with same name.
        for pc in pc_slots:
            name_key = str(pc.get("pc_name") or "")
            sources = by_name.get(name_key, [])
            if not sources:
                continue
            for src in sorted(sources, key=_candidate_sort_key)[:12]:
                pc_size = _safe_int(pc.get("pc_size"))
                src_size = _safe_int(src.get("size"))
                safe = src_size <= pc_size
                status = "SAFE_SLOT_PRESERVE" if safe else "BLOCKED_REPLACEMENT_BIGGER"
                payload_abs = Path(str(src.get("payload_abs_path") or ""))
                try:
                    # v5.2.78 fix: write the replacement path relative to the NAS CSV
                    # folder itself.  From RUN/00_XBOX_LAB_REPORTS/XBOX_CANDIDATE_BUILDER
                    # to RUN/02_XBOX_ANIM_EXTRACTED/ANIM this must usually be ../../02_...
                    repl_ref = os.path.relpath(payload_abs, candidate_root).replace("\\", "/")
                except Exception:
                    repl_ref = str(payload_abs)
                row = {
                    "candidate_status": status,
                    "enabled": "1" if safe else "0",
                    "mode": "slot_preserve" if safe else "blocked",
                    "destination": pc.get("pc_relpath", ""),
                    "replacement": repl_ref,
                    "pc_name": pc.get("pc_name", ""),
                    "pc_hash": pc.get("pc_hash", ""),
                    "pc_size": pc_size,
                    "pc_family": pc.get("pc_family", ""),
                    "xbox_name": src.get("name", ""),
                    "xbox_hash": src.get("hash", ""),
                    "xbox_size": src_size,
                    "xbox_family": src.get("family_guess", ""),
                    "xbox_risk_hint": src.get("risk_hint", ""),
                    "source_pack": src.get("source_pack", ""),
                    "payload_relpath": src.get("payload_relpath", ""),
                    "note": ("Xbox same-name source -> PC destination slot" if safe else "BLOCKED: Xbox replacement bigger than PC destination slot"),
                }
                match_rows.append(row)
                # One best candidate per PC slot for NAS export.
                if safe and not any(n.get("destination") == row["destination"] for n in nas_rows):
                    nas_rows.append(row)
        match_fields = [
            "candidate_status", "enabled", "mode", "destination", "replacement", "pc_name", "pc_hash", "pc_size", "pc_family",
            "xbox_name", "xbox_hash", "xbox_size", "xbox_family", "xbox_risk_hint", "source_pack", "payload_relpath", "note",
        ]
        _write_csv(candidate_root / "XBOX_PC_SLOT_NAME_MATCH_CANDIDATES.csv", match_rows, match_fields)
        nas_fields = ["enabled", "mode", "destination", "replacement", "note", "pc_size", "xbox_size", "pc_family", "xbox_family", "source_pack", "xbox_hash"]
        _write_csv(candidate_root / "XBOX_TO_PC_SAFE_MATCHES_NAS.csv", nas_rows, nas_fields)

    summary = {
        "mode": "SM3_XBOX_CANDIDATE_BUILDER_v1",
        "run_root": str(run_root),
        "pc_slots_folder": str(pc_folder or ""),
        "xbox_rows_total": len(rows),
        "xbox_payload_rows": len(payload_rows),
        "safe_first_candidates": len(safe_first),
        "character_pack_candidates": len(char_pack),
        "duplicate_name_best_sources": len(best_dupes),
        "pc_slots_scanned": len(pc_slots),
        "pc_same_name_match_candidates": len(match_rows),
        "safe_nas_rows": len(nas_rows),
        "family_counts": dict(family_counts),
        "reports": {
            "candidate_root": str(candidate_root),
            "safe_first_csv": str(candidate_root / "XBOX_SAFE_FIRST_CANDIDATES.csv"),
            "character_pack_anims_csv": str(candidate_root / "XBOX_CHARACTER_PACK_ANIMS.csv"),
            "pc_name_match_candidates_csv": str(candidate_root / "XBOX_PC_SLOT_NAME_MATCH_CANDIDATES.csv") if pc_slots else "",
            "safe_nas_csv": str(candidate_root / "XBOX_TO_PC_SAFE_MATCHES_NAS.csv") if pc_slots else "",
        },
        "notes": [
            "Xbox Candidate Builder does not modify Xbox packs or PC packs.",
            "Xbox animations are source-only; final patching still needs an existing PC destination slot.",
            "If pc_slots_folder is provided, XBOX_TO_PC_SAFE_MATCHES_NAS.csv can be imported into New Animation Swapper.",
        ],
    }
    bundle_path = _write_candidate_bundle(candidate_root, run_root)
    summary["reports"]["candidate_send_to_gpt_bundle"] = str(bundle_path)
    (candidate_root / "XBOX_CANDIDATE_BUILDER_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (candidate_root / "XBOX_CANDIDATE_BUILDER_SUMMARY.txt").write_text(
        "SM3 Xbox Candidate Builder\n"
        "==========================\n\n"
        f"Xbox rows total: {len(rows)}\n"
        f"Xbox payload rows: {len(payload_rows)}\n"
        f"SAFE_FIRST candidates: {len(safe_first)}\n"
        f"Character-pack candidates: {len(char_pack)}\n"
        f"Duplicate-name best sources: {len(best_dupes)}\n"
        f"PC slots scanned: {len(pc_slots)}\n"
        f"PC same-name match candidates: {len(match_rows)}\n"
        f"Safe NAS rows: {len(nas_rows)}\n\n"
        "Rules:\n"
        "- Xbox packs are source-only.\n"
        "- Final patching still needs an existing PC destination slot.\n"
        "- Bigger Xbox replacements are disabled/blocked in the NAS CSV.\n",
        encoding="utf-8",
    )
    return summary

def run_xbox_lab_scan(input_path: Path, output_root: Path, log=None, pc_slots_folder: Path | None = None) -> Dict[str, Any]:
    """Dev Xbox Lab scan for whole Xbox source folders/zips.

    This intentionally lives beside the source-only Xbox extractor. It scans all
    candidate Xbox/XE packs, extracts animation source payloads when possible,
    and writes additional lab summary/index reports for GPT/dev review.
    Original Xbox packs are never modified.
    """
    base = extract_xbox_animations(input_path, output_root, log=log)
    run_root = Path(str(base.get("output_root") or output_root))
    reports_root = run_root / "00_XBOX_EXTRACT_REPORTS"
    lab_root = run_root / "00_XBOX_LAB_REPORTS"
    lab_root.mkdir(parents=True, exist_ok=True)

    csv_path = Path(str(base.get("reports", {}).get("xbox_anim_library_csv", reports_root / "XBOX_ANIM_LIBRARY.csv")))
    rows = _read_csv_rows(csv_path)

    status_counts = Counter(str(r.get("status") or "UNKNOWN") for r in rows)
    family_counts = Counter(str(r.get("family_guess") or "unknown") for r in rows)
    risk_counts = Counter(str(r.get("risk_hint") or "UNKNOWN") for r in rows)
    pack_counts = Counter(str(r.get("parsed_candidate") or r.get("source_input") or "UNKNOWN") for r in rows)
    pack_payload_counts = Counter(str(r.get("parsed_candidate") or r.get("source_input") or "UNKNOWN") for r in rows if str(r.get("payload_relpath") or "").strip())

    by_name: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    by_hash: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        name = str(r.get("name") or r.get("safe_name") or "").strip().lower()
        h = str(r.get("hash") or "").strip().lower()
        if name:
            by_name[name].append(r)
        if h and h != "0x00000000":
            by_hash[h].append(r)

    duplicate_names = []
    for name, group in sorted(by_name.items()):
        packs = sorted({str(x.get("parsed_candidate") or x.get("source_input") or "") for x in group})
        if len(group) > 1 and len(packs) > 1:
            duplicate_names.append({
                "name": name,
                "row_count": len(group),
                "pack_count": len(packs),
                "packs": " | ".join(packs[:12]),
            })

    duplicate_hashes = []
    for h, group in sorted(by_hash.items()):
        packs = sorted({str(x.get("parsed_candidate") or x.get("source_input") or "") for x in group})
        names = sorted({str(x.get("name") or x.get("safe_name") or "") for x in group})
        if len(group) > 1 and len(packs) > 1:
            duplicate_hashes.append({
                "hash": h,
                "row_count": len(group),
                "pack_count": len(packs),
                "names": " | ".join(names[:12]),
                "packs": " | ".join(packs[:12]),
            })

    def int_size(r: Dict[str, str]) -> int:
        try:
            return int(str(r.get("size") or 0))
        except Exception:
            return 0
    top_largest = sorted(rows, key=int_size, reverse=True)[:250]

    pack_rows = []
    for pack, count in pack_counts.most_common():
        pack_rows.append({
            "parsed_candidate": pack,
            "anim_rows": count,
            "payload_rows": int(pack_payload_counts.get(pack, 0)),
        })

    _write_csv(lab_root / "XBOX_LAB_PACK_COUNTS.csv", pack_rows, ["parsed_candidate", "anim_rows", "payload_rows"])
    _write_csv(lab_root / "XBOX_LAB_STATUS_COUNTS.csv", _counter_rows(status_counts, "status"), ["status", "count"])
    _write_csv(lab_root / "XBOX_LAB_FAMILY_COUNTS.csv", _counter_rows(family_counts, "family_guess"), ["family_guess", "count"])
    _write_csv(lab_root / "XBOX_LAB_RISK_HINT_COUNTS.csv", _counter_rows(risk_counts, "risk_hint"), ["risk_hint", "count"])
    _write_csv(lab_root / "XBOX_LAB_DUPLICATE_NAMES.csv", duplicate_names, ["name", "row_count", "pack_count", "packs"])
    _write_csv(lab_root / "XBOX_LAB_DUPLICATE_HASHES.csv", duplicate_hashes, ["hash", "row_count", "pack_count", "names", "packs"])
    top_fields = [
        "status", "parsed_candidate", "name", "safe_name", "hash", "size", "component_count",
        "component_sizes", "family_guess", "risk_hint", "payload_relpath", "source_apkf_label",
        "source_outer_index", "source_outer_hash",
    ]
    _write_csv(lab_root / "XBOX_LAB_TOP_LARGEST_ANIMS.csv", top_largest, top_fields)

    lab_summary = {
        "mode": "SM3_XBOX_LAB_DEV_SCAN_v1",
        "input_path": str(input_path),
        "output_root": str(run_root),
        "extract_summary": base,
        "anim_rows": len(rows),
        "payload_rows": sum(1 for r in rows if str(r.get("payload_relpath") or "").strip()),
        "name_only_or_no_payload_rows": sum(1 for r in rows if not str(r.get("payload_relpath") or "").strip()),
        "pack_count_from_rows": len(pack_counts),
        "status_counts": dict(status_counts),
        "family_counts": dict(family_counts),
        "risk_hint_counts": dict(risk_counts),
        "duplicate_name_groups": len(duplicate_names),
        "duplicate_hash_groups": len(duplicate_hashes),
        "reports": {
            "lab_root": str(lab_root),
            "xbox_anim_library_csv": str(csv_path),
            "pack_counts_csv": str(lab_root / "XBOX_LAB_PACK_COUNTS.csv"),
            "family_counts_csv": str(lab_root / "XBOX_LAB_FAMILY_COUNTS.csv"),
            "top_largest_csv": str(lab_root / "XBOX_LAB_TOP_LARGEST_ANIMS.csv"),
        },
        "notes": [
            "Xbox Lab is a dev/research option, not the normal release extraction route.",
            "Xbox animations are source-only and must be patched into existing PC destination slots.",
            "Use this lab to scan all Xbox packs/folders/zips and inspect animation families, sizes, duplicates, and payload availability.",
        ],
    }
    (lab_root / "XBOX_LAB_SUMMARY.json").write_text(json.dumps(lab_summary, indent=2), encoding="utf-8")
    (lab_root / "XBOX_LAB_SUMMARY.txt").write_text(
        "SM3 Xbox Lab Dev Scan\n"
        "=====================\n\n"
        f"Input: {input_path}\n"
        f"Output: {run_root}\n"
        f"Packs parsed: {base.get('packs_parsed')}\n"
        f"Animation rows: {len(rows)}\n"
        f"Payload rows: {lab_summary['payload_rows']}\n"
        f"Name-only/no-payload rows: {lab_summary['name_only_or_no_payload_rows']}\n"
        f"Duplicate name groups: {len(duplicate_names)}\n"
        f"Duplicate hash groups: {len(duplicate_hashes)}\n\n"
        "Rules:\n"
        "- Xbox Lab is a dev option.\n"
        "- Xbox packs are source-only.\n"
        "- Final animation patching still needs an existing PC destination slot.\n",
        encoding="utf-8",
    )

    candidate_summary = build_xbox_candidate_reports(run_root, pc_slots_folder=pc_slots_folder, log=log)
    lab_summary["candidate_builder"] = candidate_summary
    lab_summary["reports"]["candidate_root"] = candidate_summary.get("reports", {}).get("candidate_root", "")
    lab_summary["reports"]["safe_nas_csv"] = candidate_summary.get("reports", {}).get("safe_nas_csv", "")
    (lab_root / "XBOX_LAB_SUMMARY.json").write_text(json.dumps(lab_summary, indent=2), encoding="utf-8")

    bundle_path = lab_root / "XBOX_LAB_SEND_TO_GPT_REPORT_BUNDLE.zip"
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as z:
        for folder in (reports_root, lab_root):
            if folder.exists():
                for f in sorted(folder.rglob("*")):
                    if f.is_file() and f.resolve() != bundle_path.resolve():
                        rel = str(f.relative_to(run_root)).replace("\\", "/")
                        z.write(f, rel)
    lab_summary["reports"]["send_to_gpt_bundle"] = str(bundle_path)
    (lab_root / "XBOX_LAB_SUMMARY.json").write_text(json.dumps(lab_summary, indent=2), encoding="utf-8")
    return lab_summary

# ---------------------------------------------------------------------------
# Xbox all-resource extractor (texture-research route)
# ---------------------------------------------------------------------------

def _resource_extension(file_type: str, display_name: str) -> str:
    """Return a conservative loose-file extension for an APKF resource."""
    ft = (file_type or "").strip().upper()
    suffix = Path(display_name or "").suffix
    if suffix:
        return suffix.lower()
    known = {
        "TEX": ".tex",
        "MAT": ".mat",
        "MESH": ".mesh",
        "ANIM": ".anim",
        "ASKL": ".askl",
        "SANM": ".sanm",
        "SKEL": ".skel",
        "AEPS": ".aeps",
    }
    return known.get(ft, f".{ft.lower()}" if ft and ft.isalnum() else ".bin")


def extract_xbox_resources(input_path: Path, output_root: Path, log=None) -> Dict[str, Any]:
    """Extract every payload-backed resource from an SM3 Xbox/XE pack.

    This is intentionally separate from ``extract_xbox_animations`` so the
    proven animation extraction route remains untouched.  The texture research
    build needs complete TEX component boundaries, not only combined ANIM data.

    For each resource this writes:
      * a combined loose resource file (e.g. .tex)
      * every component as ``.componentN.bin``
      * a CSV manifest with endian, component sizes and offsets

    Original source packs are read-only.
    """
    input_path = Path(input_path)
    output_root = Path(output_root)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_root = output_root / f"XBOX_RESOURCE_EXTRACT_{timestamp}"
    resources_root = run_root / "01_RESOURCES"
    components_root = run_root / "02_COMPONENTS"
    reports_root = run_root / "00_REPORTS"
    tex_root = resources_root / "TEX"
    for p in (resources_root, components_root, reports_root, tex_root):
        p.mkdir(parents=True, exist_ok=True)

    temp_root = Path(tempfile.mkdtemp(prefix="sm3_xbox_resource_extract_"))

    def write(msg: str):
        if log:
            try:
                log(msg)
            except Exception:
                pass

    rows: List[Dict[str, Any]] = []
    pack_summaries: List[Dict[str, Any]] = []
    parse_errors: List[Dict[str, str]] = []
    extracted_count = 0
    tex_count = 0
    component_file_count = 0
    duplicate_rows_skipped = 0

    inputs = discover_xbox_pack_inputs(input_path)
    if not inputs:
        raise FileNotFoundError(f"No Xbox/XE pack files found in: {input_path}")

    try:
        for input_file in inputs:
            write(f"Scanning Xbox resources: {input_file}")
            for parsed_path, pack, status in _parse_pack_candidates(input_file, temp_root):
                if pack is None:
                    parse_errors.append({"input": str(input_file), "candidate": str(parsed_path), "status": status})
                    continue

                # The legacy SM3Pack parser can expose the same Xbox resource through
                # multiple equivalent discovery passes.  DO NOT change that parser because
                # Animation Swapper depends on it.  Dedupe only this new all-resource export.
                unique_entries = []
                seen_resource_keys = set()
                pack_dupes = 0
                for r in pack.resources:
                    key = (
                        int(r.global_index), (r.file_type or "UNKNOWN").upper(),
                        int(r.filename_hash or 0), int(r.total_size or 0),
                        tuple(int(x) for x in (r.component_sizes or [])),
                        tuple((int(s), int(e)) for s,e in (r.component_offsets or [])),
                        str(r.source_apkf_label or ""), int(r.source_outer_index or 0),
                        int(r.source_outer_hash or 0), int(r.source_outer_offset or 0),
                    )
                    if key in seen_resource_keys:
                        pack_dupes += 1
                        continue
                    seen_resource_keys.add(key)
                    unique_entries.append(r)
                duplicate_rows_skipped += pack_dupes
                type_counts = Counter((r.file_type or "UNKNOWN").upper() for r in unique_entries)
                pack_summaries.append({
                    "input": str(input_file),
                    "parsed_candidate": str(parsed_path),
                    "kind": pack.kind,
                    "platform": pack.platform,
                    "outer_endian": pack.outer_endian,
                    "resources_total_raw": len(pack.resources),
                    "resources_total": len(unique_entries),
                    "duplicate_parser_rows_skipped": pack_dupes,
                    "resource_type_counts": dict(type_counts),
                    "errors": list(pack.errors),
                    "detect_info": pack.detect_info,
                })

                write(
                    f"Parsed {pack.platform} {pack.kind}: {len(unique_entries)} unique resources "
                    f"({pack_dupes} duplicate parser rows skipped); "
                    f"TEX={type_counts.get('TEX', 0)} ANIM={type_counts.get('ANIM', 0)}"
                )

                for entry in unique_entries:
                    ft = (entry.file_type or "UNKNOWN").upper()
                    idx = int(entry.global_index)
                    name = clean_name(entry.display_name, f"resource_{idx:05d}")
                    htext = hex32(entry.filename_hash) if entry.filename_hash else "0x00000000"
                    ext = _resource_extension(ft, name)
                    stem_name = name[:-len(Path(name).suffix)] if Path(name).suffix else name
                    stem_name = clean_name(stem_name, f"resource_{idx:05d}")
                    out_name = f"{idx:05d}_{htext}.{stem_name}{ext}"

                    combined_rel = ""
                    component_rels: List[str] = []
                    combined_sha1 = ""
                    status_text = "NO_PAYLOAD"
                    can_export = bool(
                        entry.component_count
                        and entry.total_size > 0
                        and "STRING" not in (entry.pack_kind or "").upper()
                    )

                    if can_export:
                        try:
                            payload = pack.combined_blob(entry)
                            if payload:
                                type_dir = resources_root / clean_name(ft, "UNKNOWN")
                                type_dir.mkdir(parents=True, exist_ok=True)
                                out_path = type_dir / out_name
                                out_path.write_bytes(payload)
                                combined_rel = str(out_path.relative_to(run_root)).replace("\\", "/")
                                combined_sha1 = sha1(payload)
                                status_text = "EXPORTED"
                                extracted_count += 1
                                if ft == "TEX":
                                    tex_count += 1

                                comp_dir = components_root / clean_name(ft, "UNKNOWN") / f"{idx:05d}_{htext}.{stem_name}"
                                comp_dir.mkdir(parents=True, exist_ok=True)
                                for ci in range(entry.component_count):
                                    comp = pack.component_blob(entry, ci)
                                    cp = comp_dir / f"component{ci}.bin"
                                    cp.write_bytes(comp)
                                    component_rels.append(str(cp.relative_to(run_root)).replace("\\", "/"))
                                    component_file_count += 1

                                # TEX gets a compact per-resource metadata file so it can be
                                # dropped directly into the decoder investigation later.
                                if ft == "TEX":
                                    tex_meta = {
                                        "platform": pack.platform,
                                        "pack_kind": pack.kind,
                                        "outer_endian": pack.outer_endian,
                                        "apkf_endian": entry.apkf_endian,
                                        "resource_index": idx,
                                        "name": entry.display_name,
                                        "hash": htext,
                                        "component_count": entry.component_count,
                                        "component_sizes": list(entry.component_sizes),
                                        "component_offsets_in_apkf": [
                                            {"start": int(s), "end": int(e), "size": int(e - s)}
                                            for s, e in entry.component_offsets
                                        ],
                                        "combined_size": len(payload),
                                        "combined_sha1": combined_sha1,
                                        "combined_relpath": combined_rel,
                                        "component_relpaths": component_rels,
                                        "source_apkf_label": entry.source_apkf_label,
                                        "source_outer_index": entry.source_outer_index,
                                        "source_outer_hash": hex32(entry.source_outer_hash) if entry.source_outer_hash else "",
                                        "source_outer_offset": entry.source_outer_offset,
                                    }
                                    (comp_dir / "texture_metadata.json").write_text(
                                        json.dumps(tex_meta, indent=2), encoding="utf-8"
                                    )
                            else:
                                status_text = "EMPTY_PAYLOAD"
                        except Exception as exc:
                            status_text = f"EXPORT_ERROR: {exc}"

                    rows.append({
                        "status": status_text,
                        "source_input": str(input_file),
                        "parsed_candidate": str(parsed_path),
                        "platform": pack.platform,
                        "pack_kind": pack.kind,
                        "outer_endian": pack.outer_endian,
                        "apkf_endian": entry.apkf_endian,
                        "resource_index": idx,
                        "file_type": ft,
                        "name": entry.display_name,
                        "safe_name": name,
                        "hash": htext,
                        "total_size": entry.total_size,
                        "component_count": entry.component_count,
                        "component_sizes": ";".join(str(x) for x in entry.component_sizes),
                        "component_offsets": ";".join(f"0x{s:X}-0x{e:X}" for s, e in entry.component_offsets),
                        "combined_relpath": combined_rel,
                        "component_relpaths": ";".join(component_rels),
                        "combined_sha1": combined_sha1,
                        "source_apkf_label": entry.source_apkf_label,
                        "source_outer_index": entry.source_outer_index,
                        "source_outer_hash": hex32(entry.source_outer_hash) if entry.source_outer_hash else "",
                        "source_outer_offset": f"0x{int(entry.source_outer_offset):X}",
                    })
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    fields = [
        "status", "source_input", "parsed_candidate", "platform", "pack_kind",
        "outer_endian", "apkf_endian", "resource_index", "file_type", "name",
        "safe_name", "hash", "total_size", "component_count", "component_sizes",
        "component_offsets", "combined_relpath", "component_relpaths", "combined_sha1",
        "source_apkf_label", "source_outer_index", "source_outer_hash", "source_outer_offset",
    ]
    csv_path = reports_root / "XBOX_RESOURCE_LIBRARY.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    tex_rows = [r for r in rows if r.get("file_type") == "TEX"]
    tex_csv_path = reports_root / "XBOX_TEX_LIBRARY.csv"
    with tex_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tex_rows)

    summary = {
        "mode": "SM3_XBOX_ALL_RESOURCE_EXTRACTOR_TEXTURE_RESEARCH_v2",
        "input_path": str(input_path),
        "output_root": str(run_root),
        "inputs_scanned": len(inputs),
        "packs_parsed": len(pack_summaries),
        "resources_listed": len(rows),
        "resources_extracted": extracted_count,
        "duplicate_parser_rows_skipped": duplicate_rows_skipped,
        "tex_resources_extracted": tex_count,
        "component_files_written": component_file_count,
        "parse_errors": parse_errors,
        "reports": {
            "xbox_resource_library_csv": str(csv_path),
            "xbox_tex_library_csv": str(tex_csv_path),
        },
        "pack_summaries": pack_summaries,
        "notes": [
            "Read-only Xbox/XE extraction; original packs are never modified.",
            "Animation Swapper code and extract_xbox_animations() are preserved unchanged.",
            "TEX resources are exported both combined and as separate components for decoder research.",
            "Combined Xbox .tex files are compatible with Texture Lab v2 read-only Xenos preview/DDS export.",
        ],
    }
    summary_path = reports_root / "XBOX_RESOURCE_EXTRACT_SUMMARY.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (reports_root / "README_XBOX_TEXTURE_RESEARCH.txt").write_text(
        "SM3 Xbox Resource Extractor - Texture Research Build\n"
        "====================================================\n\n"
        "This route preserves the Animation Swapper/parser code and adds a separate\n"
        "all-resource extraction path for Xbox TEX research.\n\n"
        f"Resources listed: {len(rows)}\n"
        f"Resources extracted: {extracted_count}\n"
        f"Duplicate parser rows skipped: {duplicate_rows_skipped}\n"
        f"TEX extracted: {tex_count}\n"
        f"Component files: {component_file_count}\n\n"
        "For each TEX, inspect the combined .tex plus component0/component1 files\n"
        "and texture_metadata.json under 02_COMPONENTS/TEX.\n",
        encoding="utf-8",
    )
    return summary
