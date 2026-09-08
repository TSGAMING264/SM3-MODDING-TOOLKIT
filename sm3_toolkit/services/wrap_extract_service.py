#!/usr/bin/env python3
"""SM3 native WRAP extraction service.

This module turns resources inside the SM3 APKF containers already discovered by
``pack_extract_service`` into standalone exWoS-style ``.wrap.<ext>`` files.

Important design rules:
- extraction only; source packs are never modified;
- retain exact SM3 outer ownership (PACK + O index + outer hash + T class);
- do not invent archive identity for marker-only/compact candidates;
- support the one- and two-component WRAP layouts used by the current SM3 corpus;
- preserve external/global resource references and rewrite internal references as
  relative standalone pointers;
- emit a machine-readable manifest beside ``WRAP_EXTRACTS``.

The implementation is intentionally dependency-free and uses the existing SM3
pack/APKF parser for pack route discovery and resource/component boundaries.
"""
from __future__ import annotations

import json
import struct
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sm3_toolkit.services import pack_extract_service as backend

WRAP_MAGIC = b"WRAP"
PATCH_INDEX_FILENAME_TABLE = 63
MAX_PATCHES = 2_000_000
MAX_GLOBAL_PATCHES = 1_000_000
MAX_WRAP_COMPONENTS = 2


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ValueError(f"u32 outside APKF at 0x{off:X}")
    return struct.unpack_from("<I", data, off)[0]


def _s32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ValueError(f"s32 outside data at 0x{off:X}")
    return struct.unpack_from("<i", data, off)[0]


def _align(value: int, boundary: int) -> int:
    if boundary <= 1:
        return value
    return (value + boundary - 1) & ~(boundary - 1)


def _pad_align(buf: bytearray, boundary: int) -> None:
    # Current SM3 NativeWRAP extractor output uses zero-filled metadata alignment.
    # The loader treats these bytes as padding; keep the runtime-tested SM3 form.
    target = _align(len(buf), boundary)
    if target > len(buf):
        buf.extend(b"\x00" * (target - len(buf)))


def _pack_rel32(buf: bytearray, field_off: int, target_off: int) -> None:
    """Write a 32-bit relative pointer at ``field_off`` to ``target_off``."""
    rel = target_off - field_off
    if not -(1 << 31) <= rel < (1 << 31):
        raise ValueError(f"relative pointer overflow field=0x{field_off:X} target=0x{target_off:X}")
    struct.pack_into("<i", buf, field_off, rel)


def _fourcc(raw: str) -> bytes:
    b = (raw or "").encode("ascii", errors="replace")[:4]
    return b + (b"\x00" * (4 - len(b)))


def _golden_archive_folder(source: backend.APKFSourceSlice) -> str:
    if source.parent_outer_index is None or source.parent_outer_hash is None:
        raise ValueError("WRAP extraction requires authoritative outer APKF ownership")
    t = source.parent_outer_type
    type_text = f"T{t:X}" if t is not None else "TUNK"
    return f"O{source.parent_outer_index:04d}.{backend.hex32(source.parent_outer_hash)}.{type_text}.apkf"


@dataclass
class OrdinaryPatch:
    patch_index: int
    encoded_patch: int
    target_component_index: int
    target_entry_index: int
    target_address: int
    encoded_ref: int
    ref_index: int
    ref_entry_index: int
    ref_address: int
    target_file: Optional[backend.APKFFileEntry] = None
    ref_file: Optional[backend.APKFFileEntry] = None

    @property
    def patch_type(self) -> str:
        return "filename" if self.ref_index == PATCH_INDEX_FILENAME_TABLE else "pointer"


@dataclass
class GlobalPatch:
    encoded_patch: int
    ref_file_type: str
    filename_offset: int
    ref_filename_hash: int
    ref_filename: str
    target_address: int
    target_component_index: int
    target_entry_index: int
    target_value: int
    target_file: Optional[backend.APKFFileEntry] = None


@dataclass
class PatchPlan:
    kind: str  # internal / external / global
    target_offset: int
    ref_component_index: int = -1
    ref_offset: int = 0
    encoded_ref: int = 0
    ref_file_type: str = ""
    ref_filename_hash: int = 0
    global_target_value: int = 0


