#!/usr/bin/env python3
# ============================================================
# SM3 ANIMATION SWAPPER RELEASE v1.14
# CREATED BY TSGAMING264 + LIGHT/DARK MODE + CLEAN PRESETS
#
# Purpose:
#   - PC .PCPACK ANIM list/compare/same-size PC patch
#   - Xbox .XEPACK ANIM list/compare READ-ONLY
#   - Same-pack diff scan
#   - Fixes Xbox 0-ANIM issue with fallback scan + extracted-output support
#
# Xbox patching/conversion is intentionally disabled.
# ============================================================

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import struct
import zipfile
import tempfile
import subprocess
import sys
import webbrowser
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

APP_DISPLAY_NAME = "SM3 ANIMATION SWAPPER"
APP_VERSION = "RELEASE v1.14"
APP_ICON_NAME = "SM3_ANIMATION_SWAPPER.ico"
APP_CREATOR = "Created by TSGAMING264"

# Release-safe Xbox source workflow:
# The tool does NOT ship Xbox/RVB source packs. Users select their own folder
# containing these ZIPs, then choose one as Pack B/source.
XBOX_SOURCE_ZIP_DEFINITIONS = [
    ("Xbox Spider-Man", ["CH_SPIDERMANXE.zip", "CH_SPIDERMAN_XE.zip", "CH_SPIDERMAN.XE.zip"]),
    ("Xbox Black Suit", ["CH_BLACKSUITXE.zip", "CH_BLACKSUIT_XE.zip", "CH_BLACKSUIT.XE.zip"]),
    ("Xbox Peter", ["CH_PETERXE.zip", "CH_PETER_XE.zip", "CH_PETER.XE.zip"]),
    ("Xbox Player Goblin", ["CH_PLAYERGOBLINXE.zip", "CH_PLAYERGOBLIN_XE.zip", "CH_PLAYERGOBLIN.XE.zip"]),
    ("Xbox RVB Red", ["CH_SPIDERMAN_RVBXE.zip", "CH_SPIDERMAN_RVB_XE.zip", "CH_SPIDERMAN_RVB.XE.zip"]),
    ("Xbox RVB Black", ["CH_RVBBLACKXE.zip", "CH_RVBBLACK_XE.zip", "CH_RVBBLACK.XE.zip"]),
]



def apply_app_icon(window) -> None:
    """Apply the bundled SM3 Animation Swapper icon to Tk windows when possible."""
    try:
        icon_path = Path(__file__).with_name(APP_ICON_NAME)
        if icon_path.exists():
            window.iconbitmap(default=str(icon_path))
    except Exception:
        # Icon support can fail on non-Windows systems or unusual Tk builds.
        pass
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple


PC_MAGIC_OFF = 0x30
PC_COUNT_OFF = 0x54
PC_MAGIC = b"hsam"
X360_MAGIC = b"mash"
TABLE_START_CANDIDATES = [0x36C, 0x368, 0x364, 0x370, 0x360, 0x35C, 0x374, 0x350, 0x380]

KNOWN_ANIM_HINTS = [
    "idle", "run", "jump", "double", "swing", "web", "punch", "kick",
    "hit", "block", "wall", "crawl", "fall", "land", "dive", "launch",
    "uppercut", "stomp", "yank", "black", "suit", "rage", "attack",
    "gob", "gobair", "goblin", "airswrd", "sword", "throw", "turbo", "peter", "face", "winded", "bellow"
]



ANIM_NAME_PATTERNS = [
    rb"sm[23rba]?[A-Za-z0-9_]{3,64}",
    rb"gob[A-Za-z0-9_]{3,64}",
    rb"gobair[A-Za-z0-9_]{0,64}",
    rb"peter[A-Za-z0-9_]{3,64}",
    rb"sm3peter[A-Za-z0-9_]{0,64}",
    rb"BS_[A-Za-z0-9_]{3,64}",
    rb"bs[0-9a-z_]{3,64}",
    rb"bsm[0-9a-z_]{3,64}",
]

ANIM_KEYWORDS = [
    "idle", "run", "jump", "jmp", "swing", "swg", "web", "zip", "punch", "kick",
    "atck", "attack", "hit", "block", "rage", "uppercut", "stomp", "dive",
    "fall", "land", "wall", "crawl", "crch", "yank", "launch", "lnch",
    "black", "suit", "beatdown", "pummel",
    "gob", "gobair", "goblin", "airswrd", "sword", "throw", "turbo", "peter", "face", "winded", "bellow"
]


def looks_like_anim_string(name: str) -> bool:
    low = name.lower()
    if len(low) < 5 or len(low) > 80:
        return False
    if not re.match(r"^[a-zA-Z0-9_]+$", name):
        return False
    return any(k in low for k in ANIM_KEYWORDS)


def xbox_raw_anim_string_scan(data: bytes, pack_path: str) -> list:
    """Last-resort read-only fallback: recover animation-like names from raw XEPACK strings.

    This does not recover payload offsets. It is only for list/compare guidance.
    """
    found = {}
    for pat in ANIM_NAME_PATTERNS:
        for m in re.finditer(pat, data, flags=re.I):
            raw = m.group(0)
            try:
                name = raw.decode("ascii", errors="ignore").strip("\x00")
            except Exception:
                continue
            name = name.strip("_")
            if not looks_like_anim_string(name):
                continue
            # Avoid obvious texture/material names.
            low = name.lower()
            if any(bad in low for bad in ["tex", "dif", "nor", "spe", "mat", "mesh", "skeleton"]):
                continue
            if name not in found:
                found[name] = m.start()

    resources = []
    for idx, (name, off) in enumerate(sorted(found.items(), key=lambda kv: kv[0].lower())):
        resources.append(ResourceEntry(
            platform="X360",
            pack_path=pack_path,
            pack_kind="XEPACK_RAW_STRING_SCAN",
            global_index=idx,
            file_type="ANIM",
            local_index=idx,
            filename=name,
            filename_hash=0,
            file_header_offset=off,
            component_sizes=[0],
            component_offsets=[(off, off)],
            source_outer_index=-1,
            source_outer_hash=0,
            source_outer_type_id=0,
            source_outer_offset=0,
            source_apkf_label=f"RAW_STRING_OFFSET_0x{off:X}",
            apkf_endian="string-scan",
        ))
    return resources



def hex32(v: int) -> str:
    return f"0x{v & 0xFFFFFFFF:08X}"


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def u32(data: bytes, off: int, endian: str) -> int:
    if off < 0 or off + 4 > len(data):
        return 0
    return struct.unpack_from(endian + "I", data, off)[0]


def read_cstr(data: bytes, off: int, max_len: int = 512) -> str:
    if off < 0 or off >= len(data):
        return ""
    end = off
    lim = min(len(data), off + max_len)
    while end < lim and data[end] != 0:
        end += 1
    return data[off:end].decode("utf-8", errors="replace")


def clean_name(s: str, fallback: str = "unknown") -> str:
    s = (s or fallback).replace("\x00", "")
    s = re.sub(r"[^A-Za-z0-9_.\-]+", "_", s).strip("._")
    return s[:160] or fallback


def looks_like_anim_path(s: str) -> bool:
    low = s.lower().replace("\\", "/")
    name = Path(low).name
    return (
        "/anim/" in low
        or low.endswith(".anim")
        or ".anim." in low
        or "_anim_" in low
        or name.endswith(".wrap.anim")
        or "anim" in name
    )


def hash_from_text(s: str) -> int:
    m = re.search(r"0x([0-9A-Fa-f]{8})", s)
    if not m:
        return 0
    return int(m.group(1), 16)


def name_from_path_text(s: str) -> str:
    name = Path(s.replace("\\", "/")).name
    stem = name
    for ext in [".combined_raw.bin", ".component1.bin", ".component0.bin", ".wrap.anim", ".anim", ".bin"]:
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
    stem = re.sub(r"^F\d+_", "", stem, flags=re.I)
    stem = re.sub(r"^0x[0-9A-Fa-f]{8}[._-]*", "", stem)
    stem = stem.strip("._- ")
    return stem or name


def match_known_hint(name: str) -> str:
    n = (name or "").lower().replace("_", " ")
    hits = [h for h in KNOWN_ANIM_HINTS if h in n]
    return ", ".join(hits[:4])


def name_tokens(name: str) -> set:
    n = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    return {t for t in n.split() if len(t) >= 3}


def family_score(a_name: str, b_name: str, a_hash: int, b_hash: int) -> int:
    score = 0
    if a_hash and a_hash == b_hash:
        score += 100
    if a_name.lower() == b_name.lower():
        score += 100
    score += 10 * len(name_tokens(a_name) & name_tokens(b_name))
    family_words = ["idle","run","jump","punch","kick","hit","block","web","swing","wall","fall","land","uppercut","stomp","yank","rage","attack"]
    for w in family_words:
        if w in a_name.lower() and w in b_name.lower():
            score += 20
    risky = ["swing", "webzip", "mission", "scene", "boss", "launch", "dive", "fall", "land"]
    for w in risky:
        if w in a_name.lower() or w in b_name.lower():
            score -= 5
    return score


def safety_label(name_a: str, name_b: str) -> str:
    n = (name_a + " " + name_b).lower()
    safer = ["idle", "punch", "kick", "hit", "block", "uppercut", "stomp", "rage", "attack"]
    risky = ["swing", "webzip", "vertweb", "mission", "scene", "boss", "launch", "dive", "fall", "land", "wall"]
    if any(w in n for w in safer) and not any(w in n for w in risky):
        return "SAFER_FIRST_TEST"
    if any(w in n for w in risky):
        return "RISKY_TRAVERSAL_OR_SCENE"
    return "UNKNOWN_TEST_CAREFULLY"


def detailed_anim_safety(name: str) -> str:
    low = (name or "").lower()
    safest = [
        "smratck", "smbatck", "bs_rage", "beatdown", "punch", "kick",
        "uppercut", "stomp", "hit", "block", "idle"
    ]
    medium = [
        "footplant", "divekick", "crch", "crouch", "gndbnc", "jmpland",
        "jmpsprint", "grapple", "sync", "fly", "yank"
    ]
    high = [
        "swing", "swg", "wall", "webzip", "vertweb", "mission", "scene",
        "boss", "vehicle", "veco", "sewer", "door", "metal", "launch",
        "lnch", "dive", "fall", "land"
    ]
    if any(k in low for k in high):
        return "HIGH_RISK"
    if any(k in low for k in safest):
        return "SAFE_FIRST"
    if any(k in low for k in medium):
        return "MEDIUM_RISK"
    return "UNKNOWN"


def platform_name(pack):
    return getattr(pack, "platform", "UNKNOWN")


def pc_xbox_diff_reports(pack_a, pack_b):
    """Return clean PC vs Xbox animation diff report rows."""
    # Identify PC/Xbox sides regardless of A/B order.
    if platform_name(pack_a) == "PC" and platform_name(pack_b) == "X360":
        pc = pack_a
        x360 = pack_b
    elif platform_name(pack_a) == "X360" and platform_name(pack_b) == "PC":
        pc = pack_b
        x360 = pack_a
    else:
        # fallback: left as PC-ish and right as Xbox-ish
        pc = pack_a
        x360 = pack_b

    pc_by_name = {}
    x_by_name = {}
    pc_by_hash = {}
    x_by_hash = {}

    for e in pc.anim_files:
        pc_by_name.setdefault(e.display_name.lower(), []).append(e)
        if e.filename_hash:
            pc_by_hash.setdefault(e.filename_hash, []).append(e)

    for e in x360.anim_files:
        x_by_name.setdefault(e.display_name.lower(), []).append(e)
        if e.filename_hash:
            x_by_hash.setdefault(e.filename_hash, []).append(e)

    pc_names = set(pc_by_name)
    x_names = set(x_by_name)
    shared_names = sorted(pc_names & x_names)
    xbox_only = sorted(x_names - pc_names)
    pc_only = sorted(pc_names - x_names)

    shared_rows = []
    size_rows = []
    for nm in shared_names:
        for x in x_by_name[nm]:
            for p in pc_by_name[nm]:
                delta = x.total_size - p.total_size
                ratio = (x.total_size / p.total_size) if p.total_size else 0
                shared_rows.append({
                    "name": p.display_name,
                    "safety": detailed_anim_safety(p.display_name),
                    "x360_hash": hex32(x.filename_hash),
                    "pc_hash": hex32(p.filename_hash),
                    "hash_match": x.filename_hash == p.filename_hash and x.filename_hash != 0,
                    "x360_size": x.total_size,
                    "pc_size": p.total_size,
                    "size_delta_x360_minus_pc": delta,
                    "size_ratio_x360_over_pc": f"{ratio:.4f}",
                    "x360_components": "/".join(map(str, x.component_sizes)),
                    "pc_components": "/".join(map(str, p.component_sizes)),
                    "same_component_layout": x.component_sizes == p.component_sizes,
                    "x360_source": x.source_apkf_label,
                    "pc_source": p.source_apkf_label,
                })
                size_rows.append(shared_rows[-1])

    hash_rows = []
    shared_hashes = sorted(set(pc_by_hash) & set(x_by_hash))
    for h in shared_hashes:
        for x in x_by_hash[h]:
            for p in pc_by_hash[h]:
                hash_rows.append({
                    "hash": hex32(h),
                    "x360_name": x.display_name,
                    "pc_name": p.display_name,
                    "same_name": x.display_name.lower() == p.display_name.lower(),
                    "safety": detailed_anim_safety(p.display_name + " " + x.display_name),
                    "x360_size": x.total_size,
                    "pc_size": p.total_size,
                    "size_delta_x360_minus_pc": x.total_size - p.total_size,
                    "x360_components": "/".join(map(str, x.component_sizes)),
                    "pc_components": "/".join(map(str, p.component_sizes)),
                })

    xbox_only_rows = []
    for nm in xbox_only:
        for x in x_by_name[nm]:
            xbox_only_rows.append({
                "name": x.display_name,
                "safety": detailed_anim_safety(x.display_name),
                "x360_hash": hex32(x.filename_hash),
                "x360_size": x.total_size,
                "x360_components": "/".join(map(str, x.component_sizes)),
                "hint": match_known_hint(x.display_name),
                "source": x.source_apkf_label,
            })

    pc_only_rows = []
    for nm in pc_only:
        for p in pc_by_name[nm]:
            pc_only_rows.append({
                "name": p.display_name,
                "safety": detailed_anim_safety(p.display_name),
                "pc_hash": hex32(p.filename_hash),
                "pc_size": p.total_size,
                "pc_components": "/".join(map(str, p.component_sizes)),
                "hint": match_known_hint(p.display_name),
                "source": p.source_apkf_label,
            })

    combat_rows = []
    for r in shared_rows + xbox_only_rows:
        name = r.get("name", "")
        safe = detailed_anim_safety(name)
        if safe == "SAFE_FIRST" or any(k in name.lower() for k in ["smratck", "smbatck", "rage", "punch", "kick", "uppercut", "stomp", "hit", "block"]):
            combat_rows.append(r)

    high_risk_rows = []
    for r in shared_rows + xbox_only_rows + pc_only_rows:
        if detailed_anim_safety(r.get("name", r.get("pc_name", "") + r.get("x360_name", ""))) == "HIGH_RISK":
            high_risk_rows.append(r)

    summary = {
        "pc_pack": str(getattr(pc, "path", "")),
        "x360_pack": str(getattr(x360, "path", "")),
        "pc_anim_count": len(pc.anim_files),
        "x360_anim_count": len(x360.anim_files),
        "shared_name_count": len(shared_names),
        "shared_hash_count": len(shared_hashes),
        "xbox_only_name_count": len(xbox_only),
        "pc_only_name_count": len(pc_only),
        "shared_rows_count": len(shared_rows),
        "xbox_only_rows_count": len(xbox_only_rows),
        "pc_only_rows_count": len(pc_only_rows),
        "safe_or_combat_candidate_rows": len(combat_rows),
        "high_risk_rows": len(high_risk_rows),
    }

    return {
        "summary": summary,
        "shared_by_name": shared_rows,
        "shared_by_hash": hash_rows,
        "xbox_only": xbox_only_rows,
        "pc_only": pc_only_rows,
        "size_comparison": size_rows,
        "safe_combat_candidates": combat_rows,
        "high_risk": high_risk_rows,
    }



def decode_apkf_tag(typeb: bytes, endian: str) -> str:
    """Decode APKF 4-byte type tags.

    PC little-endian payloads store tags readable as bytes: ANIM/MESH/TEX.
    Xbox big-endian payloads in this game store the tag bytes reversed:
    MINA/HSEM/XET/TAM/LEKS/LKSA.
    """
    if endian == ">":
        raw = typeb[::-1]
    else:
        raw = typeb
    return raw.replace(b"\x00", b"").decode("ascii", errors="replace")


@dataclass
class OuterEntry:
    index: int
    hash: int
    type_id: int
    offset: int
    size: int
    end: int
    valid: bool
    sig: str


@dataclass
class ComponentHeader:
    index: int
    table_offset: int
    type_id: str
    external: int
    field2: int
    field3: int
    data_size: int
    data_offset: int
    base_data_address: int
    cursor_pos: int = 0


@dataclass
class ResourceEntry:
    platform: str
    pack_path: str
    pack_kind: str
    global_index: int
    file_type: str
    local_index: int
    filename: str
    filename_hash: int
    file_header_offset: int
    component_sizes: List[int]
    component_offsets: List[Tuple[int, int]]
    source_outer_index: int
    source_outer_hash: int
    source_outer_type_id: int
    source_outer_offset: int
    source_apkf_label: str
    apkf_endian: str

    @property
    def component_count(self) -> int:
        return len(self.component_sizes)

    @property
    def total_size(self) -> int:
        return sum(self.component_sizes)

    @property
    def display_name(self) -> str:
        return self.filename or f"unknown_{self.file_type}_{self.global_index:05d}"

    def identity_key(self) -> Tuple[str, int, str]:
        return (self.file_type.upper(), self.filename_hash, self.display_name.lower())

    def row(self):
        r = {
            "platform": self.platform,
            "pack_kind": self.pack_kind,
            "global_index": self.global_index,
            "file_type": self.file_type,
            "local_index": self.local_index,
            "filename": self.filename,
            "filename_hash": hex32(self.filename_hash),
            "total_size": self.total_size,
            "component_count": self.component_count,
            "components": "/".join(str(x) for x in self.component_sizes),
            "source_outer_index": self.source_outer_index,
            "source_outer_hash": hex32(self.source_outer_hash),
            "source_outer_type_id": f"0x{self.source_outer_type_id:X}",
            "source_outer_offset": hex(self.source_outer_offset),
            "source_apkf_label": self.source_apkf_label,
            "apkf_endian": self.apkf_endian,
            "hint": match_known_hint(self.filename) if self.file_type.upper() == "ANIM" else "",
            "pack_path": self.pack_path,
        }
        for i, sz in enumerate(self.component_sizes):
            r[f"component{i}_size"] = sz
            if i < len(self.component_offsets):
                s, e = self.component_offsets[i]
                r[f"component{i}_start_in_apkf"] = hex(s)
                r[f"component{i}_end_in_apkf"] = hex(e)
                r[f"component{i}_absolute_start"] = hex(self.source_outer_offset + s)
                r[f"component{i}_absolute_end"] = hex(self.source_outer_offset + e)
        return r


class APKFArchive:
    def __init__(self, data: bytes, label: str, endian: str = "<"):
        self.data = data
        self.label = label
        self.endian = endian
        self.resources: List[ResourceEntry] = []
        self.component_headers: List[ComponentHeader] = []
        self.parse()

    @staticmethod
    def align(pos: int, align: int) -> int:
        return pos if align <= 0 else (pos + align - 1) & ~(align - 1)

    def parse(self):
        if self.data[:4] != b"APKF":
            raise ValueError("not APKF")
        endian = self.endian
        comp_count = u32(self.data, 16, endian)
        comp_table_ptr_raw = u32(self.data, 20, endian)
        if not (0 < comp_count < 64):
            raise ValueError(f"bad comp_count={comp_count} endian={endian}")
        comp_off = comp_table_ptr_raw + 20
        if comp_off < 0 or comp_off + comp_count * 24 > len(self.data):
            raise ValueError("component table OOB")

        for i in range(comp_count):
            o = comp_off + i * 24
            typeb = self.data[o:o+4]
            external = u32(self.data, o+4, endian)
            field2 = u32(self.data, o+8, endian)
            field3 = u32(self.data, o+12, endian)
            data_size = u32(self.data, o+16, endian)
            data_offset = u32(self.data, o+20, endian)
            type_id = decode_apkf_tag(typeb, endian)
            base = o + 20 + data_offset
            self.component_headers.append(ComponentHeader(i, o, type_id, external, field2, field3, data_size, data_offset, base))

        off = struct.calcsize("<4s6I")
        global_i = 0
        while off + 4 <= len(self.data):
            type_int = u32(self.data, off, endian)
            if type_int == 0:
                break
            base = off
            if off + 20 > len(self.data):
                break
            n_active = u32(self.data, off + 8, endian)
            p_file_header_table = u32(self.data, off + 12, endian)
            n_file_headers = u32(self.data, off + 16, endian)
            off += 20
            if not (0 <= n_active <= len(self.component_headers)) or not (0 <= n_file_headers <= 50000):
                raise ValueError("bad file type block")
            if off + 4 * len(self.component_headers) > len(self.data):
                break
            aligns = [u32(self.data, off + 4*i, endian) for i in range(len(self.component_headers))]
            off += 4 * len(self.component_headers)

            raw_type = self.data[base:base+4]
            type_id = decode_apkf_tag(raw_type, endian)

            p_headers = base + 12 + p_file_header_table
            if p_headers < 0 or p_headers >= len(self.data):
                continue
            foff = p_headers
            for local_i in range(n_file_headers):
                if foff + 8 > len(self.data):
                    break
                fh_base = foff
                p_filename = u32(self.data, foff, endian)
                fname_hash = u32(self.data, foff+4, endian)
                foff += 8
                sizes = []
                if n_active:
                    if foff + 4*n_active > len(self.data):
                        break
                    sizes = [u32(self.data, foff + 4*i, endian) for i in range(n_active)]
                    foff += 4*n_active

                filename = read_cstr(self.data, fh_base + p_filename)
                offsets = []
                for ci, comp_size in enumerate(sizes):
                    ch = self.component_headers[ci]
                    alignment = aligns[ci] & 0xFFFFFF
                    read_pos = self.align(max(0, ch.cursor_pos - 1), alignment)
                    start = ch.base_data_address + read_pos
                    end = start + comp_size
                    offsets.append((start, end))
                    ch.cursor_pos = read_pos + comp_size

                self.resources.append(ResourceEntry(
                    platform="",
                    pack_path="",
                    pack_kind="",
                    global_index=global_i,
                    file_type=type_id,
                    local_index=local_i,
                    filename=filename,
                    filename_hash=fname_hash,
                    file_header_offset=fh_base,
                    component_sizes=sizes,
                    component_offsets=offsets,
                    source_outer_index=-1,
                    source_outer_hash=0,
                    source_outer_type_id=0,
                    source_outer_offset=0,
                    source_apkf_label=self.label,
                    apkf_endian=endian,
                ))
                global_i += 1


def try_parse_apkf(payload: bytes, label: str) -> APKFArchive:
    errs = []
    for endian in ("<", ">"):
        try:
            return APKFArchive(payload, label, endian=endian)
        except Exception as e:
            errs.append(f"{endian}:{e}")
    raise ValueError("; ".join(errs))


