# SM3 Modding Toolkit v5.2.202

Created by TSGAMING264

## Release Source

This update publishes the complete source used for the verified
`v5.2.202 FINAL STABILITY RELEASE` Windows build. The separate SM3 Audio
Separator remains at v1.0.3 and is still an official companion application.

## Updates Since v5.2.196

- Added local scrolling to Browse + Image and the Classic Workflow so their
  controls stay reachable on smaller displays.
- Added content-aware PC/Xbox pack routing while retaining the established
  direct APKF, normal HSAM, mash-at-`0x30`, and `.bin` routes.
- Added deterministic compact texture-preview paths and clearer stage-specific
  preview errors for long Windows paths.
- Kept shotariya as the sixth and final WoS contributor with the supplied
  avatar and `Material Combiner creator` credit.
- Added all built-in Motion Editor profile/preset JSON files to the PyInstaller
  bundle and added Windows file/product version `5.2.202.0`.
- Updated launcher and in-app version labels to v5.2.202.

No parser, patcher, resource identity, codec, Motion Editor math, or output
format was intentionally changed in this preservation and packaging pass.

## Verification Summary

- All 45 Toolkit Python files compiled and the application imported without
  auto-launching.
- The application constructed all 13 tabs with Home first and selected.
- Synthetic PC/Xbox routing, compact path, WRAP build/rebuild, component
  recovery, archive retargeting, and profile-loading checks passed.
- Critical WRAP, Motion Editor, PCPACK rebuild, pack extraction, animation
  swapper, and Xbox extraction backends are byte-identical to v5.2.201.
- The one-file Toolkit build contains FFmpeg, the shotariya avatar, and all
  four built-in data files.
- SM3 Modding Toolkit and SM3 Audio Separator launched independently, remained
  responsive, and exposed the same Toolkit icon.
- Source and release stages contained no `.pyc` or `__pycache__` files.

See `FINAL_VALIDATION_REPORT_v5_2_202.txt` for the full executed checks and
validation limits. No game files, game assets, built EXEs, Demucs model
weights, or local test output are committed to this repository.

These checks are regression coverage, not a guarantee of compatibility with
every mod or pack. Keep original backups and test generated output before
installing it.
