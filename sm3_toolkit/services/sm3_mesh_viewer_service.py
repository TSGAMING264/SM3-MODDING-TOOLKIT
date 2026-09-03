from __future__ import annotations

"""Native Spider-Man 3 PC loose .mesh decoder used by Model Viewer.

This is intentionally VIEW-ONLY.  It never writes or rebuilds mesh files.

The loose SM3 mesh resources extracted by the toolkit contain the serialized
metadata component followed by the physical vertex/index stream.  The parser
below validates that complete layout before exposing geometry to the UI.
"""

from dataclasses import dataclass, field
from pathlib import Path
import math
import re
import struct
from typing import Iterable


class SM3MeshError(RuntimeError):
    pass


@dataclass(frozen=True)
class FVFEntry:
    channel: int
    offset: int
    data_type: int
    usage: int


@dataclass
class SM3MeshSection:
    index: int
    metadata_offset: int
    material_ref: int
    bone_palette: tuple[int, ...]
    vertex_count: int
    index_count: int
    stride: int
    bounds_center: tuple[float, float, float]
    bounds_radius: float
    bounds_extents: tuple[float, float, float]
    fvf: tuple[FVFEntry, ...]
    position_type: int
    position_scale: float
    vertex_stream_offset: int
    index_stream_offset: int
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)

    @property
    def material_label(self) -> str:
        # The serialized loose MESH stores this native reference token rather
        # than a human-readable MAT filename.  Keep the raw value truthful.
        return f"0x{self.material_ref:08X}"


@dataclass
class SM3MeshDocument:
    path: Path
    magic: int
    embedded_hash: int
    flags: int
    section_count: int
    data_start: int
    sections: list[SM3MeshSection]
    filename_hash: int | None = None
    filename_asset_name: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def vertex_count(self) -> int:
        return sum(s.vertex_count for s in self.sections)

    @property
    def triangle_count(self) -> int:
        return sum(s.triangle_count for s in self.sections)

    @property
    def file_size(self) -> int:
        try:
            return self.path.stat().st_size
        except Exception:
            return 0

    @property
    def display_name(self) -> str:
        return self.filename_asset_name or self.path.stem

    def all_positions(self, visible: set[int] | None = None) -> list[tuple[float, float, float]]:
        out: list[tuple[float, float, float]] = []
        for sec in self.sections:
            if visible is not None and sec.index not in visible:
                continue
            out.extend(sec.positions)
        return out


# D3DDECLTYPE values used by SM3's NGL mesh declaration.
_TYPE_SIZES = {
    0: 4,    # FLOAT1
    1: 8,    # FLOAT2
    2: 12,   # FLOAT3
    3: 16,   # FLOAT4
    4: 4,    # D3DCOLOR
    5: 4,    # UBYTE4
    6: 4,    # SHORT2
    7: 8,    # SHORT4
    8: 4,    # UBYTE4N
    9: 4,    # SHORT2N
    10: 8,   # SHORT4N
    11: 4,   # USHORT2N
    12: 8,   # USHORT4N
    13: 4,   # UDEC3
    14: 4,   # DEC3N
    15: 4,   # FLOAT16_2
    16: 8,   # FLOAT16_4
}

# Native SM3 fixed-point meshes in the CH_SPIDERMAN family use 512 or 1000;
# other in-game assets use the larger quantization steps below.  We infer the
# actual step from each section's serialized bounds instead of filename rules.
_COMMON_POSITION_SCALES = (64, 128, 256, 512, 1000, 1024, 2048, 4096, 8192, 16384, 32767)
_FILENAME_RE = re.compile(r"^0x([0-9A-Fa-f]{8})\.(.+)\.mesh$", re.IGNORECASE)


def _align16(value: int) -> int:
    return (value + 15) & ~15


def _read(fmt: str, data: bytes, offset: int):
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise SM3MeshError(f"Unexpected end of file at 0x{offset:X} while reading {fmt}.")
    return struct.unpack_from(fmt, data, offset)