class ExtractedAnimSet:
    def __init__(self, path: Path, platform_hint="X360"):
        self.path = path
        self.data = b""
        self.size = 0
        self.kind = "EXTRACTED_OUTPUT"
        self.platform = platform_hint
        self.outer_endian = "n/a"
        self.outer_entries = []
        self.resources: List[ResourceEntry] = []
        self.errors: List[str] = []
        self._blob_sources = {}  # source_apkf_label -> APKF bytes or focused extracted component bytes
        self.detect_info = {
            "path": str(path),
            "kind": self.kind,
            "platform": self.platform,
            "note": "folder/zip fallback: APKF + focused-chain entry.json support + loose extracted ANIM list",
        }
        self.scan()

    @property
    def anim_files(self):
        return [r for r in self.resources if r.file_type.upper() == "ANIM"]

    def _add_loose(self, rel: str, size: int, idx: int, blob: bytes = b""):
        nm = name_from_path_text(rel)
        h = hash_from_text(rel)
        label = f"LOOSE_FILE_{rel}"
        if blob:
            self._blob_sources[label] = blob
        self.resources.append(ResourceEntry(
            platform=self.platform,
            pack_path=str(self.path),
            pack_kind=self.kind,
            global_index=idx,
            file_type="ANIM",
            local_index=idx,
            filename=nm,
            filename_hash=h,
            file_header_offset=0,
            component_sizes=[size],
            component_offsets=[(0, size)],
            source_outer_index=-1,
            source_outer_hash=0,
            source_outer_type_id=0,
            source_outer_offset=0,
            source_apkf_label=label,
            apkf_endian="n/a",
        ))

    def _component_sizes_from_entry_json(self, meta: dict) -> List[int]:
        count = int(meta.get("component_count") or 0)
        sizes = []
        for i in range(count):
            v = meta.get(f"component{i}_size")
            try:
                sizes.append(int(v))
            except Exception:
                pass
        if not sizes:
            for k, v in sorted(meta.items()):
                if re.match(r"component\d+_size$", str(k)):
                    try:
                        sizes.append(int(v))
                    except Exception:
                        pass
        if not sizes:
            try:
                sizes = [int(meta.get("combined_raw_size") or meta.get("total_component_size") or 0)]
            except Exception:
                sizes = [0]
        return [int(x) for x in sizes if int(x) >= 0]

    def _hash_from_entry_json(self, meta: dict) -> int:
        h = meta.get("filename_hash", 0)
        if isinstance(h, int):
            return h & 0xFFFFFFFF
        if isinstance(h, str):
            return hash_from_text(h)
        return 0

    def _add_focused_chain_entry(self, rel_entry_json: str, meta: dict, read_member, idx: int) -> bool:
        """Parse v1.6 focus-chain ANIM/<resource>/entry.json into one resource.

        This prevents focused extracted outputs from being miscounted as 3 ANIM files
        (combined_raw.bin + component0.bin + entry.json). It also retains payload bytes
        so same-size slot tests can use focused chains as source payloads.
        """
        if str(meta.get("file_type", "")).upper() != "ANIM":
            return False
        name = str(meta.get("filename") or name_from_path_text(rel_entry_json))
        sizes = self._component_sizes_from_entry_json(meta)
        if not sizes:
            return False
        folder = str(Path(rel_entry_json).parent).replace("\\", "/")
        combined_name = str(meta.get("combined_raw_file") or "combined_raw.bin")
        combined_rel = f"{folder}/{combined_name}"
        blob = b""
        try:
            blob = read_member(combined_rel)
        except Exception:
            # Fall back to concatenating componentN_file values.
            chunks = []
            for i, sz in enumerate(sizes):
                fn = meta.get(f"component{i}_file") or f"component{i}_{sz}bytes.bin"
                try:
                    chunks.append(read_member(f"{folder}/{fn}"))
                except Exception:
                    chunks.append(b"\x00" * int(sz))
            blob = b"".join(chunks)
        offsets = []
        pos = 0
        for sz in sizes:
            offsets.append((pos, pos + int(sz)))
            pos += int(sz)
        # If combined file is bigger/smaller, keep component table authoritative but retain bytes.
        label = f"FOCUSED_CHAIN_{rel_entry_json}"
        self._blob_sources[label] = blob
        try:
            global_index = int(meta.get("global_index", idx))
        except Exception:
            global_index = idx
        try:
            local_index = int(meta.get("local_index", idx))
        except Exception:
            local_index = idx
        self.resources.append(ResourceEntry(
            platform=self.platform,
            pack_path=str(self.path),
            pack_kind="FOCUSED_CHAIN_OUTPUT",
            global_index=global_index,
            file_type="ANIM",
            local_index=local_index,
            filename=name,
            filename_hash=self._hash_from_entry_json(meta),
            file_header_offset=0,
            component_sizes=sizes,
            component_offsets=offsets,
            source_outer_index=-1,
            source_outer_hash=hash_from_text(str(meta.get("source_outer_hash", ""))),
            source_outer_type_id=hash_from_text(str(meta.get("source_outer_type", ""))),
            source_outer_offset=0,
            source_apkf_label=label,
            apkf_endian="focused-chain",
        ))
        return True

    def _parse_apkf_blob_from_output(self, rel_name: str, blob: bytes, idx_start: int) -> int:
        if not blob.startswith(b"APKF"):
            return idx_start
        try:
            apkf = try_parse_apkf(blob, f"EXTRACTED_APKF_BIN_{rel_name}")
        except Exception as e:
            self.errors.append(f"Could not parse APKF bin {rel_name}: {e}")
            return idx_start

        label = f"EXTRACTED_APKF_BIN_{rel_name}"
        self._blob_sources[label] = blob

        added = 0
        for r in apkf.resources:
            r.platform = self.platform
            r.pack_path = str(self.path)
            r.pack_kind = "X360_EXTRACTED_APKF_BIN" if self.platform == "X360" else "EXTRACTED_APKF_BIN"
            r.global_index = idx_start + added
            r.source_outer_offset = 0
            r.source_apkf_label = label
            self.resources.append(r)
            added += 1

        self.errors.append(
            f"Parsed extracted APKF bin {rel_name}: recovered {added} resources, "
            f"{len([r for r in apkf.resources if r.file_type.upper() == 'ANIM'])} ANIM."
        )
        return idx_start + added

    def scan(self):
        idx = 0
        focused_added = 0

        if self.path.is_dir():
            # First pass: focus-chain entry.json folders from extractor v1.6.
            def read_dir_member(rel):
                return (self.path / rel).read_bytes()
            for p in self.path.rglob("entry.json"):
                rel = str(p.relative_to(self.path)).replace("\\", "/")
                if "/ANIM/" not in rel.upper().replace("\\", "/"):
                    continue
                try:
                    meta = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                    if self._add_focused_chain_entry(rel, meta, read_dir_member, idx):
                        idx += 1
                        focused_added += 1
                except Exception as e:
                    self.errors.append(f"Focused entry.json read failed {rel}: {e}")
            if focused_added:
                self.detect_info["focused_chain_entry_json_count"] = focused_added
                self.detect_info["anim_count"] = len(self.anim_files)
                self.detect_info["resource_count"] = len(self.resources)
                return

            # Second pass: APKF bins and loose outputs.
            for p in self.path.rglob("*"):
                if not p.is_file():
                    continue
                rel = str(p.relative_to(self.path)).replace("\\", "/")
                try:
                    blob = p.read_bytes()
                    head = blob[:4]
                except Exception:
                    blob = b""
                    head = b""
                if head == b"APKF":
                    try:
                        idx = self._parse_apkf_blob_from_output(rel, blob, idx)
                    except Exception as e:
                        self.errors.append(f"APKF read failed {rel}: {e}")
                    continue
                if not looks_like_anim_path(rel):
                    continue
                # Avoid counting helper JSON as loose ANIM.
                if Path(rel).name.lower() == "entry.json":
                    continue
                self._add_loose(rel, p.stat().st_size, idx, blob)
                idx += 1
        else:
            with zipfile.ZipFile(self.path, "r") as z:
                names = [n for n in z.namelist() if not n.endswith("/")]
                name_set = set(names)

                def read_zip_member(rel):
                    # Normalize from Path() on Linux to zip slash names.
                    rel = str(rel).replace("\\", "/")
                    if rel in name_set:
                        return z.read(rel)
                    # Some zips include a top folder. Try suffix match.
                    matches = [n for n in names if n.endswith("/" + rel) or n == rel]
                    if matches:
                        return z.read(matches[0])
                    raise KeyError(rel)

                # First pass: focus-chain entry.json folders from extractor v1.6.
                for n in names:
                    norm = n.replace("\\", "/")
                    if not norm.lower().endswith("/entry.json"):
                        continue
                    if "/anim/" not in norm.lower():
                        continue
                    try:
                        meta = json.loads(z.read(n).decode("utf-8", errors="replace"))
                        if self._add_focused_chain_entry(norm, meta, read_zip_member, idx):
                            idx += 1
                            focused_added += 1
                    except Exception as e:
                        self.errors.append(f"Focused zip entry.json read failed {n}: {e}")
                if focused_added:
                    self.detect_info["focused_chain_entry_json_count"] = focused_added
                    self.detect_info["anim_count"] = len(self.anim_files)
                    self.detect_info["resource_count"] = len(self.resources)
                    return

                # Second pass: APKF bins and loose outputs.
                for n in names:
                    try:
                        blob = z.read(n)
                        head = blob[:4]
                    except Exception:
                        blob = b""
                        head = b""
                    if head == b"APKF":
                        try:
                            idx = self._parse_apkf_blob_from_output(n, blob, idx)
                        except Exception as e:
                            self.errors.append(f"APKF zip read failed {n}: {e}")
                        continue
                    if not looks_like_anim_path(n):
                        continue
                    if Path(n).name.lower() == "entry.json":
                        continue
                    info = z.getinfo(n)
                    self._add_loose(n, info.file_size, idx, blob)
                    idx += 1

        self.detect_info["focused_chain_entry_json_count"] = focused_added
        self.detect_info["anim_count"] = len(self.anim_files)
        self.detect_info["resource_count"] = len(self.resources)

    def component_blob(self, entry, i):
        # Real APKF parsed entries or focused-chain entries point into retained blob bytes.
        blob = self._blob_sources.get(entry.source_apkf_label)
        if blob is not None and i < len(entry.component_offsets):
            s, e = entry.component_offsets[i]
            return blob[s:e]
        return b""

    def combined_blob(self, entry):
        out = bytearray()
        for i in range(entry.component_count):
            out += self.component_blob(entry, i)
        return bytes(out)

    def component_sha_list(self, entry):
        return [sha1(self.component_blob(entry, i)) for i in range(entry.component_count)]


class SM3Pack:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        self.size = len(self.data)
        self.kind = "UNKNOWN"
        self.platform = "UNKNOWN"
        self.outer_endian = "<"
        self.table_start: Optional[int] = None
        self.outer_entries: List[OuterEntry] = []
        self.resources: List[ResourceEntry] = []
        self.errors: List[str] = []
        self.detect_info: Dict[str, object] = {}
        self.parse()

    @property
    def anim_files(self):
        return [r for r in self.resources if r.file_type.upper() == "ANIM"]

    def score_table(self, start: int, count: int, endian: str) -> dict:
        if count <= 0 or count > 100000 or start + count * 16 > self.size:
            return {"table_start": hex(start), "score": -1, "valid": 0, "apkf": 0}
        valid = apkf = known = small = 0
        for i in range(count):
            o = start + i*16
            h = u32(self.data, o, endian)
            t = u32(self.data, o+4, endian)
            do = u32(self.data, o+8, endian)
            ds = u32(self.data, o+12, endian)
            end = do + ds
            ok = ds > 0 and 0 <= do <= end <= self.size
            if not ok:
                continue
            valid += 1
            sig = self.data[do:do+4]
            if sig == b"APKF":
                apkf += 1
                known += 1
            elif sig in (b"hsam", b"mash", b"ElmS", b"NumW") or sig.startswith(b"__Id"):
                known += 1
            if 0 <= t <= 0x100:
                small += 1
        return {"table_start": hex(start), "score": valid*10 + apkf*500 + known*30 + small*5, "valid": valid, "apkf": apkf, "known": known, "small_type": small}

    def detect(self):
        sig0 = self.data[:4]
        sig30 = self.data[PC_MAGIC_OFF:PC_MAGIC_OFF+4] if self.size >= PC_MAGIC_OFF + 4 else b""
        if sig30 == PC_MAGIC:
            self.kind = "PCPACK"
            self.platform = "PC"
            self.outer_endian = "<"
            count = u32(self.data, PC_COUNT_OFF, "<")
        elif sig30 == X360_MAGIC:
            self.kind = "XEPACK"
            self.platform = "X360"
            self.outer_endian = ">"
            count = u32(self.data, PC_COUNT_OFF, ">")
            if not (0 < count < 100000):
                count = u32(self.data, PC_COUNT_OFF, "<")
                self.outer_endian = "<"
        elif sig0.startswith(b"NCH"):
            raise ValueError("Looks like WOS/NCH, not SM3 PC/X360.")
        else:
            raise ValueError(f"Unknown pack. sig0={sig0!r} sig30={sig30!r}")

        scores = [self.score_table(s, count, self.outer_endian) for s in TABLE_START_CANDIDATES]
        best = max(scores, key=lambda r: r["score"])
        self.table_start = int(best["table_start"], 16)
        self.detect_info = {
            "path": str(self.path),
            "size": self.size,
            "sha1": sha1(self.data),
            "kind": self.kind,
            "platform": self.platform,
            "outer_endian": self.outer_endian,
            "count": count,
            "selected_table_start": best["table_start"],
            "candidate_scores": scores,
        }

    def parse(self):
        self.detect()
        count = int(self.detect_info["count"])
        endian = self.outer_endian
        assert self.table_start is not None
        for i in range(count):
            o = self.table_start + i*16
            if o + 16 > self.size:
                break
            h = u32(self.data, o, endian)
            t = u32(self.data, o+4, endian)
            do = u32(self.data, o+8, endian)
            ds = u32(self.data, o+12, endian)
            end = do + ds
            valid = ds > 0 and 0 <= do <= end <= self.size
            sig = self.data[do:do+4].decode("latin1", errors="replace") if valid else ""
            self.outer_entries.append(OuterEntry(i, h, t, do, ds, end, valid, sig))
        self._parse_apkfs_from_outer()

        if self.platform == "X360" and len(self.anim_files) == 0:
            self._xbox_brute_apkf_fallback()

    def _parse_apkfs_from_outer(self):
        for outer in self.outer_entries:
            if not outer.valid:
                continue
            payload = self.data[outer.offset:outer.end]
            if not payload.startswith(b"APKF"):
                continue
            label = f"F{outer.index:04d}_{hex32(outer.hash)}_T{outer.type_id}"
            try:
                apkf = try_parse_apkf(payload, label)
            except Exception as e:
                self.errors.append(f"{label}: {e}")
                continue
            for r in apkf.resources:
                r.platform = self.platform
                r.pack_path = str(self.path)
                r.pack_kind = self.kind
                r.source_outer_index = outer.index
                r.source_outer_hash = outer.hash
                r.source_outer_type_id = outer.type_id
                r.source_outer_offset = outer.offset
                r.source_apkf_label = label
                self.resources.append(r)

    def _xbox_brute_apkf_fallback(self):
        positions = []
        start = 0
        while True:
            pos = self.data.find(b"APKF", start)
            if pos < 0:
                break
            positions.append(pos)
            start = pos + 4
        recovered = 0
        for idx, pos in enumerate(positions):
            next_pos = positions[idx+1] if idx+1 < len(positions) else len(self.data)
            # Try next APKF boundary and a few bounded windows.
            sizes = [next_pos - pos, 0x200000, 0x800000, 0x2000000, len(self.data) - pos]
            tried = set()
            for sz in sizes:
                if sz <= 0 or sz in tried:
                    continue
                tried.add(sz)
                blob = self.data[pos:pos+sz]
                if len(blob) < 32:
                    continue
                try:
                    apkf = try_parse_apkf(blob, f"BRUTE_APKF_{idx:03d}_0x{pos:X}")
                    got = 0
                    for r in apkf.resources:
                        if r.file_type.upper() != "ANIM":
                            continue
                        r.platform = "X360"
                        r.pack_path = str(self.path)
                        r.pack_kind = "XEPACK_BRUTE_APKF_SCAN"
                        r.source_outer_offset = pos
                        r.source_apkf_label = f"BRUTE_APKF_{idx:03d}_0x{pos:X}"
                        self.resources.append(r)
                        got += 1
                    if got:
                        recovered += got
                        break
                except Exception:
                    pass
        if recovered:
            self.kind = "XEPACK_BRUTE_APKF_SCAN"
            self.errors.append(f"Direct XEPACK parse found 0 ANIM; brute APKF fallback recovered {recovered} ANIM entries.")
        else:
            # Last resort: recover animation-like string names from the raw XEPACK.
            string_resources = xbox_raw_anim_string_scan(self.data, str(self.path))
            if string_resources:
                self.kind = "XEPACK_RAW_STRING_SCAN"
                self.resources.extend(string_resources)
                self.errors.append(
                    f"Direct XEPACK parse found 0 ANIM and brute APKF recovered 0. "
                    f"Raw string scan recovered {len(string_resources)} animation-like names. "
                    f"These are NAME-ONLY entries with no payload offsets."
                )
            else:
                self.errors.append(
                    f"Direct XEPACK parse found 0 ANIM. Found {len(positions)} APKF signatures but recovered 0 ANIM, "
                    f"and raw string scan found 0 animation-like names. Use v0.3 focused extractor output zip/folder as Pack B."
                )

    def component_blob(self, entry, i):
        s, e = entry.component_offsets[i]
        return self.data[entry.source_outer_offset+s:entry.source_outer_offset+e]

    def combined_blob(self, entry):
        out = bytearray()
        for i in range(entry.component_count):
            out += self.component_blob(entry, i)
        return bytes(out)

    def component_sha_list(self, entry):
        return [sha1(self.component_blob(entry, i)) for i in range(entry.component_count)]



def detect_platform_from_extracted_path(path: Path, preferred_platform="PC") -> str:
    """Detect platform for extracted-output folders/zips.

    v2.2 fix:
    The GUI passes Pack A with preferred_platform='PC', but users often put
    X360_SpiderPack_Extract_Lab_Output.zip in Pack A. This function prevents
    the Xbox output zip from being mislabeled as PC.
    """
    text = str(path).upper()
    if any(k in text for k in ["X360", "XBOX", "XEPACK", "SPIDERPACK_EXTRACT_LAB", "TYPE36", "D5E3B4"]):
        return "X360"
    if any(k in text for k in ["PCPACK", "PC_CH_", "CH_SPIDERMAN_SIDE_FOR_ANIM_COMPARE"]):
        return "PC"

    try:
        if path.is_dir():
            sample = " ".join(str(p.relative_to(path)).upper() for p in list(path.rglob("*"))[:80])
            if any(k in sample for k in ["X360", "XBOX", "XEPACK", "TYPE36", "D5E3B4", "EXTRACTED_TYPE36"]):
                return "X360"
            if any(k in sample for k in ["PCPACK", "CH_SPIDERMAN.PCPACK"]):
                return "PC"
        elif path.is_file() and path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path, "r") as z:
                sample_names = z.namelist()[:120]
                sample = " ".join(n.upper() for n in sample_names)
                if any(k in sample for k in ["X360", "XBOX", "XEPACK", "TYPE36", "D5E3B4", "EXTRACTED_TYPE36"]):
                    return "X360"
                if any(k in sample for k in ["PCPACK", "CH_SPIDERMAN.PCPACK"]):
                    return "PC"
    except Exception:
        pass

    return preferred_platform




def bytes_from_hxd_hex_dump_blob(blob: bytes) -> bytes:
    """Convert an HxD-style hex dump TXT into original binary bytes.

    Supports lines like:
      00000030  68 73 61 6D ...  hsam...
    Returns b"" when the blob is not a recognizable offset/hex-byte dump.
    """
    try:
        text = blob.decode("utf-8-sig", errors="ignore")
    except Exception:
        return b""
    out = bytearray()
    rows = 0
    for line in text.splitlines():
        m = re.match(r"^\s*([0-9A-Fa-f]{8,16})\s+(.+)$", line)
        if not m:
            continue
        try:
            off = int(m.group(1), 16)
        except Exception:
            continue
        toks = m.group(2).strip().split()
        bs = []
        for t in toks:
            if re.fullmatch(r"[0-9A-Fa-f]{2}", t):
                bs.append(int(t, 16))
                if len(bs) >= 16:
                    break
            elif bs:
                break
        if not bs:
            continue
        # HxD dumps should be strictly ordered. If a short/duplicate row appears, stop before corruption.
        if off != len(out):
            if rows == 0:
                continue
            break
        out.extend(bs)
        rows += 1
    if rows < 4 or len(out) < 0x58:
        return b""
    return bytes(out)


def looks_like_sm3_pack_bytes(data: bytes) -> bool:
    return len(data) >= 0x58 and data[PC_MAGIC_OFF:PC_MAGIC_OFF+4] in (PC_MAGIC, X360_MAGIC)


def pack_suffix_from_bytes(data: bytes) -> str:
    if len(data) >= PC_MAGIC_OFF + 4 and data[PC_MAGIC_OFF:PC_MAGIC_OFF+4] == X360_MAGIC:
        return ".XEPACK"
    return ".PCPACK"


def try_load_hxd_hex_dump_as_pack(blob: bytes, original_path: Path, source_name: str = ""):
    data = bytes_from_hxd_hex_dump_blob(blob)
    if not looks_like_sm3_pack_bytes(data):
        return None
    tmpdir = Path(tempfile.mkdtemp(prefix="sm3_hxd_hex_input_"))
    safe_stem = clean_name(Path(source_name or original_path.name).stem, "hex_dump_input")
    tmp_pack = tmpdir / (safe_stem + pack_suffix_from_bytes(data))
    tmp_pack.write_bytes(data)
    pack = SM3Pack(tmp_pack)
    pack.detect_info["loaded_from_hxd_hex_dump"] = str(original_path)
    pack.detect_info["hex_dump_inner_name"] = source_name
    pack.detect_info["hex_dump_decoded_size"] = len(data)
    pack.path = original_path
    return pack

def load_pack_or_extracted(path: Path, preferred_platform="PC"):
    """Load a direct pack, extracted-output folder/zip, zip containing a pack, or HxD hex-dump TXT.

    v2.6 fix:
    - If a .zip contains CH_PLAYERGOBLIN.txt / CH_PETER.txt / any HxD-style TXT dump,
      convert it back to a temporary PCPACK/XEPACK and parse it as a real pack.
    - Direct .txt HxD dumps are also supported.
    - This is required for uploaded CH_PLAYERGOBLIN(2).zip-style PC dumps.
    """
    detected_platform = detect_platform_from_extracted_path(path, preferred_platform)

    if path.is_dir():
        return ExtractedAnimSet(path, platform_hint=detected_platform)

    if path.is_file() and path.suffix.lower() == ".txt":
        pack = try_load_hxd_hex_dump_as_pack(path.read_bytes(), path, path.name)
        if pack is not None:
            return pack
        return ExtractedAnimSet(path, platform_hint=detected_platform)

    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            pack_names = [n for n in names if Path(n).suffix.lower() in (".pcpack", ".xepack")]
            if pack_names:
                # Prefer CH_SPIDERMAN when present, then obvious character names, otherwise shortest path.
                def pack_sort_key(n):
                    up = Path(n).name.upper()
                    pri = 5
                    if "CH_SPIDERMAN" in up: pri = 0
                    elif "CH_BLACKSUIT" in up: pri = 1
                    elif "CH_PLAYERGOBLIN" in up: pri = 2
                    elif "CH_PETER" in up: pri = 3
                    return (pri, len(n))
                pack_names.sort(key=pack_sort_key)
                inner = pack_names[0]
                tmpdir = Path(tempfile.mkdtemp(prefix="sm3_pack_zip_input_"))
                tmp_pack = tmpdir / Path(inner).name
                tmp_pack.write_bytes(z.read(inner))
                pack = SM3Pack(tmp_pack)
                pack.detect_info["loaded_from_zip"] = str(path)
                pack.detect_info["inner_pack_name"] = inner
                pack.path = path
                return pack

            # v2.6: HxD text dump inside zip, e.g. CH_PLAYERGOBLIN.txt.
            txt_names = [n for n in names if Path(n).suffix.lower() in (".txt", ".hex")]
            # Prefer CH_* dumps over README/report text.
            txt_names.sort(key=lambda n: (0 if Path(n).name.upper().startswith("CH_") else 1, len(n)))
            for inner in txt_names:
                try:
                    blob = z.read(inner)
                except Exception:
                    continue
                pack = try_load_hxd_hex_dump_as_pack(blob, path, inner)
                if pack is not None:
                    return pack

        # No inner pack/hex dump. Treat as extracted output zip.
        return ExtractedAnimSet(path, platform_hint=detected_platform)

    return SM3Pack(path)

def same_size_ok(src, dst, strict_components=True):
    if src.file_type.upper() != "ANIM" or dst.file_type.upper() != "ANIM":
        return False, "Both source and destination must be ANIM."
    if src.pack_kind == "XEPACK_RAW_STRING_SCAN" or dst.pack_kind == "XEPACK_RAW_STRING_SCAN":
        return False, "name-only Xbox string-scan entry; no payload size/offset available."
    if strict_components:
        if src.component_count != dst.component_count:
            return False, f"component count mismatch source={src.component_count} dest={dst.component_count}"
        for i, (a, b) in enumerate(zip(src.component_sizes, dst.component_sizes)):
            if a != b:
                return False, f"component{i} size mismatch source={a} dest={b}"
        return True, "strict component sizes match"
    if src.total_size != dst.total_size:
        return False, f"total size mismatch source={src.total_size} dest={dst.total_size}"
    return True, "combined total size matches"


def patch_pc_anim_copy(dest_pack, source_pack, dest, src, output, strict_components=True, allow_x360_source=False):
    if dest_pack.platform != "PC":
        raise ValueError("Destination must be a PC PCPACK. This tool never patches Xbox packs.")

    if source_pack.platform != "PC":
        if not allow_x360_source:
            raise ValueError("Source is not PC. Use Xbox/RVB -> PC TEST PATCH mode for Xbox/RVB sources.")
        if source_pack.platform != "X360":
            raise ValueError("Only PC or X360 source packs are supported.")
        if src.pack_kind == "XEPACK_RAW_STRING_SCAN":
            raise ValueError("Cannot patch from name-only string-scan entries. Use extracted Type36/APKF output zip.")
        if not source_pack.combined_blob(src):
            raise ValueError("X360 source payload bytes are unavailable. Use the extracted output ZIP/folder, not raw string scan.")

    ok, reason = same_size_ok(src, dest, strict_components)
    if not ok:
        raise ValueError(reason)

    out_data = bytearray(dest_pack.data)
    records = []
    for ci in range(dest.component_count):
        d_s, d_e = dest.component_offsets[ci]
        d_abs_s = dest.source_outer_offset + d_s
        d_abs_e = dest.source_outer_offset + d_e

        src_blob = source_pack.component_blob(src, ci)
        if not src_blob:
            raise ValueError(f"Source component {ci} bytes unavailable.")
        old = bytes(out_data[d_abs_s:d_abs_e])
        if len(src_blob) != len(old):
            raise ValueError(f"Internal component length mismatch {ci}: source={len(src_blob)} dest={len(old)}")

        out_data[d_abs_s:d_abs_e] = src_blob
        records.append({
            "component": ci,
            "dest_offset": hex(d_abs_s),
            "size": len(src_blob),
            "changed": old != src_blob,
        })

    output.write_bytes(bytes(out_data))
    log = {
        "tool": "SM3_PC_RVB_TO_PC_ANIM_SWAP_TEST_v2_4",
        "mode": "Xbox/RVB_TO_PC_TEST_PATCH" if source_pack.platform == "X360" else "PC_TO_PC_PATCH",
        "warning": "Experimental. Same-size/component-size validation only; animation format/state may still crash.",
        "dest_pack": str(dest_pack.path),
        "source_pack": str(source_pack.path),
        "output": str(output),
        "dest_slot_kept": dest.display_name,
        "source_payload_from": src.display_name,
        "dest_component_sizes": dest.component_sizes,
        "source_component_sizes": src.component_sizes,
        "validation": reason,
        "patch_records": records,
    }
    output.with_suffix(output.suffix + ".ANIM_SWAP_LOG.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    output.with_suffix(output.suffix + ".ANIM_SWAP_LOG.txt").write_text(
        "SM3 ANIMATION SWAPPER - ANIM TEST PATCH\n"
        f"DEST SLOT KEPT: {dest.display_name}\n"
        f"SOURCE PAYLOAD: {src.display_name}\n"
        f"VALIDATION: {reason}\n"
        "WARNING: Experimental. Test one swap at a time.\n",
        encoding="utf-8"
    )
    return log




FAMILY_KEYWORDS = {
    "combat": [
        "atck", "attack", "punch", "kick", "hit", "block", "rage", "beatdown",
        "uppercut", "stomp", "pummel", "smratck", "smbatck", "bs_rage"
    ],
    "walk": [
        "walk", "run", "idle2run", "run2idle", "walk2idle", "idle2walk",
        "tapback", "tapforward", "tapleft", "tapright"
    ],
    "swing": [
        "swing", "swg", "webswing", "poleswg"
    ],
    "jump": [
        "jump", "jmp", "land", "fall", "dive", "launch", "lnch", "fly"
    ],
}


def anim_in_family(name: str, family: str) -> bool:
    low = (name or "").lower()
    return any(k in low for k in FAMILY_KEYWORDS.get(family, []))


