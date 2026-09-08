#!/usr/bin/env python3
"""Temporary SM3 APKF resource-reference dump service.

This module is intentionally isolated from the normal release extraction path.
It can read one selected SM3 PC pack/APKF OR scan an entire PC pack folder and
write research CSVs beneath the Pack Extractor's existing CHOOSE OUTPUT folder.

Reverse-engineered APKF facts used here:
- APKF low-16 version 0x0107
- 0x18-byte component descriptors
- packed fixup target: component=value>>26, dword_offset=value&0x03FFFFFF
- pointer relocation stream terminated by 0xFFFFFFFF
- resource-reference fixup entries are 0x10 bytes and terminated by 0xFFFFFFFF
- resource-reference entry +04 = resource type, +08/+0C = NGLResourceKey name/hash
"""
from __future__ import annotations

import csv
import datetime as _dt
import shutil
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sm3_toolkit.services import pack_extract_service as pack_backend
from sm3_toolkit.services import apkf_clean_database_service as clean_db_backend

EXPECTED_VERSION_LOW16 = 0x0107
MAX_COMPONENTS = 63
MAX_GROUPS = 10000
MAX_FIXUPS = 20_000_000


class ReferenceDumpError(Exception):
    pass


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ReferenceDumpError(f"u32 outside APKF at 0x{off:X}")
    return struct.unpack_from('<I', data, off)[0]


def _i32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise ReferenceDumpError(f"i32 outside APKF at 0x{off:X}")
    return struct.unpack_from('<i', data, off)[0]


def _align4(v: int) -> int:
    return (v + 3) & ~3


def _hx(v: Optional[int], width: int = 8) -> str:
    if v is None:
        return ''
    return f"0x{v:0{width}X}"


def _fourcc(v: int) -> str:
    raw = struct.pack('<I', v)
    # Keep printable ASCII and strip trailing NUL/non-printable padding.
    chars = ''.join(chr(b) if 32 <= b <= 126 else '\x00' for b in raw)
    return chars.rstrip('\x00')


def _safe_cstr(data: bytes, off: int, max_len: int = 4096) -> Optional[str]:
    if off < 0 or off >= len(data):
        return None
    end = data.find(b'\x00', off, min(len(data), off + max_len))
    if end < 0:
        return None
    raw = data[off:end]
    if not raw:
        return ''
    printable = sum(32 <= b <= 126 or b == 9 for b in raw)
    if printable / max(1, len(raw)) < 0.85:
        return None
    return raw.decode('utf-8', errors='replace')


def _write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def _parse_components(payload: bytes) -> Tuple[List[Dict[str, Any]], int]:
    if len(payload) < 0x1C or payload[:4] != b'APKF':
        raise ReferenceDumpError('payload does not start with APKF')
    version = _u32(payload, 4) & 0xFFFF
    if version != EXPECTED_VERSION_LOW16:
        raise ReferenceDumpError(f'unexpected APKF version low16 0x{version:04X}')
    count = _u32(payload, 0x10)
    if count > MAX_COMPONENTS:
        raise ReferenceDumpError(f'component count {count} exceeds {MAX_COMPONENTS}')
    if count == 0:
        return [], 0

    table = 0x14 + _i32(payload, 0x14)
    if table < 0 or table + count * 0x18 > len(payload):
        raise ReferenceDumpError(f'component table outside APKF: 0x{table:X}')

    out: List[Dict[str, Any]] = []
    for i in range(count):
        d = table + i * 0x18
        typ = _u32(payload, d + 0x00)
        field04 = _u32(payload, d + 0x04)
        size = _u32(payload, d + 0x10)
        rel = _i32(payload, d + 0x14)
        data_base = d + 0x14 + rel
        if data_base < 0 or data_base > len(payload):
            raise ReferenceDumpError(f'component {i} data base outside APKF: 0x{data_base:X}')
        out.append({
            'index': i,
            'descriptor_offset': d,
            'type_u32': typ,
            'type': _fourcc(typ),
            'field04': field04,
            'field08': _u32(payload, d + 0x08),
            'field0c': _u32(payload, d + 0x0C),
            'data_size': size,
            'data_rel_raw': rel & 0xFFFFFFFF,
            'data_base': data_base,
            'used_for_fixup_end': (field04 & 0x02) == 0,
        })
    return out, table


def _parse_groups(payload: bytes, component_count: int) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    if component_count == 0:
        return [], None
    off = 0x1C
    stride = 0x14 + component_count * 4
    groups: List[Dict[str, Any]] = []
    special_base: Optional[int] = None

    for gi in range(MAX_GROUPS):
        if off + 4 > len(payload):
            raise ReferenceDumpError('resource-group table ran outside APKF')
        typ = _u32(payload, off)
        if typ == 0:
            return groups, special_base
        if off + stride > len(payload):
            raise ReferenceDumpError(f'resource group {gi} header outside APKF')

        slot_count = _u32(payload, off + 0x08)
        rel = _i32(payload, off + 0x0C)
        rec_count = _u32(payload, off + 0x10)
        if slot_count > MAX_COMPONENTS:
            raise ReferenceDumpError(f'group {gi} slot_count {slot_count} implausible')
        rec_base = off + 0x0C + rel
        rec_stride = (slot_count + 2) * 4
        rec_end = rec_base + rec_stride * rec_count
        if rec_count:
            if rec_base < 0 or rec_end > len(payload):
                raise ReferenceDumpError(f'group {gi} records outside APKF')
            # Mirrors piVar6 after the latest non-empty resource group.
            special_base = rec_end

        bindings: List[Dict[str, Any]] = []
        for component_index in range(component_count):
            raw_binding = _u32(payload, off + 0x14 + component_index * 4)
            bindings.append({
                'component_index': component_index,
                'raw': raw_binding,
                'slot_index': raw_binding >> 24,
                'alignment': raw_binding & 0x00FFFFFF,
            })

        groups.append({
            'index': gi,
            'group_offset': off,
            'type_u32': typ,
            'type': _fourcc(typ),
            'variant': _u32(payload, off + 0x04),
            'slot_count': slot_count,
            'records_rel_raw': rel & 0xFFFFFFFF,
            'records_base': rec_base,
            'record_count': rec_count,
            'record_stride': rec_stride,
            'records_end': rec_end,
            'bindings': bindings,
        })
        off += stride
    raise ReferenceDumpError('resource-group guard hit / terminator not found')


def _fixup_start(components: List[Dict[str, Any]]) -> int:
    last_end: Optional[int] = None
    for c in components:
        if c['used_for_fixup_end']:
            last_end = int(c['data_base']) + int(c['data_size'])
    if last_end is None:
        raise ReferenceDumpError('could not determine APKF fixup stream start')
    return _align4(last_end)


def _decode_target(payload: bytes, components: List[Dict[str, Any]], packed: int) -> Dict[str, Any]:
    ci = packed >> 26
    dw = packed & 0x03FFFFFF
    bo = dw * 4
    ctype = ''
    local = None
    if ci < len(components):
        c = components[ci]
        ctype = str(c['type'])
        candidate = int(c['data_base']) + bo
        if 0 <= candidate and candidate + 4 <= len(payload):
            local = candidate
    return {
        'target_component': ci,
        'target_component_type': ctype,
        'target_dword_offset': dw,
        'target_byte_offset': bo,
        'target_local_offset': local,
    }


