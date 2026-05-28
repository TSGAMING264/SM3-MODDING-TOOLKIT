# SM3 ANIMATION SWAPPER

Created by TSGAMING264

SM3 ANIMATION SWAPPER is a Windows Python/Tkinter tool for Spider-Man 3 PC modding research. It lists and compares animation entries from user-selected PC destination packs and user-selected Xbox/XE source packs, then applies compatible animation swaps into a new patched PC pack copy.

## What It Does

- Loads a user-selected Spider-Man 3 PC destination pack.
- Loads a user-selected source pack or an Xbox Pack Folder containing `.XEPACK` files.
- Lists animation entries from Pack A and Pack B/source.
- Provides release presets and manual selection tools for compatible swaps.
- Validates component size/layout before patching.
- Saves a new patched PC pack copy.
- Does not automatically overwrite the original selected pack.

## What Is Not Included

This repository does not include original Spider-Man 3 game files, `.PCPACK` files, `.XEPACK` files, extracted models, extracted animations, textures, or any other game assets.

Users must supply their own legally obtained files. The source package is for the tool only.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer. The current release was tested with Python 3.13.2.
- Tkinter, included with the standard Python installer from python.org.
- PyInstaller, installed from `requirements.txt`, for building the Windows release folder.

Runtime dependencies are from the Python standard library. PyInstaller is only needed for building the distributable app.

## Setup

Open a terminal in this repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run from source:

```powershell
python SM3_ANIMATION_SWAPPER.py
```

## Build With PyInstaller

The included spec file builds a Windows folder-style release. This is preferred for review because it avoids a self-extracting one-file EXE.

```powershell
pip install -r requirements.txt
pyinstaller SM3_ANIMATION_SWAPPER.spec
```

Build output:

```text
dist/SM3_ANIMATION_SWAPPER/
```

Run:

```powershell
dist\SM3_ANIMATION_SWAPPER\SM3_ANIMATION_SWAPPER.exe
```

Keep the `_internal` folder beside the EXE. The application needs that runtime folder.

## Antivirus False Positives

PyInstaller applications can sometimes trigger antivirus or mod-site scanner warnings because PyInstaller bundles the Python runtime, standard library, and application dependencies into a distributable Windows executable. Malware authors also use PyInstaller, so some scanners treat unsigned PyInstaller EXEs as suspicious based on packaging heuristics rather than verified malicious behavior.

This project includes the full Python source code, the PyInstaller spec file, and build instructions so reviewers can inspect the source and rebuild the release from scratch.

The included spec is configured to reduce false positives:

- Folder-style build instead of one-file self-extracting mode.
- UPX disabled.
- Windows product/file version metadata included.
- No original game files included.

## Safety Notes

- Always back up original Spider-Man 3 PC pack files before testing mods.
- The tool saves patched copies and does not intentionally overwrite the selected original pack automatically.
- Test one patched pack at a time.
- The Xbox Pack Folder should contain user-supplied `.XEPACK` files directly, not included in this repository.

## Repository Contents

- `SM3_ANIMATION_SWAPPER.py` - main Python/Tkinter source.
- `SM3_ANIMATION_SWAPPER.spec` - PyInstaller build spec.
- `SM3_ANIMATION_SWAPPER_version_info.txt` - Windows version metadata for the EXE.
- `SM3_ANIMATION_SWAPPER.ico` - application icon.
- `ABOUT_INFO_RELEASE_v1_14.txt` - in-app About/Info text.
- `PRESETS_RELEASE_v1_0/` - preset JSON metadata only; no binary game assets.
- `requirements.txt` - Python build dependency list.
- `BUILD_FROM_SOURCE.md` - detailed reviewer build guide.
- `NOTICE` - source/package notice.
