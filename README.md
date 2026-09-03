![SM3 Toolkit cover](https://raw.githubusercontent.com/TSGAMING264/SM3-MODDING-TOOLKIT/main/docs/images/sm3_collectors_edition_cover.jpg)

# SM3 Modding Toolkit

**Created by TSGAMING264**

SM3 Modding Toolkit is an unofficial fan-made Python/Tkinter toolkit for Spider-Man 3 PC modding research and testing. The public package contains two separate Windows applications:

- **SM3 Toolkit**: the main pack, texture, model, animation, audio, rebuild, and inspection application.
- **SM3 Audio Separator**: a companion Demucs application for separating dialogue and music.

The two applications are intentionally kept separate. They can run independently from the same release folder and use separate private runtime folders.

## Current Source Versions

- SM3 Toolkit: **v5.2.182**
- SM3 Audio Separator: **v1.0.3**

This repository contains source code and build instructions. It does not contain the compiled release EXEs, game packs, extracted game assets, or Demucs model weights.

## Main Toolkit Tabs

1. Home
2. Pack Extractor
3. Hex/Text
4. Tex Swapper
5. Texture Folder Viewer
6. MAT Editor
7. Model Viewer
8. New Animation Swapper
9. Old Animation Swapper
10. Sound Editor
11. PCPACK Rebuild Lab
12. How To Use
13. About / Info

Home is selected on startup. The release UI uses one Tk root and one integrated notebook.

## Safety

- Original game files are not intentionally modified by normal release workflows.
- Extraction reads from the selected pack and writes to a separate output folder.
- Texture, animation, sound, and rebuild workflows create new output copies.
- Keep clean backups and test one change at a time.
- No Spider-Man 3 game files, PCPACKs, PCAPKs, APKFs, Xbox packs, DDS dumps, or extracted assets are included.
- Normal release workflows do not create Send-To-GPT bundles or internal research report packages.

## Repository Layout

```text
SM3_TOOLS.py                    Main Toolkit launcher
sm3_toolkit/                    Integrated Toolkit UI and services
SM3_EXTRACTOR_FINAL/            Legacy Animation Swapper source/presets
SM3_MODDING_TOOLKIT.spec        Main Toolkit PyInstaller build
SM3_AUDIO_SEPARATOR/            Separate Audio Separator source/build
BUILD_FROM_SOURCE.md            Detailed reproducible build guide
BUILD_FROM_SOURCE_NEXUS.md      Nexus reviewer build notes
SOURCE_MANIFEST_SHA256.csv      Source integrity manifest
```

## Run The Toolkit From Source

Requirements:

- Windows 10 or 11
- Python 3.10 or newer with Tkinter
- Pillow
- imageio-ffmpeg for Sound Editor music replacement

```powershell
py -3 -m pip install -r requirements.txt
py -3 SM3_TOOLS.py
```

## Run The Audio Separator From Source

The Audio Separator has its own dependency list because Demucs and Torch are much larger than the main Toolkit dependencies.

```powershell
py -3 -m pip install -r SM3_AUDIO_SEPARATOR/requirements.txt
py -3 SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.py
```

The selected Demucs model downloads automatically on first use. The application displays a clear download notice and remains responsive. Model weights are not stored in this repository or release ZIP.

## Build Windows Releases

Main Toolkit:

```powershell
py -3 -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

Audio Separator:

```powershell
Push-Location SM3_AUDIO_SEPARATOR
py -3 -m PyInstaller SM3_AUDIO_SEPARATOR.spec --clean --noconfirm
Pop-Location
```

See [BUILD_FROM_SOURCE.md](BUILD_FROM_SOURCE.md) for the complete two-EXE packaging procedure.

## Antivirus False Positives

PyInstaller bundles the Python runtime and native dependencies into a Windows application folder. Unsigned bundled-Python applications that inspect, extract, copy, or rebuild binary files can trigger reputation-based or heuristic detections. The complete source is published here so users and Nexus Mods reviewers can inspect and reproduce both builds.

The release package uses Microsoft's official full offline x64 Visual C++ Redistributable. That Microsoft-signed installer is a release dependency and is not committed to this source repository.

## Credits

Created by **TSGAMING264**.

Huge shoutout to **Devryx** and the developers and reverse engineers connected to the Web of Shadows Toolkit projects for inspiration and reference. SM3 Modding Toolkit is a separate Spider-Man 3 PC project.

## Disclaimer

This is an unofficial fan-made modding tool. It is not affiliated with Activision, Treyarch, Marvel, Sony, or any official Spider-Man game developer or publisher. Spider-Man and related names belong to their respective owners.
