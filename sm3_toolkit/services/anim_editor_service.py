#!/usr/bin/env python3
"""
SM3 Toolkit NAS ANIM Motion Editor Service v0.1

ASKL-aware editing layer that connects the reversible scalar codec to the
named field / element / bone mapping recovered by anim_decoder_service.

This service intentionally edits the codec's signed integer scalar tracks.
It does not invent new pose semantics: the game still applies ASKL scale,
quaternion normalization, sparse IDs, and the recovered NAL post-processing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sm3_toolkit.services.anim_codec_service import AnimCodecError
from sm3_toolkit.services.anim_decoder_service import (
    AnimHeader,
    COMPRESSED_WIDTH,
    FIELD_NAMES,
    SM3AnimPoseDecoder,
)


COMPONENT_NAMES: Tuple[Tuple[str, ...], ...] = (
    ("X", "Y", "Z"),
    ("X", "Y", "Z", "W"),
    ("ANGLE",),
    ("X", "Y", "Z"),
    (),
    ("VALUE",),
    ("VALUE",),
    ("VALUE",),
    ("X", "Y", "Z"),
)


@dataclass(frozen=True)
class AnimTrackBinding:
    track_index: int
    field_index: int
    field_name: str
    element_index: int
    element_ordinal: int
    component_index: int
    component_name: str
    bone_index: Optional[int]
    bone_name: Optional[str]
    bone_hash: Optional[int]
    sparse_id: Optional[int]
    scale: Optional[float]

    @property
    def element_key(self) -> str:
        return f"{self.field_index}:{self.element_index}"

    @property
    def element_label(self) -> str:
        if self.bone_index is not None:
            name = self.bone_name or f"bone_{self.bone_index}"
            return f"{name}  [bone {self.bone_index} / element {self.element_index}]"
        if self.sparse_id is not None:
            return f"Sparse ID {self.sparse_id}  [element {self.element_index}]"
        return f"Element {self.element_index}"

    @property
    def track_label(self) -> str:
        return f"Track {self.track_index} — {self.field_name} / {self.element_label} / {self.component_name}"


def _sparse_id_for(decoder: SM3AnimPoseDecoder, field: int, ordinal: int) -> Optional[int]:
    if field == 3 and ordinal < len(decoder.error_correction_ids):
        return int(decoder.error_correction_ids[ordinal])
    if field == 8 and ordinal < len(decoder.bone_scale_ids):
        return int(decoder.bone_scale_ids[ordinal])
    return None


def build_track_bindings(decoder: SM3AnimPoseDecoder) -> List[AnimTrackBinding]:
    """Map flat compressed scalar track order to ASKL-aware field/bone/components."""
    out: List[AnimTrackBinding] = []
    track_index = 0

    for field in range(9):
        width = int(COMPRESSED_WIDTH[field])
        if width == 0:
            continue
        components = COMPONENT_NAMES[field]
        if len(components) != width:
            raise AnimCodecError(
                f"internal component map mismatch for {FIELD_NAMES[field]}: {len(components)} != {width}"
            )
        scale_array = decoder.askl.scales[field]
        if decoder.compressed_indices[field] and scale_array is None:
            raise AnimCodecError(
                f"{FIELD_NAMES[field]} has compressed elements but the matching ASKL scale array is NULL"
            )
        for ordinal, element in enumerate(decoder.compressed_indices[field]):
            if scale_array is not None and element >= len(scale_array):
                raise AnimCodecError(
                    f"{FIELD_NAMES[field]} element {element} exceeds ASKL scale array ({len(scale_array)})"
                )
            sparse_id = _sparse_id_for(decoder, field, ordinal)
            bone_index = decoder._bone_for_field_element(field, element, sparse_id)
            bone_hash, _name_token, bone_name = decoder._bone_meta(bone_index)
            scale: Optional[float] = None
            if scale_array is not None and element < len(scale_array):
                scale = float(scale_array[element])

            for component_index, component_name in enumerate(components):
                out.append(AnimTrackBinding(
                    track_index=track_index,
                    field_index=field,
                    field_name=FIELD_NAMES[field],
                    element_index=int(element),
                    element_ordinal=int(ordinal),
                    component_index=component_index,
                    component_name=component_name,
                    bone_index=bone_index,
                    bone_name=bone_name,
                    bone_hash=bone_hash,
                    sparse_id=sparse_id,
                    scale=scale,
                ))
                track_index += 1

    expected = int(decoder.anim.compressed_track_count)
    if track_index != expected:
        raise AnimCodecError(
            f"ASKL track map produced {track_index} scalar tracks; ANIM expects {expected}"
        )
    return out



def build_raw_track_bindings(track_count: int) -> List[AnimTrackBinding]:
    """Safe ANIM-only fallback when SM3 exposes only a T4 HSAM skeleton source.

    This deliberately does NOT invent field/bone semantics. It keeps the proven
    raw scalar editor usable while the true raw ASKL serialization is absent.
    """
    out: List[AnimTrackBinding] = []
    for track_index in range(int(track_count)):
        out.append(AnimTrackBinding(
            track_index=track_index,
            field_index=-1,
            field_name="RAW_TRACKS",
            element_index=track_index,
            element_ordinal=track_index,
            component_index=0,
            component_name="VALUE",
            bone_index=None,
            bone_name=None,
            bone_hash=None,
            sparse_id=None,
            scale=None,
        ))
    return out


def validate_codec_json_for_anim_header(obj: Dict[str, Any], header: AnimHeader) -> None:
    if obj.get("format") != "SM3_ANIM_CODEC_JSON_V1":
        raise AnimCodecError("JSON is not SM3_ANIM_CODEC_JSON_V1")
    jh = obj.get("header")
    frames = obj.get("frames")
    if not isinstance(jh, dict) or not isinstance(frames, list):
        raise AnimCodecError("editable JSON is missing header/frames")
    checks = (
        ("source_hash", int(header.resource_hash)),
        ("askl_hash", int(header.askl_hash)),
        ("frame_count", int(header.sample_count)),
        ("compressed_track_count", int(header.compressed_track_count)),
    )
    for key, expected in checks:
        actual = int(jh.get(key, -1))
        if actual != expected:
            raise AnimCodecError(f"editable JSON {key} mismatch: {actual} != {expected}")
    if len(frames) != int(header.sample_count):
        raise AnimCodecError(f"editable JSON frame list has {len(frames)} rows; expected {header.sample_count}")
    for fi, row in enumerate(frames):
        if not isinstance(row, list) or len(row) != int(header.compressed_track_count):
            raise AnimCodecError(
                f"editable JSON frame {fi} has {len(row) if isinstance(row, list) else 'invalid'} tracks; "
                f"expected {header.compressed_track_count}"
            )


def validate_codec_json_for_decoder(obj: Dict[str, Any], decoder: SM3AnimPoseDecoder) -> None:
    if obj.get("format") != "SM3_ANIM_CODEC_JSON_V1":
        raise AnimCodecError("JSON is not SM3_ANIM_CODEC_JSON_V1")
    header = obj.get("header")
    frames = obj.get("frames")
    if not isinstance(header, dict) or not isinstance(frames, list):
        raise AnimCodecError("editable JSON is missing header/frames")

    checks = (
        ("source_hash", int(decoder.anim.resource_hash)),
        ("askl_hash", int(decoder.anim.askl_hash)),
        ("frame_count", int(decoder.anim.sample_count)),
        ("compressed_track_count", int(decoder.anim.compressed_track_count)),
    )
    for key, expected in checks:
        actual = int(header.get(key, -1))
        if actual != expected:
            raise AnimCodecError(
                f"editable JSON {key} mismatch: {actual} != {expected} for selected ANIM/ASKL"
            )

    if len(frames) != int(decoder.anim.sample_count):
        raise AnimCodecError(
            f"editable JSON frame list has {len(frames)} rows; expected {decoder.anim.sample_count}"
        )
    track_count = int(decoder.anim.compressed_track_count)
    for fi, row in enumerate(frames):
        if not isinstance(row, list) or len(row) != track_count:
            raise AnimCodecError(
                f"editable JSON frame {fi} has {len(row) if isinstance(row, list) else 'invalid'} tracks; expected {track_count}"
            )


class AnimScalarEditor:
    def __init__(self, obj: Dict[str, Any], decoder: SM3AnimPoseDecoder):
        validate_codec_json_for_decoder(obj, decoder)
        self.obj = obj
        self.decoder = decoder
        self.bindings = build_track_bindings(decoder)
        self.binding_by_track = {b.track_index: b for b in self.bindings}

    @property
    def frame_count(self) -> int:
        return len(self.obj["frames"])

    @property
    def track_count(self) -> int:
        return len(self.bindings)

    def value(self, frame: int, track: int) -> int:
        self._validate_frame_track(frame, track)
        return int(self.obj["frames"][frame][track])

    def set_value(self, frame: int, track: int, value: int, *, note: str = "") -> Tuple[int, int]:
        self._validate_frame_track(frame, track)
        old = int(self.obj["frames"][frame][track])
        new = int(value)
        # Keep values within signed 32-bit semantics used by the native predictor.
        if new < -0x80000000 or new > 0x7FFFFFFF:
            raise AnimCodecError("edited scalar must fit signed 32-bit range")
        self.obj["frames"][frame][track] = new
        self._record_change(frame, frame, track, "SET", old, new, note)
        return old, new

    def add_delta(self, start_frame: int, end_frame: int, track: int, delta: int, *, note: str = "") -> List[Tuple[int, int, int]]:
        if start_frame > end_frame:
            start_frame, end_frame = end_frame, start_frame
        self._validate_frame_track(start_frame, track)
        self._validate_frame_track(end_frame, track)
        delta = int(delta)
        changes: List[Tuple[int, int, int]] = []
        for frame in range(start_frame, end_frame + 1):
            old = int(self.obj["frames"][frame][track])
            new = old + delta
            if new < -0x80000000 or new > 0x7FFFFFFF:
                raise AnimCodecError(f"frame {frame} edited scalar exceeds signed 32-bit range")
            self.obj["frames"][frame][track] = new
            changes.append((frame, old, new))
        self._record_change(start_frame, end_frame, track, "ADD_DELTA", None, delta, note)
        return changes

    def approximate_scaled_value(self, frame: int, track: int) -> Optional[float]:
        binding = self.binding_by_track[track]
        if binding.scale is None:
            return None
        return float(self.value(frame, track)) * float(binding.scale)

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.obj, indent=2) + "\n", encoding="utf-8")

    def _validate_frame_track(self, frame: int, track: int) -> None:
        if frame < 0 or frame >= self.frame_count:
            raise AnimCodecError(f"frame {frame} outside 0..{self.frame_count - 1}")
        if track < 0 or track >= self.track_count:
            raise AnimCodecError(f"track {track} outside 0..{self.track_count - 1}")

    def _record_change(
        self,
        start_frame: int,
        end_frame: int,
        track: int,
        operation: str,
        old_value: Optional[int],
        new_or_delta: int,
        note: str,
    ) -> None:
        binding = self.binding_by_track.get(track)
        audit = self.obj.setdefault("nas_motion_editor", {})
        audit["format"] = "NAS_MOTION_EDITOR_V1"
        audit["askl_aware"] = self.decoder is not None
        changes = audit.setdefault("changes", [])
        entry: Dict[str, Any] = {
            "operation": operation,
            "frame_start": int(start_frame),
            "frame_end": int(end_frame),
            "track_index": int(track),
            "old_value": old_value,
            "new_value_or_delta": int(new_or_delta),
            "note": str(note or ""),
        }
        if binding is not None:
            entry["binding"] = asdict(binding)
        changes.append(entry)





class AnimNamedProfileEditor(AnimScalarEditor):
    """ANIM-only editor using a built-in named skeleton profile.

    v5.2.191 supports the shared Spider-Man/Black Suit/Peter 0xCFB154CD
    profile and Player Goblin 0x900E49A5.  Unlike ``AnimRawTrackEditor``, this
    exposes real field/node/component names without requiring an ASKL file.
    """
    def __init__(self, obj: Dict[str, Any], header: AnimHeader, named_rows):
        validate_codec_json_for_anim_header(obj, header)
        from sm3_toolkit.services.spiderman_named_profile_service import load_profile_for_hash

        profile = load_profile_for_hash(header.askl_hash)
        scales = profile.get("quantization_scales", [])
        bones = {int(b["index"]): b for b in profile.get("bones", [])}
        bindings: List[AnimTrackBinding] = []
        for row in named_rows:
            scale = None
            try:
                field_scales = scales[int(row.field_index)]
                if field_scales is not None:
                    scale = float(field_scales[int(row.element_index)])
            except Exception:
                scale = None
            bone_hash = None
            if row.bone_index is not None:
                bone = bones.get(int(row.bone_index))
                if bone:
                    try:
                        bone_hash = int(str(bone.get("runtime_id_or_hash", "0")), 0)
                    except Exception:
                        bone_hash = None
            bindings.append(AnimTrackBinding(
                track_index=int(row.track_index),
                field_index=int(row.field_index),
                field_name=str(row.field_name),
                element_index=int(row.element_index),
                element_ordinal=int(row.element_index),
                component_index=int(row.component_index),
                component_name=str(row.component_name),
                bone_index=None if row.bone_index is None else int(row.bone_index),
                bone_name=str(row.bone_name) if row.bone_name else None,
                bone_hash=bone_hash,
                sparse_id=None if row.sparse_id is None else int(row.sparse_id),
                scale=scale,
            ))
        if len(bindings) != int(header.compressed_track_count):
            raise AnimCodecError(
                f"runtime named profile produced {len(bindings)} tracks; ANIM expects {header.compressed_track_count}"
            )
        self.obj = obj
        self.decoder = None
        self.bindings = bindings
        self.binding_by_track = {b.track_index: b for b in bindings}
        self.runtime_named_profile = True


class AnimRawTrackEditor(AnimScalarEditor):
    """ANIM-only editor used when the correct SM3 source is a T4 HSAM.

    Encoding/build verification remains identical. Only named ASKL mapping and
    scale display are unavailable, so every scalar is exposed as RAW_TRACKS.
    """
    def __init__(self, obj: Dict[str, Any], header: AnimHeader):
        validate_codec_json_for_anim_header(obj, header)
        self.obj = obj
        self.decoder = None
        self.bindings = build_raw_track_bindings(int(header.compressed_track_count))
        self.binding_by_track = {b.track_index: b for b in self.bindings}


def grouped_bindings(bindings: Sequence[AnimTrackBinding]) -> Dict[str, Dict[str, List[AnimTrackBinding]]]:
    """Return field_name -> element_key -> component bindings, preserving stream order."""
    grouped: Dict[str, Dict[str, List[AnimTrackBinding]]] = {}
    for b in bindings:
        grouped.setdefault(b.field_name, {}).setdefault(b.element_key, []).append(b)
    return grouped
