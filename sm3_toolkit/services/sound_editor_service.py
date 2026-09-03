from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave


FSB3_MAGIC = b"FSB3"
SM3_PCSSB_ALIGNMENT = 0x8000
FSB3_BASE_HEADER_SIZE = 0x18
FSB3_SAMPLE_HEADER_V3_SIZE = 0x50
SAFE_MP3_BITRATES = (320, 256, 224, 192, 160, 128, 112, 96, 80, 64)
FSOUND_MPEG = 0x00000200
FSOUND_IMAADPCM = 0x00400000
XBOX_IMA_FRAME_BYTES_PER_CHANNEL = 0x24
XBOX_IMA_SAMPLES_PER_FRAME = 64

IMA_STEP_TABLE = (
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658,
    724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
    3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
)
IMA_INDEX_TABLE = (-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8)


class SoundEditorError(RuntimeError):
    pass


@dataclass(frozen=True)
class SoundEntry:
    index: int
    name: str
    fsb_offset: int
    audio_offset: int
    slot_size: int
    sample_count: int
    sample_header_bytes: int
    version: int
    audio_type: str
    sample_rate: int | None = None
    channels: int | None = None
    mode: int = 0
    sample_length: int | None = None
    codec: str = "unknown"

    @property
    def audio_end(self) -> int:
        return self.audio_offset + self.slot_size


@dataclass(frozen=True)
class ReplacementResult:
    source_path: Path
    output_path: Path
    entry: SoundEntry
    replacement_path: Path
    replacement_size: int
    padded_bytes: int
    original_size: int
    output_size: int
    output_sha256: str


@dataclass(frozen=True)
class MusicMixResult:
    output_path: Path
    entry: SoundEntry
    voice_path: Path
    music_path: Path
    duration_seconds: float
    bitrate_kbps: int
    voice_volume_percent: int
    music_volume_percent: int
    loop_music: bool
    output_size: int
    padded_bytes: int
    audio_type: str


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def detect_audio_type(head: bytes) -> str:
    if not head:
        return "Empty"
    if head.startswith(b"ID3"):
        return "MP3 (ID3 tagged)"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "MPEG audio (raw)"
    if head.startswith(b"RIFF") and len(head) >= 12 and head[8:12] == b"WAVE":
        return "WAV / RIFF"
    if head.startswith(b"OggS"):
        return "Ogg Vorbis/Opus"
    if head.startswith(b"fLaC"):
        return "FLAC"
    return "Unknown / raw"


def _decode_sample_name(raw: bytes, fallback: str) -> str:
    name = raw.split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
    return name or fallback


def _parse_entry(data: bytes, fsb_offset: int, index: int) -> SoundEntry | None:
    if fsb_offset < 0 or fsb_offset + FSB3_BASE_HEADER_SIZE > len(data):
        return None
    if data[fsb_offset:fsb_offset + 4] != FSB3_MAGIC:
        return None

    sample_count = _u32(data, fsb_offset + 0x04)
    sample_header_bytes = _u32(data, fsb_offset + 0x08)
    data_size = _u32(data, fsb_offset + 0x0C)
    version = _u32(data, fsb_offset + 0x10)

    # Proven SM3 PCSSB route: one FSB3 sample per 0x8000-aligned sound slot.
    if sample_count != 1:
        return None
    if sample_header_bytes < FSB3_SAMPLE_HEADER_V3_SIZE or sample_header_bytes > 0x10000:
        return None
    if data_size <= 0:
        return None

    sample_offset = fsb_offset + FSB3_BASE_HEADER_SIZE
    if sample_offset + FSB3_SAMPLE_HEADER_V3_SIZE > len(data):
        return None
    sample_header_size = _u16(data, sample_offset)
    if sample_header_size < FSB3_SAMPLE_HEADER_V3_SIZE:
        return None

    audio_offset = fsb_offset + FSB3_BASE_HEADER_SIZE + sample_header_bytes
    audio_end = audio_offset + data_size
    if audio_offset < sample_offset or audio_end > len(data):
        return None

    name = _decode_sample_name(data[sample_offset + 2: sample_offset + 32], f"sound_{index:03d}")

    sample_rate = None
    channels = None
    mode = 0
    sample_length = None
    try:
        sample_length = _u32(data, sample_offset + 32)
        mode = _u32(data, sample_offset + 48)
        sample_rate = _i32(data, sample_offset + 52)
        channels = _u16(data, sample_offset + 62)
        if sample_rate <= 0 or sample_rate > 384000:
            sample_rate = None
        if channels <= 0 or channels > 32:
            channels = None
    except Exception:
        pass

    payload_type = detect_audio_type(data[audio_offset:audio_offset + 16])
    if mode & FSOUND_IMAADPCM:
        codec = "xbox_ima"
        audio_type = "Xbox IMA ADPCM"
    elif mode & FSOUND_MPEG:
        codec = "mpeg"
        audio_type = payload_type
    else:
        codec = "unknown"
        audio_type = payload_type
    return SoundEntry(
        index=index,
        name=name,
        fsb_offset=fsb_offset,
        audio_offset=audio_offset,
        slot_size=data_size,
        sample_count=sample_count,
        sample_header_bytes=sample_header_bytes,
        version=version,
        audio_type=audio_type,
        sample_rate=sample_rate,
        channels=channels,
        mode=mode,
        sample_length=sample_length,
        codec=codec,
    )


