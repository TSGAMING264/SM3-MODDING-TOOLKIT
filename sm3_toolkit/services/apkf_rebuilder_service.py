from __future__ import annotations

"""
SM3 Generic APKF Rebuilder DEV — Stage 1 (v5.2.133)

What this service does now:
  * Parse APKF v0x0107 headers, resource-type tables, resource records,
    component descriptors, pointer-relocation streams, and resource-reference fixups.
  * Reconstruct the loader's component placement algorithm and verify calculated
    component sizes against the serialized descriptors.
  * Produce a true structural no-change round trip. On the current CH_SPIDERMAN
    animation APKF this is byte-identical when the file is valid.
  * Replace one single-component resource while preserving every other resource,
    rebuilding component layout, remapping relocation destination/target tokens,
    remapping resource-reference destination tokens, and rewriting component
    descriptor size/base fields.
  * Size-changing replacement is intentionally enabled only for SM3 ANIM
    v0x00020116 resources produced from the same original slot/template. The ANIM
    codec moves a known metadata tail when the compressed payload grows; this
    service translates the relocation *field locations* for that moved tail.

This is the controlled bridge toward a fully generic exWoS-style APKF rebuilder.
No game files are bundled with the toolkit.
"""

import hashlib
import json
import re
import struct
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sm3_toolkit.services.anim_codec_service import AnimResource, ANIM_VERSION


APKF_MAGIC = b"APKF"
APKF_VERSION = 0x0107
ANIM_FOURCC = 0x4D494E41
REBUILDER_STAGE = "v5.2.133 APKF REBUILDER DEV STAGE 1"
_HASH_RE = re.compile(r"0x([0-9A-Fa-f]{8})")


class APKFRebuilderError(RuntimeError):
    pass


