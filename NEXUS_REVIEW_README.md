# SM3 Modding Toolkit - Nexus Mods Source Review Package

This source package is provided for Nexus Mods review.

## What this is

SM3 Modding Toolkit is a fan-made Spider-Man 3 PC modding toolkit created by TSGAMING264.  
It is written in Python/Tkinter and is intended for pack inspection, texture workflows, hex viewing, texture folder previewing, and safe experimental animation-swap workflows.

## Why virus scanners may flag the release EXE

The public release build may be packaged with PyInstaller so Windows users can run it without setting up Python manually. PyInstaller bundles the Python runtime and many support files into an executable/distribution folder, which can trigger heuristic antivirus detections even when the source itself is normal Python code.

This source package is included so Nexus staff can review the actual code directly.

## Important safety behavior

- Original game files are not intentionally modified directly.
- Pack extraction is read/extract only.
- Texture swapping writes patched copies and uses strict DDS validation.
- Animation swapping is experimental and only allows compatible same-size/layout swaps into existing PC animation slots.
- No game files, PCPACKs, APKFs, extracted assets, or copyrighted Spider-Man 3 content are included in this source package.

## Main files for review

- `SM3_TOOLS.py` - launcher entry point.
- `SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py` - animation swapper source file requested for review.
- `NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py` - duplicate source-review copy for easier Nexus review access.
- `sm3_toolkit/app.py` - main application / tab setup.
- `sm3_toolkit/tabs/` - integrated tab UI code.
- `sm3_toolkit/services/` - backend/helper service code.
- `SM3_MODDING_TOOLKIT.spec` - PyInstaller spec file.
- `requirements.txt` - Python dependencies.
- `BUILD_FROM_SOURCE.md` - build/run instructions.
- `SOURCE_MANIFEST_SHA256.csv` - SHA256 manifest for source review.

The animation swapper source file requested by Nexus is included at:
`SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py`

A duplicate source-review copy is also included at:
`NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py`

The main toolkit source file is included at:
`SM3_TOOLS.py`

## Visible release tabs

- Home
- Pack Extractor
- Hex Viewer
- Tex Swapper
- Texture Folder Viewer
- Old Animation Swapper
- How To Use
- About / Info

## Notes

This is a source-review package. It is not meant to include a compiled executable.