class WrapAPKFArchive:
    """Adds APKF patch-table knowledge to the toolkit's existing APKF parser."""

    def __init__(self, data: bytes, source: backend.APKFSourceSlice):
        self.data = data
        self.source = source
        self.base = backend.APKFArchive(data, label=source.label)
        self.files = self.base.files
        self.component_headers = self.base.component_headers
        self.component_table_address = int(self.base.header.get("component_table_ptr_effective") or 0)
        self.filename_table_address = self._derive_filename_table_address()
        self.file_ranges: List[Tuple[int, int, backend.APKFFileEntry]] = []
        for f in self.files:
            for start, end in f.component_offsets:
                if 0 <= start < end <= len(self.data):
                    self.file_ranges.append((start, end, f))
        self.file_ranges.sort(key=lambda x: x[0])
        self.file_range_starts = [x[0] for x in self.file_ranges]
        self.file_to_patches: Dict[int, List[Any]] = defaultdict(list)
        self.ordinary_patches: List[OrdinaryPatch] = []
        self.global_patches: List[GlobalPatch] = []
        self.patch_table_offset = 0
        self.global_patch_table_offset = 0
        self._parse_patches()

    def _derive_filename_table_address(self) -> int:
        if not self.base.file_type_headers:
            raise ValueError("APKF has no file table headers")
        last = self.base.file_type_headers[-1]
        p_headers_raw = str(last.get("file_header_table") or "0")
        p_headers = int(p_headers_raw, 16) if p_headers_raw.lower().startswith("0x") else int(p_headers_raw)
        n = int(last.get("n_file_headers") or 0)
        active = int(last.get("n_active_components") or 0)
        end = p_headers + n * (8 + 4 * active)
        if end < 0 or end > len(self.data):
            raise ValueError(f"filename table outside APKF: 0x{end:X}")
        return end

    def find_file_from_address(self, address: int) -> Optional[backend.APKFFileEntry]:
        i = bisect_right(self.file_range_starts, address) - 1
        if i >= 0:
            start, end, f = self.file_ranges[i]
            if start <= address < end:
                return f
        return None

    def _parse_patches(self) -> None:
        if not self.component_headers:
            return
        last = self.component_headers[-1]
        patch_off = _align(last.base_data_address + last.data_size, 4)
        if patch_off + 4 > len(self.data):
            raise ValueError("APKF patch table outside payload")
        self.patch_table_offset = patch_off

        off = patch_off
        patch_index = 0
        while True:
            patch = _u32(self.data, off)
            if patch == 0xFFFFFFFF:
                break
            if patch_index >= MAX_PATCHES:
                raise ValueError("APKF ordinary patch guard hit")
            p = self._decode_ordinary_patch(patch_index, patch)
            p.target_file = self.find_file_from_address(p.target_address)
            if p.target_file is None:
                raise ValueError(f"ordinary patch target 0x{p.target_address:X} is not inside a parsed resource")
            if p.ref_index != PATCH_INDEX_FILENAME_TABLE and p.ref_address >= 0:
                p.ref_file = self.find_file_from_address(p.ref_address)
            self.ordinary_patches.append(p)
            self.file_to_patches[p.target_file.global_index].append(p)
            patch_index += 1
            off += 4
            if off + 4 > len(self.data):
                raise ValueError("ordinary patch table missing sentinel")

        # Global patch records immediately follow the ordinary-patch sentinel.
        off += 4
        self.global_patch_table_offset = off
        global_count = 0
        while off + 4 <= len(self.data):
            sentry = _u32(self.data, off)
            if sentry == 0xFFFFFFFF:
                break
            if global_count >= MAX_GLOBAL_PATCHES:
                raise ValueError("APKF global patch guard hit")
            if off + 16 > len(self.data):
                raise ValueError("truncated APKF global patch record")
            patch, type_bytes, filename_offset, filename_hash = struct.unpack_from("<I4sII", self.data, off)
            target_index = patch >> 26
            target_entry = patch & 0x03FFFFFF
            if target_index >= len(self.component_headers):
                raise ValueError(f"global patch target component index {target_index} out of range")
            base_ptr_addr = self.component_table_address + target_index * 24 + 20
            base_offset = _u32(self.data, base_ptr_addr)
            target_addr = base_ptr_addr + base_offset + target_entry * 4
            target_value = _u32(self.data, target_addr)
            ref_name = ""
            if filename_offset & 1:
                name_addr = self.filename_table_address + (filename_offset & 0xFFFFFFFE)
                if 0 <= name_addr < len(self.data):
                    ref_name = backend.read_cstr(self.data, name_addr)
            gp = GlobalPatch(
                encoded_patch=patch,
                ref_file_type=type_bytes.decode("ascii", errors="replace").replace("\x00", ""),
                filename_offset=filename_offset,
                ref_filename_hash=filename_hash,
                ref_filename=ref_name,
                target_address=target_addr,
                target_component_index=target_index,
                target_entry_index=target_entry,
                target_value=target_value,
                target_file=self.find_file_from_address(target_addr),
            )
            if gp.target_file is None:
                raise ValueError(f"global patch target 0x{target_addr:X} is not inside a parsed resource")
            self.global_patches.append(gp)
            self.file_to_patches[gp.target_file.global_index].append(gp)
            global_count += 1
            off += 16

    def _decode_ordinary_patch(self, patch_index: int, patch: int) -> OrdinaryPatch:
        target_component_index = patch >> 26
        target_entry_index = patch & 0x03FFFFFF
        if target_component_index >= len(self.component_headers):
            raise ValueError(f"ordinary patch target component index {target_component_index} out of range")
        base_ptr_addr = self.component_table_address + target_component_index * 24 + 20
        base_data_offset = _u32(self.data, base_ptr_addr)
        target_addr = base_ptr_addr + base_data_offset + target_entry_index * 4
        encoded_ref = _u32(self.data, target_addr)
        ref_index = encoded_ref >> 26
        ref_entry_index = encoded_ref & 0x03FFFFFF
        if ref_index == PATCH_INDEX_FILENAME_TABLE:
            ref_addr = self.filename_table_address + ref_entry_index * 4
        else:
            if ref_index >= len(self.component_headers):
                # v5.2.191: a small number of unusual legacy ANIM resources
                # (observed in CH_PETER) contain patch-table entries whose
                # target DWORD is not a normal APKF component token.  Do not
                # abort the entire owning archive. Preserve the patch against
                # its target file as unresolved so WRAP extraction fails closed
                # for that resource only, while all normal resources continue.
                ref_addr = -1
            else:
                ref_base_ptr_addr = self.component_table_address + ref_index * 24 + 20
                ref_base_offset = _u32(self.data, ref_base_ptr_addr)
                ref_addr = ref_base_ptr_addr + ref_base_offset + ref_entry_index * 4
        if target_addr < 0 or target_addr + 4 > len(self.data):
            raise ValueError("ordinary patch target outside APKF")
        if ref_addr >= 0 and ref_addr >= len(self.data):
            raise ValueError("ordinary patch reference outside APKF")
        return OrdinaryPatch(
            patch_index=patch_index,
            encoded_patch=patch,
            target_component_index=target_component_index,
            target_entry_index=target_entry_index,
            target_address=target_addr,
            encoded_ref=encoded_ref,
            ref_index=ref_index,
            ref_entry_index=ref_entry_index,
            ref_address=ref_addr,
        )

    def components_for(self, f: backend.APKFFileEntry) -> List[bytes]:
        out: List[bytes] = []
        for i, ((start, end), declared_size) in enumerate(zip(f.component_offsets, f.component_sizes)):
            if start < 0 or end < start or end > len(self.data):
                raise ValueError(f"component {i} outside APKF")
            blob = self.data[start:end]
            if len(blob) != declared_size:
                raise ValueError(
                    f"component {i} size mismatch for {f.filename}: declared={declared_size} actual={len(blob)}"
                )
            out.append(blob)
        return out

    def patch_plans_for(self, f: backend.APKFFileEntry) -> Tuple[List[PatchPlan], int]:
        if not f.component_offsets:
            return [], 0
        if len(f.component_offsets) > MAX_WRAP_COMPONENTS:
            raise ValueError(f"WRAP supports at most {MAX_WRAP_COMPONENTS} components; got {len(f.component_offsets)}")

        comp0_start, comp0_end = f.component_offsets[0]
        plans: List[PatchPlan] = []
        unresolved = 0
        seen_targets: set[int] = set()
        for p in sorted(self.file_to_patches.get(f.global_index, []), key=lambda x: x.target_address):
            target_offset = p.target_address - comp0_start
            if not (0 <= target_offset and target_offset + 4 <= (comp0_end - comp0_start)):
                # WOS/SM3 standalone WRAP patch targets are component0 pointer fields.
                unresolved += 1
                continue
            if target_offset in seen_targets:
                raise ValueError(f"duplicate patch target +0x{target_offset:X} in {f.filename}")
            seen_targets.add(target_offset)

            if isinstance(p, GlobalPatch):
                plans.append(PatchPlan(
                    kind="global",
                    target_offset=target_offset,
                    ref_file_type=p.ref_file_type,
                    ref_filename_hash=p.ref_filename_hash,
                    global_target_value=p.target_value,
                ))
                continue

            internal_component = -1
            internal_ref_offset = 0
            for ci, (start, end) in enumerate(f.component_offsets):
                if start <= p.ref_address < end:
                    internal_component = ci
                    internal_ref_offset = p.ref_address - start
                    break

            if internal_component >= 0:
                plans.append(PatchPlan(
                    kind="internal",
                    target_offset=target_offset,
                    ref_component_index=internal_component,
                    ref_offset=internal_ref_offset,
                    encoded_ref=p.encoded_ref,
                ))
                continue

            # External reference. Filename/string references use NAME/0; normal
            # cross-resource references retain the referenced resource type/hash.
            if p.ref_index == PATCH_INDEX_FILENAME_TABLE:
                plans.append(PatchPlan(
                    kind="external",
                    target_offset=target_offset,
                    encoded_ref=p.encoded_ref,
                    ref_file_type="NAME",
                    ref_filename_hash=0,
                ))
            elif p.ref_file is not None:
                plans.append(PatchPlan(
                    kind="external",
                    target_offset=target_offset,
                    encoded_ref=p.encoded_ref,
                    ref_file_type=p.ref_file.file_type,
                    ref_filename_hash=p.ref_file.filename_hash,
                ))
            else:
                unresolved += 1

        return plans, unresolved


