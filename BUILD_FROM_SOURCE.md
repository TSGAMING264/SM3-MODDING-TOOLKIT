# Build From Source

This guide is for Nexus reviewers and users who want to verify the EXE build.

## 1. Install Python

Install Python 3.10 or newer from python.org. During install, enable the option to add Python to PATH.

Verify:

```powershell
py -3 --version
```

## 2. Install Dependencies

From this source folder:

```powershell
py -3 -m pip install -r requirements.txt
```

## 3. Run From Source

```powershell
py -3 SM3_TOOLS.py
```

The main window should open as `SM3 MODDING TOOLKIT` and show these tabs:

1. Home
2. Pack Extractor
3. Hex Viewer
4. Tex Swapper
5. Texture Folder Viewer
6. Old Animation Swapper

Home is selected first with `tabs.select(0)`.

## 4. Build The EXE

```powershell
py -3 -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

Expected output:

```text
dist/SM3 MODDING TOOLKIT.exe
```

The spec file uses the Animation Swapper icon from `SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.ico`.

v5.2 is organized as one app package under `sm3_toolkit/`, with UI tabs in `sm3_toolkit/tabs/` and backend services in `sm3_toolkit/services/`.

## 5. Why PyInstaller Can Flag

PyInstaller bundles the Python runtime, application code, Tkinter files, and dependencies into a single Windows executable. Some automated scanners mark bundled Python EXEs as suspicious even when the source code is clean. This package includes the full tool source so the build can be reviewed and reproduced.

## 6. Content Notice

No Spider-Man 3 game files, PCPACK files, Xbox files, extracted game assets, or copyrighted game content are included in this source package.


## v5.2.10

How To Use tab added after Old Animation Swapper. About / Info remains the last tab.
