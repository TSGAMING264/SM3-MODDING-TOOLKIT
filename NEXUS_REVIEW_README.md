# SM3 Modding Toolkit - Nexus Source Review

SM3 Modding Toolkit is an unofficial fan-made Spider-Man 3 PC modding toolkit created by TSGAMING264.

This repository provides the full reviewable source for:

- SM3 Modding Toolkit v5.2.196 FINAL ABOUT CREDIT
- SM3 Audio Separator v1.0.3, shipped as a separate companion application

## Why The Windows Build May Be Flagged

The public Windows programs are packaged with PyInstaller. PyInstaller bundles Python, Tkinter, and native dependencies into application/runtime folders. Unsigned bundled-Python tools that inspect, extract, copy, and rebuild binary files can receive heuristic detections even when the source is normal Python code.

## Safety Behavior

- Normal workflows create extracted folders, patched copies, or rebuilt output files.
- Original game packs are not intentionally modified directly.
- Hex/Text is read-only.
- Texture replacement validates target layout and writes a copy.
- Animation and audio workflows write separate output files.
- No game files, PCPACKs, APKFs, extracted assets, or Demucs model weights are included.

## Visible Toolkit Tabs

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

## Main Review Files

- `SM3_TOOLS.py`
- `sm3_toolkit/app.py`
- `sm3_toolkit/tabs/`
- `sm3_toolkit/services/`
- `SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py`
- `NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py`
- `SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.py`
- `SM3_MODDING_TOOLKIT.spec`
- `SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.spec`
- `BUILD_FROM_SOURCE_NEXUS.md`
- `SOURCE_MANIFEST_SHA256.csv`

The duplicate file under `NEXUS_REVIEW_FILES/` is kept synchronized with the legacy swapper source for convenient review.
