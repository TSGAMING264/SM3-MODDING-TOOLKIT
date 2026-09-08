#!/usr/bin/env python3
"""
SM3 Toolkit NAS ANIM Decoder Service v0.5

Dependency-free offline decoder for Spider-Man 3 PC ANIM v0x00020116 + ASKL.
Backend used by the SM3 Toolkit New Animation Swapper (NAS) decoder/inspector page.

Current verified fixture:
  ANIM 0xACBAB3E0 pedmidla.anim
  ASKL 0xEE7EAC83 ch_ped.askl
  frame 28 -> bit cursor local 0xA0C, bit offset 7

This module does NOT modify PCPACK/APKF files.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

ANIM_VERSION = 0x00020116
ANIM_HEADER_SIZE = 0xB0
ASKL_OBJECT_LOCAL = 0x60

FIELD_NAMES = [
    "FK_POSITION",
    "FK_QUATERNION",
    "FK_AXIS1_ROTATION",
    "FK_ERROR_CORRECTION",
    "FK_TRAJECTORY",
    "FLOOR_OFFSET",
    "CAMERA_FOV",
    "MORPH_SLIDERS",
    "BONE_SCALE",
]

STORAGE_WIDTH = [4, 4, 1, 4, 8, 1, 1, 1, 4]
COMPRESSED_WIDTH = [3, 4, 1, 3, 0, 1, 1, 1, 3]
EXTENDED_WIDTH_TABLE = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 30]


class DecodeError(RuntimeError):
    pass


def _u16(data: bytes, off: int) -> int:
    if off < 0 or off + 2 > len(data):
        raise DecodeError(f"u16 read out of range at 0x{off:X}")
    return struct.unpack_from("<H", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise DecodeError(f"u32 read out of range at 0x{off:X}")
    return struct.unpack_from("<I", data, off)[0]


def _i32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise DecodeError(f"i32 read out of range at 0x{off:X}")
    return struct.unpack_from("<i", data, off)[0]


def _f32(data: bytes, off: int) -> float:
    if off < 0 or off + 4 > len(data):
        raise DecodeError(f"f32 read out of range at 0x{off:X}")
    return struct.unpack_from("<f", data, off)[0]


def _set_f32(buf: bytearray, off: int, value: float) -> None:
    if off < 0 or off + 4 > len(buf):
        raise DecodeError(f"f32 write out of range at 0x{off:X}")
    struct.pack_into("<f", buf, off, float(value))


def _set_u32(buf: bytearray, off: int, value: int) -> None:
    if off < 0 or off + 4 > len(buf):
        raise DecodeError(f"u32 write out of range at 0x{off:X}")
    struct.pack_into("<I", buf, off, int(value) & 0xFFFFFFFF)


def _read_c_string_ascii(data: bytes, off: int, max_len: int = 256) -> Optional[str]:
    if off < 0 or off >= len(data):
        return None
    end = data.find(b"\x00", off, min(len(data), off + max_len))
    if end < 0:
        return None
    raw = data[off:end]
    if not raw:
        return ""
    if any(b < 0x20 or b > 0x7E for b in raw):
        return None
    return raw.decode("ascii", errors="replace")


def _apfk_special_string_base(payload: bytes) -> Optional[int]:
    """Recover the PCAPK/APKF component-63 string base used by FCxxxxxx tokens."""
    if len(payload) < 0x1C or payload[:4] != b"APKF":
        return None
    component_count = _u32(payload, 0x10)
    if component_count == 0 or component_count > 0x10000:
        return None
    stride = 0x14 + component_count * 4
    off = 0x1C
    special_base: Optional[int] = None
    for _ in range(0x10000):
        if off + 4 > len(payload):
            return None
        typ = _u32(payload, off)
        if typ == 0:
            return special_base
        if off + stride > len(payload):
            return None
        slot_count = _u32(payload, off + 0x08)
        rec_rel = _i32(payload, off + 0x0C)
        rec_count = _u32(payload, off + 0x10)
        if slot_count > 0x10000:
            return None
        if rec_count:
            rec_base = off + 0x0C + rec_rel
            rec_stride = (slot_count + 2) * 4
            rec_end = rec_base + rec_stride * rec_count
            if rec_base < 0 or rec_end > len(payload):
                return None
            special_base = rec_end
        off += stride
    return None


def _resolve_apkf_string_token(payload: bytes, special_base: Optional[int], token: int) -> Optional[str]:
    if special_base is None or token == 0:
        return None
    component = token >> 26
    if component != 0x3F:
        return None
    dword_index = token & 0x03FFFFFF
    return _read_c_string_ascii(payload, special_base + dword_index * 4)


def _bit(mask_words: Tuple[int, ...], index: int) -> int:
    word = index >> 5
    bit = index & 31
    if word >= len(mask_words):
        return 0
    return (mask_words[word] >> bit) & 1


def _game_periodic_scalar(value: float) -> float:
    """Replicate the scalar trig approximation used by FUN_008BCBA0.

    The game feeds -abs(value) * (1 / 4pi) through a periodic reduction and
    polynomial approximation. For the Axis1 helper, value=angle produces the
    cosine half-angle term and value=pi+angle produces the negative sine
    half-angle term. Keeping the recovered approximation here makes the
    exported final quaternion track the runtime path instead of inventing a
    different convention.
    """
    scale = 0.07957747  # game constant ~= 1 / (4*pi)
    reduced_input = -abs(float(value)) * scale
    wrapped = math.ceil(reduced_input)
    f = abs((wrapped - reduced_input) - 0.5) - 0.25
    f2 = f * f
    f4 = f2 * f2
    return (
        f * 6.283185
        + (
            f4 * f * 81.60223
            + (f4 * f4 * f * 39.71066 - f4 * f2 * f * 76.57496)
            - f2 * f * 41.341675
        )
    )


def _axis1_quaternion_game(axis: Tuple[float, float, float, float], angle: float) -> Tuple[float, float, float, float]:
    """Build the Axis1 quaternion recovered from FUN_008BCBA0.

    Bone record +0x00 stores the Axis1 axis vector. The runtime helper creates
    qAxis = axis * (-sin(angle/2)), cos(angle/2) using its periodic trig
    approximation.
    """
    sine_term = _game_periodic_scalar(math.pi + float(angle))
    cosine_term = _game_periodic_scalar(float(angle))
    return (
        float(axis[0]) * sine_term,
        float(axis[1]) * sine_term,
        float(axis[2]) * sine_term,
        cosine_term,
    )


def _quat_mul_xyzw(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """Quaternion multiply a*b for XYZW storage."""
    ax, ay, az, aw = map(float, a)
    bx, by, bz, bw = map(float, b)
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _quat_dot_xyzw(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _quat_normalize_xyzw(q: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    """Normalize an XYZW quaternion for Blender-facing output without touching raw game values."""
    norm_sq = sum(float(v) * float(v) for v in q)
    if norm_sq <= 1.0e-20:
        return (0.0, 0.0, 0.0, 1.0)
    inv = 1.0 / math.sqrt(norm_sq)
    return tuple(float(v) * inv for v in q)  # type: ignore[return-value]


@dataclass
class AnimHeader:
    name_ptr_token: int
    resource_hash: int
    next_token: int
    askl_name_ptr_token: int
    askl_hash: int
    version: int
    unknown18: int
    resolved_askl_serialized: int
    flags: int
    duration_seconds: float
    sample_interval_seconds: float
    unknown2c: int
    sample_count: int
    special_data_ptr_token: int
    compressed_track_count: int
    post_scale_count: int
    post_scale_ptr_token: int
    bitstream_ptr_token: int
    presence_mask: Tuple[int, ...]
    reference_mask: Tuple[int, ...]

    @classmethod
    def parse(cls, data: bytes) -> "AnimHeader":
        if len(data) < ANIM_HEADER_SIZE:
            raise DecodeError(f"ANIM is too small: 0x{len(data):X}")
        vals = struct.unpack_from("<9I2f7I", data, 0)
        # 9I covers +00..+20, 2f +24/+28, 7I +2C..+44
        return cls(
            name_ptr_token=vals[0],
            resource_hash=vals[1],
            next_token=vals[2],
            askl_name_ptr_token=vals[3],
            askl_hash=vals[4],
            version=vals[5],
            unknown18=vals[6],
            resolved_askl_serialized=vals[7],
            flags=vals[8],
            duration_seconds=vals[9],
            sample_interval_seconds=vals[10],
            unknown2c=vals[11],
            sample_count=vals[12],
            special_data_ptr_token=vals[13],
            compressed_track_count=vals[14],
            post_scale_count=vals[15],
            post_scale_ptr_token=vals[16],
            bitstream_ptr_token=vals[17],
            presence_mask=struct.unpack_from("<13I", data, 0x48),
            reference_mask=struct.unpack_from("<13I", data, 0x7C),
        )

    def resolve_local_pointer(self, token: int) -> Optional[int]:
        """Resolve ordinary same-component ANIM pointer token using +44 -> local +0xB0 anchor."""
        if token == 0:
            return None
        return ANIM_HEADER_SIZE + (token - self.bitstream_ptr_token) * 4


@dataclass(frozen=True)
class AnimInputInfo:
    data: bytes
    container: str
    archive_hash: Optional[int] = None
    component_count: int = 1


def _normalize_anim_input(data: bytes) -> AnimInputInfo:
    """Normalize a loose SM3 ANIM or standalone NativeWRAP ``*.wrap.anim``.

    Motion Editor/decoder code historically consumed the classic extractor's
    loose ``*.anim`` bytes directly.  MOD LOADER READY now exposes the same
    resource as a standalone WRAP container, so unwrap the serialized ANIM
    component before any header/codec/skeleton work.
    """
    if data[:4] != b"WRAP":
        # Let the normal ANIM parser provide detailed validation later.
        return AnimInputInfo(data=data, container="RAW_ANIM")
    if len(data) < 0x14:
        raise DecodeError("WRAP ANIM is too small for the 0x14-byte WRAP header")
    archive_hash = _u32(data, 0x04)
    component_count = _u32(data, 0x0C)
    if component_count < 1 or component_count > 2:
        raise DecodeError(f"WRAP ANIM has unsupported component count: {component_count}")
    table_rel = struct.unpack_from("<i", data, 0x10)[0]
    table = 0x10 + table_rel
    if table < 0 or table + component_count * 8 > len(data):
        raise DecodeError("WRAP ANIM component table is outside the file")

    components = []
    starts = []
    for i in range(component_count):
        entry = table + i * 8
        size = _u32(data, entry)
        ptr_field = entry + 4
        rel = struct.unpack_from("<i", data, ptr_field)[0]
        start = ptr_field + rel
        end = start + size
        if start < 0 or size <= 0 or end > len(data):
            raise DecodeError(
                f"WRAP ANIM component {i} range is invalid: ptr=0x{start:X} size=0x{size:X}"
            )
        starts.append(start)
        components.append(bytearray(data[start:end]))

    # NativeWRAP stores internal pointer fields as byte-relative offsets so the
    # runtime can fix them directly.  The offline ANIM codec uses the original
    # APKF word-token convention instead.  Reconstruct an equivalent canonical
    # token space from the WRAP internal patch list.  Only pointer fields change;
    # animation identity, compressed motion bytes and external references stay
    # untouched.
    patch_rel = struct.unpack_from("<i", data, 0x08)[0]
    patch = 0x08 + patch_rel
    if patch < 0 or patch + 24 > len(data):
        raise DecodeError("WRAP ANIM patch table is outside the file")
    internal_count = _u32(data, patch + 8)
    internal_list_rel = struct.unpack_from("<i", data, patch + 12)[0]
    internal_list = (patch + 12) + internal_list_rel
    if internal_list < 0 or internal_list + internal_count * 4 > len(data):
        raise DecodeError("WRAP ANIM internal patch list is outside the file")

    canonical_base_token = 0x00100000
    comp0 = components[0]
    comp0_start = starts[0]
    for i in range(internal_count):
        field = internal_list + i * 4
        target_abs = field + struct.unpack_from("<i", data, field)[0]
        target_off = target_abs - comp0_start
        if target_off < 0 or target_off + 4 > len(comp0):
            # ANIM should be one-component.  Refuse to silently rewrite a patch
            # target owned by a different component.
            raise DecodeError(
                f"WRAP ANIM internal patch target is outside component0: 0x{target_abs:X}"
            )
        rel_value = struct.unpack_from("<i", comp0, target_off)[0]
        ref_off = target_off + rel_value
        if ref_off < 0 or ref_off >= len(comp0):
            raise DecodeError(
                f"WRAP ANIM internal reference +0x{target_off:X} resolves outside component0: +0x{ref_off:X}"
            )
        if ref_off & 3:
            raise DecodeError(
                f"WRAP ANIM internal reference +0x{target_off:X} is not dword-aligned: +0x{ref_off:X}"
            )
        token = canonical_base_token + (ref_off // 4)
        struct.pack_into("<I", comp0, target_off, token & 0xFFFFFFFF)

    component = bytes(comp0)
    try:
        hdr = AnimHeader.parse(component)
    except Exception as exc:
        raise DecodeError(f"WRAP component0 is not a supported SM3 ANIM: {exc}") from exc
    if int(hdr.version) != ANIM_VERSION:
        raise DecodeError(
            f"WRAP ANIM version 0x{int(hdr.version):08X} is unsupported; expected 0x{ANIM_VERSION:08X}"
        )
    return AnimInputInfo(
        data=component,
        container="WRAP_ANIM",
        archive_hash=archive_hash,
        component_count=component_count,
    )


def normalize_anim_bytes(data: bytes) -> bytes:
    """Return canonical loose-ANIM bytes from raw ANIM or standalone WRAP.ANIM bytes."""
    return _normalize_anim_input(bytes(data)).data


def read_anim_payload(anim_path: str | os.PathLike[str]) -> bytes:
    """Return the serialized inner ANIM bytes from loose or WRAP input."""
    path = Path(anim_path)
    if not path.is_file():
        raise FileNotFoundError(f"ANIM not found: {path}")
    return normalize_anim_bytes(path.read_bytes())


@dataclass
class AsklBoneRecord:
    index: int
    parent_index: int
    name_ptr_token: int
    name_hash: int
    axis1_vector: Tuple[float, float, float, float]
    bind_quaternion: Tuple[float, float, float, float]
    bind_position: Tuple[float, float, float, float]


@dataclass
class AsklInputInfo:
    data: bytes
    container: str
    pointer_mode: str
    resource_hash_override: Optional[int] = None
    component_index: Optional[int] = None


def _normalize_askl_input(data: bytes) -> AsklInputInfo:
    """Normalize raw ASKL bytes or a standalone NativeWRAP ``*.wrap.askl``.

    Classic extractor ASKLs use APKF word tokens.  MOD LOADER READY WRAPs
    store internal pointers as field-relative byte offsets plus a WRAP patch
    list.  Convert only those internal pointer fields into component-local byte
    offsets so the existing ASKL layout parser can consume the skeleton safely.
    """
    if len(data) < 4 or data[:4] != b"WRAP":
        return AsklInputInfo(data=data, container="RAW_ASKL", pointer_mode="apfk_word_token")

    if len(data) < 20:
        raise DecodeError("WRAP ASKL is too small for the 0x14-byte WRAP header")
    component_count = _u32(data, 0x0C)
    if component_count <= 0 or component_count > 2:
        raise DecodeError(f"WRAP ASKL has invalid component count: {component_count}")
    table = 0x10 + struct.unpack_from("<i", data, 0x10)[0]
    if table < 0 or table + component_count * 8 > len(data):
        raise DecodeError(
            f"WRAP ASKL component table is outside file: 0x{table:X}..0x{table + component_count * 8:X}"
        )

    starts: List[int] = []
    components: List[bytearray] = []
    for i in range(component_count):
        entry = table + i * 8
        size = _u32(data, entry)
        ptr_field = entry + 4
        start = ptr_field + struct.unpack_from("<i", data, ptr_field)[0]
        if size <= 0 or start < 0 or start + size > len(data):
            raise DecodeError(
                f"WRAP ASKL component {i} range is invalid: ptr=0x{start:X} size=0x{size:X}"
            )
        starts.append(start)
        components.append(bytearray(data[start:start + size]))

    patch = 0x08 + struct.unpack_from("<i", data, 0x08)[0]
    if patch < 0 or patch + 24 > len(data):
        raise DecodeError("WRAP ASKL patch table is outside the file")
    internal_count = _u32(data, patch + 8)
    internal_list = (patch + 12) + struct.unpack_from("<i", data, patch + 12)[0]
    if internal_list < 0 or internal_list + internal_count * 4 > len(data):
        raise DecodeError("WRAP ASKL internal patch list is outside the file")

    # ASKL WRAPs in the current corpus are one-component.  Convert the WRAP
    # field-relative internal references to component-local byte offsets.
    comp0 = components[0]
    comp0_start = starts[0]
    for i in range(internal_count):
        field = internal_list + i * 4
        target_abs = field + struct.unpack_from("<i", data, field)[0]
        target_off = target_abs - comp0_start
        if target_off < 0 or target_off + 4 > len(comp0):
            raise DecodeError(
                f"WRAP ASKL internal patch target is outside component0: 0x{target_abs:X}"
            )
        rel_value = struct.unpack_from("<i", comp0, target_off)[0]
        ref_off = target_off + rel_value
        if ref_off < 0 or ref_off >= len(comp0):
            raise DecodeError(
                f"WRAP ASKL internal reference +0x{target_off:X} resolves outside component0: +0x{ref_off:X}"
            )
        struct.pack_into("<I", comp0, target_off, ref_off & 0xFFFFFFFF)

    component = bytes(comp0)
    resource_hash = _u32(component, 0x04) if len(component) >= 8 else None
    if resource_hash is None:
        raise DecodeError("WRAP ASKL component is too small to contain its resource hash")
    try:
        AsklLayout._parse_layout(
            component,
            pointer_mode="byte_relative",
            resource_hash_override=resource_hash,
            allow_scan=True,
        )
    except Exception as exc:
        raise DecodeError(
            f"WRAP ASKL was detected, but component0 did not contain a supported skeleton layout: {exc}"
        ) from exc
    return AsklInputInfo(
        data=component,
        container="WRAP_ASKL",
        pointer_mode="byte_relative",
        resource_hash_override=resource_hash,
        component_index=0,
    )


@dataclass
class AsklLayout:
    resource_hash: int
    object_local: int
    object_self_token: int
    pose_data_local: int
    pose_data_size: int
    field_counts: Tuple[int, ...]
    field_data_offsets: Tuple[int, ...]
    validity_bit_bases: Tuple[int, ...]
    total_validity_bits: int
    scale_locals: Tuple[Optional[int], ...]
    scales: Tuple[Optional[Tuple[float, ...]], ...]
    bone_node_local: Optional[int]
    bone_count: int
    bone_records_local: Optional[int]
    bone_records: Tuple[AsklBoneRecord, ...]
    position_bone_map: Tuple[int, ...]
    quaternion_bone_map: Tuple[int, ...]
    axis1_bone_map: Tuple[int, ...]

    @classmethod
    def parse(
        cls,
        data: bytes,
        *,
        pointer_mode: str = "apfk_word_token",
        resource_hash_override: Optional[int] = None,
    ) -> "AsklLayout":
        return cls._parse_layout(
            data,
            pointer_mode=pointer_mode,
            resource_hash_override=resource_hash_override,
            allow_scan=(pointer_mode == "byte_relative"),
        )

    @classmethod
    def _parse_layout(
        cls,
        data: bytes,
        *,
        pointer_mode: str,
        resource_hash_override: Optional[int],
        allow_scan: bool,
    ) -> "AsklLayout":
        if pointer_mode not in {"apfk_word_token", "byte_relative"}:
            raise DecodeError(f"unsupported ASKL pointer mode: {pointer_mode}")

        if pointer_mode == "apfk_word_token":
            if len(data) < ASKL_OBJECT_LOCAL + 0xBC:
                raise DecodeError(f"ASKL is too small: 0x{len(data):X}")
            object_candidates = [ASKL_OBJECT_LOCAL]
        else:
            if len(data) < 0xBC:
                raise DecodeError(f"WRAP ASKL component is too small: 0x{len(data):X}")
            # Normal standalone WRAP component starts with the ASKL object.
            # Scan a small aligned prefix as a compatibility fallback.
            object_candidates = [0]
            if allow_scan:
                object_candidates.extend(range(4, min(0x200, len(data) - 0xBC + 1), 4))

        last_error: Optional[Exception] = None
        for object_local in object_candidates:
            try:
                return cls._parse_at_object(
                    data,
                    object_local=object_local,
                    pointer_mode=pointer_mode,
                    resource_hash_override=resource_hash_override,
                )
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise DecodeError(str(last_error))
        raise DecodeError("ASKL object was not found")

    @classmethod
    def _parse_at_object(
        cls,
        data: bytes,
        *,
        object_local: int,
        pointer_mode: str,
        resource_hash_override: Optional[int],
    ) -> "AsklLayout":
        if object_local < 0 or object_local + 0xBC > len(data):
            raise DecodeError(f"ASKL object candidate 0x{object_local:X} is outside file")

        if pointer_mode == "apfk_word_token":
            header_ref_token = _u32(data, 0x0C)
            object_self_token = _u32(data, object_local + 0x00)
            if header_ref_token != object_self_token:
                raise DecodeError(
                    f"ASKL +0x0C token 0x{header_ref_token:08X} does not match "
                    f"embedded object self token 0x{object_self_token:08X} at local +0x{object_local:X}"
                )

            def resolve(token: int) -> Optional[int]:
                if token == 0:
                    return None
                off = object_local + (token - object_self_token) * 4
                if off < 0 or off >= len(data):
                    raise DecodeError(f"ASKL token 0x{token:08X} resolves outside file: 0x{off:X}")
                return off

            resource_hash = _u32(data, 0x04) if resource_hash_override is None else resource_hash_override
        else:
            # WRAP internal patches are standalone byte offsets inside the
            # component. The object normally begins at +0, but the scanner
            # permits a small prefix if present.
            object_self_token = object_local

            def resolve(token: int) -> Optional[int]:
                if token == 0:
                    return None
                off = int(token)
                if off < 0 or off >= len(data):
                    raise DecodeError(f"WRAP ASKL byte offset 0x{token:08X} is outside component")
                return off

            if resource_hash_override is None:
                raise DecodeError("WRAP ASKL requires resource hash from WRAP header")
            resource_hash = resource_hash_override

        pose_data_local = resolve(_u32(data, object_local + 0x04))
        if pose_data_local is None:
            raise DecodeError("ASKL reference poseData pointer is NULL")
        pose_data_size = _u32(data, object_local + 0x5C)
        if pose_data_size <= 0 or pose_data_local + pose_data_size > len(data):
            raise DecodeError(
                f"ASKL poseData exceeds file: local 0x{pose_data_local:X} + 0x{pose_data_size:X}"
            )

        counts = struct.unpack_from("<9H", data, object_local + 0x84)
        offsets = struct.unpack_from("<9H", data, object_local + 0x96)
        bases = struct.unpack_from("<9H", data, object_local + 0xA8)
        total_bits = _u16(data, object_local + 0xBA)

        # Strong structural guard used by the WRAP object scan: every pose field
        # must fit inside the serialized reference-pose storage and every
        # validity-bit range must fit inside total_validity_bits.
        if not any(counts):
            raise DecodeError("ASKL object candidate has zero elements in all 9 fields")
        if any(c > 0x4000 for c in counts):
            raise DecodeError("ASKL object candidate has implausible field element count")
        required_pose = 0
        for i, count in enumerate(counts):
            required_pose = max(required_pose, offsets[i] + count * STORAGE_WIDTH[i] * 4)
            if count and bases[i] + count > total_bits:
                raise DecodeError("ASKL validity-bit range exceeds total validity bits")
        if required_pose > pose_data_size:
            raise DecodeError(
                f"ASKL pose field layout needs 0x{required_pose:X} bytes but poseData is 0x{pose_data_size:X}"
            )

        scale_tokens = struct.unpack_from("<9I", data, object_local + 0x60)
        scale_locals: List[Optional[int]] = []
        scale_arrays: List[Optional[Tuple[float, ...]]] = []
        for count, tok in zip(counts, scale_tokens):
            off = resolve(tok) if tok else None
            scale_locals.append(off)
            if off is None:
                scale_arrays.append(None)
            else:
                end = off + count * 4
                if end > len(data):
                    raise DecodeError(f"ASKL scale array at 0x{off:X} exceeds file")
                scale_arrays.append(struct.unpack_from("<" + "f" * count, data, off))

        # ASKL +0x08 points at a linked list. SkeletonPose_BuildBoneMatrices receives
        # FUN_008BDB70(resolvedASKL, 0), so key==0 is the bone-map node.
        # v5.2.191: raw ASKL and NativeWRAP ASKL both retain the ASKL resource
        # header at component +0.  The key-node list head is header +0x08, not
        # object_local +0x08.  The old WRAP branch happened to parse pose fields
        # but dropped named bone records for layouts whose object starts at +0x60
        # (for example CH_PLAYERGOBLIN / 0x900E49A5).
        bone_head_token = _u32(data, 0x08)
        bone_node_local = resolve(bone_head_token) if bone_head_token else None
        seen_nodes = set()
        while bone_node_local is not None:
            if bone_node_local in seen_nodes:
                raise DecodeError("ASKL bone-node linked list contains a cycle")
            seen_nodes.add(bone_node_local)
            if bone_node_local + 8 > len(data):
                raise DecodeError("ASKL bone-node header exceeds file")
            key = _u32(data, bone_node_local + 0x00)
            if key == 0:
                break
            next_token = _u32(data, bone_node_local + 0x04)
            bone_node_local = resolve(next_token) if next_token else None

        bone_count = 0
        bone_records_local: Optional[int] = None
        bone_records: List[AsklBoneRecord] = []
        position_bone_map: Tuple[int, ...] = ()
        quaternion_bone_map: Tuple[int, ...] = ()
        axis1_bone_map: Tuple[int, ...] = ()
        if bone_node_local is not None:
            bone_count = _u32(data, bone_node_local + 0x08)
            bone_records_local = resolve(_u32(data, bone_node_local + 0x0C))
            pos_map_local = resolve(_u32(data, bone_node_local + 0x10)) if counts[0] else None
            quat_map_local = resolve(_u32(data, bone_node_local + 0x14)) if counts[1] else None
            axis_map_local = resolve(_u32(data, bone_node_local + 0x18)) if counts[2] else None
            if bone_count and bone_records_local is None:
                raise DecodeError("ASKL key-0 bone node has NULL bone-record pointer")
            if bone_count > 0x10000:
                raise DecodeError("ASKL bone count is implausibly large")
            if bone_records_local is not None:
                end = bone_records_local + bone_count * 0x40
                if end > len(data):
                    raise DecodeError("ASKL bone-record table exceeds file")
                for i in range(bone_count):
                    bo = bone_records_local + i * 0x40
                    bone_records.append(AsklBoneRecord(
                        index=i,
                        parent_index=_i32(data, bo + 0x30),
                        name_ptr_token=_u32(data, bo + 0x34),
                        name_hash=_u32(data, bo + 0x38),
                        axis1_vector=struct.unpack_from("<4f", data, bo + 0x00),
                        bind_quaternion=struct.unpack_from("<4f", data, bo + 0x10),
                        bind_position=struct.unpack_from("<4f", data, bo + 0x20),
                    ))
            if counts[0]:
                if pos_map_local is None or pos_map_local + counts[0] * 2 > len(data):
                    raise DecodeError("ASKL position->bone map exceeds file")
                position_bone_map = struct.unpack_from("<" + "H" * counts[0], data, pos_map_local)
            if counts[1]:
                if quat_map_local is None or quat_map_local + counts[1] * 2 > len(data):
                    raise DecodeError("ASKL quaternion->bone map exceeds file")
                quaternion_bone_map = struct.unpack_from("<" + "H" * counts[1], data, quat_map_local)
            if counts[2]:
                if axis_map_local is None or axis_map_local + counts[2] * 2 > len(data):
                    raise DecodeError("ASKL axis1->bone map exceeds file")
                axis1_bone_map = struct.unpack_from("<" + "H" * counts[2], data, axis_map_local)

        return cls(
            resource_hash=resource_hash,
            object_local=object_local,
            object_self_token=object_self_token,
            pose_data_local=pose_data_local,
            pose_data_size=pose_data_size,
            field_counts=counts,
            field_data_offsets=offsets,
            validity_bit_bases=bases,
            total_validity_bits=total_bits,
            scale_locals=tuple(scale_locals),
            scales=tuple(scale_arrays),
            bone_node_local=bone_node_local,
            bone_count=bone_count,
            bone_records_local=bone_records_local,
            bone_records=tuple(bone_records),
            position_bone_map=tuple(position_bone_map),
            quaternion_bone_map=tuple(quaternion_bone_map),
            axis1_bone_map=tuple(axis1_bone_map),
        )



class BitReader:
    """SM3 ANIM bit reader: little-endian 32-bit words, LSB-first."""

    def __init__(self, data: bytes, byte_offset: int):
        if byte_offset < 0 or byte_offset >= len(data):
            raise DecodeError(f"bitstream start 0x{byte_offset:X} is outside file")
        self.data = data
        self.byte_offset = byte_offset
        self.bit_offset = 0

    def read_bits(self, count: int) -> int:
        if count < 0 or count > 32:
            raise DecodeError(f"invalid bit count: {count}")
        if count == 0:
            return 0
        remaining = count
        out = 0
        out_shift = 0
        while remaining:
            if self.byte_offset + 4 > len(self.data):
                raise DecodeError(
                    f"compressed bitstream overrun at 0x{self.byte_offset:X} bit {self.bit_offset}"
                )
            word = _u32(self.data, self.byte_offset)
            available = 32 - self.bit_offset
            take = min(remaining, available)
            mask = 0xFFFFFFFF if take == 32 else ((1 << take) - 1)
            out |= ((word >> self.bit_offset) & mask) << out_shift
            self.bit_offset += take
            remaining -= take
            out_shift += take
            if self.bit_offset == 32:
                self.byte_offset += 4
                self.bit_offset = 0
        return out


@dataclass
class TrackState:
    codec: int = 0
    previous_value: int = 0
    current_value: int = 0


class CompressedTrackDecoder:
    def __init__(self, anim_data: bytes, header: AnimHeader):
        self.anim_data = anim_data
        self.header = header
        self.track_count = header.compressed_track_count
        self.reader: BitReader
        self.tracks: List[TrackState]
        self.current_decoded_frame: int
        self.reset()

    @staticmethod
    def _decode_signed_value(reader: BitReader, codec: int) -> int:
        mode = codec >> 2
        base_bits = (codec & 3) + 2
        if mode == 0:
            return 0
        if reader.read_bits(1) == 0:
            return 0
        extended = reader.read_bits(1) != 0
        payload_bits = (EXTENDED_WIDTH_TABLE[mode] if extended else base_bits) + 1
        encoded = reader.read_bits(payload_bits)
        magnitude = 1 + (encoded >> 1)
        if extended:
            magnitude += 1 << base_bits
        return -magnitude if (encoded & 1) else magnitude

    def reset(self) -> None:
        bitstream_local = self.header.resolve_local_pointer(self.header.bitstream_ptr_token)
        if bitstream_local != ANIM_HEADER_SIZE:
            raise DecodeError(
                f"ANIM +44 does not resolve to local +0x{ANIM_HEADER_SIZE:X}: got {bitstream_local}"
            )
        self.reader = BitReader(self.anim_data, bitstream_local)
        self.tracks = [TrackState() for _ in range(self.track_count)]

        # Pass 1: frame 0 absolute integer values.
        for t in self.tracks:
            control = self.reader.read_bits(6)
            t.previous_value = self._decode_signed_value(self.reader, control)

        # Pass 2: frame 1 delta from frame 0.
        for t in self.tracks:
            control = self.reader.read_bits(6)
            t.current_value = t.previous_value + self._decode_signed_value(self.reader, control)

        # Pass 3: persistent 6-bit per-track residual codec.
        for t in self.tracks:
            t.codec = self.reader.read_bits(6)

        self.current_decoded_frame = 1

    def advance(self, requested_frame: int) -> None:
        if requested_frame < 0 or requested_frame >= self.header.sample_count:
            raise DecodeError(
                f"requested frame {requested_frame} is outside 0..{self.header.sample_count - 1}"
            )
        # Exact game behavior: retain current and previous; reset only if seek is earlier than previous.
        if requested_frame < self.current_decoded_frame - 1:
            self.reset()

        while self.current_decoded_frame < requested_frame:
            for t in self.tracks:
                residual = self._decode_signed_value(self.reader, t.codec)
                nxt = residual + 2 * t.current_value - t.previous_value
                t.previous_value = t.current_value
                t.current_value = nxt
            self.current_decoded_frame += 1

    def get_frame_values(self, requested_frame: int) -> List[int]:
        self.advance(requested_frame)
        if requested_frame == self.current_decoded_frame - 1:
            return [t.previous_value for t in self.tracks]
        return [t.current_value for t in self.tracks]

    @property
    def cursor(self) -> Tuple[int, int]:
        return self.reader.byte_offset, self.reader.bit_offset


@dataclass
class FieldElementResult:
    field_index: int
    field_name: str
    element_index: int
    source: str
    scale: Optional[float]
    raw_integers: List[int]
    values: List[Optional[float]]
    note: str = ""
    bone_index: Optional[int] = None
    bone_hash: Optional[int] = None
    bone_name_token: Optional[int] = None
    bone_name: Optional[str] = None
    sparse_id: Optional[int] = None


@dataclass
class DecodeResult:
    anim_hash: int
    askl_hash: int
    frame: int
    sample_count: int
    compressed_track_count: int
    consumed_scalar_count: int
    cursor_byte_offset: int
    cursor_bit_offset: int
    reference_counts: List[int]
    compressed_counts: List[int]
    field_elements: List[FieldElementResult]
    raw_scalars: List[int]
    golden_checks: Dict[str, Any]

    def to_jsonable(self) -> Dict[str, Any]:
        d = asdict(self)
        d["anim_hash"] = f"0x{self.anim_hash:08X}"
        d["askl_hash"] = f"0x{self.askl_hash:08X}"
        d["cursor_byte_offset"] = f"0x{self.cursor_byte_offset:X}"
        return d



@dataclass
class BoneFrameRow:
    frame: int
    time_seconds: float
    bone_index: int
    bone_name: str
    parent_bone_index: int
    bone_hash: int
    bone_name_token: int
    position_x: float
    position_y: float
    position_z: float
    position_source: str
    quaternion_x: float
    quaternion_y: float
    quaternion_z: float
    quaternion_w: float
    quaternion_source: str
    blender_quaternion_x: float = 0.0
    blender_quaternion_y: float = 0.0
    blender_quaternion_z: float = 0.0
    blender_quaternion_w: float = 1.0
    blender_quaternion_flipped: bool = False
    blender_quaternion_raw_dot_previous: Optional[float] = None
    blender_quaternion_dot_previous: Optional[float] = None
    blender_quaternion_source: str = "RAW_GAME_NORMALIZED"
    axis1: Optional[float] = None
    axis1_source: str = ""
    axis1_axis_x: Optional[float] = None
    axis1_axis_y: Optional[float] = None
    axis1_axis_z: Optional[float] = None
    axis1_quaternion_x: Optional[float] = None
    axis1_quaternion_y: Optional[float] = None
    axis1_quaternion_z: Optional[float] = None
    axis1_quaternion_w: Optional[float] = None
    error_correction_x: Optional[float] = None
    error_correction_y: Optional[float] = None
    error_correction_z: Optional[float] = None
    error_correction_source: str = ""
    bone_scale_x: Optional[float] = None
    bone_scale_y: Optional[float] = None
    bone_scale_z: Optional[float] = None
    bone_scale_source: str = ""
    rotation_note: str = ""


@dataclass
class AnimationDecodeResult:
    anim_hash: int
    askl_hash: int
    sample_count: int
    sample_interval_seconds: float
    duration_seconds: float
    compressed_track_count: int
    bone_count: int
    resolved_bone_names: int
    frame_cursors: List[Dict[str, Any]]
    bone_rows: List[BoneFrameRow]
    notes: List[str]

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "anim_hash": f"0x{self.anim_hash:08X}",
            "askl_hash": f"0x{self.askl_hash:08X}",
            "sample_count": self.sample_count,
            "sample_interval_seconds": self.sample_interval_seconds,
            "duration_seconds": self.duration_seconds,
            "compressed_track_count": self.compressed_track_count,
            "bone_count": self.bone_count,
            "resolved_bone_names": self.resolved_bone_names,
            "frame_cursors": self.frame_cursors,
            "bone_rows": [asdict(row) for row in self.bone_rows],
            "notes": self.notes,
        }


class SM3AnimPoseDecoder:
    def __init__(self, anim_data: bytes, askl_data: bytes, parent_apkf_data: Optional[bytes] = None):
        self.anim_data = anim_data
        self.parent_apkf_data = parent_apkf_data
        self.anim = AnimHeader.parse(anim_data)
        self.askl_input = _normalize_askl_input(askl_data)
        self.askl_data = self.askl_input.data
        self.askl = AsklLayout.parse(
            self.askl_data,
            pointer_mode=self.askl_input.pointer_mode,
            resource_hash_override=self.askl_input.resource_hash_override,
        )

        if self.anim.version != ANIM_VERSION:
            raise DecodeError(
                f"unsupported ANIM version 0x{self.anim.version:08X}; expected 0x{ANIM_VERSION:08X}"
            )
        if self.anim.askl_hash != self.askl.resource_hash:
            raise DecodeError(
                f"ANIM expects ASKL 0x{self.anim.askl_hash:08X}, but selected ASKL is "
                f"0x{self.askl.resource_hash:08X}"
            )
        if len(self.askl.field_counts) != 9:
            raise DecodeError("ASKL does not have 9 pose fields")

        self.parent_apkf_string_base = (
            _apfk_special_string_base(parent_apkf_data) if parent_apkf_data is not None else None
        )
        self.bone_names: Dict[int, str] = {}
        if parent_apkf_data is not None and self.parent_apkf_string_base is not None:
            for bone in self.askl.bone_records:
                name = _resolve_apkf_string_token(
                    parent_apkf_data, self.parent_apkf_string_base, bone.name_ptr_token
                )
                if name:
                    self.bone_names[bone.index] = name

        # MOD LOADER READY WRAP.ASKL intentionally carries relocation metadata,
        # not the APKF filename string table.  For known playable-character
        # skeletons, fill any missing names from the built-in profile recovered
        # from the user's old/raw route.  The actual WRAP.ASKL layout/maps/scales
        # still remain authoritative; this fallback supplies names only.
        if len(self.bone_names) < len(self.askl.bone_records):
            try:
                from sm3_toolkit.services.spiderman_named_profile_service import profile_bone_names
                builtin_names = profile_bone_names(self.askl.resource_hash)
                for bone in self.askl.bone_records:
                    if bone.index not in self.bone_names and bone.index in builtin_names:
                        self.bone_names[bone.index] = builtin_names[bone.index]
            except Exception:
                pass

        self.reference_indices: List[List[int]] = []
        self.compressed_indices: List[List[int]] = []
        for count, bit_base in zip(self.askl.field_counts, self.askl.validity_bit_bases):
            ref: List[int] = []
            comp: List[int] = []
            for element in range(count):
                b = bit_base + element
                if _bit(self.anim.reference_mask, b):
                    ref.append(element)
                elif _bit(self.anim.presence_mask, b):
                    comp.append(element)
            self.reference_indices.append(ref)
            self.compressed_indices.append(comp)

        expected_scalars = sum(
            len(self.compressed_indices[f]) * COMPRESSED_WIDTH[f]
            for f in range(9)
        )
        if expected_scalars != self.anim.compressed_track_count:
            raise DecodeError(
                "mask/ASKL scalar count mismatch: "
                f"computed {expected_scalars}, ANIM +0x38 says {self.anim.compressed_track_count}"
            )

        self.error_correction_ids = self._read_special_sparse_ids(0x08, 0x0C)
        self.bone_scale_ids = self._read_special_sparse_ids(0x30, 0x34)

    def _find_special_key0_node(self) -> Optional[int]:
        local = self.anim.resolve_local_pointer(self.anim.special_data_ptr_token)
        seen = set()
        while local is not None:
            if local in seen:
                raise DecodeError("ANIM special-data linked list contains a cycle")
            seen.add(local)
            key = _u32(self.anim_data, local + 0x00)
            if key == 0:
                return local
            next_token = _u32(self.anim_data, local + 0x04)
            local = self.anim.resolve_local_pointer(next_token) if next_token else None
        return None

    def _read_special_sparse_ids(self, count_off: int, ptr_off: int) -> Tuple[int, ...]:
        node = self._find_special_key0_node()
        if node is None:
            return ()
        count = _u32(self.anim_data, node + count_off)
        token = _u32(self.anim_data, node + ptr_off)
        if count == 0 or token == 0:
            return ()
        local = self.anim.resolve_local_pointer(token)
        if local is None or local + count * 4 > len(self.anim_data):
            raise DecodeError("ANIM sparse-ID table exceeds file")
        return struct.unpack_from("<" + "I" * count, self.anim_data, local)

    def _bone_for_field_element(self, field: int, element: int, sparse_id: Optional[int] = None) -> Optional[int]:
        if field == 0 and element < len(self.askl.position_bone_map):
            return self.askl.position_bone_map[element]
        if field == 1 and element < len(self.askl.quaternion_bone_map):
            return self.askl.quaternion_bone_map[element]
        if field == 2 and element < len(self.askl.axis1_bone_map):
            return self.askl.axis1_bone_map[element]
        # SkeletonPose_BuildBoneMatrices uses FK_ERROR_CORRECTION DWORD +0x0C
        # directly as boneIndex * 0x40. FUN_006B89F0 does the same for BONE_SCALE,
        # resolving entry[3] through boneIndex * 0x40 + boneRecord.name.
        if field in (3, 8) and sparse_id is not None:
            return sparse_id
        return None

    def _bone_meta(self, bone_index: Optional[int]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        if bone_index is None or bone_index < 0 or bone_index >= len(self.askl.bone_records):
            return None, None, None
        b = self.askl.bone_records[bone_index]
        return b.name_hash, b.name_ptr_token, self.bone_names.get(bone_index)

    def _pose_element_offset(self, field: int, element: int) -> int:
        return self.askl.field_data_offsets[field] + STORAGE_WIDTH[field] * element * 4

    def _apply_post_scales(self, pose_data: bytearray) -> None:
        if self.anim.post_scale_count == 0:
            return
        table_local = self.anim.resolve_local_pointer(self.anim.post_scale_ptr_token)
        if table_local is None:
            raise DecodeError("ANIM has nonzero postScaleCount but NULL postScalePtr")
        for i in range(self.anim.post_scale_count):
            off = table_local + i * 8
            multiplier = _f32(self.anim_data, off)
            pose_offset = _u32(self.anim_data, off + 4)
            value = _f32(pose_data, pose_offset)
            _set_f32(pose_data, pose_offset, value * multiplier)

    def decode_frame(self, frame: int) -> DecodeResult:
        track_decoder = CompressedTrackDecoder(self.anim_data, self.anim)
        scalars = track_decoder.get_frame_values(frame)

        # A real SkeletonPose only needs valid elements. Start zeroed, then copy reference or decoded values.
        pose_data = bytearray(self.askl.pose_data_size)
        ref_pose = self.askl_data[
            self.askl.pose_data_local:self.askl.pose_data_local + self.askl.pose_data_size
        ]

        elements: List[FieldElementResult] = []
        scalar_cursor = 0

        for field in range(9):
            width_storage = STORAGE_WIDTH[field]
            width_compressed = COMPRESSED_WIDTH[field]

            # Reference-mask elements copy canonical stored data from ASKL reference pose.
            for element in self.reference_indices[field]:
                off = self._pose_element_offset(field, element)
                size = width_storage * 4
                pose_data[off:off + size] = ref_pose[off:off + size]
                sparse_id: Optional[int] = None
                if field in (3, 8):
                    sparse_id = _u32(pose_data, off + 0x0C)
                    values: List[Optional[float]] = [
                        float(_f32(pose_data, off + i * 4)) for i in range(3)
                    ] + [None]
                else:
                    values = [
                        float(v) for v in struct.unpack_from("<" + "f" * width_storage, pose_data, off)
                    ]
                bone_index = self._bone_for_field_element(field, element, sparse_id)
                bone_hash, bone_name_token, bone_name = self._bone_meta(bone_index)
                elements.append(FieldElementResult(
                    field, FIELD_NAMES[field], element, "ASKL_REFERENCE", None, [],
                    values, "copied from ASKL reference pose",
                    bone_index=bone_index, bone_hash=bone_hash, bone_name_token=bone_name_token,
                    bone_name=bone_name, sparse_id=sparse_id,
                ))

            # Presence-only elements consume compressed scalar tracks.
            for element in self.compressed_indices[field]:
                scale_array = self.askl.scales[field]
                if scale_array is None:
                    raise DecodeError(
                        f"field {field} {FIELD_NAMES[field]} has compressed elements but NULL ASKL scale array"
                    )
                scale = float(scale_array[element])
                raw = scalars[scalar_cursor:scalar_cursor + width_compressed]
                if len(raw) != width_compressed:
                    raise DecodeError("ran out of scalar values while reconstructing pose")
                scalar_cursor += width_compressed
                out = [float(v) * scale for v in raw]
                note = ""

                # Write only compressed semantic components first.
                off = self._pose_element_offset(field, element)
                for c, value in enumerate(out):
                    _set_f32(pose_data, off + c * 4, value)

                # Channel-specific postprocess recovered from game code.
                if field == 0:  # FK_POSITION ClearW
                    _set_f32(pose_data, off + 12, 0.0)
                elif field == 1:  # Quaternion normalize
                    q = [_f32(pose_data, off + i * 4) for i in range(4)]
                    norm = math.sqrt(sum(v * v for v in q))
                    if norm > 0.0:
                        q = [v / norm for v in q]
                        for i, v in enumerate(q):
                            _set_f32(pose_data, off + i * 4, v)
                    else:
                        note = "zero quaternion encountered; game normalize behavior needs edge-case check"
                sparse_id: Optional[int] = None
                if field == 3:
                    ordinal = self.compressed_indices[field].index(element)
                    if ordinal < len(self.error_correction_ids):
                        sparse_id = self.error_correction_ids[ordinal]
                        _set_u32(pose_data, off + 0x0C, sparse_id)
                        note = "FK_ERROR_CORRECTION sparse ID restored from ANIM special-data key-0 node"
                    else:
                        note = "FK_ERROR_CORRECTION sparse ID table missing/short"
                elif field == 8:
                    ordinal = self.compressed_indices[field].index(element)
                    if ordinal < len(self.bone_scale_ids):
                        sparse_id = self.bone_scale_ids[ordinal]
                        _set_u32(pose_data, off + 0x0C, sparse_id)
                        note = "BONE_SCALE bone index restored from ANIM special-data key-0 node; consumer FUN_006B89F0 confirmed DWORD +0x0C as bone index"
                    else:
                        note = "BONE_SCALE sparse ID table missing/short"

                if field in (3, 8):
                    vals: List[Optional[float]] = [
                        float(_f32(pose_data, off + i * 4)) for i in range(3)
                    ] + [None]
                else:
                    vals = [float(_f32(pose_data, off + i * 4)) for i in range(width_storage)]
                bone_index = self._bone_for_field_element(field, element, sparse_id)
                bone_hash, bone_name_token, bone_name = self._bone_meta(bone_index)
                elements.append(FieldElementResult(
                    field, FIELD_NAMES[field], element, "COMPRESSED", scale, list(raw), vals, note,
                    bone_index=bone_index, bone_hash=bone_hash, bone_name_token=bone_name_token,
                    bone_name=bone_name, sparse_id=sparse_id,
                ))

        if scalar_cursor != self.anim.compressed_track_count:
            raise DecodeError(
                f"pose reconstruction consumed {scalar_cursor} scalars, expected {self.anim.compressed_track_count}"
            )

        self._apply_post_scales(pose_data)

        cursor_byte, cursor_bit = track_decoder.cursor
        golden: Dict[str, Any] = {}
        if self.anim.resource_hash == 0xACBAB3E0 and frame == 28:
            golden = {
                "fixture": "0xACBAB3E0 pedmidla frame 28",
                "expected_cursor_byte": "0xA0C",
                "expected_cursor_bit": 7,
                "cursor_match": cursor_byte == 0xA0C and cursor_bit == 7,
                "expected_scalar_count": 185,
                "scalar_count_match": self.anim.compressed_track_count == 185 and scalar_cursor == 185,
                "pass": (
                    cursor_byte == 0xA0C and cursor_bit == 7 and
                    self.anim.compressed_track_count == 185 and scalar_cursor == 185
                ),
            }

        return DecodeResult(
            anim_hash=self.anim.resource_hash,
            askl_hash=self.anim.askl_hash,
            frame=frame,
            sample_count=self.anim.sample_count,
            compressed_track_count=self.anim.compressed_track_count,
            consumed_scalar_count=scalar_cursor,
            cursor_byte_offset=cursor_byte,
            cursor_bit_offset=cursor_bit,
            reference_counts=[len(x) for x in self.reference_indices],
            compressed_counts=[len(x) for x in self.compressed_indices],
            field_elements=elements,
            raw_scalars=scalars,
            golden_checks=golden,
        )


    def _build_bone_rows_for_frame(self, result: DecodeResult) -> List[BoneFrameRow]:
        """Flatten one decoded SkeletonPose into one named row per ASKL bone.

        This mirrors the recovered SkeletonPose_BuildBoneMatrices rotation order:
          1) Axis1 builds qAxis from bone-record +0x00 and the pose scalar, then
             final local quaternion = ASKL bind quaternion * qAxis.
          2) A valid FK_QUATERNION channel is processed later and therefore wins
             if a skeleton ever maps both rotation channel types to the same bone.

        POSITION/QUATERNION otherwise fall back to ASKL bind/default records.
        """
        rows: Dict[int, BoneFrameRow] = {}
        t = float(result.frame) * float(self.anim.sample_interval_seconds)
        for bone in self.askl.bone_records:
            name = self.bone_names.get(bone.index) or f"bone_{bone.index}"
            rows[bone.index] = BoneFrameRow(
                frame=result.frame,
                time_seconds=t,
                bone_index=bone.index,
                bone_name=name,
                parent_bone_index=bone.parent_index,
                bone_hash=bone.name_hash,
                bone_name_token=bone.name_ptr_token,
                position_x=float(bone.bind_position[0]),
                position_y=float(bone.bind_position[1]),
                position_z=float(bone.bind_position[2]),
                position_source="ASKL_BIND_DEFAULT",
                quaternion_x=float(bone.bind_quaternion[0]),
                quaternion_y=float(bone.bind_quaternion[1]),
                quaternion_z=float(bone.bind_quaternion[2]),
                quaternion_w=float(bone.bind_quaternion[3]),
                quaternion_source="ASKL_BIND_DEFAULT",
            )

        # BuildBoneMatrices does not process the generic fields in numeric order.
        # Reproduce the relevant consumer order so FK_QUATERNION can overwrite
        # Axis1 on any unusual skeleton that maps both to the same bone.
        ordered_fields = (0, 2, 1, 3, 8)
        for wanted_field in ordered_fields:
            for e in result.field_elements:
                if e.field_index != wanted_field:
                    continue
                bi = e.bone_index
                if bi is None or bi not in rows:
                    continue
                row = rows[bi]
                source = f"{e.field_name}:{e.source}"

                if e.field_index == 0 and len(e.values) >= 3:
                    row.position_x = float(e.values[0] or 0.0)
                    row.position_y = float(e.values[1] or 0.0)
                    row.position_z = float(e.values[2] or 0.0)
                    row.position_source = source

                elif e.field_index == 2 and e.values:
                    angle = None if e.values[0] is None else float(e.values[0])
                    row.axis1 = angle
                    row.axis1_source = source
                    if angle is not None and 0 <= bi < len(self.askl.bone_records):
                        bone = self.askl.bone_records[bi]
                        axis = bone.axis1_vector
                        q_axis = _axis1_quaternion_game(axis, angle)
                        q_final = _quat_mul_xyzw(bone.bind_quaternion, q_axis)
                        row.axis1_axis_x = float(axis[0])
                        row.axis1_axis_y = float(axis[1])
                        row.axis1_axis_z = float(axis[2])
                        row.axis1_quaternion_x = float(q_axis[0])
                        row.axis1_quaternion_y = float(q_axis[1])
                        row.axis1_quaternion_z = float(q_axis[2])
                        row.axis1_quaternion_w = float(q_axis[3])
                        row.quaternion_x = float(q_final[0])
                        row.quaternion_y = float(q_final[1])
                        row.quaternion_z = float(q_final[2])
                        row.quaternion_w = float(q_final[3])
                        row.quaternion_source = "FK_AXIS1_ROTATION:GAME_COMBINED_WITH_ASKL_BIND"
                        row.rotation_note = (
                            "Axis1 final local quaternion reproduced from FUN_008BCBA0 + "
                            "SkeletonPose_BuildBoneMatrices: ASKL bind quaternion * Axis1 quaternion."
                        )

                elif e.field_index == 1 and len(e.values) >= 4:
                    had_axis1 = row.axis1 is not None
                    row.quaternion_x = float(e.values[0] or 0.0)
                    row.quaternion_y = float(e.values[1] or 0.0)
                    row.quaternion_z = float(e.values[2] or 0.0)
                    row.quaternion_w = float(e.values[3] or 0.0)
                    row.quaternion_source = source
                    if had_axis1:
                        row.rotation_note = (
                            "FK_QUATERNION overrides the earlier Axis1 matrix for this bone, "
                            "matching SkeletonPose_BuildBoneMatrices consumer order."
                        )

                elif e.field_index == 3 and len(e.values) >= 3:
                    row.error_correction_x = None if e.values[0] is None else float(e.values[0])
                    row.error_correction_y = None if e.values[1] is None else float(e.values[1])
                    row.error_correction_z = None if e.values[2] is None else float(e.values[2])
                    row.error_correction_source = source

                elif e.field_index == 8 and len(e.values) >= 3:
                    row.bone_scale_x = None if e.values[0] is None else float(e.values[0])
                    row.bone_scale_y = None if e.values[1] is None else float(e.values[1])
                    row.bone_scale_z = None if e.values[2] is None else float(e.values[2])
                    row.bone_scale_source = source

        return [rows[i] for i in sorted(rows)]

    @staticmethod
    def _apply_blender_quaternion_continuity(bone_rows: List[BoneFrameRow]) -> Tuple[int, int]:
        """Populate Blender-safe quaternion columns while preserving raw SM3 quaternions.

        q and -q are the same orientation, but interpolation packages can take the
        long arc if successive keys change sign. For each bone independently we
        normalize a copy of the decoded local quaternion and flip it only when its
        dot product with the previous Blender-facing key is negative.

        Returns (sign_adjusted_key_count, raw_negative_transition_count).
        """
        previous_safe_by_bone: Dict[int, Tuple[float, float, float, float]] = {}
        previous_raw_by_bone: Dict[int, Tuple[float, float, float, float]] = {}
        sign_adjusted_keys = 0
        raw_negative_transitions = 0
        for row in sorted(bone_rows, key=lambda r: (r.frame, r.bone_index)):
            raw = _quat_normalize_xyzw((
                float(row.quaternion_x),
                float(row.quaternion_y),
                float(row.quaternion_z),
                float(row.quaternion_w),
            ))

            prev_raw = previous_raw_by_bone.get(row.bone_index)
            raw_dot: Optional[float] = None
            if prev_raw is not None:
                raw_dot = _quat_dot_xyzw(prev_raw, raw)
                if raw_dot < 0.0:
                    raw_negative_transitions += 1

            safe = raw
            prev_safe = previous_safe_by_bone.get(row.bone_index)
            safe_dot: Optional[float] = None
            flipped = False
            if prev_safe is not None:
                safe_dot = _quat_dot_xyzw(prev_safe, safe)
                if safe_dot < 0.0:
                    safe = tuple(-v for v in safe)  # type: ignore[assignment]
                    flipped = True
                    sign_adjusted_keys += 1
                    safe_dot = -safe_dot

            row.blender_quaternion_x = float(safe[0])
            row.blender_quaternion_y = float(safe[1])
            row.blender_quaternion_z = float(safe[2])
            row.blender_quaternion_w = float(safe[3])
            row.blender_quaternion_flipped = flipped
            row.blender_quaternion_raw_dot_previous = raw_dot
            row.blender_quaternion_dot_previous = safe_dot
            row.blender_quaternion_source = (
                "RAW_GAME_NORMALIZED_SIGN_FLIPPED_FOR_CONTINUITY"
                if flipped else "RAW_GAME_NORMALIZED"
            )
            previous_raw_by_bone[row.bone_index] = raw
            previous_safe_by_bone[row.bone_index] = safe
        return sign_adjusted_keys, raw_negative_transitions

    def decode_all_frames(self) -> AnimationDecodeResult:
        frame_cursors: List[Dict[str, Any]] = []
        bone_rows: List[BoneFrameRow] = []
        for frame in range(self.anim.sample_count):
            result = self.decode_frame(frame)
            if result.consumed_scalar_count != result.compressed_track_count:
                raise DecodeError(
                    f"frame {frame} consumed {result.consumed_scalar_count} scalars, "
                    f"expected {result.compressed_track_count}"
                )
            frame_cursors.append({
                "frame": frame,
                "time_seconds": float(frame) * float(self.anim.sample_interval_seconds),
                "cursor_byte_offset": f"0x{result.cursor_byte_offset:X}",
                "cursor_bit_offset": result.cursor_bit_offset,
                "consumed_scalar_count": result.consumed_scalar_count,
                "golden_pass": result.golden_checks.get("pass") if result.golden_checks else None,
            })
            bone_rows.extend(self._build_bone_rows_for_frame(result))

        continuity_flips, raw_negative_transitions = self._apply_blender_quaternion_continuity(bone_rows)

        notes = [
            "One row is emitted for every ASKL bone at every animation sample.",
            "Missing FK_POSITION/FK_QUATERNION channels fall back to ASKL bind/default values, matching SkeletonPose_BuildBoneMatrices fallback behavior.",
            "FK_ERROR_CORRECTION sparse ID is confirmed as bone index.",
            "BONE_SCALE sparse ID is confirmed as bone index by FUN_006B89F0; XYZ is exported on that bone.",
            "AXIS1 final local quaternion is now reconstructed with the recovered FUN_008BCBA0 path: bone-record axis + game half-angle trig approximation, then ASKL bind quaternion * Axis1 quaternion.",
            f"Blender quaternion continuity copy generated without modifying raw SM3 quaternions; {raw_negative_transitions} raw hemisphere transitions were detected and {continuity_flips} timeline keys were sign-adjusted to keep each bone on one continuous quaternion hemisphere.",
            "Blender-facing quaternions are normalized XYZW copies. Coordinate-system conversion is intentionally NOT applied yet; positions/rotations remain SM3 local-space values.",
            "FK_TRAJECTORY is synthesized later by the game evaluator and is not invented by this exporter.",
        ]
        return AnimationDecodeResult(
            anim_hash=self.anim.resource_hash,
            askl_hash=self.anim.askl_hash,
            sample_count=self.anim.sample_count,
            sample_interval_seconds=float(self.anim.sample_interval_seconds),
            duration_seconds=float(self.anim.duration_seconds),
            compressed_track_count=self.anim.compressed_track_count,
            bone_count=self.askl.bone_count,
            resolved_bone_names=len(self.bone_names),
            frame_cursors=frame_cursors,
            bone_rows=bone_rows,
            notes=notes,
        )


def decode_files(
    anim_path: str | os.PathLike[str],
    askl_path: str | os.PathLike[str],
    frame: int,
    parent_apkf_path: str | os.PathLike[str] | None = None,
) -> DecodeResult:
    anim_data = Path(anim_path).read_bytes()
    askl_data = Path(askl_path).read_bytes()
    parent_data = Path(parent_apkf_path).read_bytes() if parent_apkf_path else None
    return SM3AnimPoseDecoder(anim_data, askl_data, parent_data).decode_frame(frame)


def export_result_json(result: DecodeResult, path: str | os.PathLike[str]) -> None:
    Path(path).write_text(json.dumps(result.to_jsonable(), indent=2), encoding="utf-8")


def export_result_csv(result: DecodeResult, path: str | os.PathLike[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "field_index", "field_name", "element_index", "source", "scale",
            "bone_index", "bone_hash", "bone_name_token", "bone_name", "sparse_id",
            "raw_integers", "values", "note"
        ])
        for e in result.field_elements:
            w.writerow([
                e.field_index, e.field_name, e.element_index, e.source,
                "" if e.scale is None else repr(e.scale),
                "" if e.bone_index is None else e.bone_index,
                "" if e.bone_hash is None else f"0x{e.bone_hash:08X}",
                "" if e.bone_name_token is None else f"0x{e.bone_name_token:08X}",
                e.bone_name or "",
                "" if e.sparse_id is None else e.sparse_id,
                " ".join(str(v) for v in e.raw_integers),
                " ".join("" if v is None else repr(v) for v in e.values),
                e.note,
            ])


def format_summary(decoder: SM3AnimPoseDecoder, result: DecodeResult) -> str:
    a = decoder.anim
    s = decoder.askl
    lines = [
        "SM3 NAS ANIM DECODER — DEV",
        "=" * 72,
        f"ANIM hash        : 0x{a.resource_hash:08X}",
        f"ASKL hash        : 0x{a.askl_hash:08X}",
        f"ANIM version     : 0x{a.version:08X}",
        f"Frame            : {result.frame} / {a.sample_count - 1}",
        f"Duration         : {a.duration_seconds:.9f} sec",
        f"Sample interval  : {a.sample_interval_seconds:.9f} sec",
        f"Compressed tracks: {a.compressed_track_count}",
        f"Bit cursor       : local 0x{result.cursor_byte_offset:X}, bit {result.cursor_bit_offset}",
        f"PoseData size    : 0x{s.pose_data_size:X}",
        f"Validity bits    : {s.total_validity_bits}",
        f"Bone-map node    : {('NONE' if s.bone_node_local is None else f'local 0x{s.bone_node_local:X}')}",
        f"Bone count       : {s.bone_count}",
        f"Bone names       : {len(decoder.bone_names)} resolved from parent APKF" if decoder.parent_apkf_data else "Bone names       : parent APKF not auto-resolved",
        "",
        "FIELD COUNTS",
    ]
    for i, name in enumerate(FIELD_NAMES):
        lines.append(
            f"  {i} {name:<22} total={s.field_counts[i]:>3}  "
            f"ref={result.reference_counts[i]:>3}  compressed={result.compressed_counts[i]:>3}  "
            f"semanticWidth={COMPRESSED_WIDTH[i]}"
        )
    lines += [
        "",
        f"Consumed scalars : {result.consumed_scalar_count}",
    ]
    if result.golden_checks:
        lines.append(
            "Golden frame 28  : " + ("PASS" if result.golden_checks.get("pass") else "FAIL")
        )
    lines += ["", "DECODED VALID ELEMENTS"]
    for e in result.field_elements:
        vals = ", ".join(f"{v:.9g}" for v in e.values if v is not None)
        if e.bone_index is None:
            bone_text = ""
        elif e.bone_name:
            bone_text = f"  bone={e.bone_index}:{e.bone_name}"
        elif e.bone_hash is not None:
            bone_text = f"  bone={e.bone_index}:0x{e.bone_hash:08X}"
        else:
            bone_text = f"  bone={e.bone_index}"
        sparse_text = "" if e.sparse_id is None else f"  sparseID={e.sparse_id}"
        lines.append(
            f"  {e.field_name}[{e.element_index}] {e.source:<14} "
            f"scale={'' if e.scale is None else f'{e.scale:.9g}'}  values=({vals})"
            + bone_text + sparse_text
            + (f"  [{e.note}]" if e.note else "")
        )
    return "\n".join(lines)





def export_animation_json(result: AnimationDecodeResult, path: str | os.PathLike[str]) -> None:
    Path(path).write_text(json.dumps(result.to_jsonable(), indent=2), encoding="utf-8")


def export_animation_csv(result: AnimationDecodeResult, path: str | os.PathLike[str]) -> None:
    fields = [
        "frame", "time_seconds", "bone_index", "bone_name", "parent_bone_index",
        "bone_hash", "bone_name_token",
        "position_x", "position_y", "position_z", "position_source",
        "quaternion_x", "quaternion_y", "quaternion_z", "quaternion_w", "quaternion_source",
        "blender_quaternion_x", "blender_quaternion_y", "blender_quaternion_z", "blender_quaternion_w",
        "blender_quaternion_flipped", "blender_quaternion_raw_dot_previous",
        "blender_quaternion_dot_previous", "blender_quaternion_source",
        "axis1", "axis1_source",
        "axis1_axis_x", "axis1_axis_y", "axis1_axis_z",
        "axis1_quaternion_x", "axis1_quaternion_y", "axis1_quaternion_z", "axis1_quaternion_w",
        "error_correction_x", "error_correction_y", "error_correction_z", "error_correction_source",
        "bone_scale_x", "bone_scale_y", "bone_scale_z", "bone_scale_source",
        "rotation_note",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in result.bone_rows:
            d = asdict(row)
            d["bone_hash"] = f"0x{row.bone_hash:08X}"
            d["bone_name_token"] = f"0x{row.bone_name_token:08X}"
            w.writerow(d)


def build_blender_animation_payload(result: AnimationDecodeResult) -> Dict[str, Any]:
    """Build a compact importer-facing JSON document using continuity-safe rotations.

    This is intentionally an SM3-local bridge format, not a claim that SM3 and
    Blender coordinate systems are already identical.  The future Blender addon
    can perform the final axis/handedness conversion in one controlled place.
    """
    rows_by_bone: Dict[int, List[BoneFrameRow]] = {}
    for row in result.bone_rows:
        rows_by_bone.setdefault(row.bone_index, []).append(row)

    bones: List[Dict[str, Any]] = []
    for bone_index in sorted(rows_by_bone):
        rows = sorted(rows_by_bone[bone_index], key=lambda r: r.frame)
        first = rows[0]
        frames: List[Dict[str, Any]] = []
        for row in rows:
            frame_data: Dict[str, Any] = {
                "frame": row.frame,
                "time_seconds": row.time_seconds,
                "location_sm3_local": [row.position_x, row.position_y, row.position_z],
                "rotation_quaternion_xyzw": [
                    row.blender_quaternion_x, row.blender_quaternion_y,
                    row.blender_quaternion_z, row.blender_quaternion_w,
                ],
                "raw_sm3_quaternion_xyzw": [
                    row.quaternion_x, row.quaternion_y, row.quaternion_z, row.quaternion_w,
                ],
                "continuity_sign_flipped": row.blender_quaternion_flipped,
                "raw_dot_previous": row.blender_quaternion_raw_dot_previous,
                "continuity_dot_previous": row.blender_quaternion_dot_previous,
                "position_source": row.position_source,
                "rotation_source": row.quaternion_source,
            }
            if row.axis1 is not None:
                frame_data["sm3_axis1"] = row.axis1
            if row.error_correction_x is not None:
                frame_data["sm3_error_correction_xyz"] = [
                    row.error_correction_x, row.error_correction_y, row.error_correction_z
                ]
            if row.bone_scale_x is not None:
                frame_data["sm3_bone_scale_xyz"] = [
                    row.bone_scale_x, row.bone_scale_y, row.bone_scale_z
                ]
            frames.append(frame_data)
        bones.append({
            "bone_index": first.bone_index,
            "bone_name": first.bone_name,
            "parent_bone_index": first.parent_bone_index,
            "bone_hash": f"0x{first.bone_hash:08X}",
            "bone_name_token": f"0x{first.bone_name_token:08X}",
            "frames": frames,
        })

    interval = float(result.sample_interval_seconds)
    fps = (1.0 / interval) if interval > 0.0 else 0.0
    flip_count = sum(1 for row in result.bone_rows if row.blender_quaternion_flipped)
    raw_transition_count = sum(
        1 for row in result.bone_rows
        if row.blender_quaternion_raw_dot_previous is not None
        and row.blender_quaternion_raw_dot_previous < 0.0
    )
    return {
        "format": "SM3_NAS_BLENDER_ANIM_V1",
        "toolkit_version": "v5.2.133 QUICK MOTION + NAMED PROFILE + APKF REBUILDER DEV",
        "coordinate_space": "SM3_LOCAL_UNCONVERTED",
        "quaternion_storage": "XYZW",
        "quaternion_policy": "normalized copy + per-bone hemisphere continuity; raw SM3 quaternion preserved",
        "anim_hash": f"0x{result.anim_hash:08X}",
        "askl_hash": f"0x{result.askl_hash:08X}",
        "frame_start": 0,
        "frame_end": max(0, result.sample_count - 1),
        "sample_count": result.sample_count,
        "sample_interval_seconds": interval,
        "fps": fps,
        "duration_seconds": result.duration_seconds,
        "bone_count": result.bone_count,
        "resolved_bone_names": result.resolved_bone_names,
        "raw_negative_quaternion_transition_count": raw_transition_count,
        "continuity_sign_adjusted_key_count": flip_count,
        "trajectory_status": "NOT_EXPORTED_GAME_SYNTHESIZED",
        "bones": bones,
        "notes": [
            "Use rotation_quaternion_xyzw for interpolation/import.",
            "raw_sm3_quaternion_xyzw is preserved for verification.",
            "Coordinate-system conversion is intentionally deferred to the Blender importer.",
            "sm3_error_correction_xyz and sm3_bone_scale_xyz are preserved metadata and are not automatically mapped to Blender transforms yet.",
        ],
    }


def export_blender_animation_json(result: AnimationDecodeResult, path: str | os.PathLike[str]) -> None:
    Path(path).write_text(
        json.dumps(build_blender_animation_payload(result), indent=2),
        encoding="utf-8",
    )


def format_animation_summary(decoder: SM3AnimPoseDecoder, result: AnimationDecodeResult) -> str:
    channel_counts = {
        "position": 0,
        "quaternion": 0,
        "axis1": 0,
        "error_correction": 0,
        "bone_scale": 0,
    }
    for row in result.bone_rows:
        if row.position_source != "ASKL_BIND_DEFAULT":
            channel_counts["position"] += 1
        if row.quaternion_source.startswith("FK_QUATERNION:"):
            channel_counts["quaternion"] += 1
        if row.axis1 is not None:
            channel_counts["axis1"] += 1
        if row.error_correction_x is not None:
            channel_counts["error_correction"] += 1
        if row.bone_scale_x is not None:
            channel_counts["bone_scale"] += 1

    continuity_adjusted = sum(1 for row in result.bone_rows if row.blender_quaternion_flipped)
    raw_negative_transitions = sum(
        1 for row in result.bone_rows
        if row.blender_quaternion_raw_dot_previous is not None
        and row.blender_quaternion_raw_dot_previous < 0.0
    )

    lines = [
        "SM3 NAS ANIM DECODER — ALL FRAMES / BLENDER BRIDGE",
        "=" * 72,
        f"ANIM hash        : 0x{result.anim_hash:08X}",
        f"ASKL hash        : 0x{result.askl_hash:08X}",
        f"Samples          : {result.sample_count}",
        f"Sample interval  : {result.sample_interval_seconds:.9f} sec",
        f"Duration         : {result.duration_seconds:.9f} sec",
        f"Bones            : {result.bone_count}",
        f"Named bones      : {result.resolved_bone_names}",
        f"Timeline rows    : {len(result.bone_rows)}",
        f"Compressed tracks: {result.compressed_track_count}",
        f"Raw quat sign transitions: {raw_negative_transitions}",
        f"Blender sign-adjusted keys: {continuity_adjusted}",
        "",
        "ANIMATED CHANNEL SAMPLES ACROSS TIMELINE",
        f"  FK_POSITION        : {channel_counts['position']}",
        f"  FK_QUATERNION      : {channel_counts['quaternion']}",
        f"  FK_AXIS1_ROTATION  : {channel_counts['axis1']}",
        f"  FK_ERROR_CORRECTION: {channel_counts['error_correction']}",
        f"  BONE_SCALE         : {channel_counts['bone_scale']}",
        "",
        "FRAME CURSORS",
    ]
    if result.frame_cursors:
        picks = sorted(set([0, result.sample_count // 2, result.sample_count - 1]))
        for i in picks:
            c = result.frame_cursors[i]
            lines.append(
                f"  frame {i:>4}: t={c['time_seconds']:.6f}s  "
                f"cursor={c['cursor_byte_offset']} bit {c['cursor_bit_offset']}"
            )
    lines += ["", "NOTES"]
    for note in result.notes:
        lines.append(f"  - {note}")
    return "\n".join(lines)


def find_parent_apkf_for_anim(anim_path: str | os.PathLike[str]) -> Optional[Path]:
    """Best-effort lookup of the raw parent APKF from current extractor output.

    Uses 06_MOD_LOADER_READY/ownership_manifest.json when the ANIM came from the
    canonical 02_APKF_EXTRACTED_REAL_EXT/ANIM folder. This is optional; decoding
    does not depend on it. It only lets the NAS display real bone names from
    serialized component-63 string tokens.
    """
    anim_path = Path(anim_path)
    if not anim_path.is_file():
        return None
    try:
        header = inspect_anim_header(anim_path)
    except Exception:
        return None

    extracted_root: Optional[Path] = None
    for parent in anim_path.parents:
        if (parent / "01_OUTER_PAYLOADS").is_dir():
            extracted_root = parent
            break
    if extracted_root is None:
        return None

    outer_index: Optional[int] = None
    for parent in anim_path.parents:
        m = re.match(r"_O(\d+)\.", parent.name, flags=re.IGNORECASE)
        if m:
            outer_index = int(m.group(1))
            break

    if outer_index is None:
        manifest = extracted_root / "06_MOD_LOADER_READY" / "ownership_manifest.json"
        if manifest.is_file():
            try:
                obj = json.loads(manifest.read_text(encoding="utf-8"))
                needle = f"0x{header.resource_hash:08X}".lower()
                for row in obj.get("resources", []):
                    if str(row.get("resource_hash", "")).lower() == needle and str(row.get("resource_type", "")).upper() == "ANIM":
                        outer_index = int(row.get("parent_outer_index"))
                        break
            except Exception:
                outer_index = None

    if outer_index is None:
        return None
    raw_dir = extracted_root / "01_OUTER_PAYLOADS" / "APKF_ARCHIVE"
    if not raw_dir.is_dir():
        return None
    candidates = sorted(raw_dir.glob(f"outer_{outer_index:04d}_*.apkf"))
    return candidates[0] if candidates else None


def inspect_anim_header(anim_path: str | os.PathLike[str]) -> AnimHeader:
    """Read only the serialized SM3 ANIM header from an extracted .anim file."""
    return AnimHeader.parse(read_anim_payload(anim_path))


def _nearest_sm3_extract_pack_root(path: Path) -> Optional[Path]:
    """Locate the nearest extracted-pack root containing 02_APKF_EXTRACTED_REAL_EXT."""
    path = Path(path)
    for parent in [path.parent, *path.parents]:
        if parent.name.upper() == "02_APKF_EXTRACTED_REAL_EXT":
            return parent.parent
        if (parent / "02_APKF_EXTRACTED_REAL_EXT").is_dir():
            return parent
    return None


def _expected_hash_token(expected_hash: int) -> str:
    return f"0x{int(expected_hash) & 0xFFFFFFFF:08X}".lower()


def _looks_like_sm3_t4_hsam_source(path: Path, expected_hash: int) -> bool:
    """Return True for an exact-hash outer T4 HSAM skeleton source.

    v5.2.129 intentionally does not reject a candidate because of a folder name.
    Detection is content/hash based so mixed SM3/WOS extraction trees cannot be
    misclassified just from provenance text.
    """
    path = Path(path)
    name = path.name.lower()
    token = _expected_hash_token(expected_hash)
    if not path.is_file() or path.suffix.lower() != ".hsam":
        return False
    if token not in name:
        return False
    if "_t4_" not in name and ".t4." not in name:
        return False
    try:
        raw = path.read_bytes()
    except Exception:
        return False
    if len(raw) < 0x80 or raw[:4] != b"hsam":
        return False
    needle = struct.pack("<I", int(expected_hash) & 0xFFFFFFFF)
    return needle in raw[:0x400]


def _validate_matching_askl_bytes(anim_path: Path, askl_path: Path) -> AsklInputInfo:
    """Validate ASKL by parsed contents, never by WOS/SM3 path labels.

    Both raw ``*.askl`` and supported ``*.wrap.askl`` containers are allowed.
    The normalized ASKL resource hash must exactly match the ANIM +0x10 hash,
    and the full skeleton layout must parse successfully.
    """
    if not anim_path.is_file():
        raise FileNotFoundError(f"ANIM not found: {anim_path}")
    if not askl_path.is_file():
        raise DecodeError(f"ASKL not found: {askl_path}")
    header = inspect_anim_header(anim_path)
    raw = askl_path.read_bytes()
    info = _normalize_askl_input(raw)
    layout = AsklLayout.parse(
        info.data,
        pointer_mode=info.pointer_mode,
        resource_hash_override=info.resource_hash_override,
    )
    if layout.resource_hash != header.askl_hash:
        raise DecodeError(
            f"ASKL hash mismatch: ANIM requires 0x{header.askl_hash:08X}, "
            f"selected resource parses as 0x{layout.resource_hash:08X}."
        )
    if len(layout.field_counts) != 9:
        raise DecodeError("Selected ASKL does not contain the expected 9 pose fields.")
    return info


def classify_sm3_skeleton_source(
    anim_path: str | os.PathLike[str],
    source_path: str | os.PathLike[str],
) -> str:
    """Classify a verified skeleton source using file contents.

    Returns ``RAW_ASKL``, ``WRAP_ASKL`` or ``SM3_T4_HSAM``.  v5.2.129 removes
    the former WOS/path-name lock: a WRAP ASKL is accepted when its parsed
    skeleton hash and layout match the selected ANIM.
    """
    anim_path = Path(anim_path)
    source_path = Path(source_path)
    header = inspect_anim_header(anim_path)
    if source_path.suffix.lower() == ".hsam":
        if _looks_like_sm3_t4_hsam_source(source_path, header.askl_hash):
            return "SM3_T4_HSAM"
        raise DecodeError(
            f"HSAM does not prove the required skeleton hash 0x{header.askl_hash:08X}: {source_path.name}"
        )
    if source_path.suffix.lower() == ".askl":
        info = _validate_matching_askl_bytes(anim_path, source_path)
        return info.container
    raise DecodeError("Unsupported skeleton source. Select .askl/.wrap.askl or outer T4 .hsam.")


def validate_matching_sm3_skeleton_source_path(
    anim_path: str | os.PathLike[str],
    source_path: str | os.PathLike[str],
) -> Path:
    """Validate a skeleton source against the selected ANIM by content/hash."""
    source_path = Path(source_path)
    _ = classify_sm3_skeleton_source(anim_path, source_path)
    return source_path


def validate_matching_sm3_askl_path(
    anim_path: str | os.PathLike[str],
    askl_path: str | os.PathLike[str],
) -> Path:
    """Validate raw or WRAP ASKL against ANIM using parsed resource contents."""
    anim_path = Path(anim_path)
    askl_path = Path(askl_path)
    if askl_path.suffix.lower() != ".askl":
        raise DecodeError(f"Selected file is not an ASKL: {askl_path.name}")
    _validate_matching_askl_bytes(anim_path, askl_path)
    return askl_path


def _candidate_score(anim_path: Path, candidate: Path, kind: str, expected_hash: int) -> tuple:
    """Rank already-validated candidates without using game-name/WOS locks."""
    low = candidate.as_posix().lower()
    token = _expected_hash_token(expected_hash)
    anim_pack_root = _nearest_sm3_extract_pack_root(anim_path)
    candidate_pack_root = _nearest_sm3_extract_pack_root(candidate)
    same_pack = 0 if anim_pack_root is not None and candidate_pack_root == anim_pack_root else 1
    # Prefer a directly parsed ASKL to HSAM fallback; prefer raw ASKL to WRAP
    # when both describe the same exact skeleton. WRAP remains fully supported.
    kind_rank = {"RAW_ASKL": 0, "WRAP_ASKL": 1, "SM3_T4_HSAM": 2}.get(kind, 9)
    filename_hash = 0 if token in candidate.name.lower() else 1
    canonical = 0 if "/02_apkf_extracted_real_ext/askl/" in f"/{low}" else 1
    return (kind_rank, same_pack, filename_hash, canonical, len(candidate.parts), low)


def find_matching_skeleton_source(
    anim_path: str | os.PathLike[str],
    search_root: str | os.PathLike[str],
) -> Optional[Path]:
    """Scan a user-selected folder and find the skeleton that truly matches ANIM.

    v5.2.129 rules:
      * no WOS/path-name blacklist;
      * raw ASKL and WRAP ASKL are both parsed and hash-checked;
      * exact-hash T4 HSAM remains a safe RAW_TRACK fallback;
      * wrong same-name/same-folder files are ignored when their contents fail.
    """
    anim_path = Path(anim_path)
    search_root = Path(search_root)
    if not anim_path.is_file() or not search_root.exists() or not search_root.is_dir():
        return None
    header = inspect_anim_header(anim_path)
    token = _expected_hash_token(header.askl_hash)

    askl_files = [p for p in search_root.rglob("*.askl") if p.is_file()]
    # Fast path first: filenames carrying the expected hash. Then scan all
    # remaining ASKLs because a valid wrapper may use a different filename.
    askl_files.sort(key=lambda p: (0 if token in p.name.lower() else 1, len(p.parts), p.as_posix().lower()))

    validated: List[Tuple[tuple, Path]] = []
    for candidate in askl_files:
        try:
            kind = classify_sm3_skeleton_source(anim_path, candidate)
        except Exception:
            continue
        if kind not in ("RAW_ASKL", "WRAP_ASKL"):
            continue
        validated.append((_candidate_score(anim_path, candidate, kind, header.askl_hash), candidate))

    if validated:
        validated.sort(key=lambda item: item[0])
        return validated[0][1]

    # No parseable ASKL in the selected folder. Fall back to exact-hash T4
    # HSAM provenance so Motion Editor can still use proven RAW_TRACKS mode.
    hsam_matches: List[Path] = []
    for candidate in search_root.rglob("*.hsam"):
        if _looks_like_sm3_t4_hsam_source(candidate, header.askl_hash):
            hsam_matches.append(candidate)
    if hsam_matches:
        hsam_matches.sort(key=lambda p: _candidate_score(anim_path, p, "SM3_T4_HSAM", header.askl_hash))
        return hsam_matches[0]
    return None


def find_matching_askl(anim_path: str | os.PathLike[str], search_root: str | os.PathLike[str]) -> Optional[Path]:
    """Find a parsed exact-match raw/WRAP ASKL inside ``search_root``."""
    found = find_matching_skeleton_source(anim_path, search_root)
    if found is not None and found.suffix.lower() == ".askl":
        return found
    return None