def scan_pcssb(path: str | Path) -> list[SoundEntry]:
    path = Path(path)
    if not path.is_file():
        raise SoundEditorError(f"PCSSB file not found: {path}")
    data = path.read_bytes()
    if len(data) < FSB3_BASE_HEADER_SIZE:
        raise SoundEditorError("File is too small to contain an SM3 FSB3 sound bank.")

    entries: list[SoundEntry] = []
    for offset in range(0, len(data) - FSB3_BASE_HEADER_SIZE + 1, SM3_PCSSB_ALIGNMENT):
        if data[offset:offset + 4] != FSB3_MAGIC:
            continue
        entry = _parse_entry(data, offset, len(entries))
        if entry is not None:
            entries.append(entry)

    if not entries:
        raise SoundEditorError(
            "No supported 0x8000-aligned single-sample FSB3 entries were found. "
            "This Sound Editor currently targets the proven Spider-Man 3 PCSSB layout."
        )
    return entries


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return minimum if value < minimum else maximum if value > maximum else value


def _ima_decode_nibble(code: int, history: int, step_index: int) -> tuple[int, int]:
    step = IMA_STEP_TABLE[step_index]
    delta = step >> 3
    if code & 1:
        delta += step >> 2
    if code & 2:
        delta += step >> 1
    if code & 4:
        delta += step
    if code & 8:
        delta = -delta
    history = _clamp(history + delta, -32768, 32767)
    step_index = _clamp(step_index + IMA_INDEX_TABLE[code & 0x0F], 0, 88)
    return history, step_index