def family_label_for_name(name: str) -> str:
    hits = [fam for fam in FAMILY_KEYWORDS if anim_in_family(name, fam)]
    return ",".join(hits) if hits else "other"


SAFE_LITE_ALLOW = {
    "combat_lite": [
        "hit", "block", "punch", "kick", "uppercut", "stomp", "pummel",
        "smratckcreskck", "smbatckpummel"
    ],
    "hit_reaction": [
        "hit", "deflect", "enemyblock", "block"
    ],
    "idle_walk_lite": [
        "idle_tap", "idle2run", "idle2walk", "walk2idle", "run2idle"
    ],
}

DANGER_WORDS = [
    "swg", "swing", "wall", "jmp", "jump", "dive", "fall", "land", "lnch",
    "launch", "zip", "grap", "mission", "scene", "boss", "vehicle", "veco",
    "water", "pole", "crawl", "crwl", "sky"
]


def is_danger_anim(name: str) -> bool:
    low = (name or "").lower()
    return any(w in low for w in DANGER_WORDS)


def in_safe_lite_group(name: str, group: str) -> bool:
    low = (name or "").lower()
    if not any(w in low for w in SAFE_LITE_ALLOW.get(group, [])):
        return False
    if group == "idle_walk_lite":
        return not any(w in low for w in ["swg", "swing", "jmp", "jump", "dive", "fall", "wall", "zip", "grap"])
    return not is_danger_anim(low)


def source_suit_warning(dest_pack, src_pack):
    src_text = str(getattr(src_pack, "path", "")).upper()
    dest_text = str(getattr(dest_pack, "path", "")).upper()
    warnings = []
    if "BLACK" in dest_text and not any(k in src_text for k in ["BLACK", "RVBBLACK", "RVB_BLACK"]):
        warnings.append("Destination looks like BLACKSUIT, but source path does not look like RVB/BLACK. You may be mixing normal Spider-Man source into black suit.")
    if "SPIDERMAN" in dest_text and "BLACK" in src_text:
        warnings.append("Destination looks like red Spider-Man, but source path looks black suit.")
    return warnings


def build_safe_lite_matches(dest_pack, src_pack, group: str, max_count: int = 20):
    dest_by_name = {d.display_name.lower(): d for d in dest_pack.anim_files}
    rows = []
    pairs = []
    for s in src_pack.anim_files:
        if s.pack_kind == "XEPACK_RAW_STRING_SCAN":
            continue
        if not in_safe_lite_group(s.display_name, group):
            continue
        d = dest_by_name.get(s.display_name.lower())
        if not d:
            continue
        ok, reason = same_size_ok(s, d, True)
        row = {
            "will_patch": bool(ok),
            "reason": reason,
            "group": group,
            "name": s.display_name,
            "source_hash": hex32(s.filename_hash),
            "dest_hash": hex32(d.filename_hash),
            "source_size": s.total_size,
            "dest_size": d.total_size,
            "source_components": "/".join(map(str, s.component_sizes)),
            "dest_components": "/".join(map(str, d.component_sizes)),
            "safety": detailed_anim_safety(s.display_name),
            "danger_filtered": is_danger_anim(s.display_name),
        }
        rows.append(row)
        if ok and src_pack.combined_blob(s):
            pairs.append((d, s))
    pairs.sort(key=lambda ds: (is_danger_anim(ds[1].display_name), ds[1].total_size, ds[1].display_name.lower()))
    rows.sort(key=lambda r: (not r["will_patch"], r["danger_filtered"], r["source_size"], r["name"].lower()))
    return pairs[:max_count], rows




def source_dest_for_rvb_mode(pack_a, pack_b):
    """Release source mode: Pack A is always the PC destination; Pack B can be PC or Xbox/RVB source."""
    if not pack_a or not pack_b:
        raise ValueError("Load/verify packs first.")
    if pack_a.platform != "PC":
        raise ValueError("Pack A must be the PC destination pack. Pack B can be a PC source pack or an Xbox/RVB source ZIP.")
    if pack_b.platform not in ("PC", "X360"):
        raise ValueError("Pack B must be a supported source pack: PC or Xbox/RVB.")
    return pack_a, pack_b



MULTI_SELECTION_PRESETS = {
    "RVB_RED_COMBAT_RESTORED_5PACK - RELEASE STABLE": [
        ("sm3k02_powerswitch", "bs3atck3bheb"),
        ("sm3idle_tapback", "rvbatckmultianglefury2"),
        ("sm3crchlwebbck", "rvbatckmultianglefury3"),
        ("sm3idle_tapleft", "smridlcrchstickit"),
        ("sm3webmulti_webright", "smridlcrchrlegback"),
    ],
    "BLACK_SUIT_COMBAT_BETA - RELEASE": [
        ("sm3ddgatck3hl_v2", "smratckpun2kneelnch"),
    ],
    "SM2_MOVEMENT_RESTORE_PACK - EXPERIMENTAL RELEASE": [
        ("sm3swgsprintrlsmid2dive", "sm2divefall"),
        ("sm3jmpsprintchg2dive", "sm2jmpsprintchgfly"),
        ("sm3jmplnch", "sm2jmprunchgfly"),
        ("sm3jmpchglnch", "sm2jmpchgfly"),
        ("sm3doublejump2dive", "sm2divefall"),
        ("sm3jmpchg2dive", "sm2flailf"),
    ],
    "SWING_DIVE_COMPATIBILITY_TEST - SUBTLE RELEASE": [
        ("sm3jmpsprint2dive", "bs3swgchgrls2dive"),
    ],
    "SLOW_SWING_SAFE_TEST - RELEASE": [
        ("sm3slowswing270", "sm3slowswing180"),
    ],
    "PETER_DEBUG_WALL_TEST_F - LAB RELEASE": [
        ("sm3toa_dan3ht2crkscr", "smrwallatck_test_f"),
    ],
    "PETER_DEBUG_WALL_TEST_L - LAB RELEASE": [
        ("sm3toa_dan1horcrtwhl", "smrwallatck_test_l"),
    ],
    "PETER_DEBUG_WALL_TEST_R - LAB RELEASE": [
        ("sm3toa_dan1horcrtwhl", "smrwallatck_test_r"),
    ],
}

PRESET_RELEASE_INFO = {
    "RVB_RED_COMBAT_RESTORED_5PACK - RELEASE STABLE": {
        "release_name": "SM3_RVB_RED_STABLE_5PACK_v1",
        "status": "CONFIRMED_STABLE",
        "risk": "LOW",
        "target_pack": "CH_SPIDERMAN.PCPACK",
        "notes": "Best first public preset. Real animation-changing preset only.",
    },
    "BLACK_SUIT_COMBAT_BETA - RELEASE": {
        "release_name": "SM3_BLACKSUIT_COMBAT_RESTORED_TEST_v1",
        "status": "PROMISING",
        "risk": "LOW_MEDIUM",
        "target_pack": "CH_BLACKSUIT.PCPACK",
        "notes": "Best black-suit combat result. Avoid sm3atckhf1 <- smbatckangleddivekick because it crashed.",
    },
    "SM2_MOVEMENT_RESTORE_PACK - EXPERIMENTAL RELEASE": {
        "release_name": "SM3_SM2_MOVEMENT_RESTORE_PACK_v1",
        "status": "EXPERIMENTAL",
        "risk": "MEDIUM",
        "target_pack": "CH_SPIDERMAN.PCPACK",
        "notes": "Experimental movement pack. Use separate from stable red 5-pack.",
    },
    "SWING_DIVE_COMPATIBILITY_TEST - SUBTLE RELEASE": {
        "release_name": "SM3_SWING_DIVE_COMPATIBILITY_TEST_v1",
        "status": "PROMISING_SUBTLE",
        "risk": "MEDIUM_EXPERIMENTAL",
        "target_pack": "CH_SPIDERMAN.PCPACK or test destination pack",
        "notes": "Best current swing/dive result but subtle; not a full swing overhaul.",
    },
    "SLOW_SWING_SAFE_TEST - RELEASE": {
        "release_name": "SM3_SLOW_SWING_LOOP_TEST_v1",
        "status": "SAFE_FIRST_SWING_TEST",
        "risk": "LOW_MEDIUM",
        "target_pack": "CH_SPIDERMAN.PCPACK",
        "notes": "Safe slow-swing loop family swap.",
    },
    "PETER_DEBUG_WALL_TEST_F - LAB RELEASE": {
        "release_name": "SM3_PETER_DEBUG_WALL_TEST_F_v1",
        "status": "LAB_ONLY",
        "risk": "MEDIUM_HIGH",
        "target_pack": "CH_PETER.PCPACK",
        "notes": "One-slot Peter debug wall test. Test alone.",
    },
    "PETER_DEBUG_WALL_TEST_L - LAB RELEASE": {
        "release_name": "SM3_PETER_DEBUG_WALL_TEST_L_v1",
        "status": "TOOL_PASS_LIKELY_SAFE",
        "risk": "MEDIUM_HIGH",
        "target_pack": "CH_PETER.PCPACK",
        "notes": "Tool PASS candidate. Do not batch with wall R because both use same destination slot.",
    },
    "PETER_DEBUG_WALL_TEST_R - LAB RELEASE": {
        "release_name": "SM3_PETER_DEBUG_WALL_TEST_R_v1",
        "status": "LAB_ONLY",
        "risk": "MEDIUM_HIGH",
        "target_pack": "CH_PETER.PCPACK",
        "notes": "Separate one-slot test from wall L.",
    },
}

RVB_RED_ONLY_REPORT_ONLY = [
    "rvbfootplantlaunch",
    "rvbwallplantlaunchl",
    "rvbwallplantlaunchr",
    "smrgndbncchglnch",
    "smrgndbnclnch",
    "smridlcrchjmpland",
    "smrjmpland",
    "smrjmplandstickit",
    "smrjmpsprint",
    "smrjmpsprintland",
]

UNSAFE_PAIR_NOTES = {
    ("sm3airwebyank", "smratcktorpedo"): "UNSAFE: crashed. Avoid web/yank destination for torpedo/combat payload.",
    ("sm3atck4le", "smratckturnaroundpunch"): "UNSTABLE: seemed safe then crashed.",
    ("sm3atckhf1", "smbatckangleddivekick"): "UNSAFE: crashed.",
}

# ============================================================
# v2.10 no-op / same-name preset patch guard
# ============================================================
def is_noop_same_name_pair(pair):
    """True when a preset row is PC name <- exact same source name.

    These rows are useful as reference/control rows, but they are NOT a real
    restored swap candidate. Patching only these can produce no visible change,
    so v2.10 blocks them from Apply/Patch workflows.
    """
    try:
        d, s = pair[0], pair[1]
    except Exception:
        return False
    return str(d).strip().lower() == str(s).strip().lower()


def split_real_and_reference_pairs(pairs):
    real = []
    reference = []
    for p in pairs or []:
        if is_noop_same_name_pair(p):
            reference.append(tuple(p))
        else:
            real.append(tuple(p))
    return real, reference


def preset_patchability_status(pairs):
    real, reference = split_real_and_reference_pairs(pairs)
    if reference and not real:
        return "REFERENCE_ONLY_NO_PATCH", real, reference
    if reference and real:
        return "MIXED_SKIPS_REFERENCE_ROWS", real, reference
    return "PATCHABLE_REAL_SWAPS", real, reference


# ============================================================
# v2.7 Peter preset test data
# ============================================================
PETER_PRESET_GROUPS = {
    "PETER DEBUG WALL F - one-slot lab only": {
        "pairs": [("sm3toa_dan3ht2crkscr", "smrwallatck_test_f")],
        "note": "High-value debug-only wall attack payload. Same-size PC slot found, but the PC destination name/family is not a natural Peter wall slot. Test one copy only.",
        "risk": "HIGH_RISK_LAB_ONLY",
    },
    "PETER DEBUG WALL L - one-slot lab only": {
        "pairs": [("sm3toa_dan1horcrtwhl", "smrwallatck_test_l")],
        "note": "High-value debug-only wall attack left payload. Shares the same PC destination slot as wall R, so never batch L and R together.",
        "risk": "HIGH_RISK_LAB_ONLY",
    },
    "PETER DEBUG WALL R - one-slot lab only": {
        "pairs": [("sm3toa_dan1horcrtwhl", "smrwallatck_test_r")],
        "note": "High-value debug-only wall attack right payload. Shares the same PC destination slot as wall L, so never batch L and R together.",
        "risk": "HIGH_RISK_LAB_ONLY",
    },
}


PETER_SIZE_DIFF_REPORT_ONLY = [
    "sm3atckfrt_lo2",
    "sm3atcklo",
    "sm3jmpchglnd",
    "sm3jmpfly",
    "sm3jmplnch",
    "sm3walk2run",
]

def peter_likely_used_by_normal_peter(name: str) -> bool:
    low = (name or "").lower()
    return (
        "peterface" in low
        or low.startswith("sm3pp")
        or "peter" in low
    )

def peter_unused_reason(name: str) -> str:
    low = (name or "").lower()
    if low.startswith("sm2") or "sm2" in low:
        return "SM2_LEFTOVER_PRESENT_IN_PC_PETER"
    if low.startswith("bs") or low.startswith("bsm") or "bs3" in low:
        return "BLACK_SUIT_LEFTOVER_PRESENT_IN_PC_PETER"
    if any(w in low for w in ["swing", "swg", "web", "wall", "climb", "crawl", "zip"]):
        return "SPIDER_TRAVERSAL_PRESENT_BUT_LIKELY_UNUSED_BY_PETER"
    if any(w in low for w in ["atck", "attack", "punch", "kick", "throw", "combat"]):
        return "COMBAT_PRESENT_BUT_LIKELY_UNUSED_BY_PETER"
    if any(w in low for w in ["jump", "jmp", "land", "fall", "dive", "launch", "lnch"]):
        return "JUMP_LAND_PRESENT_BUT_LIKELY_UNUSED_BY_PETER"
    if any(w in low for w in ["gob", "goblin", "bomb", "glider", "turbo"]):
        return "GOBLIN_OBJECT_PRESENT_BUT_LIKELY_UNUSED_BY_PETER"
    if any(w in low for w in ["scene", "cut", "cin", "mission", "boss"]):
        return "SCENE_CUTSCENE_PRESENT_IN_PC_PETER"
    return "OTHER_PRESENT_BUT_LIKELY_UNUSED_BY_PETER"


# ============================================================
# v2.2 Swing / Dive / Jump Lab data
# ============================================================
# These are PC destination slot names to test one-at-a-time. The tool
# does not add new names to the PC resource space. It keeps the PC slot
# and replaces only same-size/same-layout payload bytes from the Xbox/RVB side.
SWING_BLUE_TEXT_TEST_ORDER = [
    {
        "order": 1,
        "name": "sm3jmplnch",
        "label": "regular jump launch",
        "blue_text": "Launch:Jump:Layer_0",
        "risk": "FIRST TEST",
    },
    {
        "order": 2,
        "name": "sm3jmpchgland",
        "label": "normal jump landing",
        "blue_text": "Fall_Land:Layer_0",
        "risk": "FIRST TEST / MEDIUM",
    },
    {
        "order": 3,
        "name": "sm3swgrintroe",
        "label": "forward into swing",
        "blue_text": "Forward_to swing_right behind:Swing_Launch:Layer_0",
        "risk": "MEDIUM",
    },
    {
        "order": 4,
        "name": "sm3slowswing270",
        "label": "slow swing loop 270",
        "blue_text": "Swing_Slow:Swing:Layer_0",
        "risk": "MEDIUM",
    },
    {
        "order": 5,
        "name": "sm3slowswing360",
        "label": "slow swing loop 360",
        "blue_text": "Swing_Slow:Swing:Layer_0",
        "risk": "MEDIUM",
    },
    {
        "order": 6,
        "name": "sm3swgrlsa",
        "label": "swing exit to jump",
        "blue_text": "Exit:Jump:Layer_0",
        "risk": "HIGHER RISK",
    },
    {
        "order": 7,
        "name": "sm3swgrlsa2dive",
        "label": "swing exit into dive",
        "blue_text": "Swing_charge_Exit_Dive:Jump:Layer_0",
        "risk": "HIGH RISK",
    },
    {
        "order": 8,
        "name": "smjmpsprintchgland",
        "label": "headfirst dive landing",
        "blue_text": "Headfirst_Land:Fall_Land:Layer",
        "risk": "HIGH RISK",
    },
    {
        "order": 9,
        "name": "sm3swgmidrls",
        "label": "mid swing release",
        "blue_text": "Swing_idle_Exit_lowjump:Layer_0",
        "risk": "HIGH RISK",
    },
    {
        "order": 10,
        "name": "sm3swglowrls",
        "label": "low swing release",
        "blue_text": "Swing_idle_Exit_lowjump:Layer_0",
        "risk": "HIGH RISK",
    },
    {
        "order": 11,
        "name": "sm3jmpsprintchg",
        "label": "sprint charge jump",
        "blue_text": "Sprint_charge_jump:Launch:Jump:Layer_0",
        "risk": "HIGH RISK",
    },
]

SWING_EXTRA_SINGLE_TEST_SLOTS = [
    {
        "order": 101,
        "name": "sm3swgrlsb2dive",
        "label": "extra single test A - swing release B to dive",
        "blue_text": "PC resource-space screenshot test",
        "risk": "HIGH RISK / SINGLE TEST",
    },
    {
        "order": 102,
        "name": "sm3swgearlyrls2dive",
        "label": "extra single test B - early swing release to dive",
        "blue_text": "PC resource-space screenshot test",
        "risk": "HIGH RISK / SINGLE TEST",
    },
    {
        "order": 103,
        "name": "sm3jmpsprint2dive",
        "label": "extra single test C - sprint jump to dive",
        "blue_text": "PC resource-space screenshot test",
        "risk": "HIGH RISK / SINGLE TEST",
    },
    {
        "order": 104,
        "name": "bs3jmpchg2dive",
        "label": "black suit extra test D - jump charge to dive",
        "blue_text": "BLACK SUIT ONLY if loaded pack is CH_BLACKSUIT",
        "risk": "HIGH RISK / BLACK SINGLE TEST",
    },
    {
        "order": 105,
        "name": "bs3divefall",
        "label": "black suit extra test E - dive fall",
        "blue_text": "BLACK SUIT ONLY if loaded pack is CH_BLACKSUIT",
        "risk": "HIGH RISK / BLACK SINGLE TEST",
    },
]

RVB_RED_ONLY_AVOID_FIRST = [
    "rvbfootplantlaunch",
    "rvbwallplantlaunchl",
    "rvbwallplantlaunchr",
    "smrgndbncchglnch",
    "smrgndbnclnch",
    "smridlcrchjmpland",
    "smrjmpland",
    "smrjmplandstickit",
    "smrjmpsprint",
    "smrjmpsprintland",
]

SWING_LAB_FILTER_WORDS = [
    "swg", "swing", "slow", "jmp", "jump", "dive", "fall", "land",
    "launch", "lnch", "rls", "release", "wall", "plant", "foot", "sprint", "chg", "charge",
]


def components_text(entry) -> str:
    if not entry:
        return ""
    return "/".join(map(str, entry.component_sizes))


def is_swing_lab_name(name: str) -> bool:
    low = (name or "").lower()
    return any(w in low for w in SWING_LAB_FILTER_WORDS)


def swing_lab_test_order(include_extra=True):
    rows = list(SWING_BLUE_TEXT_TEST_ORDER)
    if include_extra:
        rows += list(SWING_EXTRA_SINGLE_TEST_SLOTS)
    return rows



def swing_group_set(name: str) -> set:
    """Broad swing/jump/dive family buckets for v2.2 candidate discovery."""
    low = (name or "").lower()
    groups = set()
    if any(k in low for k in ["slowswing", "slow_swing", "slow"]):
        groups.add("slow_swing_loop")
    if any(k in low for k in ["swgrls", "rls", "release", "chgrls"]):
        groups.add("swing_release")
    if any(k in low for k in ["swg", "swing", "webswing"]):
        groups.add("swing")
    if any(k in low for k in ["2dive", "dive", "divefall"]):
        groups.add("dive")
    if any(k in low for k in ["jmpland", "land", "fall_land", "fall"]):
        groups.add("landing")
    if any(k in low for k in ["jmplnch", "lnch", "launch"]):
        groups.add("launch")
    if any(k in low for k in ["jmpsprint", "sprint"]):
        groups.add("sprint_jump")
    if any(k in low for k in ["jmp", "jump"]):
        groups.add("jump")
    if any(k in low for k in ["wall", "plant", "footplant"]):
        groups.add("wall_footplant")
    if any(k in low for k in ["gndbnc", "bounce", "bnc"]):
        groups.add("ground_bounce")
    return groups or {"other"}


def swing_group_text(name: str) -> str:
    return ",".join(sorted(swing_group_set(name)))


def swing_lab_risk_for_pair(dest_name: str, src_name: str) -> str:
    combined = (dest_name + " " + src_name).lower()
    if any(k in combined for k in ["wallplant", "footplant", "wall", "gndbnc", "noanchor", "hang", "climb"]):
        return "HIGH-RISK LAB ONLY"
    if any(k in combined for k in ["swgrls", "chgrls", "rls2dive", "2dive", "divefall", "jmpsprint"]):
        return "HIGH-RISK ONE-SLOT"
    if any(k in combined for k in ["slowswing", "slow_swing"]):
        return "PROMISING SLOW-SWING"
    if any(k in combined for k in ["jmplnch", "jmpchgland", "jmpland"]):
        return "MEDIUM JUMP/LAND"
    return "MANUAL ONE-SLOT"


def source_text_matches_filter(entry, text_filter: str) -> bool:
    q = (text_filter or "").strip().lower()
    if not q:
        return True
    hay = f"{entry.display_name} {hex32(entry.filename_hash)} {components_text(entry)}".lower()
    return all(part in hay for part in q.split())


def candidate_mode_allows(mode: str, dest_entry, src_entry, exact: bool, family_overlap: bool, source_group: set, dest_group: set) -> bool:
    mode = (mode or "STRICT_SAFE").upper()
    if mode == "STRICT_SAFE":
        # v2.1-style safe lane: exact names first, plus very close slow-swing/same-family loop matches.
        if exact:
            return True
        close_loop = ("slow_swing_loop" in source_group and "slow_swing_loop" in dest_group)
        same_core = bool(source_group & dest_group & {"swing_release", "dive", "jump", "landing", "launch", "sprint_jump"})
        return close_loop or same_core
    if mode == "FAMILY_MATCH":
        return family_overlap
    if mode == "STRONG_VISIBLE":
        return bool(source_group & {"swing_release", "dive", "swing", "slow_swing_loop"}) or bool(dest_group & {"swing_release", "dive", "swing", "slow_swing_loop"})
    if mode == "RISKY_REPORT_ONLY":
        risky = {"wall_footplant", "ground_bounce", "launch", "swing_release", "dive", "sprint_jump"}
        return bool((source_group | dest_group) & risky)
    if mode == "SAME_SIZE_ANY_NAME":
        return True
    return True


def swing_source_candidates_for_dest(src_pack, dest_entry, limit: int = 200, mode: str = "STRICT_SAFE", text_filter: str = ""):
    """Return same-size/same-layout source candidates for one PC destination slot.

    v2.2 keeps patch safety strict: every candidate must still pass component-size/layout validation.
    The mode only controls how wide the discovery list is.
    """
    rows = []
    if not src_pack or not dest_entry:
        return rows
    dest_groups = swing_group_set(dest_entry.display_name)
    for s in src_pack.anim_files:
        if s.pack_kind == "XEPACK_RAW_STRING_SCAN":
            continue
        if not src_pack.combined_blob(s):
            continue
        if not source_text_matches_filter(s, text_filter):
            continue
        ok, reason = same_size_ok(s, dest_entry, True)
        if not ok:
            continue
        exact = s.display_name.lower() == dest_entry.display_name.lower()
        src_groups = swing_group_set(s.display_name)
        family_overlap = bool(src_groups & dest_groups)
        if not candidate_mode_allows(mode, dest_entry, s, exact, family_overlap, src_groups, dest_groups):
            continue
        score = family_score(dest_entry.display_name, s.display_name, dest_entry.filename_hash, s.filename_hash)
        if exact:
            score += 10000
        if family_overlap:
            score += 2000
        if "slow_swing_loop" in src_groups and "slow_swing_loop" in dest_groups:
            score += 1500
        if "swing_release" in src_groups and "dive" in dest_groups:
            score += 600
        if "dive" in src_groups and "dive" in dest_groups:
            score += 800
        # Known current best/subtle results get lifted to the top when present.
        if dest_entry.display_name.lower() == "sm3jmpsprint2dive" and s.display_name.lower() == "bs3swgchgrls2dive":
            score += 25000
        if dest_entry.display_name.lower() == "sm3slowswing270" and s.display_name.lower() == "sm3slowswing180":
            score += 20000
        rows.append({
            "source_name": s.display_name,
            "source_hash": hex32(s.filename_hash),
            "source_size": s.total_size,
            "source_components": components_text(s),
            "source_groups": ",".join(sorted(src_groups)),
            "dest_name": dest_entry.display_name,
            "dest_hash": hex32(dest_entry.filename_hash),
            "dest_size": dest_entry.total_size,
            "dest_components": components_text(dest_entry),
            "dest_groups": ",".join(sorted(dest_groups)),
            "exact_name": "YES" if exact else "NO",
            "family_match": "YES" if family_overlap else "NO",
            "candidate_mode": mode,
            "score": score,
            "risk_label": swing_lab_risk_for_pair(dest_entry.display_name, s.display_name),
            "validation": reason,
            "source_safety": detailed_anim_safety(s.display_name),
            "candidate_note": "CURRENT BEST SUBTLE RESULT" if (dest_entry.display_name.lower() == "sm3jmpsprint2dive" and s.display_name.lower() == "bs3swgchgrls2dive") else ("SAFE SLOW-SWING RESULT" if (dest_entry.display_name.lower() == "sm3slowswing270" and s.display_name.lower() == "sm3slowswing180") else ("EXACT SAME-NAME FIRST" if exact else "manual candidate; test one copy only")),
        })
    rows.sort(key=lambda r: (-int(r["candidate_note"].startswith("CURRENT BEST")), -int(r["candidate_note"].startswith("SAFE SLOW")), -int(r["exact_name"] == "YES"), -int(r["family_match"] == "YES"), -int(r["score"]), r["source_name"].lower()))
    return rows[:limit]


