<p align="center">
  <img src="docs/images/sm3_collectors_edition_cover.jpg" alt="SM3 Collector's Edition cover art" width="360">
</p>

<p align="center">
  <img src="docs/images/sm3_black_suit_wallpaper.jpg" alt="SM3 black suit wallpaper" width="850">
</p>

# SM3 MODDING TOOLKIT

<p align="center">
  <img src="sm3_toolkit/assets/tsgaming264_profile.png" alt="TSGAMING264" width="160">
</p>

**Created by TSGAMING264**

SM3 MODDING TOOLKIT is an unofficial fan-made **Spider-Man 3 PC** modding toolkit focused on making Spider-Man 3 easier to research, extract, view, and test.

This project is still in a **beta / release-candidate phase**. A lot of work still needs to be done. I am really hoping more people can help with Spider-Man 3 modding and research. I wanted Spider-Man 3 to get more mod support, and at least I was able to contribute something useful to the community.

**GitHub media note:** the images at the top are README presentation artwork only. They are not required for the tool to run and are not extracted from game pack files.

## What This Tool Includes

- **Pack Extractor** — list and extract supported Spider-Man 3 PC pack/resource data.
- **Hex Viewer** — safe read-only file viewer for packs, binaries, text, HTML, and other files.
- **Tex Swapper** — experimental Spider-Man 3 texture swap/patch-copy workflow with strict safety checks.
- **Texture Folder Viewer** — preview DDS/texture folders and quickly reveal files.
- **Old Animation Swapper** — experimental animation swap testing using existing PC destination slots and same-size/layout safety rules.
- **How To Use** tab — built-in usage guide.
- **About / Info** tab — toolkit info, creator credit, and beta status.
- **Language selector** — English, Arabic, Português (Brazil), Filipino, Türkçe, Français, Deutsch, Español, Italiano, and 日本語.

## Important Safety Notes

- **No Spider-Man 3 game data files are included.**
- **No PCPACK, PCAPK, APKF, XEPACK, PS3PACK, or extracted game assets are included.**
- Always back up your original files before testing any modding workflow.
- The Pack Extractor does not modify original packs.
- The public Pack Extractor flow is cleaned so release users do not receive `00_REPORTS`, `00_MASTER_REPORTS`, or Send-To-GPT report ZIP bundles in the output.
- Tex Swapper and Old Animation Swapper are experimental. They are designed around patched-copy workflows instead of direct original-file overwrite.
- Old Animation Swapper should only patch a source animation payload into an existing PC destination slot when size/component layout rules match.

## Source Files Nexus Asked For

The main toolkit source is included here:

```text
SM3_TOOLS.py
sm3_toolkit/
```

The animation swapper source requested for review is included here:

```text
SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py
NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py
```

## Requirements

- Windows 10/11 recommended
- Python 3.10 or newer
- Tkinter, normally included with Python on Windows
- Pillow, for image/texture previews
- PyInstaller, only needed if building the EXE

Install requirements:

```powershell
py -3 -m pip install -r requirements.txt
```

Run from source:

```powershell
py -3 SM3_TOOLS.py
```

Or run:

```powershell
run_main_launcher.bat
```

## Build EXE

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

The built executable should appear under:

```text
dist/SM3 MODDING TOOLKIT.exe
```

## Virus Scanner / False Positive Note

PyInstaller apps sometimes trigger antivirus heuristic warnings because the Python runtime, bytecode, Tkinter support files, and dependencies are bundled together. This source package is provided so reviewers can inspect the code and rebuild the EXE from source.

## Credits / Shoutout

Created by **TSGAMING264**.

Shoutout to **Devryx** and the **Web of Shadows Toolkit** developers for inspiration on how a public Spider-Man modding toolkit can be presented and shared. This SM3 toolkit is a separate Spider-Man 3 project and does not include Spider-Man: Web of Shadows game files or copyrighted game content.

## Disclaimer

This is an unofficial fan-made modding tool. It is not affiliated with Activision, Treyarch, Marvel, Sony, or any official Spider-Man game developer or publisher. Spider-Man and related names belong to their respective owners.

## Current Version

**v5.2.13 RELEASE CANDIDATE SOURCE — GitHub-ready normalized package**

Key release-candidate cleanup:

- `SM3_TOOLS.py` included at the repository root.
- `SM3_ANIMATION_SWAPPER.py` included for Nexus review.
- Pack Extractor public release cleanup removes report leftovers from visible output.
- No game assets included.
- No local real-name/path leaks detected in this prepared package.
- Source compiles successfully with Python compile checks.
