#!/usr/bin/env python3
"""
SM3 PC Route Handler Extractor v2.24 - Beta Pack Extractor Flow
Created for TSGAMING264 public toolkit source.

Purpose:
- Spider-Man 3 PC only. WOS is not a target.
- Uses the route scan discoveries from v1.7 and starts turning them into real extraction handlers.
- Extraction/audit only. It never modifies the input PCPACK.

Locked handler routes:
1. Normal hsam outer table -> real type 0x36 APKF
2. Stub/tiny 0x28 APKF + outer-hsam-heavy packs
3. Voice/audio type 0x35 payload + tiny type 0x36 APKF stub
4. Compact header wrapper packs
5. Non-type36 APKF marker route
6. Preserve unknown outer/APKF groups raw

No external dependencies. Python 3.8+.
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import io
import os
import re
import shutil
import struct
import sys
import threading
import traceback
import webbrowser
import zipfile
import html as _html
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

TOOL_NAME = "SM3_PC_ROUTE_HANDLER_EXTRACTOR"
TOOL_VERSION = "v2.25_CLEAN_RELEASE_BETA_EXTRACTOR_UI"

SM3_MAGIC = b"hsam"
APKF_MAGIC = b"APKF"
NCH_MAGIC = b"NCH\x00"
PACK_EXTS = {".pcpack", ".pcapk", ".apkf", ".bin"}
ZIP_EXTS = {".zip"}
REPORT_ZIP_NAME = "SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE.zip"
SLIM_REPORT_ZIP_NAME = "SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE_SLIM.zip"

# v2.11: controlled payload extraction test set. These are not for scanning again;
# they are the first safe payload-output proof set after full-folder route/probe PASS.
PAYLOAD_TEST_TARGET_PACKS = [
    "CH_SPIDERMAN.PCPACK",
    "CH_BLACKSUIT.PCPACK",
    "GAME.PCPACK",
    "MEGACITY.PCPACK",
    "STORY_KINGPIN_1_COURTHOUSE.PCPACK",
    "A01.PCPACK",
    "C01.PCPACK",
    "CITY_PEDFEMALE.PCPACK",
    "VOICE_CZ01_EN.PCPACK",
]


# v2.18 optional layout/swizzle review lab. Disabled by default to avoid huge outputs.
# Enable with CLI --tex-layout-lab, GUI checkbox, or env SM3_TEX_LAYOUT_LAB=1.
TEX_LAYOUT_LAB_ENV = "SM3_TEX_LAYOUT_LAB"
TEX_LAYOUT_LAB_ALL_ENV = "SM3_TEX_LAYOUT_LAB_ALL"
TEX_LAYOUT_LAB_MAX_BYTES_ENV = "SM3_TEX_LAYOUT_LAB_MAX_BYTES"
TEX_LAYOUT_LAB_DEFAULT_MAX_BYTES = 4 * 1024 * 1024
TEX_LAYOUT_LOCK_MAP_ENV = "SM3_TEX_LAYOUT_LOCK_MAP"
TEX_LAYOUT_LOCK_VALID_MODES = {"linear_copy", "source_morton_to_linear", "source_tile4_to_linear", "source_tile8_to_linear", "source_tile16_to_linear"}
_TEX_LAYOUT_LOCK_CACHE: Dict[str, Any] = {"path": None, "mtime": None, "rows": [], "by_hash": {}, "by_hash_name": {}}
TEX_LAYOUT_SPECIAL_KEYWORDS = [
    "water", "cloud", "sky", "ocean", "river", "sea", "wave", "fog", "smoke", "mist",
    "terrain", "road", "street", "wall", "building", "window", "glass", "metal", "grass",
    "tree", "leaf", "foliage", "shadow", "light", "fx", "swirl", "noise", "mask", "alpha",
]

# Confirmed useful/seen in SM3 PC APKF outputs.
EXT_BY_TYPE = {
    "MESH": ".mesh",
    "SKEL": ".skel",
    "MAT": ".mat",
    "TEX": ".tex",
    "ANIM": ".anim",
    "ASKL": ".askl",
    "MORH": ".morh",
    "SANM": ".sanm",
    "FONT": ".font",
    "FX": ".fx",
    "CVX": ".cvx",
    "AEPS": ".aeps",
}

SM3_TABLE_START_CANDIDATES = [0x36C, 0x368, 0x364, 0x370, 0x360, 0x35C, 0x374, 0x394, 0x398, 0x3A0]
KNOWN_MARKERS = [b"hsam", b"APKF", b"mash", b"NCH\x00", b"TEX", b"MESH", b"MAT", b"ANIM", b"SKEL", b"ASKL", b"MORH", b"SANM", b"FX"]

KNOWN_HASHES = {
    0x003A261A: "Game.pcapk",
    0x07DBBC18: "Level.desc",
    0x7AD02BE9: "terrain_types.csv",
    0x5773B276: "itm_collectables.pcsx",
    0xE824EA58: "ui_game_collectible.pcsx",
    0x055E9FEC: "Master.pcgv/pcsv",
}

# ------------------------- basic helpers -------------------------

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_name(text: str, fallback: str = "unknown", max_len: int = 150) -> str:
    text = (text or fallback).replace("\x00", "")
    text = re.sub(r"[^A-Za-z0-9_.\-]+", "_", text).strip("._")
    return (text[:max_len] or fallback)


def hex32(v: int) -> str:
    return f"0x{v:08X}"


def hx(v: Optional[int]) -> str:
    if v is None:
        return ""
    return f"0x{v:X}"


def u32le(data: bytes, off: int) -> Optional[int]:
    if off < 0 or off + 4 > len(data):
        return None
    return struct.unpack_from("<I", data, off)[0]


def magic_at(data: bytes, off: int, size: int = 16) -> bytes:
    if off < 0 or off >= len(data):
        return b""
    return data[off:off + size]


def ascii_sig(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data[:16])


def hexbytes(data: bytes, n: int = 16) -> str:
    return " ".join(f"{x:02X}" for x in data[:n])


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    ensure_dir(path.parent)
    if fieldnames is None:
        keys: List[str] = []
        for row in rows:
            for key in row.keys():
                if key not in keys:
                    keys.append(key)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_cstr(data: bytes, off: int, max_len: int = 512) -> str:
    if off < 0 or off >= len(data):
        return ""
    end = off
    limit = min(len(data), off + max_len)
    while end < limit and data[end] != 0:
        end += 1
    return data[off:end].decode("utf-8", errors="replace")


def find_all(data: bytes, needle: bytes, max_hits: int = 4096) -> List[int]:
    hits: List[int] = []
    pos = 0
    while len(hits) < max_hits:
        idx = data.find(needle, pos)
        if idx < 0:
            break
        hits.append(idx)
        pos = idx + 1
    return hits


def extract_ascii_strings(data: bytes, min_len: int = 4, max_count: int = 600) -> List[Tuple[int, str]]:
    rows: List[Tuple[int, str]] = []
    for match in re.finditer(rb"[A-Za-z0-9_ .\\/\-:]{%d,}" % min_len, data):
        s = match.group(0).decode("latin1", errors="replace").strip()
        if s:
            rows.append((match.start(), s[:240]))
        if len(rows) >= max_count:
            break
    return rows


def inner_extension(file_type: str, filename: str) -> str:
    t = (file_type or "").upper()
    if t in EXT_BY_TYPE:
        return EXT_BY_TYPE[t]
    n = (filename or "").lower()
    for ext in [".mesh", ".mat", ".tex", ".anim", ".askl", ".skel", ".fx", ".font", ".desc", ".csv", ".pcsx", ".pcgv", ".pcsv", ".pcps", ".pcapk"]:
        if n.endswith(ext):
            return ext
    return "." + t.lower() if t else ".bin"


def sniff_outer_ext(payload: bytes, strings: str = "") -> Tuple[str, str, str]:
    sig = payload[:4]
    low = (strings or "").lower()
    if sig == b"APKF":
        return ".apkf", "APKF_ARCHIVE", "magic_APKF"
    if sig == b"hsam":
        return ".hsam", "NESTED_HSAM", "magic_hsam"
    if sig == b"CVXL":
        return ".cvxl", "KNOWN_DIRECT", "magic_CVXL"
    if sig == b"ElmS":
        return ".elms", "KNOWN_DIRECT", "magic_ElmS"
    if sig == b"NumW":
        return ".numw", "KNOWN_DIRECT", "magic_NumW"
    if payload[:8].startswith(b"__IdvSpt") or sig == b"\xE8\x03\x00\x00":
        return ".spt", "KNOWN_DIRECT", "speedtree_candidate"
    for ext in [".desc", ".csv", ".pcsx", ".pcgv", ".pcsv", ".pcps", ".fx", ".font", ".ent", ".environment", ".outdoors", ".wind"]:
        if ext[1:] in low or ext in low:
            return ext, "KNOWN_DIRECT", "string_hint_" + ext
    return ".bin", "UNKNOWN_OUTER", "unknown_direct_payload"


def sample_strings(data: bytes, off: int, size: int, limit: int = 8192, max_strings: int = 20) -> str:
    if off < 0 or off >= len(data) or size <= 0:
        return ""
    blob = data[off:off + min(size, limit)]
    vals: List[str] = []
    for _off, text in extract_ascii_strings(blob, min_len=4, max_count=max_strings * 3):
        if text not in vals:
            vals.append(text)
        if len(vals) >= max_strings:
            break
    return " | ".join(vals)


def split_name_tokens(value: str) -> List[str]:
    """Tokenize a resource name for browse/index hinting."""
    base = Path(value or "").stem.lower()
    toks = [t for t in re.split(r"[^a-z0-9]+", base) if t]
    return toks[:40]


def size_bucket(size: Any) -> str:
    n = _safe_int(size)
    if n <= 0:
        return "empty"
    if n < 256:
        return "tiny_lt_256"
    if n < 4096:
        return "small_lt_4k"
    if n < 65536:
        return "medium_lt_64k"
    if n < 1024 * 1024:
        return "large_lt_1mb"
    return "huge_ge_1mb"


def component_layout(row: Dict[str, Any]) -> str:
    count = _safe_int(row.get("component_count"))
    sizes = []
    for i in range(count):
        sizes.append(str(_safe_int(row.get(f"component{i}_size"))))
    return f"{count}c:" + "+".join(sizes)


def texture_role_hint(name: str) -> str:
    n = (name or "").lower()
    if any(x in n for x in ["_nor", "normal", "norm"]):
        return "normal_map"
    if any(x in n for x in ["_dif", "diff", "diffuse", "albedo"]):
        return "diffuse_map"
    if any(x in n for x in ["_spe", "spec"]):
        return "specular_map"
    if any(x in n for x in ["_rfl", "reflect", "env"]):
        return "reflection_environment_map"
    if any(x in n for x in ["_ao", "ambient"]):
        return "ambient_occlusion_map"
    if "web" in n:
        return "webbing_or_web_effect_texture"
    return "texture_unknown_role"


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _is_plausible_tex_dim(n: int) -> bool:
    # SM3 PC textures are usually powers of two, but keep common non-powers
    # allowed for odd UI/effect resources. Keep the parser conservative.
    if n < 1 or n > 8192:
        return False
    if _is_power_of_two(n):
        return True
    return n % 4 == 0 and n <= 4096


def _dds_payload_size(width: int, height: int, mips: int, fmt: str) -> int:
    total = 0
    w = max(1, width)
    h = max(1, height)
    mips = max(1, min(16, mips))
    for _ in range(mips):
        if fmt == "DXT1_BC1":
            total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
        elif fmt in {"DXT3_BC2", "DXT5_BC3", "ATI2_BC5"}:
            total += max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
        elif fmt == "BGRA32":
            total += w * h * 4
        elif fmt == "RGB24":
            total += w * h * 3
        elif fmt == "L8_A8_OR_ALPHA8":
            total += w * h
        w = max(1, w // 2)
        h = max(1, h // 2)
    return total


def _candidate_values_from_descriptor(desc: bytes) -> Tuple[List[Tuple[int, int, str]], List[Tuple[int, str]]]:
    """Find plausible width/height and mip values inside a TEX component0 descriptor.

    This is intentionally a heuristic parser. It does not claim the exact SM3 TEX
    descriptor schema yet; it finds fields that match the payload size and records
    the offsets so later reverse-engineering can lock the schema.
    """
    dims: List[Tuple[int, int, str]] = []
    mips: List[Tuple[int, str]] = []
    seen_dims = set()
    seen_mips = set()
    limit = min(len(desc), 0x100)

    for off in range(0, max(0, limit - 3), 2):
        w = int.from_bytes(desc[off:off+2], "little", signed=False)
        h = int.from_bytes(desc[off+2:off+4], "little", signed=False)
        if _is_plausible_tex_dim(w) and _is_plausible_tex_dim(h) and max(w, h) / max(1, min(w, h)) <= 16:
            key = (w, h, f"u16@0x{off:X}")
            if key not in seen_dims:
                seen_dims.add(key)
                dims.append(key)

    for off in range(0, max(0, limit - 7), 4):
        w = int.from_bytes(desc[off:off+4], "little", signed=False)
        h = int.from_bytes(desc[off+4:off+8], "little", signed=False)
        if _is_plausible_tex_dim(w) and _is_plausible_tex_dim(h) and max(w, h) / max(1, min(w, h)) <= 16:
            key = (w, h, f"u32@0x{off:X}")
            if key not in seen_dims:
                seen_dims.add(key)
                dims.append(key)

    for off in range(0, limit):
        v = desc[off]
        if 1 <= v <= 16:
            key = (v, f"u8@0x{off:X}")
            if key not in seen_mips:
                seen_mips.add(key)
                mips.append(key)
    for off in range(0, max(0, limit - 1), 2):
        v = int.from_bytes(desc[off:off+2], "little", signed=False)
        if 1 <= v <= 16:
            key = (v, f"u16@0x{off:X}")
            if key not in seen_mips:
                seen_mips.add(key)
                mips.append(key)

    # Keep search bounded for full-folder runs.
    return dims[:96], mips[:96]


def infer_tex_metadata_from_components(name: str, component_blobs: List[Tuple[int, bytes, int, int]]) -> Dict[str, Any]:
    """v2.15 conservative TEX metadata parser.

    SM3 TEX resources normally have descriptor/component0 + image payload/component1.
    This parser guesses width/height/mips/format by reading plausible descriptor values
    and matching them to the actual component1 payload size. It is a metadata/review
    parser only; it does not decode or rewrite texture bytes.
    """
    result: Dict[str, Any] = {
        "tex_metadata_parser_version": "v2.16_tex_review_triage_priority",
        "tex_parse_status": "NOT_TEX_OR_NO_COMPONENTS",
        "tex_descriptor_size": 0,
        "tex_payload_size": 0,
        "tex_width_guess": "",
        "tex_height_guess": "",
        "tex_mip_count_guess": "",
        "tex_format_guess": "",
        "tex_payload_expected_size": "",
        "tex_payload_size_match": "",
        "tex_metadata_confidence": "NONE",
        "tex_guess_reason": "",
        "tex_dimension_field_hint": "",
        "tex_mip_field_hint": "",
        "tex_role_hint": texture_role_hint(name),
        "tex_descriptor_hex_first64": "",
    }
    if len(component_blobs) < 2:
        result.update({"tex_parse_status": "NO_COMPONENT1_PAYLOAD", "tex_guess_reason": "TEX has fewer than 2 components", "tex_review_reason": "NO_COMPONENT1_PAYLOAD"})
        if component_blobs:
            result["tex_descriptor_size"] = len(component_blobs[0][1])
            result["tex_descriptor_hex_first64"] = hexbytes(component_blobs[0][1], 64)
        return result

    desc = component_blobs[0][1]
    payload = component_blobs[1][1]
    payload_size = len(payload)
    result.update({
        "tex_parse_status": "HEURISTIC_PARSED",
        "tex_descriptor_size": len(desc),
        "tex_payload_size": payload_size,
        "tex_descriptor_hex_first64": hexbytes(desc, 64),
    })
    dims, mips = _candidate_values_from_descriptor(desc)
    if not dims:
        result.update({"tex_parse_status": "NO_DIMENSION_CANDIDATE", "tex_guess_reason": "no plausible width/height values found in component0", "tex_review_reason": "NO_PLAUSIBLE_DIMENSION_IN_COMPONENT0"})
        return result

    fmt_order = ["DXT1_BC1", "DXT5_BC3", "DXT3_BC2", "ATI2_BC5", "BGRA32", "L8_A8_OR_ALPHA8", "RGB24"]
    best = None
    best_score = -10**18
    mip_candidates = mips or [(m, "synthetic") for m in range(1, 17)]
    for w, h, dim_hint in dims:
        for mip_count, mip_hint in mip_candidates:
            if mip_count < 1 or mip_count > 16:
                continue
            # Mip count cannot exceed the logical full mip chain by much.
            max_chain = 1
            tw, th = w, h
            while tw > 1 or th > 1:
                max_chain += 1
                tw = max(1, tw // 2)
                th = max(1, th // 2)
            if mip_count > max_chain:
                continue
            for fmt in fmt_order:
                expected = _dds_payload_size(w, h, mip_count, fmt)
                diff = abs(expected - payload_size)
                exact = expected == payload_size
                # Prefer exact size match, power-of-two dims, descriptor mips over synthetic.
                score = 0
                score += 1000000 if exact else max(0, 100000 - diff)
                score += 5000 if _is_power_of_two(w) and _is_power_of_two(h) else 0
                score += 1000 if mip_hint != "synthetic" else 0
                score += 250 if fmt in {"DXT1_BC1", "DXT5_BC3", "DXT3_BC2"} else 0
                score -= (w * h) // 4096
                if score > best_score:
                    best_score = score
                    best = (w, h, mip_count, fmt, expected, diff, dim_hint, mip_hint, exact)

    if not best:
        result.update({"tex_parse_status": "NO_SIZE_MATCH_CANDIDATE", "tex_guess_reason": "no payload-size compatible candidate", "tex_review_reason": "NO_PAYLOAD_SIZE_COMPATIBLE_CANDIDATE"})
        return result

    w, h, mip_count, fmt, expected, diff, dim_hint, mip_hint, exact = best
    if exact:
        conf = "HIGH_EXACT_PAYLOAD_SIZE_MATCH"
        review_reason = "OK_EXACT_PAYLOAD_SIZE_MATCH"
    elif payload_size and diff / max(1, payload_size) <= 0.02:
        conf = "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH"
        review_reason = "NEAR_PAYLOAD_SIZE_MATCH_REVIEW_OPTIONAL"
    else:
        conf = "LOW_BEST_EFFORT_GUESS"
        ratio = diff / max(1, payload_size)
        if ratio <= 0.10:
            review_reason = "LOW_PAYLOAD_SIZE_MISMATCH_UNDER_10_PERCENT"
        elif ratio <= 0.50:
            review_reason = "LOW_PAYLOAD_SIZE_MISMATCH_UNDER_50_PERCENT"
        else:
            review_reason = "LOW_PAYLOAD_SIZE_MISMATCH_OVER_50_PERCENT"
    result.update({
        "tex_width_guess": w,
        "tex_height_guess": h,
        "tex_mip_count_guess": mip_count,
        "tex_format_guess": fmt,
        "tex_payload_expected_size": expected,
        "tex_payload_size_match": bool(exact),
        "tex_metadata_confidence": conf,
        "tex_guess_reason": f"payload_size={payload_size}; expected={expected}; diff={diff}",
        "tex_review_reason": review_reason,
        "tex_payload_size_diff": diff,
        "tex_payload_size_diff_ratio": round(diff / max(1, payload_size), 6),
        "tex_dimension_field_hint": dim_hint,
        "tex_mip_field_hint": mip_hint,
    })
    return result


def _dds_fourcc(fmt: str) -> Optional[bytes]:
    return {
        "DXT1_BC1": b"DXT1",
        "DXT3_BC2": b"DXT3",
        "DXT5_BC3": b"DXT5",
        "ATI2_BC5": b"ATI2",
    }.get(fmt)


def _dds_header(width: int, height: int, mip_count: int, fmt: str, payload_size: int) -> Optional[bytes]:
    """Create a minimal DDS header for exact/strong TEX metadata rows.

    v2.15: This does not decode or recompress. It wraps the already-extracted
    component1 payload with a standard DDS header when the component0 metadata
    guess is strong enough. Supports DXT1/DXT3/DXT5/ATI2, BGRA32, and RGB24.
    """
    width = int(width or 0)
    height = int(height or 0)
    mip_count = int(mip_count or 1)
    if width <= 0 or height <= 0 or payload_size <= 0:
        return None
    flags = 0x0002100F  # CAPS | HEIGHT | WIDTH | PITCH/LINEARSIZE | PIXELFORMAT | MIPMAPCOUNT
    caps = 0x1000
    caps2 = 0
    linear_size = payload_size
    pf_flags = 0
    fourcc = b"\x00\x00\x00\x00"
    rgb_bit_count = 0
    r_mask = g_mask = b_mask = a_mask = 0
    fcc = _dds_fourcc(fmt)
    if fcc:
        pf_flags = 0x4  # DDPF_FOURCC
        fourcc = fcc
    elif fmt == "BGRA32":
        pf_flags = 0x41  # DDPF_RGB | DDPF_ALPHAPIXELS
        rgb_bit_count = 32
        r_mask = 0x00FF0000
        g_mask = 0x0000FF00
        b_mask = 0x000000FF
        a_mask = 0xFF000000
        linear_size = width * 4
    elif fmt == "RGB24":
        # v2.15: uncompressed 24-bit RGB/BGR-style DDS header.
        # DDS channel masks use the common byte layout used by many viewers.
        pf_flags = 0x40  # DDPF_RGB
        rgb_bit_count = 24
        r_mask = 0x00FF0000
        g_mask = 0x0000FF00
        b_mask = 0x000000FF
        a_mask = 0x00000000
        linear_size = width * 3
    else:
        return None
    if mip_count > 1:
        caps |= 0x400000 | 0x8  # MIPMAP | COMPLEX
    header = struct.pack(
        "<4s" + "I"*31,
        b"DDS ",
        124,
        flags,
        height,
        width,
        linear_size,
        0,
        mip_count,
        *([0] * 11),
        32,
        pf_flags,
        int.from_bytes(fourcc, "little"),
        rgb_bit_count,
        r_mask,
        g_mask,
        b_mask,
        a_mask,
        caps,
        caps2,
        0,
        0,
        0,
    )
    return header



def _normalize_hash_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        if text.lower().startswith("0x"):
            return f"0x{int(text, 16):08X}"
        return f"0x{int(text, 10):08X}"
    except Exception:
        m = re.search(r"0x[0-9a-fA-F]{1,8}", text)
        if m:
            return f"0x{int(m.group(0), 16):08X}"
    return text.upper()


def _normalize_tex_name_key(value: Any) -> str:
    return Path(str(value or "").strip()).stem.lower()


def _lock_map_blank_result() -> Dict[str, Any]:
    return {
        "tex_layout_lock_status": "NO_LOCK_MAP",
        "tex_layout_locked_mode": "",
        "tex_layout_lock_source": "",
        "tex_layout_lock_reason": "layout_lock_map_not_loaded",
    }


def _load_tex_layout_lock_map_from_path(path: Path) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    by_hash: Dict[str, Dict[str, Any]] = {}
    by_hash_name: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if not path or not path.exists():
        return {"rows": [], "by_hash": {}, "by_hash_name": {}}
    def accept_row(raw: Dict[str, Any], source_label: str) -> None:
        h = _normalize_hash_key(raw.get("hash") or raw.get("filename_hash") or raw.get("tex_hash") or raw.get("resource_hash"))
        name = _normalize_tex_name_key(raw.get("tex_name") or raw.get("name") or raw.get("filename") or raw.get("resource_name"))
        mode = str(raw.get("best_layout") or raw.get("layout") or raw.get("mode") or raw.get("selected_layout") or "").strip()
        note = str(raw.get("notes") or raw.get("note") or raw.get("reason") or "")
        if not h or not mode:
            return
        if mode not in TEX_LAYOUT_LOCK_VALID_MODES:
            return
        row = {
            "hash": h,
            "tex_name": name,
            "best_layout": mode,
            "notes": note,
            "source": source_label,
        }
        rows.append(row)
        if name:
            by_hash_name[(h, name)] = row
        # hash-only fallback: first wins, so a very specific hash/name row can still override above
        by_hash.setdefault(h, row)
    try:
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
            if isinstance(data, dict) and isinstance(data.get("locks"), list):
                for item in data.get("locks", []):
                    if isinstance(item, dict):
                        accept_row(item, str(path))
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        accept_row(item, str(path))
        else:
            with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
                for raw in csv.DictReader(fh):
                    accept_row(raw, str(path))
    except Exception:
        return {"rows": [], "by_hash": {}, "by_hash_name": {}}
    return {"rows": rows, "by_hash": by_hash, "by_hash_name": by_hash_name}


def _get_tex_layout_lock_map() -> Dict[str, Any]:
    path_text = os.environ.get(TEX_LAYOUT_LOCK_MAP_ENV, "").strip().strip('"')
    if not path_text:
        _TEX_LAYOUT_LOCK_CACHE.update({"path": None, "mtime": None, "rows": [], "by_hash": {}, "by_hash_name": {}})
        return _TEX_LAYOUT_LOCK_CACHE
    path = Path(path_text)
    try:
        mtime = path.stat().st_mtime if path.exists() else None
    except Exception:
        mtime = None
    if _TEX_LAYOUT_LOCK_CACHE.get("path") == str(path) and _TEX_LAYOUT_LOCK_CACHE.get("mtime") == mtime:
        return _TEX_LAYOUT_LOCK_CACHE
    loaded = _load_tex_layout_lock_map_from_path(path)
    _TEX_LAYOUT_LOCK_CACHE.update({"path": str(path), "mtime": mtime, **loaded})
    return _TEX_LAYOUT_LOCK_CACHE


def lookup_tex_layout_lock(filename_hash: int, tex_name: str) -> Dict[str, Any]:
    cache = _get_tex_layout_lock_map()
    if not cache.get("path"):
        return _lock_map_blank_result()
    h = f"0x{int(filename_hash) & 0xFFFFFFFF:08X}"
    n = _normalize_tex_name_key(tex_name)
    row = cache.get("by_hash_name", {}).get((h, n))
    if row:
        return {
            "tex_layout_lock_status": "LOCK_FOUND_HASH_NAME",
            "tex_layout_locked_mode": row.get("best_layout", ""),
            "tex_layout_lock_source": row.get("source", ""),
            "tex_layout_lock_reason": row.get("notes", "locked_by_hash_and_name"),
        }
    row = cache.get("by_hash", {}).get(h)
    if row:
        return {
            "tex_layout_lock_status": "LOCK_FOUND_HASH_ONLY",
            "tex_layout_locked_mode": row.get("best_layout", ""),
            "tex_layout_lock_source": row.get("source", ""),
            "tex_layout_lock_reason": row.get("notes", "locked_by_hash"),
        }
    return {
        "tex_layout_lock_status": "NO_LOCK_FOR_TEXTURE",
        "tex_layout_locked_mode": "",
        "tex_layout_lock_source": cache.get("path") or "",
        "tex_layout_lock_reason": "layout_map_loaded_but_texture_not_locked",
    }


def write_tex_layout_lock_map_load_report(reports: Path) -> None:
    cache = _get_tex_layout_lock_map()
    source = cache.get("path") or ""
    rows = list(cache.get("rows") or [])
    write_csv(reports / "TEX_LAYOUT_LOCK_MAP_LOADED.csv", rows)
    summary = {
        "layout_lock_map_source": source,
        "layout_lock_row_count": len(rows),
        "valid_modes": sorted(TEX_LAYOUT_LOCK_VALID_MODES),
        "note": "v2.20 layout locks can force DDS export/layout candidate choice by texture hash/name. Original packs are never modified.",
    }
    write_json(reports / "TEX_LAYOUT_LOCK_MAP_LOADED.json", summary)
    (reports / "TEX_LAYOUT_LOCK_MAP_LOADED.txt").write_text("\n".join(f"{k}: {v}" for k, v in summary.items()) + "\n", encoding="utf-8")

def maybe_export_tex_dds(out_root: Path, tex_name: str, filename_hash: int, metadata: Dict[str, Any], payload: bytes) -> Dict[str, Any]:
    """v2.20 DDS export for strong TEX metadata rows with optional layout lock map.

    DDS export remains conservative. High-confidence exact rows are wrapped with a DDS
    header. If a layout-lock CSV says a non-linear candidate is the approved visual
    layout, that candidate is written for DDS export. Otherwise the original linear
    payload is used. Original PCPACKs are never modified.
    """
    lock = lookup_tex_layout_lock(filename_hash, tex_name)
    base_result = {
        "tex_layout_lock_status": lock.get("tex_layout_lock_status", ""),
        "tex_layout_locked_mode": lock.get("tex_layout_locked_mode", ""),
        "tex_layout_lock_source": lock.get("tex_layout_lock_source", ""),
        "tex_layout_lock_reason": lock.get("tex_layout_lock_reason", ""),
        "tex_dds_layout_mode": "linear_copy",
        "tex_dds_layout_lock_applied": False,
    }
    status = "NOT_EXPORTED"
    reason = "not_requested_or_not_exact"
    path = ""
    conf = str(metadata.get("tex_metadata_confidence") or "")
    fmt = str(metadata.get("tex_format_guess") or "")
    try:
        w = int(metadata.get("tex_width_guess") or 0)
        h = int(metadata.get("tex_height_guess") or 0)
        mips = int(metadata.get("tex_mip_count_guess") or 1)
    except Exception:
        w = h = 0
        mips = 1
    exact = str(metadata.get("tex_payload_size_match") or "").lower() in {"true", "1", "yes"}
    if conf != "HIGH_EXACT_PAYLOAD_SIZE_MATCH" or not exact:
        return {**base_result, "tex_dds_export_status": status, "tex_dds_export_reason": reason, "tex_dds_export_file": path}

    dds_payload = payload
    mode = str(lock.get("tex_layout_locked_mode") or "linear_copy")
    if mode and mode in TEX_LAYOUT_LOCK_VALID_MODES:
        base_result["tex_dds_layout_mode"] = mode
        if mode != "linear_copy":
            transformed = _transform_texture_payload_layout(payload, w, h, mips, fmt, mode)
            if transformed is not None:
                dds_payload = transformed
                base_result["tex_dds_layout_lock_applied"] = True
            else:
                base_result["tex_layout_lock_status"] = "LOCK_TRANSFORM_FAILED"
                base_result["tex_layout_lock_reason"] = f"locked_mode_transform_failed:{mode}"
                # Fall back to linear export instead of dropping a high-confidence texture.
                base_result["tex_dds_layout_mode"] = "linear_copy_fallback_after_lock_transform_failed"
        elif lock.get("tex_layout_lock_status") in {"LOCK_FOUND_HASH_NAME", "LOCK_FOUND_HASH_ONLY"}:
            base_result["tex_dds_layout_lock_applied"] = True
    elif mode:
        base_result["tex_layout_lock_status"] = "LOCK_INVALID_MODE"
        base_result["tex_layout_lock_reason"] = f"invalid_locked_mode:{mode}"

    header = _dds_header(w, h, mips, fmt, len(dds_payload))
    if not header:
        return {**base_result, "tex_dds_export_status": "SKIPPED_UNSUPPORTED_DDS_HEADER", "tex_dds_export_reason": f"unsupported_format_for_dds_header:{fmt}", "tex_dds_export_file": path}
    try:
        folder = ensure_dir(out_root / "05_TEX_DDS_EXPORT" / fmt)
        safe = clean_name(tex_name, "tex")
        mode_suffix = "" if base_result["tex_dds_layout_mode"] == "linear_copy" else f".{clean_name(str(base_result['tex_dds_layout_mode']), 'layout')}"
        fname = f"{hex32(filename_hash)}.{safe}.{w}x{h}.m{mips}.{fmt}{mode_suffix}.dds"
        dst = folder / clean_name(fname, "texture.dds")
        dst.write_bytes(header + dds_payload)
        applied = "locked_layout" if base_result.get("tex_dds_layout_lock_applied") else "linear"
        return {**base_result, "tex_dds_export_status": "DDS_EXPORT_OK", "tex_dds_export_reason": f"high_exact_payload_wrapped_with_{fmt}_dds_header:{applied}", "tex_dds_export_file": str(dst), "tex_dds_export_size": len(header) + len(dds_payload)}
    except Exception as exc:
        return {**base_result, "tex_dds_export_status": "DDS_EXPORT_FAILED", "tex_dds_export_reason": str(exc), "tex_dds_export_file": path}


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}


def _tex_layout_lab_enabled() -> bool:
    return _env_truthy(TEX_LAYOUT_LAB_ENV)


def _tex_layout_lab_all_enabled() -> bool:
    return _env_truthy(TEX_LAYOUT_LAB_ALL_ENV)


def _tex_layout_lab_max_bytes() -> int:
    try:
        return int(os.environ.get(TEX_LAYOUT_LAB_MAX_BYTES_ENV, str(TEX_LAYOUT_LAB_DEFAULT_MAX_BYTES)))
    except Exception:
        return TEX_LAYOUT_LAB_DEFAULT_MAX_BYTES


def _morton2(x: int, y: int) -> int:
    # small, dependency-free 2D Morton order helper for texture-layout review candidates
    answer = 0
    bit = 0
    while (1 << bit) <= max(x, y, 1):
        answer |= ((x >> bit) & 1) << (2 * bit)
        answer |= ((y >> bit) & 1) << (2 * bit + 1)
        bit += 1
    return answer


def _reorder_source_morton_to_linear(seg: bytes, unit_w: int, unit_h: int, unit_bytes: int) -> Optional[bytes]:
    total_units = unit_w * unit_h
    if len(seg) != total_units * unit_bytes:
        return None
    out = bytearray(len(seg))
    positions = [(_morton2(x, y), x, y) for y in range(unit_h) for x in range(unit_w)]
    positions.sort(key=lambda t: t[0])
    for src_i, (_m, x, y) in enumerate(positions):
        src = src_i * unit_bytes
        dst = (y * unit_w + x) * unit_bytes
        out[dst:dst+unit_bytes] = seg[src:src+unit_bytes]
    return bytes(out)


def _reorder_source_tiled_to_linear(seg: bytes, unit_w: int, unit_h: int, unit_bytes: int, tile: int) -> Optional[bytes]:
    total_units = unit_w * unit_h
    if len(seg) != total_units * unit_bytes:
        return None
    out = bytearray(len(seg))
    src_i = 0
    for ty in range(0, unit_h, tile):
        for tx in range(0, unit_w, tile):
            for y in range(ty, min(unit_h, ty + tile)):
                for x in range(tx, min(unit_w, tx + tile)):
                    src = src_i * unit_bytes
                    dst = (y * unit_w + x) * unit_bytes
                    out[dst:dst+unit_bytes] = seg[src:src+unit_bytes]
                    src_i += 1
    return bytes(out)


def _tex_mip_unit_info(width: int, height: int, fmt: str, mip_index: int) -> Tuple[int, int, int, int]:
    w = max(1, width >> mip_index)
    h = max(1, height >> mip_index)
    if fmt == "DXT1_BC1":
        return max(1, (w + 3) // 4), max(1, (h + 3) // 4), 8, 4
    if fmt in {"DXT3_BC2", "DXT5_BC3", "ATI2_BC5"}:
        return max(1, (w + 3) // 4), max(1, (h + 3) // 4), 16, 4
    if fmt == "BGRA32":
        return w, h, 4, 1
    if fmt == "RGB24":
        return w, h, 3, 1
    if fmt == "L8_A8_OR_ALPHA8":
        return w, h, 1, 1
    return 0, 0, 0, 0


def _transform_texture_payload_layout(payload: bytes, width: int, height: int, mips: int, fmt: str, mode: str) -> Optional[bytes]:
    out = bytearray()
    off = 0
    for mip in range(max(1, mips)):
        unit_w, unit_h, unit_bytes, _pixels_per_unit = _tex_mip_unit_info(width, height, fmt, mip)
        if unit_w <= 0 or unit_h <= 0 or unit_bytes <= 0:
            return None
        size = unit_w * unit_h * unit_bytes
        if off + size > len(payload):
            return None
        seg = payload[off:off+size]
        if mode == "linear_copy":
            new_seg = seg
        elif mode == "source_morton_to_linear":
            new_seg = _reorder_source_morton_to_linear(seg, unit_w, unit_h, unit_bytes)
        elif mode == "source_tile4_to_linear":
            new_seg = _reorder_source_tiled_to_linear(seg, unit_w, unit_h, unit_bytes, 4)
        elif mode == "source_tile8_to_linear":
            new_seg = _reorder_source_tiled_to_linear(seg, unit_w, unit_h, unit_bytes, 8)
        elif mode == "source_tile16_to_linear":
            new_seg = _reorder_source_tiled_to_linear(seg, unit_w, unit_h, unit_bytes, 16)
        else:
            return None
        if new_seg is None:
            return None
        out.extend(new_seg)
        off += size
    if off != len(payload):
        # Do not guess when component1 has extra unknown tail bytes.
        return None
    return bytes(out)


def tex_layout_review_hint(tex_name: str, metadata: Dict[str, Any], payload_size: int = 0) -> Dict[str, Any]:
    name_l = (tex_name or "").lower()
    conf = str(metadata.get("tex_metadata_confidence") or "")
    fmt = str(metadata.get("tex_format_guess") or "")
    exact = str(metadata.get("tex_payload_size_match") or "").lower() in {"true", "1", "yes"}
    dds_status = str(metadata.get("tex_dds_export_status") or "")
    special = any(k in name_l for k in TEX_LAYOUT_SPECIAL_KEYWORDS)
    supported = fmt in {"DXT1_BC1", "DXT3_BC2", "DXT5_BC3", "ATI2_BC5", "BGRA32", "RGB24", "L8_A8_OR_ALPHA8"}
    if conf != "HIGH_EXACT_PAYLOAD_SIZE_MATCH" or not exact:
        status = "METADATA_REVIEW_FIRST"
        reason = "layout_lab_waits_for_exact_metadata"
        modes = ""
    elif not supported:
        status = "UNSUPPORTED_FORMAT_FOR_LAYOUT_LAB"
        reason = f"unsupported_format:{fmt}"
        modes = ""
    elif payload_size and payload_size > _tex_layout_lab_max_bytes():
        status = "TOO_LARGE_FOR_AUTO_LAYOUT_LAB"
        reason = f"payload_size_over_limit:{payload_size}>{_tex_layout_lab_max_bytes()}"
        modes = "linear_copy,source_morton_to_linear,source_tile4_to_linear,source_tile8_to_linear,source_tile16_to_linear"
    elif special or _tex_layout_lab_all_enabled():
        status = "LAYOUT_LAB_CANDIDATE"
        reason = "special_texture_or_lab_all_enabled"
        modes = "linear_copy,source_morton_to_linear,source_tile4_to_linear,source_tile8_to_linear,source_tile16_to_linear"
    elif dds_status == "DDS_EXPORT_OK":
        status = "LINEAR_DDS_READY_VISUAL_CHECK"
        reason = "linear_dds_export_ok_enable_lab_if_swizzled"
        modes = "linear_copy,source_morton_to_linear,source_tile4_to_linear,source_tile8_to_linear,source_tile16_to_linear"
    else:
        status = "NOT_A_LAYOUT_LAB_CANDIDATE"
        reason = "not_special_or_not_exported"
        modes = ""
    return {
        "tex_layout_review_status": status,
        "tex_layout_review_reason": reason,
        "tex_layout_candidate_modes": modes,
        "tex_layout_lab_enabled": _tex_layout_lab_enabled(),
    }


def maybe_export_tex_layout_lab(out_root: Path, tex_name: str, filename_hash: int, metadata: Dict[str, Any], payload: bytes) -> Dict[str, Any]:
    """v2.18 optional TEX layout/swizzle review lab.

    This does not modify game packs and does not claim to automatically solve every texture.
    It writes alternate DDS wrappers that assume the source payload may be Morton/tiled rather
    than already linear. The user compares the candidates visually; the winning layout can be
    locked later once proven.
    """
    hint = tex_layout_review_hint(tex_name, metadata, len(payload))
    result = dict(hint)
    result.update({
        "tex_layout_lab_candidate_count": 0,
        "tex_layout_lab_folder": "",
        "tex_layout_lab_manifest": "",
    })
    if not _tex_layout_lab_enabled():
        return result
    if hint.get("tex_layout_review_status") not in {"LAYOUT_LAB_CANDIDATE", "LINEAR_DDS_READY_VISUAL_CHECK"}:
        return result
    try:
        w = int(metadata.get("tex_width_guess") or 0)
        h = int(metadata.get("tex_height_guess") or 0)
        mips = int(metadata.get("tex_mip_count_guess") or 1)
        fmt = str(metadata.get("tex_format_guess") or "")
    except Exception:
        return result
    if not w or not h or not fmt:
        return result
    if len(payload) > _tex_layout_lab_max_bytes():
        result["tex_layout_review_status"] = "TOO_LARGE_FOR_AUTO_LAYOUT_LAB"
        return result
    header = _dds_header(w, h, mips, fmt, len(payload))
    if not header:
        result["tex_layout_review_status"] = "UNSUPPORTED_FORMAT_FOR_LAYOUT_LAB"
        result["tex_layout_review_reason"] = f"unsupported_dds_header:{fmt}"
        return result
    safe = clean_name(tex_name, "tex")
    lab_dir = ensure_dir(out_root / "06_TEX_LAYOUT_LAB" / clean_name(f"{hex32(filename_hash)}.{safe}", "tex_layout"))
    modes = ["linear_copy", "source_morton_to_linear", "source_tile4_to_linear", "source_tile8_to_linear", "source_tile16_to_linear"]
    manifest: List[Dict[str, Any]] = []
    count = 0
    for mode in modes:
        transformed = _transform_texture_payload_layout(payload, w, h, mips, fmt, mode)
        if transformed is None:
            manifest.append({"mode": mode, "status": "SKIPPED_TRANSFORM_FAILED"})
            continue
        dst = lab_dir / clean_name(f"{hex32(filename_hash)}.{safe}.{w}x{h}.m{mips}.{fmt}.{mode}.dds", "layout_candidate.dds")
        dst.write_bytes(header + transformed)
        manifest.append({
            "mode": mode,
            "status": "DDS_LAYOUT_CANDIDATE_WRITTEN",
            "file": str(dst),
            "dds_size": len(header) + len(transformed),
            "note": "visual_compare_candidate_not_auto_final",
        })
        count += 1
    write_csv(lab_dir / "LAYOUT_CANDIDATES.csv", manifest)
    write_json(lab_dir / "LAYOUT_CANDIDATES.json", {"tex_name": tex_name, "hash": hex32(filename_hash), "width": w, "height": h, "mips": mips, "format": fmt, "candidates": manifest})
    (lab_dir / "README_LAYOUT_LAB.txt").write_text(
        "SM3 TEX Layout Lab candidates. Compare the DDS files visually.\n"
        "linear_copy is the normal DDS wrapper. Other files assume the source payload was stored in Morton/tiled order.\n"
        "These are review candidates only; the tool does not modify original PCPACKs.\n",
        encoding="utf-8",
    )
    result.update({
        "tex_layout_lab_candidate_count": count,
        "tex_layout_lab_folder": str(lab_dir),
        "tex_layout_lab_manifest": str(lab_dir / "LAYOUT_CANDIDATES.csv"),
    })
    return result

def anim_family_hint(name: str) -> str:
    n = (name or "").lower()
    families = [
        ("swing", ["swg", "swing"]),
        ("jump_dive_air", ["jmp", "jump", "dive", "air", "fall", "fly"]),
        ("wall_hang_climb", ["wall", "hang", "climb"]),
        ("combat_attack_hit", ["atck", "atk", "hit", "combat", "kick", "punch", "block", "deflect"]),
        ("idle_walk_run", ["idle", "walk", "run", "sprint", "crawl"]),
        ("web_action", ["web", "yank", "catch"]),
        ("cutscene_story", ["toa", "dan", "igc", "cs", "cut"]),
    ]
    hits = [family for family, keys in families if any(k in n for k in keys)]
    return "+".join(hits) if hits else "anim_unknown_family"


def _float_or_zero(v: Any) -> float:
    try:
        if v in (None, ""):
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def tex_review_priority_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    """v2.16: classify TEX rows for low-confidence review triage.

    This does not change metadata guesses or export bytes. It gives a practical
    next action for rows that are not high-confidence exact matches, especially
    city/MEGACITY special textures.
    """
    conf = str(row.get("tex_metadata_confidence") or "NONE")
    status = str(row.get("tex_parse_status") or "")
    reason = str(row.get("tex_review_reason") or "")
    name = str(row.get("filename") or "").lower()
    role = str(row.get("role_hint") or texture_role_hint(name))
    ratio = _float_or_zero(row.get("tex_payload_size_diff_ratio"))
    fmt = str(row.get("tex_format_guess") or "")
    priority = "NONE"
    action = "NO_ACTION"
    group = "OK_OR_NOT_TEX"

    if conf == "HIGH_EXACT_PAYLOAD_SIZE_MATCH":
        priority = "READY"
        action = "READY_FOR_DDS_EXPORT_OR_TEXTURE_PREVIEW"
        group = "EXACT_OK"
    elif conf == "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH":
        priority = "MEDIUM"
        action = "REVIEW_OPTIONAL_CHECK_DESCRIPTOR_FIELDS_BEFORE_EXPORT"
        group = "NEAR_MATCH_OPTIONAL_REVIEW"
    elif status in {"NO_COMPONENT1_PAYLOAD", "NO_DIMENSION_CANDIDATE", "NO_SIZE_MATCH_CANDIDATE"} or reason.startswith("NO_"):
        priority = "HIGH"
        action = "MANUAL_DESCRIPTOR_REVIEW_REQUIRED_NO_SAFE_TEXTURE_EXPORT"
        group = "NO_SAFE_METADATA"
    elif "water" in name or "cloud" in name or "sky" in name or "ocean" in name or "river" in name:
        priority = "HIGH"
        action = "PRIORITY_SPECIAL_CITY_TEXTURE_REVIEW_VERIFY_FORMAT_MIPS"
        group = "SPECIAL_CITY_TEXTURE"
    elif ratio and ratio <= 0.10:
        priority = "MEDIUM"
        action = "TRY_ALTERNATE_MIP_COUNT_OR_FORMAT_FROM_COMPONENT0_DESCRIPTOR"
        group = "LOW_DIFF_UNDER_10_PERCENT"
    elif ratio and ratio <= 0.50:
        priority = "HIGH"
        action = "CHECK_IF_DESCRIPTOR_DIMENSIONS_OR_MIP_COUNT_ARE_MISREAD"
        group = "LOW_DIFF_UNDER_50_PERCENT"
    elif conf == "LOW_BEST_EFFORT_GUESS":
        priority = "HIGH"
        action = "MANUAL_REVIEW_REQUIRED_BEST_EFFORT_METADATA_ONLY"
        group = "LOW_CONFIDENCE_BEST_EFFORT"
    else:
        priority = "LOW"
        action = "REVIEW_IF_TEXTURE_IS_IMPORTANT"
        group = "OTHER_REVIEW"

    if fmt == "RGB24" and conf == "HIGH_EXACT_PAYLOAD_SIZE_MATCH":
        action = "READY_FOR_RGB24_DDS_EXPORT"
        group = "EXACT_RGB24_OK"
    return {
        "tex_review_priority": priority,
        "tex_review_action": action,
        "tex_review_group": group,
    }


def resource_metadata_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    ftype = str(row.get("file_type") or "UNKNOWN").upper()
    name = str(row.get("filename") or "")
    ext = str(row.get("extension") or inner_extension(ftype, name))
    total = _safe_int(row.get("total_component_size") or row.get("combined_raw_size"))
    tokens = split_name_tokens(name)
    role = "unknown"
    family = "unknown"
    if ftype == "TEX":
        role = texture_role_hint(name)
        family = "texture"
    elif ftype == "ANIM":
        role = anim_family_hint(name)
        family = "animation"
    elif ftype == "MESH":
        role = "mesh_geometry"
        family = "model"
    elif ftype == "MAT":
        role = "material_definition"
        family = "material"
    elif ftype == "SKEL":
        role = "skeleton"
        family = "model"
    elif ftype == "ASKL":
        role = "animation_skeleton_link"
        family = "animation"
    elif ftype in {"MORH", "SANM"}:
        role = "special_animation_or_morph_group"
        family = "animation_special"
    elif ftype == "FX":
        role = "shader_or_effect"
        family = "effect"
    return {
        "global_index": row.get("global_index"),
        "file_type": ftype,
        "extension": ext,
        "filename": name,
        "filename_hash": row.get("filename_hash"),
        "resource_family": family,
        "role_hint": role,
        "name_tokens": " ".join(tokens),
        "component_count": row.get("component_count"),
        "component_layout": component_layout(row),
        "total_component_size": total,
        "size_bucket": size_bucket(total),
        "source_apkf_label": row.get("source_apkf_label"),
        "source_apkf_absolute_base": row.get("source_apkf_absolute_base"),
        "real_ext_file": row.get("real_ext_file"),
        "exported": row.get("exported"),
        "tex_parse_status": row.get("tex_parse_status"),
        "tex_width_guess": row.get("tex_width_guess"),
        "tex_height_guess": row.get("tex_height_guess"),
        "tex_mip_count_guess": row.get("tex_mip_count_guess"),
        "tex_format_guess": row.get("tex_format_guess"),
        "tex_payload_size": row.get("tex_payload_size"),
        "tex_payload_expected_size": row.get("tex_payload_expected_size"),
        "tex_payload_size_match": row.get("tex_payload_size_match"),
        "tex_metadata_confidence": row.get("tex_metadata_confidence"),
        "tex_dimension_field_hint": row.get("tex_dimension_field_hint"),
        "tex_mip_field_hint": row.get("tex_mip_field_hint"),
        "tex_guess_reason": row.get("tex_guess_reason"),
        "tex_review_reason": row.get("tex_review_reason"),
        "tex_payload_size_diff": row.get("tex_payload_size_diff"),
        "tex_payload_size_diff_ratio": row.get("tex_payload_size_diff_ratio"),
        **tex_review_priority_hint(row),
        "tex_dds_export_status": row.get("tex_dds_export_status"),
        "tex_dds_export_reason": row.get("tex_dds_export_reason"),
        "tex_dds_export_file": row.get("tex_dds_export_file"),
        "tex_dds_export_size": row.get("tex_dds_export_size"),
        "tex_dds_layout_mode": row.get("tex_dds_layout_mode"),
        "tex_dds_layout_lock_applied": row.get("tex_dds_layout_lock_applied"),
        "tex_layout_lock_status": row.get("tex_layout_lock_status"),
        "tex_layout_locked_mode": row.get("tex_layout_locked_mode"),
        "tex_layout_lock_source": row.get("tex_layout_lock_source"),
        "tex_layout_lock_reason": row.get("tex_layout_lock_reason"),
        "tex_layout_review_status": row.get("tex_layout_review_status"),
        "tex_layout_review_reason": row.get("tex_layout_review_reason"),
        "tex_layout_candidate_modes": row.get("tex_layout_candidate_modes"),
        "tex_layout_lab_enabled": row.get("tex_layout_lab_enabled"),
        "tex_layout_lab_candidate_count": row.get("tex_layout_lab_candidate_count"),
        "tex_layout_lab_folder": row.get("tex_layout_lab_folder"),
        "tex_layout_lab_manifest": row.get("tex_layout_lab_manifest"),
    }


def mesh_metadata_starter_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    """v2.21: conservative MESH metadata starter.

    This does not decode vertex/index buffers. It only classifies component layout,
    size, and likely review intent so model research can be prioritized safely.
    """
    name = str(row.get("filename") or "")
    lname = name.lower()
    total = _safe_int(row.get("total_component_size"))
    comp_count = _safe_int(row.get("component_count"))
    layout = str(row.get("component_layout") or "")
    tokens = split_name_tokens(name)
    if any(t in lname for t in ["skeleton", "skel"]):
        mesh_role = "mesh_named_like_skeleton_review"
    elif any(t in lname for t in ["cloth", "cape", "web", "fx"]):
        mesh_role = "special_or_effect_mesh_review"
    elif any(t in lname for t in ["city", "building", "road", "prop", "wall", "sign"]):
        mesh_role = "world_or_prop_mesh"
    elif any(t in lname for t in ["spider", "black", "peter", "gob", "ch_"]):
        mesh_role = "character_mesh"
    else:
        mesh_role = "generic_mesh"
    if comp_count >= 3:
        layout_class = "MULTI_COMPONENT_GEOMETRY_CANDIDATE"
    elif comp_count == 2:
        layout_class = "TWO_COMPONENT_GEOMETRY_CANDIDATE"
    elif comp_count == 1:
        layout_class = "ONE_COMPONENT_GEOMETRY_CANDIDATE"
    else:
        layout_class = "NO_COMPONENTS_REVIEW"
    priority = "NORMAL"
    if total >= 1024 * 1024:
        priority = "HIGH_LARGE_MESH"
    elif mesh_role == "character_mesh":
        priority = "HIGH_CHARACTER_MESH"
    return {
        "global_index": row.get("global_index"),
        "filename_hash": row.get("filename_hash"),
        "filename": name,
        "file_type": row.get("file_type"),
        "extension": row.get("extension"),
        "mesh_role_hint": mesh_role,
        "mesh_layout_class": layout_class,
        "mesh_review_priority": priority,
        "mesh_dependency_hint": "MAT;SKEL/ASKL possible",
        "component_count": comp_count,
        "component_layout": layout,
        "total_component_size": total,
        "size_bucket": row.get("size_bucket"),
        "name_tokens": " ".join(tokens),
        "real_ext_file": row.get("real_ext_file"),
        "exported": row.get("exported"),
    }


def mat_metadata_starter_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    """v2.21: conservative MAT metadata starter.

    This does not fully parse material binary data yet. It labels likely material role
    and texture-channel hints from names/component layout so MAT->TEX work can start.
    """
    name = str(row.get("filename") or "")
    lname = name.lower()
    total = _safe_int(row.get("total_component_size"))
    comp_count = _safe_int(row.get("component_count"))
    layout = str(row.get("component_layout") or "")
    channels = []
    for token in ["dif", "diff", "normal", "nor", "spe", "spec", "rfl", "ao", "alpha", "mask", "env", "spx"]:
        if token in lname:
            channels.append(token)
    if "ch_" in lname or "spider" in lname or "black" in lname or "gob" in lname or "peter" in lname:
        mat_role = "character_material"
    elif any(t in lname for t in ["city", "building", "road", "prop", "wall", "sign"]):
        mat_role = "world_or_prop_material"
    elif any(t in lname for t in ["fx", "web", "splat", "smoke", "water", "cloud"]):
        mat_role = "effect_or_special_material"
    else:
        mat_role = "generic_material"
    priority = "NORMAL"
    if channels:
        priority = "TEXTURE_CHANNEL_NAME_HINT"
    elif total >= 65536:
        priority = "LARGE_MATERIAL_REVIEW"
    return {
        "global_index": row.get("global_index"),
        "filename_hash": row.get("filename_hash"),
        "filename": name,
        "file_type": row.get("file_type"),
        "extension": row.get("extension"),
        "mat_role_hint": mat_role,
        "mat_texture_channel_name_hints": ";".join(sorted(set(channels))),
        "mat_review_priority": priority,
        "mat_dependency_hint": "TEX references likely; binary parse not implemented yet",
        "component_count": comp_count,
        "component_layout": layout,
        "total_component_size": total,
        "size_bucket": row.get("size_bucket"),
        "name_tokens": row.get("name_tokens"),
        "real_ext_file": row.get("real_ext_file"),
        "exported": row.get("exported"),
    }


def anim_metadata_starter_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    """v2.21: conservative ANIM metadata starter.

    This does not decode animation curves. It classifies by name family, component
    layout, and safer swap-test categories for future animation tools.
    """
    name = str(row.get("filename") or "")
    lname = name.lower()
    total = _safe_int(row.get("total_component_size"))
    comp_count = _safe_int(row.get("component_count"))
    layout = str(row.get("component_layout") or "")
    family = anim_family_hint(name)
    if any(t in lname for t in ["swg", "swing", "jmp", "jump", "dive", "wall", "hang", "web"]):
        safety = "HIGH_RISK_TRAVERSAL_REVIEW"
    elif any(t in lname for t in ["idle", "tap", "stand"]):
        safety = "LOWER_RISK_IDLE_STANCE"
    elif any(t in lname for t in ["hit", "hurt", "block", "deflect"]):
        safety = "LOWER_RISK_HIT_REACTION"
    elif any(t in lname for t in ["atck", "attack", "punch", "kick", "combat"]):
        safety = "MEDIUM_COMBAT_REVIEW"
    else:
        safety = "UNKNOWN_ANIM_REVIEW"
    size_class = size_bucket(total)
    return {
        "global_index": row.get("global_index"),
        "filename_hash": row.get("filename_hash"),
        "filename": name,
        "file_type": row.get("file_type"),
        "extension": row.get("extension"),
        "anim_family_hint": family,
        "anim_swap_safety_hint": safety,
        "anim_size_class": size_class,
        "anim_dependency_hint": "ASKL/SKEL plus state graph context required before swapping",
        "component_count": comp_count,
        "component_layout": layout,
        "total_component_size": total,
        "name_tokens": row.get("name_tokens"),
        "real_ext_file": row.get("real_ext_file"),
        "exported": row.get("exported"),
    }


def resource_dependency_starter_hint(row: Dict[str, Any]) -> Dict[str, Any]:
    ftype = str(row.get("file_type") or "UNKNOWN").upper()
    name = str(row.get("filename") or "")
    if ftype == "MESH":
        dep = "MAT;SKEL/ASKL"
        action = "MAP_MESH_TO_MATERIAL_AND_SKELETON_LATER"
    elif ftype == "MAT":
        dep = "TEX"
        action = "SCAN_MAT_BINARY_FOR_TEXTURE_HASHES_LATER"
    elif ftype == "ANIM":
        dep = "ASKL;SKEL;STATE_GRAPH"
        action = "KEEP_COMPONENT_LAYOUT_FOR_SAFE_ANIM_SWAP_RESEARCH"
    elif ftype == "TEX":
        dep = "MAT"
        action = "LINK_TO_MAT_REFERENCES_LATER"
    elif ftype in {"SKEL", "ASKL"}:
        dep = "MESH;ANIM"
        action = "LINK_CHARACTER_CHAIN_LATER"
    else:
        dep = "UNKNOWN"
        action = "REVIEW_IF_USED_BY_KNOWN_RESOURCE"
    return {
        "global_index": row.get("global_index"),
        "file_type": ftype,
        "filename_hash": row.get("filename_hash"),
        "filename": name,
        "resource_family": row.get("resource_family"),
        "possible_dependencies": dep,
        "dependency_action": action,
        "component_layout": row.get("component_layout"),
        "total_component_size": row.get("total_component_size"),
        "real_ext_file": row.get("real_ext_file"),
    }


def _count_rows(rows: List[Dict[str, Any]], key: str, count_name: str = "count") -> List[Dict[str, Any]]:
    c = Counter(str(r.get(key) or "UNKNOWN") for r in rows)
    return [{key: k, count_name: v} for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]



def _csv_link(name: str) -> str:
    return f"<a href='{_html.escape(name)}'>{_html.escape(name)}</a>"


def _safe_html_table(rows: List[Dict[str, Any]], columns: List[str], max_rows: int = 800) -> str:
    out = ["<table>", "<tr>" + "".join(f"<th>{_html.escape(c)}</th>" for c in columns) + "</tr>"]
    for r in rows[:max_rows]:
        out.append("<tr>" + "".join(f"<td>{_html.escape(str(r.get(c, '')))}</td>" for c in columns) + "</tr>")
    out.append("</table>")
    if len(rows) > max_rows:
        out.append(f"<p class='note'>Showing {max_rows} of {len(rows)} rows. See CSV for full list.</p>")
    return "\n".join(out)


def write_pack_browse_dashboard_v222(reports: Path, meta_rows: List[Dict[str, Any]], dep_rows: List[Dict[str, Any]]) -> None:
    """v2.22: write a friendlier per-pack HTML dashboard and dependency navigation reports."""
    ensure_dir(reports)
    type_counts = Counter(str(r.get('file_type') or 'UNKNOWN') for r in meta_rows)
    family_counts = Counter(str(r.get('resource_family') or 'unknown') for r in meta_rows)
    nav_rows: List[Dict[str, Any]] = []
    for r in meta_rows:
        ftype = str(r.get('file_type') or 'UNKNOWN').upper()
        action = ''
        if ftype == 'TEX':
            action = 'open TEX metadata/DDS export reports; link to MAT later'
        elif ftype == 'MAT':
            action = 'review MAT hints; scan binary for TEX hashes later'
        elif ftype == 'MESH':
            action = 'review MESH component layout; link to MAT/SKEL later'
        elif ftype == 'ANIM':
            action = 'review ANIM safety/family hints; link to ASKL/SKEL later'
        elif ftype in {'SKEL', 'ASKL'}:
            action = 'character-chain dependency anchor'
        else:
            action = 'unknown/CVX review'
        nav_rows.append({
            'file_type': ftype,
            'filename_hash': r.get('filename_hash'),
            'filename': r.get('filename'),
            'resource_family': r.get('resource_family'),
            'role_hint': r.get('role_hint'),
            'component_layout': r.get('component_layout'),
            'dependency_action': action,
            'real_ext_file': r.get('real_ext_file'),
            'tex_confidence': r.get('tex_metadata_confidence'),
            'tex_dds_export_status': r.get('tex_dds_export_status'),
            'anim_swap_safety_hint': r.get('anim_swap_safety_hint'),
        })
    write_csv(reports / 'RESOURCE_NAVIGATION_INDEX.csv', nav_rows)
    write_csv(reports / 'RESOURCE_FAMILY_COUNTS.csv', [{"resource_family": k, "resource_count": v} for k, v in sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / 'RESOURCE_DEPENDENCY_NAVIGATION.csv', dep_rows)

    type_rows = [{'file_type': k, 'resource_count': v} for k, v in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    family_rows = [{'resource_family': k, 'resource_count': v} for k, v in sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    key_links = [
        'RESOURCE_BROWSE_INDEX.csv', 'RESOURCE_NAVIGATION_INDEX.csv', 'RESOURCE_DEPENDENCY_NAVIGATION.csv',
        'TEX_METADATA_HINTS.csv', 'TEX_DDS_EXPORTS.csv', 'TEX_REVIEW_TRIAGE.csv', 'TEX_LAYOUT_CANDIDATES.csv',
        'MESH_METADATA_HINTS.csv', 'MAT_METADATA_HINTS.csv', 'ANIM_METADATA_HINTS.csv', 'RESOURCE_METADATA_SUMMARY.txt'
    ]
    top_tex = [r for r in nav_rows if r.get('file_type') == 'TEX'][:120]
    top_mesh = [r for r in nav_rows if r.get('file_type') == 'MESH'][:120]
    top_mat = [r for r in nav_rows if r.get('file_type') == 'MAT'][:120]
    top_anim = [r for r in nav_rows if r.get('file_type') == 'ANIM'][:120]
    css = """
    body{font-family:Segoe UI,Arial,sans-serif;margin:22px;background:#101114;color:#eee}
    a{color:#8cc8ff} table{border-collapse:collapse;width:100%;margin:10px 0 22px 0} td,th{border:1px solid #3b3b3b;padding:5px;font-size:12px} th{background:#20232a;position:sticky;top:0}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}.card{background:#181b22;border:1px solid #333;border-radius:10px;padding:10px}.num{font-size:22px;font-weight:700}.note{color:#bbb}.pill{display:inline-block;background:#242936;padding:4px 8px;border-radius:999px;margin:3px}
    """
    html_parts = [
        "<!doctype html><html><head><meta charset='utf-8'><title>SM3 Pack Browse Dashboard</title>",
        f"<style>{css}</style></head><body>",
        "<h1>SM3 Pack Browse Dashboard</h1>",
        f"<p class='note'>Generated by {TOOL_NAME} {TOOL_VERSION}. Report-only navigation; original PCPACKs are not modified.</p>",
        "<div class='cards'>",
    ]
    for key in ['TEX','MESH','MAT','ANIM','CVX','SKEL','ASKL','SANM','MORH','UNKNOWN']:
        html_parts.append(f"<div class='card'><div>{_html.escape(key)}</div><div class='num'>{type_counts.get(key,0)}</div></div>")
    html_parts += ["</div>", "<h2>Quick Links</h2><p>"]
    html_parts.append(' '.join(f"<span class='pill'>{_csv_link(k)}</span>" for k in key_links if (reports/k).exists()))
    html_parts += ["</p>", "<h2>Resource Type Counts</h2>", _safe_html_table(type_rows, ['file_type','resource_count'], 40), "<h2>Resource Family Counts</h2>", _safe_html_table(family_rows, ['resource_family','resource_count'], 40)]
    cols = ['file_type','filename_hash','filename','resource_family','role_hint','component_layout','dependency_action','tex_confidence','tex_dds_export_status','anim_swap_safety_hint']
    if top_tex:
        html_parts += ["<h2>TEX Preview Navigation</h2>", _safe_html_table(top_tex, cols, 120)]
    if top_mesh:
        html_parts += ["<h2>MESH Navigation</h2>", _safe_html_table(top_mesh, cols, 120)]
    if top_mat:
        html_parts += ["<h2>MAT Navigation</h2>", _safe_html_table(top_mat, cols, 120)]
    if top_anim:
        html_parts += ["<h2>ANIM Navigation</h2>", _safe_html_table(top_anim, cols, 120)]
    html_parts += ["<h2>Dependency Navigation</h2>", _safe_html_table(dep_rows, ['file_type','filename_hash','filename','possible_dependencies','dependency_action','component_layout'], 400), "</body></html>"]
    (reports / 'PACK_BROWSE_DASHBOARD.html').write_text('\n'.join(html_parts) + '\n', encoding='utf-8')
    (reports / 'RESOURCE_DEPENDENCY_NAVIGATION.html').write_text('\n'.join([
        "<!doctype html><html><head><meta charset='utf-8'><title>SM3 Resource Dependency Navigation</title>",
        f"<style>{css}</style></head><body>",
        "<h1>SM3 Resource Dependency Navigation</h1>",
        "<p class='note'>Starter dependency hints only. MESH->MAT/SKEL, MAT->TEX, ANIM->ASKL/SKEL are conservative report hints, not decoded links yet.</p>",
        _safe_html_table(dep_rows, ['file_type','filename_hash','filename','possible_dependencies','dependency_action','component_layout','real_ext_file'], 1200),
        "</body></html>"
    ]) + '\n', encoding='utf-8')

def write_resource_browse_reports(reports: Path, inner_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """v2.8: write cleaner browse/index reports for extracted APKF resources.

    These are report-only metadata hints. They do not change extraction bytes and they
    are intentionally conservative: TEX/MESH/MAT/ANIM parsing here means names,
    component sizes, type counts, and role/family hints, not full decoding.
    """
    ensure_dir(reports)
    meta_rows = [resource_metadata_hint(r) for r in inner_rows]
    write_csv(reports / "RESOURCE_BROWSE_INDEX.csv", meta_rows)
    write_csv(reports / "RESOURCE_TYPE_COUNTS.csv", _count_rows(meta_rows, "file_type", "resource_count"))
    write_csv(reports / "RESOURCE_EXTENSION_COUNTS.csv", _count_rows(meta_rows, "extension", "resource_count"))
    write_csv(reports / "RESOURCE_COMPONENT_LAYOUT_COUNTS.csv", _count_rows(meta_rows, "component_layout", "resource_count"))

    type_file_map = {
        "TEX": "TEX_RESOURCE_HINTS.csv",
        "MESH": "MESH_RESOURCE_HINTS.csv",
        "MAT": "MAT_RESOURCE_HINTS.csv",
        "ANIM": "ANIM_RESOURCE_HINTS.csv",
    }
    for ftype, fname in type_file_map.items():
        write_csv(reports / fname, [r for r in meta_rows if r.get("file_type") == ftype])

    # v2.21 starter metadata reports for non-TEX resources. These are conservative
    # and do not decode/rebuild assets; they help decide what to inspect next.
    mesh_meta_rows = [mesh_metadata_starter_hint(r) for r in meta_rows if r.get("file_type") == "MESH"]
    mat_meta_rows = [mat_metadata_starter_hint(r) for r in meta_rows if r.get("file_type") == "MAT"]
    anim_meta_rows = [anim_metadata_starter_hint(r) for r in meta_rows if r.get("file_type") == "ANIM"]
    dep_rows = [resource_dependency_starter_hint(r) for r in meta_rows if str(r.get("file_type") or "").upper() in {"TEX", "MESH", "MAT", "ANIM", "SKEL", "ASKL"}]
    write_csv(reports / "MESH_METADATA_HINTS.csv", mesh_meta_rows)
    write_csv(reports / "MESH_COMPONENT_LAYOUT_COUNTS.csv", _count_rows(mesh_meta_rows, "component_layout", "mesh_count"))
    write_csv(reports / "MESH_REVIEW_PRIORITY_COUNTS.csv", _count_rows(mesh_meta_rows, "mesh_review_priority", "mesh_count"))
    write_csv(reports / "MAT_METADATA_HINTS.csv", mat_meta_rows)
    write_csv(reports / "MAT_COMPONENT_LAYOUT_COUNTS.csv", _count_rows(mat_meta_rows, "component_layout", "mat_count"))
    write_csv(reports / "MAT_ROLE_COUNTS.csv", _count_rows(mat_meta_rows, "mat_role_hint", "mat_count"))
    write_csv(reports / "ANIM_METADATA_HINTS.csv", anim_meta_rows)
    write_csv(reports / "ANIM_COMPONENT_LAYOUT_COUNTS.csv", _count_rows(anim_meta_rows, "component_layout", "anim_count"))
    write_csv(reports / "ANIM_FAMILY_COUNTS.csv", _count_rows(anim_meta_rows, "anim_family_hint", "anim_count"))
    write_csv(reports / "ANIM_SWAP_SAFETY_COUNTS.csv", _count_rows(anim_meta_rows, "anim_swap_safety_hint", "anim_count"))
    write_csv(reports / "RESOURCE_DEPENDENCY_HINTS.csv", dep_rows)
    write_csv(reports / "RESOURCE_DEPENDENCY_ACTION_COUNTS.csv", _count_rows(dep_rows, "dependency_action", "resource_count"))
    write_pack_browse_dashboard_v222(reports, meta_rows, dep_rows)

    tex_meta_rows = [r for r in meta_rows if r.get("file_type") == "TEX"]
    write_csv(reports / "TEX_METADATA_HINTS.csv", tex_meta_rows)
    write_csv(reports / "TEX_FORMAT_COUNTS.csv", _count_rows(tex_meta_rows, "tex_format_guess", "texture_count"))
    write_csv(reports / "TEX_DIMENSION_COUNTS.csv", _count_rows(tex_meta_rows, "tex_width_guess", "texture_count_width_only"))
    write_csv(reports / "TEX_REVIEW_REASON_COUNTS.csv", _count_rows(tex_meta_rows, "tex_review_reason", "texture_count"))
    tex_review_rows = [r for r in tex_meta_rows if str(r.get("tex_metadata_confidence") or "") not in {"HIGH_EXACT_PAYLOAD_SIZE_MATCH", "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH"}]
    tex_medium_rows = [r for r in tex_meta_rows if str(r.get("tex_metadata_confidence") or "") == "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH"]
    tex_triage_rows = [r for r in tex_meta_rows if str(r.get("tex_metadata_confidence") or "") != "HIGH_EXACT_PAYLOAD_SIZE_MATCH"]
    dds_candidate_rows = [r for r in tex_meta_rows if str(r.get("tex_metadata_confidence") or "") == "HIGH_EXACT_PAYLOAD_SIZE_MATCH"]
    dds_exported_rows = [r for r in tex_meta_rows if str(r.get("tex_dds_export_status") or "") == "DDS_EXPORT_OK"]
    write_csv(reports / "TEX_REVIEW_QUEUE.csv", tex_review_rows)
    write_csv(reports / "TEX_MEDIUM_REVIEW_QUEUE.csv", tex_medium_rows)
    write_csv(reports / "TEX_REVIEW_TRIAGE.csv", sorted(tex_triage_rows, key=lambda r: (str(r.get("tex_review_priority") or ""), str(r.get("tex_review_group") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "TEX_REVIEW_ACTION_COUNTS.csv", _count_rows(tex_triage_rows, "tex_review_action", "texture_count"))
    write_csv(reports / "TEX_REVIEW_PRIORITY_COUNTS.csv", _count_rows(tex_triage_rows, "tex_review_priority", "texture_count"))
    write_csv(reports / "TEX_REVIEW_GROUP_COUNTS.csv", _count_rows(tex_triage_rows, "tex_review_group", "texture_count"))
    write_csv(reports / "TEX_DDS_EXPORT_CANDIDATES.csv", dds_candidate_rows)
    write_csv(reports / "TEX_DDS_EXPORTS.csv", dds_exported_rows)
    tex_layout_review_rows = [r for r in tex_meta_rows if str(r.get("tex_layout_review_status") or "") not in {"", "NOT_A_LAYOUT_LAB_CANDIDATE"}]
    tex_layout_candidate_rows = [r for r in tex_meta_rows if str(r.get("tex_layout_review_status") or "") in {"LAYOUT_LAB_CANDIDATE", "LINEAR_DDS_READY_VISUAL_CHECK"}]
    write_csv(reports / "TEX_SWIZZLE_REVIEW_QUEUE.csv", tex_layout_review_rows)
    write_csv(reports / "TEX_LAYOUT_CANDIDATES.csv", tex_layout_candidate_rows)
    write_csv(reports / "TEX_LAYOUT_STATUS_COUNTS.csv", _count_rows(tex_meta_rows, "tex_layout_review_status", "texture_count"))
    tex_lock_rows = [r for r in tex_meta_rows if str(r.get("tex_layout_lock_status") or "") in {"LOCK_FOUND_HASH_NAME", "LOCK_FOUND_HASH_ONLY", "LOCK_TRANSFORM_FAILED", "LOCK_INVALID_MODE"}]
    write_csv(reports / "TEX_LAYOUT_LOCK_APPLIED.csv", tex_lock_rows)
    write_csv(reports / "TEX_LAYOUT_LOCK_STATUS_COUNTS.csv", _count_rows(tex_meta_rows, "tex_layout_lock_status", "texture_count"))
    write_tex_layout_lock_map_load_report(reports)
    write_csv(reports / "UNKNOWN_RESOURCE_HINTS.csv", [r for r in meta_rows if str(r.get("file_type") or "UNKNOWN") not in EXT_BY_TYPE])

    counts = Counter(str(r.get("file_type") or "UNKNOWN") for r in meta_rows)
    tex_conf_counts = Counter(str(r.get("tex_metadata_confidence") or "NONE") for r in tex_meta_rows)
    summary = {
        "total_resources": len(meta_rows),
        "counts_by_type": dict(sorted(counts.items())),
        "tex_count": counts.get("TEX", 0),
        "mesh_count": counts.get("MESH", 0),
        "mat_count": counts.get("MAT", 0),
        "anim_count": counts.get("ANIM", 0),
        "mesh_metadata_rows": len(mesh_meta_rows),
        "mat_metadata_rows": len(mat_meta_rows),
        "anim_metadata_rows": len(anim_meta_rows),
        "resource_dependency_hint_rows": len(dep_rows),
        "unknown_type_count": sum(v for k, v in counts.items() if k not in EXT_BY_TYPE),
        "tex_metadata_confidence_counts": dict(sorted(tex_conf_counts.items())),
        "tex_exact_payload_size_match_count": tex_conf_counts.get("HIGH_EXACT_PAYLOAD_SIZE_MATCH", 0),
        "tex_review_queue_count": len(tex_review_rows),
        "tex_dds_export_candidate_count": len(dds_candidate_rows),
        "tex_dds_exported_count": len(dds_exported_rows),
        "tex_rgb24_dds_export_support": True,
        "tex_review_triage_count": len([r for r in tex_meta_rows if str(r.get("tex_metadata_confidence") or "") != "HIGH_EXACT_PAYLOAD_SIZE_MATCH"]),
        "tex_layout_review_queue_count": len(tex_layout_review_rows),
        "tex_layout_candidate_count": len(tex_layout_candidate_rows),
        "tex_layout_lock_applied_count": len(tex_lock_rows),
        "note": "v2.20 adds optional TEX layout lock maps for approved best-layout choices. It does not modify original packs or auto-apply unknown swizzle fixes.",
    }
    write_json(reports / "RESOURCE_METADATA_SUMMARY.json", summary)
    (reports / "RESOURCE_METADATA_SUMMARY.txt").write_text("\n".join([f"{k}: {v}" for k, v in summary.items()]) + "\n", encoding="utf-8")

    # Small per-pack HTML index for quick browsing. It links to report CSVs, not payloads.
    max_html = 2000
    html_rows = meta_rows[:max_html]
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>SM3 Resource Browse Index</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#111;color:#eee} a{color:#8cc8ff} table{border-collapse:collapse;width:100%;font-size:12px} td,th{border:1px solid #444;padding:4px} th{background:#222;position:sticky;top:0} .note{color:#aaa}</style>",
        "</head><body>",
        "<h1>SM3 Resource Browse Index</h1>",
        f"<p>Total resources: {len(meta_rows)}. Showing {len(html_rows)} rows in HTML; full list is RESOURCE_BROWSE_INDEX.csv.</p>",
        "<p><a href='RESOURCE_BROWSE_INDEX.csv'>RESOURCE_BROWSE_INDEX.csv</a> | <a href='TEX_RESOURCE_HINTS.csv'>TEX</a> | <a href='TEX_METADATA_HINTS.csv'>TEX metadata</a> | <a href='MESH_RESOURCE_HINTS.csv'>MESH</a> | <a href='MAT_RESOURCE_HINTS.csv'>MAT</a> | <a href='ANIM_RESOURCE_HINTS.csv'>ANIM</a></p>",
        "<table><tr><th>#</th><th>Type</th><th>Hash</th><th>Name</th><th>Role</th><th>Components</th><th>Size</th><th>Exported File</th></tr>",
    ]
    for i, r in enumerate(html_rows, 1):
        html.append("<tr>" + "".join([
            f"<td>{i}</td>",
            f"<td>{_html.escape(str(r.get('file_type') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('filename_hash') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('filename') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('role_hint') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('component_layout') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('total_component_size') or ''))}</td>",
            f"<td>{_html.escape(str(r.get('real_ext_file') or ''))}</td>",
        ]) + "</tr>")
    html += ["</table>", "<p class='note'>Generated by v2.22 browse/index reports. Original packs were not modified.</p>", "</body></html>"]
    (reports / "RESOURCE_BROWSE_INDEX.html").write_text("\n".join(html) + "\n", encoding="utf-8")
    return summary


def _read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []

# ------------------------- outer table parser / route scan -------------------------

@dataclass
class OuterRow:
    index: int
    table_offset: int
    hash_value: int
    type_id: int
    data_offset: int
    data_size: int
    data_magic: str
    known_name: str = ""
    valid: bool = True

    @property
    def end(self) -> int:
        return self.data_offset + self.data_size

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "table_offset": hx(self.table_offset),
            "hash": hex32(self.hash_value),
            "known_name": self.known_name,
            "type_hex": f"0x{self.type_id:X}",
            "type_dec": self.type_id,
            "data_offset": hx(self.data_offset),
            "data_offset_dec": self.data_offset,
            "data_size": hx(self.data_size),
            "data_size_dec": self.data_size,
            "data_end": hx(self.end),
            "data_magic": self.data_magic,
            "valid": self.valid,
        }

@dataclass
class TableCandidate:
    start: int
    rows: int
    score: int
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {"start": hx(self.start), "rows": self.rows, "score": self.score, "note": self.note}


def row_valid(data: bytes, pos: int) -> Optional[Tuple[int, int, int, int]]:
    size = len(data)
    if pos < 0 or pos + 16 > size:
        return None
    h, t, off, sz = struct.unpack_from("<IIII", data, pos)
    if sz <= 0 or off < 0 or off > size or off + sz > size:
        return None
    # Type values in SM3 are usually small-ish, but keep room for 0x194 and similar.
    if t > 0x5000:
        return None
    # Reject obvious null/junk rows.
    if h == 0 and t == 0 and off == 0:
        return None
    return h, t, off, sz


def count_rows_from(data: bytes, start: int, max_rows: int = 5000) -> int:
    count = 0
    pos = start
    last_off = -1
    while count < max_rows:
        rv = row_valid(data, pos)
        if not rv:
            break
        _, _, off, _ = rv
        # Most valid table rows point forward into the file. Do not strictly require sorted offsets.
        if off == last_off and count > 0:
            break
        count += 1
        pos += 16
        last_off = off
    return count


def score_table(data: bytes, start: int, row_count: int, marker_offsets: Iterable[int]) -> Optional[TableCandidate]:
    if row_count <= 0:
        return None
    size = len(data)
    if start < 0 or start + row_count * 16 > size:
        return None
    markers = set(marker_offsets)
    valid = 0
    apkf = 0
    hsam = 0
    marker_ptr = 0
    small_types = 0
    type35 = 0
    type36_stub = 0
    notes: List[str] = []
    for i in range(row_count):
        pos = start + i * 16
        rv = row_valid(data, pos)
        if not rv:
            return None if valid == 0 else TableCandidate(start, valid, valid * 5, "truncated_after_valid_rows")
        h, t, off, sz = rv
        valid += 1
        if t <= 0x500:
            small_types += 1
        if t == 0x35:
            type35 += 1
        if t == 0x36 and sz <= 0x28:
            type36_stub += 1
        sig = data[off:off + 4]
        if sig == b"APKF":
            apkf += 1
        if sig == b"hsam":
            hsam += 1
        if off in markers:
            marker_ptr += 1
    score = valid * 10 + small_types * 3 + apkf * 500 + hsam * 50 + marker_ptr * 100
    if type35 and type36_stub:
        score += 300
        notes.append("voice_type35_plus_stub36_pattern")
    if valid >= 2:
        notes.append("valid_rows")
    if apkf:
        notes.append("row_points_to_APKF")
    if hsam:
        notes.append("row_points_to_hsam")
    if marker_ptr:
        notes.append("row_offsets_match_markers")
    return TableCandidate(start, valid, score, ";".join(notes))


def find_table_candidates(data: bytes, marker_offsets: Iterable[int], max_candidates: int = 12) -> List[TableCandidate]:
    candidates: Dict[int, TableCandidate] = {}
    size = len(data)
    header_count = u32le(data, 0x54) or 0

    def add(start: int, count: Optional[int] = None, note: str = "") -> None:
        if start < 0 or start + 16 > size:
            return
        row_count = count if count and count > 0 else count_rows_from(data, start)
        cand = score_table(data, start, row_count, marker_offsets)
        if cand:
            if note:
                cand.note = (cand.note + ";" + note).strip(";")
            old = candidates.get(cand.start)
            if old is None or cand.score > old.score:
                candidates[cand.start] = cand

    for s in SM3_TABLE_START_CANDIDATES:
        if header_count:
            add(s, header_count, "standard_count_at_0x54")
        add(s, None, "standard_inferred_rows")

    # Marker-backreference recovery: offset field is row_start + 8.
    scan_limit = min(len(data), 0x5000)
    for m in marker_offsets:
        pat = struct.pack("<I", m)
        pos = 0
        while True:
            idx = data.find(pat, pos, scan_limit)
            if idx < 0:
                break
            row_start = idx - 8
            if row_start >= 0 and row_start % 4 == 0 and row_valid(data, row_start):
                # Backtrack to first contiguous row.
                start = row_start
                while start - 16 >= 0 and row_valid(data, start - 16):
                    start -= 16
                add(start, None, f"marker_backreference_to_{hx(m)}")
            pos = idx + 1

    # Conservative sweep around the known SM3 header/table area.
    for s in range(0x300, min(0x600, size - 16), 4):
        rows = count_rows_from(data, s)
        if rows >= 2:
            add(s, rows, "header_sweep_2plus_rows")

    return sorted(candidates.values(), key=lambda c: c.score, reverse=True)[:max_candidates]


def parse_outer_rows(data: bytes, table: TableCandidate) -> List[OuterRow]:
    rows: List[OuterRow] = []
    for i in range(table.rows):
        pos = table.start + i * 16
        rv = row_valid(data, pos)
        if not rv:
            continue
        h, t, off, sz = rv
        rows.append(OuterRow(
            index=i,
            table_offset=pos,
            hash_value=h,
            type_id=t,
            data_offset=off,
            data_size=sz,
            data_magic=hexbytes(data[off:off + 16]),
            known_name=KNOWN_HASHES.get(h, ""),
            valid=True,
        ))
    return rows


def detect_compact_header(data: bytes, marker_offsets: Dict[str, List[int]], allow_marker_fallback: bool = False) -> Dict[str, Any]:
    result = {"is_compact_header": False, "hsam_pointer": None, "apkf_pointer": None, "reason": ""}
    hsam_ptr = u32le(data, 0x18)
    apkf_ptr = u32le(data, 0x1C)

    # v2.1: direct compact-header pointers should be detected even if a tiny
    # one-row table was also recovered. CITY_PEDFEMALE/CITY_PEDMALE style packs
    # can have a valid 0x28 APKF row plus compact header pointers to the hsam/APKF
    # regions, so do not suppress this just because outer_rows exist.
    if hsam_ptr is not None and apkf_ptr is not None:
        hsig = data[hsam_ptr:hsam_ptr + 4] if 0 <= hsam_ptr < len(data) else b""
        asig = data[apkf_ptr:apkf_ptr + 4] if 0 <= apkf_ptr < len(data) else b""
        if hsig == b"hsam" and asig == b"APKF":
            result.update({"is_compact_header": True, "hsam_pointer": hsam_ptr, "apkf_pointer": apkf_ptr, "reason": "0x18_points_to_hsam_and_0x1C_points_to_APKF"})
            return result

    # fallback: hsam at 0x30 + APKF marker with no normal table is still likely compact wrapper.
    # Only allow this fallback when no reliable outer rows were recovered, or it would over-label
    # normal hsam/APKF packs as compact wrappers.
    if allow_marker_fallback and data[0x30:0x34] == b"hsam" and marker_offsets.get("APKF"):
        result.update({"is_compact_header": True, "hsam_pointer": 0x30, "apkf_pointer": marker_offsets["APKF"][0], "reason": "hsam_at_0x30_plus_APKF_marker_no_regular_table"})
    return result

# ------------------------- APKF parser -------------------------

@dataclass
class ComponentHeader:
    index: int
    offset: int
    type_id: str
    external_flag: int
    field2: int
    field3: int
    data_size: int
    data_offset: int
    base_data_address: int
    cursor_pos: int = 0

@dataclass
class APKFFileEntry:
    global_index: int
    file_type: str
    local_index: int
    filename: str
    filename_hash: int
    file_header_offset: int
    component_sizes: List[int]
    component_offsets: List[Tuple[int, int]]

    def to_dict(self) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "global_index": self.global_index,
            "file_type": self.file_type,
            "local_index": self.local_index,
            "filename": self.filename,
            "filename_hash": hex32(self.filename_hash),
            "file_header_offset": hx(self.file_header_offset),
            "component_count": len(self.component_sizes),
            "total_component_size": sum(self.component_sizes),
            "extension": inner_extension(self.file_type, self.filename),
        }
        for i, size in enumerate(self.component_sizes):
            row[f"component{i}_size"] = size
            if i < len(self.component_offsets):
                row[f"component{i}_start"] = hx(self.component_offsets[i][0])
                row[f"component{i}_end"] = hx(self.component_offsets[i][1])
        return row

class APKFArchive:
    def __init__(self, data: bytes, label: str = "APKF"):
        self.data = data
        self.label = label
        self.files: List[APKFFileEntry] = []
        self.component_headers: List[ComponentHeader] = []
        self.file_type_headers: List[Dict[str, Any]] = []
        self.header: Dict[str, Any] = {}
        self.parse()

    @staticmethod
    def align(pos: int, align: int) -> int:
        if align <= 0:
            return pos
        return (pos + align - 1) & ~(align - 1)

    def parse(self) -> None:
        if self.data[:4] != b"APKF":
            raise ValueError("payload does not start with APKF")
        if len(self.data) < 28:
            raise ValueError("APKF too small")
        magic, version, flag_field, bool_field, comp_count, comp_table_ptr_raw, file_table_ptr = struct.unpack_from("<4s6I", self.data, 0)
        if comp_count > 128:
            raise ValueError(f"APKF component_count too large: {comp_count}")
        comp_off = comp_table_ptr_raw + 20
        if comp_off < 0 or comp_off + comp_count * 24 > len(self.data):
            raise ValueError("APKF component table outside payload")
        self.header = {
            "label": self.label,
            "size": len(self.data),
            "magic": magic.decode("ascii", errors="replace"),
            "version": version,
            "flag_field": flag_field,
            "bool_field": bool_field,
            "component_count": comp_count,
            "component_table_ptr_raw": comp_table_ptr_raw,
            "component_table_ptr_effective": comp_off,
            "file_table_ptr": file_table_ptr,
        }
        for i in range(comp_count):
            o = comp_off + i * 24
            typeb, external, field2, field3, data_size, data_offset = struct.unpack_from("<4s5I", self.data, o)
            type_id = typeb.decode("ascii", errors="replace").replace("\x00", "")
            base = o + 20 + data_offset
            if base < 0 or base > len(self.data):
                raise ValueError(f"APKF component {i} base outside payload")
            self.component_headers.append(ComponentHeader(i, o, type_id, external, field2, field3, data_size, data_offset, base))

        off = struct.calcsize("<4s6I")
        global_i = 0
        guard = 0
        while off + 4 <= len(self.data):
            if guard > 10000:
                raise ValueError("APKF file-type table guard hit")
            guard += 1
            if struct.unpack_from("<I", self.data, off)[0] == 0:
                break
            base = off
            if off + 20 > len(self.data):
                break
            type_int, unk0, n_active, p_file_header_table, n_file_headers = struct.unpack_from("<5I", self.data, off)
            off += 20
            if n_active > len(self.component_headers):
                raise ValueError(f"APKF n_active_components too large: {n_active}")
            if n_file_headers > 250000:
                raise ValueError(f"APKF n_file_headers too large: {n_file_headers}")
            if off + 4 * len(self.component_headers) > len(self.data):
                break
            aligns = list(struct.unpack_from("<" + "I" * len(self.component_headers), self.data, off))
            off += 4 * len(self.component_headers)
            type_id = type_int.to_bytes(4, "little").decode("ascii", errors="replace").replace("\x00", "")
            p_headers = base + 12 + p_file_header_table
            self.file_type_headers.append({
                "file_type": type_id,
                "unk0": unk0,
                "n_active_components": n_active,
                "n_file_headers": n_file_headers,
                "file_header_table": hx(p_headers),
                "component_alignments": aligns,
                "header_offset": hx(base),
            })
            foff = p_headers
            for local_i in range(n_file_headers):
                if foff + 8 > len(self.data):
                    break
                fh_base = foff
                p_filename, fname_hash = struct.unpack_from("<II", self.data, foff)
                foff += 8
                sizes: List[int] = []
                if n_active:
                    if foff + 4 * n_active > len(self.data):
                        break
                    sizes = list(struct.unpack_from("<" + "I" * n_active, self.data, foff))
                    foff += 4 * n_active
                filename = read_cstr(self.data, fh_base + p_filename)
                offsets: List[Tuple[int, int]] = []
                for ci, comp_size in enumerate(sizes):
                    ch = self.component_headers[ci]
                    alignment = aligns[ci] & 0xFFFFFF
                    read_pos = self.align(max(0, ch.cursor_pos - 1), alignment)
                    start = ch.base_data_address + read_pos
                    end = start + comp_size
                    if end > len(self.data):
                        # Keep offsets for report, but parser should not crash on one bad component.
                        end = min(end, len(self.data))
                    offsets.append((start, end))
                    ch.cursor_pos = read_pos + comp_size
                self.files.append(APKFFileEntry(global_i, type_id, local_i, filename, fname_hash, fh_base, sizes, offsets))
                global_i += 1

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for f in self.files:
            counts[f.file_type] = counts.get(f.file_type, 0) + 1
        return {
            "header": self.header,
            "component_headers": [asdict(c) for c in self.component_headers],
            "file_type_headers": self.file_type_headers,
            "total_files": len(self.files),
            "counts_by_type": counts,
        }

# ------------------------- route handler extraction -------------------------

@dataclass
class PackProbe:
    path_name: str
    file_size: int
    detection: str
    route: str
    hsam_offsets: List[int]
    apkf_offsets: List[int]
    table: Optional[TableCandidate]
    outer_rows: List[OuterRow]
    compact_header: Dict[str, Any]
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path_name": self.path_name,
            "file_size": self.file_size,
            "file_size_hex": hx(self.file_size),
            "detection": self.detection,
            "route": self.route,
            "hsam_offsets": ";".join(hx(x) for x in self.hsam_offsets[:20]),
            "apkf_offsets": ";".join(hx(x) for x in self.apkf_offsets[:20]),
            "table_start": hx(self.table.start) if self.table else "",
            "table_rows": self.table.rows if self.table else 0,
            "table_score": self.table.score if self.table else 0,
            "outer_row_count": len(self.outer_rows),
            "compact_header": self.compact_header.get("is_compact_header", False),
            "compact_hsam_pointer": hx(self.compact_header.get("hsam_pointer")) if self.compact_header.get("hsam_pointer") is not None else "",
            "compact_apkf_pointer": hx(self.compact_header.get("apkf_pointer")) if self.compact_header.get("apkf_pointer") is not None else "",
            "reasons": " | ".join(self.reasons),
        }


def probe_pack_bytes(name: str, data: bytes) -> PackProbe:
    if data.startswith(NCH_MAGIC):
        return PackProbe(name, len(data), "WOS_NCH_REFERENCE_NOT_SM3", "NOT_SM3_WOS_REFERENCE_ONLY", [], find_all(data, b"APKF", 128), None, [], {}, ["starts_with_NCH"])
    hsam_offsets = find_all(data, b"hsam", 128)
    apkf_offsets = find_all(data, b"APKF", 512)
    marker_offsets = list(dict.fromkeys(hsam_offsets + apkf_offsets + find_all(data, b"mash", 128)))
    candidates = find_table_candidates(data, marker_offsets)
    best = candidates[0] if candidates and candidates[0].score >= 80 else None
    outer_rows = parse_outer_rows(data, best) if best else []
    marker_dict = {"hsam": hsam_offsets, "APKF": apkf_offsets}
    compact = detect_compact_header(data, marker_dict, allow_marker_fallback=(not outer_rows))

    reasons: List[str] = []
    detection = "SM3_PC_HSAM_PCPACK" if (data[0x30:0x34] == b"hsam" or hsam_offsets) else "UNKNOWN"

    type35 = [r for r in outer_rows if r.type_id == 0x35]
    type36 = [r for r in outer_rows if r.type_id == 0x36]
    real_type36 = [r for r in type36 if r.data_size > 0x28 and data[r.data_offset:r.data_offset + 4] == b"APKF"]
    stub36 = [r for r in type36 if r.data_size <= 0x28]
    hsam_outer = [r for r in outer_rows if data[r.data_offset:r.data_offset + 4] == b"hsam"]
    apkf_outer_any = [r for r in outer_rows if data[r.data_offset:r.data_offset + 4] == b"APKF"]

    compact_should_win = bool(compact.get("is_compact_header")) and not (type35 and stub36) and not real_type36
    if type35 and stub36:
        route = "VOICE_AUDIO_TYPE35_PLUS_TINY_TYPE36_STUB"
        reasons.append("type35_payload_plus_type36_0x28_stub")
    elif real_type36:
        route = "NORMAL_HSAM_TABLE_REAL_TYPE36_APKF"
        reasons.append("real_type36_apkf")
    elif compact_should_win:
        route = "COMPACT_HEADER_HSAM_APKF_WRAPPER"
        reasons.append(compact.get("reason", "compact_header"))
    elif stub36 and hsam_outer:
        route = "STUB_APKF_OUTER_HSAM_HEAVY"
        reasons.append("tiny_type36_stub_and_hsam_outer_payloads")
    elif apkf_outer_any:
        route = "TINY_OR_NONSTANDARD_APKF_RESOURCE"
        reasons.append("tiny_or_nonstandard_apkf_resource")
    elif apkf_offsets:
        route = "NON_TYPE36_APKF_MARKER_ROUTE"
        reasons.append("apkf_marker_exists_without_standard_type36_row")
    elif outer_rows:
        route = "OUTER_HSAM_TABLE_RAW_PRESERVE"
        reasons.append("outer_table_found_no_real_apkf")
    else:
        route = "UNRESOLVED_PROBE_ONLY"
        reasons.append("no_reliable_table_or_compact_header_found")
    return PackProbe(name, len(data), detection, route, hsam_offsets, apkf_offsets, best, outer_rows, compact, reasons)


def write_outer_payloads(data: bytes, probe: PackProbe, out_root: Path, max_outer_mb: int = 2048) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    base = ensure_dir(out_root / "01_OUTER_PAYLOADS")
    total = 0
    limit = max_outer_mb * 1024 * 1024
    for row in probe.outer_rows:
        payload = data[row.data_offset:row.end]
        strings = sample_strings(payload, 0, len(payload), limit=8192, max_strings=12)
        ext, category, reason = sniff_outer_ext(payload, strings)
        if row.type_id == 0x35:
            category = "VOICE_AUDIO_TYPE35_CANDIDATES"
            ext = ".type35.raw.bin"
            reason = "voice_audio_type35_candidate"
        elif row.type_id == 0x36 and row.data_size <= 0x28:
            category = "TINY_TYPE36_APKF_STUBS"
            ext = ".stub36.apkf"
            reason = "tiny_type36_stub"
        export = True
        skip = ""
        if total + len(payload) > limit:
            export = False
            skip = "max_outer_mb_limit"
        out_path = ""
        if export:
            folder = ensure_dir(base / category)
            fname = f"outer_{row.index:04d}_{hex32(row.hash_value)}_T{row.type_id:X}_off{row.data_offset:08X}_size{row.data_size:X}{ext}"
            p = folder / clean_name(fname, f"outer_{row.index:04d}")
            p.write_bytes(payload)
            total += len(payload)
            out_path = str(p)
        r = row.to_dict()
        r.update({"outer_category": category, "outer_ext": ext, "outer_reason": reason, "exported": export, "skip_reason": skip, "export_path": out_path, "string_sample": strings})
        rows.append(r)
    return rows



def write_compact_header_preserved_regions(data: bytes, probe: PackProbe, out_root: Path, max_outer_mb: int = 2048) -> List[Dict[str, Any]]:
    """Preserve compact-header hsam regions that are not represented by normal outer rows.

    v2.1 fix: compact-header packs may have a one-row tiny APKF stub table, but
    still contain useful hsam wrapper regions at 0x30 / secondary hsam markers.
    Export those regions so compact wrapper packs are not reduced to only the
    0x28 APKF stub.
    """
    if not probe.compact_header.get("is_compact_header"):
        return []
    base = ensure_dir(out_root / "01_OUTER_PAYLOADS" / "COMPACT_HEADER_HSAM_REGIONS")

    # Cover already-exported normal outer rows to avoid exact duplicates.
    covered: List[Tuple[int, int]] = [(r.data_offset, r.end) for r in probe.outer_rows]

    def is_covered(start: int) -> bool:
        return any(s <= start < e for s, e in covered)

    apkf_ptr = probe.compact_header.get("apkf_pointer")
    hsam_ptr = probe.compact_header.get("hsam_pointer")
    starts: List[int] = []
    if isinstance(hsam_ptr, int):
        starts.append(hsam_ptr)
    for off in probe.hsam_offsets:
        if off not in starts:
            starts.append(off)
    starts = sorted(x for x in starts if isinstance(x, int) and 0 <= x < len(data) and data[x:x+4] == b"hsam")

    boundaries = sorted(set(starts + [x for x in probe.apkf_offsets if 0 <= x <= len(data)] + [len(data)]))
    rows: List[Dict[str, Any]] = []
    total = 0
    limit = max_outer_mb * 1024 * 1024
    idx = 0

    for start in starts:
        if is_covered(start):
            continue
        # End at the next marker/APKF/EOF boundary.
        possible_ends = [b for b in boundaries if b > start]
        end = possible_ends[0] if possible_ends else len(data)
        if isinstance(apkf_ptr, int) and start < apkf_ptr and end > apkf_ptr:
            end = apkf_ptr
        if end <= start + 4:
            continue
        payload = data[start:end]
        export = True
        skip = ""
        out_path = ""
        if total + len(payload) > limit:
            export = False
            skip = "max_outer_mb_limit"
        if export:
            fname = f"compact_hsam_region_{idx:04d}_off{start:08X}_size{len(payload):X}.compact.hsam_region.bin"
            p = base / clean_name(fname, f"compact_region_{idx:04d}.bin")
            p.write_bytes(payload)
            out_path = str(p)
            total += len(payload)
        rows.append({
            "index": f"compact_{idx:04d}",
            "table_offset": "",
            "hash": "",
            "known_name": "",
            "type_hex": "COMPACT",
            "type_dec": "",
            "data_offset": hx(start),
            "data_offset_dec": start,
            "data_size": hx(len(payload)),
            "data_size_dec": len(payload),
            "data_end": hx(end),
            "data_magic": hexbytes(payload[:16]),
            "valid": True,
            "outer_category": "COMPACT_HEADER_HSAM_REGIONS",
            "outer_ext": ".compact.hsam_region.bin",
            "outer_reason": "compact_header_hsam_region_not_in_outer_rows",
            "exported": export,
            "skip_reason": skip,
            "export_path": out_path,
            "string_sample": sample_strings(payload, 0, len(payload), limit=8192, max_strings=12),
        })
        idx += 1
    return rows


def extract_apkf_archive(apkf_data: bytes, label: str, absolute_base: int, out_root: Path, output_layout: str = "smart_browse", max_inner_mb: int = 4096, write_payloads: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[Dict[str, Any]], Optional[str]]:
    inner_rows: List[Dict[str, Any]] = []
    action_rows: List[Dict[str, Any]] = []
    try:
        apkf = APKFArchive(apkf_data, label=label)
    except Exception as exc:
        return [], [{"action": "parse_apkf_failed", "label": label, "absolute_base": hx(absolute_base), "error": str(exc)}], None, str(exc)

    summary = apkf.summary()
    real_root = ensure_dir(out_root / "02_APKF_EXTRACTED_REAL_EXT")
    comp_root = ensure_dir(out_root / "03_APKF_COMPONENTS")
    raw_unknown_root = ensure_dir(out_root / "04_RAW_PRESERVED" / "UNKNOWN_APKF_GROUPS")
    total = 0
    limit = max_inner_mb * 1024 * 1024

    for f in apkf.files:
        safe = clean_name(f.filename, f"unknown_{f.file_type}_{f.global_index:05d}")
        ext = inner_extension(f.file_type, f.filename)
        category = (f.file_type or "UNKNOWN").upper() or "UNKNOWN"
        combined = bytearray()
        component_blobs: List[Tuple[int, bytes, int, int]] = []
        for ci, (s, e) in enumerate(f.component_offsets):
            blob = apkf.data[s:e]
            component_blobs.append((ci, blob, s, e))
            combined += blob
        combined_bytes = bytes(combined)

        exported = False
        skip_reason = ""
        real_path = ""
        if total + len(combined_bytes) > limit:
            skip_reason = "max_inner_mb_limit"
        else:
            if write_payloads:
                if output_layout in ("smart_browse", "research_full", "real_ext_only"):
                    dest_dir = ensure_dir(real_root / category)
                    fname = f"{hex32(f.filename_hash)}.{safe}{ext}"
                    real_file = dest_dir / clean_name(fname, f"file_{f.global_index:05d}{ext}")
                    real_file.write_bytes(combined_bytes)
                    real_path = str(real_file)
                    exported = True
                    total += len(combined_bytes)
                if output_layout in ("research_full", "component_only"):
                    comp_dir = ensure_dir(comp_root / category / f"{f.global_index:05d}_{hex32(f.filename_hash)}_{safe}")
                    for ci, blob, _s, _e in component_blobs:
                        (comp_dir / f"component{ci}_{len(blob)}bytes.bin").write_bytes(blob)
                    (comp_dir / "combined_raw.bin").write_bytes(combined_bytes)
                    write_json(comp_dir / "entry.json", f.to_dict())
                if category not in EXT_BY_TYPE:
                    unk_dir = ensure_dir(raw_unknown_root / category)
                    (unk_dir / f"{hex32(f.filename_hash)}.{safe}.combined_raw.bin").write_bytes(combined_bytes)
            else:
                skip_reason = "reports_only_payload_export_disabled"

        row = f.to_dict()
        if (f.file_type or "").upper() == "TEX":
            tex_meta = infer_tex_metadata_from_components(f.filename, component_blobs)
            row.update(tex_meta)
            if write_payloads and len(component_blobs) >= 2:
                row.update(maybe_export_tex_dds(out_root, f.filename, f.filename_hash, tex_meta, component_blobs[1][1]))
                row.update(maybe_export_tex_layout_lab(out_root, f.filename, f.filename_hash, {**tex_meta, **row}, component_blobs[1][1]))
            else:
                row.update({"tex_dds_export_status": "NOT_EXPORTED_REPORTS_ONLY", "tex_dds_export_reason": "payload_export_disabled_or_missing_component1", "tex_dds_export_file": ""})
                row.update({"tex_layout_review_status": "NOT_EXPORTED_REPORTS_ONLY", "tex_layout_review_reason": "payload_export_disabled_or_missing_component1", "tex_layout_candidate_modes": "", "tex_layout_lab_enabled": _tex_layout_lab_enabled(), "tex_layout_lab_candidate_count": 0, "tex_layout_lab_folder": "", "tex_layout_lab_manifest": ""})
        row.update({
            "source_apkf_label": label,
            "source_apkf_absolute_base": hx(absolute_base),
            "combined_raw_size": len(combined_bytes),
            "exported": exported,
            "skip_reason": skip_reason,
            "real_ext_file": real_path,
        })
        for ci, (_blob_i, _blob, s, e) in enumerate(component_blobs):
            row[f"component{ci}_absolute_start_in_pcpack"] = hx(absolute_base + s)
            row[f"component{ci}_absolute_end_in_pcpack"] = hx(absolute_base + e)
        inner_rows.append(row)

    action_rows.append({"action": "parse_apkf_ok", "label": label, "absolute_base": hx(absolute_base), "files": len(apkf.files), "counts_by_type": json.dumps(summary.get("counts_by_type", {}), sort_keys=True)})
    return inner_rows, action_rows, summary, None


def _inside_range(off: int, ranges: List[Tuple[int, int]]) -> bool:
    for start, end in ranges:
        if start < off < end:
            return True
    return False


def quick_apkf_header_check(payload: bytes) -> Tuple[bool, str]:
    """Cheap sanity check before treating an arbitrary APKF marker as a real archive.

    v2.5: MEGACITY can contain stray byte text "APKF" inside a real already-parsed
    type36 APKF payload. Those false markers previously produced scary parse warnings
    even though the pack extracted correctly. This check and the covered-range filter
    keep the report bundle focused on real problems.
    """
    if len(payload) < 28:
        return False, "too_small_for_apkf_header"
    if payload[:4] != b"APKF":
        return False, "missing_APKF_magic"
    try:
        _magic, version, _flag_field, _bool_field, comp_count, comp_table_ptr_raw, _file_table_ptr = struct.unpack_from("<4s6I", payload, 0)
    except Exception as e:
        return False, f"header_unpack_failed:{e}"
    if version not in (0x107, 263):
        return False, f"unexpected_version_{version}"
    if comp_count > 128:
        return False, f"component_count_too_large_{comp_count}"
    if comp_count == 0:
        # Valid for tiny 0x28 stubs. If this is a huge marker-to-EOF candidate,
        # it will still parse as a stub and produce 0 files without warning.
        return True, "valid_tiny_or_empty_apkf_stub_header"
    comp_off = comp_table_ptr_raw + 20
    if comp_off < 0 or comp_off + comp_count * 24 > len(payload):
        return False, "component_table_outside_payload"
    return True, "header_ok"


def apkf_slices_from_probe(data: bytes, probe: PackProbe) -> Tuple[List[Tuple[str, int, bytes, str]], List[Dict[str, Any]]]:
    """Return candidate APKF slices plus filtered marker report rows.

    Returns:
        (slices, filtered_marker_rows)
        slices are (label, absolute_offset, bytes, route_reason).
    """
    slices: List[Tuple[str, int, bytes, str]] = []
    filtered: List[Dict[str, Any]] = []
    seen: set[int] = set()
    covered_apkf_ranges: List[Tuple[int, int]] = []

    # Exact outer row APKF payloads first. These are authoritative because the
    # outer hsam table gives the exact payload size.
    for row in probe.outer_rows:
        if row.data_offset in seen:
            continue
        if data[row.data_offset:row.data_offset + 4] == b"APKF":
            payload = data[row.data_offset:row.end]
            ok, why = quick_apkf_header_check(payload)
            label = f"outer_{row.index:04d}_T{row.type_id:X}_{hex32(row.hash_value)}"
            if ok:
                slices.append((label, row.data_offset, payload, "outer_row_exact_size"))
                covered_apkf_ranges.append((row.data_offset, row.end))
                seen.add(row.data_offset)
            else:
                filtered.append({"label": label, "absolute_base": hx(row.data_offset), "reason": "outer_row_apkf_failed_sanity_check", "detail": why})

    # Compact header APKF pointer.
    if probe.compact_header.get("is_compact_header"):
        ptr = probe.compact_header.get("apkf_pointer")
        if isinstance(ptr, int) and ptr not in seen and data[ptr:ptr + 4] == b"APKF":
            payload = data[ptr:]
            ok, why = quick_apkf_header_check(payload)
            if ok:
                slices.append(("compact_header_apkf_pointer", ptr, payload, "compact_header_to_eof"))
                covered_apkf_ranges.append((ptr, len(data)))
                seen.add(ptr)
            else:
                filtered.append({"label": "compact_header_apkf_pointer", "absolute_base": hx(ptr), "reason": "compact_header_apkf_failed_sanity_check", "detail": why})

    # Non-type36 marker route: only parse APKF markers that are not already
    # inside an authoritative outer-row APKF range. This prevents false warnings
    # from random APKF byte strings inside MEGACITY/GAME's real inner archive.
    for idx, off in enumerate(probe.apkf_offsets):
        label = f"marker_apkf_{idx:03d}_off{off:08X}"
        if off in seen:
            filtered.append({"label": label, "absolute_base": hx(off), "reason": "already_parsed_authoritative_apkf", "detail": ""})
            continue
        if _inside_range(off, covered_apkf_ranges):
            filtered.append({"label": label, "absolute_base": hx(off), "reason": "inside_already_parsed_outer_apkf_range", "detail": ""})
            continue
        if data[off:off + 4] != b"APKF":
            continue
        payload = data[off:]
        ok, why = quick_apkf_header_check(payload)
        if not ok:
            filtered.append({"label": label, "absolute_base": hx(off), "reason": "marker_apkf_failed_sanity_check", "detail": why})
            continue
        slices.append((label, off, payload, "marker_to_eof_non_type36_route"))
        seen.add(off)
    return slices, filtered


def extract_one_bytes(display_name: str, data: bytes, out_dir: Path, output_layout: str = "smart_browse", max_outer_mb: int = 2048, max_inner_mb: int = 4096, write_payloads: bool = True) -> Dict[str, Any]:
    pack_name = clean_name(Path(display_name).stem, "pack")
    root = ensure_dir(out_dir / pack_name)
    reports = ensure_dir(root / "00_REPORTS")
    probe = probe_pack_bytes(display_name, data)

    write_json(reports / "PACK_PROBE.json", probe.to_dict())
    (reports / "ROUTE_HANDLER_SUMMARY.txt").write_text(
        f"{TOOL_NAME} {TOOL_VERSION}\n"
        f"Pack: {display_name}\n"
        f"Size: {len(data)} ({hx(len(data))})\n"
        f"Detection: {probe.detection}\n"
        f"Route: {probe.route}\n"
        f"Reasons: {' | '.join(probe.reasons)}\n"
        f"Outer rows: {len(probe.outer_rows)}\n"
        f"APKF markers: {', '.join(hx(x) for x in probe.apkf_offsets[:20])}\n"
        f"hsam markers: {', '.join(hx(x) for x in probe.hsam_offsets[:20])}\n"
        f"\nDONE NOTE:\nThis is route-handler extraction, not patching. Original pack was not modified.\n",
        encoding="utf-8",
    )

    write_csv(reports / "OUTER_ROWS.csv", [r.to_dict() for r in probe.outer_rows])
    write_csv(reports / "TABLE_CANDIDATE_SELECTED.csv", [probe.table.to_dict()] if probe.table else [])
    write_csv(reports / "STRING_SAMPLES.csv", [{"offset": hx(o), "text": s} for o, s in extract_ascii_strings(data[:min(len(data), 2 * 1024 * 1024)], max_count=1000)])

    action_rows: List[Dict[str, Any]] = []
    outer_export_rows: List[Dict[str, Any]] = []
    inner_rows: List[Dict[str, Any]] = []
    apkf_summaries: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if write_payloads and probe.outer_rows:
        outer_export_rows = write_outer_payloads(data, probe, root, max_outer_mb=max_outer_mb)
        action_rows.append({"action": "outer_payloads_exported", "count": len([r for r in outer_export_rows if r.get("exported")]), "note": "all valid outer rows were preserved subject to max_outer_mb"})

    if write_payloads and probe.compact_header.get("is_compact_header"):
        compact_rows = write_compact_header_preserved_regions(data, probe, root, max_outer_mb=max_outer_mb)
        if compact_rows:
            outer_export_rows.extend(compact_rows)
            action_rows.append({"action": "compact_header_hsam_regions_preserved", "count": len([r for r in compact_rows if r.get("exported")]), "note": "v2.1 preserved compact header hsam regions that were not represented by normal outer rows"})

    # Always try APKF slices for known/marker routes. Stub 0x28 APKF will produce parse info or small failure instead of blocking.
    apkf_slices, filtered_apkf_markers = apkf_slices_from_probe(data, probe)
    for fr in filtered_apkf_markers:
        action_rows.append({"action": "apkf_marker_filtered", **fr})
    for label, base, payload, reason in apkf_slices:
        rows, actions, summary, error = extract_apkf_archive(payload, label=label, absolute_base=base, out_root=root, output_layout=output_layout, max_inner_mb=max_inner_mb, write_payloads=write_payloads)
        for a in actions:
            a["route_reason"] = reason
            action_rows.append(a)
        if summary:
            summary_row = {"label": label, "absolute_base": hx(base), "route_reason": reason, "total_files": summary.get("total_files"), "counts_by_type": json.dumps(summary.get("counts_by_type", {}), sort_keys=True)}
            apkf_summaries.append(summary_row)
        if error:
            errors.append({"label": label, "absolute_base": hx(base), "route_reason": reason, "error": error})
        inner_rows.extend(rows)

    write_csv(reports / "OUTER_PAYLOAD_EXPORTS.csv", outer_export_rows)
    write_csv(reports / "INNER_APKF_FILES.csv", inner_rows)
    write_csv(reports / "APKF_SUMMARIES.csv", apkf_summaries)
    write_csv(reports / "APKF_PARSE_ERRORS.csv", errors)
    write_csv(reports / "APKF_MARKER_FILTERED.csv", filtered_apkf_markers)
    write_csv(reports / "HANDLER_ACTIONS.csv", action_rows)

    resource_summary = write_resource_browse_reports(reports, inner_rows)
    if inner_rows:
        action_rows.append({"action": "resource_browse_index_written", "count": len(inner_rows), "note": "v2.8 wrote RESOURCE_BROWSE_INDEX.csv/html and type-specific hint reports"})
        write_csv(reports / "HANDLER_ACTIONS.csv", action_rows)

    final = {
        "pack": display_name,
        "out_dir": str(root),
        "probe": probe.to_dict(),
        "outer_exports": len([r for r in outer_export_rows if r.get("exported")]),
        "inner_files": len(inner_rows),
        "apkf_summaries": apkf_summaries,
        "parse_errors": errors,
        "filtered_apkf_markers": filtered_apkf_markers,
        "resource_metadata_summary": resource_summary,
        "v2_8_browse_reports": [
            "RESOURCE_BROWSE_INDEX.csv",
            "RESOURCE_BROWSE_INDEX.html",
        "PACK_BROWSE_DASHBOARD.html",
        "RESOURCE_NAVIGATION_INDEX.csv",
        "RESOURCE_DEPENDENCY_NAVIGATION.csv",
        "RESOURCE_DEPENDENCY_NAVIGATION.html",
        "RESOURCE_FAMILY_COUNTS.csv",
            "RESOURCE_TYPE_COUNTS.csv",
            "TEX_RESOURCE_HINTS.csv",
            "MESH_RESOURCE_HINTS.csv",
            "MAT_RESOURCE_HINTS.csv",
            "ANIM_RESOURCE_HINTS.csv",
        ],
    }
    write_json(reports / "EXTRACT_RESULT.json", final)
    return final

# ------------------------- folder/zip handling -------------------------

def discover_packs(root: Path, recursive: bool = True, include_zips: bool = False) -> List[Path]:
    if root.is_file():
        return [root]
    pattern = "**/*" if recursive else "*"
    files: List[Path] = []
    for p in root.glob(pattern):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in PACK_EXTS or (include_zips and ext in ZIP_EXTS):
            files.append(p)
    return sorted(files, key=lambda p: str(p).lower())


# ------------------------- CSV target pack list resolver -------------------------

def normalize_pack_request_name(value: str) -> str:
    """Normalize a CSV requested pack name for matching against files on disk."""
    v = (value or "").strip().strip('"').strip("'")
    v = v.replace("\\", "/")
    v = Path(v).name if "/" in v else v
    return v.lower()


def request_keys_for_name(value: str) -> List[str]:
    base = normalize_pack_request_name(value)
    if not base:
        return []
    keys = {base}
    stem = Path(base).stem.lower()
    suffix = Path(base).suffix.lower()
    if stem:
        keys.add(stem)
    if not suffix and stem:
        # Most requested lists use bare pack names. Search common SM3 pack extensions too.
        for ext in [".pcpack", ".pcapk", ".apkf", ".bin", ".zip"]:
            keys.add(stem + ext)
    return sorted(keys)


def read_pack_requests_from_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """Read target pack names from CSV or plain text.

    Supported CSV headers: pack, pack_name, filename, file, name, path, source_input.
    If no known header is found, the first non-empty column is used. Plain one-name-per-line
    text files are also accepted.
    """
    raw = csv_path.read_text(encoding="utf-8-sig", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return []
    preferred = ["pack", "pack_name", "filename", "file", "name", "path", "source_input"]
    rows: List[Dict[str, Any]] = []
    try:
        sample = "\n".join(lines[:10])
        dialect = csv.Sniffer().sniff(sample) if ("," in sample or "\t" in sample or ";" in sample) else csv.excel
        first_cell = lines[0].split(",")[0].split("\t")[0].split(";")[0].strip().lower()
        forced_header = first_cell in preferred
        sniff_header = csv.Sniffer().has_header(sample) if ("," in sample or "\t" in sample or ";" in sample) else False
        has_header = forced_header or sniff_header
    except Exception:
        dialect = csv.excel
        first_cell = lines[0].split(",")[0].split("\t")[0].split(";")[0].strip().lower()
        has_header = first_cell in preferred
    if has_header:
        reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
        fieldnames = [f or "" for f in (reader.fieldnames or [])]
        lower_map = {f.lower().strip(): f for f in fieldnames}
        chosen = None
        for col in preferred:
            if col in lower_map:
                chosen = lower_map[col]
                break
        for idx, row in enumerate(reader, 1):
            val = ""
            if chosen:
                val = row.get(chosen, "") or ""
            else:
                for f in fieldnames:
                    if row.get(f, "").strip():
                        val = row.get(f, "")
                        break
            val = (val or "").strip()
            if val and not val.startswith("#"):
                rows.append({"request_index": len(rows) + 1, "requested_name": val, "source_row": idx + 1, "source_column": chosen or "first_non_empty"})
    else:
        for idx, line in enumerate(lines, 1):
            val = line.strip().strip(',')
            if not val or val.startswith("#"):
                continue
            # For accidental CSV without headers, use first comma/tab separated field.
            for sep in [",", "\t", ";"]:
                if sep in val:
                    val = val.split(sep)[0].strip()
                    break
            if val:
                rows.append({"request_index": len(rows) + 1, "requested_name": val, "source_row": idx, "source_column": "plain_text_or_first_column"})
    return rows


def resolve_csv_target_packs(csv_path: Path, pack_root: Path, recursive: bool = True, include_zips: bool = False, log=print) -> Tuple[List[Path], Dict[str, Any]]:
    """Resolve requested pack names from a CSV/text file against a folder of SM3 packs."""
    requests = read_pack_requests_from_csv(csv_path)
    candidates = discover_packs(pack_root, recursive=recursive, include_zips=include_zips)
    by_key: Dict[str, List[Path]] = {}
    for p in candidates:
        keys = {p.name.lower(), p.stem.lower()}
        for k in keys:
            by_key.setdefault(k, []).append(p)
    selected: List[Path] = []
    selected_seen: set[str] = set()
    request_rows: List[Dict[str, Any]] = []
    match_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []
    duplicate_rows: List[Dict[str, Any]] = []
    for req in requests:
        name = str(req.get("requested_name") or "").strip()
        keys = request_keys_for_name(name)
        matches: List[Path] = []
        for k in keys:
            for p in by_key.get(k, []):
                if p not in matches:
                    matches.append(p)
        # Stable ordering: shortest relative path first, then name.
        def sort_key(path: Path):
            try:
                rel = str(path.relative_to(pack_root))
            except Exception:
                rel = str(path)
            return (len(rel), rel.lower())
        matches = sorted(matches, key=sort_key)
        status = "FOUND" if matches else "MISSING"
        request_row = dict(req)
        request_row.update({
            "normalized_keys": " | ".join(keys),
            "match_count": len(matches),
            "status": status,
            "chosen_path": str(matches[0]) if matches else "",
        })
        request_rows.append(request_row)
        if not matches:
            missing_rows.append(request_row)
            continue
        for mi, m in enumerate(matches, 1):
            row = dict(req)
            row.update({"match_index": mi, "matched_path": str(m), "chosen_for_batch": mi == 1})
            match_rows.append(row)
            if mi > 1:
                duplicate_rows.append(row)
        key = str(matches[0].resolve()) if matches[0].exists() else str(matches[0])
        if key not in selected_seen:
            selected.append(matches[0])
            selected_seen.add(key)
    report = {
        "csv_path": str(csv_path),
        "pack_root": str(pack_root),
        "recursive": recursive,
        "include_zips": include_zips,
        "request_rows": request_rows,
        "match_rows": match_rows,
        "missing_rows": missing_rows,
        "duplicate_rows": duplicate_rows,
        "request_count": len(request_rows),
        "matched_request_count": len([r for r in request_rows if r.get("status") == "FOUND"]),
        "missing_request_count": len(missing_rows),
        "selected_pack_count": len(selected),
        "candidate_file_count": len(candidates),
    }
    log(f"CSV target list: {len(requests)} requested, {report['matched_request_count']} matched, {len(selected)} selected, {len(missing_rows)} missing.")
    return selected, report



def resolve_named_target_packs(target_names: List[str], pack_root: Path, recursive: bool = True, include_zips: bool = False, log=print) -> Tuple[List[Path], Dict[str, Any]]:
    """Resolve an in-tool target list without requiring the user to create a CSV.

    Used by the v2.11 payload extraction test preset. The report shape matches
    the CSV target resolver so existing CSV_TARGET_* master reports still work.
    """
    candidates = discover_packs(pack_root, recursive=recursive, include_zips=include_zips)
    by_key: Dict[str, List[Path]] = {}
    for p in candidates:
        for k in {p.name.lower(), p.stem.lower()}:
            by_key.setdefault(k, []).append(p)
    selected: List[Path] = []
    selected_seen: set[str] = set()
    request_rows: List[Dict[str, Any]] = []
    match_rows: List[Dict[str, Any]] = []
    missing_rows: List[Dict[str, Any]] = []
    duplicate_rows: List[Dict[str, Any]] = []

    for idx, name in enumerate(target_names, 1):
        keys = request_keys_for_name(name)
        matches: List[Path] = []
        for k in keys:
            for found in by_key.get(k, []):
                if found not in matches:
                    matches.append(found)
        def sort_key(path: Path):
            try:
                rel = str(path.relative_to(pack_root))
            except Exception:
                rel = str(path)
            return (len(rel), rel.lower())
        matches = sorted(matches, key=sort_key)
        status = "FOUND" if matches else "MISSING"
        request_row = {
            "request_index": idx,
            "requested_name": name,
            "source_row": idx,
            "source_column": "built_in_payload_test_preset",
            "normalized_keys": " | ".join(keys),
            "match_count": len(matches),
            "status": status,
            "chosen_path": str(matches[0]) if matches else "",
        }
        request_rows.append(request_row)
        if not matches:
            missing_rows.append(request_row)
            continue
        for mi, matched in enumerate(matches, 1):
            row = {
                "request_index": idx,
                "requested_name": name,
                "source_row": idx,
                "source_column": "built_in_payload_test_preset",
                "match_index": mi,
                "matched_path": str(matched),
                "chosen_for_batch": mi == 1,
            }
            match_rows.append(row)
            if mi > 1:
                duplicate_rows.append(row)
        key = str(matches[0].resolve()) if matches[0].exists() else str(matches[0])
        if key not in selected_seen:
            selected.append(matches[0])
            selected_seen.add(key)

    report = {
        "csv_path": "BUILT_IN_V2_11_PAYLOAD_TEST_PRESET",
        "pack_root": str(pack_root),
        "recursive": recursive,
        "include_zips": include_zips,
        "request_rows": request_rows,
        "match_rows": match_rows,
        "missing_rows": missing_rows,
        "duplicate_rows": duplicate_rows,
        "request_count": len(request_rows),
        "matched_request_count": len([r for r in request_rows if r.get("status") == "FOUND"]),
        "missing_request_count": len(missing_rows),
        "selected_pack_count": len(selected),
        "candidate_file_count": len(candidates),
        "preset_name": "v2.11 payload extraction proof set",
    }
    log(f"Payload test preset: {len(target_names)} requested, {report['matched_request_count']} matched, {len(selected)} selected, {len(missing_rows)} missing.")
    return selected, report


def extract_file(path: Path, out_dir: Path, output_layout: str, max_outer_mb: int, max_inner_mb: int, write_payloads: bool, log=print) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                ext = Path(info.filename).suffix.lower()
                if ext not in PACK_EXTS:
                    continue
                log(f"[ZIP] {path.name} :: {info.filename}")
                data = zf.read(info)
                display = f"{path.name}::{info.filename}"
                results.append(extract_one_bytes(display, data, out_dir, output_layout, max_outer_mb, max_inner_mb, write_payloads))
        return results
    log(f"[PACK] {path}")
    data = path.read_bytes()
    results.append(extract_one_bytes(str(path), data, out_dir, output_layout, max_outer_mb, max_inner_mb, write_payloads))
    return results




def build_run_verdict(*, input_count: int, processed_count: int, hard_error_count: int, apkf_parse_error_count: int, route_counts: Dict[str, int], detection_counts: Dict[str, int], csv_target_report: Optional[Dict[str, Any]], stopped: bool, write_payloads: bool, output_layout: str) -> Dict[str, Any]:
    """Return a simple top-level PASS/FAIL verdict for batch testing.

    PASS means the handler run completed with at least one processed pack, no hard
    exceptions, no APKF parser warnings/errors, no missing CSV targets, and no user stop.
    Any of those conditions becomes FAIL so the user does not have to inspect five CSVs
    before knowing whether the run needs review.
    """
    issues: List[str] = []
    warnings: List[str] = []
    csv_summary: Optional[Dict[str, Any]] = None
    if csv_target_report is not None:
        csv_summary = {k: v for k, v in csv_target_report.items() if k not in {"request_rows", "match_rows", "missing_rows", "duplicate_rows"}}
        missing = int(csv_target_report.get("missing_request_count") or 0)
        duplicates = int(csv_target_report.get("duplicate_request_count") or 0)
        if missing:
            issues.append(f"CSV target list has {missing} missing request(s)")
        if duplicates:
            warnings.append(f"CSV target list has {duplicates} duplicate match group(s); first/best match was selected where possible")
    if input_count <= 0:
        issues.append("No input pack files were found")
    if processed_count <= 0:
        issues.append("No pack outputs were processed")
    if hard_error_count:
        issues.append(f"{hard_error_count} hard extractor error(s)")
    if apkf_parse_error_count:
        issues.append(f"{apkf_parse_error_count} APKF parse warning/error row(s)")
    if stopped:
        issues.append("Run was stopped before completion")

    verdict = "PASS" if not issues else "FAIL"
    return {
        "verdict": verdict,
        "pass": verdict == "PASS",
        "needs_review": verdict != "PASS" or bool(warnings),
        "issues": issues,
        "warnings": warnings,
        "input_count": input_count,
        "processed_count": processed_count,
        "hard_error_count": hard_error_count,
        "apkf_parse_error_count": apkf_parse_error_count,
        "route_counts": route_counts,
        "detection_counts": detection_counts,
        "csv_target_list_used": csv_target_report is not None,
        "csv_target_summary": csv_summary,
        "output_layout": output_layout,
        "write_payloads": write_payloads,
        "meaning": "PASS = no hard errors, no APKF parse warnings/errors, no missing CSV targets, at least one pack processed, and run not stopped.",
    }


def _norm_path_variants(path_value: Any) -> List[str]:
    """Return simple string variants for a path so reports can be sanitized consistently."""
    if not path_value:
        return []
    raw = str(path_value)
    variants = {raw, raw.replace("\\", "/"), raw.replace("/", "\\")}
    try:
        resolved = str(Path(raw).resolve())
        variants.add(resolved)
        variants.add(resolved.replace("\\", "/"))
        variants.add(resolved.replace("/", "\\"))
    except Exception:
        pass
    return sorted([v for v in variants if v], key=len, reverse=True)


def sanitize_report_text_for_diagnostic_bundle(text: str, out_dir: Optional[Path] = None, extra_roots: Optional[List[Path]] = None) -> str:
    """Sanitize report text before it is written into diagnostic report bundles.

    v2.12 privacy fix:
    - local absolute Windows paths become LOCAL_PATH_REDACTED/<filename when obvious>
    - container sandbox paths are redacted
    - output-folder absolute paths are replaced with OUTPUT_ROOT

    This is intentionally applied only to the diagnostic report bundles. The local reports on
    the user's PC can keep full paths so Open Output/Open Reports still works.
    """
    if not text:
        return text
    sanitized = text

    # Replace known output/root paths first so relative report structure stays readable.
    roots: List[Tuple[str, str]] = []
    if out_dir is not None:
        roots.append((str(out_dir), "OUTPUT_ROOT"))
    if extra_roots:
        for idx, root in enumerate(extra_roots, 1):
            roots.append((str(root), f"INPUT_ROOT_{idx}"))
    for root, repl in roots:
        for variant in _norm_path_variants(root):
            sanitized = sanitized.replace(variant, repl)
            # JSON-escaped backslash form.
            sanitized = sanitized.replace(variant.replace("\\", "\\\\"), repl)

    def _redact_windows_path(match: re.Match) -> str:
        value = match.group(0)
        raw = value.replace("\\\\", "\\")
        tail = re.split(r"[\\/]", raw.rstrip("\\/"))[-1]
        if tail and "." in tail and len(tail) < 120:
            return f"LOCAL_PATH_REDACTED/{tail}"
        return "LOCAL_PATH_REDACTED"

    # Normal and JSON-escaped Windows absolute paths.
    sanitized = re.sub(r"[A-Za-z]:(?:\\\\|\\|/)[^\"'\r\n,;<>|]*", _redact_windows_path, sanitized)

    # Common local/container absolute paths that can appear in reports while testing.
    sanitized = re.sub(r"/" + r"mnt/data/[^\"'\r\n,;<>|]*", "SANDBOX_PATH_REDACTED", sanitized)
    sanitized = re.sub(r"/" + r"home/[^\"'\r\n,;<>|]*", "LOCAL_PATH_REDACTED", sanitized)
    sanitized = re.sub(r"/Users/[^\"'\r\n,;<>|]*", "LOCAL_PATH_REDACTED", sanitized)

    return sanitized


def _is_text_report_file(path: Path) -> bool:
    return path.suffix.lower() in {".txt", ".csv", ".json", ".html", ".htm", ".log", ".md"}


def _zip_report_file_sanitized(zf: zipfile.ZipFile, path: Path, arcname: str, out_dir: Path) -> None:
    """Write a report file into a zip, sanitizing text report content when possible."""
    if _is_text_report_file(path):
        text = path.read_text(encoding="utf-8", errors="replace")
        zf.writestr(arcname, sanitize_report_text_for_diagnostic_bundle(text, out_dir=out_dir))
    else:
        zf.write(path, arcname)


def build_diagnostic_report_zip(out_dir: Path, log=print) -> Path:
    """Create a compact diagnostic zip with the reports support diagnostics need.

    This intentionally excludes extracted payload folders so the user can send diagnostics
    without uploading huge game-resource dumps. It includes master reports plus each
    pack's 00_REPORTS files that explain routing, outer rows, APKF summaries, errors,
    and handler actions.
    """
    out_dir = Path(out_dir)
    report_zip = out_dir / REPORT_ZIP_NAME
    if report_zip.exists():
        report_zip.unlink()
    log("Report zip generation is disabled in this public release build.")
    return report_zip
    master = out_dir / "00_MASTER_REPORTS"
    pack_report_dirs = sorted([p for p in out_dir.glob("*/00_REPORTS") if p.is_dir()], key=lambda p: str(p).lower())

    master_keep = {
        "BATCH_INPUT_MANIFEST.csv",
        "MASTER_EXTRACT_SUMMARY.csv",
        "MASTER_EXTRACT_SUMMARY.json",
        "MASTER_EXTRACT_SUMMARY.txt",
        "MASTER_ERRORS.csv",
        "MASTER_APKF_PARSE_ERRORS.csv",
        "PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv",
        "PER_PACK_REPORT_INDEX.csv",
        "CSV_TARGET_REQUESTS.csv",
        "CSV_TARGET_MATCHES.csv",
        "CSV_TARGET_MISSING.csv",
        "CSV_TARGET_DUPLICATE_MATCHES.csv",
        "CSV_TARGET_SUMMARY.json",
        "CSV_TARGET_SUMMARY.txt",
        "RUN_VERDICT.txt",
        "RUN_VERDICT.json",
        "RUN_VERDICT.csv",
        "MASTER_ROUTE_DASHBOARD.txt",
        "MASTER_ROUTE_DASHBOARD.json",
        "MASTER_ROUTE_COUNTS.csv",
        "MASTER_DETECTION_COUNTS.csv",
        "MASTER_TOP_PACKS_BY_INNER_FILES.csv",
        "MASTER_TOP_PACKS_BY_OUTER_ROWS.csv",
        "MASTER_TOP_PACKS_BY_OUTER_EXPORTS.csv",
        "MASTER_ROUTE_GROUPS_INDEX.csv",
        "MASTER_REPORT_INDEX.html",
        "FULL_FOLDER_PHASE_STATUS.txt",
        "FULL_FOLDER_PHASE_STATUS.json",
        "ROUTE_HANDLER_NEXT_PHASE_PLAN.txt",
        "MASTER_RESOURCE_TYPE_COUNTS.csv",
        "MASTER_RESOURCE_EXTENSION_COUNTS.csv",
        "MASTER_RESOURCE_FAMILY_COUNTS.csv",
        "MASTER_TOP_PACKS_BY_TEX.csv",
        "MASTER_TOP_PACKS_BY_MESH.csv",
        "MASTER_TOP_PACKS_BY_MAT.csv",
        "MASTER_TOP_PACKS_BY_ANIM.csv",
        "MASTER_TOP_PACKS_BY_CVX.csv",
        "MASTER_TOP_PACKS_BY_UNKNOWN.csv",
        "MASTER_RESOURCE_PACK_MATRIX.csv",
        "MASTER_MESH_METADATA_SUMMARY.csv",
        "MASTER_MESH_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_MESH_REVIEW_PRIORITY_COUNTS.csv",
        "MASTER_MAT_METADATA_SUMMARY.csv",
        "MASTER_MAT_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_MAT_ROLE_COUNTS.csv",
        "MASTER_ANIM_METADATA_SUMMARY.csv",
        "MASTER_ANIM_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_ANIM_FAMILY_COUNTS.csv",
        "MASTER_ANIM_SWAP_SAFETY_COUNTS.csv",
        "MASTER_RESOURCE_DEPENDENCY_HINTS.csv",
        "MASTER_RESOURCE_DEPENDENCY_ACTION_COUNTS.csv",
        "MASTER_RESOURCE_NAVIGATION_INDEX.csv",
        "MASTER_DEPENDENCY_NAVIGATION_INDEX.csv",
        "MASTER_PACK_BROWSE_INDEX.html",
        "MASTER_BETTER_BROWSE_GUIDE.txt",
        "MASTER_TEX_METADATA_SUMMARY.csv",
        "MASTER_TEX_FORMAT_COUNTS.csv",
        "MASTER_TEX_DIMENSION_COUNTS.csv",
        "MASTER_TEX_MIP_COUNTS.csv",
        "MASTER_TEX_METADATA_CONFIDENCE.csv",
        "MASTER_TOP_PACKS_BY_TEX_METADATA_READY.csv",
        "MASTER_TEX_DDS_EXPORT_CANDIDATES.csv",
        "MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "MASTER_TEX_LAYOUT_CANDIDATES.csv",
        "MASTER_TEX_LAYOUT_STATUS_COUNTS.csv",
        "MASTER_TEX_LAYOUT_LOCK_APPLIED.csv",
        "MASTER_TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "MASTER_TEX_DDS_EXPORT_CANDIDATES.csv",
        "MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "MASTER_TEX_LAYOUT_CANDIDATES.csv",
        "MASTER_TEX_LAYOUT_STATUS_COUNTS.csv",
        "MASTER_TEX_LAYOUT_LOCK_APPLIED.csv",
        "MASTER_TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "MASTER_TEX_REVIEW_QUEUE.csv",
        "MASTER_TEX_REVIEW_QUEUE.csv",
        "MASTER_TEX_DDS_EXPORT_STATUS_COUNTS.csv",
        "MASTER_TEX_REVIEW_REASON_COUNTS.csv",
        "MASTER_TEX_REVIEW_TRIAGE.csv",
        "MASTER_TEX_LOW_CONFIDENCE_BY_PACK.csv",
        "MASTER_TEX_REVIEW_ACTION_COUNTS.csv",
        "MASTER_TEX_REVIEW_PRIORITY_COUNTS.csv",
        "MASTER_TEX_REVIEW_GROUP_COUNTS.csv",
        "MASTER_TEX_DDS_EXPORT_STATUS_COUNTS.csv",
        "MASTER_TEX_REVIEW_REASON_COUNTS.csv",
        "MASTER_TEX_REVIEW_TRIAGE.csv",
        "MASTER_TEX_LOW_CONFIDENCE_BY_PACK.csv",
        "MASTER_TEX_REVIEW_ACTION_COUNTS.csv",
        "MASTER_TEX_REVIEW_PRIORITY_COUNTS.csv",
        "MASTER_TEX_REVIEW_GROUP_COUNTS.csv",
        "MASTER_BROWSE_OUTPUT_GUIDE.txt",
        "MASTER_EXTRACTION_READINESS.csv",
        "MASTER_PAYLOAD_TEST_CANDIDATES.csv",
        "MASTER_FILETYPE_METADATA_PRIORITY.csv",
        "MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv",
        "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.txt",
        "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.json",
        "MASTER_PACK_EXTRACTION_MODE_RECOMMENDATIONS.csv",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.txt",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.json",
        "MASTER_RECOMMENDED_WORKFLOW.txt",
        "MASTER_WORKFLOW_RECOMMENDED.html",
        "MASTER_WORKFLOW_SHORTCUTS.csv",
        "MASTER_OPEN_OUTPUT_SHORTCUTS.csv",
        "MASTER_RELEASE_READINESS_CHECKLIST.csv",
        "MASTER_WORKFLOW_MODES.csv",
        "MASTER_WORKFLOW_STATUS.json",
    }
    pack_keep = {
        "ROUTE_HANDLER_SUMMARY.txt",
        "PACK_PROBE.json",
        "OUTER_ROWS.csv",
        "TABLE_CANDIDATE_SELECTED.csv",
        "OUTER_PAYLOAD_EXPORTS.csv",
        "INNER_APKF_FILES.csv",
        "APKF_SUMMARIES.csv",
        "APKF_PARSE_ERRORS.csv",
        "APKF_MARKER_FILTERED.csv",
        "HANDLER_ACTIONS.csv",
        "EXTRACT_RESULT.json",
        "STRING_SAMPLES.csv",
        "RESOURCE_BROWSE_INDEX.csv",
        "RESOURCE_BROWSE_INDEX.html",
        "PACK_BROWSE_DASHBOARD.html",
        "RESOURCE_NAVIGATION_INDEX.csv",
        "RESOURCE_DEPENDENCY_NAVIGATION.csv",
        "RESOURCE_DEPENDENCY_NAVIGATION.html",
        "RESOURCE_FAMILY_COUNTS.csv",
        "RESOURCE_TYPE_COUNTS.csv",
        "RESOURCE_EXTENSION_COUNTS.csv",
        "RESOURCE_COMPONENT_LAYOUT_COUNTS.csv",
        "TEX_RESOURCE_HINTS.csv",
        "TEX_METADATA_HINTS.csv",
        "TEX_FORMAT_COUNTS.csv",
        "TEX_DIMENSION_COUNTS.csv",
        "TEX_DDS_EXPORTS.csv",
        "TEX_REVIEW_REASON_COUNTS.csv",
        "TEX_REVIEW_TRIAGE.csv",
        "TEX_MEDIUM_REVIEW_QUEUE.csv",
        "TEX_REVIEW_ACTION_COUNTS.csv",
        "TEX_REVIEW_PRIORITY_COUNTS.csv",
        "TEX_REVIEW_GROUP_COUNTS.csv",
        "TEX_DDS_EXPORTS.csv",
        "TEX_REVIEW_REASON_COUNTS.csv",
        "TEX_REVIEW_TRIAGE.csv",
        "TEX_MEDIUM_REVIEW_QUEUE.csv",
        "TEX_REVIEW_ACTION_COUNTS.csv",
        "TEX_REVIEW_PRIORITY_COUNTS.csv",
        "TEX_REVIEW_GROUP_COUNTS.csv",
        "TEX_DDS_EXPORT_CANDIDATES.csv",
        "TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "TEX_LAYOUT_CANDIDATES.csv",
        "TEX_LAYOUT_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_APPLIED.csv",
        "TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.txt",
        "TEX_LAYOUT_LOCK_MAP_LOADED.json",
        "TEX_DDS_EXPORT_CANDIDATES.csv",
        "TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "TEX_LAYOUT_CANDIDATES.csv",
        "TEX_LAYOUT_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_APPLIED.csv",
        "TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.txt",
        "TEX_LAYOUT_LOCK_MAP_LOADED.json",
        "TEX_REVIEW_QUEUE.csv",
        "TEX_REVIEW_QUEUE.csv",
        "MESH_RESOURCE_HINTS.csv",
        "MAT_RESOURCE_HINTS.csv",
        "ANIM_RESOURCE_HINTS.csv",
        "MESH_METADATA_HINTS.csv",
        "MESH_COMPONENT_LAYOUT_COUNTS.csv",
        "MESH_REVIEW_PRIORITY_COUNTS.csv",
        "MAT_METADATA_HINTS.csv",
        "MAT_COMPONENT_LAYOUT_COUNTS.csv",
        "MAT_ROLE_COUNTS.csv",
        "ANIM_METADATA_HINTS.csv",
        "ANIM_COMPONENT_LAYOUT_COUNTS.csv",
        "ANIM_FAMILY_COUNTS.csv",
        "ANIM_SWAP_SAFETY_COUNTS.csv",
        "RESOURCE_DEPENDENCY_HINTS.csv",
        "RESOURCE_DEPENDENCY_ACTION_COUNTS.csv",
        "ANIM_RESOURCE_HINTS.csv",
        "MESH_METADATA_HINTS.csv",
        "MESH_COMPONENT_LAYOUT_COUNTS.csv",
        "MESH_REVIEW_PRIORITY_COUNTS.csv",
        "MAT_METADATA_HINTS.csv",
        "MAT_COMPONENT_LAYOUT_COUNTS.csv",
        "MAT_ROLE_COUNTS.csv",
        "ANIM_METADATA_HINTS.csv",
        "ANIM_COMPONENT_LAYOUT_COUNTS.csv",
        "ANIM_FAMILY_COUNTS.csv",
        "ANIM_SWAP_SAFETY_COUNTS.csv",
        "RESOURCE_DEPENDENCY_HINTS.csv",
        "RESOURCE_DEPENDENCY_ACTION_COUNTS.csv",
        "UNKNOWN_RESOURCE_HINTS.csv",
        "RESOURCE_METADATA_SUMMARY.json",
        "RESOURCE_METADATA_SUMMARY.txt",
    }
    manifest_rows: List[Dict[str, Any]] = []
    skipped_rows: List[Dict[str, Any]] = []

    def rel_to_out(path: Path) -> str:
        try:
            return str(path.relative_to(out_dir))
        except Exception:
            return str(path)

    def add_file(zf: zipfile.ZipFile, path: Path, arcname: str, reason: str, max_bytes: Optional[int] = None) -> None:
        try:
            size = path.stat().st_size
            if max_bytes is not None and size > max_bytes:
                skipped_rows.append({
                    "path": rel_to_out(path),
                    "size_bytes": size,
                    "reason": f"skipped_size_limit_{max_bytes}",
                })
                return
            _zip_report_file_sanitized(zf, path, arcname, out_dir)
            manifest_rows.append({"arcname": arcname, "source_rel": rel_to_out(path), "size_bytes": size, "reason": reason, "sanitized_in_bundle": _is_text_report_file(path)})
        except Exception as exc:
            skipped_rows.append({"path": sanitize_report_text_for_diagnostic_bundle(str(path), out_dir=out_dir), "size_bytes": "", "reason": f"add_failed: {exc}"})

    def csv_bytes(rows: List[Dict[str, Any]]) -> bytes:
        sio = io.StringIO()
        if rows:
            fieldnames: List[str] = []
            for row in rows:
                for k in row.keys():
                    if k not in fieldnames:
                        fieldnames.append(k)
            writer = csv.DictWriter(sio, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        else:
            sio.write("note\nno rows\n")
        return sanitize_report_text_for_diagnostic_bundle(sio.getvalue(), out_dir=out_dir).encode("utf-8")

    with zipfile.ZipFile(report_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        readme = [
            f"{TOOL_NAME} {TOOL_VERSION} - Diagnostic Report Bundle",
            f"Created: {_dt.datetime.now().isoformat(timespec='seconds')}",
            "",
            "Purpose:",
            "This zip contains the reports needed to review route-handler extraction results.",
            "It does NOT include extracted game payload folders, raw outer payloads, or full APKF resource dumps.",
            "v2.12 privacy: text reports in this bundle are sanitized so local Windows/container paths are replaced with safe placeholders.",
            "",
            "Included:",
            "- 00_MASTER_REPORTS summary/index/error reports",
            "- CSV_TARGET_* reports when a pack-list CSV/text file was used",
            "- Each pack's 00_REPORTS route summary, probe JSON, outer rows, APKF summaries, parse errors, and handler actions",
            "- v2.9 resource browse indexes, resource pack matrix, TEX/MESH/MAT/ANIM/CVX/UNKNOWN top-pack reports, and slim diagnostic bundle",
            "- DIAGNOSTIC_REPORT_MANIFEST.csv listing exactly what was included",
            "- DIAGNOSTIC_REPORT_SKIPPED_FILES.csv listing anything skipped by size/safety rules",
            "",
            "How to use:",
            "Share this zip for support diagnostics instead of the full extraction output when troubleshooting handlers.",
            "If support asks for one specific pack later, review that pack's generated diagnostics from your local output folder.",
        ]
        zf.writestr("README_DIAGNOSTIC_REPORT.txt", "\n".join(readme) + "\n")

        if master.exists():
            for p in sorted(master.iterdir(), key=lambda x: x.name.lower()):
                if p.is_file() and (p.name in master_keep or p.name.startswith("PACKS_BY_ROUTE_")):
                    add_file(zf, p, f"00_MASTER_REPORTS/{p.name}", "master_report")
        else:
            skipped_rows.append({"path": "00_MASTER_REPORTS", "size_bytes": "", "reason": "missing_master_reports_folder"})

        for rep_dir in pack_report_dirs:
            pack_dir = rep_dir.parent
            safe_pack = clean_name(pack_dir.name, "pack")
            for p in sorted(rep_dir.iterdir(), key=lambda x: x.name.lower()):
                if not p.is_file() or p.name not in pack_keep:
                    continue
                # String samples can be useful but get bulky on full-game runs.
                max_bytes = 512 * 1024 if p.name == "STRING_SAMPLES.csv" else None
                add_file(zf, p, f"PER_PACK_REPORTS/{safe_pack}/00_REPORTS/{p.name}", "per_pack_report", max_bytes=max_bytes)

        zf.writestr("SANITIZED_REPORT_PATHS_README.txt", "v2.12 privacy cleanup\n\nText reports inside this diagnostic report bundle are sanitized before zipping.\nLocal absolute Windows paths are replaced with LOCAL_PATH_REDACTED or OUTPUT_ROOT placeholders.\nSandbox/container absolute paths are also redacted.\nThe local output folder on your PC still keeps full paths for Open Output/Open Reports usability.\n")
        zf.writestr("SANITIZED_REPORT_PATHS.json", json.dumps({"enabled": True, "version_added": "v2.12", "bundle_only": True, "placeholders": ["OUTPUT_ROOT", "LOCAL_PATH_REDACTED", "SANDBOX_PATH_REDACTED"]}, indent=2))
        zf.writestr("DIAGNOSTIC_REPORT_MANIFEST.csv", csv_bytes(manifest_rows))
        zf.writestr("DIAGNOSTIC_REPORT_SKIPPED_FILES.csv", csv_bytes(skipped_rows))
        summary_obj = {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "master_reports_present": master.exists(),
            "pack_report_folder_count": len(pack_report_dirs),
            "included_file_count": len(manifest_rows),
            "skipped_file_count": len(skipped_rows),
            "zip_name": report_zip.name,
            "note": "Full report bundle only. No extracted payload folders are included. A smaller slim bundle is also created for whole-folder review.",
        }
        zf.writestr("DIAGNOSTIC_REPORT_SUMMARY.json", json.dumps(summary_obj, indent=2))
        zf.writestr("DIAGNOSTIC_REPORT_SUMMARY.txt", "\n".join([f"{k}: {v}" for k, v in summary_obj.items()]) + "\n")

    log(f"Diagnostic report bundle written: {report_zip}")
    return report_zip



def build_diagnostic_report_zip_slim(out_dir: Path, log=print) -> Path:
    """Create a smaller full-folder diagnostic zip.

    v2.9 purpose:
    The full diagnostic report bundle is useful for deep debugging, but whole-folder runs can
    include tens of thousands of report files. The slim bundle keeps the proof-level
    master reports and small per-pack summaries/counts, while excluding large per-pack
    browse indexes/hint CSVs unless they contain errors.
    """
    out_dir = Path(out_dir)
    report_zip = out_dir / SLIM_REPORT_ZIP_NAME
    if report_zip.exists():
        report_zip.unlink()
    log("Slim report zip generation is disabled in this public release build.")
    return report_zip
    master = out_dir / "00_MASTER_REPORTS"
    pack_report_dirs = sorted([p for p in out_dir.glob("*/00_REPORTS") if p.is_dir()], key=lambda p: str(p).lower())

    master_keep_prefixes = ("PACKS_BY_ROUTE_",)
    master_keep = {
        "BATCH_INPUT_MANIFEST.csv",
        "MASTER_EXTRACT_SUMMARY.csv",
        "MASTER_EXTRACT_SUMMARY.json",
        "MASTER_EXTRACT_SUMMARY.txt",
        "MASTER_ERRORS.csv",
        "MASTER_APKF_PARSE_ERRORS.csv",
        "PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv",
        "PER_PACK_REPORT_INDEX.csv",
        "CSV_TARGET_REQUESTS.csv",
        "CSV_TARGET_MATCHES.csv",
        "CSV_TARGET_MISSING.csv",
        "CSV_TARGET_DUPLICATE_MATCHES.csv",
        "CSV_TARGET_SUMMARY.json",
        "CSV_TARGET_SUMMARY.txt",
        "RUN_VERDICT.txt",
        "RUN_VERDICT.json",
        "RUN_VERDICT.csv",
        "MASTER_ROUTE_DASHBOARD.txt",
        "MASTER_ROUTE_DASHBOARD.json",
        "MASTER_ROUTE_COUNTS.csv",
        "MASTER_DETECTION_COUNTS.csv",
        "MASTER_TOP_PACKS_BY_INNER_FILES.csv",
        "MASTER_TOP_PACKS_BY_OUTER_ROWS.csv",
        "MASTER_TOP_PACKS_BY_OUTER_EXPORTS.csv",
        "MASTER_ROUTE_GROUPS_INDEX.csv",
        "MASTER_REPORT_INDEX.html",
        "FULL_FOLDER_PHASE_STATUS.txt",
        "FULL_FOLDER_PHASE_STATUS.json",
        "ROUTE_HANDLER_NEXT_PHASE_PLAN.txt",
        "MASTER_RESOURCE_TYPE_COUNTS.csv",
        "MASTER_RESOURCE_EXTENSION_COUNTS.csv",
        "MASTER_RESOURCE_FAMILY_COUNTS.csv",
        "MASTER_TOP_PACKS_BY_TEX.csv",
        "MASTER_TOP_PACKS_BY_MESH.csv",
        "MASTER_TOP_PACKS_BY_MAT.csv",
        "MASTER_TOP_PACKS_BY_ANIM.csv",
        "MASTER_TOP_PACKS_BY_CVX.csv",
        "MASTER_TOP_PACKS_BY_UNKNOWN.csv",
        "MASTER_RESOURCE_PACK_MATRIX.csv",
        "MASTER_MESH_METADATA_SUMMARY.csv",
        "MASTER_MESH_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_MESH_REVIEW_PRIORITY_COUNTS.csv",
        "MASTER_MAT_METADATA_SUMMARY.csv",
        "MASTER_MAT_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_MAT_ROLE_COUNTS.csv",
        "MASTER_ANIM_METADATA_SUMMARY.csv",
        "MASTER_ANIM_COMPONENT_LAYOUT_COUNTS.csv",
        "MASTER_ANIM_FAMILY_COUNTS.csv",
        "MASTER_ANIM_SWAP_SAFETY_COUNTS.csv",
        "MASTER_RESOURCE_DEPENDENCY_HINTS.csv",
        "MASTER_RESOURCE_DEPENDENCY_ACTION_COUNTS.csv",
        "MASTER_RESOURCE_NAVIGATION_INDEX.csv",
        "MASTER_DEPENDENCY_NAVIGATION_INDEX.csv",
        "MASTER_PACK_BROWSE_INDEX.html",
        "MASTER_BETTER_BROWSE_GUIDE.txt",
        "MASTER_TEX_METADATA_SUMMARY.csv",
        "MASTER_TEX_FORMAT_COUNTS.csv",
        "MASTER_TEX_DIMENSION_COUNTS.csv",
        "MASTER_TEX_MIP_COUNTS.csv",
        "MASTER_TEX_METADATA_CONFIDENCE.csv",
        "MASTER_TOP_PACKS_BY_TEX_METADATA_READY.csv",
        "MASTER_TEX_DDS_EXPORT_STATUS_COUNTS.csv",
        "MASTER_TEX_REVIEW_REASON_COUNTS.csv",
        "MASTER_TEX_REVIEW_TRIAGE.csv",
        "MASTER_TEX_LOW_CONFIDENCE_BY_PACK.csv",
        "MASTER_TEX_REVIEW_ACTION_COUNTS.csv",
        "MASTER_TEX_REVIEW_PRIORITY_COUNTS.csv",
        "MASTER_TEX_REVIEW_GROUP_COUNTS.csv",
        "MASTER_TEX_REVIEW_QUEUE.csv",
        "MASTER_TEX_DDS_EXPORT_CANDIDATES.csv",
        "MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "MASTER_TEX_LAYOUT_CANDIDATES.csv",
        "MASTER_TEX_LAYOUT_STATUS_COUNTS.csv",
        "MASTER_TEX_LAYOUT_LOCK_APPLIED.csv",
        "MASTER_TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "MASTER_BROWSE_OUTPUT_GUIDE.txt",
        "MASTER_EXTRACTION_READINESS.csv",
        "MASTER_PAYLOAD_TEST_CANDIDATES.csv",
        "MASTER_FILETYPE_METADATA_PRIORITY.csv",
        "MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv",
        "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.txt",
        "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.json",
        "MASTER_PACK_EXTRACTION_MODE_RECOMMENDATIONS.csv",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.txt",
        "MASTER_PAYLOAD_EXTRACTION_VALIDATION.json",
        "MASTER_RECOMMENDED_WORKFLOW.txt",
        "MASTER_WORKFLOW_RECOMMENDED.html",
        "MASTER_WORKFLOW_SHORTCUTS.csv",
        "MASTER_OPEN_OUTPUT_SHORTCUTS.csv",
        "MASTER_RELEASE_READINESS_CHECKLIST.csv",
        "MASTER_WORKFLOW_MODES.csv",
        "MASTER_WORKFLOW_STATUS.json",
    }
    pack_keep = {
        "ROUTE_HANDLER_SUMMARY.txt",
        "EXTRACT_RESULT.json",
        "RESOURCE_METADATA_SUMMARY.txt",
        "RESOURCE_METADATA_SUMMARY.json",
        "RESOURCE_TYPE_COUNTS.csv",
        "RESOURCE_EXTENSION_COUNTS.csv",
        "TEX_FORMAT_COUNTS.csv",
        "TEX_DIMENSION_COUNTS.csv",
        "TEX_REVIEW_QUEUE.csv",
        "TEX_DDS_EXPORT_CANDIDATES.csv",
        "TEX_SWIZZLE_REVIEW_QUEUE.csv",
        "TEX_LAYOUT_CANDIDATES.csv",
        "TEX_LAYOUT_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_APPLIED.csv",
        "TEX_LAYOUT_LOCK_STATUS_COUNTS.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.csv",
        "TEX_LAYOUT_LOCK_MAP_LOADED.txt",
        "TEX_LAYOUT_LOCK_MAP_LOADED.json",
        "TEX_DDS_EXPORTS.csv",
        "TEX_REVIEW_REASON_COUNTS.csv",
        "TEX_REVIEW_TRIAGE.csv",
        "TEX_MEDIUM_REVIEW_QUEUE.csv",
        "TEX_REVIEW_ACTION_COUNTS.csv",
        "TEX_REVIEW_PRIORITY_COUNTS.csv",
        "TEX_REVIEW_GROUP_COUNTS.csv",
        "APKF_PARSE_ERRORS.csv",
        "APKF_MARKER_FILTERED.csv",
    }

    manifest_rows: List[Dict[str, Any]] = []
    skipped_rows: List[Dict[str, Any]] = []

    def rel_to_out(path: Path) -> str:
        try:
            return str(path.relative_to(out_dir))
        except Exception:
            return str(path)

    def add_file(zf: zipfile.ZipFile, path: Path, arcname: str, reason: str) -> None:
        try:
            size = path.stat().st_size
            _zip_report_file_sanitized(zf, path, arcname, out_dir)
            manifest_rows.append({"arcname": arcname, "source_rel": rel_to_out(path), "size_bytes": size, "reason": reason, "sanitized_in_bundle": _is_text_report_file(path)})
        except Exception as exc:
            skipped_rows.append({"path": sanitize_report_text_for_diagnostic_bundle(str(path), out_dir=out_dir), "size_bytes": "", "reason": f"add_failed: {exc}"})

    def csv_bytes(rows: List[Dict[str, Any]]) -> bytes:
        sio = io.StringIO()
        if rows:
            fieldnames: List[str] = []
            for row in rows:
                for k in row.keys():
                    if k not in fieldnames:
                        fieldnames.append(k)
            writer = csv.DictWriter(sio, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        else:
            sio.write("note\nno rows\n")
        return sanitize_report_text_for_diagnostic_bundle(sio.getvalue(), out_dir=out_dir).encode("utf-8")

    with zipfile.ZipFile(report_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        readme = [
            f"{TOOL_NAME} {TOOL_VERSION} - SLIM Diagnostic Report Bundle",
            f"Created: {_dt.datetime.now().isoformat(timespec='seconds')}",
            "",
            "Purpose:",
            "This is the smaller full-folder review zip. Send this first for PASS/FAIL and dashboard checks.",
            "Use the full SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE.zip only when deep per-pack debugging is needed.",
            "v2.12 privacy: text reports in this bundle are sanitized so local Windows/container paths are replaced with safe placeholders.",
            "",
            "Included:",
            "- 00_MASTER_REPORTS proof/dashboard/resource matrix files",
            "- Small per-pack summaries/counts/errors",
            "",
            "Excluded:",
            "- Full per-pack RESOURCE_BROWSE_INDEX.csv/html and large hint CSVs",
            "- Extracted payload folders/raw game dumps",
        ]
        zf.writestr("README_DIAGNOSTIC_REPORT_SLIM.txt", "\n".join(readme) + "\n")

        if master.exists():
            for p in sorted(master.iterdir(), key=lambda x: x.name.lower()):
                if p.is_file() and (p.name in master_keep or any(p.name.startswith(px) for px in master_keep_prefixes)):
                    add_file(zf, p, f"00_MASTER_REPORTS/{p.name}", "master_report_slim")
        else:
            skipped_rows.append({"path": "00_MASTER_REPORTS", "size_bytes": "", "reason": "missing_master_reports_folder"})

        for rep_dir in pack_report_dirs:
            safe_pack = clean_name(rep_dir.parent.name, "pack")
            for p in sorted(rep_dir.iterdir(), key=lambda x: x.name.lower()):
                if not p.is_file() or p.name not in pack_keep:
                    continue
                add_file(zf, p, f"PER_PACK_REPORTS/{safe_pack}/00_REPORTS/{p.name}", "per_pack_slim_report")

        zf.writestr("SANITIZED_REPORT_PATHS_README.txt", "v2.12 privacy cleanup\n\nText reports inside this diagnostic report bundle are sanitized before zipping.\nLocal absolute Windows paths are replaced with LOCAL_PATH_REDACTED or OUTPUT_ROOT placeholders.\nSandbox/container absolute paths are also redacted.\nThe local output folder on your PC still keeps full paths for Open Output/Open Reports usability.\n")
        zf.writestr("SANITIZED_REPORT_PATHS.json", json.dumps({"enabled": True, "version_added": "v2.12", "bundle_only": True, "placeholders": ["OUTPUT_ROOT", "LOCAL_PATH_REDACTED", "SANDBOX_PATH_REDACTED"]}, indent=2))
        zf.writestr("DIAGNOSTIC_REPORT_MANIFEST.csv", csv_bytes(manifest_rows))
        zf.writestr("DIAGNOSTIC_REPORT_SKIPPED_FILES.csv", csv_bytes(skipped_rows))
        summary_obj = {
            "tool": TOOL_NAME,
            "version": TOOL_VERSION,
            "created": _dt.datetime.now().isoformat(timespec="seconds"),
            "master_reports_present": master.exists(),
            "pack_report_folder_count": len(pack_report_dirs),
            "included_file_count": len(manifest_rows),
            "skipped_file_count": len(skipped_rows),
            "zip_name": report_zip.name,
            "note": "Slim report bundle only. Send the full bundle if support asks for deep per-pack browse indexes.",
        }
        zf.writestr("DIAGNOSTIC_REPORT_SUMMARY.json", json.dumps(summary_obj, indent=2))
        zf.writestr("DIAGNOSTIC_REPORT_SUMMARY.txt", "\n".join([f"{k}: {v}" for k, v in summary_obj.items()]) + "\n")

    log(f"SLIM Diagnostic report bundle written: {report_zip}")
    return report_zip


def _safe_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except Exception:
        return 0




def write_payload_extraction_validation_reports(reports: Path, master_rows: List[Dict[str, Any]], write_payloads: bool) -> Dict[str, Any]:
    """v2.11: validate that payload-mode extraction produced useful folders/files.

    This does not decode resources. It checks the practical extraction outputs:
    real-extension APKF exports for normal packs, outer-payload preservation for
    stub/voice/compact routes, and expected report/index files.
    """
    rows: List[Dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for row in master_rows:
        pack = str(row.get("pack") or "")
        route = str(row.get("route") or "")
        out_dir = Path(str(row.get("out_dir") or ""))
        reports_dir = Path(str(row.get("reports_dir") or ""))
        real_root = out_dir / "02_APKF_EXTRACTED_REAL_EXT"
        outer_root = out_dir / "01_OUTER_PAYLOADS"
        compact_root = outer_root / "COMPACT_HEADER_HSAM_REGIONS"
        comp_root = out_dir / "03_APKF_COMPONENTS"
        raw_root = out_dir / "04_RAW_PRESERVED"

        def count_files(root_path: Path) -> int:
            if not root_path.exists():
                return 0
            return sum(1 for p in root_path.rglob("*") if p.is_file())

        real_files = count_files(real_root)
        outer_files = count_files(outer_root)
        compact_files = count_files(compact_root)
        component_files = count_files(comp_root)
        raw_files = count_files(raw_root)
        inner_files = _safe_int(row.get("inner_files"))
        outer_exports = _safe_int(row.get("outer_exports"))
        parse_errors = _safe_int(row.get("parse_error_count"))

        expected: List[str] = []
        issues: List[str] = []
        if not write_payloads:
            expected.append("reports-only run; payload files are not expected")
            status = "REPORTS_ONLY_NOT_PAYLOAD_TEST"
        elif parse_errors:
            issues.append("parse errors present")
            status = "REVIEW_PARSE_ERRORS"
        elif route == "NORMAL_HSAM_TABLE_REAL_TYPE36_APKF":
            expected.append("real-extension inner APKF files")
            if inner_files <= 0:
                issues.append("no inner APKF files reported")
            if real_files <= 0:
                issues.append("no real-extension payload files written")
            status = "PAYLOAD_EXPORT_OK" if not issues else "PAYLOAD_EXPORT_REVIEW"
        elif route == "STUB_APKF_OUTER_HSAM_HEAVY":
            expected.append("outer hsam payload preservation; tiny APKF stub is expected")
            if outer_exports <= 0 or outer_files <= 0:
                issues.append("no outer payload files preserved")
            status = "OUTER_PRESERVE_OK" if not issues else "OUTER_PRESERVE_REVIEW"
        elif route == "VOICE_AUDIO_TYPE35_PLUS_TINY_TYPE36_STUB":
            expected.append("type35 voice/audio raw preserve plus tiny type36 stub")
            if outer_exports <= 0 or outer_files <= 0:
                issues.append("no type35/outer payload files preserved")
            status = "TYPE35_PRESERVE_OK" if not issues else "TYPE35_PRESERVE_REVIEW"
        elif route == "COMPACT_HEADER_HSAM_APKF_WRAPPER":
            expected.append("compact-header hsam region preservation")
            if outer_exports <= 0 or outer_files <= 0:
                issues.append("no compact/outer payload files preserved")
            status = "COMPACT_PRESERVE_OK" if not issues else "COMPACT_PRESERVE_REVIEW"
        else:
            expected.append("raw preserve/report review")
            if outer_exports <= 0 and inner_files <= 0:
                issues.append("no payload/inner output reported")
            status = "GENERIC_REVIEW" if issues else "GENERIC_OK"

        status_counts[status] += 1
        rows.append({
            "pack": pack,
            "route": route,
            "validation_status": status,
            "issues": " | ".join(issues),
            "expected_output": " | ".join(expected),
            "inner_files_reported": inner_files,
            "outer_exports_reported": outer_exports,
            "real_ext_payload_file_count": real_files,
            "outer_payload_file_count": outer_files,
            "compact_region_file_count": compact_files,
            "component_file_count": component_files,
            "raw_preserved_file_count": raw_files,
            "resource_browse_index_exists": (reports_dir / "RESOURCE_BROWSE_INDEX.csv").exists(),
            "resource_browse_html_exists": (reports_dir / "RESOURCE_BROWSE_INDEX.html").exists(),
            "reports_dir": str(reports_dir),
            "out_dir": str(out_dir),
        })

    write_csv(reports / "MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv", rows)
    summary = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "payload_export_enabled": write_payloads,
        "packs_checked": len(rows),
        "validation_status_counts": dict(status_counts),
        "review_count": sum(v for k, v in status_counts.items() if k.endswith("REVIEW") or k.startswith("REVIEW")),
        "meaning": "v2.11 validates actual payload output folders/files. It does not decode TEX/MESH/MAT/ANIM yet.",
    }
    write_json(reports / "MASTER_PAYLOAD_EXTRACTION_VALIDATION.json", summary)
    lines = [
        "============================================================",
        f"{TOOL_NAME} {TOOL_VERSION} - PAYLOAD EXTRACTION VALIDATION",
        "============================================================",
        f"Payload export enabled: {write_payloads}",
        f"Packs checked: {len(rows)}",
        "",
        "Validation status counts:",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(status_counts.items())] or ["- None"]
    lines += [
        "",
        "Use this report after scanning is already done. The route/probe phase is locked; this validates extraction-output usefulness.",
        "Main file: MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv",
    ]
    (reports / "MASTER_PAYLOAD_EXTRACTION_VALIDATION.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def write_master_resource_index_reports(reports: Path, master_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """v2.8 aggregate per-pack resource browse reports into master summaries."""
    type_counts: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    top_by_type: Dict[str, List[Dict[str, Any]]] = {"TEX": [], "MESH": [], "MAT": [], "ANIM": [], "CVX": [], "UNKNOWN": []}
    pack_matrix_rows: List[Dict[str, Any]] = []
    tex_format_counts: Counter[str] = Counter()
    tex_dimension_counts: Counter[str] = Counter()
    tex_mip_counts: Counter[str] = Counter()
    tex_confidence_counts: Counter[str] = Counter()
    tex_dds_export_counts: Counter[str] = Counter()
    tex_review_reason_counts: Counter[str] = Counter()
    tex_review_action_counts: Counter[str] = Counter()
    tex_review_priority_counts: Counter[str] = Counter()
    tex_review_group_counts: Counter[str] = Counter()
    tex_summary_rows: List[Dict[str, Any]] = []
    tex_ready_pack_rows: List[Dict[str, Any]] = []
    tex_review_master_rows: List[Dict[str, Any]] = []
    tex_triage_master_rows: List[Dict[str, Any]] = []
    tex_low_by_pack_rows: List[Dict[str, Any]] = []
    tex_dds_candidate_master_rows: List[Dict[str, Any]] = []
    tex_layout_status_counts: Counter[str] = Counter()
    tex_layout_lock_status_counts: Counter[str] = Counter()
    tex_layout_master_rows: List[Dict[str, Any]] = []
    tex_layout_candidate_master_rows: List[Dict[str, Any]] = []
    tex_layout_lock_master_rows: List[Dict[str, Any]] = []
    mesh_summary_rows: List[Dict[str, Any]] = []
    mat_summary_rows: List[Dict[str, Any]] = []
    anim_summary_rows: List[Dict[str, Any]] = []
    dependency_master_rows: List[Dict[str, Any]] = []
    mesh_layout_counts: Counter[str] = Counter()
    mesh_priority_counts: Counter[str] = Counter()
    mat_layout_counts: Counter[str] = Counter()
    mat_role_counts: Counter[str] = Counter()
    anim_layout_counts: Counter[str] = Counter()
    anim_family_counts: Counter[str] = Counter()
    anim_safety_counts: Counter[str] = Counter()
    dependency_action_counts: Counter[str] = Counter()

    for row in master_rows:
        pack = str(row.get("pack") or "")
        reports_dir = Path(str(row.get("reports_dir") or ""))
        type_csv = reports_dir / "RESOURCE_TYPE_COUNTS.csv"
        ext_csv = reports_dir / "RESOURCE_EXTENSION_COUNTS.csv"
        browse_csv = reports_dir / "RESOURCE_BROWSE_INDEX.csv"
        tex_meta_csv = reports_dir / "TEX_METADATA_HINTS.csv"
        tex_review_csv = reports_dir / "TEX_REVIEW_QUEUE.csv"
        tex_triage_csv = reports_dir / "TEX_REVIEW_TRIAGE.csv"
        tex_dds_csv = reports_dir / "TEX_DDS_EXPORT_CANDIDATES.csv"
        tex_layout_csv = reports_dir / "TEX_SWIZZLE_REVIEW_QUEUE.csv"
        tex_layout_candidates_csv = reports_dir / "TEX_LAYOUT_CANDIDATES.csv"
        tex_layout_lock_csv = reports_dir / "TEX_LAYOUT_LOCK_APPLIED.csv"
        mesh_meta_csv = reports_dir / "MESH_METADATA_HINTS.csv"
        mat_meta_csv = reports_dir / "MAT_METADATA_HINTS.csv"
        anim_meta_csv = reports_dir / "ANIM_METADATA_HINTS.csv"
        dependency_csv = reports_dir / "RESOURCE_DEPENDENCY_HINTS.csv"
        pack_type_counts: Dict[str, int] = {}
        pack_family_counts: Counter[str] = Counter()
        for tr in _read_csv_dicts(type_csv):
            ftype = str(tr.get("file_type") or "UNKNOWN")
            cnt = _safe_int(tr.get("resource_count") or tr.get("count"))
            type_counts[ftype] += cnt
            pack_type_counts[ftype] = pack_type_counts.get(ftype, 0) + cnt
        for er in _read_csv_dicts(ext_csv):
            ext = str(er.get("extension") or "UNKNOWN")
            cnt = _safe_int(er.get("resource_count") or er.get("count"))
            ext_counts[ext] += cnt
        for br in _read_csv_dicts(browse_csv):
            fam = str(br.get("resource_family") or "unknown")
            family_counts[fam] += 1
            pack_family_counts[fam] += 1
        tex_rows = _read_csv_dicts(tex_meta_csv)
        tex_exact = 0
        tex_high_or_medium = 0
        for tr in tex_rows:
            fmt = str(tr.get("tex_format_guess") or "UNKNOWN")
            wh = f"{tr.get('tex_width_guess') or '?'}x{tr.get('tex_height_guess') or '?'}"
            mip = str(tr.get("tex_mip_count_guess") or "UNKNOWN")
            conf = str(tr.get("tex_metadata_confidence") or "NONE")
            tex_format_counts[fmt] += 1
            tex_dimension_counts[wh] += 1
            tex_mip_counts[mip] += 1
            tex_confidence_counts[conf] += 1
            tex_dds_export_counts[str(tr.get("tex_dds_export_status") or "NOT_EXPORTED")] += 1
            tex_layout_status_counts[str(tr.get("tex_layout_review_status") or "UNKNOWN")] += 1
            tex_layout_lock_status_counts[str(tr.get("tex_layout_lock_status") or "UNKNOWN")] += 1
            tex_review_reason_counts[str(tr.get("tex_review_reason") or "UNKNOWN")] += 1
            tex_review_action_counts[str(tr.get("tex_review_action") or "UNKNOWN")] += 1
            tex_review_priority_counts[str(tr.get("tex_review_priority") or "UNKNOWN")] += 1
            tex_review_group_counts[str(tr.get("tex_review_group") or "UNKNOWN")] += 1
            if conf == "HIGH_EXACT_PAYLOAD_SIZE_MATCH":
                tex_exact += 1
            if conf in {"HIGH_EXACT_PAYLOAD_SIZE_MATCH", "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH"}:
                tex_high_or_medium += 1
        for rr in _read_csv_dicts(tex_review_csv):
            rr = dict(rr)
            rr["pack"] = pack
            rr["route"] = row.get("route")
            tex_review_master_rows.append(rr)
        triage_rows_for_pack = []
        for trr in _read_csv_dicts(tex_triage_csv):
            trr = dict(trr)
            trr["pack"] = pack
            trr["route"] = row.get("route")
            tex_triage_master_rows.append(trr)
            triage_rows_for_pack.append(trr)
        if triage_rows_for_pack:
            low_count = sum(1 for _r in triage_rows_for_pack if str(_r.get("tex_metadata_confidence") or "") == "LOW_BEST_EFFORT_GUESS")
            medium_count = sum(1 for _r in triage_rows_for_pack if str(_r.get("tex_metadata_confidence") or "") == "MEDIUM_NEAR_PAYLOAD_SIZE_MATCH")
            high_priority = sum(1 for _r in triage_rows_for_pack if str(_r.get("tex_review_priority") or "") == "HIGH")
            tex_low_by_pack_rows.append({
                "pack": pack,
                "route": row.get("route"),
                "tex_triage_count": len(triage_rows_for_pack),
                "tex_low_best_effort_count": low_count,
                "tex_medium_near_match_count": medium_count,
                "tex_high_priority_review_count": high_priority,
                "reports_dir": row.get("reports_dir"),
            })
        for dr in _read_csv_dicts(tex_dds_csv):
            dr = dict(dr)
            dr["pack"] = pack
            dr["route"] = row.get("route")
            tex_dds_candidate_master_rows.append(dr)
        for lr in _read_csv_dicts(tex_layout_csv):
            lr = dict(lr)
            lr["pack"] = pack
            lr["route"] = row.get("route")
            tex_layout_master_rows.append(lr)
        for lcr in _read_csv_dicts(tex_layout_candidates_csv):
            lcr = dict(lcr)
            lcr["pack"] = pack
            lcr["route"] = row.get("route")
            tex_layout_candidate_master_rows.append(lcr)
        for llr in _read_csv_dicts(tex_layout_lock_csv):
            llr = dict(llr)
            llr["pack"] = pack
            llr["route"] = row.get("route")
            tex_layout_lock_master_rows.append(llr)

        mesh_rows = _read_csv_dicts(mesh_meta_csv)
        if mesh_rows:
            pcount = 0
            for mr in mesh_rows:
                mr = dict(mr); mr["pack"] = pack; mr["route"] = row.get("route")
                mesh_layout_counts[str(mr.get("component_layout") or "UNKNOWN")] += 1
                mesh_priority_counts[str(mr.get("mesh_review_priority") or "UNKNOWN")] += 1
                pcount += 1
            mesh_summary_rows.append({"pack": pack, "route": row.get("route"), "mesh_count": len(mesh_rows), "large_or_character_mesh_count": sum(1 for _r in mesh_rows if str(_r.get("mesh_review_priority") or "").startswith("HIGH")), "reports_dir": row.get("reports_dir")})
        mat_rows = _read_csv_dicts(mat_meta_csv)
        if mat_rows:
            for mr in mat_rows:
                mat_layout_counts[str(mr.get("component_layout") or "UNKNOWN")] += 1
                mat_role_counts[str(mr.get("mat_role_hint") or "UNKNOWN")] += 1
            mat_summary_rows.append({"pack": pack, "route": row.get("route"), "mat_count": len(mat_rows), "texture_channel_hint_count": sum(1 for _r in mat_rows if str(_r.get("mat_texture_channel_name_hints") or "")), "reports_dir": row.get("reports_dir")})
        anim_rows = _read_csv_dicts(anim_meta_csv)
        if anim_rows:
            for ar in anim_rows:
                anim_layout_counts[str(ar.get("component_layout") or "UNKNOWN")] += 1
                anim_family_counts[str(ar.get("anim_family_hint") or "UNKNOWN")] += 1
                anim_safety_counts[str(ar.get("anim_swap_safety_hint") or "UNKNOWN")] += 1
            anim_summary_rows.append({"pack": pack, "route": row.get("route"), "anim_count": len(anim_rows), "high_risk_traversal_count": sum(1 for _r in anim_rows if str(_r.get("anim_swap_safety_hint") or "") == "HIGH_RISK_TRAVERSAL_REVIEW"), "lower_risk_idle_or_hit_count": sum(1 for _r in anim_rows if str(_r.get("anim_swap_safety_hint") or "") in {"LOWER_RISK_IDLE_STANCE", "LOWER_RISK_HIT_REACTION"}), "reports_dir": row.get("reports_dir")})
        for dep in _read_csv_dicts(dependency_csv):
            dep = dict(dep); dep["pack"] = pack; dep["route"] = row.get("route")
            dependency_master_rows.append(dep)
            dependency_action_counts[str(dep.get("dependency_action") or "UNKNOWN")] += 1

        if tex_rows:
            tex_summary_rows.append({
                "pack": pack,
                "route": row.get("route"),
                "tex_count": len(tex_rows),
                "tex_high_exact_payload_match": tex_exact,
                "tex_high_or_medium_confidence": tex_high_or_medium,
                "tex_needs_review": max(0, len(tex_rows) - tex_high_or_medium),
                "tex_dds_export_ok": sum(1 for _tr in tex_rows if str(_tr.get("tex_dds_export_status") or "") == "DDS_EXPORT_OK"),
                "reports_dir": row.get("reports_dir"),
            })
            tex_ready_pack_rows.append({
                "pack": pack,
                "route": row.get("route"),
                "tex_count": len(tex_rows),
                "tex_high_or_medium_confidence": tex_high_or_medium,
                "ready_ratio": round(tex_high_or_medium / max(1, len(tex_rows)), 4),
                "reports_dir": row.get("reports_dir"),
            })
        total_resources = sum(pack_type_counts.values())
        pack_matrix_rows.append({
            "pack": pack,
            "route": row.get("route"),
            "detection": row.get("detection"),
            "outer_rows": row.get("outer_row_count"),
            "outer_exports": row.get("outer_exports"),
            "inner_files": row.get("inner_files"),
            "total_resources_counted": total_resources,
            "TEX": pack_type_counts.get("TEX", 0),
            "MESH": pack_type_counts.get("MESH", 0),
            "MAT": pack_type_counts.get("MAT", 0),
            "ANIM": pack_type_counts.get("ANIM", 0),
            "CVX": pack_type_counts.get("CVX", 0),
            "SKEL": pack_type_counts.get("SKEL", 0),
            "ASKL": pack_type_counts.get("ASKL", 0),
            "SANM": pack_type_counts.get("SANM", 0),
            "MORH": pack_type_counts.get("MORH", 0),
            "UNKNOWN_FAMILY": pack_family_counts.get("unknown", 0),
            "reports_dir": row.get("reports_dir"),
        })
        for ftype in top_by_type:
            count = pack_type_counts.get(ftype, 0)
            if ftype == "UNKNOWN":
                count = pack_family_counts.get("unknown", 0)
            top_by_type[ftype].append({
                "pack": pack,
                "route": row.get("route"),
                "detection": row.get("detection"),
                "resource_type": ftype,
                "resource_count": count,
                "inner_files": row.get("inner_files"),
                "reports_dir": row.get("reports_dir"),
            })

    write_csv(reports / "MASTER_RESOURCE_TYPE_COUNTS.csv", [{"file_type": k, "resource_count": v} for k, v in sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_RESOURCE_EXTENSION_COUNTS.csv", [{"extension": k, "resource_count": v} for k, v in sorted(ext_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_RESOURCE_FAMILY_COUNTS.csv", [{"resource_family": k, "resource_count": v} for k, v in sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_RESOURCE_PACK_MATRIX.csv", sorted(pack_matrix_rows, key=lambda r: _safe_int(r.get("total_resources_counted")), reverse=True))
    write_csv(reports / "MASTER_MESH_METADATA_SUMMARY.csv", sorted(mesh_summary_rows, key=lambda r: _safe_int(r.get("mesh_count")), reverse=True))
    write_csv(reports / "MASTER_MESH_COMPONENT_LAYOUT_COUNTS.csv", [{"component_layout": k, "mesh_count": v} for k, v in sorted(mesh_layout_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_MESH_REVIEW_PRIORITY_COUNTS.csv", [{"mesh_review_priority": k, "mesh_count": v} for k, v in sorted(mesh_priority_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_MAT_METADATA_SUMMARY.csv", sorted(mat_summary_rows, key=lambda r: _safe_int(r.get("mat_count")), reverse=True))
    write_csv(reports / "MASTER_MAT_COMPONENT_LAYOUT_COUNTS.csv", [{"component_layout": k, "mat_count": v} for k, v in sorted(mat_layout_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_MAT_ROLE_COUNTS.csv", [{"mat_role_hint": k, "mat_count": v} for k, v in sorted(mat_role_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_ANIM_METADATA_SUMMARY.csv", sorted(anim_summary_rows, key=lambda r: _safe_int(r.get("anim_count")), reverse=True))
    write_csv(reports / "MASTER_ANIM_COMPONENT_LAYOUT_COUNTS.csv", [{"component_layout": k, "anim_count": v} for k, v in sorted(anim_layout_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_ANIM_FAMILY_COUNTS.csv", [{"anim_family_hint": k, "anim_count": v} for k, v in sorted(anim_family_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_ANIM_SWAP_SAFETY_COUNTS.csv", [{"anim_swap_safety_hint": k, "anim_count": v} for k, v in sorted(anim_safety_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_RESOURCE_DEPENDENCY_HINTS.csv", sorted(dependency_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("file_type") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_RESOURCE_DEPENDENCY_ACTION_COUNTS.csv", [{"dependency_action": k, "resource_count": v} for k, v in sorted(dependency_action_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_METADATA_SUMMARY.csv", sorted(tex_summary_rows, key=lambda r: _safe_int(r.get("tex_count")), reverse=True))
    write_csv(reports / "MASTER_TEX_FORMAT_COUNTS.csv", [{"tex_format_guess": k, "texture_count": v} for k, v in sorted(tex_format_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_DIMENSION_COUNTS.csv", [{"dimension_guess": k, "texture_count": v} for k, v in sorted(tex_dimension_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_MIP_COUNTS.csv", [{"mip_count_guess": k, "texture_count": v} for k, v in sorted(tex_mip_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_METADATA_CONFIDENCE.csv", [{"tex_metadata_confidence": k, "texture_count": v} for k, v in sorted(tex_confidence_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_DDS_EXPORT_STATUS_COUNTS.csv", [{"tex_dds_export_status": k, "texture_count": v} for k, v in sorted(tex_dds_export_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_REVIEW_REASON_COUNTS.csv", [{"tex_review_reason": k, "texture_count": v} for k, v in sorted(tex_review_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_REVIEW_ACTION_COUNTS.csv", [{"tex_review_action": k, "texture_count": v} for k, v in sorted(tex_review_action_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_REVIEW_PRIORITY_COUNTS.csv", [{"tex_review_priority": k, "texture_count": v} for k, v in sorted(tex_review_priority_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_REVIEW_GROUP_COUNTS.csv", [{"tex_review_group": k, "texture_count": v} for k, v in sorted(tex_review_group_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_REVIEW_QUEUE.csv", sorted(tex_review_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TEX_REVIEW_TRIAGE.csv", sorted(tex_triage_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("tex_review_priority") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TEX_LOW_CONFIDENCE_BY_PACK.csv", sorted(tex_low_by_pack_rows, key=lambda r: (_safe_int(r.get("tex_high_priority_review_count")), _safe_int(r.get("tex_low_best_effort_count")), _safe_int(r.get("tex_triage_count"))), reverse=True))
    write_csv(reports / "MASTER_TEX_DDS_EXPORT_CANDIDATES.csv", sorted(tex_dds_candidate_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TEX_LAYOUT_STATUS_COUNTS.csv", [{"tex_layout_review_status": k, "texture_count": v} for k, v in sorted(tex_layout_status_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_LAYOUT_LOCK_STATUS_COUNTS.csv", [{"tex_layout_lock_status": k, "texture_count": v} for k, v in sorted(tex_layout_lock_status_counts.items(), key=lambda kv: (-kv[1], kv[0]))])
    write_csv(reports / "MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv", sorted(tex_layout_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("tex_layout_review_status") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TEX_LAYOUT_CANDIDATES.csv", sorted(tex_layout_candidate_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TEX_LAYOUT_LOCK_APPLIED.csv", sorted(tex_layout_lock_master_rows, key=lambda r: (str(r.get("pack") or ""), str(r.get("filename") or ""))))
    write_csv(reports / "MASTER_TOP_PACKS_BY_TEX_METADATA_READY.csv", sorted(tex_ready_pack_rows, key=lambda r: (_safe_int(r.get("tex_high_or_medium_confidence")), _safe_int(r.get("tex_count"))), reverse=True)[:200])
    for ftype, rows in top_by_type.items():
        top = sorted(rows, key=lambda r: _safe_int(r.get("resource_count")), reverse=True)[:100]
        write_csv(reports / f"MASTER_TOP_PACKS_BY_{ftype}.csv", top)

    # v2.22 master navigation/index files for easier browsing across pack outputs.
    nav_index_rows: List[Dict[str, Any]] = []
    dep_nav_rows: List[Dict[str, Any]] = []
    for row in master_rows:
        pack = str(row.get("pack") or "")
        reports_dir = str(row.get("reports_dir") or "")
        if not reports_dir:
            continue
        nav_index_rows.append({
            "pack": pack,
            "route": row.get("route"),
            "resource_dashboard": str(Path(reports_dir) / "PACK_BROWSE_DASHBOARD.html"),
            "resource_browse_index": str(Path(reports_dir) / "RESOURCE_BROWSE_INDEX.csv"),
            "dependency_navigation": str(Path(reports_dir) / "RESOURCE_DEPENDENCY_NAVIGATION.html"),
            "tex_metadata": str(Path(reports_dir) / "TEX_METADATA_HINTS.csv"),
            "mesh_metadata": str(Path(reports_dir) / "MESH_METADATA_HINTS.csv"),
            "mat_metadata": str(Path(reports_dir) / "MAT_METADATA_HINTS.csv"),
            "anim_metadata": str(Path(reports_dir) / "ANIM_METADATA_HINTS.csv"),
            "reports_dir": reports_dir,
        })
    for d in dependency_master_rows:
        dep_nav_rows.append({
            "pack": d.get("pack"),
            "route": d.get("route"),
            "file_type": d.get("file_type"),
            "filename_hash": d.get("filename_hash"),
            "filename": d.get("filename"),
            "possible_dependencies": d.get("possible_dependencies"),
            "dependency_action": d.get("dependency_action"),
            "component_layout": d.get("component_layout"),
            "real_ext_file": d.get("real_ext_file"),
        })
    write_csv(reports / "MASTER_RESOURCE_NAVIGATION_INDEX.csv", nav_index_rows)
    write_csv(reports / "MASTER_DEPENDENCY_NAVIGATION_INDEX.csv", dep_nav_rows)
    css = "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#111;color:#eee}a{color:#8cc8ff}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #444;padding:6px;font-size:12px}th{background:#222}.note{color:#bbb}.card{display:inline-block;background:#181b22;border:1px solid #333;border-radius:10px;padding:10px;margin:6px}.num{font-size:20px;font-weight:bold}"
    html = ["<!doctype html><html><head><meta charset='utf-8'><title>SM3 Master Pack Browse Index</title>", f"<style>{css}</style></head><body>", f"<h1>SM3 Master Pack Browse Index - {TOOL_VERSION}</h1>", "<p class='note'>Open a per-pack dashboard for easier TEX/MESH/MAT/ANIM/resource dependency browsing. Paths in diagnostic bundles are sanitized placeholders.</p>"]
    html.append("<h2>Resource Totals</h2>")
    for key in ['TEX','MESH','MAT','ANIM','CVX','SKEL','ASKL','SANM','MORH','UNKNOWN']:
        html.append(f"<div class='card'><div>{_html.escape(key)}</div><div class='num'>{type_counts.get(key,0)}</div></div>")
    html.append("<h2>Key Master Reports</h2><ul>")
    for name in ["MASTER_RESOURCE_PACK_MATRIX.csv", "MASTER_RESOURCE_NAVIGATION_INDEX.csv", "MASTER_DEPENDENCY_NAVIGATION_INDEX.csv", "MASTER_RESOURCE_DEPENDENCY_HINTS.csv", "MASTER_TEX_METADATA_SUMMARY.csv", "MASTER_MESH_METADATA_SUMMARY.csv", "MASTER_MAT_METADATA_SUMMARY.csv", "MASTER_ANIM_METADATA_SUMMARY.csv", "MASTER_TEX_REVIEW_TRIAGE.csv", "MASTER_TEX_LAYOUT_CANDIDATES.csv"]:
        if (reports / name).exists():
            html.append(f"<li><a href='{_html.escape(name)}'>{_html.escape(name)}</a></li>")
    html.append("</ul><h2>Pack Dashboards</h2><table><tr><th>Pack</th><th>Route</th><th>Dashboard</th><th>Browse CSV</th><th>Dependency Nav</th></tr>")
    for r in nav_index_rows[:1500]:
        dash = Path(str(r.get('resource_dashboard') or '')).name
        browse = Path(str(r.get('resource_browse_index') or '')).name
        dephtml = Path(str(r.get('dependency_navigation') or '')).name
        # Links are relative only within copied report folders; CSV still gives full/sanitized paths for scripts.
        html.append(f"<tr><td>{_html.escape(str(r.get('pack') or ''))}</td><td>{_html.escape(str(r.get('route') or ''))}</td><td>{_html.escape(str(r.get('resource_dashboard') or ''))}</td><td>{_html.escape(str(r.get('resource_browse_index') or ''))}</td><td>{_html.escape(str(r.get('dependency_navigation') or ''))}</td></tr>")
    html.append("</table></body></html>")
    (reports / "MASTER_PACK_BROWSE_INDEX.html").write_text("\n".join(html) + "\n", encoding="utf-8")
    (reports / "MASTER_BETTER_BROWSE_GUIDE.txt").write_text("\n".join([
        "============================================================",
        "SM3 v2.22 BETTER BROWSE / DEPENDENCY NAVIGATION GUIDE",
        "============================================================",
        "New per-pack HTML files:",
        "- PACK_BROWSE_DASHBOARD.html: friendly summary with quick links and TEX/MESH/MAT/ANIM tables.",
        "- RESOURCE_DEPENDENCY_NAVIGATION.html: starter dependency hint navigation for MESH/MAT/ANIM/TEX/SKEL/ASKL.",
        "New per-pack CSV files:",
        "- RESOURCE_NAVIGATION_INDEX.csv",
        "- RESOURCE_DEPENDENCY_NAVIGATION.csv",
        "- RESOURCE_FAMILY_COUNTS.csv",
        "New master files:",
        "- MASTER_PACK_BROWSE_INDEX.html",
        "- MASTER_RESOURCE_NAVIGATION_INDEX.csv",
        "- MASTER_DEPENDENCY_NAVIGATION_INDEX.csv",
        "These are navigation/report improvements only. They do not decode MESH/MAT/ANIM further and do not modify original PCPACKs.",
    ]) + "\n", encoding="utf-8")

    guide = [
        "============================================================",
        "SM3 v2.22 BROWSE / METADATA / DEPENDENCY INDEX GUIDE",
        "============================================================",
        "New per-pack 00_REPORTS files:",
        "- RESOURCE_BROWSE_INDEX.csv/html: compact resource browser index with type, hash, name, role hint, component layout, and exported file path.",
        "- RESOURCE_TYPE_COUNTS.csv and RESOURCE_EXTENSION_COUNTS.csv: quick per-pack counts.",
        "- TEX_RESOURCE_HINTS.csv, MESH_RESOURCE_HINTS.csv, MAT_RESOURCE_HINTS.csv, ANIM_RESOURCE_HINTS.csv: type-focused review lists.",
        "- TEX_METADATA_HINTS.csv: v2.15 conservative width/height/mip/format guesses based on TEX component0 + component1 payload size.",
        "- MESH_METADATA_HINTS.csv, MAT_METADATA_HINTS.csv, ANIM_METADATA_HINTS.csv: v2.21 starter metadata reports for model/material/animation research.",
        "- RESOURCE_DEPENDENCY_HINTS.csv: v2.21 conservative dependency hints such as MESH->MAT/SKEL, MAT->TEX, ANIM->ASKL/SKEL.",
        "- TEX_FORMAT_COUNTS.csv / TEX_DIMENSION_COUNTS.csv: quick per-pack texture metadata buckets.",
        "- UNKNOWN_RESOURCE_HINTS.csv: resource types not in the current extension map.",
        "- RESOURCE_METADATA_SUMMARY.txt/json: per-pack summary.",
        "",
        "New master files:",
        "- MASTER_RESOURCE_TYPE_COUNTS.csv",
        "- MASTER_RESOURCE_EXTENSION_COUNTS.csv",
        "- MASTER_RESOURCE_FAMILY_COUNTS.csv",
        "- MASTER_TOP_PACKS_BY_TEX/MESH/MAT/ANIM/CVX/UNKNOWN.csv",
        "- MASTER_RESOURCE_PACK_MATRIX.csv = one row per pack with TEX/MESH/MAT/ANIM/CVX counts",
        "- MASTER_MESH/MAT/ANIM_* reports = v2.21 starter metadata summaries and component layout buckets.",
        "- MASTER_RESOURCE_DEPENDENCY_HINTS.csv = v2.21 starter dependency map for MESH/MAT/ANIM/TEX/SKEL/ASKL linking.",
        "- MASTER_TEX_METADATA_SUMMARY.csv, MASTER_TEX_* counts, MASTER_TEX_REVIEW_QUEUE.csv, MASTER_TEX_REVIEW_TRIAGE.csv, and MASTER_TEX_DDS_EXPORT_CANDIDATES.csv = TEX metadata/DDS export/review overview",
        "- MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv and MASTER_TEX_LAYOUT_CANDIDATES.csv = v2.18 layout/swizzle visual-review queues",
        "- SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE_SLIM.zip = smaller whole-folder review bundle",
        "",
        "Important:",
        "These are conservative metadata hints and browse indexes. TEX metadata is guessed by descriptor/payload-size matching; full TEX decode/export is still a later phase.",
        "Original PCPACK files are never modified.",
    ]
    (reports / "MASTER_BROWSE_OUTPUT_GUIDE.txt").write_text("\n".join(guide) + "\n", encoding="utf-8")
    return {
        "master_resource_type_counts": dict(type_counts),
        "master_resource_extension_counts": dict(ext_counts),
        "master_resource_family_counts": dict(family_counts),
        "master_tex_format_counts": dict(tex_format_counts),
        "master_tex_metadata_confidence_counts": dict(tex_confidence_counts),
        "master_tex_dds_export_status_counts": dict(tex_dds_export_counts),
        "master_tex_review_reason_counts": dict(tex_review_reason_counts),
        "master_tex_review_action_counts": dict(tex_review_action_counts),
        "master_tex_review_priority_counts": dict(tex_review_priority_counts),
        "master_tex_review_group_counts": dict(tex_review_group_counts),
        "master_tex_review_queue_count": len(tex_review_master_rows),
        "master_tex_review_triage_count": len(tex_triage_master_rows),
        "master_tex_dds_export_candidate_count": len(tex_dds_candidate_master_rows),
        "master_tex_layout_review_queue_count": len(tex_layout_master_rows),
        "master_tex_layout_candidate_count": len(tex_layout_candidate_master_rows),
    }


def write_master_extraction_readiness_reports(reports: Path, master_rows: List[Dict[str, Any]], output_layout: str, write_payloads: bool) -> Dict[str, Any]:
    """v2.10: turn the proven route-handler reports into an extraction readiness plan.

    This is still a report/planning layer. It does not change extraction bytes.
    It answers: which packs are ready for payload export, which routes should be
    preserved raw/stub-style, and which file families should be tackled next for
    real TEX/MESH/MAT/ANIM/CVX metadata parsing.
    """
    ensure_dir(reports)
    matrix_rows = _read_csv_dicts(reports / "MASTER_RESOURCE_PACK_MATRIX.csv")
    matrix_by_pack: Dict[str, Dict[str, str]] = {str(r.get("pack") or ""): r for r in matrix_rows}

    readiness_rows: List[Dict[str, Any]] = []
    mode_rows: List[Dict[str, Any]] = []
    priority_rows: List[Dict[str, Any]] = []
    cvx_unknown_rows: List[Dict[str, Any]] = []

    route_mode_counts: Counter[str] = Counter()
    readiness_counts: Counter[str] = Counter()

    for row in master_rows:
        pack = str(row.get("pack") or "")
        route = str(row.get("route") or "UNKNOWN")
        parse_errors = _safe_int(row.get("parse_error_count"))
        inner_files = _safe_int(row.get("inner_files"))
        outer_exports = _safe_int(row.get("outer_exports"))
        outer_rows = _safe_int(row.get("outer_row_count"))
        mat = matrix_by_pack.get(pack, {})
        tex = _safe_int(mat.get("TEX"))
        mesh = _safe_int(mat.get("MESH"))
        material = _safe_int(mat.get("MAT"))
        anim = _safe_int(mat.get("ANIM"))
        cvx = _safe_int(mat.get("CVX"))
        skel = _safe_int(mat.get("SKEL"))
        askl = _safe_int(mat.get("ASKL"))
        sanm = _safe_int(mat.get("SANM"))
        morh = _safe_int(mat.get("MORH"))
        unknown = _safe_int(mat.get("UNKNOWN_FAMILY"))
        total_resources = _safe_int(mat.get("total_resources_counted")) or inner_files

        if parse_errors:
            readiness = "REVIEW_PARSE_ERRORS_BEFORE_EXTRACTION"
        elif route == "NORMAL_HSAM_TABLE_REAL_TYPE36_APKF":
            readiness = "READY_FOR_SMART_BROWSE_PAYLOAD_EXPORT"
        elif route == "STUB_APKF_OUTER_HSAM_HEAVY":
            readiness = "READY_FOR_OUTER_PAYLOAD_PRESERVE_ONLY"
        elif route == "VOICE_AUDIO_TYPE35_PLUS_TINY_TYPE36_STUB":
            readiness = "READY_FOR_TYPE35_VOICE_RAW_PRESERVE_ONLY"
        elif route == "COMPACT_HEADER_HSAM_APKF_WRAPPER":
            readiness = "READY_FOR_COMPACT_HEADER_REGION_PRESERVE"
        else:
            readiness = "READY_BUT_ROUTE_REVIEW_RECOMMENDED"

        if route == "NORMAL_HSAM_TABLE_REAL_TYPE36_APKF":
            recommended_mode = "smart_browse payload export"
            first_test = "export real-extension inner APKF files and review RESOURCE_BROWSE_INDEX"
        elif route == "STUB_APKF_OUTER_HSAM_HEAVY":
            recommended_mode = "outer payload preserve"
            first_test = "review 01_OUTER_PAYLOADS hsam regions; tiny type36 APKF is expected"
        elif route == "VOICE_AUDIO_TYPE35_PLUS_TINY_TYPE36_STUB":
            recommended_mode = "type35 raw preserve"
            first_test = "preserve type35 payload; do not expect normal inner APKF resources"
        elif route == "COMPACT_HEADER_HSAM_APKF_WRAPPER":
            recommended_mode = "compact header preserve"
            first_test = "review COMPACT_HEADER_HSAM_REGIONS and tiny APKF stub"
        else:
            recommended_mode = "raw preserve + report review"
            first_test = "inspect route summary before payload use"

        metadata_score = tex * 5 + mesh * 4 + material * 3 + anim * 4 + cvx * 2 + unknown
        payload_score = total_resources * 2 + outer_exports + outer_rows
        notes = []
        if tex:
            notes.append("TEX metadata target")
        if mesh or skel or askl:
            notes.append("model-chain metadata target")
        if anim or sanm or morh:
            notes.append("animation metadata target")
        if cvx:
            notes.append("CVX review target")
        if unknown:
            notes.append("unknown-family review target")
        if not notes:
            notes.append("route/output validation target")

        out_row = {
            "pack": pack,
            "route": route,
            "readiness": readiness,
            "recommended_extraction_mode": recommended_mode,
            "first_test_action": first_test,
            "parse_error_count": parse_errors,
            "outer_rows": outer_rows,
            "outer_exports": outer_exports,
            "inner_files": inner_files,
            "total_resources_counted": total_resources,
            "TEX": tex,
            "MESH": mesh,
            "MAT": material,
            "ANIM": anim,
            "CVX": cvx,
            "SKEL": skel,
            "ASKL": askl,
            "SANM": sanm,
            "MORH": morh,
            "UNKNOWN_FAMILY": unknown,
            "metadata_priority_score": metadata_score,
            "payload_test_score": payload_score,
            "notes": "; ".join(notes),
            "reports_dir": row.get("reports_dir"),
        }
        readiness_rows.append(out_row)
        mode_rows.append({k: out_row[k] for k in ["pack", "route", "readiness", "recommended_extraction_mode", "first_test_action", "outer_exports", "inner_files", "reports_dir"]})
        if metadata_score > 0:
            priority_rows.append(out_row)
        if cvx or unknown:
            cvx_unknown_rows.append(out_row)
        readiness_counts[readiness] += 1
        route_mode_counts[recommended_mode] += 1

    readiness_sorted = sorted(readiness_rows, key=lambda r: (_safe_int(r.get("parse_error_count")), -_safe_int(r.get("payload_test_score")), str(r.get("pack") or "")))
    payload_candidates = sorted([r for r in readiness_rows if _safe_int(r.get("parse_error_count")) == 0], key=lambda r: _safe_int(r.get("payload_test_score")), reverse=True)[:200]
    priority_sorted = sorted(priority_rows, key=lambda r: _safe_int(r.get("metadata_priority_score")), reverse=True)[:300]
    cvx_unknown_sorted = sorted(cvx_unknown_rows, key=lambda r: (_safe_int(r.get("CVX")) + _safe_int(r.get("UNKNOWN_FAMILY"))), reverse=True)[:300]

    write_csv(reports / "MASTER_EXTRACTION_READINESS.csv", readiness_sorted)
    write_csv(reports / "MASTER_PAYLOAD_TEST_CANDIDATES.csv", payload_candidates)
    write_csv(reports / "MASTER_FILETYPE_METADATA_PRIORITY.csv", priority_sorted)
    write_csv(reports / "MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv", cvx_unknown_sorted)
    write_csv(reports / "MASTER_PACK_EXTRACTION_MODE_RECOMMENDATIONS.csv", sorted(mode_rows, key=lambda r: (str(r.get("recommended_extraction_mode")), str(r.get("pack")))))

    status = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "processed_pack_count": len(master_rows),
        "output_layout": output_layout,
        "payload_export_enabled_this_run": write_payloads,
        "readiness_counts": dict(readiness_counts),
        "recommended_mode_counts": dict(route_mode_counts),
        "payload_candidate_count_written": len(payload_candidates),
        "metadata_priority_count_written": len(priority_sorted),
        "cvx_unknown_review_count_written": len(cvx_unknown_sorted),
        "meaning": "v2.10 reports plan the next extraction work after route handling passed. They do not alter extraction bytes.",
    }
    write_json(reports / "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.json", status)

    lines = [
        "============================================================",
        f"{TOOL_NAME} {TOOL_VERSION} - EXTRACTION READINESS PLAN",
        "============================================================",
        f"Processed packs: {len(master_rows)}",
        f"Output layout: {output_layout}",
        f"Payload export enabled in this run: {write_payloads}",
        "",
        "Readiness counts:",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(readiness_counts.items())] or ["- None"]
    lines += ["", "Recommended extraction modes:"]
    lines += [f"- {k}: {v}" for k, v in sorted(route_mode_counts.items())] or ["- None"]
    lines += [
        "",
        "New v2.10 master reports:",
        "- MASTER_EXTRACTION_READINESS.csv = one row per pack with the recommended extraction route/mode.",
        "- MASTER_PAYLOAD_TEST_CANDIDATES.csv = highest-value packs to test with payload export before a full extraction dump.",
        "- MASTER_FILETYPE_METADATA_PRIORITY.csv = top packs for TEX/MESH/MAT/ANIM metadata parser work.",
        "- MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv = CVX/unknown-family packs to review after common file types.",
        "- MASTER_PACK_EXTRACTION_MODE_RECOMMENDATIONS.csv = simplified pack -> recommended mode table.",
        "",
        "Recommended next practical test:",
        "Run payload export on the highest-value candidates first, not the entire 1,096-pack folder.",
        "Suggested first payload test set: CH_SPIDERMAN, CH_BLACKSUIT, GAME, MEGACITY, STORY_KINGPIN_1_COURTHOUSE, A01, C01, CITY_PEDFEMALE, VOICE_CZ01_EN.",
        "",
        "Original PCPACK files are never modified.",
    ]
    (reports / "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return status


def write_master_workflow_polish_reports(reports: Path, master_rows: List[Dict[str, Any]], run_verdict: Dict[str, Any], output_layout: str, write_payloads: bool) -> Dict[str, Any]:
    """v2.24 beta extractor flow: make the proven extractor easier to use daily.

    These reports do not affect extraction bytes. They summarize the recommended
    workflows and the most useful output buttons/paths for release-style use.
    """
    ensure_dir(reports)
    processed = len(master_rows)
    route_counts = Counter(str(r.get("route") or "UNKNOWN") for r in master_rows)
    mode_rows = [
        {"mode": "Release Mode", "audience": "normal daily use", "recommended_actions": "Full Folder Reports-Only, Payload Test Preset, Open Master Dashboard, Open Pack Browse Index, Create Slim Diagnostic Bundle", "avoid_by_default": "research_full, layout-lab-all, giant full-game payload dumps"},
        {"mode": "Advanced Mode", "audience": "advanced parser review", "recommended_actions": "TEX Layout/Swizzle Lab, Layout Lock Map, full diagnostic bundle, per-pack dependency navigation, component_only/research_full on selected packs", "avoid_by_default": "applying layout guesses globally without visual confirmation"},
    ]
    write_csv(reports / "MASTER_WORKFLOW_MODES.csv", mode_rows)

    shortcut_rows = [
        {"button_or_file": "FULL FOLDER REPORTS-ONLY PRESET", "when_to_use": "First check of a full SM3 packs folder", "expected_output": "RUN_VERDICT PASS, route/dashboard reports, no payload dump"},
        {"button_or_file": "PAYLOAD EXTRACTION TEST PRESET", "when_to_use": "Proof that extraction output writes useful files", "expected_output": "MASTER_PAYLOAD_EXTRACTION_VALIDATION PASS for main route families"},
        {"button_or_file": "PAYLOAD TEST + TEX LAYOUT LAB", "when_to_use": "When DDS images look tiled/swizzled and need visual candidates", "expected_output": "06_TEX_LAYOUT_LAB folders with linear/morton/tile candidate DDS files"},
        {"button_or_file": "Layout lock CSV/JSON", "when_to_use": "After visually confirming the best layout for a texture", "expected_output": "TEX_LAYOUT_LOCK_APPLIED rows and locked DDS layout mode"},
        {"button_or_file": "SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE_SLIM.zip", "when_to_use": "Default bundle for diagnostic review", "expected_output": "Small sanitized report zip"},
        {"button_or_file": "SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE.zip", "when_to_use": "Only when deep per-pack HTML/CSV debugging is needed", "expected_output": "Large sanitized report zip with more per-pack files"},
    ]
    write_csv(reports / "MASTER_WORKFLOW_SHORTCUTS.csv", shortcut_rows)

    open_rows = [
        {"open_this": "00_MASTER_REPORTS/RUN_VERDICT.txt", "purpose": "Top-level PASS/FAIL"},
        {"open_this": "00_MASTER_REPORTS/MASTER_REPORT_INDEX.html", "purpose": "Clickable master report index"},
        {"open_this": "00_MASTER_REPORTS/MASTER_PACK_BROWSE_INDEX.html", "purpose": "Open per-pack dashboards"},
        {"open_this": "00_MASTER_REPORTS/MASTER_ROUTE_DASHBOARD.txt", "purpose": "Route counts and biggest packs"},
        {"open_this": "00_MASTER_REPORTS/MASTER_BETTER_BROWSE_GUIDE.txt", "purpose": "Guide to browse/dependency outputs"},
        {"open_this": "<PACK>/PACK_BROWSE_DASHBOARD.html", "purpose": "One-pack browse dashboard"},
        {"open_this": "<PACK>/05_TEX_DDS_EXPORT/", "purpose": "High-confidence DDS exports"},
        {"open_this": "<PACK>/06_TEX_LAYOUT_LAB/", "purpose": "Visual swizzle/layout candidates"},
    ]
    write_csv(reports / "MASTER_OPEN_OUTPUT_SHORTCUTS.csv", open_rows)

    release_check_rows = [
        {"check": "run_verdict_pass", "status": run_verdict.get("verdict"), "ready_if": "PASS"},
        {"check": "processed_packs", "status": processed, "ready_if": ">= 1"},
        {"check": "hard_errors", "status": run_verdict.get("hard_error_count"), "ready_if": "0"},
        {"check": "apkf_parse_warnings_errors", "status": run_verdict.get("apkf_parse_error_count"), "ready_if": "0"},
        {"check": "payload_export_enabled", "status": write_payloads, "ready_if": "True for payload proof, False for reports-only proof"},
        {"check": "output_layout", "status": output_layout, "ready_if": "smart_browse for daily use"},
    ]
    write_csv(reports / "MASTER_RELEASE_READINESS_CHECKLIST.csv", release_check_rows)

    lines = [
        "============================================================",
        f"{TOOL_NAME} {TOOL_VERSION} - RECOMMENDED WORKFLOW",
        "============================================================",
        "This v2.23 update is workflow polish only. Extraction bytes are unchanged.",
        "",
        "Recommended daily workflow:",
        "1. Full Folder Reports-Only Preset - proves routes without dumping payloads.",
        "2. Payload Extraction Test Preset - proves real output on the safe proof set.",
        "3. Open Master Dashboard / Pack Browse Index - review high-level results first.",
        "4. Use TEX Layout/Swizzle Lab only when images look tiled/swizzled.",
        "5. Save/import a Layout Lock Map only after visual confirmation.",
        "6. Use the slim diagnostic bundle first; use the full bundle only for deep debugging.",
        "",
        "Release Mode mindset:",
        "- Prefer smart_browse.",
        "- Prefer reports-only for full-folder checks.",
        "- Avoid layout-lab-all unless you really need it.",
        "- Avoid full-game payload dumps until selected packs are proven.",
        "",
        "Advanced Mode mindset:",
        "- Use layout lab, lock maps, component_only, and full diagnostic bundle for focused packs.",
        "- Do not auto-apply swizzle/layout globally.",
        "- Original PCPACKs are never modified.",
        "",
        f"Current run verdict: {run_verdict.get('verdict')}",
        f"Processed packs: {processed}",
        "",
        "Key files:",
        "- MASTER_WORKFLOW_SHORTCUTS.csv",
        "- MASTER_OPEN_OUTPUT_SHORTCUTS.csv",
        "- MASTER_RELEASE_READINESS_CHECKLIST.csv",
        "- MASTER_WORKFLOW_RECOMMENDED.html",
    ]
    (reports / "MASTER_RECOMMENDED_WORKFLOW.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_json(reports / "MASTER_WORKFLOW_STATUS.json", {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "verdict": run_verdict.get("verdict"),
        "processed_packs": processed,
        "route_counts": dict(route_counts),
        "output_layout": output_layout,
        "write_payloads": write_payloads,
        "release_mode_default": True,
        "research_mode_available": True,
        "extraction_bytes_changed_in_v2_23": False,
    })

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>SM3 Route Handler Recommended Workflow</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#101216;color:#f5f7fa} a{color:#7fc7ff} .card{background:#191d23;border:1px solid #333;padding:14px;margin:12px 0;border-radius:10px} li{margin:6px 0} code{background:#222;padding:2px 5px;border-radius:4px}</style>",
        "</head><body>",
        f"<h1>SM3 Route Handler {TOOL_VERSION}</h1>",
        f"<p>Verdict: <b>{_html.escape(str(run_verdict.get('verdict')))}</b> | Processed packs: {processed}</p>",
        "<div class='card'><h2>Recommended Workflow</h2><ol>",
        "<li>Run <b>Full Folder Reports-Only</b> first.</li>",
        "<li>Run <b>Payload Extraction Test Preset</b> for output proof.</li>",
        "<li>Open <a href='MASTER_REPORT_INDEX.html'>MASTER_REPORT_INDEX.html</a> and <a href='MASTER_PACK_BROWSE_INDEX.html'>MASTER_PACK_BROWSE_INDEX.html</a>.</li>",
        "<li>Use TEX Layout/Swizzle Lab only for bad-looking DDS exports.</li>",
        "<li>Import a layout lock map after visual confirmation.</li>",
        "</ol></div>",
        "<div class='card'><h2>Useful Files</h2><ul>",
        "<li><a href='RUN_VERDICT.txt'>RUN_VERDICT.txt</a></li>",
        "<li><a href='MASTER_ROUTE_DASHBOARD.txt'>MASTER_ROUTE_DASHBOARD.txt</a></li>",
        "<li><a href='MASTER_WORKFLOW_SHORTCUTS.csv'>MASTER_WORKFLOW_SHORTCUTS.csv</a></li>",
        "<li><a href='MASTER_OPEN_OUTPUT_SHORTCUTS.csv'>MASTER_OPEN_OUTPUT_SHORTCUTS.csv</a></li>",
        "<li><a href='MASTER_RELEASE_READINESS_CHECKLIST.csv'>MASTER_RELEASE_READINESS_CHECKLIST.csv</a></li>",
        "</ul></div>",
        "</body></html>",
    ]
    (reports / "MASTER_WORKFLOW_RECOMMENDED.html").write_text("\n".join(html) + "\n", encoding="utf-8")

    return {"workflow_reports_written": True, "processed_packs": processed, "release_mode_default": True}

def write_master_dashboard_reports(reports: Path, master_rows: List[Dict[str, Any]], route_counts: Dict[str, int], detection_counts: Dict[str, int], run_verdict: Dict[str, Any], csv_target_report: Optional[Dict[str, Any]], output_layout: str, write_payloads: bool, started: str, finished: str) -> Dict[str, Any]:
    """Write full-folder-friendly dashboard/index reports.

    v2.7 purpose:
    When a whole SM3 pack folder passes, the user should not have to dig through
    thousands of per-pack reports to understand what happened. These reports give
    a route histogram, top large packs, route-group index, and next-phase plan.
    """
    ensure_dir(reports)
    total_outer_rows = sum(_safe_int(r.get("outer_row_count")) for r in master_rows)
    total_outer_exports = sum(_safe_int(r.get("outer_exports")) for r in master_rows)
    total_inner_files = sum(_safe_int(r.get("inner_files")) for r in master_rows)
    processed = len(master_rows)
    master_resource_status = write_master_resource_index_reports(reports, master_rows)

    route_count_rows = []
    for route, count in sorted(route_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = (count / processed * 100.0) if processed else 0.0
        route_count_rows.append({"route": route, "pack_count": count, "percent_of_processed": f"{pct:.2f}"})
    write_csv(reports / "MASTER_ROUTE_COUNTS.csv", route_count_rows)

    detection_count_rows = []
    for det, count in sorted(detection_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        pct = (count / processed * 100.0) if processed else 0.0
        detection_count_rows.append({"detection": det, "pack_count": count, "percent_of_processed": f"{pct:.2f}"})
    write_csv(reports / "MASTER_DETECTION_COUNTS.csv", detection_count_rows)

    def top_rows(metric: str, limit: int = 50) -> List[Dict[str, Any]]:
        rows = sorted(master_rows, key=lambda r: _safe_int(r.get(metric)), reverse=True)[:limit]
        out: List[Dict[str, Any]] = []
        for i, r in enumerate(rows, 1):
            out.append({
                "rank": i,
                "pack": r.get("pack"),
                "route": r.get("route"),
                "detection": r.get("detection"),
                metric: r.get(metric),
                "outer_row_count": r.get("outer_row_count"),
                "outer_exports": r.get("outer_exports"),
                "inner_files": r.get("inner_files"),
                "parse_error_count": r.get("parse_error_count"),
                "reports_dir": r.get("reports_dir"),
            })
        return out

    write_csv(reports / "MASTER_TOP_PACKS_BY_INNER_FILES.csv", top_rows("inner_files"))
    write_csv(reports / "MASTER_TOP_PACKS_BY_OUTER_ROWS.csv", top_rows("outer_row_count"))
    write_csv(reports / "MASTER_TOP_PACKS_BY_OUTER_EXPORTS.csv", top_rows("outer_exports"))

    route_index_rows: List[Dict[str, Any]] = []
    for route in sorted(route_counts.keys()):
        route_rows = [r for r in master_rows if str(r.get("route") or "UNKNOWN") == route]
        file_name = f"PACKS_BY_ROUTE_{clean_name(route, 'route')}.csv"
        out_rows = []
        for r in sorted(route_rows, key=lambda x: str(x.get("pack") or "").lower()):
            out_rows.append({
                "pack": r.get("pack"),
                "source_input": r.get("source_input"),
                "route": r.get("route"),
                "detection": r.get("detection"),
                "outer_row_count": r.get("outer_row_count"),
                "outer_exports": r.get("outer_exports"),
                "inner_files": r.get("inner_files"),
                "parse_error_count": r.get("parse_error_count"),
                "reports_dir": r.get("reports_dir"),
            })
        write_csv(reports / file_name, out_rows)
        route_index_rows.append({"route": route, "pack_count": len(route_rows), "csv_file": file_name})
    write_csv(reports / "MASTER_ROUTE_GROUPS_INDEX.csv", route_index_rows)

    csv_summary = None
    if csv_target_report is not None:
        csv_summary = {k: v for k, v in csv_target_report.items() if k not in {"request_rows", "match_rows", "missing_rows", "duplicate_rows"}}

    phase_status = {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "verdict": run_verdict.get("verdict"),
        "processed_packs": processed,
        "route_counts": route_counts,
        "detection_counts": detection_counts,
        "total_outer_rows": total_outer_rows,
        "total_outer_exports": total_outer_exports,
        "total_inner_apkf_files": total_inner_files,
        "csv_target_list_used": csv_target_report is not None,
        "csv_target_summary": csv_summary,
        "output_layout": output_layout,
        "write_payloads": write_payloads,
        "meaning": "Route-handler folder test is done when verdict is PASS, all requested SM3 packs are processed/matched, and parse warnings/errors are zero.",
        "next_phase": "Use v2.8 browse indexes to improve extraction usability, then add true TEX/MESH/MAT/ANIM binary metadata parsers.",
        "resource_index_status": master_resource_status,
    }
    write_json(reports / "FULL_FOLDER_PHASE_STATUS.json", phase_status)

    dashboard_lines = [
        "============================================================",
        f"{TOOL_NAME} {TOOL_VERSION} - MASTER ROUTE DASHBOARD",
        "============================================================",
        f"Started: {started}",
        f"Finished: {finished}",
        f"RUN_VERDICT: {run_verdict.get('verdict')}",
        f"Processed packs: {processed}",
        f"Total outer rows: {total_outer_rows}",
        f"Total outer payload exports reported: {total_outer_exports}",
        f"Total inner APKF files reported: {total_inner_files}",
        f"Output layout: {output_layout}",
        f"Payload export enabled: {write_payloads}",
        "",
        "Route counts:",
    ]
    dashboard_lines += [f"- {r['route']}: {r['pack_count']} ({r['percent_of_processed']}%)" for r in route_count_rows] or ["- None"]
    dashboard_lines += ["", "Detection counts:"]
    dashboard_lines += [f"- {r['detection']}: {r['pack_count']} ({r['percent_of_processed']}%)" for r in detection_count_rows] or ["- None"]
    dashboard_lines += ["", "Top packs by inner APKF files:"]
    for r in top_rows("inner_files", limit=12):
        dashboard_lines.append(f"- {r.get('pack')}: inner_files={r.get('inner_files')} route={r.get('route')}")
    dashboard_lines += ["", "Top packs by outer rows:"]
    for r in top_rows("outer_row_count", limit=12):
        dashboard_lines.append(f"- {r.get('pack')}: outer_rows={r.get('outer_row_count')} route={r.get('route')}")
    dashboard_lines += [
        "",
        "Generated v2.7/v2.8 dashboard files:",
        "- MASTER_ROUTE_COUNTS.csv",
        "- MASTER_DETECTION_COUNTS.csv",
        "- MASTER_TOP_PACKS_BY_INNER_FILES.csv",
        "- MASTER_TOP_PACKS_BY_OUTER_ROWS.csv",
        "- MASTER_TOP_PACKS_BY_OUTER_EXPORTS.csv",
        "- MASTER_ROUTE_GROUPS_INDEX.csv plus PACKS_BY_ROUTE_*.csv",
        "- MASTER_REPORT_INDEX.html",
        "- FULL_FOLDER_PHASE_STATUS.txt/json",
        "- ROUTE_HANDLER_NEXT_PHASE_PLAN.txt",
        "- MASTER_RESOURCE_TYPE_COUNTS.csv / MASTER_RESOURCE_EXTENSION_COUNTS.csv",
        "- MASTER_TOP_PACKS_BY_TEX/MESH/MAT/ANIM/CVX/UNKNOWN.csv",
        "- MASTER_RESOURCE_PACK_MATRIX.csv = one row per pack with TEX/MESH/MAT/ANIM/CVX counts",
        "- MASTER_MESH/MAT/ANIM_* reports = v2.21 starter metadata summaries and component layout buckets.",
        "- MASTER_RESOURCE_DEPENDENCY_HINTS.csv = v2.21 starter dependency map for MESH/MAT/ANIM/TEX/SKEL/ASKL linking.",
        "- MASTER_TEX_METADATA_SUMMARY.csv, MASTER_TEX_* counts, MASTER_TEX_REVIEW_QUEUE.csv, MASTER_TEX_REVIEW_TRIAGE.csv, and MASTER_TEX_DDS_EXPORT_CANDIDATES.csv = TEX metadata/DDS export/review overview",
        "- MASTER_TEX_SWIZZLE_REVIEW_QUEUE.csv and MASTER_TEX_LAYOUT_CANDIDATES.csv = v2.18 layout/swizzle visual-review queues",
        "- SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE_SLIM.zip = smaller whole-folder review bundle",
        "- MASTER_BROWSE_OUTPUT_GUIDE.txt",
    ]
    (reports / "MASTER_ROUTE_DASHBOARD.txt").write_text("\n".join(dashboard_lines) + "\n", encoding="utf-8")
    write_json(reports / "MASTER_ROUTE_DASHBOARD.json", phase_status | {"route_count_rows": route_count_rows, "detection_count_rows": detection_count_rows})

    (reports / "FULL_FOLDER_PHASE_STATUS.txt").write_text("\n".join([
        "============================================================",
        "SM3 ROUTE-HANDLER PHASE STATUS",
        "============================================================",
        f"VERDICT: {run_verdict.get('verdict')}",
        f"Processed packs: {processed}",
        f"Hard errors: {run_verdict.get('hard_error_count')}",
        f"APKF parse warnings/errors: {run_verdict.get('apkf_parse_error_count')}",
        f"Total outer rows: {total_outer_rows}",
        f"Total outer exports reported: {total_outer_exports}",
        f"Total inner APKF files reported: {total_inner_files}",
        "",
        "If this is a full SM3 folder run and verdict is PASS, the route-handler phase is proven at folder level.",
        "Next work should focus on cleaner extraction browsing and deeper file-specific parsers, not more route scanning.",
    ]) + "\n", encoding="utf-8")

    next_plan = [
        "============================================================",
        "SM3 ROUTE HANDLER - NEXT PHASE PLAN",
        "============================================================",
        "Current phase:",
        "- Route scanning is done.",
        "- Route-handler reports-only/full-folder proof is done when RUN_VERDICT is PASS.",
        "",
        "Next phase options:",
        "1. Use v2.8 RESOURCE_BROWSE_INDEX reports to review extracted files by type/name/hash/component layout.",
        "2. File-type-specific parsing: true TEX metadata, model chain grouping, animation counts, material/mesh/texture links.",
        "3. Preview/index layer: HTML index for extracted TEX/MESH/ANIM groups and per-pack navigation.",
        "4. Selective extraction presets: character packs only, city packs only, voice packs only, story packs only.",
        "5. Keep WOS as reference-only. Do not add WOS extraction as the main target.",
        "",
        "Do not modify original PCPACK files. This tool remains extractor/research-only.",
    ]
    (reports / "ROUTE_HANDLER_NEXT_PHASE_PLAN.txt").write_text("\n".join(next_plan) + "\n", encoding="utf-8")

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>SM3 Route Handler Master Report</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#111;color:#eee} a{color:#8cc8ff} table{border-collapse:collapse;margin:12px 0;width:100%} td,th{border:1px solid #444;padding:6px} th{background:#222} .pass{color:#7CFC98;font-weight:bold}.fail{color:#ff7777;font-weight:bold}</style>",
        "</head><body>",
        f"<h1>SM3 Route Handler Master Report - {TOOL_VERSION}</h1>",
        f"<p>Verdict: <span class='{str(run_verdict.get('verdict')).lower()}'>{run_verdict.get('verdict')}</span></p>",
        f"<p>Processed packs: {processed}<br>Total outer rows: {total_outer_rows}<br>Total outer exports: {total_outer_exports}<br>Total inner APKF files: {total_inner_files}</p>",
        "<h2>Route Counts</h2><table><tr><th>Route</th><th>Pack Count</th><th>%</th></tr>",
    ]
    for r in route_count_rows:
        html.append(f"<tr><td>{r['route']}</td><td>{r['pack_count']}</td><td>{r['percent_of_processed']}</td></tr>")
    html += ["</table>", "<h2>Key Files</h2><ul>"]
    for name in ["RUN_VERDICT.txt", "MASTER_ROUTE_DASHBOARD.txt", "MASTER_EXTRACT_SUMMARY.csv", "MASTER_ROUTE_COUNTS.csv", "MASTER_RESOURCE_TYPE_COUNTS.csv", "MASTER_TOP_PACKS_BY_TEX.csv", "MASTER_TOP_PACKS_BY_MESH.csv", "MASTER_TOP_PACKS_BY_ANIM.csv", "MASTER_TOP_PACKS_BY_INNER_FILES.csv", "PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv", "MASTER_BROWSE_OUTPUT_GUIDE.txt", "MASTER_PACK_BROWSE_INDEX.html", "MASTER_BETTER_BROWSE_GUIDE.txt", "MASTER_RESOURCE_NAVIGATION_INDEX.csv", "MASTER_DEPENDENCY_NAVIGATION_INDEX.csv", "ROUTE_HANDLER_NEXT_PHASE_PLAN.txt", "MASTER_RECOMMENDED_WORKFLOW.txt", "MASTER_WORKFLOW_RECOMMENDED.html", "MASTER_OPEN_OUTPUT_SHORTCUTS.csv"]:
        html.append(f"<li><a href='{name}'>{name}</a></li>")
    html += ["</ul>", "</body></html>"]
    (reports / "MASTER_REPORT_INDEX.html").write_text("\n".join(html) + "\n", encoding="utf-8")

    return phase_status

def run_extract(inputs: List[Path], out_dir: Path, recursive: bool = True, include_zips: bool = False, output_layout: str = "smart_browse", max_outer_mb: int = 2048, max_inner_mb: int = 4096, write_payloads: bool = True, log=print, stop_event: Optional[threading.Event] = None, csv_target_report: Optional[Dict[str, Any]] = None) -> Path:
    """Run route handlers on one or many pack files/folders.

    v2.4 batch/report-zip promise:
    - one output folder per pack
    - one 00_REPORTS folder per pack
    - master CSV/JSON/TXT index for all packs
    - separate parse-error and failed-pack reports for quick testing
    - optional CSV target list resolver reports for pack-list driven testing
    """
    ensure_dir(out_dir)
    all_files: List[Path] = []
    for inp in inputs:
        all_files.extend(discover_packs(inp, recursive=recursive, include_zips=include_zips))
    # de-dup while preserving order
    seen: set[str] = set()
    files: List[Path] = []
    for f in all_files:
        key = str(f.resolve()) if f.exists() else str(f)
        if key not in seen:
            files.append(f)
            seen.add(key)

    reports = ensure_dir(out_dir / "00_MASTER_REPORTS")
    master_rows: List[Dict[str, Any]] = []
    error_rows: List[Dict[str, Any]] = []
    parse_error_rows: List[Dict[str, Any]] = []
    per_pack_index_rows: List[Dict[str, Any]] = []
    input_manifest_rows: List[Dict[str, Any]] = []
    started = _dt.datetime.now().isoformat(timespec="seconds")

    for idx, f in enumerate(files, 1):
        input_manifest_rows.append({
            "input_index": idx,
            "path": str(f),
            "name": f.name,
            "suffix": f.suffix,
            "exists": f.exists(),
            "size_bytes": f.stat().st_size if f.exists() and f.is_file() else "",
        })

    log(f"Found {len(files)} input file(s).")
    for i, path in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            log("Stop requested.")
            break
        try:
            log(f"[{i}/{len(files)}] {path.name}")
            results = extract_file(path, out_dir, output_layout, max_outer_mb, max_inner_mb, write_payloads, log=log)
            for r in results:
                pr = r.get("probe", {})
                pack_out = Path(str(r.get("out_dir"))) if r.get("out_dir") else Path("")
                pack_reports = pack_out / "00_REPORTS" if str(pack_out) else ""
                parse_errors = r.get("parse_errors", []) or []
                row = {
                    "batch_index": len(master_rows) + 1,
                    "source_input": str(path),
                    "pack": r.get("pack"),
                    "out_dir": str(pack_out),
                    "reports_dir": str(pack_reports),
                    "route_summary_txt": str(pack_reports / "ROUTE_HANDLER_SUMMARY.txt") if str(pack_out) else "",
                    "pack_probe_json": str(pack_reports / "PACK_PROBE.json") if str(pack_out) else "",
                    "outer_rows_csv": str(pack_reports / "OUTER_ROWS.csv") if str(pack_out) else "",
                    "inner_apkf_files_csv": str(pack_reports / "INNER_APKF_FILES.csv") if str(pack_out) else "",
                    "apkf_parse_errors_csv": str(pack_reports / "APKF_PARSE_ERRORS.csv") if str(pack_out) else "",
                    "detection": pr.get("detection"),
                    "route": pr.get("route"),
                    "outer_row_count": pr.get("outer_row_count"),
                    "outer_exports": r.get("outer_exports"),
                    "inner_files": r.get("inner_files"),
                    "parse_error_count": len(parse_errors),
                    "reasons": pr.get("reasons"),
                }
                master_rows.append(row)
                per_pack_index_rows.append(row)
                for pe in parse_errors:
                    pe_row = {"pack": r.get("pack"), "source_input": str(path), "reports_dir": str(pack_reports)}
                    if isinstance(pe, dict):
                        pe_row.update(pe)
                    else:
                        pe_row["error"] = str(pe)
                    parse_error_rows.append(pe_row)
        except Exception as exc:
            tb = traceback.format_exc()
            log(f"ERROR {path}: {exc}")
            error_rows.append({"path": str(path), "error": str(exc), "traceback": tb})

    stopped = bool(stop_event is not None and stop_event.is_set())
    finished = _dt.datetime.now().isoformat(timespec="seconds")
    route_counts: Dict[str, int] = {}
    detection_counts: Dict[str, int] = {}
    for row in master_rows:
        route = str(row.get("route") or "UNKNOWN")
        route_counts[route] = route_counts.get(route, 0) + 1
        det = str(row.get("detection") or "UNKNOWN")
        detection_counts[det] = detection_counts.get(det, 0) + 1

    run_verdict = build_run_verdict(
        input_count=len(files),
        processed_count=len(master_rows),
        hard_error_count=len(error_rows),
        apkf_parse_error_count=len(parse_error_rows),
        route_counts=route_counts,
        detection_counts=detection_counts,
        csv_target_report=csv_target_report,
        stopped=stopped,
        write_payloads=write_payloads,
        output_layout=output_layout,
    )

    write_csv(reports / "RUN_VERDICT.csv", [{
        "verdict": run_verdict.get("verdict"),
        "pass": run_verdict.get("pass"),
        "needs_review": run_verdict.get("needs_review"),
        "input_count": run_verdict.get("input_count"),
        "processed_count": run_verdict.get("processed_count"),
        "hard_error_count": run_verdict.get("hard_error_count"),
        "apkf_parse_error_count": run_verdict.get("apkf_parse_error_count"),
        "issue_count": len(run_verdict.get("issues") or []),
        "warning_count": len(run_verdict.get("warnings") or []),
    }])
    write_json(reports / "RUN_VERDICT.json", run_verdict)
    verdict_lines = [
        "============================================================",
        f"{TOOL_NAME} {TOOL_VERSION} - RUN VERDICT",
        "============================================================",
        f"VERDICT: {run_verdict.get('verdict')}",
        f"Inputs found: {len(files)}",
        f"Processed pack outputs: {len(master_rows)}",
        f"Hard errors: {len(error_rows)}",
        f"APKF parse warnings/errors: {len(parse_error_rows)}",
        f"CSV target list used: {csv_target_report is not None}",
        f"Output layout: {output_layout}",
        f"Payload export enabled: {write_payloads}",
        "",
        "Issues:",
    ]
    verdict_lines += [f"- {x}" for x in (run_verdict.get("issues") or ["None"])]
    verdict_lines += ["", "Warnings:"]
    verdict_lines += [f"- {x}" for x in (run_verdict.get("warnings") or ["None"])]
    verdict_lines += ["", "Route counts:"]
    verdict_lines += [f"- {k}: {v}" for k, v in sorted(route_counts.items())] or ["- None"]
    verdict_lines += ["", str(run_verdict.get("meaning"))]
    (reports / "RUN_VERDICT.txt").write_text("\n".join(verdict_lines) + "\n", encoding="utf-8")
    log(f"RUN VERDICT: {run_verdict.get('verdict')} | issues={len(run_verdict.get('issues') or [])} warnings={len(run_verdict.get('warnings') or [])}")

    write_csv(reports / "BATCH_INPUT_MANIFEST.csv", input_manifest_rows)
    write_csv(reports / "MASTER_EXTRACT_SUMMARY.csv", master_rows)
    write_csv(reports / "PER_PACK_REPORT_INDEX.csv", per_pack_index_rows)
    write_csv(reports / "MASTER_ERRORS.csv", error_rows)
    write_csv(reports / "MASTER_APKF_PARSE_ERRORS.csv", parse_error_rows)
    write_csv(reports / "PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv", [r for r in master_rows if int(r.get("parse_error_count") or 0) > 0] + error_rows)

    if csv_target_report is not None:
        write_csv(reports / "CSV_TARGET_REQUESTS.csv", csv_target_report.get("request_rows", []))
        write_csv(reports / "CSV_TARGET_MATCHES.csv", csv_target_report.get("match_rows", []))
        write_csv(reports / "CSV_TARGET_MISSING.csv", csv_target_report.get("missing_rows", []))
        write_csv(reports / "CSV_TARGET_DUPLICATE_MATCHES.csv", csv_target_report.get("duplicate_rows", []))
        csv_summary = {k: v for k, v in csv_target_report.items() if k not in {"request_rows", "match_rows", "missing_rows", "duplicate_rows"}}
        write_json(reports / "CSV_TARGET_SUMMARY.json", csv_summary)
        (reports / "CSV_TARGET_SUMMARY.txt").write_text("\n".join([f"{k}: {v}" for k, v in csv_summary.items()]) + "\n", encoding="utf-8")

    dashboard_status = write_master_dashboard_reports(
        reports=reports,
        master_rows=master_rows,
        route_counts=route_counts,
        detection_counts=detection_counts,
        run_verdict=run_verdict,
        csv_target_report=csv_target_report,
        output_layout=output_layout,
        write_payloads=write_payloads,
        started=started,
        finished=finished,
    )
    extraction_readiness_status = write_master_extraction_readiness_reports(
        reports=reports,
        master_rows=master_rows,
        output_layout=output_layout,
        write_payloads=write_payloads,
    )
    payload_validation_status = write_payload_extraction_validation_reports(
        reports=reports,
        master_rows=master_rows,
        write_payloads=write_payloads,
    )
    workflow_polish_status = write_master_workflow_polish_reports(
        reports=reports,
        master_rows=master_rows,
        run_verdict=run_verdict,
        output_layout=output_layout,
        write_payloads=write_payloads,
    )

    write_json(reports / "MASTER_EXTRACT_SUMMARY.json", {
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "started": started,
        "finished": finished,
        "input_count": len(files),
        "processed_count": len(master_rows),
        "hard_error_count": len(error_rows),
        "apkf_parse_error_count": len(parse_error_rows),
        "verdict": run_verdict.get("verdict"),
        "run_verdict": run_verdict,
        "route_counts": route_counts,
        "detection_counts": detection_counts,
        "output_layout": output_layout,
        "write_payloads": write_payloads,
        "csv_target_list_used": csv_target_report is not None,
        "csv_target_summary": ({k: v for k, v in csv_target_report.items() if k not in {"request_rows", "match_rows", "missing_rows", "duplicate_rows"}} if csv_target_report else None),
        "dashboard_status": dashboard_status,
        "extraction_readiness_status": extraction_readiness_status,
        "payload_validation_status": payload_validation_status,
        "workflow_polish_status": workflow_polish_status,
        "workflow_polish_reports_added_in_v2_23": [
            "MASTER_RECOMMENDED_WORKFLOW.txt",
            "MASTER_WORKFLOW_RECOMMENDED.html",
            "MASTER_WORKFLOW_SHORTCUTS.csv",
            "MASTER_OPEN_OUTPUT_SHORTCUTS.csv",
            "MASTER_RELEASE_READINESS_CHECKLIST.csv",
            "MASTER_WORKFLOW_MODES.csv",
            "MASTER_WORKFLOW_STATUS.json",
        ],
        "payload_validation_reports_added_in_v2_11": [
            "MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv",
            "MASTER_PAYLOAD_EXTRACTION_VALIDATION.txt",
            "MASTER_PAYLOAD_EXTRACTION_VALIDATION.json",
        ],
        "tex_metadata_parser_update_v2_13": [
            "TEX_METADATA_HINTS.csv per pack",
            "MASTER_TEX_METADATA_SUMMARY.csv and TEX format/dimension/mip/confidence counts",
            "Conservative TEX width/height/mip/format guesses by component0 descriptor candidates plus component1 payload-size matching",
            "No texture bytes are decoded or modified",
        ],
        "tex_review_triage_update_v2_16": [
            "TEX_REVIEW_TRIAGE.csv per pack",
            "TEX_MEDIUM_REVIEW_QUEUE.csv per pack",
            "TEX_REVIEW_ACTION_COUNTS.csv / TEX_REVIEW_PRIORITY_COUNTS.csv / TEX_REVIEW_GROUP_COUNTS.csv per pack",
            "MASTER_TEX_REVIEW_TRIAGE.csv",
            "MASTER_TEX_LOW_CONFIDENCE_BY_PACK.csv",
            "Review actions and priorities for low/medium TEX metadata rows",
        ],
        "sanitized_diagnostic_bundle_update_v2_12": [
            "Text reports inside diagnostic report bundles are sanitized before zipping",
            "Local absolute paths are replaced with OUTPUT_ROOT/LOCAL_PATH_REDACTED/SANDBOX_PATH_REDACTED placeholders",
            "Local on-disk reports remain unchanged for Open Output/Open Reports usability",
        ],
        "extraction_readiness_reports_added_in_v2_10": [
            "MASTER_EXTRACTION_READINESS.csv",
            "MASTER_PAYLOAD_TEST_CANDIDATES.csv",
            "MASTER_FILETYPE_METADATA_PRIORITY.csv",
            "MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv",
            "MASTER_PACK_EXTRACTION_MODE_RECOMMENDATIONS.csv",
            "MASTER_ROUTE_HANDLER_EXTRACTION_PLAN.txt/json",
        ],
        "browse_index_reports_added_in_v2_8": [
            "Per-pack RESOURCE_BROWSE_INDEX.csv/html",
            "Per-pack RESOURCE_TYPE_COUNTS.csv and RESOURCE_EXTENSION_COUNTS.csv",
            "Per-pack TEX/MESH/MAT/ANIM_RESOURCE_HINTS.csv",
            "Master MASTER_RESOURCE_TYPE_COUNTS.csv and MASTER_RESOURCE_EXTENSION_COUNTS.csv",
            "Master MASTER_TOP_PACKS_BY_TEX/MESH/MAT/ANIM.csv",
            "MASTER_BROWSE_OUTPUT_GUIDE.txt",
        ],
        "dashboard_reports_added_in_v2_7": [
            "MASTER_ROUTE_DASHBOARD.txt/json",
            "MASTER_ROUTE_COUNTS.csv",
            "MASTER_DETECTION_COUNTS.csv",
            "MASTER_TOP_PACKS_BY_INNER_FILES.csv",
            "MASTER_TOP_PACKS_BY_OUTER_ROWS.csv",
            "MASTER_TOP_PACKS_BY_OUTER_EXPORTS.csv",
            "MASTER_ROUTE_GROUPS_INDEX.csv",
            "PACKS_BY_ROUTE_*.csv",
            "MASTER_REPORT_INDEX.html",
            "FULL_FOLDER_PHASE_STATUS.txt/json",
            "ROUTE_HANDLER_NEXT_PHASE_PLAN.txt",
        ],
        "batch_reports_added_in_v2_4": [
            "BATCH_INPUT_MANIFEST.csv",
            "PER_PACK_REPORT_INDEX.csv",
            "MASTER_APKF_PARSE_ERRORS.csv",
            "PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv",
            "SM3_ROUTE_HANDLER_DIAGNOSTIC_REPORT_BUNDLE.zip",
            "CSV_TARGET_REQUESTS.csv",
            "CSV_TARGET_MATCHES.csv",
            "CSV_TARGET_MISSING.csv",
        ],
    })

    lines = [
        f"{TOOL_NAME} {TOOL_VERSION}",
        f"Started: {started}",
        f"Finished: {finished}",
        f"VERDICT: {run_verdict.get('verdict')}",
        f"Inputs found: {len(files)}",
        f"Processed pack outputs: {len(master_rows)}",
        f"Hard errors: {len(error_rows)}",
        f"APKF parse warnings/errors: {len(parse_error_rows)}",
        "",
        "Route counts:",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(route_counts.items())]
    lines += [
        "",
        "Detection counts:",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(detection_counts.items())]
    lines += [
        "",
        "Batch report files:",
        "- RUN_VERDICT.txt/json/csv = top-level PASS/FAIL result for the run",
        "- BATCH_INPUT_MANIFEST.csv = every input pack discovered for this run",
        "- PER_PACK_REPORT_INDEX.csv = one row per pack with links/paths to that pack's 00_REPORTS folder",
        "- MASTER_EXTRACT_SUMMARY.csv/json/txt = full run summary",
        "- MASTER_APKF_PARSE_ERRORS.csv = all APKF parser warnings/errors across the batch",
        "- PACKS_WITH_ERRORS_OR_PARSE_WARNINGS.csv = quick list of packs needing review",
        "- CSV_TARGET_REQUESTS/MATCHES/MISSING.csv = present when running from a submitted pack-list CSV",
        "- MASTER_ROUTE_DASHBOARD.txt/json = v2.7 full-folder overview",
        "- MASTER_ROUTE_COUNTS.csv and PACKS_BY_ROUTE_*.csv = route-group index",
        "- MASTER_TOP_PACKS_BY_*.csv = top large packs by inner files/outer rows/exports",
        "- MASTER_REPORT_INDEX.html = clickable master report index",
        "- MASTER_RESOURCE_TYPE_COUNTS.csv / MASTER_TOP_PACKS_BY_TEX-MESH-MAT-ANIM.csv = v2.8 browse metadata summaries",
        "- MASTER_EXTRACTION_READINESS.csv / MASTER_PAYLOAD_TEST_CANDIDATES.csv = v2.10 extraction readiness plan",
        "- MASTER_PAYLOAD_EXTRACTION_VALIDATION.csv/txt/json = v2.11 actual payload-output validation",
        "- MASTER_RECOMMENDED_WORKFLOW.txt/html and workflow shortcut CSVs = v2.23 daily-use/release-mode guide",
        "- SANITIZED_REPORT_PATHS_README.txt/json inside diagnostic bundles = v2.12 path privacy cleanup",
        "- TEX_METADATA_HINTS.csv and MASTER_TEX_METADATA_SUMMARY.csv = v2.15 TEX metadata parser reports",
        "- MASTER_FILETYPE_METADATA_PRIORITY.csv / MASTER_CVX_UNKNOWN_REVIEW_QUEUE.csv = v2.10 metadata parser priorities",
        "",
        "This is route-handler extraction/probing. Original packs were not modified.",
    ]
    (reports / "MASTER_EXTRACT_SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("Report zip bundles are disabled in this public release build.")
    return out_dir


def clean_release_report_artifacts(out_dir: Path, log=print) -> Dict[str, Any]:
    """Remove report folders/zips for the public release Pack Extractor flow.

    The backend still builds temporary metadata while extracting so the UI can list
    contents, but release users should not get 00_REPORTS, 00_MASTER_REPORTS,
    or diagnostic report bundles in their output folder.
    """
    removed: List[str] = []
    failed: List[Dict[str, str]] = []
    targets: List[Path] = []
    try:
        out_dir = Path(out_dir)
        if not out_dir.exists():
            return {"removed_count": 0, "failed_count": 0, "removed": [], "failed": []}
        for name in ["00_MASTER_REPORTS", "_SM3_LIST_PREVIEW"]:
            p = out_dir / name
            if p.exists():
                targets.append(p)
        targets.extend(sorted(out_dir.glob("*/00_REPORTS"), key=lambda p: str(p).lower()))
        for pattern in ["*REPORT_BUNDLE*.zip", "*REPORT_BUNDLE*.json", "DIAGNOSTIC_REPORT_*.csv", "DIAGNOSTIC_REPORT_*.txt"]:
            targets.extend(sorted(out_dir.glob(pattern), key=lambda p: str(p).lower()))
        seen: set[str] = set()
        unique_targets: List[Path] = []
        for p in targets:
            key = str(p.resolve()) if p.exists() else str(p)
            if key not in seen:
                unique_targets.append(p)
                seen.add(key)
        for p in unique_targets:
            if not p.exists():
                continue
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed.append(str(p))
            except Exception as exc:
                failed.append({"path": str(p), "error": str(exc)})
        if removed:
            log(f"Release cleanup removed {len(removed)} report artifact(s).")
        return {"removed_count": len(removed), "failed_count": len(failed), "removed": removed, "failed": failed}
    except Exception as exc:
        failed.append({"path": str(out_dir), "error": str(exc)})
        return {"removed_count": len(removed), "failed_count": len(failed), "removed": removed, "failed": failed}


# GUI and CLI entry points removed for toolkit service integration.
