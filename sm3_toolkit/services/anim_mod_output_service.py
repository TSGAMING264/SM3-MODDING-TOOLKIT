from __future__ import annotations

import json
import re
import shutil
import struct
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

ANIM_FOURCC = "ANIM"
ANIM_VERSION = 0x00020116
_HASH_RE = re.compile(r"0x([0-9A-Fa-f]{8})")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_. -]+")


class AnimModOutputError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnimIdentity:
    pack: str
    archive: str
    archive_index: int
    archive_hash: int
    archive_type: int
    resource_type: str
    resource_hash: int
    resource_name: str
    catalog_relative_path: str
    catalog_file: str

    @property
    def target_filename(self) -> str:
        return f"0x{self.resource_hash:08X}.{self.resource_name}.anim"


@dataclass
class AnimModBuildResult:
    source_anim: str
    source_size: int
    source_hash: int
    source_version: int
    identity: AnimIdentity
    mod_name: str
    mod_root: str
    output_anim: str
    output_size: int
    manifest_json: str
    install_readme: str
    zip_path: str

    def to_dict(self) -> dict:
        out = asdict(self)
        out["identity"] = asdict(self.identity)
        return out


def _clean_mod_name(name: str) -> str:
    name = _SAFE_NAME_RE.sub("_", str(name or "").strip()).strip(" ._")
    return name[:96] or "SM3 ANIM Mod"


def inspect_anim_identity(path: str | Path) -> tuple[int, int, int]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ANIM not found: {path}")
    data = path.read_bytes()
    if len(data) < 0x18:
        raise AnimModOutputError(f"ANIM is too small: {len(data)} bytes")
    resource_hash = struct.unpack_from("<I", data, 0x04)[0]
    version = struct.unpack_from("<I", data, 0x14)[0]
    askl_hash = struct.unpack_from("<I", data, 0x10)[0]
    if version != ANIM_VERSION:
        raise AnimModOutputError(
            f"Unsupported ANIM version 0x{version:08X}; expected 0x{ANIM_VERSION:08X}."
        )
    return resource_hash, version, askl_hash


def _candidate_catalogs(search_root: Path) -> list[Path]:
    """Find the extraction catalog from top-root, READY root, or a nested pack folder.

    v5.2.133 deliberately uses content/location discovery rather than folder-name
    blacklists. A path containing words such as WOS is not rejected.
    """
    search_root = Path(search_root)
    candidates: list[Path] = []

    def add(p: Path) -> None:
        try:
            if p.is_file() and p.name.lower() == "filelist.apkf.txt" and p not in candidates:
                candidates.append(p)
        except OSError:
            pass

    # Direct/common forms.
    add(search_root / "06_MOD_LOADER_READY" / "filelist.apkf.txt")
    add(search_root / "filelist.apkf.txt")

    # If the user selected 06_MOD_LOADER_READY/CH_SPIDERMAN or another nested
    # child, walk a few ancestors and test their standard locations.
    cur = search_root
    for _ in range(6):
        add(cur / "filelist.apkf.txt")
        add(cur / "06_MOD_LOADER_READY" / "filelist.apkf.txt")
        if cur.parent == cur:
            break
        cur = cur.parent

    # Recursive fallback under the selected root. Avoid recursively searching an
    # output tree forever by collecting paths before any build starts.
    try:
        for p in list(search_root.rglob("filelist.apkf.txt")):
            add(p)
    except OSError:
        pass
    return candidates


def _parse_catalog_line(line: str, catalog: Path) -> Optional[AnimIdentity]:
    raw = line.strip("\r\n")
    if not raw or raw.startswith("#"):
        return None
    parts = raw.split("\t")
    if len(parts) < 9:
        return None
    pack, archive, index_text, archive_hash_text, archive_type_text, resource_type, hash_text, name, rel = parts[:9]
    if resource_type.strip().upper() != ANIM_FOURCC:
        return None
    try:
        archive_index = int(index_text, 0)
        archive_hash = int(archive_hash_text, 0)
        archive_type = int(archive_type_text, 0)
        resource_hash = int(hash_text, 0)
    except Exception:
        return None
    return AnimIdentity(
        pack=pack.strip(),
        archive=archive.strip(),
        archive_index=archive_index,
        archive_hash=archive_hash,
        archive_type=archive_type,
        resource_type=resource_type.strip().upper(),
        resource_hash=resource_hash & 0xFFFFFFFF,
        resource_name=name.strip(),
        catalog_relative_path=rel.strip(),
        catalog_file=str(catalog),
    )


