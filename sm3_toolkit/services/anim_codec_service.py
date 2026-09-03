#!/usr/bin/env python3
"""
SM3 Toolkit NAS ANIM Codec Service v0.3
Integrated NAS scalar-track decoder / encoder for Spider-Man 3 PC ANIM v0x20116.

Scope in v0.3:
  * Parse loose .anim resources used by RaimiHook NativeANIM.
  * Resolve local APKF pointer tokens relative to the +0xB0 bitstream token.
  * Decode every compressed scalar track for every frame.
  * Parse known auxiliary metadata and post-scale entries.
  * Re-encode scalar tracks with preserved or automatically selected codecs.
  * Safe template-based rebuild for edits that still fit the original payload region.
  * EXPERIMENTAL arbitrary-size loose-ANIM rebuild: grow the compressed payload, shift the metadata tail, and rewrite the known local ANIM pointer tokens.
  * Bit-exact no-edit round-trip verification.

The separate NAS pose decoder supplies ASKL/named-bone reconstruction; this module owns the reversible scalar codec/rebuilder layer.
No external Python dependencies are required.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import struct
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ANIM_VERSION = 0x00020116
ANIM_HEADER_SIZE = 0xB0
CLASS_WIDTHS = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 20, 30)
FIELD_NAMES = (
    "FK_POSITION",
    "FK_QUATERNION",
    "FK_AXIS1_ROTATION",
    "FK_ERROR_CORRECTION",
    "FK_TRAJECTORY",
    "FLOOR_OFFSET",
    "CAMERA_FOV",
    "MORPH_SLIDERS",
    "BONE_SCALE",
)
FIELD_SCALAR_WIDTHS = (3, 4, 1, 3, 0, 1, 1, 1, 3)
FIELD_POSE_STRIDES = (4, 4, 1, 4, 8, 1, 1, 1, 4)


class AnimCodecError(RuntimeError):
    pass


def u32(data: bytes | bytearray, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise AnimCodecError(f"u32 read out of range at 0x{off:X}")
    return struct.unpack_from("<I", data, off)[0]


def i32_from_u32(v: int) -> int:
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v


def wrap_i32(v: int) -> int:
    return i32_from_u32(v)


def f32(data: bytes | bytearray, off: int) -> float:
    if off < 0 or off + 4 > len(data):
        raise AnimCodecError(f"f32 read out of range at 0x{off:X}")
    return struct.unpack_from("<f", data, off)[0]


def p32(buf: bytearray, off: int, value: int) -> None:
    if off < 0 or off + 4 > len(buf):
        raise AnimCodecError(f"u32 write out of range at 0x{off:X}")
    struct.pack_into("<I", buf, off, value & 0xFFFFFFFF)


@dataclass
class DecodeStats:
    class0: int = 0
    explicit_zero: int = 0
    short_form: int = 0
    long_form: int = 0
    positive: int = 0
    negative: int = 0

    def add(self, other: "DecodeStats") -> None:
        self.class0 += other.class0
        self.explicit_zero += other.explicit_zero
        self.short_form += other.short_form
        self.long_form += other.long_form
        self.positive += other.positive
        self.negative += other.negative


class BitReader:
    def __init__(self, data: bytes | bytearray, start: int, end: int):
        if not (0 <= start <= end <= len(data)):
            raise AnimCodecError("invalid bit-reader bounds")
        self.data = data
        self.start = start
        self.end = end
        self.bit_pos = 0

    @property
    def bits_read(self) -> int:
        return self.bit_pos

    @property
    def absolute_bit_pos(self) -> int:
        return self.start * 8 + self.bit_pos

    def read_bits(self, count: int) -> int:
        if count < 0 or count > 31:
            raise AnimCodecError(f"invalid bit count {count}")
        if count == 0:
            return 0
        if self.bit_pos + count > (self.end - self.start) * 8:
            raise AnimCodecError(
                f"compressed bitstream exhausted at relative bit {self.bit_pos} requesting {count} bits"
            )
        value = 0
        for bit_index in range(count):
            absolute = self.start * 8 + self.bit_pos + bit_index
            byte_index = absolute >> 3
            bit_in_byte = absolute & 7
            value |= ((self.data[byte_index] >> bit_in_byte) & 1) << bit_index
        self.bit_pos += count
        return value


class BitWriter:
    def __init__(self, template: bytes | bytearray, start: int, end: int):
        if not (0 <= start <= end <= len(template)):
            raise AnimCodecError("invalid bit-writer bounds")
        self.buf = bytearray(template)
        self.start = start
        self.end = end
        self.bit_pos = 0

    @property
    def bits_written(self) -> int:
        return self.bit_pos

    def write_bits(self, value: int, count: int) -> None:
        if count < 0 or count > 31:
            raise AnimCodecError(f"invalid bit count {count}")
        if count == 0:
            return
        if value < 0 or value >= (1 << count):
            raise AnimCodecError(f"value 0x{value:X} does not fit in {count} bits")
        if self.bit_pos + count > (self.end - self.start) * 8:
            raise AnimCodecError(
                f"encoded bitstream exceeds template payload at bit {self.bit_pos} writing {count} bits"
            )
        for bit_index in range(count):
            absolute = self.start * 8 + self.bit_pos + bit_index
            byte_index = absolute >> 3
            bit_in_byte = absolute & 7
            mask = 1 << bit_in_byte
            if (value >> bit_index) & 1:
                self.buf[byte_index] |= mask
            else:
                self.buf[byte_index] &= (~mask) & 0xFF
        self.bit_pos += count


@dataclass
class TrackCodec:
    first_descriptor6: int
    delta_descriptor6: int
    residual_codec6: int


@dataclass
class PostScaleEntry:
    multiplier: float
    pose_data_byte_offset: int


@dataclass
class SpecialNode:
    offset: int
    key: int
    next_offset: int
    data: Dict[str, Any]


@dataclass
class AnimHeader:
    source_hash: int
    askl_hash: int
    version: int
    flags: int
    duration: float
    frame_interval: float
    field_2c: int
    frame_count: int
    compressed_track_count: int
    post_scale_count: int
    bitstream_token: int
    bitstream_offset: int
    special_token: int
    special_offset: int
    post_scale_token: int
    post_scale_offset: int
    payload_end: int
    channel_present_mask: List[int]
    reference_channel_mask: List[int]


@dataclass
class DecodedAnim:
    header: AnimHeader
    codecs: List[TrackCodec]
    frames: List[List[int]]
    bits_consumed: int
    init_first_stats: DecodeStats
    init_delta_stats: DecodeStats
    residual_stats: DecodeStats
    special_nodes: List[SpecialNode]
    post_scale_entries: List[PostScaleEntry]


class AnimResource:
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < ANIM_HEADER_SIZE:
            raise AnimCodecError(f"file is smaller than 0x{ANIM_HEADER_SIZE:X} ANIM header")
        self.bitstream_token = u32(data, 0x44)
        if self.bitstream_token < 0x2C:
            raise AnimCodecError("invalid ANIM bitstream pointer token")
        self.component_base_token = (self.bitstream_token - 0x2C) & 0xFFFFFFFF
        bitstream_offset = self.resolve_local_token(self.bitstream_token)
        if bitstream_offset != ANIM_HEADER_SIZE:
            raise AnimCodecError(
                f"bitstream token resolves to 0x{bitstream_offset:X}, expected 0x{ANIM_HEADER_SIZE:X}"
            )

    def resolve_local_token(self, token: int) -> int:
        if token == 0:
            return 0
        if (token & 0xFC000000) == 0xFC000000:
            raise AnimCodecError(f"external APKF pointer token 0x{token:08X} is not a local ANIM pointer")
        if token < self.component_base_token:
            raise AnimCodecError(f"pointer token 0x{token:08X} precedes component base token")
        off = (token - self.component_base_token) * 4
        if off >= len(self.data):
            raise AnimCodecError(
                f"pointer token 0x{token:08X} resolves outside file at 0x{off:X}"
            )
        return off

    def resolve_local_token_optional(self, token: int) -> int:
        if token == 0:
            return 0
        return self.resolve_local_token(token)

    def parse_special_nodes(self, special_offset: int) -> Tuple[List[SpecialNode], int]:
        if special_offset == 0:
            return [], len(self.data)
        nodes: List[SpecialNode] = []
        visited = set()
        current = special_offset
        boundary = len(self.data)
        for _ in range(16):
            if current == 0:
                return nodes, boundary
            if current in visited:
                raise AnimCodecError("specialData linked list contains a cycle")
            visited.add(current)
            if current + 8 > len(self.data):
                raise AnimCodecError("specialData node is truncated")
            boundary = min(boundary, current)
            key = u32(self.data, current)
            next_token = u32(self.data, current + 4)
            next_offset = self.resolve_local_token_optional(next_token)
            if next_offset:
                boundary = min(boundary, next_offset)

            payload: Dict[str, Any] = {}
            if key == 0:
                if current + 0x38 > len(self.data):
                    raise AnimCodecError("key0 specialData node is truncated")
                error_count = u32(self.data, current + 0x08)
                error_ids_token = u32(self.data, current + 0x0C)
                error_ids_offset = self.resolve_local_token_optional(error_ids_token)
                scale_count = u32(self.data, current + 0x30)
                scale_ids_token = u32(self.data, current + 0x34)
                scale_ids_offset = self.resolve_local_token_optional(scale_ids_token)
                for off in (error_ids_offset, scale_ids_offset):
                    if off:
                        boundary = min(boundary, off)
                error_ids: List[int] = []
                scale_ids: List[int] = []
                if error_count:
                    if not error_ids_offset or error_ids_offset + error_count * 4 > len(self.data):
                        raise AnimCodecError("FK_ERROR_CORRECTION ID array is outside file")
                    error_ids = [u32(self.data, error_ids_offset + i * 4) for i in range(error_count)]
                if scale_count:
                    if not scale_ids_offset or scale_ids_offset + scale_count * 4 > len(self.data):
                        raise AnimCodecError("BONE_SCALE ID array is outside file")
                    scale_ids = [u32(self.data, scale_ids_offset + i * 4) for i in range(scale_count)]
                payload = {
                    "fk_error_correction_id_count": error_count,
                    "fk_error_correction_ids_offset": error_ids_offset,
                    "fk_error_correction_ids": error_ids,
                    "raw_10_2f_hex": self.data[current + 0x10: current + 0x30].hex(),
                    "bone_scale_id_count": scale_count,
                    "bone_scale_ids_offset": scale_ids_offset,
                    "bone_scale_ids": scale_ids,
                }
            elif key == 1:
                if current + 0x10 > len(self.data):
                    raise AnimCodecError("key1 specialData node is truncated")
                count = u32(self.data, current + 0x08)
                array_token = u32(self.data, current + 0x0C)
                array_offset = self.resolve_local_token_optional(array_token)
                if array_offset:
                    boundary = min(boundary, array_offset)
                array_hex: List[str] = []
                if count:
                    if not array_offset or array_offset + count * 0x10 > len(self.data):
                        raise AnimCodecError("key1 specialData array is outside file")
                    for i in range(count):
                        array_hex.append(self.data[array_offset + i * 0x10: array_offset + (i + 1) * 0x10].hex())
                payload = {
                    "count": count,
                    "array_offset": array_offset,
                    "entries_raw_hex": array_hex,
                }
            else:
                raise AnimCodecError(f"unsupported specialData key {key}")

            nodes.append(SpecialNode(current, key, next_offset, payload))
            current = next_offset
        if current != 0:
            raise AnimCodecError("specialData linked list exceeds 16 nodes")
        return nodes, boundary

    def parse_header(self) -> Tuple[AnimHeader, List[SpecialNode], List[PostScaleEntry]]:
        source_hash = u32(self.data, 0x04)
        askl_hash = u32(self.data, 0x10)
        version = u32(self.data, 0x14)
        if version != ANIM_VERSION:
            raise AnimCodecError(f"unsupported ANIM version 0x{version:08X}; expected 0x{ANIM_VERSION:08X}")
        flags = u32(self.data, 0x20)
        duration = f32(self.data, 0x24)
        frame_interval = f32(self.data, 0x28)
        field_2c = u32(self.data, 0x2C)
        frame_count = u32(self.data, 0x30)
        special_token = u32(self.data, 0x34)
        track_count = u32(self.data, 0x38)
        post_scale_count = u32(self.data, 0x3C)
        post_scale_token = u32(self.data, 0x40)
        bitstream_token = u32(self.data, 0x44)
        special_offset = self.resolve_local_token_optional(special_token)
        post_scale_offset = self.resolve_local_token_optional(post_scale_token)
        bitstream_offset = self.resolve_local_token(bitstream_token)
        present = [u32(self.data, 0x48 + i * 4) for i in range(13)]
        reference = [u32(self.data, 0x7C + i * 4) for i in range(13)]
        special_nodes, special_boundary = self.parse_special_nodes(special_offset)
        payload_end = len(self.data)
        if post_scale_offset:
            payload_end = min(payload_end, post_scale_offset)
        if special_boundary:
            payload_end = min(payload_end, special_boundary)
        if payload_end < ANIM_HEADER_SIZE:
            raise AnimCodecError("computed payload boundary precedes bitstream")
        post_scale_entries: List[PostScaleEntry] = []
        if post_scale_count:
            if not post_scale_offset or post_scale_offset + post_scale_count * 8 > len(self.data):
                raise AnimCodecError("post-scale table is outside ANIM file")
            for i in range(post_scale_count):
                off = post_scale_offset + i * 8
                post_scale_entries.append(PostScaleEntry(f32(self.data, off), u32(self.data, off + 4)))
        header = AnimHeader(
            source_hash=source_hash,
            askl_hash=askl_hash,
            version=version,
            flags=flags,
            duration=duration,
            frame_interval=frame_interval,
            field_2c=field_2c,
            frame_count=frame_count,
            compressed_track_count=track_count,
            post_scale_count=post_scale_count,
            bitstream_token=bitstream_token,
            bitstream_offset=bitstream_offset,
            special_token=special_token,
            special_offset=special_offset,
            post_scale_token=post_scale_token,
            post_scale_offset=post_scale_offset,
            payload_end=payload_end,
            channel_present_mask=present,
            reference_channel_mask=reference,
        )
        return header, special_nodes, post_scale_entries


def decode_signed_value(reader: BitReader, codec6: int, stats: DecodeStats) -> int:
    class_index = codec6 >> 2
    small_bits = (codec6 & 3) + 2
    if class_index >= len(CLASS_WIDTHS):
        raise AnimCodecError(f"invalid codec6 0x{codec6:02X}")
    if class_index == 0:
        stats.class0 += 1
        return 0
    has_value = reader.read_bits(1)
    if has_value == 0:
        stats.explicit_zero += 1
        return 0
    long_form = reader.read_bits(1)
    magnitude_bits = CLASS_WIDTHS[class_index] if long_form else small_bits
    payload_bits = magnitude_bits + 1
    if payload_bits > 31:
        raise AnimCodecError(f"codec6 0x{codec6:02X} requests unsupported {payload_bits}-bit payload")
    payload = reader.read_bits(payload_bits)
    magnitude = (payload >> 1) + 1
    if long_form:
        magnitude += 1 << small_bits
        stats.long_form += 1
    else:
        stats.short_form += 1
    if payload & 1:
        stats.negative += 1
        return -magnitude
    stats.positive += 1
    return magnitude


def decode_initial_signed(reader: BitReader, stats: DecodeStats) -> Tuple[int, int]:
    descriptor6 = reader.read_bits(6) & 0x3F
    return descriptor6, decode_signed_value(reader, descriptor6, stats)


def decode_anim(data: bytes) -> DecodedAnim:
    resource = AnimResource(data)
    header, special_nodes, post_scale_entries = resource.parse_header()
    tc = header.compressed_track_count
    fc = header.frame_count
    if tc <= 0 or tc > 1_000_000:
        raise AnimCodecError(f"unreasonable compressed track count {tc}")
    if fc <= 0 or fc > 10_000_000:
        raise AnimCodecError(f"unreasonable frame count {fc}")
    reader = BitReader(data, header.bitstream_offset, header.payload_end)
    first_stats = DecodeStats()
    delta_stats = DecodeStats()
    residual_stats = DecodeStats()
    first_values = [0] * tc
    current_values = [0] * tc
    first_descriptors = [0] * tc
    delta_descriptors = [0] * tc
    residual_codecs = [0] * tc

    for i in range(tc):
        d, v = decode_initial_signed(reader, first_stats)
        first_descriptors[i] = d
        first_values[i] = wrap_i32(v)

    for i in range(tc):
        d, delta = decode_initial_signed(reader, delta_stats)
        delta_descriptors[i] = d
        current_values[i] = wrap_i32(first_values[i] + delta)

    for i in range(tc):
        residual_codecs[i] = reader.read_bits(6) & 0x3F

    codecs = [TrackCodec(first_descriptors[i], delta_descriptors[i], residual_codecs[i]) for i in range(tc)]
    frames: List[List[int]] = []
    frames.append(first_values.copy())
    if fc >= 2:
        frames.append(current_values.copy())

    previous = first_values.copy()
    current = current_values.copy()
    for _frame in range(2, fc):
        nxt = [0] * tc
        for i in range(tc):
            residual = decode_signed_value(reader, residual_codecs[i], residual_stats)
            nxt[i] = wrap_i32(2 * current[i] - previous[i] + residual)
        frames.append(nxt)
        previous, current = current, nxt

    if len(frames) != fc:
        raise AnimCodecError(f"decoded {len(frames)} frames, header says {fc}")

    return DecodedAnim(
        header=header,
        codecs=codecs,
        frames=frames,
        bits_consumed=reader.bits_read,
        init_first_stats=first_stats,
        init_delta_stats=delta_stats,
        residual_stats=residual_stats,
        special_nodes=special_nodes,
        post_scale_entries=post_scale_entries,
    )


def signed_value_bit_cost(codec6: int, value: int) -> Optional[int]:
    class_index = codec6 >> 2
    small_bits = (codec6 & 3) + 2
    if not (0 <= class_index < 16):
        return None
    if class_index == 0:
        return 0 if value == 0 else None
    if value == 0:
        return 1  # hasValue=0
    mag = abs(int(value))
    short_max = 1 << small_bits
    if mag <= short_max:
        return 2 + small_bits + 1
    long_max = short_max + (1 << CLASS_WIDTHS[class_index])
    if mag <= long_max:
        payload_bits = CLASS_WIDTHS[class_index] + 1
        if payload_bits > 31:
            return None
        return 2 + payload_bits
    return None


def choose_best_descriptor(values: Sequence[int]) -> int:
    best: Optional[Tuple[int, int]] = None
    for codec6 in range(64):
        total = 6  # descriptor itself
        possible = True
        for v in values:
            c = signed_value_bit_cost(codec6, v)
            if c is None:
                possible = False
                break
            total += c
        if possible and (best is None or total < best[0] or (total == best[0] and codec6 < best[1])):
            best = (total, codec6)
    if best is None:
        max_abs = max((abs(int(v)) for v in values), default=0)
        raise AnimCodecError(f"no codec descriptor can represent value set (max abs={max_abs})")
    return best[1]


def encode_signed_value(writer: BitWriter, codec6: int, value: int) -> None:
    class_index = codec6 >> 2
    small_bits = (codec6 & 3) + 2
    if not (0 <= class_index < 16):
        raise AnimCodecError(f"invalid codec6 0x{codec6:02X}")
    value = int(value)
    if class_index == 0:
        if value != 0:
            raise AnimCodecError(f"class0 codec cannot encode nonzero value {value}")
        return
    if value == 0:
        writer.write_bits(0, 1)
        return
    writer.write_bits(1, 1)
    mag = abs(value)
    short_max = 1 << small_bits
    negative = 1 if value < 0 else 0
    if mag <= short_max:
        writer.write_bits(0, 1)
        magnitude_base = mag - 1
        payload = (magnitude_base << 1) | negative
        writer.write_bits(payload, small_bits + 1)
        return
    class_width = CLASS_WIDTHS[class_index]
    long_max = short_max + (1 << class_width)
    if mag > long_max:
        raise AnimCodecError(
            f"codec6 0x{codec6:02X} cannot encode magnitude {mag} (max {long_max})"
        )
    writer.write_bits(1, 1)
    magnitude_base = mag - short_max - 1
    payload = (magnitude_base << 1) | negative
    writer.write_bits(payload, class_width + 1)


def residual_for(previous: int, current: int, next_value: int) -> int:
    return wrap_i32(int(next_value) - 2 * int(current) + int(previous))



def _align4(value: int) -> int:
    return (int(value) + 3) & ~3


def _grow_anim_template_for_payload(
    template: bytes,
    resource: AnimResource,
    header: AnimHeader,
    required_bits: int,
) -> Tuple[bytes, int, Dict[str, Any]]:
    """Grow only the loose ANIM resource's compressed-payload region.

    The compressed stream always begins at +0xB0.  When it outgrows the old
    payload boundary, shift the entire metadata tail forward by a DWORD-aligned
    delta and rewrite the local pointer tokens whose targets moved.

    This is intentionally narrower than a generic APKF pack rebuilder: it
    produces a self-consistent *loose ANIM resource* for RaimiHook/NativeANIM
    testing.  Unknown tail bytes are preserved verbatim.  Only pointer fields
    already proven by the ANIM reverse pass are rewritten.
    """
    old_payload_end = int(header.payload_end)
    old_capacity_bits = (old_payload_end - header.bitstream_offset) * 8
    if required_bits <= old_capacity_bits:
        return template, old_payload_end, {
            "resized": False,
            "size_delta_bytes": 0,
            "relocated_known_tokens": 0,
            "old_payload_end": old_payload_end,
            "new_payload_end": old_payload_end,
        }

    required_bytes = (int(required_bits) + 7) // 8
    new_payload_end = _align4(header.bitstream_offset + required_bytes)
    if new_payload_end <= old_payload_end:
        new_payload_end = old_payload_end + 4
    delta = new_payload_end - old_payload_end
    if delta <= 0 or (delta & 3):
        raise AnimCodecError(f"invalid arbitrary-size payload growth delta {delta}")

    # Preserve the entire old tail byte-for-byte, inserting only the new room
    # needed by the compressed stream before it.
    buf = bytearray(template[:old_payload_end])
    buf.extend(b"\x00" * delta)
    buf.extend(template[old_payload_end:])

    word_delta = delta // 4
    relocated = 0

    def shifted_offset(old_off: int) -> int:
        return old_off + delta if old_off >= old_payload_end else old_off

    def translated_token(old_token: int) -> int:
        nonlocal relocated
        if old_token == 0:
            return 0
        # External APKF resource-ref tokens (0xFC......) do not describe local
        # ANIM offsets and must remain untouched.
        if (old_token & 0xFC000000) == 0xFC000000:
            return old_token
        old_target = resource.resolve_local_token(old_token)
        if old_target >= old_payload_end:
            relocated += 1
            return (old_token + word_delta) & 0xFFFFFFFF
        return old_token

    # Header local pointers proven by 008BDDF0 / AnimClipData layout.
    for field_off in (0x34, 0x40):  # auxMetadata, postScaleEntries
        tok = u32(template, field_off)
        p32(buf, field_off, translated_token(tok))

    # Rewrite the local links/arrays inside the known auxiliary metadata chain.
    _h, nodes, _post = resource.parse_header()
    for node in nodes:
        new_node_off = shifted_offset(node.offset)
        p32(buf, new_node_off + 0x04, translated_token(u32(template, node.offset + 0x04)))
        if node.key == 0:
            p32(buf, new_node_off + 0x0C, translated_token(u32(template, node.offset + 0x0C)))
            p32(buf, new_node_off + 0x34, translated_token(u32(template, node.offset + 0x34)))
        elif node.key == 1:
            p32(buf, new_node_off + 0x0C, translated_token(u32(template, node.offset + 0x0C)))

    return bytes(buf), new_payload_end, {
        "resized": True,
        "size_delta_bytes": delta,
        "relocated_known_tokens": relocated,
        "old_payload_end": old_payload_end,
        "new_payload_end": new_payload_end,
    }


def _encoded_bit_count(
    header: AnimHeader,
    frames: Sequence[Sequence[int]],
    codecs: Sequence[TrackCodec],
    residuals_by_track: Sequence[Sequence[int]],
) -> int:
    tc = header.compressed_track_count
    bits = 0
    for ti in range(tc):
        c = signed_value_bit_cost(codecs[ti].first_descriptor6, int(frames[0][ti]))
        if c is None:
            raise AnimCodecError(f"track {ti} frame0 value is not encodable")
        bits += 6 + c
    for ti in range(tc):
        delta = wrap_i32(int(frames[1][ti]) - int(frames[0][ti])) if header.frame_count >= 2 else 0
        c = signed_value_bit_cost(codecs[ti].delta_descriptor6, delta)
        if c is None:
            raise AnimCodecError(f"track {ti} initial delta is not encodable")
        bits += 6 + c
    bits += 6 * tc
    for fi in range(2, header.frame_count):
        for ti in range(tc):
            r = residual_for(frames[fi - 2][ti], frames[fi - 1][ti], frames[fi][ti])
            c = signed_value_bit_cost(codecs[ti].residual_codec6, r)
            if c is None:
                raise AnimCodecError(f"track {ti} frame {fi} residual is not encodable")
            bits += c
    return bits


def encode_frames_into_template(
    template: bytes,
    decoded_or_dict: DecodedAnim | Dict[str, Any],
    auto_codecs: bool = False,
    allow_arbitrary_size: bool = False,
) -> Tuple[bytes, Dict[str, Any]]:
    resource = AnimResource(template)
    header, _nodes, _post = resource.parse_header()

    if isinstance(decoded_or_dict, DecodedAnim):
        frames = decoded_or_dict.frames
        original_codecs = decoded_or_dict.codecs
    else:
        frames = [[int(v) for v in row] for row in decoded_or_dict["frames"]]
        original_codecs = [TrackCodec(**c) for c in decoded_or_dict.get("codecs", [])]

    if len(frames) != header.frame_count:
        raise AnimCodecError(f"JSON has {len(frames)} frames; template expects {header.frame_count}")
    tc = header.compressed_track_count
    for fi, row in enumerate(frames):
        if len(row) != tc:
            raise AnimCodecError(f"frame {fi} has {len(row)} tracks; template expects {tc}")
        for ti, v in enumerate(row):
            if not (-0x80000000 <= int(v) <= 0x7FFFFFFF):
                raise AnimCodecError(f"frame {fi} track {ti} is outside int32 range: {v}")

    residuals_by_track: List[List[int]] = [[] for _ in range(tc)]
    if header.frame_count >= 3:
        for ti in range(tc):
            for fi in range(2, header.frame_count):
                residuals_by_track[ti].append(
                    residual_for(frames[fi - 2][ti], frames[fi - 1][ti], frames[fi][ti])
                )

    codecs: List[TrackCodec] = []
    for ti in range(tc):
        first = frames[0][ti]
        delta = wrap_i32(frames[1][ti] - frames[0][ti]) if header.frame_count >= 2 else 0
        if auto_codecs or len(original_codecs) != tc:
            first_d = choose_best_descriptor([first])
            delta_d = choose_best_descriptor([delta])
            residual_d = choose_best_descriptor(residuals_by_track[ti]) if residuals_by_track[ti] else 0
        else:
            orig = original_codecs[ti]
            first_d = orig.first_descriptor6
            delta_d = orig.delta_descriptor6
            residual_d = orig.residual_codec6
            # Validate representability before writing anything.
            if signed_value_bit_cost(first_d, first) is None:
                raise AnimCodecError(
                    f"track {ti} frame0 value {first} no longer fits preserved first descriptor 0x{first_d:02X}; use --auto-codecs"
                )
            if signed_value_bit_cost(delta_d, delta) is None:
                raise AnimCodecError(
                    f"track {ti} initial delta {delta} no longer fits preserved delta descriptor 0x{delta_d:02X}; use --auto-codecs"
                )
            for r in residuals_by_track[ti]:
                if signed_value_bit_cost(residual_d, r) is None:
                    raise AnimCodecError(
                        f"track {ti} residual {r} no longer fits preserved residual codec 0x{residual_d:02X}; use --auto-codecs"
                    )
        codecs.append(TrackCodec(first_d, delta_d, residual_d))

    required_bits = _encoded_bit_count(header, frames, codecs, residuals_by_track)
    old_capacity_bits = (header.payload_end - header.bitstream_offset) * 8
    working_template = template
    writer_end = header.payload_end
    resize_info = {
        "resized": False,
        "size_delta_bytes": 0,
        "relocated_known_tokens": 0,
        "old_payload_end": header.payload_end,
        "new_payload_end": header.payload_end,
    }
    if required_bits > old_capacity_bits:
        if not allow_arbitrary_size:
            raise AnimCodecError(
                f"encoded bitstream requires {required_bits} bits but template payload has only {old_capacity_bits}; "
                "enable EXPERIMENTAL arbitrary-size loose ANIM rebuild"
            )
        working_template, writer_end, resize_info = _grow_anim_template_for_payload(
            template, resource, header, required_bits
        )

    writer = BitWriter(working_template, header.bitstream_offset, writer_end)
    for ti in range(tc):
        writer.write_bits(codecs[ti].first_descriptor6, 6)
        encode_signed_value(writer, codecs[ti].first_descriptor6, frames[0][ti])
    for ti in range(tc):
        delta = wrap_i32(frames[1][ti] - frames[0][ti]) if header.frame_count >= 2 else 0
        writer.write_bits(codecs[ti].delta_descriptor6, 6)
        encode_signed_value(writer, codecs[ti].delta_descriptor6, delta)
    for ti in range(tc):
        writer.write_bits(codecs[ti].residual_codec6, 6)
    for fi in range(2, header.frame_count):
        for ti in range(tc):
            r = residual_for(frames[fi - 2][ti], frames[fi - 1][ti], frames[fi][ti])
            encode_signed_value(writer, codecs[ti].residual_codec6, r)

    capacity_bits = (writer_end - header.bitstream_offset) * 8
    info = {
        "bits_written": writer.bits_written,
        "required_bits": required_bits,
        "old_capacity_bits": old_capacity_bits,
        "capacity_bits": capacity_bits,
        "free_bits": capacity_bits - writer.bits_written,
        "bytes_used_ceil": (writer.bits_written + 7) // 8,
        "payload_capacity_bytes": writer_end - header.bitstream_offset,
        "auto_codecs": auto_codecs,
        "allow_arbitrary_size": allow_arbitrary_size,
        "rebuild_mode": "ARBITRARY_SIZE_LOOSE" if resize_info["resized"] else "TEMPLATE_SIZE",
        "old_file_size": len(template),
        "new_file_size": len(writer.buf),
        **resize_info,
        "codecs": [asdict(c) for c in codecs],
    }
    return bytes(writer.buf), info


def decoded_to_json_dict(decoded: DecodedAnim, source_path: Optional[str] = None) -> Dict[str, Any]:
    h = asdict(decoded.header)
    for key in ("source_hash", "askl_hash", "version", "flags", "bitstream_token", "special_token", "post_scale_token"):
        h[key + "_hex"] = f"0x{h[key]:08X}"
    out = {
        "format": "SM3_ANIM_CODEC_JSON_V1",
        "source_file": source_path,
        "field_table": [
            {
                "index": i,
                "name": FIELD_NAMES[i],
                "compressed_scalar_width": FIELD_SCALAR_WIDTHS[i],
                "pose_stride_floats": FIELD_POSE_STRIDES[i],
            }
            for i in range(9)
        ],
        "header": h,
        "bits_consumed": decoded.bits_consumed,
        "bytes_consumed_ceil": (decoded.bits_consumed + 7) // 8,
        "codecs": [asdict(c) for c in decoded.codecs],
        "stats": {
            "initial_first_value": asdict(decoded.init_first_stats),
            "initial_delta": asdict(decoded.init_delta_stats),
            "frame2_plus_residual": asdict(decoded.residual_stats),
        },
        "special_nodes": [asdict(n) for n in decoded.special_nodes],
        "post_scale_entries": [asdict(p) for p in decoded.post_scale_entries],
        "frames": decoded.frames,
    }
    return out


def write_frames_csv(decoded: DecodedAnim, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame"] + [f"track_{i:04d}" for i in range(decoded.header.compressed_track_count)])
        for fi, row in enumerate(decoded.frames):
            w.writerow([fi] + row)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if obj.get("format") != "SM3_ANIM_CODEC_JSON_V1":
        raise AnimCodecError("JSON is not SM3_ANIM_CODEC_JSON_V1")
    return obj


def inspect_text(decoded: DecodedAnim, path: str) -> str:
    h = decoded.header
    expected_duration = h.frame_interval * h.frame_count
    lines = [
        "SM3 Toolkit NAS ANIM Codec Service v0.3",
        f"File: {path}",
        f"Size: {os.path.getsize(path)} bytes",
        f"Source hash: 0x{h.source_hash:08X}",
        f"ASKL hash: 0x{h.askl_hash:08X}",
        f"Version: 0x{h.version:08X}",
        f"Flags: 0x{h.flags:08X} (loop={'YES' if h.flags & 1 else 'NO'})",
        f"Frame count: {h.frame_count}",
        f"Duration: {h.duration:.9f}",
        f"Frame interval: {h.frame_interval:.9f}",
        f"frameInterval*frameCount: {expected_duration:.9f}",
        f"Compressed scalar tracks: {h.compressed_track_count}",
        f"Bitstream: 0x{h.bitstream_offset:X} .. 0x{h.payload_end:X}",
        f"Bitstream capacity: {h.payload_end - h.bitstream_offset} bytes",
        f"Bits consumed: {decoded.bits_consumed} ({(decoded.bits_consumed + 7)//8} bytes ceil)",
        f"Unused payload capacity: {(h.payload_end - h.bitstream_offset)*8 - decoded.bits_consumed} bits",
        f"SpecialData offset: 0x{h.special_offset:X}",
        f"PostScale count: {h.post_scale_count} offset=0x{h.post_scale_offset:X}",
        f"Special nodes: {len(decoded.special_nodes)}",
        "Field widths: " + ", ".join(f"{FIELD_NAMES[i]}={FIELD_SCALAR_WIDTHS[i]}" for i in range(9)),
    ]
    return "\n".join(lines)


def cmd_inspect(args: argparse.Namespace) -> int:
    path = Path(args.input)
    decoded = decode_anim(path.read_bytes())
    print(inspect_text(decoded, str(path)))
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    path = Path(args.input)
    decoded = decode_anim(path.read_bytes())
    out = Path(args.output) if args.output else path.with_suffix(path.suffix + ".decoded.json")
    with out.open("w", encoding="utf-8") as f:
        json.dump(decoded_to_json_dict(decoded, str(path)), f, indent=2)
    if args.csv:
        write_frames_csv(decoded, Path(args.csv))
    print(inspect_text(decoded, str(path)))
    print(f"Decoded JSON: {out}")
    if args.csv:
        print(f"Frames CSV: {args.csv}")
    return 0


def cmd_roundtrip(args: argparse.Namespace) -> int:
    path = Path(args.input)
    data = path.read_bytes()
    decoded = decode_anim(data)
    rebuilt, info = encode_frames_into_template(data, decoded, auto_codecs=False)
    if rebuilt != data:
        first = next((i for i, (a, b) in enumerate(zip(data, rebuilt)) if a != b), None)
        raise AnimCodecError(f"bit-exact roundtrip FAILED; first difference at 0x{first:X}" if first is not None else "bit-exact roundtrip FAILED")
    if args.output:
        Path(args.output).write_bytes(rebuilt)
    print("ROUNDTRIP PASS — entire .anim is bit-identical")
    print(f"bits_written={info['bits_written']} capacity_bits={info['capacity_bits']} free_bits={info['free_bits']}")
    return 0


def cmd_encode(args: argparse.Namespace) -> int:
    json_path = Path(args.json)
    template_path = Path(args.template)
    obj = load_json(json_path)
    template = template_path.read_bytes()
    rebuilt, info = encode_frames_into_template(
        template, obj, auto_codecs=args.auto_codecs,
        allow_arbitrary_size=bool(getattr(args, "allow_arbitrary_size", False)),
    )
    out = Path(args.output)
    out.write_bytes(rebuilt)
    verify = decode_anim(rebuilt)
    input_frames = [[int(v) for v in row] for row in obj["frames"]]
    if verify.frames != input_frames:
        raise AnimCodecError("re-encoded file decoded successfully but scalar frames do not match requested JSON")
    print("ENCODE PASS — re-decoded scalar frames match JSON")
    print(f"Output: {out}")
    print(f"bits_written={info['bits_written']} capacity_bits={info['capacity_bits']} free_bits={info['free_bits']}")
    print("NOTE: v0.3 can optionally grow a loose ANIM resource and relocate its proven local pointer fields. Generic size-changing PCPACK/APKF rebuilding remains separate.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Spider-Man 3 PC ANIM v0x20116 standalone scalar codec")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect", help="parse and summarize a loose .anim")
    s.add_argument("input")
    s.set_defaults(func=cmd_inspect)

    s = sub.add_parser("decode", help="decode every scalar track/frame to JSON")
    s.add_argument("input")
    s.add_argument("-o", "--output")
    s.add_argument("--csv", help="optional frame x track CSV output")
    s.set_defaults(func=cmd_decode)

    s = sub.add_parser("roundtrip", help="decode + re-encode and require whole-file bit identity")
    s.add_argument("input")
    s.add_argument("-o", "--output", help="optional path to write verified identical copy")
    s.set_defaults(func=cmd_roundtrip)

    s = sub.add_parser("encode", help="encode edited scalar-frame JSON back into a template .anim")
    s.add_argument("json")
    s.add_argument("--template", required=True)
    s.add_argument("-o", "--output", required=True)
    s.add_argument("--auto-codecs", action="store_true", help="re-select optimal initial and residual descriptors when edited values no longer fit the originals")
    s.add_argument("--allow-arbitrary-size", action="store_true", help="EXPERIMENTAL: grow a loose ANIM payload and relocate proven local pointer fields when required")
    s.set_defaults(func=cmd_encode)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (AnimCodecError, OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
