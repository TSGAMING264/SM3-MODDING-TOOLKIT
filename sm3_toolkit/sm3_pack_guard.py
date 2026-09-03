from __future__ import annotations

from pathlib import Path


WRONG_GAME_GUARD_MESSAGE = (
    "Failed to list: SM3 pack route not recognized.\n"
    "Expected PCPACK/PCAPK/APKF structure; required SM3 signatures were missing.\n"
    "This file does not look like a Spider-Man 3 PC pack.\n"
    "GO DOWNLOAD THE FUCKING LEGENDARY WOS TOOLKIT."
)

WRONG_GAME_LOG_CODE = "WRONG_GAME_OR_UNSUPPORTED_PACK"
NOT_SM3_LOG_CODE = "NOT_SM3_PC_PACK"


def _head_from_path(path: Path, limit: int = 4 * 1024 * 1024) -> bytes:
    with path.open("rb") as f:
        return f.read(limit)


def looks_like_sm3_pc_pack_header(data: bytes) -> bool:
    head = bytes(data[: min(len(data), 4 * 1024 * 1024)])
    if head.startswith(b"APKF"):
        return True
    if head.startswith(b"hsam"):
        return True
    if head[0x30:0x34] == b"hsam":
        return True
    return b"hsam" in head or b"APKF" in head


def looks_like_wrong_game_or_unsupported_sm3_path(path: Path) -> bool:
    try:
        data = _head_from_path(path)
    except OSError:
        return False
    if data[:3] == b"NCH":
        return True
    return not looks_like_sm3_pc_pack_header(data)


def exception_suggests_wrong_game(exc: BaseException) -> bool:
    text = str(exc).lower()
    needles = (
        "web of shadows",
        "wos",
        "starts with nch",
        "not sm3",
        "not recognized as sm3",
        "sm3 pack route not recognized",
        "required sm3 signatures were missing",
    )
    return any(needle in text for needle in needles)


def wrong_game_detail(path: Path | None = None) -> str:
    where = f" file={path}" if path else ""
    return f"{WRONG_GAME_LOG_CODE}; {NOT_SM3_LOG_CODE};{where}"