def make_swing_lab_row_from_dest(dest_entry, src_pack, order: int, label: str = "PC swing/dive/jump slot", risk: str = "MANUAL ONE-SLOT", blue_text: str = "v2.2 generated target", candidate_mode: str = "STRICT_SAFE", text_filter: str = ""):
    candidates = swing_source_candidates_for_dest(src_pack, dest_entry, limit=500, mode=candidate_mode, text_filter=text_filter)
    src_by_name = {s.display_name.lower(): s for s in src_pack.anim_files}
    s = src_by_name.get(dest_entry.display_name.lower())
    same_name_status = "NO SAME-NAME SOURCE"
    same_name_validation = ""
    same_name_patchable = "NO"
    if s:
        if s.pack_kind == "XEPACK_RAW_STRING_SCAN":
            same_name_status = "SOURCE NAME-ONLY; NOT PATCHABLE"
        elif not src_pack.combined_blob(s):
            same_name_status = "SOURCE BYTES MISSING"
        else:
            ok, reason = same_size_ok(s, dest_entry, True)
            same_name_status = "PATCHABLE" if ok else "SIZE/LAYOUT MISMATCH"
            same_name_validation = reason
            same_name_patchable = "YES" if ok else "NO"
    return {
        "order": order,
        "pc_destination_name": dest_entry.display_name,
        "label": label,
        "blue_text_context": blue_text,
        "risk": risk,
        "target_groups": swing_group_text(dest_entry.display_name),
        "dest_exists": "YES",
        "dest_hash": hex32(dest_entry.filename_hash),
        "dest_size": dest_entry.total_size,
        "dest_components": components_text(dest_entry),
        "same_name_source_exists": "YES" if s else "NO",
        "same_name_source_hash": hex32(s.filename_hash) if s else "",
        "same_name_source_size": s.total_size if s else "",
        "same_name_source_components": components_text(s) if s else "",
        "same_name_patchable": same_name_patchable,
        "same_name_status": same_name_status,
        "same_name_validation": same_name_validation,
        "same_size_candidate_count": len(candidates),
        "best_candidate_source": candidates[0]["source_name"] if candidates else "",
        "best_candidate_validation": candidates[0]["validation"] if candidates else "",
        "best_candidate_note": candidates[0]["candidate_note"] if candidates else "",
    }


def build_swing_lab_rows(dest_pack, src_pack, target_mode: str = "GUIDED_ORDER", candidate_mode: str = "STRICT_SAFE", text_filter: str = ""):
    dest_by_name = {d.display_name.lower(): d for d in dest_pack.anim_files}
    src_by_name = {s.display_name.lower(): s for s in src_pack.anim_files}
    rows = []
    target_mode = (target_mode or "GUIDED_ORDER").upper()

    if target_mode == "PROMISING_RESULTS":
        promising = [
            {"order": 1, "name": "sm3jmpsprint2dive", "label": "CURRENT BEST: subtle compatible swing/dive result", "blue_text": "tested: sm3jmpsprint2dive <- bs3swgchgrls2dive", "risk": "PROMISING / SUBTLE / ONE-SLOT"},
            {"order": 2, "name": "sm3slowswing270", "label": "SAFE SLOW-SWING LOOP RESULT", "blue_text": "tested: sm3slowswing270 <- sm3slowswing180", "risk": "PROMISING SLOW-SWING"},
            {"order": 3, "name": "sm3slowswing360", "label": "slow swing loop 360", "blue_text": "Swing_Slow:Swing:Layer_0", "risk": "MEDIUM"},
            {"order": 4, "name": "bs3jmpchg2dive", "label": "black suit jump charge to dive", "blue_text": "BLACK SUIT SINGLE TEST", "risk": "HIGH RISK / BLACK SINGLE TEST"},
            {"order": 5, "name": "bs3divefall", "label": "black suit dive fall", "blue_text": "BLACK SUIT SINGLE TEST", "risk": "HIGH RISK / BLACK SINGLE TEST"},
        ]
        items = promising
    elif target_mode == "ALL_SWING_PC_SLOTS":
        order = 1000
        for d in dest_pack.anim_files:
            if is_swing_lab_name(d.display_name):
                rows.append(make_swing_lab_row_from_dest(d, src_pack, order, "all PC swing/jump/dive slot", detailed_anim_safety(d.display_name), "v2.2 all PC slots", candidate_mode, text_filter))
                order += 1
        rows.sort(key=lambda r: (-int(r["same_size_candidate_count"]), r["risk"], r["pc_destination_name"].lower()))
        return rows
    elif target_mode == "COMPATIBLE_ONLY":
        order = 2000
        for d in dest_pack.anim_files:
            cands = swing_source_candidates_for_dest(src_pack, d, limit=2, mode=candidate_mode, text_filter=text_filter)
            if cands:
                label = "compatible PC slot"
                if is_swing_lab_name(d.display_name):
                    label = "compatible swing/jump/dive PC slot"
                rows.append(make_swing_lab_row_from_dest(d, src_pack, order, label, detailed_anim_safety(d.display_name), "v2.2 compatible-only list", candidate_mode, text_filter))
                order += 1
        rows.sort(key=lambda r: (-int(r["same_size_candidate_count"]), -int(is_swing_lab_name(r["pc_destination_name"])), r["pc_destination_name"].lower()))
        return rows
    else:
        items = swing_lab_test_order(include_extra=True)

    for item in items:
        name = item["name"]
        d = dest_by_name.get(name.lower())
        s = src_by_name.get(name.lower())
        same_name_status = "NO SAME-NAME SOURCE"
        same_name_validation = ""
        same_name_patchable = "NO"
        candidate_count = 0
        best_candidate = ""
        best_candidate_validation = ""
        best_candidate_note = ""
        if d:
            candidates = swing_source_candidates_for_dest(src_pack, d, limit=500, mode=candidate_mode, text_filter=text_filter)
            candidate_count = len(candidates)
            if candidates:
                best_candidate = candidates[0]["source_name"]
                best_candidate_validation = candidates[0]["validation"]
                best_candidate_note = candidates[0].get("candidate_note", "")
        if d and s:
            if s.pack_kind == "XEPACK_RAW_STRING_SCAN":
                same_name_status = "SOURCE NAME-ONLY; NOT PATCHABLE"
            elif not src_pack.combined_blob(s):
                same_name_status = "SOURCE BYTES MISSING"
            else:
                ok, reason = same_size_ok(s, d, True)
                same_name_status = "PATCHABLE" if ok else "SIZE/LAYOUT MISMATCH"
                same_name_validation = reason
                same_name_patchable = "YES" if ok else "NO"
        elif not d:
            same_name_status = "PC DESTINATION SLOT MISSING"
        rows.append({
            "order": item["order"],
            "pc_destination_name": name,
            "label": item["label"],
            "blue_text_context": item["blue_text"],
            "risk": item["risk"],
            "target_groups": swing_group_text(name),
            "dest_exists": "YES" if d else "NO",
            "dest_hash": hex32(d.filename_hash) if d else "",
            "dest_size": d.total_size if d else "",
            "dest_components": components_text(d) if d else "",
            "same_name_source_exists": "YES" if s else "NO",
            "same_name_source_hash": hex32(s.filename_hash) if s else "",
            "same_name_source_size": s.total_size if s else "",
            "same_name_source_components": components_text(s) if s else "",
            "same_name_patchable": same_name_patchable,
            "same_name_status": same_name_status,
            "same_name_validation": same_name_validation,
            "same_size_candidate_count": candidate_count,
            "best_candidate_source": best_candidate,
            "best_candidate_validation": best_candidate_validation,
            "best_candidate_note": best_candidate_note,
        })
    return rows

def build_rvb_red_only_avoid_rows(dest_pack, src_pack):
    src_by_name = {s.display_name.lower(): s for s in src_pack.anim_files}
    rows = []
    for name in RVB_RED_ONLY_AVOID_FIRST:
        s = src_by_name.get(name.lower())
        slot_count = 0
        best_dest = ""
        best_validation = ""
        if s and s.pack_kind != "XEPACK_RAW_STRING_SCAN" and src_pack.combined_blob(s):
            slots = compatible_dest_slots_for_source(dest_pack, s)
            slot_count = len(slots)
            if slots:
                best_dest = slots[0]["dest_name"]
                best_validation = slots[0]["validation"]
        rows.append({
            "rvb_red_only_source": name,
            "source_exists_in_loaded_rvb": "YES" if s else "NO",
            "source_hash": hex32(s.filename_hash) if s else "",
            "source_size": s.total_size if s else "",
            "source_components": components_text(s) if s else "",
            "compatible_pc_slot_count": slot_count,
            "best_pc_slot_candidate": best_dest,
            "best_validation": best_validation,
            "status": "AVOID FIRST / LAB ONLY / not direct PC name",
        })
    return rows


def build_same_name_family_matches(dest_pack, src_pack, family: str):
    """Same-name + same-component-size family match list.

    This is intentionally strict. It does NOT use RVB-only names because those
    need manual compatible-slot choice.
    """
    dest_by_name = {d.display_name.lower(): d for d in dest_pack.anim_files}
    rows = []
    pairs = []
    for s in src_pack.anim_files:
        if s.pack_kind == "XEPACK_RAW_STRING_SCAN":
            continue
        if not anim_in_family(s.display_name, family):
            continue
        d = dest_by_name.get(s.display_name.lower())
        if not d:
            continue
        ok, reason = same_size_ok(s, d, True)
        if not ok:
            rows.append({
                "will_patch": False,
                "reason": reason,
                "family": family,
                "name": s.display_name,
                "source_hash": hex32(s.filename_hash),
                "dest_hash": hex32(d.filename_hash),
                "source_size": s.total_size,
                "dest_size": d.total_size,
                "source_components": "/".join(map(str, s.component_sizes)),
                "dest_components": "/".join(map(str, d.component_sizes)),
                "safety": detailed_anim_safety(s.display_name),
            })
            continue
        if not src_pack.combined_blob(s):
            rows.append({
                "will_patch": False,
                "reason": "source bytes unavailable",
                "family": family,
                "name": s.display_name,
                "source_hash": hex32(s.filename_hash),
                "dest_hash": hex32(d.filename_hash),
                "source_size": s.total_size,
                "dest_size": d.total_size,
                "source_components": "/".join(map(str, s.component_sizes)),
                "dest_components": "/".join(map(str, d.component_sizes)),
                "safety": detailed_anim_safety(s.display_name),
            })
            continue
        rows.append({
            "will_patch": True,
            "reason": reason,
            "family": family,
            "name": s.display_name,
            "source_hash": hex32(s.filename_hash),
            "dest_hash": hex32(d.filename_hash),
            "source_size": s.total_size,
            "dest_size": d.total_size,
            "source_components": "/".join(map(str, s.component_sizes)),
            "dest_components": "/".join(map(str, d.component_sizes)),
            "safety": detailed_anim_safety(s.display_name),
        })
        pairs.append((d, s))
    rows.sort(key=lambda r: (not r["will_patch"], r["safety"], r["name"].lower()))
    return pairs, rows



def patch_pc_anim_copy_many(dest_pack, source_pack, pairs, output, strict_components=True, allow_x360_source=False):
    """Patch multiple selected destination/source ANIM pairs into one new PC PCPACK copy."""
    if dest_pack.platform != "PC":
        raise ValueError("Destination must be a PC PCPACK. This tool never patches Xbox packs.")
    if source_pack.platform != "PC":
        if not allow_x360_source or source_pack.platform != "X360":
            raise ValueError("Source must be PC, or X360 with Xbox/RVB patch mode enabled.")

    out_data = bytearray(dest_pack.data)
    logs = []
    used_ranges = []

    for pair_index, (dest, src) in enumerate(pairs, start=1):
        if source_pack.platform == "X360":
            if src.pack_kind == "XEPACK_RAW_STRING_SCAN":
                raise ValueError(f"{src.display_name}: cannot patch from name-only string-scan entry.")
            if not source_pack.combined_blob(src):
                raise ValueError(f"{src.display_name}: source payload bytes unavailable.")

        ok, reason = same_size_ok(src, dest, strict_components)
        if not ok:
            raise ValueError(f"Pair {pair_index} failed: {dest.display_name} <- {src.display_name}: {reason}")

        pair_log = {
            "pair_index": pair_index,
            "dest_slot_kept": dest.display_name,
                "source_payload_from": src.display_name,
                "dest_component_sizes": dest.component_sizes,
            "source_component_sizes": src.component_sizes,
            "validation": reason,
            "components": [],
        }

        for ci in range(dest.component_count):
            d_s, d_e = dest.component_offsets[ci]
            d_abs_s = dest.source_outer_offset + d_s
            d_abs_e = dest.source_outer_offset + d_e
            for os_, oe_, oname in used_ranges:
                if not (d_abs_e <= os_ or d_abs_s >= oe_):
                    raise ValueError(f"Patch overlap: {dest.display_name} overlaps previous patch {oname}")
            src_blob = source_pack.component_blob(src, ci)
            if not src_blob:
                raise ValueError(f"{src.display_name}: source component {ci} bytes unavailable.")
            old = bytes(out_data[d_abs_s:d_abs_e])
            if len(src_blob) != len(old):
                raise ValueError(f"{dest.display_name}: component {ci} length mismatch source={len(src_blob)} dest={len(old)}")

            out_data[d_abs_s:d_abs_e] = src_blob
            used_ranges.append((d_abs_s, d_abs_e, dest.display_name))
            pair_log["components"].append({
                "component": ci,
                "dest_offset": hex(d_abs_s),
                "size": len(src_blob),
                "changed": old != src_blob,
            })
        logs.append(pair_log)

    output.write_bytes(bytes(out_data))
    log = {
        "tool": "SM3_PC_RVB_TO_PC_ANIM_SWAP_TEST_v2_4",
        "mode": "MULTI_RVB_X360_TO_PC_PATCH" if source_pack.platform == "X360" else "MULTI_PC_TO_PC_PATCH",
        "warning": "Experimental. Same-size/component-size validation only; state logic may still crash.",
        "dest_pack": str(dest_pack.path),
        "source_pack": str(source_pack.path),
        "output": str(output),
        "pair_count": len(pairs),
        "pairs": logs,
    }
    (output.parent / (output.stem + "_MULTI_ANIM_SWAP_LOG.json")).write_text(json.dumps(log, indent=2), encoding="utf-8")
    write_csv(output.parent / (output.stem + "_MULTI_ANIM_SWAP_PAIRS.csv"), [
        {
            "pair_index": p["pair_index"],
            "pc_destination": p["dest_slot_kept"],
            "source_payload": p["source_payload_from"],
            "dest_components": "/".join(map(str, p["dest_component_sizes"])),
            "source_components": "/".join(map(str, p["source_component_sizes"])),
            "validation": p["validation"],
        } for p in logs
    ])
    return log