def resolve_anim_owner(
    anim_path: str | Path,
    extracted_pack_root: str | Path,
) -> AnimIdentity:
    anim_path = Path(anim_path)
    root = Path(extracted_pack_root)
    if not root.is_dir():
        raise FileNotFoundError(f"Extracted pack folder not found: {root}")
    resource_hash, _version, _askl_hash = inspect_anim_identity(anim_path)
    catalogs = _candidate_catalogs(root)
    if not catalogs:
        raise AnimModOutputError(
            "No filelist.apkf.txt was found from the selected extraction path. "
            "You may select the top extracted pack folder, 06_MOD_LOADER_READY, or its nested pack folder."
        )

    matches: list[AnimIdentity] = []
    for catalog in catalogs:
        try:
            with catalog.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    row = _parse_catalog_line(line, catalog)
                    if row and row.resource_hash == resource_hash:
                        matches.append(row)
        except OSError:
            continue

    if not matches:
        raise AnimModOutputError(
            f"ANIM 0x{resource_hash:08X} was not found in any filelist.apkf.txt under {root}."
        )

    # Prefer a path already describing the canonical mod-loader route.
    matches.sort(key=lambda r: (
        0 if "06_MOD_LOADER_READY" in r.catalog_file.replace("\\", "/").upper() else 1,
        len(r.catalog_file),
        r.pack.lower(),
        r.archive.lower(),
    ))
    chosen = matches[0]
    conflicting = {(m.pack, m.archive, m.resource_name) for m in matches}
    if len(conflicting) > 1:
        raise AnimModOutputError(
            f"ANIM 0x{resource_hash:08X} has multiple ownership records: "
            + ", ".join(f"{p}/{a}/{n}" for p, a, n in sorted(conflicting))
        )
    return chosen


