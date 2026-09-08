#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

# Backward-compatible public constant: the original built-in profile remains
# CH_SPIDERMAN / 0xCFB154CD.
PROFILE_HASH = 0xCFB154CD
ANIM_VERSION = 0x00020116
ANIM_HEADER_SIZE = 0xB0
FIELD_NAMES = [
    'FK_POSITION','FK_QUATERNION','FK_AXIS1_ROTATION','FK_ERROR_CORRECTION',
    'FK_TRAJECTORY','FLOOR_OFFSET','CAMERA_FOV','MORPH_SLIDERS','BONE_SCALE'
]
COMPRESSED_WIDTH = [3,4,1,3,0,1,1,1,3]
COMPONENT_NAMES = [
    ('X','Y','Z'), ('X','Y','Z','W'), ('ANGLE',), ('X','Y','Z'), (),
    ('OFFSET',), ('FOV',), ('VALUE',), ('X','Y','Z')
]

# v5.2.191: character-aware built-in named skeleton profiles. Black Suit and
# Peter use the same 0xCFB154CD skeleton as Spider-Man in the supplied archives.
BUILTIN_PROFILE_FILES = {
    0xCFB154CD: 'ch_spiderman_0xCFB154CD_named_profile_v1.json',
    0x900E49A5: 'ch_playergoblin_0x900E49A5_named_profile_v1.json',
}

CHARACTER_PATH_ALIASES = (
    ('ch_blacksuit', 'Black Suit', 0xCFB154CD),
    ('ch_peter', 'Peter Parker', 0xCFB154CD),
    ('ch_spiderman', 'Spider-Man', 0xCFB154CD),
    ('ch_playergoblin', 'Player Goblin', 0x900E49A5),
    ('playergoblin', 'Player Goblin', 0x900E49A5),
)

class NamedProfileError(RuntimeError):
    pass

@dataclass(frozen=True)
class NamedTrackRow:
    track_index: int
    field_index: int
    field_name: str
    element_index: int
    component_index: int
    component_name: str
    bone_index: Optional[int]
    bone_name: str
    source: str
    sparse_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise NamedProfileError(f'u32 out of range at 0x{off:X}')
    return struct.unpack_from('<I', data, off)[0]


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / 'data'


def _profile_path_for_hash(resource_hash: int) -> Path:
    h = int(resource_hash) & 0xFFFFFFFF
    filename = BUILTIN_PROFILE_FILES.get(h)
    if not filename:
        raise NamedProfileError(f'No built-in named skeleton profile for ASKL 0x{h:08X}')
    return _data_dir() / filename


def has_builtin_profile(resource_hash: int) -> bool:
    return (int(resource_hash) & 0xFFFFFFFF) in BUILTIN_PROFILE_FILES


def load_profile_for_hash(resource_hash: int) -> dict[str, Any]:
    h = int(resource_hash) & 0xFFFFFFFF
    p = _profile_path_for_hash(h)
    if not p.is_file():
        raise NamedProfileError(f'Built-in named skeleton profile missing: {p}')
    obj = json.loads(p.read_text(encoding='utf-8'))
    if int(str(obj.get('resource_hash','0')), 0) != h:
        raise NamedProfileError(
            f'Built-in profile hash mismatch: requested 0x{h:08X}, file says {obj.get("resource_hash")}'
        )
    bone_count = int(obj.get('bone_count', 0))
    if bone_count <= 0 or len(obj.get('bones', [])) != bone_count:
        raise NamedProfileError(f'Built-in profile 0x{h:08X} has invalid bone table')
    return obj


def load_profile() -> dict[str, Any]:
    """Backward-compatible Spider-Man profile loader."""
    return load_profile_for_hash(PROFILE_HASH)


