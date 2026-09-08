# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None
ROOT = Path.cwd()
ICON = ROOT / "SM3_EXTRACTOR_FINAL" / "12_OLD_ANIMATION_SWAPPER" / "SM3_ANIMATION_SWAPPER.ico"

# Music Replacement Mode uses imageio-ffmpeg so reviewers/users do not need to
# manually install a separate FFmpeg executable. collect_all includes the wheel's
# platform FFmpeg binary in PyInstaller builds.
ffmpeg_datas, ffmpeg_binaries, ffmpeg_hiddenimports = collect_all("imageio_ffmpeg")

a = Analysis(
    ["SM3_TOOLS.py"],
    pathex=[str(ROOT)],
    binaries=ffmpeg_binaries,
    datas=[
        ("SM3_EXTRACTOR_FINAL", "SM3_EXTRACTOR_FINAL"),
        ("sm3_toolkit/assets", "sm3_toolkit/assets"),
        # Motion Editor profiles and animation presets are loaded at runtime.
        ("sm3_toolkit/data", "sm3_toolkit/data"),
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SM3 Modding Toolkit",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)