def _u32(data: bytes | bytearray, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise APKFRebuilderError(f"u32 read outside file at 0x{off:X}")
    return struct.unpack_from("<I", data, off)[0]


def _p32(buf: bytearray, off: int, value: int) -> None:
    if off < 0 or off + 4 > len(buf):
        raise APKFRebuilderError(f"u32 write outside buffer at 0x{off:X}")
    struct.pack_into("<I", buf, off, value & 0xFFFFFFFF)


def _align_up(value: int, alignment: int) -> int:
    alignment = int(alignment)
    if alignment <= 1:
        return int(value)
    # SM3 builder calls use power-of-two alignments. Reject a malformed archive
    # instead of silently producing a different layout.
    if alignment & (alignment - 1):
        raise APKFRebuilderError(f"non-power-of-two APKF alignment 0x{alignment:X}")
    return (int(value) + alignment - 1) & ~(alignment - 1)


def _fourcc(value: int) -> str:
    raw = struct.pack("<I", int(value) & 0xFFFFFFFF)
    return raw.rstrip(b"\x00").decode("ascii", "replace")


def decode_relocation_token(token: int) -> Tuple[int, int]:
    token &= 0xFFFFFFFF
    return token >> 26, (token & 0x03FFFFFF) << 2


def encode_relocation_token(component_index: int, byte_offset: int) -> int:
    component_index = int(component_index)
    byte_offset = int(byte_offset)
    if not (0 <= component_index <= 0x3F):
        raise APKFRebuilderError(f"component index {component_index} does not fit relocation token")
    if byte_offset < 0 or (byte_offset & 3):
        raise APKFRebuilderError(f"relocation offset 0x{byte_offset:X} is not DWORD aligned")
    word_offset = byte_offset >> 2
    if word_offset > 0x03FFFFFF:
        raise APKFRebuilderError(f"relocation offset 0x{byte_offset:X} exceeds token capacity")
    return ((component_index & 0x3F) << 26) | word_offset


@dataclass
class APKFComponent:
    index: int
    descriptor_offset: int
    type_value: int
    type_name: str
    flags: int
    alignment: int
    field_0c: int
    size: int
    data_offset: int
    serialized_data_rel: int


@dataclass
class APKFResourceTypeTable:
    table_offset: int
    type_value: int
    type_name: str
    version: int
    slot_count: int
    records_offset: int
    resource_count: int
    placements: List[int]


@dataclass
class APKFResource:
    table_index: int
    index: int
    record_offset: int
    type_value: int
    type_name: str
    version: int
    name_relative: int
    resource_hash: int
    resource_name: str
    sizes: List[int]
    component_offsets: Dict[int, int] = field(default_factory=dict)

    @property
    def hash_hex(self) -> str:
        return f"0x{self.resource_hash:08X}"


@dataclass
class APKFReferenceFixup:
    destination_token: int
    resource_type: int
    ref0: int
    ref1: int


@dataclass
class APKFAnalysis:
    path: str
    file_size: int
    sha256: str
    header_version: int
    header_flags: int
    header_field_0c: int
    component_count: int
    component_table_offset: int
    resource_type_table_count: int
    resource_count: int
    relocation_stream_offset: int
    relocation_count: int
    resource_reference_stream_offset: int
    resource_reference_count: int
    stream_end_offset: int
    component_size_match: bool
    components: List[APKFComponent]
    type_tables: List[APKFResourceTypeTable]
    resources: List[APKFResource]
    relocation_tokens: List[int]
    reference_fixups: List[APKFReferenceFixup]

    def compact_dict(self) -> dict:
        return {
            "stage": REBUILDER_STAGE,
            "path": self.path,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "header_version": f"0x{self.header_version:04X}",
            "header_flags": f"0x{self.header_flags:08X}",
            "header_field_0c": f"0x{self.header_field_0c:08X}",
            "component_count": self.component_count,
            "component_table_offset": f"0x{self.component_table_offset:X}",
            "resource_type_table_count": self.resource_type_table_count,
            "resource_count": self.resource_count,
            "relocation_stream_offset": f"0x{self.relocation_stream_offset:X}",
            "relocation_count": self.relocation_count,
            "resource_reference_stream_offset": f"0x{self.resource_reference_stream_offset:X}",
            "resource_reference_count": self.resource_reference_count,
            "stream_end_offset": f"0x{self.stream_end_offset:X}",
            "component_size_match": self.component_size_match,
            "components": [
                {
                    "index": c.index,
                    "type": c.type_name,
                    "type_value": f"0x{c.type_value:08X}",
                    "flags": f"0x{c.flags:08X}",
                    "alignment": c.alignment,
                    "size": c.size,
                    "size_hex": f"0x{c.size:X}",
                    "data_offset": f"0x{c.data_offset:X}",
                }
                for c in self.components
            ],
            "type_tables": [
                {
                    "type": t.type_name,
                    "type_value": f"0x{t.type_value:08X}",
                    "version": f"0x{t.version:08X}",
                    "slot_count": t.slot_count,
                    "resource_count": t.resource_count,
                    "records_offset": f"0x{t.records_offset:X}",
                    "placements": [f"0x{x:08X}" for x in t.placements],
                }
                for t in self.type_tables
            ],
        }


@dataclass
class APKFBuildResult:
    mode: str
    source_path: str
    output_path: str
    source_size: int
    output_size: int
    source_sha256: str
    output_sha256: str
    byte_identical: bool
    structural_validation: bool
    target_type: str = ""
    target_hash: str = ""
    target_name: str = ""
    old_resource_size: int = 0
    new_resource_size: int = 0
    old_component_size: int = 0
    new_component_size: int = 0
    relocation_count: int = 0
    resource_reference_count: int = 0
    notes: List[str] = field(default_factory=list)


@dataclass
class _Segment:
    resource: APKFResource
    component_index: int
    slot_index: int
    alignment: int
    old_start: int
    old_end: int
    new_start: int
    new_end: int


class APKFDocument:
    def __init__(self, data: bytes, path: str = ""):
        self.data = bytes(data)
        self.path = str(path)
        self.analysis = self._parse()

    @classmethod
    def from_file(cls, path: str | Path) -> "APKFDocument":
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"APKF not found: {p}")
        return cls(p.read_bytes(), str(p))

    def _parse(self) -> APKFAnalysis:
        data = self.data
        if len(data) < 0x1C or data[:4] != APKF_MAGIC:
            raise APKFRebuilderError("Not an APKF container (missing APKF magic).")
        version_raw = _u32(data, 0x04)
        version = version_raw & 0xFFFF
        if version != APKF_VERSION:
            raise APKFRebuilderError(
                f"Unsupported APKF version 0x{version:04X}; expected 0x{APKF_VERSION:04X}."
            )
        component_count = _u32(data, 0x10)
        if component_count <= 0 or component_count > 63:
            raise APKFRebuilderError(f"Implausible APKF component count {component_count}.")
        component_table_offset = 0x14 + _u32(data, 0x14)
        if component_table_offset < 0x1C or component_table_offset + component_count * 0x18 > len(data):
            raise APKFRebuilderError("APKF component table is outside the file.")

        components: List[APKFComponent] = []
        for index in range(component_count):
            off = component_table_offset + index * 0x18
            rel = _u32(data, off + 0x14)
            data_off = off + 0x14 + rel
            size = _u32(data, off + 0x10)
            if data_off < 0 or data_off + size > len(data):
                raise APKFRebuilderError(
                    f"Component {index} data 0x{data_off:X}+0x{size:X} is outside the APKF."
                )
            type_value = _u32(data, off)
            components.append(
                APKFComponent(
                    index=index,
                    descriptor_offset=off,
                    type_value=type_value,
                    type_name=_fourcc(type_value),
                    flags=_u32(data, off + 0x04),
                    alignment=_u32(data, off + 0x08),
                    field_0c=_u32(data, off + 0x0C),
                    size=size,
                    data_offset=data_off,
                    serialized_data_rel=rel,
                )
            )

        tables: List[APKFResourceTypeTable] = []
        table_off = 0x1C
        max_table_count = 1024
        while True:
            if table_off + 4 > len(data):
                raise APKFRebuilderError("Resource-type table list does not terminate before EOF.")
            type_value = _u32(data, table_off)
            if type_value == 0:
                break
            if len(tables) >= max_table_count:
                raise APKFRebuilderError("Too many APKF resource-type tables.")
            table_size = 0x14 + component_count * 4
            if table_off + table_size > component_table_offset:
                raise APKFRebuilderError("Resource-type table overlaps APKF metadata/component table.")
            records_off = table_off + 0x0C + _u32(data, table_off + 0x0C)
            slot_count = _u32(data, table_off + 0x08)
            resource_count = _u32(data, table_off + 0x10)
            if slot_count > component_count:
                raise APKFRebuilderError(
                    f"Table {_fourcc(type_value)} has slot_count={slot_count} > components={component_count}."
                )
            record_stride = (2 + slot_count) * 4
            if records_off < 0 or records_off + record_stride * resource_count > component_table_offset:
                raise APKFRebuilderError(
                    f"Table {_fourcc(type_value)} resource records are outside APKF metadata."
                )
            placements = [_u32(data, table_off + 0x14 + i * 4) for i in range(component_count)]
            tables.append(
                APKFResourceTypeTable(
                    table_offset=table_off,
                    type_value=type_value,
                    type_name=_fourcc(type_value),
                    version=_u32(data, table_off + 0x04),
                    slot_count=slot_count,
                    records_offset=records_off,
                    resource_count=resource_count,
                    placements=placements,
                )
            )
            table_off += table_size

        cursors = [0] * component_count
        resources: List[APKFResource] = []
        for table_index, table in enumerate(tables):
            stride = (2 + table.slot_count) * 4
            for index in range(table.resource_count):
                rec_off = table.records_offset + index * stride
                name_rel = _u32(data, rec_off)
                resource_hash = _u32(data, rec_off + 4)
                sizes = [_u32(data, rec_off + 8 + 4 * i) for i in range(table.slot_count)]
                name = ""
                if name_rel:
                    name_off = rec_off + name_rel
                    if not (0 <= name_off < component_table_offset):
                        raise APKFRebuilderError(
                            f"Resource name pointer 0x{name_off:X} is outside APKF metadata."
                        )
                    end = data.find(b"\0", name_off, component_table_offset)
                    if end < 0:
                        raise APKFRebuilderError(f"Unterminated resource name at 0x{name_off:X}.")
                    name = data[name_off:end].decode("utf-8", "replace")
                res = APKFResource(
                    table_index=table_index,
                    index=index,
                    record_offset=rec_off,
                    type_value=table.type_value,
                    type_name=table.type_name,
                    version=table.version,
                    name_relative=name_rel,
                    resource_hash=resource_hash,
                    resource_name=name,
                    sizes=sizes,
                )
                for ci, packed in enumerate(table.placements):
                    slot = packed >> 24
                    alignment = packed & 0x00FFFFFF
                    if slot == 0xFF:
                        continue
                    if slot >= len(sizes):
                        raise APKFRebuilderError(
                            f"{table.type_name} placement maps component {ci} to invalid slot {slot}."
                        )
                    cursors[ci] = _align_up(cursors[ci], alignment)
                    res.component_offsets[ci] = cursors[ci]
                    cursors[ci] += sizes[slot]
                resources.append(res)

        component_size_match = all(cursors[i] == components[i].size for i in range(component_count))
        if not component_size_match:
            detail = ", ".join(
                f"{i}:calc=0x{cursors[i]:X}/desc=0x{components[i].size:X}"
                for i in range(component_count)
            )
            raise APKFRebuilderError(f"Component placement reconstruction mismatch ({detail}).")

        reloc_off = _align_up(max(c.data_offset + c.size for c in components), 4)
        p = reloc_off
        relocations: List[int] = []
        while True:
            token = _u32(data, p)
            p += 4
            if token == 0xFFFFFFFF:
                break
            ci, off = decode_relocation_token(token)
            if ci >= component_count:
                raise APKFRebuilderError(
                    f"Relocation destination token 0x{token:08X} uses invalid component {ci}."
                )
            if off + 4 > components[ci].size:
                raise APKFRebuilderError(
                    f"Relocation destination 0x{token:08X} is outside component {ci}."
                )
            relocations.append(token)
            if len(relocations) > 10_000_000:
                raise APKFRebuilderError("Relocation stream appears unterminated.")

        refs_off = p
        refs: List[APKFReferenceFixup] = []
        while True:
            dest = _u32(data, p)
            if dest == 0xFFFFFFFF:
                p += 4
                break
            if p + 16 > len(data):
                raise APKFRebuilderError("Truncated APKF resource-reference fixup.")
            ci, off = decode_relocation_token(dest)
            if ci >= component_count or off + 4 > components[ci].size:
                raise APKFRebuilderError(
                    f"Resource-reference destination 0x{dest:08X} is outside a component."
                )
            refs.append(
                APKFReferenceFixup(
                    destination_token=dest,
                    resource_type=_u32(data, p + 4),
                    ref0=_u32(data, p + 8),
                    ref1=_u32(data, p + 12),
                )
            )
            p += 16
            if len(refs) > 10_000_000:
                raise APKFRebuilderError("Resource-reference stream appears unterminated.")

        if p != len(data):
            # Current SM3 v0x107 archives observed in this project end directly
            # after the second FFFFFFFF. Keep this strict for Stage 1 so we do
            # not destroy an unknown trailer.
            raise APKFRebuilderError(
                f"APKF has 0x{len(data) - p:X} unparsed bytes after fixup terminator; Stage 1 refuses to rewrite it."
            )

        return APKFAnalysis(
            path=self.path,
            file_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            header_version=version,
            header_flags=_u32(data, 0x08),
            header_field_0c=_u32(data, 0x0C),
            component_count=component_count,
            component_table_offset=component_table_offset,
            resource_type_table_count=len(tables),
            resource_count=len(resources),
            relocation_stream_offset=reloc_off,
            relocation_count=len(relocations),
            resource_reference_stream_offset=refs_off,
            resource_reference_count=len(refs),
            stream_end_offset=p,
            component_size_match=component_size_match,
            components=components,
            type_tables=tables,
            resources=resources,
            relocation_tokens=relocations,
            reference_fixups=refs,
        )

    def find_resource(
        self,
        resource_hash: int,
        resource_type: Optional[int | str] = None,
    ) -> APKFResource:
        wanted_hash = int(resource_hash) & 0xFFFFFFFF
        wanted_type_value: Optional[int] = None
        wanted_type_name: Optional[str] = None
        if isinstance(resource_type, int):
            wanted_type_value = resource_type & 0xFFFFFFFF
        elif resource_type:
            wanted_type_name = str(resource_type).upper()
        matches = []
        for r in self.analysis.resources:
            if r.resource_hash != wanted_hash:
                continue
            if wanted_type_value is not None and r.type_value != wanted_type_value:
                continue
            if wanted_type_name is not None and r.type_name.upper() != wanted_type_name:
                continue
            matches.append(r)
        if not matches:
            extra = f" type {resource_type}" if resource_type else ""
            raise APKFRebuilderError(f"Resource 0x{wanted_hash:08X}{extra} not found in APKF.")
        if len(matches) != 1:
            raise APKFRebuilderError(
                f"Resource 0x{wanted_hash:08X} is ambiguous ({len(matches)} records); choose its type as well."
            )
        return matches[0]

    def resource_bytes(self, resource: APKFResource, component_index: Optional[int] = None) -> bytes:
        participants = []
        table = self.analysis.type_tables[resource.table_index]
        for ci, packed in enumerate(table.placements):
            slot = packed >> 24
            if slot != 0xFF:
                participants.append((ci, slot))
        if component_index is None:
            if len(participants) != 1:
                raise APKFRebuilderError(
                    f"{resource.type_name} 0x{resource.resource_hash:08X} uses {len(participants)} components; choose one."
                )
            component_index, slot = participants[0]
        else:
            found = [(ci, slot) for ci, slot in participants if ci == component_index]
            if not found:
                raise APKFRebuilderError("Selected resource is not present in that component.")
            slot = found[0][1]
        comp = self.analysis.components[component_index]
        start = resource.component_offsets[component_index]
        size = resource.sizes[slot]
        return self.data[comp.data_offset + start : comp.data_offset + start + size]