def _decode_xbox_ima(payload: bytes, channels: int, sample_length: int | None = None) -> bytes:
    if channels not in (1, 2):
        raise SoundEditorError(f"Xbox IMA extraction currently supports mono/stereo; target has {channels} channels.")
    frame_size = XBOX_IMA_FRAME_BYTES_PER_CHANNEL * channels
    if not payload or len(payload) % frame_size:
        raise SoundEditorError("Xbox IMA slot size is not aligned to the expected 0x24-byte-per-channel frame size.")

    output = bytearray()
    total_frames = len(payload) // frame_size
    wanted = sample_length if sample_length and sample_length > 0 else total_frames * XBOX_IMA_SAMPLES_PER_FRAME
    samples_written = 0

    for frame_no in range(total_frames):
        frame = payload[frame_no * frame_size:(frame_no + 1) * frame_size]
        channel_samples: list[list[int]] = []
        for channel in range(channels):
            header = 4 * channel if channels == 2 else 0
            history = struct.unpack_from("<h", frame, header)[0]
            step_index = _clamp(frame[header + 2], 0, 88)
            values = [history]
            for i in range(1, XBOX_IMA_SAMPLES_PER_FRAME):
                if channels == 2:
                    byte_offset = 8 + 4 * channel + 8 * ((i - 1) // 8) + ((i - 1) % 8) // 2
                else:
                    byte_offset = 4 + (i - 1) // 2
                shift = 0 if ((i - 1) & 1) == 0 else 4
                code = (frame[byte_offset] >> shift) & 0x0F
                history, step_index = _ima_decode_nibble(code, history, step_index)
                values.append(history)
            channel_samples.append(values)

        frame_samples = min(XBOX_IMA_SAMPLES_PER_FRAME, wanted - samples_written)
        if frame_samples <= 0:
            break
        for i in range(frame_samples):
            for channel in range(channels):
                output += struct.pack("<h", channel_samples[channel][i])
        samples_written += frame_samples
    return bytes(output)


def _nearest_ima_step_index(delta: int) -> int:
    target = max(7, abs(int(delta)))
    best = 0
    best_error = abs(IMA_STEP_TABLE[0] - target)
    for i in range(1, len(IMA_STEP_TABLE)):
        error = abs(IMA_STEP_TABLE[i] - target)
        if error < best_error:
            best = i
            best_error = error
    return best


def _ima_encode_code(target: int, history: int, step_index: int) -> tuple[int, int, int]:
    step = IMA_STEP_TABLE[step_index]
    diff = int(target) - int(history)
    code = 0
    if diff < 0:
        code |= 8
        diff = -diff
    if diff >= step:
        code |= 4
        diff -= step
    if diff >= (step >> 1):
        code |= 2
        diff -= step >> 1
    if diff >= (step >> 2):
        code |= 1
    history, step_index = _ima_decode_nibble(code, history, step_index)
    return code, history, step_index


def _encode_xbox_ima(pcm_s16le: bytes, channels: int, target_samples: int) -> bytes:
    if channels not in (1, 2):
        raise SoundEditorError(f"Xbox IMA replacement currently supports mono/stereo; target has {channels} channels.")
    if target_samples <= 0 or target_samples % XBOX_IMA_SAMPLES_PER_FRAME:
        raise SoundEditorError("Xbox IMA target sample count is not aligned to 64-sample frames.")
    frame_bytes = 2 * channels
    if len(pcm_s16le) != target_samples * frame_bytes:
        raise SoundEditorError("Internal Xbox IMA encoder received the wrong PCM sample count.")

    frame_size = XBOX_IMA_FRAME_BYTES_PER_CHANNEL * channels
    output = bytearray()
    previous_index: list[int | None] = [None] * channels

    def pcm_sample(sample_index: int, channel: int) -> int:
        return struct.unpack_from("<h", pcm_s16le, (sample_index * channels + channel) * 2)[0]

    for base in range(0, target_samples, XBOX_IMA_SAMPLES_PER_FRAME):
        frame = bytearray(frame_size)
        states: list[list[int]] = []
        for channel in range(channels):
            history = pcm_sample(base, channel)
            if previous_index[channel] is None:
                delta = pcm_sample(base + 1, channel) - history
                step_index = _nearest_ima_step_index(delta)
            else:
                step_index = int(previous_index[channel])
            struct.pack_into("<hBB", frame, 4 * channel if channels == 2 else 0, history, step_index, 0)
            states.append([history, step_index])

        for i in range(1, XBOX_IMA_SAMPLES_PER_FRAME):
            for channel in range(channels):
                history, step_index = states[channel]
                code, history, step_index = _ima_encode_code(pcm_sample(base + i, channel), history, step_index)
                states[channel] = [history, step_index]
                if channels == 2:
                    byte_offset = 8 + 4 * channel + 8 * ((i - 1) // 8) + ((i - 1) % 8) // 2
                else:
                    byte_offset = 4 + (i - 1) // 2
                if ((i - 1) & 1) == 0:
                    frame[byte_offset] = (frame[byte_offset] & 0xF0) | code
                else:
                    frame[byte_offset] = (frame[byte_offset] & 0x0F) | (code << 4)
        for channel in range(channels):
            previous_index[channel] = states[channel][1]
        output.extend(frame)
    return bytes(output)


def _looks_like_xbox_ima(payload: bytes, channels: int) -> bool:
    if channels not in (1, 2):
        return False
    frame_size = XBOX_IMA_FRAME_BYTES_PER_CHANNEL * channels
    if not payload or len(payload) % frame_size:
        return False
    for offset in range(0, len(payload), frame_size):
        for channel in range(channels):
            header = offset + (4 * channel if channels == 2 else 0)
            if header + 3 >= len(payload) or payload[header + 2] > 88:
                return False
    return True


def _write_pcm_wave(path: Path, pcm_s16le: bytes, sample_rate: int, channels: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_s16le)
    return path


def _entry_payload(source_path: Path, entry: SoundEntry) -> bytes:
    with source_path.open("rb") as src:
        src.seek(entry.audio_offset)
        payload = src.read(entry.slot_size)
    if len(payload) != entry.slot_size:
        raise SoundEditorError("Could not read the full selected sound slot.")
    return payload


def extract_entry(source_path: str | Path, entry: SoundEntry, output_path: str | Path) -> Path:
    source_path = Path(source_path)
    output_path = Path(output_path)
    if not source_path.is_file():
        raise SoundEditorError(f"PCSSB file not found: {source_path}")
    size = source_path.stat().st_size
    if entry.audio_offset < 0 or entry.audio_end > size:
        raise SoundEditorError("Selected sound slot points outside the PCSSB file.")

    payload = _entry_payload(source_path, entry)
    if entry.codec == "xbox_ima" and output_path.suffix.lower() == ".wav":
        channels = entry.channels or 2
        sample_rate = entry.sample_rate or 48000
        pcm = _decode_xbox_ima(payload, channels, entry.sample_length)
        return _write_pcm_wave(output_path, pcm, sample_rate, channels)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(payload)
    return output_path


def _replacement_family(data: bytes) -> str:
    kind = detect_audio_type(data[:16])
    if kind == "MPEG audio (raw)":
        return "mpeg_raw"
    if kind == "MP3 (ID3 tagged)":
        return "mpeg_tagged"
    if kind == "WAV / RIFF":
        return "wav"
    if kind.startswith("Ogg"):
        return "ogg"
    if kind == "FLAC":
        return "flac"
    return "unknown"


def _xbox_ima_target_info(entry: SoundEntry) -> tuple[int, int, int]:
    channels = entry.channels or 0
    sample_rate = entry.sample_rate or 0
    sample_length = entry.sample_length or 0
    if channels not in (1, 2) or sample_rate <= 0 or sample_length <= 0:
        raise SoundEditorError("Xbox IMA target is missing valid channel/rate/sample metadata.")
    expected = (sample_length // XBOX_IMA_SAMPLES_PER_FRAME) * XBOX_IMA_FRAME_BYTES_PER_CHANNEL * channels
    if sample_length % XBOX_IMA_SAMPLES_PER_FRAME or expected != entry.slot_size:
        raise SoundEditorError(
            "Xbox IMA target does not match the proven SM3 0x24-byte / 64-sample frame layout. "
            "This slot is blocked rather than guessed."
        )
    return channels, sample_rate, sample_length


def _prepare_xbox_ima_replacement(entry: SoundEntry, replacement_path: Path) -> bytes:
    channels, sample_rate, target_samples = _xbox_ima_target_info(entry)
    raw = replacement_path.read_bytes()
    if len(raw) == entry.slot_size and _looks_like_xbox_ima(raw, channels):
        return raw

    # Normal user audio is decoded/resampled by FFmpeg, then encoded to the exact
    # Xbox-IMA frame count required by the unchanged FSB3 sample header.
    with tempfile.TemporaryDirectory(prefix="sm3_xbox_ima_") as td:
        pcm_path = Path(td) / "replacement.s16le"
        proc = _run_ffmpeg([
            "-y", "-i", str(replacement_path),
            "-map_metadata", "-1",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-c:a", "pcm_s16le",
            "-f", "s16le",
            str(pcm_path),
        ])
        if proc.returncode != 0 or not pcm_path.is_file():
            tail = "\n".join(((proc.stderr or "").strip().splitlines())[-12:])
            raise SoundEditorError("FFmpeg could not decode the replacement for Xbox IMA conversion.\n" + tail)
        pcm = pcm_path.read_bytes()

    frame_bytes = 2 * channels
    if len(pcm) % frame_bytes:
        raise SoundEditorError("Decoded PCM byte count is not aligned to the target channel count.")
    input_samples = len(pcm) // frame_bytes
    if input_samples > target_samples:
        excess = (input_samples - target_samples) / sample_rate
        raise SoundEditorError(
            f"Replacement is {excess:.2f} seconds longer than this Xbox IMA slot. "
            "Trim the audio or choose a shorter file; the PCSSB header/sample count will not be shifted."
        )
    if input_samples < target_samples:
        pcm += b"\x00" * ((target_samples - input_samples) * frame_bytes)

    encoded = _encode_xbox_ima(pcm, channels, target_samples)
    if len(encoded) != entry.slot_size:
        raise SoundEditorError(
            f"Xbox IMA encoder safety check failed: expected {entry.slot_size:,} bytes, got {len(encoded):,}."
        )
    return encoded


def validate_replacement(source_path: str | Path, entry: SoundEntry, replacement_path: str | Path) -> tuple[int, int, str]:
    source_path = Path(source_path)
    replacement_path = Path(replacement_path)
    if not source_path.is_file():
        raise SoundEditorError(f"PCSSB file not found: {source_path}")
    if not replacement_path.is_file():
        raise SoundEditorError(f"Replacement audio not found: {replacement_path}")

    if entry.codec == "xbox_ima":
        channels, sample_rate, target_samples = _xbox_ima_target_info(entry)
        raw = replacement_path.read_bytes()
        if len(raw) == entry.slot_size and _looks_like_xbox_ima(raw, channels):
            return len(raw), 0, "Xbox IMA ADPCM (raw, exact-size)"
        duration = probe_audio_duration(replacement_path)
        max_duration = target_samples / sample_rate
        if duration > max_duration + 0.02:
            raise SoundEditorError(
                f"Replacement is {duration:.2f}s but this Xbox IMA slot is {max_duration:.2f}s. "
                "Trim the replacement first."
            )
        return entry.slot_size, 0, f"Xbox IMA ADPCM (auto-convert {sample_rate} Hz / {channels} ch)"

    replacement = replacement_path.read_bytes()
    replacement_size = len(replacement)
    if replacement_size <= 0:
        raise SoundEditorError("Replacement audio is empty.")
    if replacement_size > entry.slot_size:
        raise SoundEditorError(
            f"Replacement is too large by {replacement_size - entry.slot_size:,} bytes. "
            "SM3 PCSSB slots must stay fixed-size; choose/export a smaller audio file."
        )

    with source_path.open("rb") as src:
        src.seek(entry.audio_offset)
        target_head = src.read(16)
    target_family = _replacement_family(target_head)
    replacement_family = _replacement_family(replacement)

    if entry.codec == "mpeg" or target_family == "mpeg_raw":
        if replacement_family != "mpeg_raw":
            if replacement_family == "mpeg_tagged":
                raise SoundEditorError(
                    "This target is a raw MPEG/MP3 stream, but the replacement starts with an ID3 tag. "
                    "Re-export/strip MP3 metadata so the file begins with an MPEG frame sync."
                )
            raise SoundEditorError(
                f"Audio type mismatch: target is {detect_audio_type(target_head)}, "
                f"replacement is {detect_audio_type(replacement[:16])}."
            )
    elif target_family in {"wav", "ogg", "flac"} and replacement_family != target_family:
        raise SoundEditorError(
            f"Audio type mismatch: target is {detect_audio_type(target_head)}, "
            f"replacement is {detect_audio_type(replacement[:16])}."
        )
    elif entry.codec == "unknown":
        raise SoundEditorError(
            f"This FSB3 slot uses an unsupported codec/mode (0x{entry.mode:08X}). "
            "The editor blocks unknown codecs instead of guessing."
        )

    return replacement_size, entry.slot_size - replacement_size, detect_audio_type(replacement[:16])


def replace_entry(
    source_path: str | Path,
    entry: SoundEntry,
    replacement_path: str | Path,
    output_path: str | Path,
) -> ReplacementResult:
    source_path = Path(source_path)
    replacement_path = Path(replacement_path)
    output_path = Path(output_path)

    replacement_size, padded_bytes, _ = validate_replacement(source_path, entry, replacement_path)
    if entry.codec == "xbox_ima":
        replacement = _prepare_xbox_ima_replacement(entry, replacement_path)
        replacement_size = len(replacement)
        padded_bytes = 0
    else:
        replacement = replacement_path.read_bytes()
    original_size = source_path.stat().st_size
    if entry.audio_end > original_size:
        raise SoundEditorError("Selected sound slot points outside the source PCSSB.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == output_path.resolve():
        raise SoundEditorError("Output must be a new file. The original PCSSB is never modified directly.")

    shutil.copy2(source_path, output_path)
    with output_path.open("r+b") as out:
        out.seek(entry.audio_offset)
        out.write(replacement)
        if padded_bytes:
            out.write(b"\x00" * padded_bytes)

    output_size = output_path.stat().st_size
    if output_size != original_size:
        try:
            output_path.unlink()
        except Exception:
            pass
        raise SoundEditorError(
            f"Safety check failed: output size changed ({original_size:,} -> {output_size:,}). Output deleted."
        )

    h = hashlib.sha256()
    with output_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)

    return ReplacementResult(
        source_path=source_path,
        output_path=output_path,
        entry=entry,
        replacement_path=replacement_path,
        replacement_size=replacement_size,
        padded_bytes=padded_bytes,
        original_size=original_size,
        output_size=output_size,
        output_sha256=h.hexdigest(),
    )


def _bundled_ffmpeg_candidates() -> list[Path]:
    """Locations a source or frozen release may use for a bundled FFmpeg binary."""
    candidates: list[Path] = []
    try:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir / "ffmpeg.exe", exe_dir / "ffmpeg"])
    except Exception:
        pass

    try:
        here = Path(__file__).resolve()
        app_root = here.parents[2]
        candidates.extend([
            app_root / "ffmpeg.exe",
            app_root / "ffmpeg",
            app_root / "tools" / "ffmpeg.exe",
            app_root / "tools" / "ffmpeg",
        ])
    except Exception:
        pass

    # PyInstaller one-file/one-folder extraction root, when present.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        base = Path(meipass)
        candidates.extend([base / "ffmpeg.exe", base / "ffmpeg", base / "tools" / "ffmpeg.exe", base / "tools" / "ffmpeg"])

    # Preserve order while removing duplicates.
    seen: set[str] = set()
    result: list[Path] = []
    for item in candidates:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def get_ffmpeg_executable() -> str:
    """Return a usable FFmpeg executable without making toolkit startup depend on it."""
    for candidate in _bundled_ffmpeg_candidates():
        try:
            if candidate.is_file():
                return str(candidate)
        except OSError:
            pass

    try:
        import imageio_ffmpeg  # type: ignore

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and Path(candidate).is_file():
            return str(candidate)
    except Exception:
        pass

    candidate = shutil.which("ffmpeg")
    if candidate:
        return candidate

    raise SoundEditorError(
        "Music Replacement Mode audio support is not installed yet. "
        "Open Sound Editor > Music Replacement and click INSTALL / REPAIR AUDIO SUPPORT. "
        "Direct PCSSB extract/replace still works without FFmpeg."
    )


def audio_support_status() -> tuple[bool, str]:
    """Return whether Music Replacement audio support is ready and its resolved path/message."""
    try:
        return True, get_ffmpeg_executable()
    except Exception as exc:
        return False, str(exc)


def install_audio_support_current_python(timeout: int = 360) -> str:
    """Install imageio-ffmpeg into the exact Python interpreter running this source toolkit.

    This intentionally avoids PATH/`where python` detection. In a frozen release the
    dependency should already be bundled by the PyInstaller spec.
    """
    if getattr(sys, "frozen", False):
        raise SoundEditorError(
            "This is a compiled toolkit build. Audio support should be bundled with the release; "
            "reinstall the complete toolkit package if it is missing."
        )

    python_exe = Path(sys.executable)
    if not python_exe.is_file():
        raise SoundEditorError(f"The running Python interpreter could not be resolved: {sys.executable}")

    def run_module(args: list[str], step: str) -> subprocess.CompletedProcess[str]:
        cmd = [str(python_exe), "-m"] + args
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )
        except subprocess.TimeoutExpired as exc:
            raise SoundEditorError(f"{step} timed out.") from exc
        except OSError as exc:
            raise SoundEditorError(f"Could not start the running Python interpreter: {exc}") from exc
        return proc

    pip_check = run_module(["pip", "--version"], "pip check")
    if pip_check.returncode != 0:
        ensure = run_module(["ensurepip", "--upgrade"], "pip repair")
        if ensure.returncode != 0:
            tail = ((ensure.stderr or "") + "\n" + (ensure.stdout or "")).strip()[-1600:]
            raise SoundEditorError("Python was found, but pip could not be enabled.\n" + tail)

    install = run_module(["pip", "install", "--upgrade", "imageio-ffmpeg>=0.6.0"], "audio-support install")
    if install.returncode != 0:
        tail = ((install.stderr or "") + "\n" + (install.stdout or "")).strip()[-1800:]
        raise SoundEditorError(
            "Python was found correctly, but imageio-ffmpeg installation failed.\n" + tail
        )

    # The current process may be able to import the newly installed package immediately.
    import importlib
    importlib.invalidate_caches()
    try:
        import imageio_ffmpeg  # type: ignore
        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        if candidate and Path(candidate).is_file():
            return str(candidate)
    except Exception:
        pass

    # A restart can be needed if the package path changed during this process. Verify using
    # the exact same interpreter before asking the user to restart.
    check = subprocess.run(
        [str(python_exe), "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True, errors="replace", timeout=60,
        creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0),
    )
    if check.returncode == 0 and check.stdout.strip():
        return check.stdout.strip().splitlines()[-1]

    tail = ((check.stderr or "") + "\n" + (check.stdout or "")).strip()[-1200:]
    raise SoundEditorError(
        "Audio support installed, but verification did not complete. Restart the toolkit and check again.\n" + tail
    )