def _parse_filename(path: Path) -> tuple[int | None, str]:
    m = _FILENAME_RE.match(path.name)
    if not m:
        return None, path.stem
    return int(m.group(1), 16), m.group(2)


def _parse_metadata(data: bytes):
    if len(data) < 0x50:
        raise SM3MeshError("File is too small to be a native SM3 MESH resource.")

    magic, mesh_hash, flags, section_count = _read("<4I", data, 0)
    if (magic & 0xFF000000) != 0xFC000000:
        raise SM3MeshError(
            f"Not a supported native SM3 MESH resource (header 0x{magic:08X})."
        )
    if section_count <= 0 or section_count > 4096:
        raise SM3MeshError(f"Invalid SM3 section count: {section_count}.")

    # The native top-level table is 0x50 bytes plus one 8-byte slot per section,
    # aligned to 16.  Section declarations then follow sequentially.
    offset = _align16(0x50 + section_count * 8)
    sections = []

    for sec_index in range(section_count):
        metadata_offset = offset
        if offset + 32 + 56 > len(data):
            raise SM3MeshError(f"Section {sec_index}: truncated metadata.")

        bounds = _read("<8f", data, offset)
        offset += 32
        fields = _read("<14I", data, offset)
        offset += 56

        material_ref = int(fields[0])
        bone_count = int(fields[2])
        vertex_count = int(fields[5])
        index_count = int(fields[9])

        if bone_count > 2048:
            raise SM3MeshError(f"Section {sec_index}: impossible bone palette count {bone_count}.")
        if vertex_count > 10_000_000 or index_count > 50_000_000:
            raise SM3MeshError(f"Section {sec_index}: impossible vertex/index counts.")

        if offset + bone_count * 2 > len(data):
            raise SM3MeshError(f"Section {sec_index}: truncated bone palette.")
        bones = _read(f"<{bone_count}H", data, offset) if bone_count else ()
        offset += bone_count * 2
        offset = (offset + 3) & ~3

        stride, _native_aux1, _native_aux2 = _read("<3I", data, offset)
        offset += 12
        if stride <= 0 or stride > 1024:
            raise SM3MeshError(f"Section {sec_index}: invalid vertex stride {stride}.")

        fvf: list[FVFEntry] = []
        for _ in range(64):
            chan, pos, dtype, usage = _read("<4H", data, offset)
            offset += 8
            if (chan, pos, dtype, usage) == (0x00FF, 0x0000, 0x0011, 0x0000):
                break
            if pos >= stride or dtype not in _TYPE_SIZES:
                raise SM3MeshError(
                    f"Section {sec_index}: unsupported/corrupt vertex declaration "
                    f"(channel={chan}, offset={pos}, type={dtype}, usage={usage})."
                )
            if pos + _TYPE_SIZES[dtype] > stride:
                raise SM3MeshError(f"Section {sec_index}: vertex declaration exceeds stride.")
            fvf.append(FVFEntry(chan, pos, dtype, usage))
        else:
            raise SM3MeshError(f"Section {sec_index}: vertex declaration sentinel not found.")

        sections.append(
            {
                "index": sec_index,
                "metadata_offset": metadata_offset,
                "material_ref": material_ref,
                "bones": tuple(int(x) for x in bones),
                "vertex_count": vertex_count,
                "index_count": index_count,
                "stride": int(stride),
                "bounds": bounds,
                "fvf": tuple(fvf),
            }
        )

        # Every section except the last declaration starts on a 16-byte boundary.
        if sec_index < section_count - 1:
            offset = _align16(offset)

    return magic, mesh_hash, flags, section_count, offset, sections


def _predict_stream_end(meta_sections, data_start: int) -> int:
    offset = data_start
    for i, sec in enumerate(meta_sections):
        offset += sec["vertex_count"] * sec["stride"]
        offset += sec["index_count"] * 2
        # SM3 pads odd 16-bit index streams between sections to a dword.  The
        # final stream is allowed to end without terminal padding.
        if i < len(meta_sections) - 1 and (sec["index_count"] * 2) & 3:
            offset += 2
    return offset


