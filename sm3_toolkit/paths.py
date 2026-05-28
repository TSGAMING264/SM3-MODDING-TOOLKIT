from __future__ import annotations

import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    candidates: list[Path] = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(getattr(sys, "_MEIPASS")))
    candidates.append(APP_DIR)
    for base in candidates:
        if (base / "SM3_EXTRACTOR_FINAL").exists():
            return base
    return APP_DIR


RESOURCE_ROOT = resource_root()
SM3_ROOT = RESOURCE_ROOT / "SM3_EXTRACTOR_FINAL"
PACK_EXTRACTOR_DIR = SM3_ROOT / "00_SM3_BETA_PACK_EXTRACTOR"
TEX_SWAPPER_DIR = SM3_ROOT / "09_SM3_PC_TEXTURE_BROWSER_FINAL_MANUAL_DDS"
TEXTURE_FOLDER_VIEWER_DIR = SM3_ROOT / "11_TEXTURE_FOLDER_PREVIEWER"
OLD_ANIMATION_SWAPPER_DIR = SM3_ROOT / "12_OLD_ANIMATION_SWAPPER"
APP_ICON_PATH = OLD_ANIMATION_SWAPPER_DIR / "SM3_ANIMATION_SWAPPER.ico"
ANIMATION_ABOUT_PATH = OLD_ANIMATION_SWAPPER_DIR / "ABOUT_INFO_RELEASE_v1_14.txt"
PRESETS_DIR = OLD_ANIMATION_SWAPPER_DIR / "PRESETS_RELEASE_v1_0"


ASSETS_DIR = RESOURCE_ROOT / "sm3_toolkit" / "assets"
TSGAMING264_PROFILE_IMAGE = ASSETS_DIR / "tsgaming264_profile.png"