def analyze_apkf(path: str | Path) -> APKFAnalysis:
    return APKFDocument.from_file(path).analysis


def _infer_hash_from_filename(path: str | Path) -> Optional[int]:
    m = _HASH_RE.search(Path(path).name)
    return int(m.group(1), 16) if m else None


def _write_report(result: APKFBuildResult, report_path: Path, extra: Optional[dict] = None) -> None:
    report = asdict(result)
    report["stage"] = REBUILDER_STAGE
    if extra:
        report.update(extra)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _validate_rebuilt_bytes(data: bytes) -> APKFAnalysis:
    doc = APKFDocument(data)
    a = doc.analysis
    # Validate pointer-relocation target tokens after all destination tokens were
    # decoded successfully by the parser.
    for token in a.relocation_tokens:
        dci, doff = decode_relocation_token(token)
        comp = a.components[dci]
        raw = _u32(data, comp.data_offset + doff)
        tci, toff = decode_relocation_token(raw)
        if tci == 0x3F:
            continue
        if tci >= a.component_count:
            raise APKFRebuilderError(
                f"Relocation target 0x{raw:08X} at destination 0x{token:08X} uses invalid component {tci}."
            )
        if toff >= a.components[tci].size:
            raise APKFRebuilderError(
                f"Relocation target 0x{raw:08X} resolves beyond component {tci} size."
            )
    return a