def _run_ffmpeg(args: list[str], timeout: int = 240) -> subprocess.CompletedProcess[str]:
    ffmpeg = get_ffmpeg_executable()
    cmd = [ffmpeg, "-hide_banner", "-nostdin"] + args
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise SoundEditorError("FFmpeg timed out while processing audio.") from exc
    except OSError as exc:
        raise SoundEditorError(f"Could not start FFmpeg: {exc}") from exc
    return proc


def probe_audio_duration(path: str | Path) -> float:
    path = Path(path)
    if not path.is_file():
        raise SoundEditorError(f"Audio file not found: {path}")
    proc = _run_ffmpeg(["-i", str(path), "-f", "null", "-"])
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise SoundEditorError(f"Could not determine audio duration for: {path.name}")
    hours, minutes, seconds = match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if duration <= 0:
        raise SoundEditorError(f"Audio duration is invalid for: {path.name}")
    return duration


def _strip_mp3_tags(data: bytes) -> bytes:
    """Remove ID3v2/ID3v1 wrappers so the result begins with an MPEG frame sync."""
    payload = data
    if len(payload) >= 10 and payload.startswith(b"ID3"):
        size = ((payload[6] & 0x7F) << 21) | ((payload[7] & 0x7F) << 14) | ((payload[8] & 0x7F) << 7) | (payload[9] & 0x7F)
        total = 10 + size
        if payload[5] & 0x10:  # footer present
            total += 10
        payload = payload[total:]
    if len(payload) >= 128 and payload[-128:-125] == b"TAG":
        payload = payload[:-128]
    return payload


