#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Optional

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


def _profile_path() -> Path:
    return Path(__file__).resolve().parent.parent / 'data' / 'ch_spiderman_0xCFB154CD_named_profile_v1.json'


def load_profile() -> dict[str, Any]:
    p = _profile_path()
    if not p.is_file():
        raise NamedProfileError(f'Built-in Spider-Man profile missing: {p}')
    obj = json.loads(p.read_text(encoding='utf-8'))
    if int(str(obj.get('resource_hash','0')), 0) != PROFILE_HASH:
        raise NamedProfileError('Built-in Spider-Man profile hash mismatch')
    if int(obj.get('bone_count',0)) != 85:
        raise NamedProfileError('Built-in Spider-Man profile bone count mismatch')
    return obj


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
    if askl_hash != PROFILE_HASH:
        raise NamedProfileError(
            f'ANIM expects ASKL 0x{askl_hash:08X}; built-in profile is only for 0x{PROFILE_HASH:08X} ch_spiderman'
        )
    profile=load_profile()
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
        raise NamedProfileError(f'Named track map computed {track} tracks but ANIM declares {declared_tracks}')
    return rows


def describe_track(anim_data: bytes, track_index: int) -> NamedTrackRow:
    rows=build_named_track_map(anim_data)
    if track_index < 0 or track_index >= len(rows):
        raise NamedProfileError(f'track {track_index} outside 0..{len(rows)-1}')
    return rows[track_index]


def export_named_track_map_csv(path: Path, rows: Iterable[NamedTrackRow]) -> None:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fields=['track_index','field_index','field_name','element_index','component_index','component_name','bone_index','bone_name','source','sparse_id']
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        for row in rows: w.writerow(row.to_dict())


def export_named_track_map_json(path: Path, anim_data: bytes, rows: Iterable[NamedTrackRow]) -> None:
    resource_hash,askl_hash,version,track_count=inspect_anim_identity(anim_data)
    obj={
        'profile':'0xCFB154CD ch_spiderman runtime named skeleton profile',
        'resource_hash':f'0x{resource_hash:08X}',
        'askl_hash':f'0x{askl_hash:08X}',
        'anim_version':f'0x{version:08X}',
        'compressed_track_count':track_count,
        'tracks':[r.to_dict() for r in rows],
    }
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