def build_wrap_bytes(
    components: Sequence[bytes],
    plans: Sequence[PatchPlan],
    archive_hash: int,
) -> Tuple[bytes, Dict[str, int]]:
    """Serialize one standalone SM3 WRAP resource."""
    if not 1 <= len(components) <= MAX_WRAP_COMPONENTS:
        raise ValueError(f"WRAP requires 1 or 2 components, got {len(components)}")
    if any(len(c) > 0xFFFFFFFF for c in components):
        raise ValueError("component too large for WRAP")

    comp0 = bytearray(components[0])
    standalone_bases = [0]
    if len(components) == 2:
        standalone_bases.append(len(comp0) + 4)  # literal PHYS marker before component1

    external: List[PatchPlan] = []
    internal: List[PatchPlan] = []
    global_patches: List[PatchPlan] = []

    for p in sorted(plans, key=lambda x: x.target_offset):
        if p.target_offset < 0 or p.target_offset + 4 > len(comp0):
            raise ValueError(f"patch target outside component0: +0x{p.target_offset:X}")
        if p.kind == "internal":
            if p.ref_component_index < 0 or p.ref_component_index >= len(components):
                raise ValueError("internal patch component index outside resource")
            if p.ref_offset < 0 or p.ref_offset >= len(components[p.ref_component_index]):
                raise ValueError("internal patch reference offset outside resource component")
            referenced_standalone = standalone_bases[p.ref_component_index] + p.ref_offset
            rel = referenced_standalone - p.target_offset
            if not -(1 << 31) <= rel < (1 << 31):
                raise ValueError("internal relative pointer overflow")
            struct.pack_into("<i", comp0, p.target_offset, rel)
            internal.append(p)
        elif p.kind == "external":
            struct.pack_into("<I", comp0, p.target_offset, p.encoded_ref & 0xFFFFFFFF)
            external.append(p)
        elif p.kind == "global":
            struct.pack_into("<I", comp0, p.target_offset, p.global_target_value & 0xFFFFFFFF)
            global_patches.append(p)
        else:
            raise ValueError(f"unknown patch kind: {p.kind}")

    # Build metadata using the exact WOS-style relative-pointer layout.
    component_count = len(components)
    component_table_start = 20
    after_component_table = component_table_start + component_count * 8
    patch_table_start = _align(after_component_table, 16)

    patch_header_size = 24
    ext_start = _align(patch_table_start + patch_header_size, 16)
    ext_end = ext_start + len(external) * 16
    int_start = _align(ext_end, 16)
    int_end = int_start + len(internal) * 4
    global_start = _align(int_end, 16)
    global_end = global_start + len(global_patches) * 16
    standalone_start = _align(global_end, 16)

    buf = bytearray()
    # Header + component table placeholders.
    buf.extend(WRAP_MAGIC)
    buf.extend(struct.pack("<I", archive_hash & 0xFFFFFFFF))
    buf.extend(b"\x00\x00\x00\x00")  # pPatchTable at +08
    buf.extend(struct.pack("<I", component_count))
    buf.extend(b"\x00\x00\x00\x00")  # pComponentTable at +10
    for c in components:
        buf.extend(struct.pack("<I", len(c)))
        buf.extend(b"\x00\x00\x00\x00")
    _pad_align(buf, 16)
    if len(buf) != patch_table_start:
        raise AssertionError("WRAP patch table layout drift")

    # Patch table header placeholders.
    buf.extend(struct.pack("<I", len(external)))
    buf.extend(b"\x00\x00\x00\x00")
    buf.extend(struct.pack("<I", len(internal)))
    buf.extend(b"\x00\x00\x00\x00")
    buf.extend(struct.pack("<I", len(global_patches)))
    buf.extend(b"\x00\x00\x00\x00")
    _pad_align(buf, 16)
    if len(buf) != ext_start:
        raise AssertionError("WRAP external table layout drift")

    # External patch records.
    ext_target_pointer_fields: List[Tuple[int, int]] = []
    for p in external:
        buf.extend(_fourcc(p.ref_file_type or "NAME"))
        buf.extend(struct.pack("<I", p.ref_filename_hash & 0xFFFFFFFF))
        buf.extend(struct.pack("<i", -1))
        field = len(buf)
        buf.extend(b"\x00\x00\x00\x00")
        ext_target_pointer_fields.append((field, p.target_offset))
    _pad_align(buf, 16)
    if len(buf) != int_start:
        raise AssertionError("WRAP internal table layout drift")

    # Internal patch list: one relative pointer per component0 target field.
    int_target_pointer_fields: List[Tuple[int, int]] = []
    for p in internal:
        field = len(buf)
        buf.extend(b"\x00\x00\x00\x00")
        int_target_pointer_fields.append((field, p.target_offset))
    _pad_align(buf, 16)
    if len(buf) != global_start:
        raise AssertionError("WRAP global table layout drift")

    global_target_pointer_fields: List[Tuple[int, int]] = []
    for p in global_patches:
        buf.extend(_fourcc(p.ref_file_type))
        buf.extend(struct.pack("<I", p.ref_filename_hash & 0xFFFFFFFF))
        buf.extend(b"GLBL")
        field = len(buf)
        buf.extend(b"\x00\x00\x00\x00")
        global_target_pointer_fields.append((field, p.target_offset))
    _pad_align(buf, 16)
    if len(buf) != standalone_start:
        raise AssertionError("WRAP standalone layout drift")

    # Standalone components.
    comp_starts: List[int] = []
    comp_starts.append(len(buf))
    buf.extend(comp0)
    if len(components) == 2:
        buf.extend(b"PHYS")
        comp_starts.append(len(buf))
        buf.extend(components[1])

    # Fill wrapper/header relative pointers.
    _pack_rel32(buf, 8, patch_table_start)
    _pack_rel32(buf, 16, component_table_start)
    for i, comp_start in enumerate(comp_starts):
        pointer_field = component_table_start + i * 8 + 4
        _pack_rel32(buf, pointer_field, comp_start)

    # Fill patch table pointers. These remain valid for zero-count arrays too.
    _pack_rel32(buf, patch_table_start + 4, ext_start)
    _pack_rel32(buf, patch_table_start + 12, int_start)
    _pack_rel32(buf, patch_table_start + 20, global_start)

    for field, target_off in ext_target_pointer_fields:
        _pack_rel32(buf, field, standalone_start + target_off)
    for field, target_off in int_target_pointer_fields:
        _pack_rel32(buf, field, standalone_start + target_off)
    for field, target_off in global_target_pointer_fields:
        _pack_rel32(buf, field, standalone_start + target_off)

    return bytes(buf), {
        "component_count": component_count,
        "component0_size": len(components[0]),
        "component1_size": len(components[1]) if len(components) > 1 else 0,
        "external_patch_count": len(external),
        "internal_patch_count": len(internal),
        "global_patch_count": len(global_patches),
        "rewritten_internal_pointer_count": len(internal),
    }


