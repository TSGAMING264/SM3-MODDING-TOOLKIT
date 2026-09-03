#!/usr/bin/env python3
"""SM3 v5.2.116 clean APKF resource database builder.

Consumes a completed TEMP_APKF_FULL_PACK_SCAN_* folder and converts the raw
research master CSVs into production-oriented MESH -> MAT -> TEX databases.

Important policy:
- Raw MASTER_CSV is preserved untouched for research.
- source_archive_kind == "marker" is excluded from production/clean tables.
- Marker rows are preserved separately as diagnostics.
- Internal MESH->MAT and MAT->TEX links require EXACT_START resource matches.
- T30 parser failures are separated for later reverse engineering.
"""
from __future__ import annotations

import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple


DB_VERSION = "v5.2.116"

MESH_TO_MAT_FIELDS = [
    "source_pack",
    "source_archive",
    "source_apkf_label",
    "mesh_name",
    "mesh_hash",
    "mesh_record_index",
    "mesh_material_field_offset",
    "serialized_material_pointer",
    "mat_name",
    "mat_hash",
    "mat_record_index",
    "match_kind",
    "resolved_offset_into_resource",
]

MAT_TO_TEX_FIELDS = [
    "source_pack",
    "source_archive",
    "source_apkf_label",
    "mat_name",
    "mat_hash",
    "mat_record_index",
    "material_texture_field_offset",
    "serialized_texture_pointer",
    "tex_name",
    "tex_hash",
    "tex_record_index",
    "match_kind",
    "resolved_offset_into_resource",
]

RESOURCE_DB_FIELDS = [
    "source_pack",
    "source_archive",
    "source_apkf_label",
    "resource_type",
    "resource_variant",
    "resource_name",
    "resource_hash",
    "record_index",
]

MESH_MATERIAL_DB_FIELDS = [
    "mesh_hash",
    "mesh_name",
    "mesh_material_field_offset",
    "mat_hash",
    "mat_name",
    "occurrences",
    "unique_pack_count",
    "context_variant_count",
    "context_dependent",
    "serialized_pointer_values",
    "example_packs",
]

MATERIAL_TEXTURE_DB_FIELDS = [
    "mat_hash",
    "mat_name",
    "material_texture_field_offset",
    "tex_hash",
    "tex_name",
    "occurrences",
    "unique_pack_count",
    "context_variant_count",
    "context_dependent",
    "serialized_pointer_values",
    "example_packs",
]

SPIDERMAN_CHAIN_FIELDS = [
    "source_pack",
    "source_archive",
    "mesh_name",
    "mesh_hash",
    "mesh_material_field_offset",
    "serialized_material_pointer",
    "mat_name",
    "mat_hash",
    "material_texture_field_offset",
    "serialized_texture_pointer",
    "tex_name",
    "tex_hash",
    "join_scope",
]

MARKER_DIAGNOSTIC_FIELDS = [
    "source_pack",
    "source_archive",
    "source_apkf_label",
    "parent_outer_type",
    "payload_size",
    "package_status",
    "package_error",
    "declared_pointer_relocations",
    "declared_resource_references",
    "resource_records",
    "internal_pointer_fixups",
    "mesh_to_mat_rows",
    "resource_reference_rows",
]

PARSE_ERROR_FIELDS = [
    "source_pack",
    "source_pack_path",
    "archive_index",
    "source_archive",
    "source_archive_kind",
    "source_apkf_label",
    "source_apkf_absolute_base",
    "parent_outer_index",
    "parent_outer_hash",
    "parent_outer_type",
    "error",
]


class CleanDatabaseError(Exception):
    pass


