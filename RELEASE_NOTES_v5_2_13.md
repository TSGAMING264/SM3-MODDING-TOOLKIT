# SM3 Modding Toolkit v5.2.13 Release Candidate

Created by TSGAMING264

## Final Cleanup

- `SM3_TOOLS.py` is included at the source root for Nexus/source review.
- `SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py` is included.
- `NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py` is included as a duplicate review copy.
- Nexus review docs explain that the toolkit is Python/Tkinter and that PyInstaller EXE detections can be heuristic false positives.
- No original Spider-Man 3 game files, PCPACK/PCAPK/APKF archives, or extracted game assets are included.
- About / Info profile image is bundled into the EXE.
- Language selector added for English, Arabic, Português (Brazil), Filipino, Türkçe, Français, Deutsch, Español, Italiano, and 日本語.

## Pack Extractor

- Pack Extractor is read/extract only and does not modify original packs.
- The release UI does not expose Open Reports.
- Temporary `00_REPORTS`, `00_MASTER_REPORTS`, and report zip bundles are removed after release List Contents or Extract actions.

## Tex Swapper

- Tex Swapper is experimental and is not a full pack browser.
- Use Pack Extractor for general pack viewing/extraction.
- Tex Swapper patches copies only.
- DDS replacements should match width, height, format, mip count, and payload size.
- Some packs have no supported textures, and that is not always a bug.

## Old Animation Swapper

- Old Animation Swapper is experimental.
- Safe swaps only: this tool replaces an existing PC animation slot with a compatible source payload.
- Source animation must match the destination slot size/layout.
- Animations not present as compatible PC slots cannot be injected safely.
- PC slot identity/name/hash stays the same.
- Same-name/no-change swaps are blocked.
- Patch output copy only, never the original pack.