def _output_resource_name(f: backend.APKFFileEntry) -> Tuple[str, str]:
    ext = backend.inner_extension(f.file_type, f.filename)
    if not ext:
        ext = "." + (f.file_type.lower() or "bin")
    if not ext.startswith("."):
        ext = "." + ext
    safe_name = backend.clean_name(f.filename, f"resource_{f.global_index:05d}")
    filename = backend.clean_name(
        f"{backend.hex32(f.filename_hash)}.{safe_name}.wrap{ext.lower()}",
        f"{backend.hex32(f.filename_hash)}.resource.wrap{ext.lower()}",
        max_len=220,
    )
    return filename, ext.lower()


def run_wrap_extract(pack_path: Path, out_dir: Path, log=print) -> Dict[str, Any]:
    """Extract one SM3 PC pack into ownership-preserving WRAP resources."""
    pack_path = Path(pack_path)
    out_dir = Path(out_dir)
    if not pack_path.exists() or not pack_path.is_file():
        raise FileNotFoundError(pack_path)
    data = pack_path.read_bytes()
    probe = backend.probe_pack_bytes(pack_path.name, data)
    slices, filtered = backend.apkf_slices_from_probe(data, probe)

    pack_name = backend.clean_name(pack_path.stem, "PACK")
    pack_root = backend.ensure_dir(out_dir / pack_name)
    wrap_root = backend.ensure_dir(pack_root / "WRAP_EXTRACTS")

    manifest: Dict[str, Any] = {
        "format": "SM3_NATIVE_WRAP_EXTRACT_V1",
        "source_pack": pack_path.name,
        "source_pack_path": str(pack_path),
        "wrap_root": str(wrap_root),
        "archives_seen": 0,
        "wraps_written": 0,
        "resources_skipped": 0,
        "archive_parse_errors": 0,
        "internal_patches": 0,
        "external_patches": 0,
        "global_patches": 0,
        "unresolved_pointer_targets": 0,
        "resources": [],
        "filtered_apkf_candidates": filtered,
    }

    authoritative = [
        s for s in slices
        if s.source_kind == "outer_row"
        and s.parent_outer_index is not None
        and s.parent_outer_hash is not None
        and s.parent_outer_type is not None
    ]
    if not authoritative:
        raise ValueError(
            "No authoritative outer-row APKF archives were found. WRAP extraction will not invent pack/archive ownership."
        )

    log(f"[WRAP] Pack route: {probe.route} | authoritative APKF archives: {len(authoritative)}")
    for ai, source in enumerate(authoritative, 1):
        manifest["archives_seen"] += 1
        archive_name = _golden_archive_folder(source)
        archive_root = wrap_root / archive_name
        try:
            apkf = WrapAPKFArchive(source.payload, source)
        except Exception as exc:
            manifest["archive_parse_errors"] += 1
            log(f"[WRAP] APKF parse failed {archive_name}: {exc}")
            manifest["resources"].append({
                "archive_index": source.parent_outer_index,
                "archive": archive_name,
                "archive_hash": backend.hex32(source.parent_outer_hash or 0),
                "resource_type": "",
                "resource_hash": "",
                "resource_name": "",
                "component_count": 0,
                "status": "ARCHIVE_PARSE_ERROR",
                "output": "",
                "wrap_size": 0,
                "internal_patch_count": 0,
                "external_patch_count": 0,
                "global_patch_count": 0,
                "rewritten_internal_pointer_count": 0,
                "unresolved_pointer_count": 0,
                "component_types": [],
                "component_sizes": [],
                "error": str(exc),
            })
            continue

        log(f"[WRAP] [{ai}/{len(authoritative)}] {archive_name}: {len(apkf.files)} resource(s)")
        for f in apkf.files:
            row: Dict[str, Any] = {
                "archive_index": source.parent_outer_index,
                "archive": archive_name,
                "archive_hash": backend.hex32(source.parent_outer_hash or 0),
                "resource_type": f.file_type,
                "resource_hash": backend.hex32(f.filename_hash),
                "resource_name": f.filename,
                "component_count": len(f.component_sizes),
                "status": "",
                "output": "",
                "wrap_size": 0,
                "internal_patch_count": 0,
                "external_patch_count": 0,
                "global_patch_count": 0,
                "rewritten_internal_pointer_count": 0,
                "unresolved_pointer_count": 0,
                "component_types": [
                    apkf.component_headers[i].type_id
                    for i in range(min(len(f.component_sizes), len(apkf.component_headers)))
                ],
                "component_sizes": list(f.component_sizes),
                "error": "",
            }
            try:
                if not 1 <= len(f.component_sizes) <= MAX_WRAP_COMPONENTS:
                    raise ValueError(f"unsupported component count {len(f.component_sizes)}")
                components = apkf.components_for(f)
                plans, unresolved = apkf.patch_plans_for(f)
                row["unresolved_pointer_count"] = unresolved
                manifest["unresolved_pointer_targets"] += unresolved
                if unresolved:
                    raise ValueError(f"{unresolved} unresolved patch target/reference(s)")
                wrapped, stats = build_wrap_bytes(
                    components,
                    plans,
                    source.parent_outer_hash or 0,
                )
                row.update(stats)
                out_name, _ext = _output_resource_name(f)
                type_dir = backend.ensure_dir(archive_root / (f.file_type.upper() or "OTHER"))
                dst = type_dir / out_name
                dst.write_bytes(wrapped)
                row["status"] = "OK"
                row["output"] = str(dst.relative_to(pack_root)).replace("/", "\\")
                row["wrap_size"] = len(wrapped)
                manifest["wraps_written"] += 1
                manifest["internal_patches"] += stats["internal_patch_count"]
                manifest["external_patches"] += stats["external_patch_count"]
                manifest["global_patches"] += stats["global_patch_count"]
            except Exception as exc:
                row["status"] = "SKIPPED"
                row["error"] = str(exc)
                manifest["resources_skipped"] += 1
                log(
                    f"[WRAP] SKIP {archive_name}/{f.file_type}/{backend.hex32(f.filename_hash)}.{f.filename}: {exc}"
                )
            manifest["resources"].append(row)

    manifest_path = wrap_root / "_SM3_WRAP_EXTRACT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    readme = wrap_root / "00_READ_ME_WRAP_EXTRACTS.txt"
    readme.write_text(
        "SM3 WRAP EXTRACTS\n"
        "=================\n\n"
        "These are standalone ownership-preserving WRAP resources produced from the selected Spider-Man 3 PC pack.\n"
        "Use the archive/type hierarchy when building xeSM3/exWoS-style loose-resource mods.\n\n"
        "The source pack was not modified.\n"
        "Archive identity is retained as O####.0xHASH.T##.apkf.\n"
        "See _SM3_WRAP_EXTRACT_MANIFEST.json for patch counts and skipped resources.\n",
        encoding="utf-8",
    )

    log(
        "[WRAP DONE] "
        f"archives={manifest['archives_seen']} wraps={manifest['wraps_written']} "
        f"skipped={manifest['resources_skipped']} archiveErrors={manifest['archive_parse_errors']} "
        f"internal={manifest['internal_patches']} external={manifest['external_patches']} "
        f"global={manifest['global_patches']} unresolved={manifest['unresolved_pointer_targets']}"
    )
    return {
        "pack_root": pack_root,
        "wrap_root": wrap_root,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }
