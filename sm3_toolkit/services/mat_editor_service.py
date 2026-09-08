from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re
import struct


class MATEditorError(RuntimeError):
    pass


# Hashes are grounded in the SM3 CH_SPIDERMAN material family and the shared
# NGL shader names already identified in the project. Unknown hashes remain
# hash-only instead of being assigned guessed names.
SHADER_NAMES: dict[int, str] = {
    0x99A1E0EC: "sm_phat",
    0x64BDFE4A: "sm_babyphat",
    0xFA4ABAD3: "SMTranslucent",
    0xFC097C8A: "SMSimple",
    0xA693F062: "sm_phatpalettecharnormal",
    0x2B7A650F: "SM3 character/web shader",
    0xAB316696: "SM3 PS3 red-suit shader",
}


@dataclass(frozen=True)
class ShaderProfile:
    shader_hash: int
    name: str
    float_ranges: tuple[tuple[int, int], ...]
    confidence: str
    note: str


# End offsets are inclusive. 0x2B7A650F's 0x40-0x7C block is confirmed live
# in game by the ch_spidermanred/backspider tests. Other ranges are conservative
# structural profiles observed in the real CH_SPIDERMAN MAT family and are
# explicitly labeled experimental in the UI.
SHADER_PROFILES: dict[int, ShaderProfile] = {
    0x2B7A650F: ShaderProfile(
        0x2B7A650F,
        "SM3 character/web shader",
        ((0x40, 0x7C),),
        "CONFIRMED IN GAME",
        "0x40-0x7C is a live material/shader float block on Spider-Man character materials.",
    ),
    0x99A1E0EC: ShaderProfile(
        0x99A1E0EC,
        "sm_phat",
        ((0x40, 0x74),),
        "EXPERIMENTAL",
        "Conservative float block inferred from the 160-byte SM3 sm_phat layout.",
    ),
    0x64BDFE4A: ShaderProfile(
        0x64BDFE4A,
        "sm_babyphat",
        ((0x38, 0x6C),),
        "EXPERIMENTAL",
        "Conservative float block inferred from the 136-byte SM3 sm_babyphat layout.",
    ),
    0xA693F062: ShaderProfile(
        0xA693F062,
        "sm_phatpalettecharnormal",
        ((0x40, 0xB4),),
        "EXPERIMENTAL",
        "Candidate shader-constant region observed in the 184-byte PS3 character material.",
    ),
    0xFA4ABAD3: ShaderProfile(
        0xFA4ABAD3,
        "SMTranslucent",
        ((0x40, 0x40),),
        "EXPERIMENTAL",
        "Single trailing 32-bit value in the 68-byte SM3 translucent layout.",
    ),
    0xFC097C8A: ShaderProfile(
        0xFC097C8A,
        "SMSimple",
        ((0x40, 0x40),),
        "EXPERIMENTAL",
        "Single trailing 32-bit value in the 68-byte SM3 simple layout.",
    ),
    0xAB316696: ShaderProfile(
        0xAB316696,
        "SM3 PS3 red-suit shader",
        (),
        "READ ONLY",
        "44-byte material has no confirmed standalone float block yet.",
    ),
}


@dataclass
class MATParameter:
    offset: int
    name: str
    kind: str
    group: str
    editable: bool
    original_value: object
    value: object
    note: str = ""

    @property
    def offset_text(self) -> str:
        return f"0x{self.offset:04X}"


@dataclass
class MATDocument:
    path: Path
    original: bytes
    data: bytearray
    wrap_shell: bytes | None
    resource_word: int
    material_hash: int
    shader_hash: int
    header_value: int
    profile: ShaderProfile | None

    @property
    def is_wrap(self) -> bool:
        return self.wrap_shell is not None

    @property
    def shader_name(self) -> str:
        if self.profile:
            return self.profile.name
        return SHADER_NAMES.get(self.shader_hash, "Unknown shader")

    @property
    def filename_material_hash(self) -> int | None:
        m = re.match(r"^0x([0-9A-Fa-f]{8})\.", self.path.name)
        if not m:
            return None
        try:
            return int(m.group(1), 16)
        except ValueError:
            return None

    @property
    def hash_matches_filename(self) -> bool | None:
        expected = self.filename_material_hash
        return None if expected is None else expected == self.material_hash

    @property
    def dirty(self) -> bool:
        return bytes(self.data) != self.original


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _f32(data: bytes | bytearray, offset: int) -> float:
    return struct.unpack_from("<f", data, offset)[0]


def load_mat(path: str | Path) -> MATDocument:
    path = Path(path)
    if not path.is_file():
        raise MATEditorError(f"MAT file not found: {path}")

    lower_name = path.name.lower()
    wrap_shell: bytes | None = None
    if lower_name.endswith(".wrap.mat"):
        try:
            from sm3_toolkit.services.wrap_output_service import inspect_wrap_bytes
            wrap_shell = path.read_bytes()
            info = inspect_wrap_bytes(wrap_shell)
            if info.component_count < 1:
                raise MATEditorError("NativeWRAP MAT has no serialized MAT component.")
            start = info.component_offsets[0]
            size = info.component_sizes[0]
            raw = wrap_shell[start:start + size]
        except MATEditorError:
            raise
        except Exception as exc:
            raise MATEditorError(f"Could not unwrap NativeWRAP MAT: {exc}") from exc
    elif lower_name.endswith(".mat"):
        raw = path.read_bytes()
    else:
        raise MATEditorError("Choose a Spider-Man 3 .mat or .wrap.mat file.")

    if len(raw) < 0x0C:
        raise MATEditorError("MAT component is too small to contain the SM3 material header.")

    resource_word = _u32(raw, 0x00)
    material_hash = _u32(raw, 0x04)
    shader_hash = _u32(raw, 0x08)
    header_value = _u32(raw, 0x0C) if len(raw) >= 0x10 else 0
    profile = SHADER_PROFILES.get(shader_hash)

    return MATDocument(
        path=path,
        original=raw,
        data=bytearray(raw),
        wrap_shell=wrap_shell,
        resource_word=resource_word,
        material_hash=material_hash,
        shader_hash=shader_hash,
        header_value=header_value,
        profile=profile,
    )


def editable_float_offsets(doc: MATDocument) -> set[int]:
    out: set[int] = set()
    if not doc.profile:
        return out
    for start, end in doc.profile.float_ranges:
        for off in range(start, end + 1, 4):
            if off + 4 <= len(doc.data):
                out.add(off)
    return out


def group_for_offset(offset: int) -> str:
    if 0x40 <= offset <= 0x4C:
        return "A / 0x40-0x4C"
    if 0x50 <= offset <= 0x5C:
        return "B / 0x50-0x5C"
    if 0x60 <= offset <= 0x6C:
        return "C / 0x60-0x6C"
    if 0x70 <= offset <= 0x7C:
        return "D / 0x70-0x7C"
    if offset < 0x40:
        return "Header / references"
    return "Shader constants"


def parameter_name(offset: int, editable: bool) -> str:
    if offset == 0x00:
        return "resource_word"
    if offset == 0x04:
        return "material_hash"
    if offset == 0x08:
        return "shader_hash"
    if offset == 0x0C:
        return "header_value_0C"
    if editable:
        return f"shader_float_{offset:02X}"
    return f"raw_u32_{offset:02X}"


