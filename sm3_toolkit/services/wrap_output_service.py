from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence

from sm3_toolkit.services import pack_extract_service as backend
from sm3_toolkit.services.wrap_extract_service import WrapAPKFArchive, PatchPlan, build_wrap_bytes

WRAP_MAGIC = b"WRAP"
_HASH_RE = re.compile(r"0x([0-9A-Fa-f]{8})")
_ARCHIVE_RE = re.compile(r"^O(?P<index>\d+)\.0x(?P<hash>[0-9A-Fa-f]{8})\.T(?P<type>[0-9A-Fa-f]+)\.apkf$", re.I)


class WrapOutputError(RuntimeError):
    pass


def _intish(value: Any, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    try:
        return int(text, 0)
    except Exception:
        m = _HASH_RE.search(text)
        return int(m.group(1), 16) if m else default


def _s32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise WrapOutputError(f"WRAP relative pointer outside file at 0x{off:X}")
    return struct.unpack_from("<i", data, off)[0]


def _u32(data: bytes, off: int) -> int:
    if off < 0 or off + 4 > len(data):
        raise WrapOutputError(f"WRAP dword outside file at 0x{off:X}")
    return struct.unpack_from("<I", data, off)[0]


@dataclass(frozen=True)
class StandaloneWrapInfo:
    archive_hash: int
    component_count: int
    component_table_offset: int
    patch_table_offset: int
    component_offsets: tuple[int, ...]
    component_sizes: tuple[int, ...]


def inspect_wrap_bytes(data: bytes) -> StandaloneWrapInfo:
    if len(data) < 20 or data[:4] != WRAP_MAGIC:
        raise WrapOutputError("Choose a valid standalone .wrap resource.")
    archive_hash = _u32(data, 4)
    patch_table = 8 + _s32(data, 8)
    count = _u32(data, 12)
    comp_table = 16 + _s32(data, 16)
    if not 1 <= count <= 2:
        raise WrapOutputError(f"WRAP component count {count} is not supported by this focused output route.")
    if comp_table < 0 or comp_table + count * 8 > len(data):
        raise WrapOutputError("WRAP component table is outside the file.")
    sizes = []
    offsets = []
    for i in range(count):
        entry = comp_table + i * 8
        size = _u32(data, entry)
        ptr_field = entry + 4
        start = ptr_field + _s32(data, ptr_field)
        if start < 0 or start + size > len(data):
            raise WrapOutputError(f"WRAP component {i} range is outside the file.")
        sizes.append(size)
        offsets.append(start)
    return StandaloneWrapInfo(
        archive_hash=archive_hash,
        component_count=count,
        component_table_offset=comp_table,
        patch_table_offset=patch_table,
        component_offsets=tuple(offsets),
        component_sizes=tuple(sizes),
    )


def read_wrap_component(path: str | Path, component_index: int = 0) -> bytes:
    path = Path(path)
    data = path.read_bytes()
    info = inspect_wrap_bytes(data)
    if component_index < 0 or component_index >= info.component_count:
        raise WrapOutputError(f"WRAP has only {info.component_count} component(s).")
    start = info.component_offsets[component_index]
    size = info.component_sizes[component_index]
    return data[start:start + size]


def replace_wrap_component0_exact(shell_bytes: bytes, new_component0: bytes) -> bytes:
    """Replace component0 without changing any WRAP offsets/tables.

    This is deliberately exact-size only. It is used for edited MAT / same-size
    ANIM convenience output. Different-size resources should be rebuilt from the
    authoritative pack patch map instead of mutating wrapper layout blindly.
    """
    info = inspect_wrap_bytes(shell_bytes)
    expected = info.component_sizes[0]
    if len(new_component0) != expected:
        raise WrapOutputError(
            f"WRAP shell component0 is {expected} bytes but edited data is {len(new_component0)} bytes. "
            "Exact-size shell replacement is required for this button."
        )
    out = bytearray(shell_bytes)
    start = info.component_offsets[0]
    out[start:start + expected] = new_component0
    return bytes(out)


def retarget_wrap_archive_hash(wrap_bytes: bytes, archive_hash: int) -> bytes:
    inspect_wrap_bytes(wrap_bytes)
    out = bytearray(wrap_bytes)
    struct.pack_into("<I", out, 4, int(archive_hash) & 0xFFFFFFFF)
    return bytes(out)


def retarget_anim_component_resource_hash(anim_bytes: bytes, resource_hash: int) -> bytes:
    """Retarget the embedded SM3 ANIM resource hash at component +0x04.

    The motion/layout bytes remain untouched.  This is required when donor ANIM
    bytes are routed under a different target identity by XESM3/NativeWRAP.
    """
    if len(anim_bytes) < 8:
        raise WrapOutputError(f"ANIM component is too small to contain a resource hash: {len(anim_bytes)} bytes")
    out = bytearray(anim_bytes)
    struct.pack_into("<I", out, 0x04, int(resource_hash) & 0xFFFFFFFF)
    return bytes(out)


def read_wrap_anim_resource_hash(wrap_bytes: bytes) -> int:
    """Read component0 +0x04 from a standalone .wrap.anim."""
    info = inspect_wrap_bytes(wrap_bytes)
    if info.component_sizes[0] < 8:
        raise WrapOutputError("WRAP.ANIM component0 is too small to contain a resource hash.")
    return _u32(wrap_bytes, info.component_offsets[0] + 0x04)


def retarget_wrap_anim_resource_hash(wrap_bytes: bytes, resource_hash: int) -> bytes:
    """Retarget only the embedded ANIM identity inside a standalone WRAP.

    The WRAP archive hash, component table, patch tables, component sizes, and
    all donor motion bytes remain unchanged.
    """
    info_before = inspect_wrap_bytes(wrap_bytes)
    if info_before.component_sizes[0] < 8:
        raise WrapOutputError("WRAP.ANIM component0 is too small to retarget.")
    out = bytearray(wrap_bytes)
    struct.pack_into(
        "<I",
        out,
        info_before.component_offsets[0] + 0x04,
        int(resource_hash) & 0xFFFFFFFF,
    )
    result = bytes(out)
    info_after = inspect_wrap_bytes(result)
    if info_after != info_before:
        raise WrapOutputError("WRAP.ANIM identity retarget unexpectedly changed WRAP structure.")
    if read_wrap_anim_resource_hash(result) != (int(resource_hash) & 0xFFFFFFFF):
        raise WrapOutputError("WRAP.ANIM inner identity verification failed.")
    return result



def patch_plans_from_standalone_wrap(data: bytes) -> list[PatchPlan]:
    """Recover the relocation plan encoded in a standalone Toolkit WRAP.

    This is the inverse of :func:`build_wrap_bytes` for the runtime-tested
    one/two-component NativeWRAP layout.  It lets Browse + Image use an
    already-extracted ``.wrap.tex`` as the authoritative shell while safely
    rebuilding component sizes and relative pointers for a replacement DDS.
    """
    info = inspect_wrap_bytes(data)
    if info.component_count not in (1, 2):
        raise WrapOutputError(f"Unsupported WRAP component count: {info.component_count}")

    c0_start = info.component_offsets[0]
    c0_size = info.component_sizes[0]
    c0 = data[c0_start:c0_start + c0_size]
    patch = info.patch_table_offset
    if patch < 0 or patch + 24 > len(data):
        raise WrapOutputError("WRAP patch table header is outside the file.")

    ext_count = _u32(data, patch + 0)
    ext_start = (patch + 4) + _s32(data, patch + 4)
    int_count = _u32(data, patch + 8)
    int_start = (patch + 12) + _s32(data, patch + 12)
    global_count = _u32(data, patch + 16)
    global_start = (patch + 20) + _s32(data, patch + 20)

    if ext_count > 2_000_000 or int_count > 2_000_000 or global_count > 1_000_000:
        raise WrapOutputError("WRAP patch-count guard hit.")
    if ext_start < 0 or ext_start + ext_count * 16 > len(data):
        raise WrapOutputError("WRAP external patch table is outside the file.")
    if int_start < 0 or int_start + int_count * 4 > len(data):
        raise WrapOutputError("WRAP internal patch table is outside the file.")
    if global_start < 0 or global_start + global_count * 16 > len(data):
        raise WrapOutputError("WRAP global patch table is outside the file.")

    def target_offset_from_field(field: int) -> int:
        absolute = field + _s32(data, field)
        off = absolute - c0_start
        if off < 0 or off + 4 > c0_size:
            raise WrapOutputError(
                f"WRAP patch target 0x{absolute:X} is outside component0."
            )
        return off

    plans: list[PatchPlan] = []

    for i in range(ext_count):
        rec = ext_start + i * 16
        ref_type = data[rec:rec + 4].decode("ascii", errors="replace").replace("\x00", "")
        ref_hash = _u32(data, rec + 4)
        target_off = target_offset_from_field(rec + 12)
        encoded_ref = _u32(c0, target_off)
        plans.append(PatchPlan(
            kind="external", target_offset=target_off, encoded_ref=encoded_ref,
            ref_file_type=ref_type, ref_filename_hash=ref_hash,
        ))

    for i in range(int_count):
        field = int_start + i * 4
        target_off = target_offset_from_field(field)
        rel = _s32(c0, target_off)
        ref_standalone = target_off + rel
        if 0 <= ref_standalone < c0_size:
            ref_component = 0
            ref_offset = ref_standalone
        elif info.component_count == 2:
            c1_base = c0_size + 4  # build_wrap_bytes inserts literal PHYS before component1
            c1_size = info.component_sizes[1]
            if not (c1_base <= ref_standalone < c1_base + c1_size):
                raise WrapOutputError(
                    f"WRAP internal reference +0x{ref_standalone:X} is outside both components."
                )
            ref_component = 1
            ref_offset = ref_standalone - c1_base
        else:
            raise WrapOutputError(
                f"WRAP internal reference +0x{ref_standalone:X} is outside component0."
            )
        plans.append(PatchPlan(
            kind="internal", target_offset=target_off,
            ref_component_index=ref_component, ref_offset=ref_offset,
        ))

    for i in range(global_count):
        rec = global_start + i * 16
        ref_type = data[rec:rec + 4].decode("ascii", errors="replace").replace("\x00", "")
        ref_hash = _u32(data, rec + 4)
        target_off = target_offset_from_field(rec + 12)
        target_value = _u32(c0, target_off)
        plans.append(PatchPlan(
            kind="global", target_offset=target_off,
            ref_file_type=ref_type, ref_filename_hash=ref_hash,
            global_target_value=target_value,
        ))

    return sorted(plans, key=lambda x: x.target_offset)


def rebuild_wrap_from_shell_components(
    shell_bytes: bytes,
    replacement_components: Sequence[bytes],
) -> tuple[bytes, dict[str, int]]:
    """Rebuild a standalone NativeWRAP from its own authoritative patch shell.

    Unlike ``replace_wrap_component0_exact``, this route may change component
    sizes because it reconstructs all wrapper-relative offsets and internal
    references from the patch tables.  It still fails closed if an internal
    reference no longer lands inside the replacement components.
    """
    info = inspect_wrap_bytes(shell_bytes)
    if len(replacement_components) != info.component_count:
        raise WrapOutputError(
            f"WRAP shell uses {info.component_count} component(s), replacement supplied {len(replacement_components)}."
        )
    plans = patch_plans_from_standalone_wrap(shell_bytes)
    rebuilt, stats = build_wrap_bytes(
        [bytes(x) for x in replacement_components], plans, info.archive_hash
    )
    inspect_wrap_bytes(rebuilt)
    return rebuilt, stats

def rebuild_wrap_anim_from_shell(
    shell_bytes: bytes,
    replacement_anim: bytes,
) -> tuple[bytes, dict[str, int]]:
    """Rebuild a NativeWRAP ANIM shell around a canonical edited ANIM.

    Motion Editor arbitrary-size rebuilds may insert bytes immediately before
    the ANIM metadata tail.  That shifts both some pointer *fields* and the
    local objects they reference.  A generic shell rebuild only knows the old
    offsets, so this ANIM-specific route relocates patch targets by the payload
    growth delta and resolves each internal reference from the edited ANIM's
    own canonical local pointer token before rebuilding the WRAP.
    """
    from sm3_toolkit.services.anim_decoder_service import normalize_anim_bytes
    from sm3_toolkit.services.anim_codec_service import AnimResource, AnimCodecError

    info = inspect_wrap_bytes(shell_bytes)
    if info.component_count < 1:
        raise WrapOutputError("WRAP.ANIM shell contains no component0.")
    old_anim = normalize_anim_bytes(shell_bytes)
    new_anim = bytes(replacement_anim)
    try:
        old_resource = AnimResource(old_anim)
        old_header, _old_nodes, _old_post = old_resource.parse_header()
        new_resource = AnimResource(new_anim)
        new_header, _new_nodes, _new_post = new_resource.parse_header()
    except AnimCodecError as exc:
        raise WrapOutputError(f"ANIM shell/replacement parse failed: {exc}") from exc

    if int(new_header.source_hash) != int(old_header.source_hash):
        raise WrapOutputError(
            f"ANIM shell/replacement identity mismatch: shell=0x{int(old_header.source_hash):08X} "
            f"replacement=0x{int(new_header.source_hash):08X}."
        )
    if int(new_header.askl_hash) != int(old_header.askl_hash):
        raise WrapOutputError(
            f"ANIM shell/replacement ASKL mismatch: shell=0x{int(old_header.askl_hash):08X} "
            f"replacement=0x{int(new_header.askl_hash):08X}."
        )

    old_tail = int(old_header.payload_end)
    new_tail = int(new_header.payload_end)
    delta = new_tail - old_tail
    if delta < 0:
        raise WrapOutputError(
            f"Edited ANIM moved metadata tail backward by {delta} bytes; shrink relocation is not supported."
        )

    adjusted: list[PatchPlan] = []
    for plan in patch_plans_from_standalone_wrap(shell_bytes):
        target = int(plan.target_offset)
        if delta and target >= old_tail:
            target += delta
        if target < 0 or target + 4 > len(new_anim):
            raise WrapOutputError(
                f"Relocated WRAP patch target +0x{target:X} is outside edited ANIM ({len(new_anim)} bytes)."
            )

        ref_component = int(plan.ref_component_index)
        ref_offset = int(plan.ref_offset)
        encoded_ref = int(plan.encoded_ref)
        global_value = int(plan.global_target_value)
        if plan.kind == "internal" and ref_component == 0:
            token = _u32(new_anim, target)
            try:
                ref_offset = int(new_resource.resolve_local_token(token))
            except Exception as exc:
                raise WrapOutputError(
                    f"Edited ANIM internal pointer +0x{target:X} token 0x{token:08X} is invalid: {exc}"
                ) from exc
        elif plan.kind == "external":
            encoded_ref = _u32(new_anim, target)
        elif plan.kind == "global":
            global_value = _u32(new_anim, target)

        adjusted.append(PatchPlan(
            kind=plan.kind,
            target_offset=target,
            ref_component_index=ref_component,
            ref_offset=ref_offset,
            encoded_ref=encoded_ref,
            ref_file_type=plan.ref_file_type,
            ref_filename_hash=plan.ref_filename_hash,
            global_target_value=global_value,
        ))

    replacements = [new_anim]
    for i in range(1, info.component_count):
        start = info.component_offsets[i]
        size = info.component_sizes[i]
        replacements.append(shell_bytes[start:start + size])

    rebuilt, stats = build_wrap_bytes(replacements, adjusted, info.archive_hash)
    final_info = inspect_wrap_bytes(rebuilt)
    if final_info.archive_hash != info.archive_hash:
        raise WrapOutputError("WRAP.ANIM archive identity changed during rebuild.")
    # Strong verification: normalize the new WRAP back to canonical ANIM and
    # require a byte-exact match to the edited replacement.
    normalized = normalize_anim_bytes(rebuilt)
    if normalized != new_anim:
        raise WrapOutputError(
            "WRAP.ANIM post-rebuild normalization did not reproduce the edited ANIM byte-exactly."
        )
    stats = dict(stats)
    stats.update({
        "anim_old_payload_end": old_tail,
        "anim_new_payload_end": new_tail,
        "anim_payload_delta": delta,
        "anim_relocated_patch_targets": sum(1 for p in patch_plans_from_standalone_wrap(shell_bytes) if delta and p.target_offset >= old_tail),
    })
    return rebuilt, stats


def parse_wrap_resource_hash(path: str | Path) -> int | None:
    m = _HASH_RE.search(Path(path).name)
    return int(m.group(1), 16) if m else None


def derive_wrap_owner_from_path(path: str | Path) -> dict[str, Any]:
    """Resolve PACK/APKF owner from MOD LOADER READY / WRAP_EXTRACTS hierarchy."""
    path = Path(path)
    parts = list(path.parents)
    archive_dir = None
    archive_match = None
    for parent in parts:
        m = _ARCHIVE_RE.match(parent.name)
        if m:
            archive_dir = parent
            archive_match = m
            break
    if archive_dir is None or archive_match is None:
        raise WrapOutputError(
            "Could not resolve WRAP owner from path. Pick the file from MOD LOADER READY / WRAP_EXTRACTS."
        )
    wrap_root = archive_dir.parent
    if wrap_root.name.upper() != "WRAP_EXTRACTS":
        raise WrapOutputError("WRAP file is not inside the expected WRAP_EXTRACTS hierarchy.")
    pack_dir = wrap_root.parent
    return {
        "pack": pack_dir.name,
        "archive": archive_dir.name,
        "archive_index": int(archive_match.group("index"), 10),
        "archive_hash": int(archive_match.group("hash"), 16),
        "archive_type": int(archive_match.group("type"), 16),
    }


def find_matching_wrap_resource(
    root: str | Path,
    resource_hash: int,
    extension: str,
    *,
    pack: str | None = None,
    archive: str | None = None,
) -> Path:
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(root)
    ext = extension.lower().lstrip(".")
    wanted = f"0x{int(resource_hash) & 0xFFFFFFFF:08x}."
    matches: list[Path] = []
    for p in root.rglob(f"*.wrap.{ext}"):
        low = p.name.lower()
        if not low.startswith(wanted):
            continue
        if pack and pack.lower() not in [x.lower() for x in p.parts]:
            continue
        if archive and archive.lower() not in [x.lower() for x in p.parts]:
            continue
        matches.append(p)
    if not matches:
        raise WrapOutputError(
            f"No matching 0x{int(resource_hash)&0xFFFFFFFF:08X}.wrap.{ext} was found under {root}. "
            "Run MOD LOADER READY first so WRAP_EXTRACTS exists."
        )
    if len(matches) > 1 and archive:
        exact = [p for p in matches if archive.lower() in [x.lower() for x in p.parts]]
        if len(exact) == 1:
            return exact[0]
    if len(matches) > 1:
        raise WrapOutputError(
            f"Multiple matching WRAP resources were found for 0x{int(resource_hash)&0xFFFFFFFF:08X}; "
            "use a more specific extracted pack folder."
        )
    return matches[0]


def _select_authoritative_source(pack_path: Path, target: dict[str, Any]):
    data = pack_path.read_bytes()
    probe = backend.probe_pack_bytes(pack_path.name, data)
    slices, _filtered = backend.apkf_slices_from_probe(data, probe)
    expected_base = _intish(target.get("source_apkf_absolute_base"))
    expected_index = _intish(target.get("source_outer_index"), -1)
    expected_hash = _intish(target.get("source_outer_hash"), -1)
    expected_type = _intish(target.get("source_outer_type"), -1)

    authoritative = [
        s for s in slices
        if s.source_kind == "outer_row"
        and s.parent_outer_index is not None
        and s.parent_outer_hash is not None
        and s.parent_outer_type is not None
    ]
    ranked = []
    for s in authoritative:
        score = 0
        if expected_base is not None and int(s.absolute_base) == expected_base:
            score += 8
        if expected_index is not None and expected_index >= 0 and int(s.parent_outer_index) == expected_index:
            score += 4
        if expected_hash is not None and expected_hash >= 0 and int(s.parent_outer_hash) == expected_hash:
            score += 4
        if expected_type is not None and expected_type >= 0 and int(s.parent_outer_type) == expected_type:
            score += 2
        ranked.append((score, s))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked or ranked[0][0] <= 0:
        raise WrapOutputError("Could not resolve the selected resource's authoritative outer APKF owner.")
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        raise WrapOutputError("Selected resource ownership is ambiguous; WRAP output is blocked instead of guessing.")
    return ranked[0][1]


def build_wrap_from_pcpack_target(
    pack_path: str | Path,
    target: dict[str, Any],
    replacement_components: Sequence[bytes],
) -> tuple[bytes, dict[str, Any]]:
    """Build one target WRAP from an SM3 PC pack using its exact patch plan."""
    pack_path = Path(pack_path)
    if not pack_path.is_file():
        raise FileNotFoundError(pack_path)
    resource_type = str(target.get("file_type") or target.get("resource_type") or "").upper()
    resource_hash = _intish(target.get("filename_hash") or target.get("resource_hash"))
    if not resource_type or resource_hash is None:
        raise WrapOutputError("Target resource type/hash is missing.")

    source = _select_authoritative_source(pack_path, target)
    apkf = WrapAPKFArchive(source.payload, source)
    candidates = [
        f for f in apkf.files
        if str(f.file_type or "").upper() == resource_type
        and int(f.filename_hash) == int(resource_hash)
    ]
    if len(candidates) != 1:
        raise WrapOutputError(
            f"Expected one {resource_type} 0x{resource_hash:08X} in resolved APKF, found {len(candidates)}."
        )
    f = candidates[0]
    original_components = apkf.components_for(f)
    if len(replacement_components) != len(original_components):
        raise WrapOutputError(
            f"Target uses {len(original_components)} component(s), replacement supplied {len(replacement_components)}."
        )
    plans, unresolved = apkf.patch_plans_for(f)
    if unresolved:
        raise WrapOutputError(f"Target has {unresolved} unresolved APKF patch reference(s); WRAP output blocked.")
    wrapped, stats = build_wrap_bytes(
        [bytes(x) for x in replacement_components],
        plans,
        int(source.parent_outer_hash or 0),
    )
    meta = {
        "pack": pack_path.name,
        "resource_type": resource_type,
        "resource_hash": f"0x{resource_hash:08X}",
        "resource_name": f.filename,
        "archive_index": source.parent_outer_index,
        "archive_hash": f"0x{int(source.parent_outer_hash or 0):08X}",
        "archive_type": f"0x{int(source.parent_outer_type or 0):X}",
        "archive_folder": source.archive_folder,
        "original_component_sizes": [len(x) for x in original_components],
        "replacement_component_sizes": [len(x) for x in replacement_components],
        **stats,
        "wrap_bytes": len(wrapped),
    }
    return wrapped, meta


def write_wrap_from_pcpack_target(
    pack_path: str | Path,
    target: dict[str, Any],
    replacement_components: Sequence[bytes],
    output_path: str | Path,
) -> dict[str, Any]:
    wrapped, meta = build_wrap_from_pcpack_target(pack_path, target, replacement_components)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wrapped)
    meta["output"] = str(output_path)
    report = output_path.with_suffix(output_path.suffix + ".json")
    report.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    meta["report"] = str(report)
    return meta
