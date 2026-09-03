# Build From Source - Nexus Review

This repository is the public source for SM3 Toolkit v5.2.182 and its separate SM3 Audio Separator v1.0.3 companion application.

## Main Toolkit

```powershell
py -3 -m pip install -r requirements.txt
py -3 SM3_TOOLS.py
py -3 -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

Expected build:

```text
dist/SM3 Toolkit/SM3 Toolkit.exe
dist/SM3 Toolkit/Toolkit Runtime/
```

## Audio Separator

```powershell
py -3 -m pip install -r SM3_AUDIO_SEPARATOR/requirements.txt
Push-Location SM3_AUDIO_SEPARATOR
py -3 -m PyInstaller SM3_AUDIO_SEPARATOR.spec --clean --noconfirm
Pop-Location
```

Expected build:

```text
SM3_AUDIO_SEPARATOR/dist/SM3 Audio Separator/SM3 Audio Separator.exe
SM3_AUDIO_SEPARATOR/dist/SM3 Audio Separator/Audio Runtime/
```

The Audio Separator downloads the selected Demucs model on first use. Model weights are not included in this repository.

## Review Entry Points

- `SM3_TOOLS.py`: main Toolkit launcher
- `sm3_toolkit/app.py`: integrated Toolkit window and visible tabs
- `sm3_toolkit/tabs/`: user interface classes
- `sm3_toolkit/services/`: pack, texture, model, animation, sound, and rebuild logic
- `SM3_EXTRACTOR_FINAL/12_OLD_ANIMATION_SWAPPER/SM3_ANIMATION_SWAPPER.py`: legacy swapper source
- `SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.py`: companion separator source
- `SM3_MODDING_TOOLKIT.spec`: main PyInstaller build
- `SM3_AUDIO_SEPARATOR/SM3_AUDIO_SEPARATOR.spec`: separator PyInstaller build

## Review Notes

- No game files or extracted game assets are included.
- Original packs are not intentionally overwritten by normal workflows.
- Release workflows create output copies or extracted folders.
- No compiled EXEs are committed to this source repository.
- PyInstaller runtime bundling can trigger heuristic antivirus detections.