def rebuild_no_change_roundtrip(source_apkf: str | Path, output_path: str | Path) -> APKFBuildResult:
    src = Path(source_apkf)
    out = Path(output_path)
    doc = APKFDocument.from_file(src)
    # Route through the real replacement engine using a real single-component
    # resource and its exact original bytes. This verifies the parser, component
    # reconstruction, relocation remapper, reference-fixup remapper and emitter,
    # rather than merely copying the file.
    candidate = next(
        (
            r
            for r in doc.analysis.resources
            if sum(1 for p in doc.analysis.type_tables[r.table_index].placements if (p >> 24) != 0xFF) == 1
        ),
        None,
    )
    if candidate is None:
        raise APKFRebuilderError("No single-component resource exists for the no-change round-trip control test.")
    replacement = doc.resource_bytes(candidate)
    rebuilt, detail = _rebuild_single_component_resource(doc, candidate, replacement, allow_size_change=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rebuilt)
    validated = _validate_rebuilt_bytes(rebuilt)
    source_sha = hashlib.sha256(doc.data).hexdigest()
    output_sha = hashlib.sha256(rebuilt).hexdigest()
    result = APKFBuildResult(
        mode="NO_CHANGE_STRUCTURAL_ROUNDTRIP",
        source_path=str(src),
        output_path=str(out),
        source_size=len(doc.data),
        output_size=len(rebuilt),
        source_sha256=source_sha,
        output_sha256=output_sha,
        byte_identical=(doc.data == rebuilt),
        structural_validation=True,
        target_type=candidate.type_name,
        target_hash=candidate.hash_hex,
        target_name=candidate.resource_name,
        old_resource_size=len(replacement),
        new_resource_size=len(replacement),
        old_component_size=detail["old_component_size"],
        new_component_size=detail["new_component_size"],
        relocation_count=validated.relocation_count,
        resource_reference_count=validated.resource_reference_count,
        notes=[
            "Real structural emitter used; output was not produced by raw-copy shortcut.",
            "PASS requires byte_identical=true before any size-changing APKF game test.",
        ],
    )
    report_path = out.with_suffix(out.suffix + ".roundtrip.json")
    _write_report(result, report_path, {"analysis": validated.compact_dict()})
    if not result.byte_identical:
        raise APKFRebuilderError(
            f"NO-CHANGE ROUNDTRIP FAILED: rebuilt APKF differs from source. Report: {report_path}"
        )
    return result


