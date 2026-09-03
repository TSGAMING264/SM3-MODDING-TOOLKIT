# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
ROOT = Path(SPECPATH).resolve()
ICON = ROOT / "SM3_EXTRACTOR_FINAL" / "12_OLD_ANIMATION_SWAPPER" / "SM3_ANIMATION_SWAPPER.ico"
PRESETS = ROOT / "SM3_EXTRACTOR_FINAL" / "12_OLD_ANIMATION_SWAPPER" / "PRESETS_RELEASE_v1_0"
VERSION_INFO = ROOT / "SM3_TOOLKIT_VERSION_INFO.txt"

# Music Replacement Mode uses imageio-ffmpeg. Keep its platform FFmpeg binary
# inside the Toolkit's private runtime folder so the companion EXE cannot load it.
ffmpeg_datas, ffmpeg_binaries, ffmpeg_hiddenimports = collect_all("imageio_ffmpeg")
ffmpeg_datas = [
    item for item in ffmpeg_datas
    if Path(item[0]).name.lower() not in {"readme.md", "readme.txt"}
]

a = Analysis(
    [str(ROOT / "SM3_TOOLS.py")],
    pathex=[str(ROOT)],
    binaries=ffmpeg_binaries,
    datas=[
        (str(ICON), "SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER"),
        (str(PRESETS), "SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/PRESETS_RELEASE_v1_0"),
        (str(ROOT / "sm3_toolkit" / "assets"), "sm3_toolkit/assets"),
    ] + ffmpeg_datas,
    hiddenimports=[
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageOps",
    ] + ffmpeg_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SM3 Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
    version=str(VERSION_INFO),
    contents_directory="Toolkit Runtime",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SM3 Toolkit",
)