def identify_character(source_path: str | Path | None, askl_hash: int) -> str:
    """Return the friendly Motion Editor character label for this source/hash."""
    h = int(askl_hash) & 0xFFFFFFFF
    text = str(source_path or '').replace('\\', '/').lower()
    for marker, label, expected_hash in CHARACTER_PATH_ALIASES:
        if marker in text and h == expected_hash:
            return label
    if h == 0x900E49A5:
        return 'Player Goblin'
    if h == 0xCFB154CD:
        return 'Spider-Man family'
    return f'ASKL 0x{h:08X}'


def profile_display_name(resource_hash: int) -> str:
    profile = load_profile_for_hash(resource_hash)
    return str(profile.get('profile_name') or profile.get('resource_name') or f'0x{int(resource_hash)&0xFFFFFFFF:08X}')


def profile_bone_names(resource_hash: int) -> dict[int, str]:
    try:
        profile = load_profile_for_hash(resource_hash)
    except Exception:
        return {}
    return {
        int(row['index']): str(row.get('name') or f"bone_{int(row['index'])}")
        for row in profile.get('bones', [])
    }


def inspect_anim_identity(anim_data: bytes) -> tuple[int,int,int,int]:
    if len(anim_data) < ANIM_HEADER_SIZE:
        raise NamedProfileError(f'ANIM too small: {len(anim_data)} bytes')
    resource_hash = _u32(anim_data, 0x04)
    askl_hash = _u32(anim_data, 0x10)
    version = _u32(anim_data, 0x14)
    track_count = _u32(anim_data, 0x38)
    if version != ANIM_VERSION:
        raise NamedProfileError(f'Unsupported ANIM version 0x{version:08X}')
    return resource_hash, askl_hash, version, track_count


def _bit(words: tuple[int, ...], index: int) -> int:
    w=index>>5; b=index&31
    if w >= len(words): return 0
    return (words[w] >> b) & 1


def _resolve_local_pointer(anim_data: bytes, token: int) -> Optional[int]:
    if token == 0: return None
    bitstream_token = _u32(anim_data, 0x44)
    return ANIM_HEADER_SIZE + (token - bitstream_token) * 4


def _find_special_key0_node(anim_data: bytes) -> Optional[int]:
    token = _u32(anim_data, 0x34)
    local = _resolve_local_pointer(anim_data, token)
    seen=set()
    while local is not None:
        if local in seen: raise NamedProfileError('ANIM special-data linked list cycle')
        seen.add(local)
        if local < 0 or local + 8 > len(anim_data):
            raise NamedProfileError('ANIM special-data pointer outside file')
        key=_u32(anim_data, local)
        if key == 0: return local
        next_token=_u32(anim_data, local+4)
        local=_resolve_local_pointer(anim_data,next_token) if next_token else None
    return None


def _read_sparse_ids(anim_data: bytes, count_off: int, ptr_off: int) -> tuple[int,...]:
    node=_find_special_key0_node(anim_data)
    if node is None: return ()
    count=_u32(anim_data,node+count_off)
    token=_u32(anim_data,node+ptr_off)
    if count == 0 or token == 0: return ()
    local=_resolve_local_pointer(anim_data,token)
    if local is None or local < 0 or local + count*4 > len(anim_data):
        raise NamedProfileError('ANIM sparse-ID table exceeds file')
    return struct.unpack_from('<'+'I'*count, anim_data, local)