def _resolved(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return Path(path).absolute()


def _is_within(child: Path, parent: Path) -> bool:
    child = _resolved(child)
    parent = _resolved(parent)
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _validate_output_location(rebuilt_anim: Path, extracted_root: Path, output_root: Path) -> None:
    # Output inside the extracted/source/rebuild tree can cause recursive path
    # growth on Windows (WinError 206) and can contaminate catalog discovery.
    out = _resolved(output_root)
    extracted = _resolved(extracted_root)
    rebuilt_parent = _resolved(rebuilt_anim.parent)
    if _is_within(out, extracted):
        raise AnimModOutputError(
            "Output folder is inside the extracted pack tree. Choose a short separate folder such as C:\\SM3_ANIM_TEST."
        )
    if _is_within(out, rebuilt_parent):
        raise AnimModOutputError(
            "Output folder is inside the rebuilt-ANIM/source folder. Choose a short separate folder such as C:\\SM3_ANIM_TEST."
        )


def build_anim_mod_loader_output(
    rebuilt_anim: str | Path,
    extracted_pack_root: str | Path,
    output_root: str | Path,
    mod_name: str = "SM3 ANIM Mod",
    make_zip: bool = True,
) -> AnimModBuildResult:
    rebuilt_anim = Path(rebuilt_anim)
    output_root = Path(output_root)
    extracted_pack_root = Path(extracted_pack_root)
    _validate_output_location(rebuilt_anim, extracted_pack_root, output_root)
    resource_hash, version, askl_hash = inspect_anim_identity(rebuilt_anim)
    identity = resolve_anim_owner(rebuilt_anim, extracted_pack_root)
    if identity.resource_hash != resource_hash:
        raise AnimModOutputError("Internal identity mismatch while building mod output.")

    mod_name = _clean_mod_name(mod_name)
    build_root = output_root / "XESM3_MOD_READY" / mod_name
    target_dir = build_root / identity.pack / identity.archive
    target_dir.mkdir(parents=True, exist_ok=True)
    target_anim = target_dir / identity.target_filename
    shutil.copy2(rebuilt_anim, target_anim)

    copied_hash, copied_version, copied_askl = inspect_anim_identity(target_anim)
    if copied_hash != resource_hash or copied_version != version or copied_askl != askl_hash:
        raise AnimModOutputError("Post-copy ANIM identity verification failed.")

    manifest_path = build_root / "ANIM_MOD_IDENTITY.json"
    manifest = {
        "format": "XESM3_SM3_ANIM_MOD_OUTPUT_V1",
        "mod_name": mod_name,
        "resource": {
            "type": "ANIM",
            "hash": f"0x{resource_hash:08X}",
            "name": identity.resource_name,
            "filename": identity.target_filename,
            "size_bytes": target_anim.stat().st_size,
            "version": f"0x{version:08X}",
            "askl_hash": f"0x{askl_hash:08X}",
        },
        "owner": {
            "pack": identity.pack,
            "archive": identity.archive,
            "archive_index": identity.archive_index,
            "archive_hash": f"0x{identity.archive_hash:08X}",
            "archive_type": f"0x{identity.archive_type:X}",
            "catalog": identity.catalog_file,
        },
        "install_relative_path": f"{mod_name}/{identity.pack}/{identity.archive}/{identity.target_filename}",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme_path = build_root / "README_INSTALL.txt"
    readme_path.write_text(
        "XESM3 SM3 ANIM Mod Output\n"
        "=============================\n\n"
        "Copy this entire mod folder into the Spider-Man 3\\Mods\\ folder.\n\n"
        f"Mod folder: {mod_name}\n"
        f"Pack: {identity.pack}\n"
        f"APKF owner: {identity.archive}\n"
        f"ANIM: {identity.target_filename}\n"
        f"ANIM size: {target_anim.stat().st_size} bytes\n"
        f"ASKL hash: 0x{askl_hash:08X}\n\n"
        "The toolkit resolved pack/APKF ownership from filelist.apkf.txt and preserved the ANIM target hash.\n\n"
        "Enable the mod in Spider-Man 3\\Mods\\mods.config.ini with:\n"
        "[EnabledMods]\n"
        f"{mod_name}=100\n\n"
        "XESM3 uses 100 = enabled and 0 = disabled.\n",
        encoding="utf-8",
    )

    enable_note_path = build_root / "XESM3_ENABLE_THIS_MOD.txt"
    enable_note_path.write_text(
        "Add or update this entry in Spider-Man 3\\Mods\\mods.config.ini:\n\n"
        "[EnabledMods]\n"
        f"{mod_name}=100\n\n"
        "100 = enabled\n0 = disabled\n",
        encoding="utf-8",
    )

    zip_path = output_root / f"{mod_name.replace(' ', '_')}_XESM3_READY.zip"
    if make_zip:
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in sorted(build_root.rglob("*")):
                if p.is_file():
                    arc = Path(mod_name) / p.relative_to(build_root)
                    zf.write(p, arc.as_posix())
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad:
                raise AnimModOutputError(f"ZIP verification failed at {bad}")
    else:
        zip_path = Path("")

    return AnimModBuildResult(
        source_anim=str(rebuilt_anim),
        source_size=rebuilt_anim.stat().st_size,
        source_hash=resource_hash,
        source_version=version,
        identity=identity,
        mod_name=mod_name,
        mod_root=str(build_root),
        output_anim=str(target_anim),
        output_size=target_anim.stat().st_size,
        manifest_json=str(manifest_path),
        install_readme=str(readme_path),
        zip_path=str(zip_path) if str(zip_path) else "",
    )


@dataclass
class AnimSwapBuildResult:
    target_anim: str
    donor_anim: str
    target_hash: int
    donor_hash: int
    version: int
    askl_hash: int
    identity: AnimIdentity
    mod_name: str
    mod_root: str
    output_anim: str
    output_size: int
    manifest_json: str
    install_readme: str
    zip_path: str

    def to_dict(self) -> dict:
        out = asdict(self)
        out["identity"] = asdict(self.identity)
        return out


def inspect_anim_swap_compatibility(
    target_anim: str | Path,
    donor_anim: str | Path,
) -> dict[str, object]:
    """Inspect the compatibility gate used by XESM3's loose ANIM redirector.

    XESM3 v0.1.6.1 accepts v0x20116 donor ANIMs for a target runtime ANIM when
    the ASKL/skeleton hash matches. Different file sizes and compressed layouts
    can use XESM3's process-lifetime shadow route, so the old PCPACK slot-size
    restriction is intentionally not part of this compatibility check.
    """
    target_anim = Path(target_anim)
    donor_anim = Path(donor_anim)
    target_hash, target_version, target_askl = inspect_anim_identity(target_anim)
    donor_hash, donor_version, donor_askl = inspect_anim_identity(donor_anim)

    target_bytes = target_anim.read_bytes()
    donor_bytes = donor_anim.read_bytes()

    def u32(data: bytes, off: int) -> int:
        return struct.unpack_from("<I", data, off)[0] if len(data) >= off + 4 else 0

    result = {
        "compatible": False,
        "target_hash": target_hash,
        "donor_hash": donor_hash,
        "target_version": target_version,
        "donor_version": donor_version,
        "target_askl": target_askl,
        "donor_askl": donor_askl,
        "target_size": len(target_bytes),
        "donor_size": len(donor_bytes),
        "target_frame_count": u32(target_bytes, 0x30),
        "donor_frame_count": u32(donor_bytes, 0x30),
        "target_track_count": u32(target_bytes, 0x38),
        "donor_track_count": u32(donor_bytes, 0x38),
        "target_post_scale_count": u32(target_bytes, 0x3C),
        "donor_post_scale_count": u32(donor_bytes, 0x3C),
        "same_size": len(target_bytes) == len(donor_bytes),
        "same_track_count": u32(target_bytes, 0x38) == u32(donor_bytes, 0x38),
        "same_pose_masks": (
            len(target_bytes) >= 0xB0 and len(donor_bytes) >= 0xB0 and
            target_bytes[0x48:0xB0] == donor_bytes[0x48:0xB0]
        ),
        "reason": "",
    }

    if len(target_bytes) < 0xB0 or len(donor_bytes) < 0xB0:
        result["reason"] = "Both ANIM files must contain the full 0xB0 v0x20116 header."
        return result
    target_bitstream_token = u32(target_bytes, 0x44)
    donor_bitstream_token = u32(donor_bytes, 0x44)
    if target_bitstream_token == 0 or donor_bitstream_token == 0:
        result["reason"] = "Target or donor ANIM has an invalid zero bitstream token."
        return result

    if target_version != ANIM_VERSION or donor_version != ANIM_VERSION:
        result["reason"] = (
            f"Both ANIM files must be version 0x{ANIM_VERSION:08X}. "
            f"Target=0x{target_version:08X}, donor=0x{donor_version:08X}."
        )
        return result
    if target_askl != donor_askl:
        result["reason"] = (
            f"ASKL / skeleton mismatch: target 0x{target_askl:08X}, "
            f"donor 0x{donor_askl:08X}. XESM3 keeps the same-skeleton safety gate."
        )
        return result
    if len(donor_bytes) > 64 * 1024 * 1024:
        result["reason"] = "Donor ANIM exceeds XESM3's 64 MiB shadow-allocation safety cap."
        return result

    result["compatible"] = True
    result["reason"] = (
        "Compatible with XESM3: version and ASKL/skeleton match. "
        "Different ANIM size, frame count, track count, or pose layout is allowed; "
        "XESM3 chooses the appropriate runtime ANIM route."
    )
    return result


def _validate_swap_output_location(extracted_root: Path, output_root: Path) -> None:
    """Guided swap output only needs to stay outside the extracted catalog tree.

    Unlike codec/rebuild output, this builder does not recursively scan the donor's
    parent folder, so users may safely choose an Output subfolder beside an external
    donor file.
    """
    out = _resolved(Path(output_root))
    extracted = _resolved(Path(extracted_root))
    if _is_within(out, extracted):
        raise AnimModOutputError(
            "Output folder is inside the extracted pack tree. Choose a separate output folder such as C:\\SM3_ANIM_MODS."
        )


def _u32_loose(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0] if len(data) >= off + 4 else 0


def build_anim_swap_xesm3_output(
    target_anim: str | Path,
    donor_anim: str | Path,
    extracted_pack_root: str | Path,
    output_root: str | Path,
    mod_name: str = "SM3 ANIM Swap",
    make_zip: bool = True,
) -> AnimSwapBuildResult:
    """Build an unrestricted WoS-style target <- donor ANIM swap as an XESM3 loose mod.

    v5.2.141 intentionally does *not* enforce donor compatibility. The target ANIM
    is used to resolve the stock resource identity and PACK/APKF owner. The donor
    file is copied byte-for-byte under the target filename/path. This gives users
    the same freedom-first selection model as the WoS-style swap workflow.

    XESM3/the game still decides what actually works at runtime. A mismatched or
    malformed donor can fail, be ignored, animate incorrectly, or crash; the
    Toolkit does not block the user from creating that experiment.
    """
    target_anim = Path(target_anim)
    donor_anim = Path(donor_anim)
    extracted_pack_root = Path(extracted_pack_root)
    output_root = Path(output_root)

    if not target_anim.is_file():
        raise FileNotFoundError(f"Target / swap-out ANIM not found: {target_anim}")
    if not donor_anim.is_file():
        raise FileNotFoundError(f"Replacement / swap-in ANIM not found: {donor_anim}")
    if not extracted_pack_root.is_dir():
        raise FileNotFoundError(f"Extracted pack folder not found: {extracted_pack_root}")

    _validate_swap_output_location(extracted_pack_root, output_root)

    # The target must be a resolvable SM3 ANIM because its stock identity tells us
    # where XESM3 should intercept the resource. Donor compatibility is NOT gated.
    target_hash, version, askl_hash = inspect_anim_identity(target_anim)
    target_bytes = target_anim.read_bytes()
    donor_bytes = donor_anim.read_bytes()
    donor_hash = _u32_loose(donor_bytes, 0x04)
    donor_askl = _u32_loose(donor_bytes, 0x10)
    donor_version = _u32_loose(donor_bytes, 0x14)

    identity = resolve_anim_owner(target_anim, extracted_pack_root)
    if identity.resource_hash != target_hash:
        raise AnimModOutputError("Target catalog identity mismatch while building XESM3 ANIM swap.")

    mod_name = _clean_mod_name(mod_name)
    build_root = output_root / "XESM3_MOD_READY" / mod_name
    target_dir = build_root / identity.pack / identity.archive
    target_dir.mkdir(parents=True, exist_ok=True)
    output_anim = target_dir / identity.target_filename
    shutil.copy2(donor_anim, output_anim)

    # Freedom mode verification checks only that the donor bytes were copied exactly.
    copied_bytes = output_anim.read_bytes()
    if copied_bytes != donor_bytes:
        raise AnimModOutputError("Post-copy donor byte-identity verification failed.")

    manifest_path = build_root / "ANIM_SWAP_IDENTITY.json"
    manifest = {
        "format": "XESM3_SM3_ANIM_SWAP_V2_UNRESTRICTED",
        "mod_name": mod_name,
        "mode": "UNRESTRICTED_FREEDOM",
        "target": {
            "hash": f"0x{target_hash:08X}",
            "name": identity.resource_name,
            "filename": identity.target_filename,
            "source_file": str(target_anim),
            "size_bytes": len(target_bytes),
            "frame_count": _u32_loose(target_bytes, 0x30),
            "track_count": _u32_loose(target_bytes, 0x38),
            "version": f"0x{version:08X}",
            "askl_hash": f"0x{askl_hash:08X}",
        },
        "donor": {
            "internal_source_hash": f"0x{donor_hash:08X}",
            "source_file": str(donor_anim),
            "size_bytes": len(donor_bytes),
            "frame_count": _u32_loose(donor_bytes, 0x30),
            "track_count": _u32_loose(donor_bytes, 0x38),
            "version_raw": f"0x{donor_version:08X}",
            "askl_hash_raw": f"0x{donor_askl:08X}",
        },
        "compatibility_gate": {
            "enabled": False,
            "result": "NOT_CHECKED_BY_TOOLKIT",
            "note": (
                "v5.2.141 freedom mode intentionally does not block ASKL, version, size, "
                "track-count, frame-count, or layout differences. XESM3/game runtime behavior is user-tested."
            ),
        },
        "owner": {
            "pack": identity.pack,
            "archive": identity.archive,
            "archive_index": identity.archive_index,
            "archive_hash": f"0x{identity.archive_hash:08X}",
            "archive_type": f"0x{identity.archive_type:X}",
            "catalog": identity.catalog_file,
        },
        "install_relative_path": f"{mod_name}/{identity.pack}/{identity.archive}/{identity.target_filename}",
        "xesm3_runtime_identity_note": (
            "The loose file is named/routed as the TARGET resource while the SWAP-IN donor bytes are copied unchanged. "
            "The Toolkit does not make a compatibility decision for the donor."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    readme_path = build_root / "README_INSTALL.txt"
    readme_path.write_text(
        "XESM3 SM3 ANIMATION SWAP — UNRESTRICTED MODE\n"
        "==============================================\n\n"
        "Copy this entire mod folder into Spider-Man 3\\Mods\\.\n\n"
        f"Mod folder: {mod_name}\n"
        f"Swap OUT target: 0x{target_hash:08X}.{identity.resource_name}.anim\n"
        f"Swap IN donor internal hash (raw): 0x{donor_hash:08X}\n"
        f"Pack: {identity.pack}\n"
        f"APKF: {identity.archive}\n\n"
        "This is an XESM3 loose-file swap. The original PCPACK is not modified.\n"
        "The Toolkit intentionally performs NO donor compatibility gate in this mode.\n"
        "Any .anim selected as SWAP IN is copied byte-for-byte under the SWAP OUT target path.\n"
        "Incompatible or malformed animation data may fail, be ignored, animate incorrectly, or crash at runtime.\n\n"
        "Enable the mod in Spider-Man 3\\Mods\\mods.config.ini:\n"
        "[EnabledMods]\n"
        f"{mod_name}=100\n\n"
        "100 = enabled\n0 = disabled\n",
        encoding="utf-8",
    )

    enable_note_path = build_root / "XESM3_ENABLE_THIS_MOD.txt"
    enable_note_path.write_text(
        "Add or update this entry in Spider-Man 3\\Mods\\mods.config.ini:\n\n"
        "[EnabledMods]\n"
        f"{mod_name}=100\n\n"
        "100 = enabled\n0 = disabled\n",
        encoding="utf-8",
    )

    zip_path = output_root / f"{mod_name.replace(' ', '_')}_XESM3_READY.zip"
    if make_zip:
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in sorted(build_root.rglob("*")):
                if p.is_file():
                    arc = Path(mod_name) / p.relative_to(build_root)
                    zf.write(p, arc.as_posix())
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            if bad:
                raise AnimModOutputError(f"ZIP verification failed at {bad}")
    else:
        zip_path = Path("")

    return AnimSwapBuildResult(
        target_anim=str(target_anim),
        donor_anim=str(donor_anim),
        target_hash=target_hash,
        donor_hash=donor_hash,
        version=version,
        askl_hash=askl_hash,
        identity=identity,
        mod_name=mod_name,
        mod_root=str(build_root),
        output_anim=str(output_anim),
        output_size=output_anim.stat().st_size,
        manifest_json=str(manifest_path),
        install_readme=str(readme_path),
        zip_path=str(zip_path) if str(zip_path) else "",
    )