def rebuild_with_replacement(
    source_apkf: str | Path,
    replacement_file: str | Path,
    output_path: str | Path,
    resource_hash: Optional[int] = None,
    resource_type: Optional[int | str] = None,
) -> APKFBuildResult:
    src = Path(source_apkf)
    replacement_path = Path(replacement_file)
    out = Path(output_path)
    if not replacement_path.is_file():
        raise FileNotFoundError(f"Replacement file not found: {replacement_path}")
    doc = APKFDocument.from_file(src)
    if resource_hash is None:
        resource_hash = _infer_hash_from_filename(replacement_path)
    if resource_hash is None:
        raise APKFRebuilderError(
            "Could not infer the target hash from the replacement filename. Select a resource row or use a filename containing 0x12345678."
        )
    target = doc.find_resource(resource_hash, resource_type)
    replacement = replacement_path.read_bytes()
    old_bytes = doc.resource_bytes(target)
    size_change = len(replacement) != len(old_bytes)

    if size_change:
        if target.type_value != ANIM_FOURCC or target.version != ANIM_VERSION:
            raise APKFRebuilderError(
                "Stage 1 size-changing rebuild is enabled only for SM3 ANIM v0x20116. "
                "Other resource types remain parse/roundtrip-only until their serializer relocation maps are proven."
            )
        if len(replacement) < len(old_bytes):
            raise APKFRebuilderError(
                "Stage 1 ANIM size-changing rebuild currently supports growth only, matching the proven NAS arbitrary-size serializer."
            )
        if len(replacement) & 3:
            raise APKFRebuilderError("Size-changing ANIM replacement must remain DWORD-aligned.")
        # Identity + slot provenance checks.
        if len(replacement) < 0x18:
            raise APKFRebuilderError("Replacement ANIM is too small.")
        repl_hash = _u32(replacement, 0x04)
        repl_ver = _u32(replacement, 0x14)
        if repl_hash != target.resource_hash or repl_ver != target.version:
            raise APKFRebuilderError(
                f"Replacement identity mismatch: expected {target.hash_hex} / 0x{target.version:08X}, "
                f"got 0x{repl_hash:08X} / 0x{repl_ver:08X}."
            )
        old_anim = AnimResource(old_bytes)
        new_anim = AnimResource(replacement)
        table = doc.analysis.type_tables[target.table_index]
        target_components = [ci for ci, packed in enumerate(table.placements) if (packed >> 24) != 0xFF]
        if len(target_components) != 1:
            raise APKFRebuilderError("Size-changing ANIM route requires one component.")
        target_component_offset = target.component_offsets[target_components[0]]
        if (old_anim.component_base_token << 2) != target_component_offset:
            raise APKFRebuilderError(
                "Original ANIM component-base token does not match the selected APKF resource slot; refusing ambiguous rebuild."
            )
        if old_anim.component_base_token != new_anim.component_base_token:
            raise APKFRebuilderError(
                "Replacement ANIM was not rebuilt from the same APKF slot/template (component-base token changed)."
            )

    rebuilt, detail = _rebuild_single_component_resource(doc, target, replacement, allow_size_change=size_change)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rebuilt)
    validated = _validate_rebuilt_bytes(rebuilt)
    # Confirm the output table locates the replacement and reproduces its bytes.
    out_doc = APKFDocument(rebuilt)
    out_target = out_doc.find_resource(target.resource_hash, target.type_value)
    actual = out_doc.resource_bytes(out_target)
    if actual != replacement:
        raise APKFRebuilderError("Post-build verification failed: rebuilt APKF target bytes do not match replacement.")

    result = APKFBuildResult(
        mode="ARBITRARY_SIZE_ANIM_STAGE1" if size_change else "SAME_SIZE_RESOURCE_REPLACEMENT",
        source_path=str(src),
        output_path=str(out),
        source_size=len(doc.data),
        output_size=len(rebuilt),
        source_sha256=hashlib.sha256(doc.data).hexdigest(),
        output_sha256=hashlib.sha256(rebuilt).hexdigest(),
        byte_identical=(doc.data == rebuilt),
        structural_validation=True,
        target_type=target.type_name,
        target_hash=target.hash_hex,
        target_name=target.resource_name,
        old_resource_size=len(old_bytes),
        new_resource_size=len(replacement),
        old_component_size=detail["old_component_size"],
        new_component_size=detail["new_component_size"],
        relocation_count=validated.relocation_count,
        resource_reference_count=validated.resource_reference_count,
        notes=[
            "All non-target resources preserved byte-for-byte inside their rebuilt resource slices.",
            "Pointer-relocation destination tokens remapped after component movement.",
            "Pointer-relocation target tokens remapped for moved component-relative targets.",
            "Resource-reference destination tokens remapped.",
            "This output is a standalone rebuilt APKF DEV artifact; PCPACK reinjection is the next integration stage.",
        ],
    )
    report_path = out.with_suffix(out.suffix + ".rebuild.json")
    _write_report(
        result,
        report_path,
        {
            "source_analysis": doc.analysis.compact_dict(),
            "output_analysis": validated.compact_dict(),
            "detail": detail,
        },
    )
    return result


