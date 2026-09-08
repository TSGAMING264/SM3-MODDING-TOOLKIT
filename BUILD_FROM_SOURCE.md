# Build From Source

This guide builds the two applications included in the official SM3 Toolkit package:

- SM3 Modding Toolkit v5.2.196 FINAL ABOUT CREDIT
- SM3 Audio Separator v1.0.3

They remain separate applications and must not be merged into one EXE or runtime folder.

## 1. Requirements

- Windows 10 or Windows 11, 64-bit
- Python 3.10 or newer with Tkinter enabled
- A current `pip`
- Enough free disk space for the Audio Separator's Torch/Demucs build environment

Verify Python:

```powershell
py -3 --version
```

## 2. Build The Main Toolkit

From the repository root:

```powershell
py -3 -m venv .venv-toolkit
.\.venv-toolkit\Scripts\python -m pip install --upgrade pip
.\.venv-toolkit\Scripts\python -m pip install -r requirements.txt
.\.venv-toolkit\Scripts\python -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

Expected output (the supplied v5.2.196 spec is a windowed one-file build):

```text
dist/SM3 Modding Toolkit.exe
```

Run from source without building:

```powershell
.\.venv-toolkit\Scripts\python SM3_TOOLS.py
```

## 3. Build The Audio Separator

Use a separate environment so the large Demucs/Torch dependencies remain isolated:

```powershell
py -3 -m venv .venv-audio
.\.venv-audio\Scripts\python -m pip install --upgrade pip
.\.venv-audio\Scripts\python -m pip install -r SM3_AUDIO_SEPARATOR/requirements.txt
Push-Location SM3_AUDIO_SEPARATOR
..\.venv-audio\Scripts\python -m PyInstaller SM3_AUDIO_SEPARATOR.spec --clean --noconfirm
Pop-Location
```

Expected output:

```text
SM3_AUDIO_SEPARATOR/dist/SM3 Audio Separator/SM3 Audio Separator.exe
SM3_AUDIO_SEPARATOR/dist/SM3 Audio Separator/Audio Runtime/
```

Run from source without building:

```powershell
.\.venv-audio\Scripts\python SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.py
```

## 4. Assemble The Public Folder

Create one release folder with this layout:

```text
SM3 Toolkit/
  SM3 Modding Toolkit.exe
  SM3 Audio Separator.exe
  Audio Runtime/
  Dependencies/
    VC_redist.x64.exe
```

Copy the two EXEs and their matching runtime folders from the two PyInstaller outputs. Do not merge the runtime folders.

Download the full current x64 Visual C++ Redistributable from Microsoft's official permalink:

```text
https://aka.ms/vc14/vc_redist.x64.exe
```

Verify its Microsoft Authenticode signature before release. Do not substitute a small third-party downloader.

## 5. Demucs Model Downloads

The Audio Separator includes Demucs and its runtime but intentionally excludes model weights. On the first separation with a selected model, the application displays a download notice and downloads the required model. Internet access is required until that first model download finishes.

The main Toolkit embeds its Python/Tkinter/Pillow/imageio-ffmpeg runtime in its
EXE. The Audio Separator keeps its larger Torch/Demucs files in the separate
`Audio Runtime` directory. Do not merge these applications.

## 6. Runtime Checks

From the assembled release folder:

```powershell
& '.\SM3 Audio Separator.exe' --verify-runtime
```

The Audio Separator command should return exit code `0`. Launch
`SM3 Modding Toolkit.exe` normally and confirm Home is selected, all 13 tabs
open, and the Motion Editor/How To/About checks in `RELEASE_NOTES_v5_2_196.md`.

## 7. Why PyInstaller Can Flag

PyInstaller bundles Python, Tkinter, and native dependencies. Some scanners heuristically flag unsigned bundled-Python applications, especially utilities that inspect and copy binary files. This repository provides the complete source and build specifications so the release can be reviewed and reproduced.

## 8. Content Notice

No original Spider-Man 3 game files, copied packs, extracted game assets, copyrighted game content, or Demucs model weights are included in this repository.