def _detect_data_start(data: bytes, metadata_end: int, meta_sections) -> int:
    # Most assets begin physical data immediately after metadata.  A few native
    # character meshes contain a tiny trailing metadata pair, so search a small,
    # deterministic window and require the complete predicted streams to end at
    # the exact file size.  This avoids heuristic carving.
    exact: list[int] = []
    upper = min(len(data), metadata_end + 0x100)
    for candidate in range(metadata_end, upper + 1, 2):
        if _predict_stream_end(meta_sections, candidate) == len(data):
            exact.append(candidate)
    if not exact:
        raise SM3MeshError(
            "Native MESH metadata parsed, but the vertex/index stream layout does not "
            "match the file size. This MESH variant is not supported yet."
        )
    return exact[0]


def _decode_triangle_strip(indices: Iterable[int], vertex_count: int) -> list[tuple[int, int, int]]:
    faces: list[tuple[int, int, int]] = []
    strip: list[int] = []
    for value in indices:
        ix = int(value)
        if ix == 0xFFFF:
            strip.clear()
            continue
        if ix < 0 or ix >= vertex_count:
            raise SM3MeshError(f"Index {ix} exceeds section vertex count {vertex_count}.")
        strip.append(ix)
        if len(strip) < 3:
            continue
        i = len(strip) - 3
        if i & 1:
            tri = (strip[i + 1], strip[i], strip[i + 2])
        else:
            tri = (strip[i], strip[i + 1], strip[i + 2])
        if tri[0] != tri[1] and tri[1] != tri[2] and tri[2] != tri[0]:
            faces.append(tri)
    return faces


def _infer_short_position_scale(raw_positions: list[tuple[int, int, int]], bounds) -> float:
    if not raw_positions:
        return 1.0

    extents = [abs(float(x)) for x in bounds[4:7]]
    max_extent = max(extents) if extents else 0.0
    mins = [min(v[k] for v in raw_positions) for k in range(3)]
    maxs = [max(v[k] for v in raw_positions) for k in range(3)]

    # At least one sufficiently-large axis normally reaches the serialized
    # section bounds.  Using the largest range ratio also handles sections whose
    # bounds cover a larger paired/LOD region than the individual geometry.
    ratios: list[float] = []
    for axis in range(3):
        extent = extents[axis]
        if extent <= 1e-7:
            continue
        if max_extent > 0 and extent < max_extent * 0.10:
            continue
        raw_range = maxs[axis] - mins[axis]
        if raw_range > 0:
            ratios.append(raw_range / (2.0 * extent))

    if not ratios:
        for axis in range(3):
            extent = extents[axis]
            raw_range = maxs[axis] - mins[axis]
            if extent > 1e-7 and raw_range > 0:
                ratios.append(raw_range / (2.0 * extent))

    estimate = max(ratios) if ratios else 1.0
    estimate = max(1e-6, estimate)
    return float(min(_COMMON_POSITION_SCALES, key=lambda x: abs(math.log(estimate / x))))


def _position_declaration(fvf: tuple[FVFEntry, ...]) -> FVFEntry:
    # D3DDECLUSAGE_POSITION = 0.  Prefer channel 0 where available.
    matches = [entry for entry in fvf if entry.usage == 0]
    if not matches:
        raise SM3MeshError("Section has no POSITION element in its native vertex declaration.")
    matches.sort(key=lambda e: (e.channel != 0, e.offset))
    return matches[0]


