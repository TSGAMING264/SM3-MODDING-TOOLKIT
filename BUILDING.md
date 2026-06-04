# Building SM3 MODDING TOOLKIT

## Python Version

Use Python 3.10 or newer on Windows.

## Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

## Run From Source

```powershell
python SM3_TOOLS.py
```

If the Windows Python launcher is configured:

```powershell
py -3 SM3_TOOLS.py
```

## Optional Windows EXE Build

This repository includes a PyInstaller spec file:

```powershell
python -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

The built executable should appear at:

```text
dist/SM3 MODDING TOOLKIT.exe
```

Release builds should be made from this same public source checkout. Do not add copied game packs, extracted assets, report bundles, caches, or local test output to the release repository.