def _iter_csv(path: Path) -> Iterator[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {str(k): str(v or "") for k, v in row.items()}


def _writer(path: Path, fields: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    f = path.open("w", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    return f, w


def _write_rows(path: Path, fields: List[str], rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    f, w = _writer(path, fields)
    try:
        for row in rows:
            w.writerow(row)
            count += 1
    finally:
        f.close()
    return count


def _is_marker(row: Dict[str, str]) -> bool:
    return row.get("source_archive_kind", "").strip().lower() == "marker"


def _is_outer(row: Dict[str, str]) -> bool:
    return row.get("source_archive_kind", "").strip().lower() == "outer_row"


def _is_exact(row: Dict[str, str]) -> bool:
    return row.get("resolved_match_kind", "").strip().upper() == "EXACT_START"


def _u(s: str) -> str:
    return str(s or "").strip().upper()


def _sample_add(items: List[str], value: str, limit: int = 8) -> None:
    value = str(value or "").strip()
    if value and value not in items and len(items) < limit:
        items.append(value)


def _name_pick(values: Set[str]) -> str:
    clean = sorted(v for v in values if v)
    return clean[0] if clean else ""


def _unique_output_dir(scan_root: Path) -> Path:
    base = scan_root / "CLEAN_DATABASE"
    if not base.exists():
        return base
    i = 2
    while True:
        p = scan_root / f"CLEAN_DATABASE_{i:02d}"
        if not p.exists():
            return p
        i += 1


def _marker_key(row: Dict[str, str]) -> Tuple[str, str, str]:
    return (
        row.get("source_pack", ""),
        row.get("source_archive", ""),
        row.get("source_apkf_label", ""),
    )


def _marker_entry(stats: Dict[Tuple[str, str, str], Dict[str, Any]], row: Dict[str, str]) -> Dict[str, Any]:
    key = _marker_key(row)
    if key not in stats:
        stats[key] = {
            "source_pack": key[0],
            "source_archive": key[1],
            "source_apkf_label": key[2],
            "parent_outer_type": row.get("parent_outer_type", ""),
            "payload_size": row.get("payload_size", ""),
            "package_status": "",
            "package_error": "",
            "declared_pointer_relocations": 0,
            "declared_resource_references": 0,
            "resource_records": 0,
            "internal_pointer_fixups": 0,
            "mesh_to_mat_rows": 0,
            "resource_reference_rows": 0,
        }
    return stats[key]


def _to_int(value: str) -> int:
    try:
        return int(str(value or "0"), 0)
    except Exception:
        try:
            return int(str(value or "0"))
        except Exception:
            return 0


def _is_spiderman_mesh(name: str, resource_hash: str) -> bool:
    n = str(name or "").strip().lower()
    h = _u(resource_hash)
    return (
        n.startswith("ch_spiderman")
        or n.startswith("ch_spidey")
        or h in {"0XAC92103D", "0XAC92103E"}
    )


def _locate_parse_error_sources(scan_root: Path, master_root: Path) -> List[Path]:
    master_error = master_root / "MASTER_APKF_REFERENCE_ERRORS.csv"
    if master_error.exists():
        return [master_error]
    return sorted(scan_root.glob("PER_PACK/**/APKF_REFERENCE_ERRORS.csv"))


def _write_manifest(root: Path, row_counts: Dict[str, int]) -> None:
    fields = ["file", "rows", "bytes"]
    rows = []
    for p in sorted(root.glob("*")):
        if not p.is_file():
            continue
        rows.append({
            "file": p.name,
            "rows": row_counts.get(p.name, ""),
            "bytes": p.stat().st_size,
        })
    _write_rows(root / "DATABASE_MANIFEST.csv", fields, rows)


def build_clean_database(scan_root: Path, *, log=print) -> Dict[str, Any]:
    """Build clean v5.2.116 databases from a completed full APKF scan."""
    scan_root = Path(scan_root)
    master_root = scan_root / "MASTER_CSV"
    if not master_root.exists():
        raise CleanDatabaseError(
            f"MASTER_CSV was not found under completed scan folder: {scan_root}"
        )

    required = {
        "mesh_to_mat": master_root / "MASTER_MESH_TO_MAT_INTERNAL_POINTERS.csv",
        "internal": master_root / "MASTER_INTERNAL_RESOURCE_POINTER_FIXUPS.csv",
        "resources": master_root / "MASTER_RESOURCE_RECORDS.csv",
        "refs": master_root / "MASTER_RESOURCE_REFERENCE_FIXUPS.csv",
        "packages": master_root / "MASTER_APKF_PACKAGES.csv",
    }
    missing = [str(p) for p in required.values() if not p.exists()]
    if missing:
        raise CleanDatabaseError("Missing required master CSV(s):\n" + "\n".join(missing))

    final_root = _unique_output_dir(scan_root)
    staging = scan_root / (final_root.name + "_BUILDING")
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=False)

    log(f"[116 CLEAN DB] Scan root: {scan_root}")
    log(f"[116 CLEAN DB] Raw master: {master_root}")
    log("[116 CLEAN DB] Marker pseudo-APKFs will be excluded from production tables.")
    log("[116 CLEAN DB] Raw research MASTER_CSV will not be modified.")

    row_counts: Dict[str, int] = {}
    marker_stats: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    # --------------------------------------------------------------
    # Package rows establish marker diagnostics.
    # --------------------------------------------------------------
    marker_package_count = 0
    for row in _iter_csv(required["packages"]):
        if not _is_marker(row):
            continue
        e = _marker_entry(marker_stats, row)
        e["parent_outer_type"] = row.get("parent_outer_type", "")
        e["payload_size"] = row.get("payload_size", "")
        e["package_status"] = row.get("status", "")
        e["package_error"] = row.get("error", "")
        e["declared_pointer_relocations"] += _to_int(row.get("pointer_relocation_count", "0"))
        e["declared_resource_references"] += _to_int(row.get("resource_reference_count", "0"))
        marker_package_count += 1

    # --------------------------------------------------------------
    # Resource database (outer-row only).
    # --------------------------------------------------------------
    resource_unique: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    resource_type_counts: Counter[str] = Counter()

    resource_out = staging / "MASTER_RESOURCE_DATABASE.csv"
    f_res, w_res = _writer(resource_out, RESOURCE_DB_FIELDS)
    clean_resource_rows = 0
    try:
        for row in _iter_csv(required["resources"]):
            if _is_marker(row):
                _marker_entry(marker_stats, row)["resource_records"] += 1
                continue
            if not _is_outer(row):
                continue

            out = {
                "source_pack": row.get("source_pack", ""),
                "source_archive": row.get("source_archive", ""),
                "source_apkf_label": row.get("source_apkf_label", ""),
                "resource_type": row.get("group_type", ""),
                "resource_variant": row.get("group_variant", ""),
                "resource_name": row.get("resource_name", ""),
                "resource_hash": row.get("resource_hash", ""),
                "record_index": row.get("record_index", ""),
            }
            w_res.writerow(out)
            clean_resource_rows += 1
            rtype = _u(out["resource_type"])
            resource_type_counts[rtype] += 1

            key = (rtype, _u(out["resource_hash"]), out["resource_name"])
            e = resource_unique.get(key)
            if e is None:
                e = {
                    "resource_type": rtype,
                    "resource_hash": _u(out["resource_hash"]),
                    "resource_name": out["resource_name"],
                    "occurrences": 0,
                    "variants": set(),
                    "example_packs": [],
                }
                resource_unique[key] = e
            e["occurrences"] += 1
            if out["resource_variant"]:
                e["variants"].add(out["resource_variant"])
            _sample_add(e["example_packs"], out["source_pack"])
    finally:
        f_res.close()
    row_counts[resource_out.name] = clean_resource_rows

    unique_resource_fields = [
        "resource_type",
        "resource_hash",
        "resource_name",
        "occurrences",
        "variants",
        "example_packs",
    ]
    unique_resource_rows = []
    for _, e in sorted(resource_unique.items(), key=lambda kv: kv[0]):
        unique_resource_rows.append({
            "resource_type": e["resource_type"],
            "resource_hash": e["resource_hash"],
            "resource_name": e["resource_name"],
            "occurrences": e["occurrences"],
            "variants": "|".join(sorted(e["variants"])),
            "example_packs": "|".join(e["example_packs"]),
        })
    row_counts["RESOURCE_DATABASE_UNIQUE.csv"] = _write_rows(
        staging / "RESOURCE_DATABASE_UNIQUE.csv",
        unique_resource_fields,
        unique_resource_rows,
    )

    # --------------------------------------------------------------
    # MESH -> MAT clean master + aggregate DB.
    # --------------------------------------------------------------
    mesh_agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    mesh_field_variants: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    spider_mesh_rows: List[Dict[str, str]] = []

    mesh_out = staging / "MASTER_MESH_TO_MAT.csv"
    f_mesh, w_mesh = _writer(mesh_out, MESH_TO_MAT_FIELDS)
    clean_mesh_mat_rows = 0
    try:
        for row in _iter_csv(required["mesh_to_mat"]):
            if _is_marker(row):
                _marker_entry(marker_stats, row)["mesh_to_mat_rows"] += 1
                continue
            if not _is_outer(row):
                continue
            if not _is_exact(row):
                continue
            if _u(row.get("source_resource_group_type", "")) != "MESH":
                continue
            if _u(row.get("resolved_resource_group_type", "")) != "MAT":
                continue

            out = {
                "source_pack": row.get("source_pack", ""),
                "source_archive": row.get("source_archive", ""),
                "source_apkf_label": row.get("source_apkf_label", ""),
                "mesh_name": row.get("source_resource_name", ""),
                "mesh_hash": _u(row.get("source_resource_hash", "")),
                "mesh_record_index": row.get("source_resource_record_index", ""),
                "mesh_material_field_offset": row.get("source_resource_offset_of_field", ""),
                "serialized_material_pointer": row.get("serialized_pointer_value", ""),
                "mat_name": row.get("resolved_resource_name", ""),
                "mat_hash": _u(row.get("resolved_resource_hash", "")),
                "mat_record_index": row.get("resolved_resource_record_index", ""),
                "match_kind": row.get("resolved_match_kind", ""),
                "resolved_offset_into_resource": row.get("resolved_offset_into_resource", ""),
            }
            w_mesh.writerow(out)
            clean_mesh_mat_rows += 1

            field_key = (out["mesh_hash"], out["mesh_material_field_offset"])
            mesh_field_variants[field_key].add(out["mat_hash"])

            key = (out["mesh_hash"], out["mesh_material_field_offset"], out["mat_hash"])
            e = mesh_agg.get(key)
            if e is None:
                e = {
                    "mesh_names": set(),
                    "mat_names": set(),
                    "occurrences": 0,
                    "packs": set(),
                    "serialized": set(),
                }
                mesh_agg[key] = e
            if out["mesh_name"]:
                e["mesh_names"].add(out["mesh_name"])
            if out["mat_name"]:
                e["mat_names"].add(out["mat_name"])
            e["occurrences"] += 1
            if out["source_pack"]:
                e["packs"].add(out["source_pack"])
            if out["serialized_material_pointer"]:
                e["serialized"].add(out["serialized_material_pointer"])

            if _is_spiderman_mesh(out["mesh_name"], out["mesh_hash"]):
                spider_mesh_rows.append(out)
    finally:
        f_mesh.close()
    row_counts[mesh_out.name] = clean_mesh_mat_rows

    mesh_db_rows = []
    context_mesh_rows = []
    for (mesh_hash, field_off, mat_hash), e in sorted(mesh_agg.items(), key=lambda kv: kv[0]):
        variant_count = len(mesh_field_variants[(mesh_hash, field_off)])
        out = {
            "mesh_hash": mesh_hash,
            "mesh_name": _name_pick(e["mesh_names"]),
            "mesh_material_field_offset": field_off,
            "mat_hash": mat_hash,
            "mat_name": _name_pick(e["mat_names"]),
            "occurrences": e["occurrences"],
            "unique_pack_count": len(e["packs"]),
            "context_variant_count": variant_count,
            "context_dependent": 1 if variant_count > 1 else 0,
            "serialized_pointer_values": "|".join(sorted(e["serialized"])),
            "example_packs": "|".join(sorted(e["packs"])[:8]),
        }
        mesh_db_rows.append(out)
        if variant_count > 1:
            context_mesh_rows.append(out)

    row_counts["MESH_MATERIAL_DATABASE.csv"] = _write_rows(
        staging / "MESH_MATERIAL_DATABASE.csv",
        MESH_MATERIAL_DB_FIELDS,
        mesh_db_rows,
    )
    row_counts["CONTEXT_DEPENDENT_MESH_MATERIALS.csv"] = _write_rows(
        staging / "CONTEXT_DEPENDENT_MESH_MATERIALS.csv",
        MESH_MATERIAL_DB_FIELDS,
        context_mesh_rows,
    )

    # --------------------------------------------------------------
    # MAT -> TEX clean master + aggregate DB.
    # This intentionally streams the very large internal-pointer master.
    # --------------------------------------------------------------
    mat_tex_agg: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    mat_field_variants: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

    # Compact joins for Spider-Man chain.
    mattex_context: Dict[Tuple[str, str, str], List[Tuple[str, ...]]] = defaultdict(list)
    mattex_pack: Dict[Tuple[str, str], List[Tuple[str, ...]]] = defaultdict(list)
    mattex_hash: Dict[str, List[Tuple[str, ...]]] = defaultdict(list)

    mattex_out = staging / "MASTER_MAT_TO_TEX.csv"
    f_mt, w_mt = _writer(mattex_out, MAT_TO_TEX_FIELDS)
    clean_mat_tex_rows = 0
    try:
        for row in _iter_csv(required["internal"]):
            if _is_marker(row):
                _marker_entry(marker_stats, row)["internal_pointer_fixups"] += 1
                continue
            if not _is_outer(row):
                continue
            if not _is_exact(row):
                continue
            if _u(row.get("source_resource_group_type", "")) != "MAT":
                continue
            if _u(row.get("resolved_resource_group_type", "")) != "TEX":
                continue

            out = {
                "source_pack": row.get("source_pack", ""),
                "source_archive": row.get("source_archive", ""),
                "source_apkf_label": row.get("source_apkf_label", ""),
                "mat_name": row.get("source_resource_name", ""),
                "mat_hash": _u(row.get("source_resource_hash", "")),
                "mat_record_index": row.get("source_resource_record_index", ""),
                "material_texture_field_offset": row.get("source_resource_offset_of_field", ""),
                "serialized_texture_pointer": row.get("serialized_pointer_value", ""),
                "tex_name": row.get("resolved_resource_name", ""),
                "tex_hash": _u(row.get("resolved_resource_hash", "")),
                "tex_record_index": row.get("resolved_resource_record_index", ""),
                "match_kind": row.get("resolved_match_kind", ""),
                "resolved_offset_into_resource": row.get("resolved_offset_into_resource", ""),
            }
            w_mt.writerow(out)
            clean_mat_tex_rows += 1

            field_key = (out["mat_hash"], out["material_texture_field_offset"])
            mat_field_variants[field_key].add(out["tex_hash"])

            key = (out["mat_hash"], out["material_texture_field_offset"], out["tex_hash"])
            e = mat_tex_agg.get(key)
            if e is None:
                e = {
                    "mat_names": set(),
                    "tex_names": set(),
                    "occurrences": 0,
                    "packs": set(),
                    "serialized": set(),
                }
                mat_tex_agg[key] = e
            if out["mat_name"]:
                e["mat_names"].add(out["mat_name"])
            if out["tex_name"]:
                e["tex_names"].add(out["tex_name"])
            e["occurrences"] += 1
            if out["source_pack"]:
                e["packs"].add(out["source_pack"])
            if out["serialized_texture_pointer"]:
                e["serialized"].add(out["serialized_texture_pointer"])

            compact = (
                out["material_texture_field_offset"],
                out["serialized_texture_pointer"],
                out["tex_name"],
                out["tex_hash"],
            )
            mattex_context[(out["source_pack"], out["source_archive"], out["mat_hash"])].append(compact)
            mattex_pack[(out["source_pack"], out["mat_hash"])].append(compact)
            mattex_hash[out["mat_hash"]].append(compact)
    finally:
        f_mt.close()
    row_counts[mattex_out.name] = clean_mat_tex_rows

    mattex_db_rows = []
    context_mattex_rows = []
    for (mat_hash, field_off, tex_hash), e in sorted(mat_tex_agg.items(), key=lambda kv: kv[0]):
        variant_count = len(mat_field_variants[(mat_hash, field_off)])
        out = {
            "mat_hash": mat_hash,
            "mat_name": _name_pick(e["mat_names"]),
            "material_texture_field_offset": field_off,
            "tex_hash": tex_hash,
            "tex_name": _name_pick(e["tex_names"]),
            "occurrences": e["occurrences"],
            "unique_pack_count": len(e["packs"]),
            "context_variant_count": variant_count,
            "context_dependent": 1 if variant_count > 1 else 0,
            "serialized_pointer_values": "|".join(sorted(e["serialized"])),
            "example_packs": "|".join(sorted(e["packs"])[:8]),
        }
        mattex_db_rows.append(out)
        if variant_count > 1:
            context_mattex_rows.append(out)

    row_counts["MATERIAL_TEXTURE_DATABASE.csv"] = _write_rows(
        staging / "MATERIAL_TEXTURE_DATABASE.csv",
        MATERIAL_TEXTURE_DB_FIELDS,
        mattex_db_rows,
    )
    row_counts["CONTEXT_DEPENDENT_MATERIAL_TEXTURES.csv"] = _write_rows(
        staging / "CONTEXT_DEPENDENT_MATERIAL_TEXTURES.csv",
        MATERIAL_TEXTURE_DB_FIELDS,
        context_mattex_rows,
    )

    # --------------------------------------------------------------
    # External resource references.
    # Production copy = outer_row only. Marker refs retained separately.
    # --------------------------------------------------------------
    refs_path = required["refs"]
    with refs_path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        ref_fields = list(reader.fieldnames or [])
        clean_ref_file, clean_ref_writer = _writer(
            staging / "MASTER_RESOURCE_REFERENCE_FIXUPS_CLEAN.csv", ref_fields
        )
        marker_ref_file, marker_ref_writer = _writer(
            staging / "MARKER_RESOURCE_REFERENCE_FIXUPS_RAW.csv", ref_fields
        )
        tex_file, tex_writer = _writer(staging / "MASTER_TEX_REFERENCES_CLEAN.csv", ref_fields)
        mesh_file, mesh_writer = _writer(staging / "MASTER_MESH_REFERENCES_CLEAN.csv", ref_fields)
        mat_file, mat_writer = _writer(staging / "MASTER_MAT_REFERENCES_CLEAN.csv", ref_fields)

        clean_refs = marker_refs = tex_refs = mesh_refs = mat_refs = 0
        clean_ref_types: Counter[str] = Counter()
        try:
            for raw in reader:
                row = {str(k): str(v or "") for k, v in raw.items()}
                if _is_marker(row):
                    marker_ref_writer.writerow(row)
                    marker_refs += 1
                    _marker_entry(marker_stats, row)["resource_reference_rows"] += 1
                    continue
                if not _is_outer(row):
                    continue

                clean_ref_writer.writerow(row)
                clean_refs += 1
                typ = _u(row.get("resource_type", ""))
                clean_ref_types[typ] += 1
                if typ == "TEX":
                    tex_writer.writerow(row)
                    tex_refs += 1
                elif typ == "MESH":
                    mesh_writer.writerow(row)
                    mesh_refs += 1
                elif typ == "MAT":
                    mat_writer.writerow(row)
                    mat_refs += 1
        finally:
            clean_ref_file.close()
            marker_ref_file.close()
            tex_file.close()
            mesh_file.close()
            mat_file.close()

    row_counts["MASTER_RESOURCE_REFERENCE_FIXUPS_CLEAN.csv"] = clean_refs
    row_counts["MARKER_RESOURCE_REFERENCE_FIXUPS_RAW.csv"] = marker_refs
    row_counts["MASTER_TEX_REFERENCES_CLEAN.csv"] = tex_refs
    row_counts["MASTER_MESH_REFERENCES_CLEAN.csv"] = mesh_refs
    row_counts["MASTER_MAT_REFERENCES_CLEAN.csv"] = mat_refs

    # --------------------------------------------------------------
    # Spider-Man MESH -> MAT -> TEX chain.
    # Prefer exact package+archive context; fall back conservatively.
    # --------------------------------------------------------------
    chain_rows: List[Dict[str, Any]] = []
    seen_chain: Set[Tuple[str, ...]] = set()

    for m in spider_mesh_rows:
        exact_key = (m["source_pack"], m["source_archive"], m["mat_hash"])
        pack_key = (m["source_pack"], m["mat_hash"])
        tex_rows = mattex_context.get(exact_key, [])
        scope = "SAME_ARCHIVE"

        if not tex_rows:
            tex_rows = mattex_pack.get(pack_key, [])
            scope = "SAME_PACK"
        if not tex_rows:
            tex_rows = mattex_hash.get(m["mat_hash"], [])
            scope = "MAT_HASH_FALLBACK"

        if not tex_rows:
            key = (
                m["source_pack"], m["source_archive"], m["mesh_hash"],
                m["mesh_material_field_offset"], m["mat_hash"], "", ""
            )
            if key not in seen_chain:
                seen_chain.add(key)
                chain_rows.append({
                    "source_pack": m["source_pack"],
                    "source_archive": m["source_archive"],
                    "mesh_name": m["mesh_name"],
                    "mesh_hash": m["mesh_hash"],
                    "mesh_material_field_offset": m["mesh_material_field_offset"],
                    "serialized_material_pointer": m["serialized_material_pointer"],
                    "mat_name": m["mat_name"],
                    "mat_hash": m["mat_hash"],
                    "material_texture_field_offset": "",
                    "serialized_texture_pointer": "",
                    "tex_name": "",
                    "tex_hash": "",
                    "join_scope": "NO_TEX_MAPPING",
                })
            continue

        for tex_field, tex_serialized, tex_name, tex_hash in tex_rows:
            key = (
                m["source_pack"], m["source_archive"], m["mesh_hash"],
                m["mesh_material_field_offset"], m["mat_hash"], tex_field, tex_hash
            )
            if key in seen_chain:
                continue
            seen_chain.add(key)
            chain_rows.append({
                "source_pack": m["source_pack"],
                "source_archive": m["source_archive"],
                "mesh_name": m["mesh_name"],
                "mesh_hash": m["mesh_hash"],
                "mesh_material_field_offset": m["mesh_material_field_offset"],
                "serialized_material_pointer": m["serialized_material_pointer"],
                "mat_name": m["mat_name"],
                "mat_hash": m["mat_hash"],
                "material_texture_field_offset": tex_field,
                "serialized_texture_pointer": tex_serialized,
                "tex_name": tex_name,
                "tex_hash": tex_hash,
                "join_scope": scope,
            })

    chain_rows.sort(
        key=lambda r: (
            r["mesh_hash"],
            r["mesh_material_field_offset"],
            r["mat_hash"],
            r["material_texture_field_offset"],
            r["tex_hash"],
            r["source_pack"],
        )
    )
    row_counts["SPIDERMAN_MESH_MAT_TEX_CHAIN.csv"] = _write_rows(
        staging / "SPIDERMAN_MESH_MAT_TEX_CHAIN.csv",
        SPIDERMAN_CHAIN_FIELDS,
        chain_rows,
    )

    # --------------------------------------------------------------
    # Marker diagnostics.
    # --------------------------------------------------------------
    marker_rows = sorted(
        marker_stats.values(),
        key=lambda r: (
            str(r.get("source_pack", "")).lower(),
            str(r.get("source_archive", "")).lower(),
        ),
    )
    row_counts["MARKER_DIAGNOSTICS.csv"] = _write_rows(
        staging / "MARKER_DIAGNOSTICS.csv",
        MARKER_DIAGNOSTIC_FIELDS,
        marker_rows,
    )

    # --------------------------------------------------------------
    # Parse-error diagnostics, including T30.
    # --------------------------------------------------------------
    parse_errors: List[Dict[str, str]] = []
    t30_errors: List[Dict[str, str]] = []
    for err_path in _locate_parse_error_sources(scan_root, master_root):
        if not err_path.exists():
            continue
        for row in _iter_csv(err_path):
            if not any(row.values()):
                continue
            out = {k: row.get(k, "") for k in PARSE_ERROR_FIELDS}
            parse_errors.append(out)
            if (
                _u(out.get("parent_outer_type", "")) == "0X00000030"
                or ".T30." in _u(out.get("source_archive", ""))
                or "_T30_" in _u(out.get("source_apkf_label", ""))
            ):
                t30_errors.append(out)

    parse_errors.sort(key=lambda r: (r["source_pack"].lower(), r["source_archive"].lower()))
    t30_errors.sort(key=lambda r: (r["source_pack"].lower(), r["source_archive"].lower()))
    row_counts["ALL_APKF_PARSE_ERRORS.csv"] = _write_rows(
        staging / "ALL_APKF_PARSE_ERRORS.csv", PARSE_ERROR_FIELDS, parse_errors
    )
    row_counts["T30_PARSE_DIAGNOSTICS.csv"] = _write_rows(
        staging / "T30_PARSE_DIAGNOSTICS.csv", PARSE_ERROR_FIELDS, t30_errors
    )

    # --------------------------------------------------------------
    # Summary.
    # --------------------------------------------------------------
    summary = [
        f"SM3 CLEAN RESOURCE DATABASE {DB_VERSION}",
        "=" * 52,
        "",
        f"Source scan: {scan_root}",
        f"Raw master preserved: {master_root}",
        "",
        "PRODUCTION FILTERS",
        "------------------",
        'source_archive_kind == "outer_row"',
        "MESH -> MAT match == EXACT_START",
        "MAT -> TEX match == EXACT_START",
        'source_archive_kind == "marker" is excluded from production tables',
        "",
        f"Clean resource instances: {clean_resource_rows:,}",
        f"Unique resource identities: {len(resource_unique):,}",
        f"Clean MESH -> MAT rows: {clean_mesh_mat_rows:,}",
        f"Aggregated MESH/material identities: {len(mesh_db_rows):,}",
        f"Context-dependent MESH/material rows: {len(context_mesh_rows):,}",
        f"Clean MAT -> TEX rows: {clean_mat_tex_rows:,}",
        f"Aggregated MAT/texture identities: {len(mattex_db_rows):,}",
        f"Context-dependent MAT/texture rows: {len(context_mattex_rows):,}",
        f"Clean external resource references: {clean_refs:,}",
        f"Clean external TEX references: {tex_refs:,}",
        f"Clean external MESH references: {mesh_refs:,}",
        f"Clean external MAT references: {mat_refs:,}",
        f"Marker package candidates: {marker_package_count:,}",
        f"Marker raw external-reference rows isolated: {marker_refs:,}",
        f"APKF parse errors: {len(parse_errors):,}",
        f"T30 parse errors: {len(t30_errors):,}",
        f"Spider-Man MESH -> MAT -> TEX chain rows: {len(chain_rows):,}",
        "",
        "RESOURCE TYPE COUNTS (CLEAN RESOURCE RECORDS)",
        "---------------------------------------------",
    ]
    for typ, count in sorted(resource_type_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        summary.append(f"{typ or '<blank>'}: {count:,}")

    summary += [
        "",
        "EXTERNAL REFERENCE TYPE COUNTS (CLEAN OUTER-ROW ONLY)",
        "-----------------------------------------------------",
    ]
    for typ, count in sorted(clean_ref_types.items(), key=lambda kv: (-kv[1], kv[0])):
        summary.append(f"{typ or '<blank>'}: {count:,}")

    summary += [
        "",
        "OPEN THESE FIRST",
        "----------------",
        "MASTER_MESH_TO_MAT.csv",
        "MASTER_MAT_TO_TEX.csv",
        "MESH_MATERIAL_DATABASE.csv",
        "MATERIAL_TEXTURE_DATABASE.csv",
        "MASTER_RESOURCE_DATABASE.csv",
        "RESOURCE_DATABASE_UNIQUE.csv",
        "SPIDERMAN_MESH_MAT_TEX_CHAIN.csv",
        "",
        "RESEARCH / DIAGNOSTICS",
        "----------------------",
        "MARKER_DIAGNOSTICS.csv",
        "MARKER_RESOURCE_REFERENCE_FIXUPS_RAW.csv",
        "ALL_APKF_PARSE_ERRORS.csv",
        "T30_PARSE_DIAGNOSTICS.csv",
        "",
        "Raw MASTER_CSV was intentionally left untouched.",
    ]

    (staging / "DATABASE_SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    row_counts["DATABASE_SUMMARY.txt"] = len(summary)

    _write_manifest(staging, row_counts)

    staging.rename(final_root)

    log(f"[116 CLEAN DB] DONE: {final_root}")
    log(
        f"[116 CLEAN DB] MESH->MAT={clean_mesh_mat_rows} "
        f"MAT->TEX={clean_mat_tex_rows} clean_refs={clean_refs} "
        f"marker_refs={marker_refs} T30_errors={len(t30_errors)}"
    )

    return {
        "database_root": str(final_root),
        "database_version": DB_VERSION,
        "resource_instances": clean_resource_rows,
        "unique_resources": len(resource_unique),
        "mesh_to_mat_rows": clean_mesh_mat_rows,
        "mesh_material_database_rows": len(mesh_db_rows),
        "context_dependent_mesh_material_rows": len(context_mesh_rows),
        "mat_to_tex_rows": clean_mat_tex_rows,
        "material_texture_database_rows": len(mattex_db_rows),
        "context_dependent_material_texture_rows": len(context_mattex_rows),
        "clean_resource_reference_rows": clean_refs,
        "marker_reference_rows": marker_refs,
        "parse_errors": len(parse_errors),
        "t30_parse_errors": len(t30_errors),
        "spiderman_chain_rows": len(chain_rows),
    }