def build_named_track_map(anim_data: bytes) -> list[NamedTrackRow]:
    resource_hash, askl_hash, _version, declared_tracks = inspect_anim_identity(anim_data)
    if not has_builtin_profile(askl_hash):
        raise NamedProfileError(
            f'ANIM expects ASKL 0x{askl_hash:08X}; no built-in named profile exists for that skeleton'
        )
    profile=load_profile_for_hash(askl_hash)
    counts=tuple(int(x) for x in profile['field_counts'])
    bases=tuple(int(x) for x in profile['validity_bit_bases'])
    presence=struct.unpack_from('<13I', anim_data, 0x48)
    reference=struct.unpack_from('<13I', anim_data, 0x7C)
    bones={int(b['index']):str(b['name']) for b in profile['bones']}
    pos=tuple(int(x) for x in profile['position_bone_map'])
    quat=tuple(int(x) for x in profile['quaternion_bone_map'])
    axis=tuple(int(x) for x in profile['axis1_bone_map'])
    error_ids=_read_sparse_ids(anim_data,0x08,0x0C)
    scale_ids=_read_sparse_ids(anim_data,0x30,0x34)
    compressed_elements=[]
    for field,(count,base) in enumerate(zip(counts,bases)):
        elems=[]
        for e in range(count):
            bit=base+e
            if _bit(reference,bit):
                continue
            if _bit(presence,bit):
                elems.append(e)
        compressed_elements.append(elems)

    rows=[]
    track=0
    for field, elems in enumerate(compressed_elements):
        width=COMPRESSED_WIDTH[field]
        if width == 0: continue
        for ordinal, element in enumerate(elems):
            bone_index: Optional[int]=None
            sparse_id: Optional[int]=None
            source='FIELD_ELEMENT'
            if field == 0 and element < len(pos):
                bone_index=pos[element]; source='ASKL_POSITION_MAP'
            elif field == 1 and element < len(quat):
                bone_index=quat[element]; source='ASKL_QUATERNION_MAP'
            elif field == 2 and element < len(axis):
                bone_index=axis[element]; source='ASKL_AXIS1_MAP'
            elif field == 3 and ordinal < len(error_ids):
                sparse_id=int(error_ids[ordinal]); bone_index=sparse_id; source='ANIM_FK_ERROR_SPECIAL_ID'
            elif field == 8 and ordinal < len(scale_ids):
                sparse_id=int(scale_ids[ordinal]); bone_index=sparse_id; source='ANIM_BONE_SCALE_SPECIAL_ID'
            if bone_index is not None:
                bone_name=bones.get(bone_index,f'Bone {bone_index}')
            elif field == 5:
                bone_name='Floor Offset'
            elif field == 6:
                bone_name='Camera FOV'
            elif field == 7:
                bone_name=f'Morph Slider {element}'
            else:
                bone_name=f'Element {element}'
            comps=COMPONENT_NAMES[field]
            if len(comps) != width:
                raise NamedProfileError(f'component width mismatch for {FIELD_NAMES[field]}')
            for ci,comp in enumerate(comps):
                rows.append(NamedTrackRow(
                    track_index=track,
                    field_index=field,
                    field_name=FIELD_NAMES[field],
                    element_index=element,
                    component_index=ci,
                    component_name=comp,
                    bone_index=bone_index,
                    bone_name=bone_name,
                    source=source,
                    sparse_id=sparse_id,
                ))
                track += 1
    if track != declared_tracks:
        raise NamedProfileError(
            f'Named profile 0x{askl_hash:08X} computed {track} tracks but ANIM declares {declared_tracks}'
        )
    return rows


def describe_track(anim_data: bytes, track_index: int) -> NamedTrackRow:
    rows=build_named_track_map(anim_data)
    if track_index < 0 or track_index >= len(rows):
        raise NamedProfileError(f'track {track_index} outside 0..{len(rows)-1}')
    return rows[track_index]


def export_named_track_map_csv(path: Path, rows: Iterable[NamedTrackRow]) -> None:
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields=['track_index','field_index','field_name','element_index','component_index','component_name','bone_index','bone_name','source','sparse_id']
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for row in rows: w.writerow(row.to_dict())


def export_named_track_map_json(path: Path, anim_data: bytes, rows: Iterable[NamedTrackRow]) -> None:
    resource_hash,askl_hash,version,track_count=inspect_anim_identity(anim_data)
    obj={
        'profile':profile_display_name(askl_hash),
        'resource_hash':f'0x{resource_hash:08X}',
        'askl_hash':f'0x{askl_hash:08X}',
        'anim_version':f'0x{version:08X}',
        'compressed_track_count':track_count,
        'tracks':[r.to_dict() for r in rows],
    }
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