def build_parameters(doc: MATDocument, *, include_raw: bool = False) -> list[MATParameter]:
    editable = editable_float_offsets(doc)
    params: list[MATParameter] = []

    # Always expose core identity fields as read-only rows.
    fixed = [
        (0x00, "resource_word", "UInt32 / read-only", "Header", doc.resource_word, "SM3 material resource/header word."),
        (0x04, "material_hash", "Hash32 / read-only", "Header", doc.material_hash, "Material identity hash."),
        (0x08, "shader_hash", "Hash32 / read-only", "Header", doc.shader_hash, f"Shader: {doc.shader_name}"),
    ]
    if len(doc.data) >= 0x10:
        fixed.append((0x0C, "header_value_0C", "UInt32 / read-only", "Header", doc.header_value, "Unlabeled SM3 header field."))
    for off, name, kind, group, value, note in fixed:
        params.append(MATParameter(off, name, kind, group, False, value, value, note))

    for off in sorted(editable):
        value = _f32(doc.data, off)
        params.append(
            MATParameter(
                off,
                parameter_name(off, True),
                "Float32",
                group_for_offset(off),
                True,
                _f32(doc.original, off),
                value,
                "Editable shader constant. Human-readable semantic name is intentionally not guessed.",
            )
        )

    if include_raw:
        already = {p.offset for p in params}
        for off in range(0, len(doc.data) - 3, 4):
            if off in already:
                continue
            value = _u32(doc.data, off)
            params.append(
                MATParameter(
                    off,
                    parameter_name(off, False),
                    "UInt32 / read-only",
                    group_for_offset(off),
                    False,
                    _u32(doc.original, off),
                    value,
                    "Raw 32-bit field. Read-only to avoid corrupting references/pointers.",
                )
            )

    return sorted(params, key=lambda p: p.offset)


def read_float(doc: MATDocument, offset: int) -> float:
    if offset not in editable_float_offsets(doc):
        raise MATEditorError(f"Offset 0x{offset:X} is not an editable shader-float slot for this profile.")
    return _f32(doc.data, offset)


def write_float(doc: MATDocument, offset: int, value: float) -> None:
    if offset not in editable_float_offsets(doc):
        raise MATEditorError(f"Offset 0x{offset:X} is not an editable shader-float slot for this profile.")
    try:
        value = float(value)
    except Exception as exc:
        raise MATEditorError("Enter a valid numeric float value.") from exc
    if not math.isfinite(value):
        raise MATEditorError("NaN and infinity are not allowed.")
    # Keep values in a broad but finite range. This is intentionally much wider
    # than the diagnostic tests while still rejecting accidental absurd input.
    if abs(value) > 1_000_000.0:
        raise MATEditorError("Value is outside the editor safety range (+/- 1,000,000).")
    struct.pack_into("<f", doc.data, offset, value)


def reset_float(doc: MATDocument, offset: int) -> None:
    if offset not in editable_float_offsets(doc):
        raise MATEditorError(f"Offset 0x{offset:X} is not editable.")
    doc.data[offset:offset + 4] = doc.original[offset:offset + 4]


def reset_all(doc: MATDocument) -> None:
    doc.data[:] = doc.original


def bytes_changed(doc: MATDocument) -> int:
    return sum(1 for a, b in zip(doc.original, doc.data) if a != b)


def changed_offsets(doc: MATDocument) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(doc.original, doc.data)) if a != b]


def hex_context(doc: MATDocument, offset: int, radius: int = 16) -> str:
    start = max(0, offset - radius)
    end = min(len(doc.data), offset + 4 + radius)
    lines = []
    row_start = start - (start % 16)
    for row in range(row_start, end, 16):
        chunk = doc.data[row:min(row + 16, len(doc.data))]
        hexes = " ".join(f"{b:02X}" for b in chunk)
        marker = "  < selected" if row <= offset < row + 16 else ""
        lines.append(f"{row:04X}: {hexes}{marker}")
    return "\n".join(lines)


def save_copy(doc: MATDocument, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(doc.data))
    return output_path


def overwrite_with_backup(doc: MATDocument) -> tuple[Path, Path]:
    path = doc.path
    backup = path.with_suffix(path.suffix + ".bak")
    if doc.wrap_shell is not None:
        from sm3_toolkit.services.wrap_output_service import replace_wrap_component0_exact
        if not backup.exists():
            backup.write_bytes(doc.wrap_shell)
        wrapped = replace_wrap_component0_exact(doc.wrap_shell, bytes(doc.data))
        path.write_bytes(wrapped)
        doc.wrap_shell = wrapped
    else:
        if not backup.exists():
            backup.write_bytes(doc.original)
        path.write_bytes(bytes(doc.data))
    # Keep the session's original component bytes in memory for explicit Reset.
    return path, backup
