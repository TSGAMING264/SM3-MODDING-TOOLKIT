# Build From Source - Nexus Review

## Requirements

- Python 3.10+ recommended
- Tkinter included with most Python installations
- Pillow is recommended for image preview features

## Run from source

```bash
python SM3_TOOLS.py
```

The main toolkit source file is included at:
`SM3_TOOLS.py`

The animation swapper source file requested by Nexus is included at:
`SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py`

A duplicate source-review copy is also included at:
`NEXUS_REVIEW_FILES/SM3_ANIMATION_SWAPPER.py`

## Optional dependency install

```bash
python -m pip install -r requirements.txt
```

## Optional PyInstaller build

```bash
python -m pip install pyinstaller
pyinstaller SM3_MODDING_TOOLKIT.spec
```

## Review notes

- No game assets are included in this source package.
- The source package is intended for review and reproducible building.
- Public release EXE detections may come from PyInstaller bundling behavior.
