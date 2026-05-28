# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
ROOT = Path.cwd()
ICON = ROOT / "SM3_EXTRACTOR_FINAL" / "12_OLD_ANIMATION_SWAPPER" / "SM3_ANIMATION_SWAPPER.ico"

a = Analysis(
    ["SM3_TOOLS.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        ("SM3_EXTRACTOR_FINAL", "SM3_EXTRACTOR_FINAL"),
        ("sm3_toolkit/assets", "sm3_toolkit/assets"),
    ],
    hiddenimports=[
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageOps",
    ],
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