def _decode_positions(data: bytes, stream_offset: int, count: int, stride: int,
                      decl: FVFEntry, bounds) -> tuple[list[tuple[float, float, float]], float]:
    positions: list[tuple[float, float, float]] = []

    if decl.data_type == 2:  # FLOAT3
        for i in range(count):
            positions.append(tuple(float(x) for x in _read("<3f", data, stream_offset + i * stride + decl.offset)))
        return positions, 1.0

    if decl.data_type == 3:  # FLOAT4
        for i in range(count):
            vals = _read("<4f", data, stream_offset + i * stride + decl.offset)
            positions.append((float(vals[0]), float(vals[1]), float(vals[2])))
        return positions, 1.0

    if decl.data_type == 7:  # SHORT4, SM3 fixed-point position
        raw: list[tuple[int, int, int]] = []
        for i in range(count):
            vals = _read("<4h", data, stream_offset + i * stride + decl.offset)
            raw.append((int(vals[0]), int(vals[1]), int(vals[2])))
        scale = _infer_short_position_scale(raw, bounds)
        positions = [(x / scale, y / scale, z / scale) for x, y, z in raw]
        return positions, scale

    if decl.data_type == 10:  # SHORT4N fallback
        for i in range(count):
            vals = _read("<4h", data, stream_offset + i * stride + decl.offset)
            positions.append((vals[0] / 32767.0, vals[1] / 32767.0, vals[2] / 32767.0))
        return positions, 32767.0

    raise SM3MeshError(
        f"Unsupported SM3 POSITION declaration type {decl.data_type}. "
        "The viewer only opens native layouts whose geometry can be decoded safely."
    )


def load_sm3_mesh(path: str | Path) -> SM3MeshDocument:
    p = Path(path)
    if p.suffix.lower() != ".mesh":
        raise SM3MeshError("Model Viewer accepts Spider-Man 3 .mesh files only.")
    if not p.is_file():
        raise SM3MeshError(f"MESH file not found: {p}")

    data = p.read_bytes()
    magic, mesh_hash, flags, section_count, metadata_end, meta_sections = _parse_metadata(data)
    data_start = _detect_data_start(data, metadata_end, meta_sections)
    file_hash, asset_name = _parse_filename(p)

    warnings: list[str] = []
    if file_hash is not None and file_hash != mesh_hash:
        warnings.append(
            f"Filename hash 0x{file_hash:08X} does not match embedded MESH hash 0x{mesh_hash:08X}."
        )

    sections: list[SM3MeshSection] = []
    stream = data_start

    for i, meta in enumerate(meta_sections):
        vertex_count = meta["vertex_count"]
        index_count = meta["index_count"]
        stride = meta["stride"]
        vertex_offset = stream
        index_offset = vertex_offset + vertex_count * stride
        index_end = index_offset + index_count * 2
        if index_end > len(data):
            raise SM3MeshError(f"Section {i}: vertex/index stream exceeds file size.")

        pos_decl = _position_declaration(meta["fvf"])
        positions, pos_scale = _decode_positions(
            data, vertex_offset, vertex_count, stride, pos_decl, meta["bounds"]
        )
        indices = _read(f"<{index_count}H", data, index_offset) if index_count else ()
        triangles = _decode_triangle_strip(indices, vertex_count)

        bounds = meta["bounds"]
        sections.append(
            SM3MeshSection(
                index=i,
                metadata_offset=meta["metadata_offset"],
                material_ref=meta["material_ref"],
                bone_palette=meta["bones"],
                vertex_count=vertex_count,
                index_count=index_count,
                stride=stride,
                bounds_center=(float(bounds[0]), float(bounds[1]), float(bounds[2])),
                bounds_radius=float(bounds[3]),
                bounds_extents=(float(bounds[4]), float(bounds[5]), float(bounds[6])),
                fvf=meta["fvf"],
                position_type=pos_decl.data_type,
                position_scale=pos_scale,
                vertex_stream_offset=vertex_offset,
                index_stream_offset=index_offset,
                positions=positions,
                triangles=triangles,
            )
        )

        stream = index_end
        if i < section_count - 1 and (index_count * 2) & 3:
            stream += 2

    if stream != len(data):
        raise SM3MeshError(
            f"Decoded stream ended at 0x{stream:X}, expected exact file end 0x{len(data):X}."
        )

    return SM3MeshDocument(
        path=p,
        magic=magic,
        embedded_hash=mesh_hash,
        flags=flags,
        section_count=section_count,
        data_start=data_start,
        sections=sections,
        filename_hash=file_hash,
        filename_asset_name=asset_name,
        warnings=warnings,
    )