def patch_family_same_name_copy(dest_pack, src_pack, pairs, output: Path, family: str):
    """Patch many same-name/same-size ANIM pairs into one NEW PC PCPACK copy."""
    if dest_pack.platform != "PC":
        raise ValueError("Destination must be PC.")
    if src_pack.platform != "X360":
        raise ValueError("Source must be Xbox/RVB extracted output.")

    out_data = bytearray(dest_pack.data)
    records = []

    for dest, src in pairs:
        ok, reason = same_size_ok(src, dest, True)
        if not ok:
            raise ValueError(f"{src.display_name}: {reason}")
        for ci in range(dest.component_count):
            d_s, d_e = dest.component_offsets[ci]
            d_abs_s = dest.source_outer_offset + d_s
            d_abs_e = dest.source_outer_offset + d_e
            src_blob = src_pack.component_blob(src, ci)
            if not src_blob:
                raise ValueError(f"{src.display_name}: source component {ci} bytes unavailable")
            old = bytes(out_data[d_abs_s:d_abs_e])
            if len(src_blob) != len(old):
                raise ValueError(f"{src.display_name}: component {ci} length mismatch")
            out_data[d_abs_s:d_abs_e] = src_blob
            records.append({
                "family": family,
                "name": dest.display_name,
                "dest_hash": hex32(dest.filename_hash),
                        "component": ci,
                "dest_offset": hex(d_abs_s),
                "size": len(src_blob),
                "changed": old != src_blob,
            })

    output.write_bytes(bytes(out_data))
    log = {
        "tool": "SM3_PC_RVB_TO_PC_ANIM_SWAP_TEST_v2_4",
        "mode": f"AUTO_REPLACE_{family.upper()}_FAMILY_SAME_NAME_SAME_SIZE",
        "warning": "Experimental. Same-name and same-size only, but gameplay state can still crash.",
        "dest_pack": str(dest_pack.path),
        "source_pack": str(src_pack.path),
        "output": str(output),
        "family": family,
        "patched_animation_count": len(pairs),
        "component_patch_count": len(records),
        "records": records,
    }
    output.with_suffix(output.suffix + f".{family.upper()}_FAMILY_SWAP_LOG.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log



def compatible_dest_slots_for_source(dest_pack, source_entry):
    rows = []
    for d in dest_pack.anim_files:
        ok, reason = same_size_ok(source_entry, d, True)
        if not ok:
            continue
        same_name = d.display_name.lower() == source_entry.display_name.lower()
        rows.append({
            "dest_name": d.display_name,
            "dest_hash": hex32(d.filename_hash),
            "dest_size": d.total_size,
            "dest_components": "/".join(map(str, d.component_sizes)),
            "source_name": source_entry.display_name,
            "source_hash": hex32(source_entry.filename_hash),
            "source_size": source_entry.total_size,
            "source_components": "/".join(map(str, source_entry.component_sizes)),
            "same_name": same_name,
            "candidate_role": "SAME_NAME_REFERENCE_CONTROL_NOT_A_NEW_SWAP" if same_name else "DISTINCT_SOURCE_PAYLOAD_CANDIDATE",
            "v2_8_note": "Exact same-name source/dest. Useful as control only; not a new candidate fallback." if same_name else "Different source payload candidate. Manual one-slot test only.",
            "dest_safety": detailed_anim_safety(d.display_name),
            "source_safety": detailed_anim_safety(source_entry.display_name),
            "family_score": family_score(d.display_name, source_entry.display_name, d.filename_hash, source_entry.filename_hash),
            "validation": reason,
        })
    # v2.8: sort real/different-source candidates before exact same-name controls.
    rows.sort(key=lambda r: (int(str(r.get("candidate_role", "")).startswith("SAME_NAME")), -r["family_score"], r["dest_safety"], r["dest_name"]))
    return rows




PETER_DEBUG_IMPORTANT_WORDS = [
    "peter", "ptr", "park", "goblin", "gob", "gbln", "playergoblin", "glider", "pumpkin", "bomb", "walk", "run", "idle", "crch", "crouch", "jump", "jmp", "land",
    "fall", "turn", "dodge", "hit", "hurt", "pain", "knock", "getup", "combat", "atck", "atk",
    "web", "swing", "swg", "wall", "climb", "crawl", "talk", "phone", "cut", "scene"
]

PETER_DEBUG_RISKY_WORDS = [
    "scene", "cut", "boss", "mission", "script", "cin", "camera", "web", "swing", "swg", "wall", "climb", "crawl", "glider", "fly"
]


def peter_debug_family_label(name: str) -> str:
    low = (name or "").lower()
    if any(w in low for w in ["idle", "idl"]):
        return "IDLE"
    if any(w in low for w in ["walk", "run", "sprint"]):
        return "LOCOMOTION"
    if any(w in low for w in ["jump", "jmp", "land", "fall"]):
        return "JUMP_LAND_FALL"
    if any(w in low for w in ["hit", "hurt", "pain", "knock", "getup", "stun"]):
        return "HIT_REACTION"
    if any(w in low for w in ["combat", "atck", "atk", "punch", "kick", "throw"]):
        return "COMBAT"
    if any(w in low for w in ["swing", "swg", "web", "wall", "climb", "crawl"]):
        return "SPIDER_TRAVERSAL"
    if any(w in low for w in ["glider", "pumpkin", "bomb", "gob", "goblin", "fly"]):
        return "GOBLIN_ACTION"
    if any(w in low for w in ["talk", "phone", "photo", "camera"]):
        return "PETER_CIVILIAN_ACTION"
    if any(w in low for w in ["scene", "cut", "cin", "mission", "boss"]):
        return "SCENE_CUTSCENE"
    return "OTHER"


def peter_debug_safety(dest_name: str, src_name: str, validation: str, same_name: bool) -> str:
    dn = (dest_name or "").lower()
    sn = (src_name or "").lower()
    combo = dn + " " + sn
    if "mismatch" in (validation or "").lower():
        return "REPORT_ONLY_SIZE_OR_LAYOUT_DIFF"
    if any(w in combo for w in ["scene", "cut", "cin", "boss", "mission", "script"]):
        return "HIGH_RISK_SCENE_ONLY"
    if any(w in combo for w in ["swing", "swg", "web", "wall", "climb", "crawl"]):
        return "HIGH_RISK_TRAVERSAL"
    if same_name and any(w in combo for w in ["idle", "idl", "walk", "run", "turn"]):
        return "FIRST_TEST_CIVILIAN_SAFE"
    if same_name:
        return "FIRST_TEST_SAME_NAME"
    if peter_debug_family_label(dest_name) == peter_debug_family_label(src_name):
        return "MEDIUM_TEST_FAMILY_MATCH"
    return "MANUAL_REVIEW"


def peter_entry_row(prefix: str, e):
    return {
        f"{prefix}_platform": e.platform,
        f"{prefix}_pack_kind": e.pack_kind,
        f"{prefix}_name": e.display_name,
        f"{prefix}_hash": hex32(e.filename_hash),
        f"{prefix}_size": e.total_size,
        f"{prefix}_component_count": e.component_count,
        f"{prefix}_components": "/".join(map(str, e.component_sizes)),
        f"{prefix}_family": peter_debug_family_label(e.display_name),
        f"{prefix}_hint": match_known_hint(e.display_name),
        f"{prefix}_global_index": e.global_index,
        f"{prefix}_pack_path": e.pack_path,
    }


def build_peter_debug_reports(pc_pack, debug_pack):
    """Build Peter-vs-debug-Peter style reports from any two loaded packs.

    Pack A is usually the PC destination CH_PETER.PCPACK.
    Pack B is usually debug/X360/RVB Peter extracted output.
    If one side is detected as PC and the other X360, this function keeps PC as destination.
    """
    if pc_pack.platform != "PC" and debug_pack.platform == "PC":
        pc_pack, debug_pack = debug_pack, pc_pack
    pc_anims = list(pc_pack.anim_files)
    dbg_anims = list(debug_pack.anim_files)
    pc_by_name = {e.display_name.lower(): e for e in pc_anims}
    dbg_by_name = {e.display_name.lower(): e for e in dbg_anims}
    all_names = sorted(set(pc_by_name) | set(dbg_by_name))

    matrix = []
    shared = []
    same_size_same_layout = []
    size_or_layout_diff = []
    pc_only = []
    debug_only = []
    high_value_debug_only = []

    for name in all_names:
        p = pc_by_name.get(name)
        d = dbg_by_name.get(name)
        row = {
            "name": name,
            "pc_present": p is not None,
            "debug_present": d is not None,
            "pc_size": p.total_size if p else "",
            "debug_size": d.total_size if d else "",
            "pc_components": "/".join(map(str, p.component_sizes)) if p else "",
            "debug_components": "/".join(map(str, d.component_sizes)) if d else "",
            "family": peter_debug_family_label(name),
            "pc_hash": hex32(p.filename_hash) if p else "",
            "debug_hash": hex32(d.filename_hash) if d else "",
        }
        if p and d:
            ok, reason = same_size_ok(d, p, True)
            row["same_size_same_layout"] = ok
            row["validation"] = reason
            row["safety"] = peter_debug_safety(p.display_name, d.display_name, reason, True)
            shared.append({**peter_entry_row("pc", p), **peter_entry_row("debug", d), "same_name": True, "validation": reason, "safety": row["safety"]})
            if ok:
                same_size_same_layout.append(shared[-1])
            else:
                size_or_layout_diff.append(shared[-1])
        elif p:
            row["same_size_same_layout"] = False
            row["validation"] = "missing from debug side"
            row["safety"] = "PC_ONLY_REFERENCE"
            pc_only.append(peter_entry_row("pc", p))
        elif d:
            row["same_size_same_layout"] = False
            row["validation"] = "missing from PC side; not directly callable by retail PC name"
            row["safety"] = "DEBUG_ONLY_NOT_DIRECT_PC_NAME"
            drow = peter_entry_row("debug", d)
            drow["note"] = "Debug-only name. Use as source payload only if injected into an existing same-size PC destination slot."
            debug_only.append(drow)
            lname = d.display_name.lower()
            if any(w in lname for w in PETER_DEBUG_IMPORTANT_WORDS):
                high_value_debug_only.append(drow)
        matrix.append(row)

    # PC-present but likely unused-by-normal-Peter report.
    # This is the user's key distinction: the resource exists in PC CH_PETER.PCPACK,
    # but normal Peter gameplay/state logic probably does not call it.
    pc_present_but_likely_unused = []
    pc_unused_combat = []
    pc_unused_traversal = []
    pc_unused_sm2 = []
    pc_unused_bs3 = []
    pc_likely_used_by_peter = []
    for p in pc_anims:
        base = peter_entry_row("pc", p)
        base["present_in_pc_resource_space"] = True
        base["likely_used_by_normal_peter"] = peter_likely_used_by_normal_peter(p.display_name)
        base["unused_reason"] = "LIKELY_USED_BY_NORMAL_PETER" if base["likely_used_by_normal_peter"] else peter_unused_reason(p.display_name)
        if base["likely_used_by_normal_peter"]:
            pc_likely_used_by_peter.append(base)
        else:
            pc_present_but_likely_unused.append(base)
            reason = base["unused_reason"]
            if "COMBAT" in reason:
                pc_unused_combat.append(base)
            if "TRAVERSAL" in reason or "JUMP_LAND" in reason:
                pc_unused_traversal.append(base)
            if "SM2" in reason:
                pc_unused_sm2.append(base)
            if "BLACK_SUIT" in reason:
                pc_unused_bs3.append(base)

    # Same-size slot candidates, not limited to same name.
    slot_candidates = []
    for d in dbg_anims:
        for p in pc_anims:
            ok, reason = same_size_ok(d, p, True)
            if not ok:
                continue
            same_name = d.display_name.lower() == p.display_name.lower()
            same_family = peter_debug_family_label(d.display_name) == peter_debug_family_label(p.display_name)
            # Keep all exact/same-family/important rows. For random same-size rows, keep them but with lower score.
            score = family_score(p.display_name, d.display_name, p.filename_hash, d.filename_hash)
            if same_name:
                score += 100
            if same_family:
                score += 25
            row = {**peter_entry_row("pc_dest", p), **peter_entry_row("debug_source", d)}
            row.update({
                "same_name": same_name,
                "same_family": same_family,
                "family_score": score,
                "validation": reason,
                "safety": peter_debug_safety(p.display_name, d.display_name, reason, same_name),
                "patch_note": "One-slot test only. PC keeps destination name; debug/Peter source supplies payload bytes.",
            })
            slot_candidates.append(row)
    slot_candidates.sort(key=lambda r: (
        0 if r.get("safety") in ("FIRST_TEST_CIVILIAN_SAFE", "FIRST_TEST_SAME_NAME") else 1,
        0 if r.get("same_name") else 1,
        0 if r.get("same_family") else 1,
        -int(r.get("family_score", 0)),
        r.get("pc_dest_name", "")
    ))

    # v2.8 bug fix:
    # Do NOT treat an exact same-name row as a replacement candidate fallback.
    # Same-name rows are useful controls/references, but when the user asks to "find a candidate"
    # they usually need a DIFFERENT source payload. If no different source exists, say that clearly
    # instead of duplicating the PC name on both sides.
    same_name_reference_controls = []
    distinct_source_slot_candidates = []
    for r in slot_candidates:
        if r.get("same_name"):
            r["candidate_role"] = "SAME_NAME_REFERENCE_CONTROL_NOT_A_NEW_SWAP"
            r["v2_8_note"] = "Exact same-name exists on both sides. This is a control/reference row, not a replacement-candidate fallback."
            same_name_reference_controls.append(r)
        else:
            r["candidate_role"] = "DISTINCT_SOURCE_PAYLOAD_CANDIDATE"
            r["v2_8_note"] = "Different source payload. Use one-slot test only after manual review."
            distinct_source_slot_candidates.append(r)

    first_tests = [r for r in distinct_source_slot_candidates if r.get("safety") in ("FIRST_TEST_CIVILIAN_SAFE", "FIRST_TEST_SAME_NAME")]
    # keep exact same-name controls separate so they don't pollute the real-candidate list
    same_name_first_test_controls = [r for r in same_name_reference_controls if r.get("safety") in ("FIRST_TEST_CIVILIAN_SAFE", "FIRST_TEST_SAME_NAME")]
    family_tests = [r for r in distinct_source_slot_candidates if r.get("safety") == "MEDIUM_TEST_FAMILY_MATCH"]
    risky_tests = [r for r in distinct_source_slot_candidates if str(r.get("safety", "")).startswith("HIGH_RISK")]

    # v2.8 Peter unused-resource status table.
    # For every PC-present-but-likely-unused Peter ANIM, report whether there is a DIFFERENT
    # debug/source payload candidate. Never copy the PC name into source as a fake match.
    pc_unused_candidate_status = []
    for p in pc_anims:
        if peter_likely_used_by_normal_peter(p.display_name):
            continue
        exact_debug = dbg_by_name.get(p.display_name.lower())
        exact_ok = False
        exact_reason = ""
        if exact_debug:
            exact_ok, exact_reason = same_size_ok(exact_debug, p, True)
        distinct = []
        for d in dbg_anims:
            if d.display_name.lower() == p.display_name.lower():
                continue
            ok, reason = same_size_ok(d, p, True)
            if not ok:
                continue
            score = family_score(p.display_name, d.display_name, p.filename_hash, d.filename_hash)
            distinct.append((score, d, reason))
        distinct.sort(key=lambda x: (-x[0], x[1].display_name.lower()))
        row = peter_entry_row("pc", p)
        row.update({
            "unused_reason": peter_unused_reason(p.display_name),
            "exact_same_name_debug_present": bool(exact_debug),
            "exact_same_name_same_size_layout": bool(exact_ok),
            "exact_same_name_validation": exact_reason,
            "distinct_source_candidate_count": len(distinct),
            "best_distinct_debug_source": distinct[0][1].display_name if distinct else "",
            "best_distinct_debug_source_size": distinct[0][1].total_size if distinct else "",
            "best_distinct_debug_source_components": "/".join(map(str, distinct[0][1].component_sizes)) if distinct else "",
            "best_distinct_family_score": distinct[0][0] if distinct else "",
            "best_distinct_validation": distinct[0][2] if distinct else "",
            "candidate_status": "HAS_DIFFERENT_SOURCE_CANDIDATE" if distinct else "NO_DIFFERENT_SOURCE_CANDIDATE_DO_NOT_DUPLICATE_PC_NAME",
            "v2_8_bugfix_note": "If no different source exists, this row intentionally leaves source blank instead of putting the same PC name on both sides.",
        })
        pc_unused_candidate_status.append(row)

    summary = {
        "tool": "SM3_PC_RVB_TO_PC_ANIM_SWAP_TEST_v2_8_NO_FAKE_SAME_NAME_CANDIDATE_FIX",
        "pc_pack_path": str(pc_pack.path),
        "debug_pack_path": str(debug_pack.path),
        "pc_platform": pc_pack.platform,
        "debug_platform": debug_pack.platform,
        "pc_anim_count": len(pc_anims),
        "debug_anim_count": len(dbg_anims),
        "shared_name_count": len(shared),
        "same_size_same_layout_shared_count": len(same_size_same_layout),
        "size_or_layout_diff_shared_count": len(size_or_layout_diff),
        "pc_only_count": len(pc_only),
        "debug_only_count": len(debug_only),
        "high_value_debug_only_count": len(high_value_debug_only),
        "same_size_slot_candidate_count_including_same_name_controls": len(slot_candidates),
        "same_name_reference_control_count": len(same_name_reference_controls),
        "distinct_source_slot_candidate_count": len(distinct_source_slot_candidates),
        "same_size_slot_candidate_count": len(distinct_source_slot_candidates),
        "first_test_candidate_count": len(first_tests),
        "same_name_first_test_control_count": len(same_name_first_test_controls),
        "family_match_candidate_count": len(family_tests),
        "risky_candidate_count": len(risky_tests),
        "pc_unused_real_candidate_status_rows": len(pc_unused_candidate_status),
        "pc_unused_without_distinct_candidate_count": sum(1 for r in pc_unused_candidate_status if r.get("candidate_status") == "NO_DIFFERENT_SOURCE_CANDIDATE_DO_NOT_DUPLICATE_PC_NAME"),
        "pc_likely_used_by_peter_count": len(pc_likely_used_by_peter),
        "pc_present_but_likely_unused_by_peter_count": len(pc_present_but_likely_unused),
        "pc_unused_combat_count": len(pc_unused_combat),
        "pc_unused_traversal_count": len(pc_unused_traversal),
        "pc_unused_sm2_leftover_count": len(pc_unused_sm2),
        "pc_unused_bs3_leftover_count": len(pc_unused_bs3),
        "rule": "Debug-only names are not direct retail-PC callable names. Use them only as source payloads injected into existing same-size/same-layout PC destination slots.",
        "peter_unused_rule": "PC-present-but-unused means the ANIM exists inside CH_PETER.PCPACK/resource space, but normal Peter gameplay/state logic probably does not call it.",
        "final_character_note": "v2.8 supports Peter preset testing, Peter present-but-likely-unused reports, Player Goblin clean comparison, and no-fake-same-name candidate reports.",
        "v2_8_no_fake_same_name_rule": "Same-name rows are separated as reference controls. Real candidate reports require a different source payload; if none exists, the source cell stays blank and candidate_status says NO_DIFFERENT_SOURCE_CANDIDATE_DO_NOT_DUPLICATE_PC_NAME.",
    }
    return {
        "summary": summary,
        "matrix": matrix,
        "shared": shared,
        "same_size_same_layout": same_size_same_layout,
        "size_or_layout_diff": size_or_layout_diff,
        "pc_only": pc_only,
        "debug_only": debug_only,
        "high_value_debug_only": high_value_debug_only,
        "slot_candidates": slot_candidates,
        "same_name_reference_controls": same_name_reference_controls,
        "distinct_source_slot_candidates": distinct_source_slot_candidates,
        "first_tests": first_tests,
        "same_name_first_test_controls": same_name_first_test_controls,
        "family_tests": family_tests,
        "risky_tests": risky_tests,
        "pc_unused_candidate_status": pc_unused_candidate_status,
        "pc_likely_used_by_peter": pc_likely_used_by_peter,
        "pc_present_but_likely_unused": pc_present_but_likely_unused,
        "pc_unused_combat": pc_unused_combat,
        "pc_unused_traversal": pc_unused_traversal,
        "pc_unused_sm2": pc_unused_sm2,
        "pc_unused_bs3": pc_unused_bs3,
    }

def write_csv(path: Path, rows: List[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    if not keys:
        keys = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def compare_rows(pack_a, pack_b):
    rows = []
    for a in pack_a.anim_files:
        for b in pack_b.anim_files:
            same_hash = a.filename_hash == b.filename_hash and a.filename_hash != 0
            same_name = a.display_name.lower() == b.display_name.lower()
            ok, reason = same_size_ok(b, a, True)
            if same_hash or same_name or ok:
                rows.append({
                    "candidate_kind": "SAME_SIZE" if ok else "REFERENCE_MATCH",
                    "validation": reason,
                    "score": family_score(a.display_name, b.display_name, a.filename_hash, b.filename_hash),
                    "safety": safety_label(a.display_name, b.display_name),
                    "a_platform": a.platform,
                    "a_name": a.display_name,
                    "a_hash": hex32(a.filename_hash),
                    "a_size": a.total_size,
                    "a_components": "/".join(map(str, a.component_sizes)),
                    "b_platform": b.platform,
                    "b_name": b.display_name,
                    "b_hash": hex32(b.filename_hash),
                    "b_size": b.total_size,
                    "b_components": "/".join(map(str, b.component_sizes)),
                    "same_hash": same_hash,
                    "same_name": same_name,
                })
    rows.sort(key=lambda r: (-int(r["candidate_kind"] == "SAME_SIZE"), -r["score"], r["safety"], r["a_name"]))
    return rows


def pack_diff_rows(clean, edited):
    by_key_a = {r.identity_key(): r for r in clean.resources}
    by_key_b = {r.identity_key(): r for r in edited.resources}
    all_keys = sorted(set(by_key_a) | set(by_key_b), key=lambda k: (k[0], k[2], k[1]))
    resource_rows = []
    component_rows = []
    changed_resources = changed_components = added = missing_in_b = 0
    for key in all_keys:
        a = by_key_a.get(key)
        b = by_key_b.get(key)
        status = "UNCHANGED"
        if a is None:
            status = "ADDED_IN_B"
            added += 1
        elif b is None:
            status = "MISSING_IN_B"
            missing_in_b += 1
        else:
            if a.component_sizes != b.component_sizes or a.component_count != b.component_count:
                status = "STRUCTURE_OR_SIZE_CHANGED"
            else:
                a_shas = clean.component_sha_list(a)
                b_shas = edited.component_sha_list(b)
                if a_shas != b_shas:
                    status = "PAYLOAD_CHANGED"
            if status != "UNCHANGED":
                changed_resources += 1
        resource_rows.append({
            "status": status,
            "file_type": key[0],
            "hash": hex32(key[1]),
            "name": key[2],
            "a_total_size": a.total_size if a else "",
            "b_total_size": b.total_size if b else "",
            "a_components": "/".join(map(str, a.component_sizes)) if a else "",
            "b_components": "/".join(map(str, b.component_sizes)) if b else "",
        })
        if a and b:
            a_shas = clean.component_sha_list(a)
            b_shas = edited.component_sha_list(b)
            for i in range(max(a.component_count, b.component_count)):
                a_sz = a.component_sizes[i] if i < a.component_count else ""
                b_sz = b.component_sizes[i] if i < b.component_count else ""
                a_sha = a_shas[i] if i < len(a_shas) else ""
                b_sha = b_shas[i] if i < len(b_shas) else ""
                if a_sz != b_sz or a_sha != b_sha:
                    changed_components += 1
                    component_rows.append({
                        "status": "CHANGED",
                        "file_type": key[0],
                        "hash": hex32(key[1]),
                        "name": key[2],
                        "component": i,
                        "a_size": a_sz,
                        "b_size": b_sz,
                        "a_sha1": a_sha,
                        "b_sha1": b_sha,
                    })
    summary = {
        "pack_a": str(clean.path),
        "pack_b": str(edited.path),
        "pack_a_size": clean.size,
        "pack_b_size": edited.size,
        "same_file_size": clean.size == edited.size,
        "pack_a_resource_count": len(clean.resources),
        "pack_b_resource_count": len(edited.resources),
        "changed_resource_count": changed_resources,
        "changed_component_count": changed_components,
        "added_resource_count": added,
        "missing_in_b_resource_count": missing_in_b,
    }
    return resource_rows, component_rows, summary


FINAL_CHARACTER_EXPECTED = {
    "PETER": {
        "pc_expected_note": "PC CH_PETER focus chain usually has 5 facial Peter ANIM slots in current extracted model chain.",
        "source_examples": "PC: SM3_CH_PETER_MODEL_CHAIN_v1_2.zip or CH_PETER.PCPACK. Debug/X360: PETERX360_* focused output when parser recovers ANIM.",
        "safe_rule": "Peter debug-only names are source payloads only. PC Peter destination slot must already exist and match size/layout.",
    },
    "GOBLIN": {
        "pc_expected_note": "PC CH_PLAYERGOBLIN v1.6 extraction is locked: 35 ANIM / 35 expected, 94 focused exports total.",
        "source_examples": "PC: SM3_CH_PLAYERGOBLIN_MODEL_CHAIN_v1_4.zip or CH_PLAYERGOBLIN(2).zip HxD dump. X360: GOBX360_CH_SPIDERMAN_FOCUSED_CHAIN_v03_Output.zip.",
        "safe_rule": "Expected clean compare: PC Goblin ANIM 35, X360 Goblin ANIM 35, shared names 35, same-size/layout 35, PC-only 0, debug-only 0.",
    },
}


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("SM3 ANIMATION SWAPPER RELEASE v1.14")
        apply_app_icon(self.root)
        self.root.geometry("1340x860")
        self.root.minsize(1080, 700)

        self.a_var = tk.StringVar()
        self.b_var = tk.StringVar()
        self.xbox_source_folder_var = tk.StringVar()
        self.xbox_source_choice_var = tk.StringVar(value="Manual Pack B")
        self.xbox_source_map = {}
        self.search_a = tk.StringVar()
        self.search_b = tk.StringVar()
        self.filter_a = tk.StringVar(value="All")
        self.filter_b = tk.StringVar(value="All")
        self.strict_var = tk.BooleanVar(value=True)
        self.max_auto_var = tk.IntVar(value=20)
        self.pack_a = None
        self.pack_b = None
        self.view_a = []
        self.view_b = []
        self.selection_center_pairs = []
        self.selection_center_active = False
        self.dark_mode_var = tk.BooleanVar(value=False)
        self.style = ttk.Style(self.root)
        self.build_ui()
        self.apply_theme()

    def iter_child_widgets(self, widget):
        for child in widget.winfo_children():
            yield child
            yield from self.iter_child_widgets(child)

    def apply_theme(self):
        dark = bool(getattr(self, "dark_mode_var", tk.BooleanVar(value=False)).get())
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        if dark:
            bg = "#1E1E1E"
            panel = "#252526"
            fg = "#EDEDED"
            field = "#111111"
            accent = "#3A7AFE"
            # v1.14: final About / How To Use guide update.
            # Only the red/blue message labels are changed; normal UI text keeps the same theme.
            warn = "#FF9A9A"
            info = "#8EC5FF"
        else:
            bg = "#F3F3F3"
            panel = "#FFFFFF"
            fg = "#111111"
            field = "#FFFFFF"
            accent = "#005A9E"
            warn = "#B00000"
            info = "#005A9E"
        try:
            self.root.configure(bg=bg)
        except Exception:
            pass
        for style_name in ["TFrame", "TLabelframe", "TLabelframe.Label"]:
            try: self.style.configure(style_name, background=bg, foreground=fg)
            except Exception: pass
        for style_name in ["TLabel", "TCheckbutton", "TRadiobutton"]:
            try: self.style.configure(style_name, background=bg, foreground=fg)
            except Exception: pass
        try:
            self.style.configure("Warn.TLabel", background=bg, foreground=warn)
            self.style.configure("Info.TLabel", background=bg, foreground=info)
        except Exception:
            pass
        try:
            self.style.configure("TButton", padding=4)
            self.style.configure("TEntry", fieldbackground=field, foreground=fg)
            self.style.configure("TCombobox", fieldbackground=field, foreground=fg)
            self.style.configure("Treeview", background=panel, foreground=fg, fieldbackground=panel)
            self.style.configure("Treeview.Heading", background=bg, foreground=fg)
            self.style.map("Treeview", background=[("selected", accent)], foreground=[("selected", "#FFFFFF")])
        except Exception:
            pass
        for w in self.iter_child_widgets(self.root):
            try:
                if isinstance(w, (tk.Text, tk.Listbox)):
                    w.configure(bg=panel, fg=fg, insertbackground=fg, selectbackground=accent, selectforeground="#FFFFFF")
                elif isinstance(w, tk.Entry):
                    w.configure(bg=field, fg=fg, insertbackground=fg)
            except Exception:
                pass
        if hasattr(self, "status"):
            try:
                self.status.configure(bg=panel, fg=fg, insertbackground=fg)
            except Exception:
                pass

    def toggle_dark_mode(self):
        self.apply_theme()
        mode = "Dark" if self.dark_mode_var.get() else "Light"
        self.write(f"\nTheme changed: {mode} mode.\n")

    def build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        brand = ttk.Frame(top)
        brand.grid(row=0, column=0, columnspan=6, sticky="ew", pady=(0, 6))
        ttk.Label(brand, text="SM3 ANIMATION SWAPPER", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(brand, text="   Created by TSGAMING264", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Checkbutton(brand, text="Dark Mode", variable=self.dark_mode_var, command=self.toggle_dark_mode).pack(side="right")
        ttk.Label(top, text="Pack A / PC destination pack:").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.a_var).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(top, text="Browse PC Pack A", command=lambda: self.browse(self.a_var)).grid(row=1, column=2, padx=4)
        ttk.Button(top, text="Clear Pack A", command=self.clear_pack_a).grid(row=1, column=3, padx=4)
        ttk.Label(top, text="Pack B / source pack (manual PC/source option):").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.b_var).grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Button(top, text="Browse Pack B", command=lambda: self.browse(self.b_var)).grid(row=2, column=2, padx=4)
        ttk.Button(top, text="Clear Pack B", command=self.clear_pack_b).grid(row=2, column=3, padx=4)

        ttk.Label(top, text="Xbox Pack Folder (optional):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(top, textvariable=self.xbox_source_folder_var).grid(row=3, column=1, sticky="ew", padx=4, pady=(6, 0))
        ttk.Button(top, text="Select Xbox Pack Folder", command=self.browse_xbox_source_folder).grid(row=3, column=2, padx=4, pady=(6, 0))
        ttk.Button(top, text="Clear Xbox Pack Folder", command=self.clear_xbox_source_folder).grid(row=3, column=3, padx=4, pady=(6, 0))

        xbox_row = ttk.Frame(top)
        xbox_row.grid(row=4, column=1, columnspan=2, sticky="ew", padx=4, pady=(3, 0))
        xbox_row.columnconfigure(0, weight=1)
        self.xbox_source_combo = ttk.Combobox(xbox_row, textvariable=self.xbox_source_choice_var, state="readonly", values=["Manual Pack B"], width=42)
        self.xbox_source_combo.grid(row=0, column=0, sticky="ew")
        self.xbox_source_combo.bind("<<ComboboxSelected>>", self.selected_xbox_source_changed)
        ttk.Button(xbox_row, text="Use Selected Xbox Source as Pack B", command=self.use_selected_xbox_source_as_pack_b).grid(row=0, column=1, padx=(6, 0))

        ttk.Button(top, text="Clear All Pack Inputs", command=self.clear_all_pack_inputs).grid(row=4, column=3, padx=4, pady=(3, 0), sticky="ew")
        ttk.Button(top, text="LOAD / VERIFY PACKS", command=self.scan).grid(row=1, column=4, rowspan=4, padx=8, sticky="ns")
        ttk.Checkbutton(top, text="Strict same component sizes", variable=self.strict_var).grid(row=5, column=0, sticky="w", pady=(6, 0))
        top.columnconfigure(1, weight=1)
        ttk.Label(self.root, text="Created by TSGAMING264. Select your PC destination pack, choose your Xbox Pack Folder or manual Pack B, then save a new patched copy.", style="Warn.TLabel").pack(fill="x", padx=10)

        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(paned, padding=4)
        right = ttk.Frame(paned, padding=4)
        paned.add(left, weight=1)
        paned.add(right, weight=1)
        self.make_panel(left, "PACK A ANIM LIST", self.search_a, True)
        self.make_panel(right, "PACK B ANIM LIST", self.search_b, False)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Preview Selected Pair", command=self.preview).pack(side="left", padx=4)
        ttk.Button(bottom, text="PATCH SELECTED PAIR -> NEW PC COPY", command=self.rvb_to_pc_patch).pack(side="left", padx=4)
        ttk.Button(bottom, text="MULTI SELECTION CENTER", command=self.multi_selection_center).pack(side="left", padx=4)
        ttk.Button(bottom, text="ABOUT / INFO", command=self.show_about_info).pack(side="left", padx=4)

        self.status = tk.Text(self.root, height=11, wrap="word")
        self.status.pack(fill="both", expand=False, padx=8, pady=(0,8))
        self.write("SM3 ANIMATION SWAPPER RELEASE v1.14 ready. Created by TSGAMING264. Light Mode default, Dark Mode toggle available. Only real animation-changing presets are listed. Imported same-name/no-change presets are blocked.\n")

    def open_external_link(self, url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("Open link failed", str(exc))

    def show_about_info(self):
        """Public About / Info window for release users."""
        win = tk.Toplevel(self.root)
        win.title("About / Info - SM3 ANIMATION SWAPPER")
        apply_app_icon(win)
        win.geometry("760x680")
        win.minsize(620, 520)
        win.transient(self.root)

        outer = ttk.Frame(win, padding=10)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="SM3 ANIMATION SWAPPER",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text="Created by TSGAMING264",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        text_frame = ttk.Frame(outer)
        text_frame.pack(fill="both", expand=True)
        scroll = ttk.Scrollbar(text_frame, orient="vertical")
        info = tk.Text(text_frame, wrap="word", height=24, yscrollcommand=scroll.set)
        scroll.config(command=info.yview)
        info.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        about_text = 'SM3 ANIMATION SWAPPER - HOW TO USE\n============================================================\n\n1. OPEN THE TOOL\n============================================================\n\nOpen:\n\nSM3 ANIMATION SWAPPER.bat\n\nOptional:\nRun the shortcut creator if you want a desktop shortcut:\n\nCREATE_DESKTOP_SHORTCUT_SM3_ANIMATION_SWAPPER.bat\n\n\n============================================================\n2. PICK PACK A - YOUR PC DESTINATION PACK\n============================================================\n\nPack A is the PC pack you want to modify.\n\nChoose one clean PC pack, for example:\n\nCH_SPIDERMAN.PCPACK\nCH_BLACKSUIT.PCPACK\nCH_PETER.PCPACK\nCH_PLAYERGOBLIN.PCPACK\n\nImportant:\nPack A can also be a previously patched PC pack if you want to add more changes later.\n\nExample:\n\nFirst patch:\nClean CH_SPIDERMAN.PCPACK -> patched copy\n\nFollow-up patch:\nLoad the patched copy as Pack A -> apply another preset\n\n\n============================================================\n3. PICK YOUR XBOX PACK FOLDER\n============================================================\n\nClick the Xbox Pack Folder button.\n\nChoose the folder that contains your Xbox source ZIPs.\n\nDO NOT UNZIP the ZIP files inside this folder.\n\nLeave them zipped.\n\nExpected Xbox Pack Folder contents:\n\nCH_SPIDERMANXE.zip\nCH_BLACKSUITXE.zip\nCH_PETERXE.zip\nCH_PLAYERGOBLINXE.zip\nCH_SPIDERMAN_RVBXE.zip\nCH_RVBBLACKXE.zip\n\nThe tool will read the ZIPs from the folder.\n\n\n============================================================\n4. PACK B / SOURCE SIDE\n============================================================\n\nPack B is the source side.\n\nYou can use:\n\n- Xbox pack ZIP from the Xbox Pack Folder\n- manually selected source pack\n- another PC pack\n- a previously patched PC pack\n\nFor normal release presets, the tool usually uses the correct source based on the preset/source you select.\n\n\n============================================================\n5. LOAD / VERIFY PACKS\n============================================================\n\nAfter Pack A and Pack B/source are selected, click:\n\nLOAD / VERIFY PACKS\n\nThe tool should show the animation lists for Pack A and Pack B.\n\nIf you picked the wrong pack, use:\n\nClear Pack A\nClear Pack B\nClear Source Folder\nClear All Pack Inputs\n\n\n============================================================\n6. OPEN RELEASE PRESET CENTER\n============================================================\n\nClick:\n\nRELEASE PRESET CENTER\n\nPick a preset.\n\nGood first preset:\n\nRVB_RED_COMBAT_RESTORED_5PACK\n\nThis is the most stable release preset.\n\n\n============================================================\n7. USE MULTI SELECTION CENTER IF NEEDED\n============================================================\n\nClick:\n\nMULTI SELECTION CENTER\n\nUse this when you want to add several preset rows together or manage selected swaps more easily.\n\nThe tool blocks same-name/no-change rows.\n\nExample of blocked no-change row:\n\ngobairturbo <- gobairturbo\n\nThat would patch the same animation back into itself, so the tool correctly blocks it.\n\n\n============================================================\n8. PATCH A NEW COPY\n============================================================\n\nWhen ready, click the patch button.\n\nThe tool should save a NEW patched PC copy.\n\nImportant:\nDo not overwrite your clean original pack.\n\nAlways keep backups.\n\n\n============================================================\n9. INSTALL THE PATCHED PACK\n============================================================\n\nAfter the new patched pack is created:\n\n1. Back up your original game pack.\n2. Rename the patched copy if needed.\n3. Put it in your Spider-Man 3 PC packs folder.\n4. Test in-game.\n\nExample game folder:\n\nYour Spider-Man 3 PC packs folder\n\n\n============================================================\nBEST FIRST TEST\n============================================================\n\nStart with:\n\nPack A:\nCH_SPIDERMAN.PCPACK\n\nXbox Pack Folder:\nfolder containing the zipped Xbox packs\n\nPreset:\nRVB_RED_COMBAT_RESTORED_5PACK\n\nOutput:\nnew patched CH_SPIDERMAN copy\n\nThis is the safest main release preset.\n\n\n============================================================\nIMPORTANT SAFETY NOTES\n============================================================\n\n- Do not unzip the Xbox Pack Folder ZIPs.\n- Do not overwrite your original PC packs.\n- Use clean PC packs for first-time patching.\n- Use Clear Pack buttons if you select the wrong pack.\n- Same-name/no-change presets are blocked.\n\n\n============================================================\nBOTTOM LINE\n============================================================\n\nPack A = PC pack you want to change.\n\nXbox Pack Folder = folder with zipped Xbox source packs.\n\nPreset Center = choose animation preset.\n\nMulti Selection Center = manage multiple selected swaps.\n\nPatch = save a new PC pack copy.\n============================================================\n\n\nMESSAGE FROM TSGAMING264\n============================================================\n\nI really wanted this game to get some more mod support. Hopefully you all like and enjoy the tool.\n\nSupport my YouTube channel. Drop a like on the breakdown video whenever it is released.\n\nI will try to make a video of me using this tool. I know these text examples might not be the best at explaining everything, but the tool works and is simple to use.\n\nJoin my Discord, and follow my pages below.'
        info.insert("1.0", about_text)
        info.configure(state="disabled")

        links = ttk.LabelFrame(outer, text="Links", padding=8)
        links.pack(fill="x", pady=(8, 0))
        link_rows = [
            ("Discord", "https://discord.com/invite/57pm3eUUQK"),
            ("YouTube", "https://youtube.com/@tsgaming264?si=xOL9EJYQ-ZfFf7fj"),
            ("X / Twitter", "https://x.com/tsgaming0416?s=21"),
            ("Instagram", "https://www.instagram.com/tsgaming0416?igsh=aGRjM29pcmR6aXh4&utm_source=qr"),
            ("Reddit", "https://www.reddit.com/u/TSGAMING264/s/IJogsEHNtp"),
        ]
        for label, url in link_rows:
            row = ttk.Frame(links)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{label}:", width=14).pack(side="left")
            ttk.Label(row, text=url).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Open", command=lambda u=url: self.open_external_link(u)).pack(side="right")

        ttk.Button(outer, text="Close", command=win.destroy).pack(anchor="e", pady=(8, 0))
        try:
            self.apply_theme()
        except Exception:
            pass

    def make_panel(self, parent, title, var, is_a):
        ttk.Label(parent, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        sf = ttk.Frame(parent)
        sf.pack(fill="x", pady=3)
        ttk.Label(sf, text="Search:").pack(side="left")
        ent = ttk.Entry(sf, textvariable=var)
        ent.pack(side="left", fill="x", expand=True, padx=4)
        ent.bind("<KeyRelease>", lambda e: self.refresh_preserve_selection())
        ttk.Button(sf, text="Search", command=self.refresh_preserve_selection).pack(side="left")
        ttk.Button(sf, text="Clear Search", command=lambda v=var: self.clear_search(v)).pack(side="left", padx=4)

        ttk.Label(sf, text="Filter:").pack(side="left", padx=(10, 2))
        filter_var = self.filter_a if is_a else self.filter_b
        combo = ttk.Combobox(
            sf,
            textvariable=filter_var,
            state="readonly",
            width=10,
            values=["All", "Combat", "Swing", "Jump", "Walk", "Idle"]
        )
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_preserve_selection())
        ttk.Button(sf, text="Apply Filter", command=self.refresh_preserve_selection).pack(side="left", padx=4)
        ttk.Button(sf, text="Clear Filter", command=lambda side=is_a: self.clear_filter(side)).pack(side="left", padx=4)

        sel_var = tk.StringVar(value="Selected: none")
        sel_label = ttk.Label(parent, textvariable=sel_var, style="Info.TLabel")
        sel_label.pack(anchor="w", pady=(0, 3))

        cols = ("platform","name","size","components","family","safety")
        # Release v1.14 startup fix:
        # Use PACK ONLY for the main list scrollbars. This avoids Tk's
        # pack/grid geometry-manager conflict on some Python/Tk builds.
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True)

        tree_body = ttk.Frame(tree_frame)
        tree_body.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_body, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            tree.heading(c, text=c)
        tree.column("platform", width=55, stretch=False)
        tree.column("name", width=285, stretch=True)
        tree.column("size", width=85, stretch=False)
        tree.column("components", width=105, stretch=False)
        tree.column("family", width=95, stretch=False)
        tree.column("safety", width=120, stretch=False)

        y = ttk.Scrollbar(tree_body, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)

        y.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        x.pack(side="bottom", fill="x")

        def wheel(e, t=tree):
            if e.num == 4:
                t.yview_scroll(-3, "units")
            elif e.num == 5:
                t.yview_scroll(3, "units")
            else:
                t.yview_scroll(int(-1*(e.delta/120))*3, "units")
            return "break"

        tree.bind("<MouseWheel>", wheel)
        tree.bind("<Button-4>", wheel)
        tree.bind("<Button-5>", wheel)
        tree.bind("<<TreeviewSelect>>", lambda e, side=is_a: self.update_selection_labels())

        if is_a:
            self.tree_a = tree
            self.sel_a_var = sel_var
        else:
            self.tree_b = tree
            self.sel_b_var = sel_var

    def write(self, s):
        self.status.insert("end", s)
        self.status.see("end")
        self.root.update_idletasks()

    def clear_search(self, var):
        var.set("")
        self.refresh_preserve_selection()

    def clear_filter(self, is_a):
        if is_a:
            self.filter_a.set("All")
        else:
            self.filter_b.set("All")
        self.refresh_preserve_selection()

    def anim_matches_real_filter(self, entry, filter_name):
        f = (filter_name or "All").lower()
        if f == "all":
            return True
        low = (entry.display_name or "").lower()
        if f == "combat":
            return any(k in low for k in [
                "atck", "attack", "punch", "kick", "hit", "block", "uppercut",
                "stomp", "pummel", "rage", "fury", "smash", "beatdown", "deflect"
            ])
        if f == "swing":
            return any(k in low for k in ["swing", "swg", "webswing", "poleswg"])
        if f == "jump":
            return any(k in low for k in ["jump", "jmp", "dive", "fall", "land", "launch", "lnch", "rls"])
        if f == "walk":
            return any(k in low for k in ["walk", "run", "sprint"]) and not any(k in low for k in ["wall", "swg", "swing"])
        if f == "idle":
            return any(k in low for k in ["idle", "idl", "tapleft", "tapright", "tapback", "tapfwd"])
        return True

    def entry_key(self, e):
        return (e.platform, e.display_name, int(e.filename_hash or 0), int(e.total_size or 0), tuple(e.component_sizes or []))

    def selected_keys(self, is_a):
        tree = self.tree_a if is_a else self.tree_b
        view = self.view_a if is_a else self.view_b
        keys = []
        for iid in tree.selection():
            try:
                keys.append(self.entry_key(view[int(iid)]))
            except Exception:
                pass
        return keys

    def restore_selection_by_keys(self, is_a, keys):
        if not keys:
            return
        tree = self.tree_a if is_a else self.tree_b
        view = self.view_a if is_a else self.view_b
        keyset = set(keys)
        restore = []
        for i, e in enumerate(view):
            if self.entry_key(e) in keyset:
                restore.append(str(i))
        if restore:
            tree.selection_set(restore)
            tree.see(restore[0])

    def refresh_preserve_selection(self):
        a_keys = self.selected_keys(True) if hasattr(self, "tree_a") else []
        b_keys = self.selected_keys(False) if hasattr(self, "tree_b") else []
        self.refresh(a_keys=a_keys, b_keys=b_keys)

    def entry_summary(self, e):
        if not e:
            return "Selected: none"
        return (
            f"Selected: {e.platform} | {e.display_name} | "
            f"size={e.total_size} | comps={'/'.join(map(str, e.component_sizes))} | "
            f"family={family_label_for_name(e.display_name)} | safety={detailed_anim_safety(e.display_name)}"
        )

    def entry_multi_summary(self, entries):
        if not entries:
            return "Selected: none"
        if len(entries) == 1:
            return self.entry_summary(entries[0])
        names = ", ".join(e.display_name for e in entries[:3])
        if len(entries) > 3:
            names += f", ... +{len(entries)-3}"
        return f"Selected {len(entries)} ANIM: {names}"

    def update_selection_labels(self):
        try:
            if hasattr(self, "sel_a_var"):
                try:
                    self.sel_a_var.set(self.entry_multi_summary(self.selected_many(True)))
                except Exception:
                    self.sel_a_var.set("Selected: none")
            if hasattr(self, "sel_b_var"):
                try:
                    self.sel_b_var.set(self.entry_multi_summary(self.selected_many(False)))
                except Exception:
                    self.sel_b_var.set("Selected: none")
        except Exception:
            pass




    def reset_tree_panel(self, is_a):
        """Clear one visible ANIM list without requiring both packs to be loaded."""
        try:
            tree = self.tree_a if is_a else self.tree_b
            tree.delete(*tree.get_children())
        except Exception:
            pass
        if is_a:
            self.view_a = []
            try: self.sel_a_var.set("Selected: none")
            except Exception: pass
        else:
            self.view_b = []
            try: self.sel_b_var.set("Selected: none")
            except Exception: pass

    def clear_selection_center_state(self):
        """Pack inputs changed, so any queued multi-patch rows are no longer reliable."""
        try:
            self.selection_center_pairs.clear()
        except Exception:
            self.selection_center_pairs = []
        self.selection_center_active = False

    def clear_pack_a(self):
        self.a_var.set("")
        self.pack_a = None
        self.search_a.set("")
        self.filter_a.set("All")
        self.reset_tree_panel(True)
        self.clear_selection_center_state()
        self.write("\nPack A cleared. Choose the correct PC destination pack before loading again.\n")

    def clear_pack_b(self):
        self.b_var.set("")
        self.pack_b = None
        self.search_b.set("")
        self.filter_b.set("All")
        self.reset_tree_panel(False)
        self.xbox_source_choice_var.set("Manual Pack B")
        self.clear_selection_center_state()
        self.write("\nPack B cleared. Choose a manual source pack or select one from the Xbox Pack Folder.\n")

    def clear_xbox_source_folder(self):
        self.xbox_source_folder_var.set("")
        self.xbox_source_map = {}
        self.xbox_source_choice_var.set("Manual Pack B")
        try:
            self.xbox_source_combo.configure(values=["Manual Pack B"])
        except Exception:
            pass
        self.write("\nXbox Pack Folder cleared. Manual Pack B is still available.\n")

    def clear_all_pack_inputs(self):
        self.a_var.set("")
        self.b_var.set("")
        self.pack_a = None
        self.pack_b = None
        self.search_a.set("")
        self.search_b.set("")
        self.filter_a.set("All")
        self.filter_b.set("All")
        self.reset_tree_panel(True)
        self.reset_tree_panel(False)
        self.clear_xbox_source_folder()
        self.clear_selection_center_state()
        self.write("\nAll pack inputs cleared. Start again with the correct PC Pack A and source Pack B.\n")

    def browse_xbox_source_folder(self):
        folder = filedialog.askdirectory(title="Choose folder containing your own Xbox/XE source ZIPs")
        if folder:
            self.xbox_source_folder_var.set(folder)
            self.scan_xbox_source_folder(Path(folder))

    def scan_xbox_source_folder(self, folder: Path):
        """Scan a user-provided folder for Xbox/XE source ZIPs.

        This is release-safe: the tool does not include source packs. It only
        detects files the user selected from their own folder and lets one be
        loaded as Pack B.
        """
        self.xbox_source_map = {}
        values = ["Manual Pack B"]
        if not folder.exists() or not folder.is_dir():
            messagebox.showerror("Xbox Pack Folder", "Selected Xbox Pack Folder does not exist.")
            return
        lower_to_path = {p.name.lower(): p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".zip"}
        status_lines = []
        for label, aliases in XBOX_SOURCE_ZIP_DEFINITIONS:
            found = None
            for alias in aliases:
                p = lower_to_path.get(alias.lower())
                if p:
                    found = p
                    break
            if found:
                display = f"{label}  - FOUND ({found.name})"
                self.xbox_source_map[display] = found
                values.append(display)
                status_lines.append(f"{label}: FOUND ({found.name})")
            else:
                status_lines.append(f"{label}: missing")
        try:
            self.xbox_source_combo.configure(values=values)
        except Exception:
            pass
        self.xbox_source_choice_var.set(values[1] if len(values) > 1 else "Manual Pack B")
        if len(values) > 1:
            self.use_selected_xbox_source_as_pack_b(silent=True)
        self.write("\nXbox Pack Folder scanned:\n" + "\n".join(status_lines) + "\n")

    def selected_xbox_source_changed(self, _event=None):
        self.use_selected_xbox_source_as_pack_b(silent=True)

    def use_selected_xbox_source_as_pack_b(self, silent: bool = False):
        choice = self.xbox_source_choice_var.get()
        p = self.xbox_source_map.get(choice)
        if not p:
            if not silent and choice != "Manual Pack B":
                messagebox.showinfo("Xbox source", "Select a detected Xbox source ZIP first.")
            return
        self.b_var.set(str(p))
        if not silent:
            self.write(f"\nPack B set from Xbox Pack Folder: {p.name}\n")

    def browse(self, var):
        p = filedialog.askopenfilename(title="Choose pack or output zip", filetypes=[("SM3 pack/output zip/hex txt", "*.PCPACK *.XEPACK *.zip *.txt"), ("All files", "*.*")])
        if p:
            var.set(p)

    def scan(self):
        try:
            a = Path(self.a_var.get())
            b = Path(self.b_var.get())
            if not a.exists(): raise ValueError("Pack A does not exist.")
            if not b.exists(): raise ValueError("Pack B does not exist.")
            self.write("\nScanning A...\n")
            self.pack_a = load_pack_or_extracted(a, "PC")
            self.write(f"A: {self.pack_a.platform} {self.pack_a.kind} resources={len(self.pack_a.resources)} ANIM={len(self.pack_a.anim_files)}\n")
            if getattr(self.pack_a, "errors", None):
                self.write("A warnings:\n" + "\n".join(self.pack_a.errors[:8]) + "\n")
            self.write("Scanning B...\n")
            pref = "X360" if b.suffix.lower() in (".xepack", ".zip") else "PC"
            self.pack_b = load_pack_or_extracted(b, pref)
            self.write(f"B: {self.pack_b.platform} {self.pack_b.kind} resources={len(self.pack_b.resources)} ANIM={len(self.pack_b.anim_files)}\n")
            if getattr(self.pack_b, "errors", None):
                self.write("B warnings:\n" + "\n".join(self.pack_b.errors[:8]) + "\n")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Scan failed", str(e))
            self.write(f"ERROR: {e}\n")

    def filter_list(self, entries, term, filter_name="All"):
        term = (term or "").lower().strip()
        out = []
        for e in entries:
            hay = f"{e.platform} {e.display_name} {e.total_size}".lower()
            if term and term not in hay:
                continue
            if not self.anim_matches_real_filter(e, filter_name):
                continue
            out.append(e)
        return out

    def refresh(self, a_keys=None, b_keys=None):
        if not self.pack_a or not self.pack_b:
            return
        a_keys = a_keys or []
        b_keys = b_keys or []
        self.tree_a.delete(*self.tree_a.get_children())
        self.tree_b.delete(*self.tree_b.get_children())
        self.view_a = self.filter_list(self.pack_a.anim_files, self.search_a.get(), self.filter_a.get())
        self.view_b = self.filter_list(self.pack_b.anim_files, self.search_b.get(), self.filter_b.get())
        for i, e in enumerate(self.view_a):
            self.tree_a.insert("", "end", iid=str(i), values=(e.platform, e.display_name, e.total_size, "/".join(map(str,e.component_sizes)), family_label_for_name(e.display_name), detailed_anim_safety(e.display_name)))
        for i, e in enumerate(self.view_b):
            self.tree_b.insert("", "end", iid=str(i), values=(e.platform, e.display_name, e.total_size, "/".join(map(str,e.component_sizes)), family_label_for_name(e.display_name), detailed_anim_safety(e.display_name)))
        self.restore_selection_by_keys(True, a_keys)
        self.restore_selection_by_keys(False, b_keys)
        self.update_selection_labels()

    def selected(self, is_a):
        tree = self.tree_a if is_a else self.tree_b
        view = self.view_a if is_a else self.view_b
        sel = tree.selection()
        if not sel:
            raise ValueError("No ANIM selected.")
        return view[int(sel[0])]

    def selected_many(self, is_a):
        tree = self.tree_a if is_a else self.tree_b
        view = self.view_a if is_a else self.view_b
        sel = list(tree.selection())
        if not sel:
            raise ValueError("No ANIM selected.")
        entries = []
        for iid in sel:
            try:
                entries.append(view[int(iid)])
            except Exception:
                pass
        if not entries:
            raise ValueError("No valid ANIM selected.")
        return entries


    def preview(self):
        try:
            a = self.selected(True)
            b = self.selected(False)
            ok, reason = same_size_ok(b, a, self.strict_var.get())
            msg = (
                f"A/DEST: {a.platform} {a.display_name} size={a.total_size} comps={a.component_sizes}\n"
                f"B/SRC : {b.platform} {b.display_name} size={b.total_size} comps={b.component_sizes}\n\n"
                f"Validation: {'PASS' if ok else 'FAIL'} - {reason}\n"
                f"Safety: {safety_label(a.display_name,b.display_name)}\n\n"
                "Patch only works when both A and B are PC packs."
            )
            self.write("\n" + msg + "\n")
            messagebox.showinfo("Preview", msg)
        except Exception as e:
            messagebox.showerror("Preview failed", str(e))

    def patch(self):
        try:
            if self.pack_a.platform != "PC" or self.pack_b.platform != "PC":
                raise ValueError("Patching is PC destination + PC source only. Xbox is read/list/compare only.")
            a = self.selected(True)
            b = self.selected(False)
            ok, reason = same_size_ok(b, a, self.strict_var.get())
            if not ok:
                raise ValueError(reason)
            out = filedialog.asksaveasfilename(title="Save patched PC PCPACK copy", defaultextension=".PCPACK", initialfile=Path(self.pack_a.path).stem + "_ANIM_SWAP_TEST.PCPACK", filetypes=[("PCPACK","*.PCPACK"),("All files","*.*")])
            if not out:
                return
            patch_pc_anim_copy(self.pack_a, self.pack_b, a, b, Path(out), self.strict_var.get(), allow_x360_source=False)
            self.write(f"\nPatched PC copy saved: {out}\n")
            messagebox.showinfo("Patch complete", f"Saved:\n{out}")
        except Exception as e:
            messagebox.showerror("Patch failed", str(e))
            self.write(f"ERROR: {e}\n")

    def dump(self, is_a):
        try:
            pack = self.pack_a if is_a else self.pack_b
            entry = self.selected(is_a)
            if not pack:
                raise ValueError("Scan first.")
            folder = filedialog.askdirectory(title="Choose dump folder")
            if not folder:
                return
            folder = Path(folder)
            folder.mkdir(parents=True, exist_ok=True)
            safe = clean_name(entry.display_name, "anim")
            out = folder / f"{entry.platform}_{hex32(entry.filename_hash)}.{safe}.anim"
            blob = pack.combined_blob(entry)
            if not blob:
                # Extracted ZIP fallback cannot dump bytes from inside zip in v2.2.
                blob = b""
            out.write_bytes(blob)
            meta = entry.row()
            meta["combined_sha1"] = sha1(blob) if blob else ""
            (folder / f"{out.name}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            self.write(f"\nDumped metadata/file: {out}\n")
        except Exception as e:
            messagebox.showerror("Dump failed", str(e))

    def auto_replace_safe_lite(self, group):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")
            dest_pack, src_pack = source_dest_for_rvb_mode(self.pack_a, self.pack_b)
            max_count = int(self.max_auto_var.get() or 20)
            pairs, rows = build_safe_lite_matches(dest_pack, src_pack, group, max_count=max_count)

            folder = filedialog.askdirectory(title=f"Choose report folder for SAFE {group}")
            if not folder:
                return
            report_path = Path(folder) / f"SAFE_{group.upper()}_MATCHES_v2_2.csv"
            write_csv(report_path, rows)

            warnings = source_suit_warning(dest_pack, src_pack)
            warn_text = "\n".join(warnings)

            if not pairs:
                self.write(f"\nSAFE {group}: no patchable matches. Report: {report_path}\n")
                messagebox.showwarning("No safe-lite matches", f"No patchable {group} matches found.\n\nReport saved:\n{report_path}")
                return

            msg = (
                f"Patch {len(pairs)} SAFE-LITE {group} animations into a NEW PC copy?\n\n"
                f"Max auto patches: {max_count}\n"
                f"Report: {report_path}\n\n"
                "This excludes swing/jump/wall/dive/launch danger names."
            )
            if warn_text:
                msg += "\n\nSOURCE WARNING:\n" + warn_text

            if not messagebox.askyesno(f"SAFE {group}", msg):
                self.write(f"\nSAFE {group}: cancelled. Report saved: {report_path}\n")
                return

            out = filedialog.asksaveasfilename(
                title=f"Save SAFE {group} patched PC PCPACK copy",
                defaultextension=".PCPACK",
                initialfile=Path(dest_pack.path).stem + f"_SAFE_{group.upper()}_RVB_TEST.PCPACK",
                filetypes=[("PCPACK", "*.PCPACK"), ("All files", "*.*")]
            )
            if not out:
                return

            log = patch_family_same_name_copy(dest_pack, src_pack, pairs, Path(out), group)
            self.write(f"\nSAFE {group} patched copy saved:\n{out}\n")
            self.write(f"Animations patched: {log['patched_animation_count']} | Components patched: {log['component_patch_count']}\n")
            self.write(f"Report: {report_path}\n")
            messagebox.showinfo("SAFE-LITE complete", f"Saved:\n{out}\n\nPatched animations: {log['patched_animation_count']}")
        except Exception as e:
            messagebox.showerror(f"SAFE {group} failed", str(e))
            self.write(f"ERROR: {e}\n")

    def report_family_only(self, family):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")
            dest_pack, src_pack = source_dest_for_rvb_mode(self.pack_a, self.pack_b)
            pairs, rows = build_same_name_family_matches(dest_pack, src_pack, family)

            folder = filedialog.askdirectory(title=f"Choose report folder for {family} family report")
            if not folder:
                return
            report_path = Path(folder) / f"REPORT_ONLY_{family.upper()}_FAMILY_MATCHES_v2_2.csv"
            write_csv(report_path, rows)

            self.write(f"\nREPORT ONLY {family}: {len(pairs)} patchable matches found. No patch created.\n")
            self.write(f"Report: {report_path}\n")
            messagebox.showinfo(
                f"{family} report only",
                f"Report saved:\n{report_path}\n\nPatchable matches: {len(pairs)}\n\nNo pack was patched."
            )
        except Exception as e:
            messagebox.showerror(f"{family} report failed", str(e))
            self.write(f"ERROR: {e}\n")


    def auto_replace_family(self, family):
        messagebox.showwarning(
            "Full auto disabled in v2.2",
            "Full family auto-patching is disabled in v2.2 because it caused crashes.\n\n"
            "Use SAFE Combat Lite / SAFE Hit Reactions / SAFE Idle-Walk Lite, or use REPORT Swing/Jump Only."
        )
        self.write("\nFull AUTO family patching is disabled in v2.2. Use safe-lite buttons.\n")

    def rvb_to_pc_patch(self):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")

            if self.pack_a.platform != "PC":
                raise ValueError("Pack A must be the PC destination pack. Pack B is the source side.")
            if self.pack_b.platform not in ("PC", "X360"):
                raise ValueError("Pack B must be a PC source pack or Xbox/RVB source ZIP/folder output.")

            dest_pack, src_pack = self.pack_a, self.pack_b
            dest_entry = self.selected(True)
            src_entry = self.selected(False)

            # Release guard: same-name rows are normally reference/no-change controls.
            if dest_entry.display_name.lower() == src_entry.display_name.lower():
                raise ValueError(
                    "This selected pair has the same destination and source name.\n\n"
                    f"{dest_entry.display_name} <- {src_entry.display_name}\n\n"
                    "Release mode blocks same-name/no-change pairs so users do not patch the same animation back into itself. "
                    "Choose a source animation with a different name, or use a real release preset."
                )

            ok, reason = same_size_ok(src_entry, dest_entry, self.strict_var.get())
            if not ok:
                raise ValueError(reason + "\n\nChoose a compatible source with the same size/component layout.")

            out = filedialog.asksaveasfilename(
                title="Save patched PC PCPACK copy",
                defaultextension=".PCPACK",
                initialfile=Path(dest_pack.path).stem + "_ANIM_SWAP_TEST.PCPACK",
                filetypes=[("PCPACK","*.PCPACK"),("All files","*.*")]
            )
            if not out:
                return

            patch_pc_anim_copy(dest_pack, src_pack, dest_entry, src_entry, Path(out), self.strict_var.get(), allow_x360_source=True)
            self.write(f"\nPatched PC copy saved: {out}\n")
            self.write(f"{dest_entry.display_name} <- {src_entry.display_name}\n")
            messagebox.showinfo("Patch complete", f"Saved patched PC copy:\n{out}\n\nSource side used: {src_pack.platform}")
        except Exception as e:
            messagebox.showerror("Patch failed", str(e))
            self.write(f"ERROR: {e}\n")

    def find_visible_iid_by_name(self, is_a, name):
        view = self.view_a if is_a else self.view_b
        for i, e in enumerate(view):
            if e.display_name.lower() == name.lower():
                return str(i)
        return None

    def find_loaded_entry_by_name(self, pack, name):
        if not pack:
            return None
        for e in pack.anim_files:
            if e.display_name.lower() == name.lower():
                return e
        return None

    def reset_search_filter_for_pair_apply(self):
        # The center is supposed to put options into the page selection.
        # Clear search/filter so hidden rows can become visible and selectable.
        self.search_a.set("")
        self.search_b.set("")
        self.filter_a.set("All")
        self.filter_b.set("All")
        self.refresh(a_keys=[], b_keys=[])

    def side_for_pc_and_rvb(self):
        """Return booleans for release pair mode. Pack A is PC destination; Pack B is the source side.

        Older internal code calls this pc/rvb, but release v1.14 keeps it universal:
        Pack B may be Xbox/RVB or a normal PC character pack / previously patched PC pack.
        """
        if not self.pack_a or not self.pack_b:
            raise ValueError("Load/verify packs first.")
        if self.pack_a.platform != "PC":
            raise ValueError("Pack A must be the PC destination pack. Clear Pack A and choose the clean/current PC pack you want to patch.")
        if self.pack_b.platform not in ("PC", "X360"):
            raise ValueError("Pack B must be a valid source pack. Choose a PC source pack manually, or choose an Xbox/RVB ZIP from the Xbox Pack Folder.")
        return True, False   # destination is A, source is B

    def entry_by_exact_name(self, pack, name):
        if not pack:
            return None
        for e in pack.anim_files:
            if e.display_name.lower() == name.lower():
                return e
        return None

    def resolve_pair_names_to_entries(self, pairs):
        """Resolve Selection Center pair names directly against loaded packs.

        This avoids Treeview selection ordering bugs where tkinter returns selected
        rows in visible/index order instead of preset order.
        """
        pc_is_a, rvb_is_a = self.side_for_pc_and_rvb()
        dest_pack = self.pack_a if pc_is_a else self.pack_b
        src_pack = self.pack_a if rvb_is_a else self.pack_b

        resolved = []
        missing = []
        for dest_name, src_name in pairs:
            dest = self.entry_by_exact_name(dest_pack, dest_name)
            src = self.entry_by_exact_name(src_pack, src_name)
            if dest is None or src is None:
                missing.append((dest_name, src_name, dest is not None, src is not None))
                continue
            resolved.append((dest, src))
        return dest_pack, src_pack, resolved, missing

    def preview_pair_name_validation(self, pairs):
        dest_pack, src_pack, resolved, missing = self.resolve_pair_names_to_entries(pairs)
        rows = []
        for i, (dest, src) in enumerate(resolved, start=1):
            ok, reason = same_size_ok(src, dest, self.strict_var.get())
            rows.append({
                "pair": i,
                "pc_destination": dest.display_name,
                "source_payload": src.display_name,
                "dest_size": dest.total_size,
                "source_size": src.total_size,
                "dest_components": "/".join(map(str, dest.component_sizes)),
                "source_components": "/".join(map(str, src.component_sizes)),
                "status": "PASS" if ok else "FAIL",
                "reason": reason,
            })
        return dest_pack, src_pack, resolved, missing, rows

    def patch_selection_center_pairs_direct(self, pairs):
        """Patch the Selection Center pair list directly by names in preset order.

        v2.10 guard: same-name reference/control rows are not real swaps.
        If the caller passes only same-name rows, block the patch so the tool does
        not appear to patch a candidate when it would produce no changed animation.
        """
        if not pairs:
            raise ValueError("Selection Center pair list is empty.")
        status, real_pairs, reference_pairs = preset_patchability_status(pairs)
        if status == "REFERENCE_ONLY_NO_PATCH":
            examples = "\n".join([f"- {d} <- {s}" for d, s in reference_pairs[:10]])
            raise ValueError(
                "v2.10 blocked this patch because every row is a same-name reference/control row.\n\n"
                "These are useful for reports, but they are not real restored swaps and may patch the same animation back into itself.\n\n"
                f"Examples:\n{examples}\n\nChoose a preset with different source payload names."
            )
        if status == "MIXED_SKIPS_REFERENCE_ROWS":
            self.write(f"\nv2.10: skipping {len(reference_pairs)} same-name reference row(s); patching {len(real_pairs)} real swap row(s).\n")
            pairs = real_pairs
        dest_pack, src_pack, resolved, missing, rows = self.preview_pair_name_validation(pairs)
        if missing:
            msg = "Some preset names were not found in the loaded packs:\n\n"
            for dest, src, pc_ok, rvb_ok in missing[:15]:
                msg += f"- {dest} <- {src} | PC found={pc_ok} Source found={rvb_ok}\n"
            raise ValueError(msg)

        failures = [r for r in rows if r["status"] != "PASS"]
        if failures:
            msg = "Selection Center pair validation failed:\n\n"
            for r in failures[:10]:
                msg += (
                    f"Pair {r['pair']}: {r['pc_destination']} <- {r['source_payload']}\n"
                    f"source={r['source_size']} dest={r['dest_size']} | {r['reason']}\n\n"
                )
            raise ValueError(msg + "Fix the preset/pair list or patch one at a time.")

        preview = "\n".join([f"{r['pair']}. {r['pc_destination']} <- {r['source_payload']} ({r['dest_size']} bytes)" for r in rows[:20]])
        if len(rows) > 20:
            preview += f"\n...and {len(rows)-20} more."
        if not messagebox.askyesno(
            "Confirm Selection Center direct patch",
            f"Patch {len(resolved)} preset pair(s) into ONE new PC copy?\n\n{preview}\n\n"
            "This uses exact preset order by name, not Treeview selection order."
        ):
            return

        out = filedialog.asksaveasfilename(
            title="Save Selection Center patched PCPACK copy",
            defaultextension=".PCPACK",
            initialfile=Path(dest_pack.path).stem + f"_SELECTION_CENTER_{len(resolved)}_ANIM_TEST.PCPACK",
            filetypes=[("PCPACK","*.PCPACK"),("All files","*.*")]
        )
        if not out:
            return

        log = patch_pc_anim_copy_many(dest_pack, src_pack, resolved, Path(out), self.strict_var.get(), allow_x360_source=True)
        extra = {
            "mode_detail": "SELECTION_CENTER_DIRECT_NAME_ORDER",
            "preset_pairs": [{"pc_destination": d, "source_payload": s} for d, s in pairs],
            "validated_pairs": rows,
        }
        (Path(out).parent / (Path(out).stem + "_SELECTION_CENTER_DIRECT_PAIRS.json")).write_text(json.dumps(extra, indent=2), encoding="utf-8")
        self.write(f"\nSelection Center DIRECT PATCH saved: {out}\n")
        for r in rows:
            self.write(f"{r['pair']}. {r['pc_destination']} <- {r['source_payload']} | {r['status']} {r['reason']}\n")
        messagebox.showinfo(
            "Selection Center direct patch complete",
            f"Saved patched PC copy:\n{out}\n\nPairs patched: {log['pair_count']}"
        )


    def apply_pair_names_to_main_selection(self, pairs):
        """Select PC destination names and source names in the main Treeviews."""
        pc_is_a, rvb_is_a = self.side_for_pc_and_rvb()
        self.reset_search_filter_for_pair_apply()

        pc_tree = self.tree_a if pc_is_a else self.tree_b
        rvb_tree = self.tree_a if rvb_is_a else self.tree_b
        pc_tree.selection_remove(pc_tree.selection())
        rvb_tree.selection_remove(rvb_tree.selection())

        pc_iids = []
        rvb_iids = []
        missing = []
        for dest_name, src_name in pairs:
            pc_iid = self.find_visible_iid_by_name(pc_is_a, dest_name)
            rvb_iid = self.find_visible_iid_by_name(rvb_is_a, src_name)
            if pc_iid is None or rvb_iid is None:
                missing.append((dest_name, src_name, pc_iid is not None, rvb_iid is not None))
                continue
            pc_iids.append(pc_iid)
            rvb_iids.append(rvb_iid)

        if pc_iids:
            pc_tree.selection_set(pc_iids)
            pc_tree.see(pc_iids[0])
        if rvb_iids:
            rvb_tree.selection_set(rvb_iids)
            rvb_tree.see(rvb_iids[0])
        self.update_selection_labels()

        if missing:
            msg = "Some preset names were not found in the currently loaded packs:\n\n"
            for dest, src, pc_ok, rvb_ok in missing[:12]:
                msg += f"- {dest} <- {src} | PC found={pc_ok} Source found={rvb_ok}\n"
            if len(missing) > 12:
                msg += f"...and {len(missing)-12} more.\n"
            messagebox.showwarning("Selection Center missing names", msg)
        self.selection_center_pairs = list(pairs)
        self.selection_center_active = True
        self.write(f"\nSelection Center applied {len(pc_iids)} pair(s) to main lists. Pair order stored by exact names for v2.2 direct patch.\n")
        return len(pc_iids), missing

    def current_main_selection_pairs_by_order(self):
        """Build (pc destination name, source name) pairs from the current main list selections."""
        pc_is_a, rvb_is_a = self.side_for_pc_and_rvb()
        pc_entries = self.selected_many(pc_is_a)
        rvb_entries = self.selected_many(rvb_is_a)

        if len(pc_entries) != len(rvb_entries):
            raise ValueError(
                f"Main selection count mismatch.\n\nPack A destination selected: {len(pc_entries)}\n"
                f"Pack B source selected: {len(rvb_entries)}\n\n"
                "Select the same number on both sides before using Add Current Main Selection."
            )
        return [(d.display_name, s.display_name) for d, s in zip(pc_entries, rvb_entries)]



    def multi_selection_center(self):
        """Release-only preset center with clean animation-changing presets and no same-name/no-change patching."""
        try:
            if not self.pack_a or not self.pack_b:
                messagebox.showinfo("Load packs first", "Use LOAD / VERIFY PACKS first, then open Release Preset Center.")
                return
            self.side_for_pc_and_rvb()
        except Exception as e:
            messagebox.showerror("Release Preset Center", str(e))
            return

        win = tk.Toplevel(self.root)
        win.title("SM3 ANIMATION SWAPPER RELEASE v1.14 - Multi Selection Center")
        apply_app_icon(win)
        win.geometry("1120x680")
        win.minsize(940, 540)
        win.transient(self.root)

        selected_pairs = []

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(
            top,
            text="Multi Selection Center: add release presets or manual pairs, review swaps, then patch one new copy. Pack B can be PC or Xbox/RVB. Same-name/no-change rows are blocked.",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            top,
            text="Release workflow: choose presets, verify selected pairs, and save a new patched copy.",
            style="Warn.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(win, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(1, weight=1)

        ttk.Label(body, text="Release presets").grid(row=0, column=0, sticky="w")
        # Release v1.8 scrollbar fix: both list boxes now have dedicated vertical + horizontal scrollbars.
        preset_frame = ttk.Frame(body)
        preset_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        preset_frame.rowconfigure(0, weight=1)
        preset_frame.columnconfigure(0, weight=1)
        preset_list = tk.Listbox(preset_frame, exportselection=False, height=18, selectmode="browse")
        preset_y = ttk.Scrollbar(preset_frame, orient="vertical", command=preset_list.yview)
        preset_x = ttk.Scrollbar(preset_frame, orient="horizontal", command=preset_list.xview)
        preset_list.configure(yscrollcommand=preset_y.set, xscrollcommand=preset_x.set)
        preset_list.grid(row=0, column=0, sticky="nsew")
        preset_y.grid(row=0, column=1, sticky="ns")
        preset_x.grid(row=1, column=0, sticky="ew")
        for name, pairs in MULTI_SELECTION_PRESETS.items():
            status, real, reference = preset_patchability_status(pairs)
            # Release UI should only show real animation-changing presets.
            if real:
                preset_list.insert("end", name)

        ttk.Label(body, text="Selection box - Pack A destination <- Pack B source payload").grid(row=0, column=1, sticky="w")
        pair_frame = ttk.Frame(body)
        pair_frame.grid(row=1, column=1, sticky="nsew")
        pair_frame.rowconfigure(0, weight=1)
        pair_frame.columnconfigure(0, weight=1)
        pair_list = tk.Listbox(pair_frame, exportselection=False, height=18, selectmode="extended")
        pair_y = ttk.Scrollbar(pair_frame, orient="vertical", command=pair_list.yview)
        pair_x = ttk.Scrollbar(pair_frame, orient="horizontal", command=pair_list.xview)
        pair_list.configure(yscrollcommand=pair_y.set, xscrollcommand=pair_x.set)
        pair_list.grid(row=0, column=0, sticky="nsew")
        pair_y.grid(row=0, column=1, sticky="ns")
        pair_x.grid(row=1, column=0, sticky="ew")

        def _bind_listbox_mousewheel(lb):
            def _wheel(event, box=lb):
                if getattr(event, "num", None) == 4:
                    box.yview_scroll(-3, "units")
                elif getattr(event, "num", None) == 5:
                    box.yview_scroll(3, "units")
                else:
                    box.yview_scroll(int(-1 * (event.delta / 120)) * 3, "units")
                return "break"
            lb.bind("<MouseWheel>", _wheel)
            lb.bind("<Button-4>", _wheel)
            lb.bind("<Button-5>", _wheel)

        _bind_listbox_mousewheel(preset_list)
        _bind_listbox_mousewheel(pair_list)

        status_var = tk.StringVar(value="No preset loaded.")
        ttk.Label(body, textvariable=status_var, style="Info.TLabel").grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        def refresh_pair_box():
            pair_list.delete(0, "end")
            real, reference = split_real_and_reference_pairs(selected_pairs)
            for dest, src in selected_pairs:
                label = f"{dest} <- {src}"
                if is_noop_same_name_pair((dest, src)):
                    label += "   [BLOCKED: SAME-NAME / NO CHANGE]"
                pair_list.insert("end", label)
            if reference and not real:
                status_var.set(f"Blocked: {len(reference)} same-name/no-change row(s). Nothing real to patch.")
            elif reference and real:
                status_var.set(f"Ready: {len(real)} real swap(s). {len(reference)} same-name row(s) will be skipped.")
            else:
                status_var.set(f"Ready: {len(real)} real swap pair(s).")

        def load_selected_preset():
            sel = preset_list.curselection()
            if not sel:
                messagebox.showinfo("Select preset", "Select a release preset first.", parent=win)
                return
            name = preset_list.get(sel[0])
            pairs = list(MULTI_SELECTION_PRESETS.get(name, []))
            status, real, reference = preset_patchability_status(pairs)
            selected_pairs.clear()
            selected_pairs.extend(real)
            refresh_pair_box()
            info = PRESET_RELEASE_INFO.get(name, {})
            status_var.set(f"Loaded {name}: {len(real)} real swap(s). Risk: {info.get('risk', 'UNKNOWN')}")

        def add_selected_preset():
            sel = preset_list.curselection()
            if not sel:
                messagebox.showinfo("Select preset", "Select a release preset first.", parent=win)
                return
            name = preset_list.get(sel[0])
            status, real, reference = preset_patchability_status(MULTI_SELECTION_PRESETS.get(name, []))
            added = 0
            for pair in real:
                if pair not in selected_pairs:
                    selected_pairs.append(pair)
                    added += 1
            refresh_pair_box()
            status_var.set(f"Added {added} real swap pair(s) from {name}.")

        def remove_selected_pair():
            sel = list(pair_list.curselection())
            if not sel:
                return
            for idx in sorted(sel, reverse=True):
                if 0 <= idx < len(selected_pairs):
                    selected_pairs.pop(idx)
            refresh_pair_box()

        def clear_pairs():
            selected_pairs.clear()
            refresh_pair_box()

        def patchable_pairs_or_warn(action_name):
            status, real, reference = preset_patchability_status(selected_pairs)
            if not selected_pairs:
                messagebox.showinfo("Selection box empty", "Load or add a release preset first.", parent=win)
                return None
            if status == "REFERENCE_ONLY_NO_PATCH":
                messagebox.showwarning(
                    "No-change preset blocked",
                    "This selection contains only same-name/no-change rows.\n\n"
                    "Example: gobairturbo <- gobairturbo\n\n"
                    "That patches the same animation back into itself, so Release v1.8 blocks it.",
                    parent=win,
                )
                self.write(f"\nRelease v1.8 blocked no-change preset for: {action_name}\n")
                return None
            if reference and real:
                messagebox.showinfo(
                    "Same-name rows skipped",
                    f"Using {len(real)} real swap row(s). Skipping {len(reference)} same-name/no-change row(s).",
                    parent=win,
                )
            return real

        def apply_to_main():
            pairs_to_apply = patchable_pairs_or_warn("Apply To Main Lists")
            if pairs_to_apply is None:
                return
            count, missing = self.apply_pair_names_to_main_selection(pairs_to_apply)
            if count:
                messagebox.showinfo(
                    "Applied",
                    f"Applied {count} real swap pair(s) to the main lists.\n\n"
                    "Now use PATCH SELECTED PAIR or Apply + Patch Now.",
                    parent=win,
                )
            else:
                messagebox.showwarning("Nothing applied", "No matching real swap pairs were found in the loaded packs.", parent=win)

        def apply_and_patch():
            pairs_to_patch = patchable_pairs_or_warn("Apply + Patch Now")
            if pairs_to_patch is None:
                return
            count, missing = self.apply_pair_names_to_main_selection(pairs_to_patch)
            if count:
                win.destroy()
                try:
                    self.patch_selection_center_pairs_direct(list(pairs_to_patch))
                except Exception as exc:
                    messagebox.showerror("Release preset patch failed", str(exc))
                    self.write(f"ERROR: {exc}\n")

        def add_current_main_selection():
            try:
                pairs = self.current_main_selection_pairs_by_order()
                # Keep only real, different-source rows.
                real, reference = split_real_and_reference_pairs(pairs)
                added = 0
                for pair in real:
                    if pair not in selected_pairs:
                        selected_pairs.append(pair)
                        added += 1
                refresh_pair_box()
                status_var.set(f"Added {added} real pair(s) from current main selection. Same-name rows ignored.")
            except Exception as exc:
                messagebox.showerror("Add Current Selection failed", str(exc), parent=win)

        def export_selected_preset_json():
            sel = preset_list.curselection()
            if not sel:
                messagebox.showinfo("Select preset", "Select a release preset first.", parent=win)
                return
            name = preset_list.get(sel[0])
            pairs = MULTI_SELECTION_PRESETS.get(name, [])
            status, real, reference = preset_patchability_status(pairs)
            out = filedialog.asksaveasfilename(
                title="Export selected preset JSON",
                defaultextension=".json",
                initialfile=re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") + ".json",
                filetypes=[("JSON preset", "*.json"), ("All files", "*.*")],
            )
            if not out:
                return
            payload = {
                "schema": "SM3_ANIM_SWAP_RELEASE_PRESET_v1",
                "tool_build": "SM3_ANIMATION_SWAPPER_RELEASE_v1_14",
                "preset_name": name,
                "release_info": PRESET_RELEASE_INFO.get(name, {}),
                "real_swap_pair_count": len(real),
                "pairs": [
                    {"pc_destination": d, "source_payload": src, "row_kind": "REAL_SWAP_DIFFERENT_SOURCE"}
                    for d, src in real
                ],
                "warnings": [
                    "Patch the user's own clean PC pack and save a new copy.",
                    "Do not distribute original game PCPACK/XEPACK files.",
                    "Same-name/no-change rows are blocked.",
                ],
            }
            Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            status_var.set(f"Exported preset JSON: {Path(out).name}")
            self.write(f"\nExported preset JSON: {out}\n")

        def load_preset_json():
            path = filedialog.askopenfilename(
                title="Load preset JSON",
                filetypes=[("JSON preset", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return
            try:
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                raw_pairs = data.get("pairs") or []
                parsed = []
                for item in raw_pairs:
                    if isinstance(item, dict):
                        d = item.get("pc_destination") or item.get("dest") or item.get("destination")
                        src = item.get("source_payload") or item.get("source_payload") or item.get("source")
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        d, src = item[0], item[1]
                    else:
                        continue
                    if d and src:
                        parsed.append((str(d), str(src)))
                real, reference = split_real_and_reference_pairs(parsed)
                if not real:
                    raise ValueError("No real animation-changing pairs found. Same-name/no-change rows are blocked.")
                selected_pairs.clear()
                selected_pairs.extend(real)
                refresh_pair_box()
                status_var.set(f"Loaded JSON preset: {Path(path).name} ({len(real)} real swap pair(s))")
                self.write(f"\nLoaded preset JSON: {path}\n")
            except Exception as exc:
                messagebox.showerror("Load preset JSON failed", str(exc), parent=win)

        def load_red_5pack():
            key = "RVB_RED_COMBAT_RESTORED_5PACK - RELEASE STABLE"
            status, real, reference = preset_patchability_status(MULTI_SELECTION_PRESETS[key])
            selected_pairs.clear()
            selected_pairs.extend(real)
            refresh_pair_box()
            status_var.set("Loaded RVB Red Combat Restored 5-Pack.")

        btns = ttk.Frame(win, padding=8)
        btns.pack(fill="x")
        ttk.Button(btns, text="Load Preset", command=load_selected_preset).pack(side="left", padx=4)
        ttk.Button(btns, text="Add Preset", command=add_selected_preset).pack(side="left", padx=4)
        ttk.Button(btns, text="Load Red 5-Pack", command=load_red_5pack).pack(side="left", padx=4)
        ttk.Button(btns, text="Add Current Selection", command=add_current_main_selection).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove Selected Pair", command=remove_selected_pair).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear", command=clear_pairs).pack(side="left", padx=4)
        ttk.Button(btns, text="Apply To Main Lists", command=apply_to_main).pack(side="right", padx=4)
        ttk.Button(btns, text="Apply + Patch Now", command=apply_and_patch).pack(side="right", padx=4)

        note = (
            "Release preset list reviewed: no same-name/no-change presets are shown. "
            "Only real animation-changing presets are shown. Same-name/no-change rows stay blocked."
        )
        ttk.Label(win, text=note, wraplength=860, foreground="#5A5A5A", padding=8).pack(fill="x")

        if preset_list.size():
            preset_list.selection_set(0)
            preset_list.see(0)


    def swing_test_lab(self):
        """v2.2 wider one-slot swing/dive/jump testing window."""
        try:
            if not self.pack_a or not self.pack_b:
                messagebox.showinfo("Scan packs first", "Scan one PC destination pack and one source pack first.")
                return
            dest_pack, src_pack = source_dest_for_rvb_mode(self.pack_a, self.pack_b)
        except Exception as e:
            messagebox.showerror("Swing Test Lab", str(e))
            return

        candidates_cache = {}
        target_mode_var = tk.StringVar(value="GUIDED_ORDER")
        candidate_mode_var = tk.StringVar(value="STRICT_SAFE")
        source_filter_var = tk.StringVar(value="")
        rows = []

        win = tk.Toplevel(self.root)
        win.title("SM3 ANIMATION SWAPPER RELEASE v1.14 - Swing / Dive / Jump Lab")
        apply_app_icon(win)
        win.geometry("1320x780")
        win.minsize(1060, 620)
        win.transient(self.root)

        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        ttk.Label(
            top,
            text="Swing/Dive/Jump Lab v2.2: wider discovery, same safety. Patch ONE PC slot into ONE NEW copy only.",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w")
        ttk.Label(
            top,
            text="v2.2 adds target modes + candidate modes. Every patch still requires same component size/layout and a real PC destination slot.",
            style="Warn.TLabel",
            wraplength=1240,
        ).pack(anchor="w", pady=(3, 0))

        controls = ttk.LabelFrame(top, text="v2.2 discovery controls", padding=6)
        controls.pack(fill="x", pady=(6, 0))
        ttk.Label(controls, text="Target view:").pack(side="left", padx=(0, 4))
        target_combo = ttk.Combobox(
            controls,
            textvariable=target_mode_var,
            state="readonly",
            width=24,
            values=["GUIDED_ORDER", "PROMISING_RESULTS", "ALL_SWING_PC_SLOTS", "COMPATIBLE_ONLY"],
        )
        target_combo.pack(side="left", padx=(0, 10))
        ttk.Label(controls, text="Candidate mode:").pack(side="left", padx=(0, 4))
        cand_combo = ttk.Combobox(
            controls,
            textvariable=candidate_mode_var,
            state="readonly",
            width=22,
            values=["STRICT_SAFE", "FAMILY_MATCH", "STRONG_VISIBLE", "SAME_SIZE_ANY_NAME", "RISKY_REPORT_ONLY"],
        )
        cand_combo.pack(side="left", padx=(0, 10))
        ttk.Label(controls, text="Source search:").pack(side="left", padx=(0, 4))
        source_entry = ttk.Entry(controls, textvariable=source_filter_var, width=26)
        source_entry.pack(side="left", padx=(0, 10))

        body = ttk.PanedWindow(win, orient="vertical")
        body.pack(fill="both", expand=True, padx=8, pady=4)

        upper = ttk.Frame(body, padding=4)
        lower = ttk.Frame(body, padding=4)
        body.add(upper, weight=2)
        body.add(lower, weight=1)

        cols = (
            "order", "pc_destination_name", "label", "risk", "target_groups", "dest_exists",
            "same_name_patchable", "same_name_status", "same_size_candidate_count", "best_candidate_source", "best_candidate_note"
        )
        ttk.Label(upper, text="PC destination slots. Use PROMISING_RESULTS first, then ALL_SWING_PC_SLOTS / FAMILY_MATCH for wider search.").pack(anchor="w")
        tree = ttk.Treeview(upper, columns=cols, show="headings", selectmode="browse", height=13)
        for c in cols:
            tree.heading(c, text=c)
        tree.column("order", width=55, stretch=False)
        tree.column("pc_destination_name", width=190, stretch=False)
        tree.column("label", width=285, stretch=True)
        tree.column("risk", width=165, stretch=False)
        tree.column("target_groups", width=185, stretch=False)
        tree.column("dest_exists", width=80, stretch=False)
        tree.column("same_name_patchable", width=105, stretch=False)
        tree.column("same_name_status", width=190, stretch=False)
        tree.column("same_size_candidate_count", width=90, stretch=False)
        tree.column("best_candidate_source", width=190, stretch=False)
        tree.column("best_candidate_note", width=200, stretch=False)
        y1 = ttk.Scrollbar(upper, orient="vertical", command=tree.yview)
        x1 = ttk.Scrollbar(upper, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y1.set, xscrollcommand=x1.set)
        tree.pack(side="left", fill="both", expand=True)
        y1.pack(side="right", fill="y")
        x1.pack(side="bottom", fill="x")

        lower_left = ttk.Frame(lower)
        lower_left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        lower_right = ttk.Frame(lower)
        lower_right.pack(side="left", fill="both", expand=True)

        ttk.Label(lower_left, text="Same-size/same-layout source candidates for selected PC slot").pack(anchor="w")
        cand_cols = ("source_name", "candidate_note", "risk_label", "exact_name", "family_match", "source_groups", "score", "source_size", "source_components", "validation")
        cand_tree = ttk.Treeview(lower_left, columns=cand_cols, show="headings", selectmode="browse", height=9)
        for c in cand_cols:
            cand_tree.heading(c, text=c)
        cand_tree.column("source_name", width=230, stretch=True)
        cand_tree.column("candidate_note", width=190, stretch=False)
        cand_tree.column("risk_label", width=160, stretch=False)
        cand_tree.column("exact_name", width=70, stretch=False)
        cand_tree.column("family_match", width=90, stretch=False)
        cand_tree.column("source_groups", width=180, stretch=False)
        cand_tree.column("score", width=70, stretch=False)
        cand_tree.column("source_size", width=90, stretch=False)
        cand_tree.column("source_components", width=110, stretch=False)
        cand_tree.column("validation", width=190, stretch=True)
        y2 = ttk.Scrollbar(lower_left, orient="vertical", command=cand_tree.yview)
        x2 = ttk.Scrollbar(lower_left, orient="horizontal", command=cand_tree.xview)
        cand_tree.configure(yscrollcommand=y2.set, xscrollcommand=x2.set)
        cand_tree.pack(side="left", fill="both", expand=True)
        y2.pack(side="right", fill="y")
        x2.pack(side="bottom", fill="x")

        status = tk.Text(lower_right, height=9, wrap="word")
        status.pack(fill="both", expand=True)

        def log(msg):
            status.insert("end", msg)
            status.see("end")

        def current_cache_key(name):
            return (name.lower(), candidate_mode_var.get(), source_filter_var.get().strip().lower())

        def selected_target_name():
            sel = tree.selection()
            if not sel:
                return None
            idx = int(sel[0])
            if idx < 0 or idx >= len(rows):
                return None
            return rows[idx]["pc_destination_name"]

        def selected_candidate_name():
            sel = cand_tree.selection()
            if not sel:
                return None
            return cand_tree.item(sel[0], "values")[0]

        def refresh_rows(select_name=None):
            nonlocal rows
            tree.delete(*tree.get_children())
            cand_tree.delete(*cand_tree.get_children())
            candidates_cache.clear()
            rows = build_swing_lab_rows(dest_pack, src_pack, target_mode_var.get(), candidate_mode_var.get(), source_filter_var.get())
            for idx, r in enumerate(rows):
                tree.insert("", "end", iid=str(idx), values=tuple(r.get(c, "") for c in cols))
            log(f"\nRefreshed rows: {len(rows)} | target={target_mode_var.get()} | candidate_mode={candidate_mode_var.get()} | source_search='{source_filter_var.get()}'\n")
            if not rows:
                log("No rows found. Try SAME_SIZE_ANY_NAME or clear Source search.\n")
                return
            choose = "0"
            if select_name:
                for i, r in enumerate(rows):
                    if r["pc_destination_name"].lower() == select_name.lower():
                        choose = str(i)
                        break
            tree.selection_set(choose)
            tree.see(choose)
            fill_candidates_for_selected()

        def fill_candidates_for_selected(_event=None):
            cand_tree.delete(*cand_tree.get_children())
            name = selected_target_name()
            if not name:
                return
            d = self.find_loaded_entry_by_name(dest_pack, name)
            log(f"\nSelected PC slot: {name}\n")
            if not d:
                log("PC destination slot missing in the loaded PC pack. Cannot patch this slot.\n")
                return
            key = current_cache_key(name)
            cands = candidates_cache.get(key)
            if cands is None:
                cands = swing_source_candidates_for_dest(src_pack, d, limit=750, mode=candidate_mode_var.get(), text_filter=source_filter_var.get())
                candidates_cache[key] = cands
            for idx, r in enumerate(cands):
                cand_tree.insert("", "end", iid=str(idx), values=tuple(r.get(c, "") for c in cand_cols))
            if cands:
                cand_tree.selection_set("0")
                cand_tree.see("0")
                log(f"Candidates found: {len(cands)}. Top source: {cands[0]['source_name']} | {cands[0].get('candidate_note','')} | {cands[0].get('risk_label','')}\n")
            else:
                log("No same-size/same-layout source candidates in this mode/search. Try FAMILY_MATCH, STRONG_VISIBLE, SAME_SIZE_ANY_NAME, or clear Source search.\n")

        tree.bind("<<TreeviewSelect>>", fill_candidates_for_selected)
        target_combo.bind("<<ComboboxSelected>>", lambda _e: refresh_rows())
        cand_combo.bind("<<ComboboxSelected>>", lambda _e: refresh_rows(selected_target_name()))
        source_entry.bind("<Return>", lambda _e: refresh_rows(selected_target_name()))

        def write_lab_reports():
            folder = filedialog.askdirectory(title="Choose output folder for Swing/Dive Lab reports", parent=win)
            if not folder:
                return
            folder = Path(folder)
            write_csv(folder / "SWING_DIVE_JUMP_TEST_ORDER_v2_2_CURRENT_VIEW.csv", rows)
            avoid_rows = build_rvb_red_only_avoid_rows(dest_pack, src_pack)
            write_csv(folder / "RVB_RED_ONLY_AVOID_FIRST_SLOT_REVIEW_v2_2.csv", avoid_rows)
            # Write candidate CSV for selected row and a compact all-row top-candidate index.
            index_rows = []
            for r in rows:
                d = self.find_loaded_entry_by_name(dest_pack, r["pc_destination_name"])
                if not d:
                    continue
                cands = swing_source_candidates_for_dest(src_pack, d, limit=25, mode=candidate_mode_var.get(), text_filter=source_filter_var.get())
                for c in cands[:5]:
                    index_rows.append(c)
            write_csv(folder / "SWING_DIVE_TOP_CANDIDATES_CURRENT_MODE_v2_2.csv", index_rows)
            name = selected_target_name()
            if name:
                d = self.find_loaded_entry_by_name(dest_pack, name)
                if d:
                    cands = swing_source_candidates_for_dest(src_pack, d, limit=750, mode=candidate_mode_var.get(), text_filter=source_filter_var.get())
                    write_csv(folder / f"CANDIDATES_FOR_{clean_name(name)}_{candidate_mode_var.get()}_v2_2.csv", cands)
            readme = folder / "README_SWING_DIVE_WIDER_CANDIDATE_LAB_v2_2.txt"
            readme.write_text(
                "SM3 v2.2 Swing/Dive/Jump Wider Candidate Lab\n"
                "============================================================\n"
                "v2.2 keeps patch safety strict: one PC slot, one source payload, same component layout, new PCPACK copy.\n"
                "Modes:\n"
                "- STRICT_SAFE: exact/same-family safer lane.\n"
                "- FAMILY_MATCH: wider same-family same-size/layout candidates.\n"
                "- STRONG_VISIBLE: prioritizes swing/release/dive-style sources for more visible tests.\n"
                "- SAME_SIZE_ANY_NAME: broad discovery pool; manual approval only.\n"
                "- RISKY_REPORT_ONLY: shows wall/launch/dive risky candidates; patch one-at-a-time only if you accept risk.\n"
                "Current known promising results:\n"
                "- sm3jmpsprint2dive <- bs3swgchgrls2dive : best current result but subtle.\n"
                "- sm3slowswing270 <- sm3slowswing180 : safe slow-swing loop result.\n",
                encoding="utf-8"
            )
            log(f"\nReports written to: {folder}\n")
            messagebox.showinfo("Swing Lab reports", f"Reports written to:\n{folder}", parent=win)

        def patch_selected_candidate_only():
            name = selected_target_name()
            src_name = selected_candidate_name()
            if not name or not src_name:
                messagebox.showinfo("Select target and source", "Select one PC target row and one source candidate row first.", parent=win)
                return
            dest_entry = self.find_loaded_entry_by_name(dest_pack, name)
            src_entry = self.find_loaded_entry_by_name(src_pack, src_name)
            if not dest_entry or not src_entry:
                messagebox.showerror("Missing entry", "Could not resolve selected PC destination or source entry.", parent=win)
                return
            ok, reason = same_size_ok(src_entry, dest_entry, True)
            if not ok:
                messagebox.showerror("Validation failed", f"{name} <- {src_name}\n\n{reason}", parent=win)
                return
            if src_entry.pack_kind == "XEPACK_RAW_STRING_SCAN" or not src_pack.combined_blob(src_entry):
                messagebox.showerror("Source bytes missing", "Selected source is name-only or has no payload bytes.", parent=win)
                return
            risk = swing_lab_risk_for_pair(name, src_name)
            warning = (
                f"Patch ONE NEW PC copy?\n\n"
                f"PC slot kept:\n{name}\n\n"
                f"Source payload from:\n{src_name}\n\n"
                f"Candidate mode:\n{candidate_mode_var.get()}\n"
                f"Risk label:\n{risk}\n"
                f"Validation:\n{reason}\n\n"
                "Test this copy alone. Do not combine with other swing/dive tests yet.\n\n"
                "Important: v2.2 may show broader candidates. Same-size/layout does not guarantee gameplay safety."
            )
            if not messagebox.askyesno("Confirm one-slot swing test", warning, parent=win):
                return
            out = filedialog.asksaveasfilename(
                title="Save ONE-SLOT Swing/Dive test PC PCPACK copy",
                defaultextension=".PCPACK",
                filetypes=[("PCPACK", "*.PCPACK"), ("All files", "*.*")],
                initialfile=f"{Path(dest_pack.path).stem}_V22_{clean_name(name)}_FROM_{clean_name(src_name)}_ONLY.PCPACK",
                parent=win,
            )
            if not out:
                return
            logdata = patch_pc_anim_copy_many(dest_pack, src_pack, [(dest_entry, src_entry)], Path(out), strict_components=True, allow_x360_source=True)
            log(f"\nPATCHED ONE-SLOT SWING TEST:\n{out}\n{name} <- {src_name}\n")
            self.write(f"\nSwing/Dive Lab v2.2 one-slot patch saved: {out}\n{name} <- {src_name}\n")
            messagebox.showinfo("One-slot swing test saved", f"Saved:\n{out}\n\nPatched pair count: {logdata['pair_count']}", parent=win)

        def add_to_main_selection():
            name = selected_target_name()
            src_name = selected_candidate_name()
            if not name or not src_name:
                return
            try:
                count, missing = self.apply_pair_names_to_main_selection([(name, src_name)])
                log(f"\nApplied to main selection: {count} pair(s). Missing: {missing}\n")
            except Exception as exc:
                messagebox.showerror("Apply to main failed", str(exc), parent=win)

        def jump_to_current_best():
            target_mode_var.set("PROMISING_RESULTS")
            candidate_mode_var.set("STRONG_VISIBLE")
            source_filter_var.set("")
            refresh_rows("sm3jmpsprint2dive")

        def jump_to_slow_swing():
            target_mode_var.set("PROMISING_RESULTS")
            candidate_mode_var.set("FAMILY_MATCH")
            source_filter_var.set("")
            refresh_rows("sm3slowswing270")

        btns = ttk.Frame(win, padding=8)
        btns.pack(fill="x")
        ttk.Button(btns, text="Load Preset -> Selection Box", command=load_selected_preset).pack(side="left", padx=4)
        ttk.Button(btns, text="Add Preset", command=add_selected_preset).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove Selected Pair", command=remove_selected_pair).pack(side="left", padx=4)
        ttk.Button(btns, text="Clear Selection Box", command=clear_pairs).pack(side="left", padx=4)
        ttk.Button(btns, text="Apply + Patch Now", command=apply_and_patch).pack(side="right", padx=4)

        note = (
            "Release build: choose a preset, verify packs, then Apply + Patch Now. "
            "Only real animation-changing presets are listed."
        )
        ttk.Label(win, text=note, wraplength=820, foreground="#5A5A5A", padding=8).pack(fill="x")

        # Auto-select first preset for convenience.
        if preset_list.size():
            preset_list.selection_set(0)
            preset_list.see(0)


    def rvb_to_pc_multi_patch_selected(self):
        try:
            if getattr(self, "selection_center_active", False) and getattr(self, "selection_center_pairs", None):
                if messagebox.askyesno(
                    "Use Selection Center order?",
                    "A Multi Selection Center preset is active.\n\n"
                    "Use the exact preset pair order by name?\n\n"
                    "Choose YES for release presets."
                ):
                    return self.patch_selection_center_pairs_direct(self.selection_center_pairs)

            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")

            if self.pack_a.platform != "PC":
                raise ValueError("Pack A must be the PC destination pack. Pack B is the source side.")
            if self.pack_b.platform not in ("PC", "X360"):
                raise ValueError("Pack B must be a supported source pack: PC or Xbox/RVB.")

            dest_pack, src_pack = self.pack_a, self.pack_b
            dest_entries = self.selected_many(True)
            src_entries = self.selected_many(False)

            if len(dest_entries) != len(src_entries):
                raise ValueError(
                    f"Selection count mismatch.\n\nPack A destination selected: {len(dest_entries)}\n"
                    f"Pack B source selected: {len(src_entries)}\n\n"
                    "Select the same number on both sides. The tool pairs them in visible selection order."
                )

            raw_pairs = list(zip(dest_entries, src_entries))
            pairs = []
            skipped_same = []
            for dest, src in raw_pairs:
                if dest.display_name.lower() == src.display_name.lower():
                    skipped_same.append((dest, src))
                else:
                    pairs.append((dest, src))
            if skipped_same and not pairs:
                examples = "\n".join([f"- {d.display_name} <- {s.display_name}" for d, s in skipped_same[:10]])
                raise ValueError(
                    "Every selected pair is a same-name/no-change row, so release mode blocked the patch.\n\n"
                    f"Examples:\n{examples}\n\nChoose source animations with different names or load a real release preset."
                )
            if skipped_same:
                self.write(f"\nRelease guard: skipped {len(skipped_same)} same-name/no-change selected row(s).\n")

            rows = []
            for i, (dest, src) in enumerate(pairs, start=1):
                ok, reason = same_size_ok(src, dest, self.strict_var.get())
                rows.append({
                    "pair": i,
                    "pc_destination": dest.display_name,
                    "source_payload": src.display_name,
                    "dest_size": dest.total_size,
                    "source_size": src.total_size,
                    "dest_components": "/".join(map(str, dest.component_sizes)),
                    "source_components": "/".join(map(str, src.component_sizes)),
                    "status": "PASS" if ok else "FAIL",
                    "reason": reason,
                })
                if not ok:
                    raise ValueError(
                        f"Pair {i} failed:\n{dest.display_name} <- {src.display_name}\n\n{reason}\n\n"
                        "Fix the selected pair or patch one at a time."
                    )

            preview = "\n".join([f"{r['pair']}. {r['pc_destination']} <- {r['source_payload']} ({r['dest_size']} bytes)" for r in rows[:20]])
            if len(rows) > 20:
                preview += f"\n...and {len(rows)-20} more."
            if not messagebox.askyesno(
                "Confirm multi patch",
                f"Patch {len(pairs)} selected pair(s) into ONE new PC copy?\n\n{preview}\n\n"
                "Test small safe sets first."
            ):
                return

            out = filedialog.asksaveasfilename(
                title="Save MULTI patched PCPACK copy",
                defaultextension=".PCPACK",
                initialfile=Path(dest_pack.path).stem + f"_MULTI_{len(pairs)}_ANIM_SWAP.PCPACK",
                filetypes=[("PCPACK","*.PCPACK"),("All files","*.*")]
            )
            if not out:
                return

            log = patch_pc_anim_copy_many(dest_pack, src_pack, pairs, Path(out), self.strict_var.get(), allow_x360_source=True)
            self.write(f"\nMULTI PATCH saved: {out}\n")
            for r in rows:
                self.write(f"{r['pair']}. {r['pc_destination']} <- {r['source_payload']} | {r['status']} {r['reason']}\n")
            messagebox.showinfo("Multi patch complete", f"Saved patched PC copy:\n{out}\n\nPairs patched: {log['pair_count']}")
        except Exception as e:
            messagebox.showerror("Multi patch failed", str(e))
            self.write(f"ERROR: {e}\n")


    def find_slots_for_selected_source(self):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")

            # Selected source should be on the Xbox/RVB side. Destination is the PC side.
            if self.pack_a.platform == "X360" and self.pack_b.platform == "PC":
                src_entry = self.selected(True)
                dest_pack = self.pack_b
            elif self.pack_b.platform == "X360" and self.pack_a.platform == "PC":
                src_entry = self.selected(False)
                dest_pack = self.pack_a
            else:
                raise ValueError("Need one X360/source side and one PC destination side.")

            if src_entry.pack_kind == "XEPACK_RAW_STRING_SCAN":
                raise ValueError("Selected Xbox/RVB entry is name-only string scan. Use extracted APKF output zip.")

            rows = compatible_dest_slots_for_source(dest_pack, src_entry)
            folder = filedialog.askdirectory(title="Choose compatible slot report folder")
            if not folder:
                return
            out = Path(folder) / f"PC_COMPATIBLE_DEST_SLOTS_FOR_{clean_name(src_entry.display_name)}.csv"
            write_csv(out, rows)

            self.write("\nCompatible PC destination slots report saved:\n")
            self.write(str(out) + "\n")
            distinct_count = sum(1 for r in rows if r.get("candidate_role") == "DISTINCT_SOURCE_PAYLOAD_CANDIDATE")
            same_name_count = sum(1 for r in rows if str(r.get("candidate_role", "")).startswith("SAME_NAME"))
            self.write(f"Compatible slots found: {len(rows)} | distinct source candidates: {distinct_count} | same-name controls: {same_name_count}\n")
            if distinct_count == 0 and same_name_count:
                self.write("v2.8 note: only same-name controls were found; the tool will not call that a real replacement candidate.\n")
            for r in rows[:20]:
                self.write(f"{r.get('candidate_role','')} score={r['family_score']} {r['dest_safety']} DEST {r['dest_name']} <- SRC {r['source_name']} size={r['dest_size']}\n")

            messagebox.showinfo("Compatible slots", f"Saved:\n{out}\n\nCompatible slots found: {len(rows)}\nDistinct source candidates: {distinct_count}\nSame-name controls: {same_name_count}")
        except Exception as e:
            messagebox.showerror("Find slots failed", str(e))
            self.write(f"ERROR: {e}\n")


    def export_lists(self):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Scan first.")
            folder = filedialog.askdirectory(title="Choose output folder")
            if not folder:
                return
            out = Path(folder)
            out.mkdir(parents=True, exist_ok=True)
            write_csv(out/"PACK_A_ANIM_LIST.csv", [e.row() for e in self.pack_a.anim_files])
            write_csv(out/"PACK_B_ANIM_LIST.csv", [e.row() for e in self.pack_b.anim_files])
            write_csv(out/"PACK_A_vs_PACK_B_ANIM_COMPARE.csv", compare_rows(self.pack_a, self.pack_b))
            (out/"PACK_A_DETECT.json").write_text(json.dumps(getattr(self.pack_a, "detect_info", {}), indent=2), encoding="utf-8")
            (out/"PACK_B_DETECT.json").write_text(json.dumps(getattr(self.pack_b, "detect_info", {}), indent=2), encoding="utf-8")
            self.write(f"\nReports saved: {out}\n")
            messagebox.showinfo("Exported", f"Reports saved:\n{out}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def pc_xbox_diff_report(self):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Load/verify packs first.")
            reports = pc_xbox_diff_reports(self.pack_a, self.pack_b)

            # v2.2 clean report rows generated from the stable v0.9 report data.
            same_size_shared = [
                r for r in reports.get("shared_by_name", [])
                if int(r.get("x360_size", -1)) == int(r.get("pc_size", -2))
                and bool(r.get("same_component_layout", False))
            ]
            size_different_shared = [
                r for r in reports.get("shared_by_name", [])
                if not (
                    int(r.get("x360_size", -1)) == int(r.get("pc_size", -2))
                    and bool(r.get("same_component_layout", False))
                )
            ]
            same_size_safe_first = [
                r for r in same_size_shared
                if str(r.get("safety", "")).upper() == "SAFE_FIRST"
            ]
            safe_combat_clean = [
                r for r in reports.get("safe_combat_candidates", [])
                if str(r.get("safety", "")).upper() != "HIGH_RISK"
            ]
            reports["summary"]["same_size_same_layout_shared_rows"] = len(same_size_shared)
            reports["summary"]["size_different_shared_rows"] = len(size_different_shared)
            reports["summary"]["same_size_safe_first_rows"] = len(same_size_safe_first)
            reports["summary"]["safe_combat_clean_rows"] = len(safe_combat_clean)
            reports["summary"]["v2_2_note"] = "Stable build restored from working v0.9 parser base; clean report aliases added."
            folder = filedialog.askdirectory(title="Choose PC vs Xbox diff report output folder")
            if not folder:
                return
            out = Path(folder)
            out.mkdir(parents=True, exist_ok=True)

            write_csv(out/"PC_XBOX_SHARED_BY_NAME.csv", reports["shared_by_name"])
            write_csv(out/"PC_XBOX_SHARED_BY_HASH.csv", reports["shared_by_hash"])

            # Original-compatible names:
            write_csv(out/"XBOX_ONLY_ANIM_NAMES.csv", reports["xbox_only"])
            write_csv(out/"PC_ONLY_ANIM_NAMES.csv", reports["pc_only"])
            write_csv(out/"PC_XBOX_SIZE_COMPARISON_SHARED_NAMES.csv", reports["size_comparison"])
            write_csv(out/"PC_XBOX_SAFE_COMBAT_CANDIDATES.csv", safe_combat_clean)
            write_csv(out/"PC_XBOX_HIGH_RISK_NAMES.csv", reports["high_risk"])

            # Cleaner v1.x names:
            write_csv(out/"XBOX_ONLY_EXTRA_ANIMS.csv", reports["xbox_only"])
            write_csv(out/"PC_ONLY_EXTRA_ANIMS.csv", reports["pc_only"])
            write_csv(out/"PC_XBOX_SAME_SIZE_SHARED_ANIMS.csv", same_size_shared)
            write_csv(out/"PC_XBOX_SIZE_DIFFERENT_RESEARCH_TARGETS.csv", size_different_shared)
            write_csv(out/"PC_XBOX_SAME_SIZE_SAFE_FIRST_TESTS.csv", same_size_safe_first)
            write_csv(out/"PC_XBOX_SAFE_COMBAT_CANDIDATES_CLEAN.csv", safe_combat_clean)

            (out/"PC_XBOX_DIFF_SUMMARY.json").write_text(json.dumps(reports["summary"], indent=2), encoding="utf-8")
            with (out/"PC_XBOX_DIFF_SUMMARY.txt").open("w", encoding="utf-8") as f:
                f.write("============================================================\n")
                f.write("SM3 PC VS XBOX ANIMATION DIFF REPORT v2.2\n")
                f.write("============================================================\n\n")
                for k, v in reports["summary"].items():
                    f.write(f"{k}: {v}\n")
                f.write("\nReports written:\n")
                f.write("- PC_XBOX_SHARED_BY_NAME.csv\n")
                f.write("- PC_XBOX_SHARED_BY_HASH.csv\n")
                f.write("- XBOX_ONLY_EXTRA_ANIMS.csv\n")
                f.write("- PC_ONLY_EXTRA_ANIMS.csv\n")
                f.write("- PC_XBOX_SAME_SIZE_SHARED_ANIMS.csv\n")
                f.write("- PC_XBOX_SIZE_DIFFERENT_RESEARCH_TARGETS.csv\n")
                f.write("- PC_XBOX_SAME_SIZE_SAFE_FIRST_TESTS.csv\n")
                f.write("- PC_XBOX_SAFE_COMBAT_CANDIDATES.csv\n")
                f.write("- PC_XBOX_SAFE_COMBAT_CANDIDATES_CLEAN.csv\n")
                f.write("- PC_XBOX_HIGH_RISK_NAMES.csv\n")

            self.write("\nPC vs Xbox diff reports saved:\n")
            self.write(str(out) + "\n")
            self.write(f"Shared names: {reports['summary']['shared_name_count']} | Xbox-only: {reports['summary']['xbox_only_name_count']} | PC-only: {reports['summary']['pc_only_name_count']}\n")
            messagebox.showinfo("PC vs Xbox Diff Complete", f"Reports saved:\n{out}\n\nShared names: {reports['summary']['shared_name_count']}\nXbox-only: {reports['summary']['xbox_only_name_count']}\nPC-only: {reports['summary']['pc_only_name_count']}")
        except Exception as e:
            messagebox.showerror("PC vs Xbox diff failed", str(e))
            self.write(f"ERROR: {e}\n")


    def find_safe(self):
        try:
            if not self.pack_a or not self.pack_b:
                raise ValueError("Scan first.")
            rows = []
            for a in self.pack_a.anim_files:
                for b in self.pack_b.anim_files:
                    ok, reason = same_size_ok(b, a, True)
                    if not ok:
                        continue
                    rows.append({
                        "score": family_score(a.display_name,b.display_name,a.filename_hash,b.filename_hash),
                        "safety": safety_label(a.display_name,b.display_name),
                        "validation": reason,
                        "dest_name": a.display_name,
                        "dest_hash": hex32(a.filename_hash),
                        "dest_size": a.total_size,
                        "source_name": b.display_name,
                        "source_hash": hex32(b.filename_hash),
                        "source_size": b.total_size,
                        "dest_platform": a.platform,
                        "source_platform": b.platform,
                    })
            rows.sort(key=lambda r: (-r["score"], r["safety"], r["dest_name"]))
            folder = filedialog.askdirectory(title="Choose safe candidate output folder")
            if not folder:
                return
            path = Path(folder)/"SM3_ANIM_SAFE_SAME_SIZE_CANDIDATES_v2_2.csv"
            write_csv(path, rows)
            self.write(f"\nCandidate report saved: {path}\n")
            for r in rows[:20]:
                self.write(f"{r['safety']} score={r['score']} | {r['dest_name']} <- {r['source_name']}\n")
        except Exception as e:
            messagebox.showerror("Candidate finder failed", str(e))

    def diff_scan(self):
        try:
            a = Path(self.a_var.get())
            b = Path(self.b_var.get())
            if not a.exists() or not b.exists():
                raise ValueError("Select Pack A and Pack B first.")
            clean = load_pack_or_extracted(a, "PC")
            edited = load_pack_or_extracted(b, "X360" if b.suffix.lower() in (".xepack", ".zip") else "PC")
            rows, comp_rows, summary = pack_diff_rows(clean, edited)
            folder = filedialog.askdirectory(title="Choose diff output folder")
            if not folder:
                return
            out = Path(folder)
            out.mkdir(parents=True, exist_ok=True)
            write_csv(out/"SAME_PACK_RESOURCE_DIFF.csv", rows)
            write_csv(out/"SAME_PACK_CHANGED_COMPONENTS.csv", comp_rows)
            (out/"SAME_PACK_DIFF_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            (out/"SAME_PACK_DIFF_SUMMARY.txt").write_text("\n".join(f"{k}: {v}" for k,v in summary.items()), encoding="utf-8")
            self.write(f"\nDiff reports saved: {out}\nChanged resources={summary['changed_resource_count']} components={summary['changed_component_count']}\n")
            messagebox.showinfo("Diff complete", f"Reports saved:\n{out}")
        except Exception as e:
            messagebox.showerror("Diff failed", str(e))
            self.write(f"ERROR: {e}\n")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
