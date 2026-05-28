# GitHub Upload Setup for SM3 MODDING TOOLKIT

Recommended repository name:

```text
SM3-MODDING-TOOLKIT
```

Recommended public description:

```text
Unofficial beta Spider-Man 3 PC modding toolkit by TSGAMING264 for pack extraction, texture viewing/swapping, read-only hex viewing, and animation swap testing. No game files included.
```

Recommended GitHub topics:

```text
spider-man-3, sm3, modding, toolkit, pc-modding, textures, hex-viewer, tkinter, python, tsgaming264
```

## Fast Upload Through GitHub Website

1. Go to GitHub and create a new repository named `SM3-MODDING-TOOLKIT`.
2. Make it **public** if you want Nexus to review it easily, or private and add Nexus support if they asked for private access.
3. Do not add a starter README during creation because this package already includes one.
4. Upload everything from this folder into the repository root.
5. Commit with this message:

```text
Initial SM3 Modding Toolkit source release
```

## Upload With Git Commands

From inside this folder:

```powershell
git init
git add .
git commit -m "Initial SM3 Modding Toolkit source release"
git branch -M main
git remote add origin https://github.com/TSGAMING264/SM3-MODDING-TOOLKIT.git
git push -u origin main
```

## Nexus Review Message

Use the included file:

```text
NEXUS_SUPPORT_REPLY_TEMPLATE.txt
```

Important files to point Nexus to:

```text
SM3_TOOLS.py
SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py
NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py
BUILD_FROM_SOURCE_NEXUS.md
NO_GAME_ASSETS_INCLUDED.txt
SECURITY_FALSE_POSITIVE_NOTE.md
SOURCE_MANIFEST_SHA256.csv
```

## Keep These Out of GitHub

Do not upload any original game files or test dumps:

```text
*.PCPACK
*.pcpack
*.PCAPK
*.pcapk
*.APKF
*.apkf
*.XEPACK
*.xepack
*.PS3PACK
*.ps3pack
*.pak
00_REPORTS/
00_MASTER_REPORTS/
SM3_EXTRACT_OUTPUT/
dist/
build/
__pycache__/
*.pyc
```

The `.gitignore` already blocks these.

## README Images

This repo-ready package includes the requested GitHub README images here:

```text
docs/images/sm3_collectors_edition_cover.jpg
docs/images/sm3_black_suit_wallpaper.jpg
```

The README already references them at the top, similar to the visual style used by the WOS Toolkit page. These files are presentation media only and are not required for the program to run. For a strict source-code-only submission, remove `docs/images/` before upload.

