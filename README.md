![image](https://raw.githubusercontent.com/TSGAMING264/SM3-MODDING-TOOLKIT/main/docs/images/sm3_collectors_edition_cover.jpg)

# SM3 MODDING TOOLKIT

**Created by TSGAMING264**

SM3 MODDING TOOLKIT is an unofficial fan-made Python/Tkinter toolkit for Spider-Man 3 PC modding research, pack inspection, texture workflow testing, hex viewing, and animation swap testing.

This project is still in a **beta / release-candidate phase**. A lot of work still needs to be done. I am hoping more people can help bring Spider-Man 3 PC more mod support, and this source release is provided so the community and Nexus Mods staff can review how the tool works.

![image](https://raw.githubusercontent.com/TSGAMING264/SM3-MODDING-TOOLKIT/main/docs/images/sm3_black_suit_wallpaper.jpg)

## Public Release Safety

- No Spider-Man 3 game files or extracted game assets are included in this repository.
- No PCPACK, PCAPK, APKF, XEPACK, PS3PACK, DDS dumps, copied game packs, or generated extraction outputs are included.
- The toolkit works on files the user selects or copies locally. Original game files are not modified directly by the normal workflow.
- Pack editing workflows are designed to create patched copies or exported output folders.
- Temporary report, cache, build, and diagnostic bundle outputs are blocked by `.gitignore` and are not part of the public source release.

## What This Tool Includes

- **Pack Extractor**: reads copied Spider-Man 3 PC pack files, lists contents, and extracts supported resources for review.
- **Texture tools**: preview and texture patch-copy workflows for testing replacement textures.
- **Texture Folder Viewer**: view folders of texture images safely.
- **Hex Viewer**: read-only file viewing for packs, binaries, and text files.
- **Old Animation Swapper**: experimental animation swap testing using copied pack files and same-size/layout safety rules.
- **How To Use / About tabs**: built-in usage notes, credits, and beta status.

## Source Files For Review

Main launcher:

```text
SM3_TOOLS.py
```

Toolkit package:

```text
sm3_toolkit/
```

Animation swapper source requested for Nexus review:

```text
NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py
SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py
```

## Requirements

- Windows 10/11 recommended
- Python 3.10 or newer
- Tkinter, normally included with Python on Windows
- Pillow, for image/texture previews
- PyInstaller, only needed for Windows EXE builds

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run from source:

```powershell
python SM3_TOOLS.py
```

If your Windows Python launcher is configured, this also works:

```powershell
py -3 SM3_TOOLS.py
```

## Windows Build

The repository includes a PyInstaller spec file for local Windows builds:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

The built EXE should appear under:

```text
dist/SM3 MODDING TOOLKIT.exe
```

Release builds should be made from this same public source checkout.

## Antivirus False Positives

Unsigned packaged Windows utilities can trigger antivirus heuristic warnings, especially when built with PyInstaller and when the tool performs file reading, extraction, copying, and rebuild-style operations. This source repository is provided so reviewers can inspect the Python code and rebuild the executable themselves.

## Credits / Shoutout

Created by **TSGAMING264**.

Shoutout to **Devryx** and the **Web of Shadows Toolkit** developers for inspiration on how public Spider-Man modding tools can be presented and shared. This SM3 toolkit is a separate Spider-Man 3 PC project and does not include Spider-Man: Web of Shadows files or Spider-Man 3 game assets.

## Disclaimer

This is an unofficial fan-made modding tool. It is not affiliated with Activision, Treyarch, Marvel, Sony, or any official Spider-Man game developer or publisher. Spider-Man and related names belong to their respective owners.