def _rebuild_single_component_resource(
    doc: APKFDocument,
    target: APKFResource,
    replacement: bytes,
    allow_size_change: bool,
) -> Tuple[bytes, dict]:
    a = doc.analysis
    data = doc.data
    table = a.type_tables[target.table_index]
    participants = [(ci, packed >> 24) for ci, packed in enumerate(table.placements) if (packed >> 24) != 0xFF]
    if len(participants) != 1:
        raise APKFRebuilderError(
            f"Stage 1 replacement requires a single-component resource; {target.type_name} {target.hash_hex} uses {len(participants)}."
        )
    target_ci, target_slot = participants[0]
    old_target_size = target.sizes[target_slot]
    if not allow_size_change and len(replacement) != old_target_size:
        raise APKFRebuilderError("Size change was not authorized for this rebuild route.")

    old_components = [
        data[c.data_offset : c.data_offset + c.size]
        for c in a.components
    ]
    new_components = [bytearray() for _ in a.components]
    segments: List[List[_Segment]] = [[] for _ in a.components]
    old_cursors = [0] * a.component_count
    new_cursors = [0] * a.component_count

    for res in a.resources:
        res_table = a.type_tables[res.table_index]
        for ci, packed in enumerate(res_table.placements):
            slot = packed >> 24
            alignment = packed & 0x00FFFFFF
            if slot == 0xFF:
                continue
            old_start = _align_up(old_cursors[ci], alignment)
            new_start = _align_up(new_cursors[ci], alignment)
            old_pad = old_components[ci][old_cursors[ci] : old_start]
            new_pad_len = new_start - new_cursors[ci]
            if new_pad_len <= len(old_pad):
                new_components[ci].extend(old_pad[:new_pad_len])
            else:
                new_components[ci].extend(old_pad)
                new_components[ci].extend(b"\0" * (new_pad_len - len(old_pad)))
            if len(new_components[ci]) != new_start:
                raise APKFRebuilderError("Internal component-padding reconstruction error.")

            old_size = res.sizes[slot]
            old_payload = old_components[ci][old_start : old_start + old_size]
            if res is target and ci == target_ci:
                payload = replacement
            else:
                payload = old_payload
            new_components[ci].extend(payload)
            seg = _Segment(
                resource=res,
                component_index=ci,
                slot_index=slot,
                alignment=alignment,
                old_start=old_start,
                old_end=old_start + old_size,
                new_start=new_start,
                new_end=new_start + len(payload),
            )
            segments[ci].append(seg)
            old_cursors[ci] = old_start + old_size
            new_cursors[ci] = new_start + len(payload)

    # Preserve any component tail bytes that are not accounted for by resource
    # records. Current CH_SPIDERMAN components have no such tail, but retaining it
    # makes the parser less destructive for other valid archives.
    for ci, comp in enumerate(a.components):
        tail = old_components[ci][old_cursors[ci] : comp.size]
        new_components[ci].extend(tail)

    old_target_start = target.component_offsets[target_ci]
    size_delta = len(replacement) - old_target_size
    old_anim_payload_end: Optional[int] = None
    if size_delta:
        old_anim_payload_end = AnimResource(doc.resource_bytes(target)).parse_header()[0].payload_end

    def map_component_offset(ci: int, old_offset: int) -> int:
        if ci < 0 or ci >= a.component_count:
            raise APKFRebuilderError(f"Cannot map invalid component {ci}.")
        running_delta = 0
        for seg in segments[ci]:
            if seg.old_start <= old_offset < seg.old_end:
                relative = old_offset - seg.old_start
                if seg.resource is target and ci == target_ci and size_delta:
                    # v5.2.129+ ANIM arbitrary-size serializer inserts growth
                    # immediately before payload_end's metadata tail, preserving
                    # the whole tail byte-for-byte at +size_delta.
                    if old_anim_payload_end is None:
                        raise APKFRebuilderError("Missing original ANIM payload boundary.")
                    if relative >= old_anim_payload_end:
                        relative += size_delta
                    if relative >= (seg.new_end - seg.new_start):
                        raise APKFRebuilderError(
                            f"Mapped ANIM relocation offset 0x{relative:X} exceeds replacement size."
                        )
                return seg.new_start + relative
            if old_offset < seg.old_start:
                return old_offset + running_delta
            running_delta = (seg.new_end - seg.old_end)
        return old_offset + running_delta

    # Metadata before component 0 is deliberately preserved byte-for-byte except
    # for fields we own (target resource size + component descriptor sizes/bases).
    first_component_base = min(c.data_offset for c in a.components)
    if a.components[0].data_offset != first_component_base:
        raise APKFRebuilderError("Stage 1 expects component descriptor order to match data order.")
    prefix = bytearray(data[:first_component_base])
    _p32(prefix, target.record_offset + 8 + target_slot * 4, len(replacement))

    # Remap pointer relocations. For relocation fields inside the replaced ANIM,
    # the replacement bytes are authoritative because anim_codec_service already
    # rewrites local pointer token VALUES. We only translate the destination field
    # location when the metadata tail moved.
    new_relocation_tokens: List[int] = []
    for token in a.relocation_tokens:
        dci, doff = decode_relocation_token(token)
        new_doff = map_component_offset(dci, doff)
        new_relocation_tokens.append(encode_relocation_token(dci, new_doff))
        inside_target = (
            dci == target_ci
            and old_target_start <= doff < old_target_start + old_target_size
        )
        if inside_target:
            continue
        old_pointer_token = _u32(old_components[dci], doff)
        tci, toff = decode_relocation_token(old_pointer_token)
        if tci == 0x3F:
            new_pointer_token = old_pointer_token
        elif tci < a.component_count:
            new_pointer_token = encode_relocation_token(tci, map_component_offset(tci, toff))
        else:
            # Keep unknown special classes unchanged. The post-build validator will
            # reject them if they are not legal in the resulting APKF.
            new_pointer_token = old_pointer_token
        _p32(new_components[dci], new_doff, new_pointer_token)

    new_reference_fixups: List[APKFReferenceFixup] = []
    for ref in a.reference_fixups:
        dci, doff = decode_relocation_token(ref.destination_token)
        new_dest = encode_relocation_token(dci, map_component_offset(dci, doff))
        new_reference_fixups.append(
            APKFReferenceFixup(
                destination_token=new_dest,
                resource_type=ref.resource_type,
                ref0=ref.ref0,
                ref1=ref.ref1,
            )
        )

    # Lay components back into the serialized file. Component 0 keeps its metadata
    # boundary; later component bases are recomputed from their descriptor alignment.
    new_bases: List[int] = []
    cursor = first_component_base
    for i, comp in enumerate(a.components):
        if i == 0:
            base = first_component_base
        else:
            base = _align_up(cursor, comp.alignment or 4)
        new_bases.append(base)
        cursor = base + len(new_components[i])

    for i, comp in enumerate(a.components):
        _p32(prefix, comp.descriptor_offset + 0x10, len(new_components[i]))
        data_rel = new_bases[i] - (comp.descriptor_offset + 0x14)
        _p32(prefix, comp.descriptor_offset + 0x14, data_rel)

    out = bytearray(prefix)
    old_gap_ranges: List[Tuple[int, int]] = []
    for i in range(a.component_count - 1):
        old_gap_ranges.append(
            (
                a.components[i].data_offset + a.components[i].size,
                a.components[i + 1].data_offset,
            )
        )
    last_end = a.components[-1].data_offset + a.components[-1].size
    old_gap_ranges.append((last_end, a.relocation_stream_offset))

    for i, comp in enumerate(a.components):
        if len(out) > new_bases[i]:
            raise APKFRebuilderError("Component layout overlap while emitting rebuilt APKF.")
        if len(out) < new_bases[i]:
            gap_len = new_bases[i] - len(out)
            if i > 0:
                old_gap_start, old_gap_end = old_gap_ranges[i - 1]
                old_gap = data[old_gap_start:old_gap_end]
            else:
                old_gap = b""
            out.extend(old_gap[:gap_len])
            if len(out) < new_bases[i]:
                out.extend(b"\0" * (new_bases[i] - len(out)))
        out.extend(new_components[i])

    new_reloc_start = _align_up(len(out), 4)
    old_final_gap = data[old_gap_ranges[-1][0] : old_gap_ranges[-1][1]]
    final_gap_len = new_reloc_start - len(out)
    out.extend(old_final_gap[:final_gap_len])
    if len(out) < new_reloc_start:
        out.extend(b"\0" * (new_reloc_start - len(out)))

    for token in new_relocation_tokens:
        out.extend(struct.pack("<I", token))
    out.extend(struct.pack("<I", 0xFFFFFFFF))
    for ref in new_reference_fixups:
        out.extend(
            struct.pack(
                "<IIII",
                ref.destination_token,
                ref.resource_type,
                ref.ref0,
                ref.ref1,
            )
        )
    out.extend(struct.pack("<I", 0xFFFFFFFF))

    detail = {
        "target_component": target_ci,
        "target_slot": target_slot,
        "target_old_offset": f"0x{old_target_start:X}",
        "old_resource_size": old_target_size,
        "new_resource_size": len(replacement),
        "size_delta": size_delta,
        "old_anim_payload_end": f"0x{old_anim_payload_end:X}" if old_anim_payload_end is not None else None,
        "old_component_size": a.components[target_ci].size,
        "new_component_size": len(new_components[target_ci]),
        "old_component_bases": [f"0x{c.data_offset:X}" for c in a.components],
        "new_component_bases": [f"0x{x:X}" for x in new_bases],
        "old_relocation_stream": f"0x{a.relocation_stream_offset:X}",
        "new_relocation_stream": f"0x{new_reloc_start:X}",
        "relocation_count": len(new_relocation_tokens),
        "resource_reference_count": len(new_reference_fixups),
    }
    return bytes(out), detail
