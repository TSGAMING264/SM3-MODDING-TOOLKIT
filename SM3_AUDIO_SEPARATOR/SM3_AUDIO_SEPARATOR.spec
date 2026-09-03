# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = Path(SPECPATH).resolve()
ICON = ROOT / "SM3_TOOLKIT.ico"
VERSION_INFO = ROOT / "SM3_AUDIO_SEPARATOR_VERSION_INFO.txt"

# Demucs selects model implementations dynamically, so include its package
# modules and non-code data. PyInstaller's built-in hooks collect Torch and
# SoundFile native libraries reached by the normal imports.
demucs_hiddenimports = collect_submodules("demucs")
demucs_datas = collect_data_files("demucs")

a = Analysis(
    [str(ROOT / "SM3_AUDIO_SEPARATOR.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ICON), ".")] + demucs_datas,
    hiddenimports=demucs_hiddenimports + [
        "soundfile",
        "torch",
        "sphn",
        "lameenc",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "unittest.test"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Torch's hook retains selected Python sources needed by its runtime. Remove only
# known test/debug-only modules that Demucs inference does not import.
_runtime_dev_prefixes = (
    "torch/distributed/debug/",
    "torch/distributed/tensor/debug/",
    "torch/fx/passes/tests/",
)
a.datas = [
    item for item in a.datas
    if not item[0].replace("\\", "/").lower().startswith(_runtime_dev_prefixes)
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SM3 Audio Separator",
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
    contents_directory="Audio Runtime",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SM3 Audio Separator",
)