def _parse_relocations(
    payload: bytes,
    cursor: int,
    components: List[Dict[str, Any]],
    special_base: Optional[int],
) -> Tuple[List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    for idx in range(MAX_FIXUPS):
        packed = _u32(payload, cursor)
        if packed == 0xFFFFFFFF:
            return rows, cursor + 4
        target = _decode_target(payload, components, packed)
        local = target['target_local_offset']
        serialized = _u32(payload, local) if local is not None else None
        source_component = None
        source_dw = None
        resolved_local = None
        if serialized is not None:
            source_component = serialized >> 26
            source_dw = serialized & 0x03FFFFFF
            if source_component == 0x3F:
                if special_base is not None:
                    candidate = special_base + source_dw * 4
                    if 0 <= candidate < len(payload):
                        resolved_local = candidate
            elif source_component < len(components):
                candidate = int(components[source_component]['data_base']) + source_dw * 4
                if 0 <= candidate < len(payload):
                    resolved_local = candidate
        rows.append({
            'reloc_index': idx,
            'stream_local_offset': cursor,
            'target_packed': packed,
            **target,
            'serialized_pointer_value': serialized,
            'source_component': source_component,
            'source_dword_offset': source_dw,
            'resolved_source_local_offset': resolved_local,
        })
        cursor += 4
    raise ReferenceDumpError('pointer-relocation guard hit / terminator not found')


def _parse_resource_fixups(
    payload: bytes,
    cursor: int,
    components: List[Dict[str, Any]],
    special_base: Optional[int],
) -> Tuple[List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    prev_type = None
    prev_hash = None

    for idx in range(MAX_FIXUPS):
        packed = _u32(payload, cursor)
        if packed == 0xFFFFFFFF:
            return rows, cursor + 4
        if cursor + 16 > len(payload):
            raise ReferenceDumpError('truncated resource-reference fixup entry')

        typ = _u32(payload, cursor + 4)
        name_ref = _u32(payload, cursor + 8)
        rhash = _u32(payload, cursor + 12)
        target = _decode_target(payload, components, packed)
        local = target['target_local_offset']
        serialized_target = _u32(payload, local) if local is not None else None

        tagged = bool(name_ref & 1)
        name_local = None
        name = None
        if name_ref == 0:
            name = ''
        elif tagged and special_base is not None:
            candidate = special_base + (name_ref & 0xFFFFFFFE)
            if 0 <= candidate < len(payload):
                name_local = candidate
                name = _safe_cstr(payload, candidate)

        rows.append({
            'fixup_index': idx,
            'stream_local_offset': cursor,
            'target_packed': packed,
            **target,
            'serialized_target_value': serialized_target,
            'resource_type_u32': typ,
            'resource_type': _fourcc(typ),
            'resource_hash': rhash,
            'name_ref_raw': name_ref,
            'name_is_tagged_relative': tagged,
            'name_local_offset': name_local,
            'resource_name': '' if name is None else name,
            'duplicate_type_hash_of_previous': prev_type == typ and prev_hash == rhash,
        })
        prev_type = typ
        prev_hash = rhash
        cursor += 16
    raise ReferenceDumpError('resource-reference guard hit / terminator not found')



def _align_cursor(value: int, alignment: int) -> int:
    if alignment <= 1:
        return value
    return ((value + alignment - 1) & ~(alignment - 1))


def _reconstruct_resource_records(
    payload: bytes,
    components: List[Dict[str, Any]],
    groups: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Replay APKF_FixupAndInitialize's resource-record component allocation."""
    cursors = [0 for _ in components]
    records: List[Dict[str, Any]] = []
    record_components: List[Dict[str, Any]] = []

    for g in groups:
        slot_count = int(g['slot_count'])
        rec_stride = int(g['record_stride'])
        rec_base = int(g['records_base'])
        bindings = list(g.get('bindings') or [])

        for record_index in range(int(g['record_count'])):
            roff = rec_base + record_index * rec_stride
            name_ref_raw = _u32(payload, roff + 0x00)
            resource_hash = _u32(payload, roff + 0x04)

            name_local = None
            resource_name = ''
            if name_ref_raw != 0:
                signed_name_rel = _i32(payload, roff + 0x00)
                candidate = roff + signed_name_rel
                if 0 <= candidate < len(payload):
                    name_local = candidate
                    decoded = _safe_cstr(payload, candidate)
                    if decoded is not None:
                        resource_name = decoded

            slot_values = [_u32(payload, roff + 0x08 + i * 4) for i in range(slot_count)]

            records.append({
                'group_index': g['index'],
                'group_type': g['type'],
                'group_type_u32': g['type_u32'],
                'group_variant': g['variant'],
                'record_index': record_index,
                'record_local_offset': roff,
                'name_ref_raw': name_ref_raw,
                'name_local_offset': name_local,
                'resource_name': resource_name,
                'resource_hash': resource_hash,
                'slot_values_raw': slot_values,
            })

            for ci, comp in enumerate(components):
                if ci >= len(bindings):
                    continue
                binding = bindings[ci]
                slot_index = int(binding['slot_index'])
                alignment = int(binding['alignment'])

                if slot_index == 0xFF:
                    continue
                if slot_index >= slot_count:
                    record_components.append({
                        'group_index': g['index'],
                        'group_type': g['type'],
                        'group_variant': g['variant'],
                        'record_index': record_index,
                        'record_local_offset': roff,
                        'resource_name': resource_name,
                        'resource_hash': resource_hash,
                        'component_index': ci,
                        'component_type': comp['type'],
                        'binding_raw': binding['raw'],
                        'slot_index': slot_index,
                        'alignment': alignment,
                        'serialized_size': None,
                        'component_cursor_before': cursors[ci],
                        'component_cursor_aligned': None,
                        'runtime_data_local_offset': None,
                        'runtime_data_end_local_offset': None,
                        'status': 'BAD_SLOT_INDEX',
                    })
                    continue

                serialized_size = slot_values[slot_index]
                cursor_before = cursors[ci]
                aligned_cursor = _align_cursor(cursor_before, alignment)
                data_local = int(comp['data_base']) + aligned_cursor
                data_end = data_local + serialized_size
                cursors[ci] = aligned_cursor + serialized_size

                record_components.append({
                    'group_index': g['index'],
                    'group_type': g['type'],
                    'group_variant': g['variant'],
                    'record_index': record_index,
                    'record_local_offset': roff,
                    'resource_name': resource_name,
                    'resource_hash': resource_hash,
                    'component_index': ci,
                    'component_type': comp['type'],
                    'binding_raw': binding['raw'],
                    'slot_index': slot_index,
                    'alignment': alignment,
                    'serialized_size': serialized_size,
                    'component_cursor_before': cursor_before,
                    'component_cursor_aligned': aligned_cursor,
                    'runtime_data_local_offset': data_local,
                    'runtime_data_end_local_offset': data_end,
                    'status': 'OK',
                })

    return records, record_components


def _find_resource_for_pointer(
    local_offset: Optional[int],
    record_components: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if local_offset is None:
        return None

    for rc in record_components:
        start = rc.get('runtime_data_local_offset')
        if start is not None and int(start) == int(local_offset):
            result = dict(rc)
            result['match_kind'] = 'EXACT_START'
            result['offset_into_resource'] = 0
            return result

    for rc in record_components:
        start = rc.get('runtime_data_local_offset')
        end = rc.get('runtime_data_end_local_offset')
        if start is None or end is None:
            continue
        if int(start) <= int(local_offset) < int(end):
            result = dict(rc)
            result['match_kind'] = 'INSIDE'
            result['offset_into_resource'] = int(local_offset) - int(start)
            return result
    return None


def _resolve_internal_pointer_relocations(
    relocations: List[Dict[str, Any]],
    record_components: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Join pointer relocation fields to source-resource and resolved-resource identities."""
    out: List[Dict[str, Any]] = []
    for r in relocations:
        target_owner = _find_resource_for_pointer(r.get('target_local_offset'), record_components)
        resolved_owner = _find_resource_for_pointer(r.get('resolved_source_local_offset'), record_components)

        row = {
            **r,
            'source_resource_group_type': '',
            'source_resource_group_variant': '',
            'source_resource_record_index': '',
            'source_resource_name': '',
            'source_resource_hash': None,
            'source_resource_component_type': '',
            'source_resource_data_local_offset': None,
            'source_resource_offset_of_field': None,
            'resolved_resource_group_type': '',
            'resolved_resource_group_variant': '',
            'resolved_resource_record_index': '',
            'resolved_resource_name': '',
            'resolved_resource_hash': None,
            'resolved_resource_component_type': '',
            'resolved_resource_data_local_offset': None,
            'resolved_resource_size': None,
            'resolved_match_kind': '',
            'resolved_offset_into_resource': None,
        }

        if target_owner is not None:
            row.update({
                'source_resource_group_type': target_owner.get('group_type', ''),
                'source_resource_group_variant': target_owner.get('group_variant', ''),
                'source_resource_record_index': target_owner.get('record_index', ''),
                'source_resource_name': target_owner.get('resource_name', ''),
                'source_resource_hash': target_owner.get('resource_hash'),
                'source_resource_component_type': target_owner.get('component_type', ''),
                'source_resource_data_local_offset': target_owner.get('runtime_data_local_offset'),
                'source_resource_offset_of_field':
                    int(r['target_local_offset']) - int(target_owner['runtime_data_local_offset'])
                    if r.get('target_local_offset') is not None and target_owner.get('runtime_data_local_offset') is not None
                    else None,
            })

        if resolved_owner is not None:
            row.update({
                'resolved_resource_group_type': resolved_owner.get('group_type', ''),
                'resolved_resource_group_variant': resolved_owner.get('group_variant', ''),
                'resolved_resource_record_index': resolved_owner.get('record_index', ''),
                'resolved_resource_name': resolved_owner.get('resource_name', ''),
                'resolved_resource_hash': resolved_owner.get('resource_hash'),
                'resolved_resource_component_type': resolved_owner.get('component_type', ''),
                'resolved_resource_data_local_offset': resolved_owner.get('runtime_data_local_offset'),
                'resolved_resource_size': resolved_owner.get('serialized_size'),
                'resolved_match_kind': resolved_owner.get('match_kind', ''),
                'resolved_offset_into_resource': resolved_owner.get('offset_into_resource'),
            })

        out.append(row)
    return out


def _common_owner(pack_path: Path, source_slice: pack_backend.APKFSourceSlice, archive_index: int) -> Dict[str, Any]:
    return {
        'source_pack': pack_path.name,
        'source_pack_path': str(pack_path),
        'archive_index': archive_index,
        'source_archive': source_slice.archive_folder,
        'source_archive_kind': source_slice.source_kind,
        'source_apkf_label': source_slice.label,
        'source_apkf_absolute_base': _hx(source_slice.absolute_base),
        'parent_outer_index': '' if source_slice.parent_outer_index is None else source_slice.parent_outer_index,
        'parent_outer_hash': '' if source_slice.parent_outer_hash is None else _hx(source_slice.parent_outer_hash),
        'parent_outer_type': '' if source_slice.parent_outer_type is None else _hx(source_slice.parent_outer_type),
    }


def dump_selected_pack_references(
    pack_path: Path,
    out_dir: Path,
    *,
    log=print,
) -> Dict[str, Any]:
    """Dump APKF relocation/resource-reference data for ONE selected pack.

    IMPORTANT UI contract: all files are written below *out_dir*, which is the
    Pack Extractor's existing CHOOSE OUTPUT folder. Nothing is written next to
    the game pack unless the user deliberately chose that location as output.
    """
    pack_path = Path(pack_path)
    out_dir = Path(out_dir)
    if not pack_path.exists() or not pack_path.is_file():
        raise ValueError(f'Input pack does not exist: {pack_path}')

    out_dir.mkdir(parents=True, exist_ok=True)
    dump_root = out_dir / f'TEMP_APKF_REFERENCE_DUMP_{pack_path.stem}'
    if dump_root.exists():
        shutil.rmtree(dump_root, ignore_errors=True)
    dump_root.mkdir(parents=True, exist_ok=True)

    log(f'[TEMP APKF REF] Input pack: {pack_path}')
    log(f'[TEMP APKF REF] CHOOSE OUTPUT root: {out_dir}')
    log(f'[TEMP APKF REF] Actual output folder: {dump_root}')

    data = pack_path.read_bytes()
    probe = pack_backend.probe_pack_bytes(pack_path.name, data)
    slices, filtered = pack_backend.apkf_slices_from_probe(data, probe)

    # Direct .APKF input fallback.
    if not slices and data[:4] == b'APKF':
        slices = [pack_backend.APKFSourceSlice(
            label='direct_apkf',
            absolute_base=0,
            payload=data,
            route_reason='direct_apkf_input',
            source_kind='direct_apkf',
        )]

    if not slices:
        raise ReferenceDumpError('No valid APKF archive slices were discovered in the selected pack.')

    package_rows: List[Dict[str, Any]] = []
    component_rows: List[Dict[str, Any]] = []
    group_rows: List[Dict[str, Any]] = []
    group_binding_rows: List[Dict[str, Any]] = []
    resource_record_rows: List[Dict[str, Any]] = []
    resource_component_rows: List[Dict[str, Any]] = []
    relocation_rows: List[Dict[str, Any]] = []
    internal_pointer_rows: List[Dict[str, Any]] = []
    ref_rows: List[Dict[str, Any]] = []
    error_rows: List[Dict[str, Any]] = []

    for ai, source_slice in enumerate(slices):
        owner = _common_owner(pack_path, source_slice, ai)
        payload = source_slice.payload
        log(f"[TEMP APKF REF {ai+1}/{len(slices)}] {source_slice.archive_folder} @ {_hx(source_slice.absolute_base)}")
        try:
            version = _u32(payload, 4) & 0xFFFF
            raw_flags = _u32(payload, 8)
            components, comp_table = _parse_components(payload)
            groups, special_base = _parse_groups(payload, len(components))
            records, record_components = _reconstruct_resource_records(payload, components, groups)
            if components:
                reloc_start = _fixup_start(components)
                relocations, ref_start = _parse_relocations(payload, reloc_start, components, special_base)
                refs, ref_end = _parse_resource_fixups(payload, ref_start, components, special_base)
                internal_links = _resolve_internal_pointer_relocations(relocations, record_components)
            else:
                reloc_start = None
                ref_start = None
                ref_end = None
                relocations = []
                refs = []
                internal_links = []

            package_rows.append({
                **owner,
                'payload_size': len(payload),
                'version_low16': _hx(version, 4),
                'raw_flags': _hx(raw_flags),
                'component_count': len(components),
                'component_table_local_offset': _hx(comp_table if components else None),
                'resource_group_count': len(groups),
                'special_base_local_offset': _hx(special_base),
                'pointer_relocation_stream_local_offset': _hx(reloc_start),
                'resource_reference_stream_local_offset': _hx(ref_start),
                'pointer_relocation_count': len(relocations),
                'resource_reference_count': len(refs),
                'status': 'OK',
                'error': '',
            })

            for c in components:
                component_rows.append({
                    **owner,
                    'component_index': c['index'],
                    'descriptor_local_offset': _hx(c['descriptor_offset']),
                    'descriptor_absolute_pack_offset': _hx(source_slice.absolute_base + c['descriptor_offset']),
                    'type': c['type'],
                    'type_u32': _hx(c['type_u32']),
                    'field04': _hx(c['field04']),
                    'field08': _hx(c['field08']),
                    'field0c': _hx(c['field0c']),
                    'data_size': _hx(c['data_size']),
                    'data_rel_raw': _hx(c['data_rel_raw']),
                    'data_base_local_offset': _hx(c['data_base']),
                    'data_base_absolute_pack_offset': _hx(source_slice.absolute_base + c['data_base']),
                    'used_for_fixup_end': int(c['used_for_fixup_end']),
                })

            for g in groups:
                group_rows.append({
                    **owner,
                    'group_index': g['index'],
                    'group_local_offset': _hx(g['group_offset']),
                    'group_absolute_pack_offset': _hx(source_slice.absolute_base + g['group_offset']),
                    'type': g['type'],
                    'type_u32': _hx(g['type_u32']),
                    'variant': g['variant'],
                    'slot_count': g['slot_count'],
                    'records_rel_raw': _hx(g['records_rel_raw']),
                    'records_base_local_offset': _hx(g['records_base']),
                    'record_count': g['record_count'],
                    'record_stride': _hx(g['record_stride']),
                    'records_end_local_offset': _hx(g['records_end']),
                })

            for g in groups:
                for b in g.get('bindings') or []:
                    ci = int(b['component_index'])
                    comp_type = components[ci]['type'] if 0 <= ci < len(components) else ''
                    group_binding_rows.append({
                        **owner,
                        'group_index': g['index'],
                        'group_type': g['type'],
                        'group_variant': g['variant'],
                        'component_index': ci,
                        'component_type': comp_type,
                        'binding_raw': _hx(b['raw']),
                        'slot_index': b['slot_index'],
                        'alignment': _hx(b['alignment']),
                    })

            for rr in records:
                name_local = rr['name_local_offset']
                resource_record_rows.append({
                    **owner,
                    'group_index': rr['group_index'],
                    'group_type': rr['group_type'],
                    'group_type_u32': _hx(rr['group_type_u32']),
                    'group_variant': rr['group_variant'],
                    'record_index': rr['record_index'],
                    'record_local_offset': _hx(rr['record_local_offset']),
                    'record_absolute_pack_offset': _hx(source_slice.absolute_base + rr['record_local_offset']),
                    'name_ref_raw': _hx(rr['name_ref_raw']),
                    'name_local_offset': _hx(name_local),
                    'name_absolute_pack_offset': _hx(source_slice.absolute_base + name_local) if name_local is not None else '',
                    'resource_name': rr['resource_name'],
                    'resource_hash': _hx(rr['resource_hash']),
                    'slot_values_raw': ';'.join(_hx(v) for v in rr['slot_values_raw']),
                })

            for rc in record_components:
                data_local = rc['runtime_data_local_offset']
                data_end = rc['runtime_data_end_local_offset']
                resource_component_rows.append({
                    **owner,
                    'group_index': rc['group_index'],
                    'group_type': rc['group_type'],
                    'group_variant': rc['group_variant'],
                    'record_index': rc['record_index'],
                    'record_local_offset': _hx(rc['record_local_offset']),
                    'resource_name': rc['resource_name'],
                    'resource_hash': _hx(rc['resource_hash']),
                    'component_index': rc['component_index'],
                    'component_type': rc['component_type'],
                    'binding_raw': _hx(rc['binding_raw']),
                    'slot_index': rc['slot_index'],
                    'alignment': _hx(rc['alignment']),
                    'serialized_size': _hx(rc['serialized_size']),
                    'component_cursor_before': _hx(rc['component_cursor_before']),
                    'component_cursor_aligned': _hx(rc['component_cursor_aligned']),
                    'runtime_data_local_offset': _hx(data_local),
                    'runtime_data_absolute_pack_offset': _hx(source_slice.absolute_base + data_local) if data_local is not None else '',
                    'runtime_data_end_local_offset': _hx(data_end),
                    'runtime_data_end_absolute_pack_offset': _hx(source_slice.absolute_base + data_end) if data_end is not None else '',
                    'status': rc['status'],
                })

            for r in relocations:
                local = r['target_local_offset']
                resolved_local = r['resolved_source_local_offset']
                relocation_rows.append({
                    **owner,
                    'reloc_index': r['reloc_index'],
                    'stream_local_offset': _hx(r['stream_local_offset']),
                    'stream_absolute_pack_offset': _hx(source_slice.absolute_base + r['stream_local_offset']),
                    'target_packed': _hx(r['target_packed']),
                    'target_component': r['target_component'],
                    'target_component_type': r['target_component_type'],
                    'target_dword_offset': _hx(r['target_dword_offset']),
                    'target_byte_offset': _hx(r['target_byte_offset']),
                    'target_local_offset': _hx(local),
                    'target_absolute_pack_offset': _hx(source_slice.absolute_base + local) if local is not None else '',
                    'serialized_pointer_value': _hx(r['serialized_pointer_value']),
                    'source_component': '' if r['source_component'] is None else r['source_component'],
                    'source_dword_offset': _hx(r['source_dword_offset']),
                    'resolved_source_local_offset': _hx(resolved_local),
                    'resolved_source_absolute_pack_offset': _hx(source_slice.absolute_base + resolved_local) if resolved_local is not None else '',
                })

            for r in internal_links:
                local = r['target_local_offset']
                resolved_local = r['resolved_source_local_offset']
                src_data_local = r.get('source_resource_data_local_offset')
                dst_data_local = r.get('resolved_resource_data_local_offset')
                internal_pointer_rows.append({
                    **owner,
                    'reloc_index': r['reloc_index'],
                    'stream_local_offset': _hx(r['stream_local_offset']),
                    'stream_absolute_pack_offset': _hx(source_slice.absolute_base + r['stream_local_offset']),
                    'target_packed': _hx(r['target_packed']),
                    'target_component': r['target_component'],
                    'target_component_type': r['target_component_type'],
                    'target_dword_offset': _hx(r['target_dword_offset']),
                    'target_byte_offset': _hx(r['target_byte_offset']),
                    'target_local_offset': _hx(local),
                    'target_absolute_pack_offset': _hx(source_slice.absolute_base + local) if local is not None else '',
                    'serialized_pointer_value': _hx(r['serialized_pointer_value']),
                    'source_component': '' if r['source_component'] is None else r['source_component'],
                    'source_dword_offset': _hx(r['source_dword_offset']),
                    'resolved_source_local_offset': _hx(resolved_local),
                    'resolved_source_absolute_pack_offset': _hx(source_slice.absolute_base + resolved_local) if resolved_local is not None else '',
                    'source_resource_group_type': r.get('source_resource_group_type',''),
                    'source_resource_group_variant': r.get('source_resource_group_variant',''),
                    'source_resource_record_index': r.get('source_resource_record_index',''),
                    'source_resource_name': r.get('source_resource_name',''),
                    'source_resource_hash': _hx(r.get('source_resource_hash')),
                    'source_resource_component_type': r.get('source_resource_component_type',''),
                    'source_resource_data_local_offset': _hx(src_data_local),
                    'source_resource_data_absolute_pack_offset': _hx(source_slice.absolute_base + src_data_local) if src_data_local is not None else '',
                    'source_resource_offset_of_field': _hx(r.get('source_resource_offset_of_field')),
                    'resolved_resource_group_type': r.get('resolved_resource_group_type',''),
                    'resolved_resource_group_variant': r.get('resolved_resource_group_variant',''),
                    'resolved_resource_record_index': r.get('resolved_resource_record_index',''),
                    'resolved_resource_name': r.get('resolved_resource_name',''),
                    'resolved_resource_hash': _hx(r.get('resolved_resource_hash')),
                    'resolved_resource_component_type': r.get('resolved_resource_component_type',''),
                    'resolved_resource_data_local_offset': _hx(dst_data_local),
                    'resolved_resource_data_absolute_pack_offset': _hx(source_slice.absolute_base + dst_data_local) if dst_data_local is not None else '',
                    'resolved_resource_size': _hx(r.get('resolved_resource_size')),
                    'resolved_match_kind': r.get('resolved_match_kind',''),
                    'resolved_offset_into_resource': _hx(r.get('resolved_offset_into_resource')),
                })

            for r in refs:
                local = r['target_local_offset']
                name_local = r['name_local_offset']
                ref_rows.append({
                    **owner,
                    'fixup_index': r['fixup_index'],
                    'stream_local_offset': _hx(r['stream_local_offset']),
                    'stream_absolute_pack_offset': _hx(source_slice.absolute_base + r['stream_local_offset']),
                    'target_packed': _hx(r['target_packed']),
                    'target_component': r['target_component'],
                    'target_component_type': r['target_component_type'],
                    'target_dword_offset': _hx(r['target_dword_offset']),
                    'target_byte_offset': _hx(r['target_byte_offset']),
                    'target_local_offset': _hx(local),
                    'target_absolute_pack_offset': _hx(source_slice.absolute_base + local) if local is not None else '',
                    'serialized_target_value': _hx(r['serialized_target_value']),
                    'resource_type': r['resource_type'],
                    'resource_type_u32': _hx(r['resource_type_u32']),
                    'resource_hash': _hx(r['resource_hash']),
                    'name_ref_raw': _hx(r['name_ref_raw']),
                    'name_is_tagged_relative': int(r['name_is_tagged_relative']),
                    'name_local_offset': _hx(name_local),
                    'name_absolute_pack_offset': _hx(source_slice.absolute_base + name_local) if name_local is not None else '',
                    'resource_name': r['resource_name'],
                    'duplicate_type_hash_of_previous': int(r['duplicate_type_hash_of_previous']),
                })

            log(f"[TEMP APKF REF] {source_slice.archive_folder}: reloc={len(relocations)} refs={len(refs)}")
        except Exception as exc:
            error_rows.append({**owner, 'error': f'{type(exc).__name__}: {exc}'})
            package_rows.append({
                **owner,
                'payload_size': len(payload),
                'version_low16': '',
                'raw_flags': '',
                'component_count': '',
                'component_table_local_offset': '',
                'resource_group_count': '',
                'special_base_local_offset': '',
                'pointer_relocation_stream_local_offset': '',
                'resource_reference_stream_local_offset': '',
                'pointer_relocation_count': '',
                'resource_reference_count': '',
                'status': 'ERROR',
                'error': f'{type(exc).__name__}: {exc}',
            })
            log(f"[TEMP APKF REF] ERROR {source_slice.archive_folder}: {exc}")

    owner_fields = [
        'source_pack','source_pack_path','archive_index','source_archive','source_archive_kind',
        'source_apkf_label','source_apkf_absolute_base','parent_outer_index','parent_outer_hash','parent_outer_type',
    ]
    package_fields = owner_fields + [
        'payload_size','version_low16','raw_flags','component_count','component_table_local_offset',
        'resource_group_count','special_base_local_offset','pointer_relocation_stream_local_offset',
        'resource_reference_stream_local_offset','pointer_relocation_count','resource_reference_count','status','error',
    ]
    component_fields = owner_fields + [
        'component_index','descriptor_local_offset','descriptor_absolute_pack_offset','type','type_u32',
        'field04','field08','field0c','data_size','data_rel_raw','data_base_local_offset',
        'data_base_absolute_pack_offset','used_for_fixup_end',
    ]
    group_fields = owner_fields + [
        'group_index','group_local_offset','group_absolute_pack_offset','type','type_u32','variant','slot_count',
        'records_rel_raw','records_base_local_offset','record_count','record_stride','records_end_local_offset',
    ]
    group_binding_fields = owner_fields + [
        'group_index','group_type','group_variant','component_index','component_type',
        'binding_raw','slot_index','alignment',
    ]
    resource_record_fields = owner_fields + [
        'group_index','group_type','group_type_u32','group_variant','record_index',
        'record_local_offset','record_absolute_pack_offset','name_ref_raw','name_local_offset',
        'name_absolute_pack_offset','resource_name','resource_hash','slot_values_raw',
    ]
    resource_component_fields = owner_fields + [
        'group_index','group_type','group_variant','record_index','record_local_offset',
        'resource_name','resource_hash','component_index','component_type','binding_raw',
        'slot_index','alignment','serialized_size','component_cursor_before',
        'component_cursor_aligned','runtime_data_local_offset','runtime_data_absolute_pack_offset',
        'runtime_data_end_local_offset','runtime_data_end_absolute_pack_offset','status',
    ]
    relocation_fields = owner_fields + [
        'reloc_index','stream_local_offset','stream_absolute_pack_offset','target_packed','target_component',
        'target_component_type','target_dword_offset','target_byte_offset','target_local_offset',
        'target_absolute_pack_offset','serialized_pointer_value','source_component','source_dword_offset',
        'resolved_source_local_offset','resolved_source_absolute_pack_offset',
    ]
    internal_pointer_fields = owner_fields + [
        'reloc_index','stream_local_offset','stream_absolute_pack_offset','target_packed','target_component',
        'target_component_type','target_dword_offset','target_byte_offset','target_local_offset',
        'target_absolute_pack_offset','serialized_pointer_value','source_component','source_dword_offset',
        'resolved_source_local_offset','resolved_source_absolute_pack_offset',
        'source_resource_group_type','source_resource_group_variant','source_resource_record_index',
        'source_resource_name','source_resource_hash','source_resource_component_type',
        'source_resource_data_local_offset','source_resource_data_absolute_pack_offset',
        'source_resource_offset_of_field',
        'resolved_resource_group_type','resolved_resource_group_variant','resolved_resource_record_index',
        'resolved_resource_name','resolved_resource_hash','resolved_resource_component_type',
        'resolved_resource_data_local_offset','resolved_resource_data_absolute_pack_offset',
        'resolved_resource_size','resolved_match_kind','resolved_offset_into_resource',
    ]
    ref_fields = owner_fields + [
        'fixup_index','stream_local_offset','stream_absolute_pack_offset','target_packed','target_component',
        'target_component_type','target_dword_offset','target_byte_offset','target_local_offset',
        'target_absolute_pack_offset','serialized_target_value','resource_type','resource_type_u32','resource_hash',
        'name_ref_raw','name_is_tagged_relative','name_local_offset','name_absolute_pack_offset','resource_name',
        'duplicate_type_hash_of_previous',
    ]

    _write_csv(dump_root / 'APKF_PACKAGES.csv', package_rows, package_fields)
    _write_csv(dump_root / 'COMPONENTS.csv', component_rows, component_fields)
    _write_csv(dump_root / 'RESOURCE_GROUPS.csv', group_rows, group_fields)
    _write_csv(dump_root / 'RESOURCE_GROUP_BINDINGS.csv', group_binding_rows, group_binding_fields)
    _write_csv(dump_root / 'RESOURCE_RECORDS.csv', resource_record_rows, resource_record_fields)
    _write_csv(dump_root / 'RESOURCE_RECORD_COMPONENTS.csv', resource_component_rows, resource_component_fields)
    _write_csv(dump_root / 'POINTER_RELOCATIONS.csv', relocation_rows, relocation_fields)
    _write_csv(dump_root / 'INTERNAL_RESOURCE_POINTER_FIXUPS.csv', internal_pointer_rows, internal_pointer_fields)
    _write_csv(dump_root / 'RESOURCE_REFERENCE_FIXUPS.csv', ref_rows, ref_fields)
    _write_csv(dump_root / 'APKF_REFERENCE_ERRORS.csv', error_rows, owner_fields + ['error'])

    mat_rows = [r for r in ref_rows if str(r.get('resource_type') or '').upper() == 'MAT']
    tex_rows = [r for r in ref_rows if str(r.get('resource_type') or '').upper() == 'TEX']
    mesh_rows = [r for r in ref_rows if str(r.get('resource_type') or '').upper() == 'MESH']
    _write_csv(dump_root / 'MAT_REFERENCES.csv', mat_rows, ref_fields)
    _write_csv(dump_root / 'TEX_REFERENCES.csv', tex_rows, ref_fields)
    _write_csv(dump_root / 'MESH_REFERENCES.csv', mesh_rows, ref_fields)

    known_serialized = {
        '0X00000028','0X000000CC','0X000003CC','0X000004B8','0X000004E4','0X00000560'
    }

    # v5.2.112 correction:
    # CH_SPIDERMAN's MATs are INTERNAL resources in the same APKF, so MESH->MAT
    # material pointers are normal APKF pointer relocations, not outer-resource
    # reference fixups. Resolve those relocations directly to MAT resource records.
    internal_mat_rows = [
        r for r in internal_pointer_rows
        if str(r.get('resolved_resource_group_type') or '').upper() == 'MAT'
    ]
    mesh_to_mat_rows = [
        r for r in internal_mat_rows
        if str(r.get('source_resource_group_type') or '').upper() == 'MESH'
    ]
    candidates = [
        r for r in mesh_to_mat_rows
        if str(r.get('serialized_pointer_value') or '').upper() in known_serialized
    ]

    _write_csv(dump_root / 'INTERNAL_MAT_POINTERS.csv', internal_mat_rows, internal_pointer_fields)
    _write_csv(dump_root / 'MESH_TO_MAT_INTERNAL_POINTERS.csv', mesh_to_mat_rows, internal_pointer_fields)
    _write_csv(dump_root / 'SPIDERMAN_MAT_MATCH_CANDIDATES.csv', candidates, internal_pointer_fields)
    _write_csv(dump_root / 'SPIDERMAN_INTERNAL_MAT_MATCH_CANDIDATES.csv', candidates, internal_pointer_fields)

    filtered_rows = []
    for f in filtered:
        filtered_rows.append({
            'source_pack': pack_path.name,
            'label': f.get('label',''),
            'absolute_base': f.get('absolute_base',''),
            'reason': f.get('reason',''),
            'detail': f.get('detail',''),
        })
    _write_csv(dump_root / 'FILTERED_APKF_MARKERS.csv', filtered_rows, ['source_pack','label','absolute_base','reason','detail'])

    summary_lines = [
        'SM3 TEMPORARY APKF REFERENCE DUMP',
        '=================================',
        '',
        f'Input pack: {pack_path}',
        f'CHOOSE OUTPUT root: {out_dir}',
        f'Actual output folder: {dump_root}',
        '',
        f'APKF archives discovered: {len(slices)}',
        f'APKF archives with parse errors: {len(error_rows)}',
        f'Pointer relocations: {len(relocation_rows)}',
        f'Internal pointer links resolved to resources: {sum(1 for r in internal_pointer_rows if r.get("resolved_resource_group_type"))}',
        f'Internal pointers resolving to MAT: {len(internal_mat_rows)}',
        f'MESH -> internal MAT pointer rows: {len(mesh_to_mat_rows)}',
        f'Resource-reference fixups: {len(ref_rows)}',
        f'External MAT references: {len(mat_rows)}',
        f'External TEX references: {len(tex_rows)}',
        f'External MESH references: {len(mesh_rows)}',
        f'Spider-Man known serialized MAT candidate rows: {len(candidates)}',
        '',
        'OPEN THESE FIRST:',
        '  SPIDERMAN_MAT_MATCH_CANDIDATES.csv',
        '  MESH_TO_MAT_INTERNAL_POINTERS.csv',
        '  RESOURCE_RECORDS.csv',
        '  SUMMARY.txt',
        '',
        'Known serialized material-field values being highlighted:',
        '  0x00000028',
        '  0x000000CC',
        '  0x000003CC',
        '  0x000004B8',
        '  0x000004E4',
        '  0x00000560',
        '',
        'v5.2.112 IMPORTANT:',
        '  CH_SPIDERMAN stores MAT resources internally in the same APKF.',
        '  MESH material links therefore resolve through APKF pointer relocations.',
        '',
        'The critical relationship is now:',
        '  MESH field serialized_pointer_value',
        '      -> resolved MAT IMG data pointer',
        '      -> MAT resource record',
        '      -> REAL MAT hash + name',
        '',
        'This is a TEMPORARY research mode. It does not modify the selected game pack.',
    ]
    (dump_root / 'SUMMARY.txt').write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')
    (dump_root / 'README_TEMP_APKF_REFERENCE_DUMP.txt').write_text(
        'TEMP APKF REFERENCE DUMP\n'
        '========================\n\n'
        'This folder was written under the Pack Extractor CHOOSE OUTPUT folder.\n'
        'It is a research-only dump of APKF pointer relocations, internal resource records, and external reference fixups.\n\n'
        'v5.2.112 resolves normal APKF pointer relocations back to internal MAT resource records.\n'
        'Use SPIDERMAN_MAT_MATCH_CANDIDATES.csv first, then MESH_TO_MAT_INTERNAL_POINTERS.csv.\n'
        'No input pack bytes are modified.\n',
        encoding='utf-8',
    )

    # Easy-to-find breadcrumb directly in the user-selected output root.
    (out_dir / 'TEMP_APKF_REFERENCE_DUMP_LATEST.txt').write_text(
        f'Input pack: {pack_path}\nLatest dump: {dump_root}\n',
        encoding='utf-8',
    )

    log(f'[TEMP APKF REF] DONE external_refs={len(ref_rows)} internal_MAT={len(internal_mat_rows)} MESH_to_MAT={len(mesh_to_mat_rows)} candidates={len(candidates)}')
    log(f'[TEMP APKF REF] OUTPUT: {dump_root}')
    return {
        'output_root': str(dump_root),
        'chosen_output_root': str(out_dir),
        'input_pack': str(pack_path),
        'apkf_archives': len(slices),
        'archive_errors': len(error_rows),
        'pointer_relocations': len(relocation_rows),
        'resource_references': len(ref_rows),
        'mat_references': len(mat_rows),
        'tex_references': len(tex_rows),
        'mesh_references': len(mesh_rows),
        'internal_mat_pointers': len(internal_mat_rows),
        'mesh_to_internal_mat_pointers': len(mesh_to_mat_rows),
        'spiderman_mat_candidates': len(candidates),
    }

# -----------------------------------------------------------------------------
# v5.2.116 TEMP CLEAN FULL APKF + RESOURCE DATABASE SCAN
# -----------------------------------------------------------------------------
FULL_SCAN_SUFFIXES = {'.pcpack', '.pcapk', '.apkf'}
FULL_SCAN_MASTER_FILES = [
    'APKF_PACKAGES.csv',
    'APKF_REFERENCE_ERRORS.csv',
    'COMPONENTS.csv',
    'RESOURCE_GROUPS.csv',
    'RESOURCE_GROUP_BINDINGS.csv',
    'RESOURCE_RECORDS.csv',
    'RESOURCE_RECORD_COMPONENTS.csv',
    'POINTER_RELOCATIONS.csv',
    'INTERNAL_RESOURCE_POINTER_FIXUPS.csv',
    'INTERNAL_MAT_POINTERS.csv',
    'MESH_TO_MAT_INTERNAL_POINTERS.csv',
    'RESOURCE_REFERENCE_FIXUPS.csv',
    'MAT_REFERENCES.csv',
    'TEX_REFERENCES.csv',
    'MESH_REFERENCES.csv',
    'SPIDERMAN_MAT_MATCH_CANDIDATES.csv',
]


def _safe_folder_name(text: str, max_len: int = 90) -> str:
    clean = ''.join(c if c.isalnum() or c in '._-' else '_' for c in str(text))
    clean = clean.strip(' ._') or 'PACK'
    return clean[:max_len]


def _create_unique_clean_scan_root(out_dir: Path) -> Path:
    """Create a brand-new timestamped scan folder, never reuse an older one."""
    stamp = _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    base = Path(out_dir) / f'TEMP_APKF_FULL_PACK_SCAN_{stamp}'
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = Path(str(base) + f'_{suffix:02d}')
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _append_csv_file(source_csv: Path, master_csv: Path) -> int:
    """Append one generated CSV to a master CSV without loading it all into RAM."""
    source_csv = Path(source_csv)
    master_csv = Path(master_csv)
    if not source_csv.exists() or not source_csv.is_file():
        return 0

    master_csv.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with source_csv.open('r', encoding='utf-8-sig', errors='replace', newline='') as src:
        reader = csv.DictReader(src)
        fields = list(reader.fieldnames or [])
        if not fields:
            return 0
        write_header = not master_csv.exists() or master_csv.stat().st_size == 0
        mode = 'w' if write_header else 'a'
        with master_csv.open(mode, encoding='utf-8-sig' if write_header else 'utf-8', newline='') as dst:
            writer = csv.DictWriter(dst, fieldnames=fields, extrasaction='ignore')
            if write_header:
                writer.writeheader()
            for row in reader:
                writer.writerow(row)
                count += 1
    return count


def _safe_write_scan_state(
    scan_root: Path,
    index_rows: List[Dict[str, Any]],
    failed_rows: List[Dict[str, Any]],
    index_fields: List[str],
    progress_text: str,
    *,
    log=print,
) -> None:
    """Best-effort live state update that is NEVER allowed to kill the scan.

    v5.2.113 could be interrupted if Windows/Excel/AV temporarily locked one of
    the live CSVs. v5.2.116 treats the per-pack output as the source of truth and
    keeps scanning even if a live status file is temporarily unavailable.
    """
    for name, rows in (
        ('PACK_SCAN_INDEX.csv', index_rows),
        ('PACK_SCAN_ERRORS.csv', failed_rows),
    ):
        try:
            _write_csv(scan_root / name, rows, index_fields)
        except Exception as exc:
            log(f'[TEMP FULL APKF SCAN] WARNING: could not update {name}: {type(exc).__name__}: {exc}')
    try:
        (scan_root / 'PROGRESS.txt').write_text(progress_text, encoding='utf-8')
    except Exception as exc:
        log(f'[TEMP FULL APKF SCAN] WARNING: could not update PROGRESS.txt: {type(exc).__name__}: {exc}')


def _build_master_csvs_after_scan(
    scan_root: Path,
    successful_rows: List[Dict[str, Any]],
    *,
    log=print,
) -> Tuple[Path, Dict[str, int], List[Dict[str, str]]]:
    """Build the whole-game master tables only AFTER the per-pack pass.

    This preserves the v5.2.115 stability fix. The old v5.2.113 scanner appended to giant
    MASTER CSVs while it was still scanning individual packs. If Windows/Excel
    locked one of those files, an already-successful pack could be reported as
    failed. v5.2.116 keeps scanning, raw aggregation, and clean database generation separated.
    """
    staging = scan_root / 'MASTER_CSV_BUILDING'
    final_root = scan_root / 'MASTER_CSV'

    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    if final_root.exists():
        shutil.rmtree(final_root, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    counts: Dict[str, int] = {name: 0 for name in FULL_SCAN_MASTER_FILES}
    errors: List[Dict[str, str]] = []

    for row in successful_rows:
        actual_dump_raw = str(row.get('output_root') or '').strip()
        if not actual_dump_raw:
            errors.append({
                'pack_index': str(row.get('pack_index') or ''),
                'relative_path': str(row.get('relative_path') or ''),
                'csv_name': '*',
                'error': 'Missing per-pack output_root.',
            })
            continue

        actual_dump = Path(actual_dump_raw)
        if not actual_dump.exists():
            errors.append({
                'pack_index': str(row.get('pack_index') or ''),
                'relative_path': str(row.get('relative_path') or ''),
                'csv_name': '*',
                'error': f'Per-pack dump folder does not exist: {actual_dump}',
            })
            continue

        for csv_name in FULL_SCAN_MASTER_FILES:
            src_csv = actual_dump / csv_name
            master_csv = staging / f'MASTER_{csv_name}'
            try:
                counts[csv_name] += _append_csv_file(src_csv, master_csv)
            except Exception as exc:
                errors.append({
                    'pack_index': str(row.get('pack_index') or ''),
                    'relative_path': str(row.get('relative_path') or ''),
                    'csv_name': csv_name,
                    'error': f'{type(exc).__name__}: {exc}',
                })
                log(
                    f'[TEMP FULL APKF SCAN] MASTER MERGE ERROR '
                    f'{row.get("relative_path")} / {csv_name}: {exc}'
                )

    merge_fields = ['pack_index', 'relative_path', 'csv_name', 'error']
    try:
        _write_csv(staging / 'MASTER_MERGE_ERRORS.csv', errors, merge_fields)
    except Exception as exc:
        log(f'[TEMP FULL APKF SCAN] WARNING: could not write MASTER_MERGE_ERRORS.csv: {exc}')

    # Publish only after the whole merge pass so users do not accidentally open
    # a half-built master folder during the scan.
    published_root = staging
    try:
        staging.rename(final_root)
        published_root = final_root
    except Exception as exc:
        log(
            '[TEMP FULL APKF SCAN] WARNING: could not rename MASTER_CSV_BUILDING '
            f'to MASTER_CSV: {type(exc).__name__}: {exc}'
        )

    return published_root, counts, errors


def scan_pack_folder_references(
    pack_folder: Path,
    out_dir: Path,
    *,
    recursive: bool = True,
    log=print,
) -> Dict[str, Any]:
    """TEMP v5.2.116: start a NEW clean whole-game APKF/material/database scan.

    Important behavior:
    - Built directly from v5.2.113, not the resumable v5.2.114 path.
    - EVERY click creates a brand-new timestamped scan folder.
    - No old scan is resumed or reused.
    - INPUT is a folder, not one pack.
    - OUTPUT always lives under Pack Extractor CHOOSE OUTPUT.
    - Per-pack data is written first and is the source of truth.
    - MASTER_CSV is built only after the full per-pack pass.
    - A locked master/live CSV cannot mark an already-successful pack as failed.
    - Source game files are read-only and never modified.
    """
    pack_folder = Path(pack_folder)
    out_dir = Path(out_dir)
    if not pack_folder.exists() or not pack_folder.is_dir():
        raise ValueError(f'Pack folder does not exist: {pack_folder}')

    out_dir.mkdir(parents=True, exist_ok=True)
    scan_root = _create_unique_clean_scan_root(out_dir)
    per_pack_root = scan_root / 'PER_PACK'
    per_pack_root.mkdir(parents=True, exist_ok=True)

    (scan_root / 'SCAN_SOURCE.txt').write_text(
        str(pack_folder) + '\n' + str(out_dir) + '\n',
        encoding='utf-8',
    )

    iterator = pack_folder.rglob('*') if recursive else pack_folder.glob('*')
    packs = sorted(
        (p for p in iterator if p.is_file() and p.suffix.lower() in FULL_SCAN_SUFFIXES),
        key=lambda p: str(p.relative_to(pack_folder)).lower(),
    )
    if not packs:
        raise ReferenceDumpError(
            f'No .PCPACK, .PCAPK, or .APKF files were found under: {pack_folder}'
        )

    log('[TEMP FULL APKF SCAN] v5.2.116 CLEAN START + RESOURCE DATABASE MODE')
    log('[TEMP FULL APKF SCAN] This scan ALWAYS starts from pack 1 in a NEW folder.')
    log(f'[TEMP FULL APKF SCAN] Pack folder: {pack_folder}')
    log(f'[TEMP FULL APKF SCAN] CHOOSE OUTPUT: {out_dir}')
    log(f'[TEMP FULL APKF SCAN] Actual scan folder: {scan_root}')
    log(f'[TEMP FULL APKF SCAN] Found {len(packs)} PC pack/APKF file(s).')
    log('[TEMP FULL APKF SCAN] Master CSV aggregation is deferred until the end.')
    log('[TEMP FULL APKF SCAN] Read-only research scan. Game files will not be modified.')

    index_fields = [
        'pack_index','relative_path','source_pack','source_pack_path','status','error',
        'output_root','apkf_archives','archive_errors','pointer_relocations',
        'resource_references','mat_references','tex_references','mesh_references',
        'internal_mat_pointers','mesh_to_internal_mat_pointers','spiderman_mat_candidates',
    ]
    pack_index_rows: List[Dict[str, Any]] = []
    failed_rows: List[Dict[str, Any]] = []

    total_archives = 0
    total_archive_errors = 0
    total_relocs = 0
    total_refs = 0
    total_internal_mat = 0
    total_mesh_mat = 0
    total_mat_refs = 0
    total_tex_refs = 0
    total_mesh_refs = 0
    total_candidates = 0
    completed = 0

    for idx, pack_path in enumerate(packs, start=1):
        rel = pack_path.relative_to(pack_folder)
        unique_dir = per_pack_root / f'{idx:04d}_{_safe_folder_name(str(rel.with_suffix("")))}'
        unique_dir.mkdir(parents=True, exist_ok=True)
        log(f'[TEMP FULL APKF SCAN {idx}/{len(packs)}] {rel}')

        # The try/except covers ONLY this pack's analysis. Master CSV output and
        # live index writes are deliberately outside this block so they cannot
        # create a false pack failure.
        try:
            result = dump_selected_pack_references(pack_path, unique_dir, log=log)
            actual_dump = Path(str(result.get('output_root') or unique_dir))
            row = {
                'pack_index': idx,
                'relative_path': str(rel),
                'source_pack': pack_path.name,
                'source_pack_path': str(pack_path),
                'status': 'OK',
                'error': '',
                'output_root': str(actual_dump),
                'apkf_archives': result.get('apkf_archives', 0),
                'archive_errors': result.get('archive_errors', 0),
                'pointer_relocations': result.get('pointer_relocations', 0),
                'resource_references': result.get('resource_references', 0),
                'mat_references': result.get('mat_references', 0),
                'tex_references': result.get('tex_references', 0),
                'mesh_references': result.get('mesh_references', 0),
                'internal_mat_pointers': result.get('internal_mat_pointers', 0),
                'mesh_to_internal_mat_pointers': result.get('mesh_to_internal_mat_pointers', 0),
                'spiderman_mat_candidates': result.get('spiderman_mat_candidates', 0),
            }
            pack_index_rows.append(row)
            completed += 1

            total_archives += int(result.get('apkf_archives', 0) or 0)
            total_archive_errors += int(result.get('archive_errors', 0) or 0)
            total_relocs += int(result.get('pointer_relocations', 0) or 0)
            total_refs += int(result.get('resource_references', 0) or 0)
            total_internal_mat += int(result.get('internal_mat_pointers', 0) or 0)
            total_mesh_mat += int(result.get('mesh_to_internal_mat_pointers', 0) or 0)
            total_mat_refs += int(result.get('mat_references', 0) or 0)
            total_tex_refs += int(result.get('tex_references', 0) or 0)
            total_mesh_refs += int(result.get('mesh_references', 0) or 0)
            total_candidates += int(result.get('spiderman_mat_candidates', 0) or 0)

        except Exception as exc:
            err = f'{type(exc).__name__}: {exc}'
            row = {
                'pack_index': idx,
                'relative_path': str(rel),
                'source_pack': pack_path.name,
                'source_pack_path': str(pack_path),
                'status': 'ERROR',
                'error': err,
                'output_root': str(unique_dir),
                'apkf_archives': 0,
                'archive_errors': 0,
                'pointer_relocations': 0,
                'resource_references': 0,
                'mat_references': 0,
                'tex_references': 0,
                'mesh_references': 0,
                'internal_mat_pointers': 0,
                'mesh_to_internal_mat_pointers': 0,
                'spiderman_mat_candidates': 0,
            }
            pack_index_rows.append(row)
            failed_rows.append(row)
            log(f'[TEMP FULL APKF SCAN] PACK ERROR {rel}: {err}')

        _safe_write_scan_state(
            scan_root,
            pack_index_rows,
            failed_rows,
            index_fields,
            (
                f'Processed: {idx}/{len(packs)}\n'
                f'Succeeded: {completed}\n'
                f'Failed: {len(failed_rows)}\n'
                f'Remaining: {len(packs) - idx}\n'
                f'Current: {rel}\n'
                'Mode: CLEAN START (no resume/reuse)\n'
                'Master CSV status: DEFERRED UNTIL END\n'
            ),
            log=log,
        )

    # Final index write is best-effort, but failure here does not invalidate the
    # per-pack data. The master builder consumes the in-memory successful rows.
    _safe_write_scan_state(
        scan_root,
        pack_index_rows,
        failed_rows,
        index_fields,
        (
            f'Processed: {len(packs)}/{len(packs)}\n'
            f'Succeeded: {completed}\n'
            f'Failed: {len(failed_rows)}\n'
            'Remaining: 0\n'
            'Current: PER-PACK PASS COMPLETE\n'
            'Mode: CLEAN START (no resume/reuse)\n'
            'Master CSV status: BUILDING\n'
        ),
        log=log,
    )

    successful_rows = [r for r in pack_index_rows if str(r.get('status') or '').upper() == 'OK']
    log('[TEMP FULL APKF SCAN] Per-pack pass complete. Building MASTER_CSV now...')
    master_root, master_row_counts, master_merge_errors = _build_master_csvs_after_scan(
        scan_root,
        successful_rows,
        log=log,
    )

    database_result: Dict[str, Any] = {}
    database_error = ""
    if len(master_merge_errors) == 0:
        try:
            log("[TEMP FULL APKF SCAN] Raw MASTER_CSV complete. Building v5.2.116 CLEAN_DATABASE...")
            database_result = clean_db_backend.build_clean_database(scan_root, log=log)
        except Exception as exc:
            database_error = f"{type(exc).__name__}: {exc}"
            log(f"[TEMP FULL APKF SCAN] CLEAN_DATABASE ERROR: {database_error}")

    fully_complete = completed == len(packs) and not failed_rows
    master_complete = len(master_merge_errors) == 0
    database_complete = bool(database_result) and not database_error

    summary_lines = [
        'SM3 TEMP CLEAN FULL APKF PACK-FOLDER REFERENCE SCAN v5.2.116',
        '===========================================================',
        '',
        f'Overall status: {"COMPLETE" if fully_complete and master_complete and database_complete else "FINISHED WITH ERRORS"}',
        'Mode: CLEAN START - this scan did not resume or reuse any old scan.',
        f'Pack folder: {pack_folder}',
        f'CHOOSE OUTPUT root: {out_dir}',
        f'Actual scan folder: {scan_root}',
        '',
        f'PC pack/APKF files discovered: {len(packs)}',
        f'Packs scanned successfully: {completed}',
        f'Packs failed: {len(failed_rows)}',
        f'APKF archives discovered: {total_archives}',
        f'APKF archive parse errors: {total_archive_errors}',
        f'Pointer relocations: {total_relocs}',
        f'Internal pointers resolving to MAT: {total_internal_mat}',
        f'MESH -> internal MAT pointer rows: {total_mesh_mat}',
        f'External resource-reference fixups: {total_refs}',
        f'External MAT references: {total_mat_refs}',
        f'External TEX references: {total_tex_refs}',
        f'External MESH references: {total_mesh_refs}',
        f'Spider-Man known serialized MAT candidate rows: {total_candidates}',
        f'Master merge errors: {len(master_merge_errors)}',
        f'Clean database status: {"COMPLETE" if database_complete else "ERROR/NOT BUILT"}',
        f'Clean database error: {database_error}',
        f'Clean MESH -> MAT rows: {database_result.get("mesh_to_mat_rows", 0)}',
        f'Clean MAT -> TEX rows: {database_result.get("mat_to_tex_rows", 0)}',
        f'Clean resource instances: {database_result.get("resource_instances", 0)}',
        f'Marker reference rows isolated: {database_result.get("marker_reference_rows", 0)}',
        f'T30 parse diagnostics: {database_result.get("t30_parse_errors", 0)}',
        '',
        'MASTER DATA:',
        f'  {master_root}',
        '',
        'CLEAN DATABASE:',
        f'  {database_result.get("database_root", "")}',
    ]
    for csv_name in FULL_SCAN_MASTER_FILES:
        summary_lines.append(f'  MASTER_{csv_name}: {master_row_counts.get(csv_name, 0)} row(s)')
    summary_lines += [
        '',
        'OPEN THESE FIRST:',
        '  CLEAN_DATABASE/MASTER_MESH_TO_MAT.csv',
        '  CLEAN_DATABASE/MASTER_MAT_TO_TEX.csv',
        '  CLEAN_DATABASE/MESH_MATERIAL_DATABASE.csv',
        '  CLEAN_DATABASE/MATERIAL_TEXTURE_DATABASE.csv',
        '  CLEAN_DATABASE/SPIDERMAN_MESH_MAT_TEX_CHAIN.csv',
        f'  {master_root.name}/MASTER_MESH_TO_MAT_INTERNAL_POINTERS.csv',
        f'  {master_root.name}/MASTER_RESOURCE_RECORDS.csv',
        f'  {master_root.name}/MASTER_INTERNAL_RESOURCE_POINTER_FIXUPS.csv',
        f'  {master_root.name}/MASTER_RESOURCE_REFERENCE_FIXUPS.csv',
        '  PACK_SCAN_INDEX.csv',
        '  SUMMARY.txt',
        '',
        'Every per-pack dump is preserved under PER_PACK.',
        'MASTER_CSV is not touched until the per-pack scan has finished.',
        'A Windows/Excel lock on a master/live CSV cannot turn an already-successful pack into a false failure.',
        'This TEMP scan reads source packs only. It never modifies the game files.',
    ]
    (scan_root / 'SUMMARY.txt').write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')

    (scan_root / 'README_TEMP_FULL_APKF_SCAN.txt').write_text(
        'TEMP CLEAN FULL APKF PACK-FOLDER SCAN v5.2.116\n'
        '==============================================\n\n'
        'This build starts a brand-new scan every time. It does NOT resume or reuse\n'
        'v5.2.113/v5.2.114 scan data.\n\n'
        'Select the Spider-Man 3 packs folder. The tool recursively scans every\n'
        '.PCPACK, .PCAPK, and .APKF file and writes everything under CHOOSE OUTPUT.\n\n'
        'PER_PACK is written first and is the source of truth. MASTER_CSV is created\n'
        'only after the entire per-pack pass is finished. This fixes the v5.2.113\n'
        'false-failure bug caused by Windows/Excel locks on giant master CSV files.\n\n'
        'Source game files are read-only and never modified.\n',
        encoding='utf-8',
    )

    try:
        _write_csv(scan_root / 'MASTER_MERGE_ERRORS.csv', master_merge_errors,
                   ['pack_index','relative_path','csv_name','error'])
    except Exception as exc:
        log(f'[TEMP FULL APKF SCAN] WARNING: could not write root MASTER_MERGE_ERRORS.csv: {exc}')

    (out_dir / 'TEMP_APKF_FULL_PACK_SCAN_LATEST.txt').write_text(
        f'Pack folder: {pack_folder}\nLatest clean full scan: {scan_root}\n',
        encoding='utf-8',
    )

    try:
        (scan_root / 'PROGRESS.txt').unlink()
    except OSError:
        pass

    log(
        f'[TEMP FULL APKF SCAN] DONE packs={completed}/{len(packs)} '
        f'failed={len(failed_rows)} archives={total_archives} '
        f'reloc={total_relocs} MESH_to_MAT={total_mesh_mat} '
        f'master_merge_errors={len(master_merge_errors)} '
        f'clean_database={"OK" if database_complete else "ERROR"}'
    )
    log(f'[TEMP FULL APKF SCAN] MASTER: {master_root}')
    log(f'[TEMP FULL APKF SCAN] OUTPUT: {scan_root}')

    return {
        'scan_root': str(scan_root),
        'chosen_output_root': str(out_dir),
        'pack_folder': str(pack_folder),
        'clean_start': True,
        'fully_complete': fully_complete,
        'master_complete': master_complete,
        'master_root': str(master_root),
        'packs_discovered': len(packs),
        'packs_processed': completed,
        'packs_failed': len(failed_rows),
        'apkf_archives': total_archives,
        'archive_errors': total_archive_errors,
        'pointer_relocations': total_relocs,
        'resource_references': total_refs,
        'internal_mat_pointers': total_internal_mat,
        'mesh_to_internal_mat_pointers': total_mesh_mat,
        'mat_references': total_mat_refs,
        'tex_references': total_tex_refs,
        'mesh_references': total_mesh_refs,
        'spiderman_mat_candidates': total_candidates,
        'master_merge_errors': len(master_merge_errors),
        'database_complete': database_complete,
        'database_error': database_error,
        'database_root': database_result.get('database_root', ''),
        'clean_resource_instances': database_result.get('resource_instances', 0),
        'clean_mesh_to_mat_rows': database_result.get('mesh_to_mat_rows', 0),
        'clean_mat_to_tex_rows': database_result.get('mat_to_tex_rows', 0),
        'marker_reference_rows': database_result.get('marker_reference_rows', 0),
        't30_parse_errors': database_result.get('t30_parse_errors', 0),
    }