def _choose_auto_bitrate(slot_size: int, duration_seconds: float) -> int:
    if duration_seconds <= 0:
        raise SoundEditorError("Cannot choose a bitrate without a valid voice-stem duration.")
    # Leave 5% room for encoder/frame rounding. The 192 kbps route is already
    # confirmed in-game for the 98.5s ME12_End test and fits comfortably.
    theoretical_kbps = (slot_size * 8.0 / duration_seconds) / 1000.0
    safe_ceiling = theoretical_kbps * 0.95
    for rate in SAFE_MP3_BITRATES:
        if rate <= safe_ceiling:
            return rate
    raise SoundEditorError(
        f"Selected slot is too small for even a 64 kbps MP3 over {duration_seconds:.2f} seconds."
    )


def _channel_layout(channels: int) -> str:
    if channels == 1:
        return "mono"
    # The proven movie bank uses stereo. For unusual counts, downmix to stereo
    # rather than generating a layout the game route has not been tested with.
    return "stereo"


def build_music_mix(
    source_path: str | Path,
    entry: SoundEntry,
    voice_path: str | Path,
    music_path: str | Path,
    output_path: str | Path,
    *,
    voice_volume_percent: int = 100,
    music_volume_percent: int = 35,
    loop_music: bool = True,
    bitrate_kbps: int | None = None,
) -> MusicMixResult:
    """Create a dialogue-stem + new-music raw MP3 that safely fits an SM3 slot.

    This intentionally does not perform vocal separation. `voice_path` must be a
    dialogue/vocal stem prepared by the user (for example from a stem separator).
    """
    source_path = Path(source_path)
    voice_path = Path(voice_path)
    music_path = Path(music_path)
    output_path = Path(output_path)

    if not source_path.is_file():
        raise SoundEditorError(f"PCSSB file not found: {source_path}")
    if not voice_path.is_file():
        raise SoundEditorError(f"Voice/dialogue stem not found: {voice_path}")
    if not music_path.is_file():
        raise SoundEditorError(f"New music file not found: {music_path}")
    if not entry.audio_type.startswith("MPEG") and not entry.audio_type.startswith("MP3"):
        raise SoundEditorError(
            f"Music Replacement Mode currently targets SM3 raw MPEG movie slots; selected slot is {entry.audio_type}."
        )

    voice_volume_percent = max(0, min(200, int(voice_volume_percent)))
    music_volume_percent = max(0, min(200, int(music_volume_percent)))
    if voice_volume_percent == 0 and music_volume_percent == 0:
        raise SoundEditorError("Voice and music volume cannot both be 0%.")

    duration = probe_audio_duration(voice_path)
    chosen_bitrate = int(bitrate_kbps) if bitrate_kbps else _choose_auto_bitrate(entry.slot_size, duration)
    if chosen_bitrate not in SAFE_MP3_BITRATES:
        raise SoundEditorError(
            "Unsupported MP3 bitrate. Choose Auto or one of: " + ", ".join(str(x) for x in SAFE_MP3_BITRATES) + " kbps."
        )

    sample_rate = entry.sample_rate or 48000
    channels = 1 if entry.channels == 1 else 2
    layout = _channel_layout(channels)
    voice_gain = voice_volume_percent / 100.0
    music_gain = music_volume_percent / 100.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_name(output_path.name + ".ffmpeg.tmp.mp3")
    try:
        if temp_output.exists():
            temp_output.unlink()
    except Exception:
        pass

    inputs = ["-y", "-i", str(voice_path)]
    if loop_music:
        inputs += ["-stream_loop", "-1"]
    inputs += ["-i", str(music_path)]

    filter_complex = (
        f"[0:a]aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts={layout},"
        f"volume={voice_gain:.6f}[voice];"
        f"[1:a]aresample={sample_rate},aformat=sample_fmts=fltp:channel_layouts={layout},"
        f"volume={music_gain:.6f}[music];"
        f"[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95[out]"
    )

    proc = _run_ffmpeg(inputs + [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "libmp3lame",
        "-b:a", f"{chosen_bitrate}k",
        "-write_xing", "0",
        "-id3v2_version", "0",
        "-write_id3v1", "0",
        "-map_metadata", "-1",
        "-f", "mp3",
        str(temp_output),
    ])
    if proc.returncode != 0 or not temp_output.is_file():
        details = (proc.stderr or "").strip().splitlines()
        tail = "\n".join(details[-12:])
        raise SoundEditorError("FFmpeg could not create the music mix.\n" + tail)

    payload = _strip_mp3_tags(temp_output.read_bytes())
    try:
        temp_output.unlink()
    except Exception:
        pass
    if not payload:
        raise SoundEditorError("FFmpeg produced an empty audio mix.")
    if detect_audio_type(payload[:16]) != "MPEG audio (raw)":
        raise SoundEditorError(
            "Generated mix is not a raw MPEG stream after metadata stripping. The file was not accepted."
        )
    output_path.write_bytes(payload)

    # Validate against the actual selected slot. If an Auto bitrate happens to
    # land over the limit due to frame rounding, step downward and retry.
    try:
        size, pad, kind = validate_replacement(source_path, entry, output_path)
    except SoundEditorError as exc:
        if bitrate_kbps is not None:
            try:
                output_path.unlink()
            except Exception:
                pass
            raise
        lower = [rate for rate in SAFE_MP3_BITRATES if rate < chosen_bitrate]
        for rate in lower:
            try:
                return build_music_mix(
                    source_path,
                    entry,
                    voice_path,
                    music_path,
                    output_path,
                    voice_volume_percent=voice_volume_percent,
                    music_volume_percent=music_volume_percent,
                    loop_music=loop_music,
                    bitrate_kbps=rate,
                )
            except SoundEditorError:
                continue
        try:
            output_path.unlink()
        except Exception:
            pass
        raise SoundEditorError(f"Could not make an Auto bitrate mix fit this slot: {exc}") from exc

    return MusicMixResult(
        output_path=output_path,
        entry=entry,
        voice_path=voice_path,
        music_path=music_path,
        duration_seconds=duration,
        bitrate_kbps=chosen_bitrate,
        voice_volume_percent=voice_volume_percent,
        music_volume_percent=music_volume_percent,
        loop_music=bool(loop_music),
        output_size=size,
        padded_bytes=pad,
        audio_type=kind,
    )
