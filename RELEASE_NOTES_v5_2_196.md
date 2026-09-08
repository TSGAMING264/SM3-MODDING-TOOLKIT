# SM3 Modding Toolkit v5.2.196

Created by TSGAMING264

## Release Source

This update publishes the complete source used for the verified
`v5.2.196 FINAL ABOUT CREDIT` Windows build. The separate SM3 Audio Separator
remains at v1.0.3 and is still an official companion application.

## Updates Since v5.2.182

- Restored and verified Motion Editor AUTO-GROW + RELOCATE for compressed edits
  that no longer fit the original ANIM payload.
- Added ANIM-specific NativeWRAP rebuilding for resized Motion Editor output,
  including pointer-target relocation and byte-exact unwrap verification.
- Added Slot 2 owner recovery for rebuilt `.anim` / `.wrap.anim` files located
  outside `WRAP_EXTRACTS`.
- Added canonical `.wrap.anim` filename cleanup and fail-closed owner checks.
- Added Player Goblin `0x900E49A5` / `ch_goblin` 74-bone character profile.
- Preserved Spider-Man, Black Suit, and Peter Parker mapping on the shared
  `0xCFB154CD` profile, with hash checks that prevent mismatched skeleton use.
- Updated the built-in How To for AUTO-GROW, Classic ANIM, WRAP.ANIM, XESM3,
  and the final Slot 1 / Slot 2 workflow.
- Added AkyrosXD and Bread About images/credits. Bread is the final community
  card with the exact role text `IDA coding for SM3`.
- Updated the PyInstaller spec to bundle all runtime character-profile and
  animation-preset JSON data required by the frozen Motion Editor.

The extraction, texture, material, model, animation, sound, Xbox, and PCPACK
backend implementations are published as supplied by the v5.2.196 source.

## Verification Summary

The final local build used Python 3.13.14 x64 and PyInstaller 6.20.0.

- All application Python files compiled and all release tabs imported.
- The packaged main EXE opened all 13 tabs with Home selected first.
- The exact `0x5634CAF3.sm3sprint` regression required 30,020 bits versus the
  original 29,952-bit capacity; AUTO-GROW added 12 bytes and re-decoded the
  requested frame values exactly.
- Resized WRAP.ANIM rebuilding, owner recovery, identity checks, canonical name
  handling, and wrong-Slot-2 rejection passed.
- A 19.6 MB local CH_SPIDERMAN pack produced 892 NativeWRAP resources with zero
  skipped resources, parse errors, or unresolved patch targets.
- Classic extraction, byte-identical no-change PCPACK rebuild, strict DDS
  validation, old swapper same-payload control, MAT reset, and mesh parsing
  checks passed on local fixtures.
- Bread's final About card and avatar rendered in the packaged application.
- The Audio Separator packaged runtime check returned exit code 0 and its
  first-use model-download notice rendered correctly.

Game fixtures, built EXEs, Demucs model weights, generated output, and local
test reports are not committed to this source repository.

These checks are concrete regression coverage, not a guarantee of compatibility
with every mod or pack. Keep original backups and test generated outputs before
installing them. A clean-Windows and in-game smoke test is still recommended.
