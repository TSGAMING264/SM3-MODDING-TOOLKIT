# Building SM3 Modding Toolkit

The detailed reproducible instructions are maintained in [BUILD_FROM_SOURCE.md](BUILD_FROM_SOURCE.md).

Quick main Toolkit build:

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller SM3_MODDING_TOOLKIT.spec --clean --noconfirm
```

Quick Audio Separator build:

```powershell
py -3 -m pip install -r SM3_AUDIO_SEPARATOR/requirements.txt
Push-Location SM3_AUDIO_SEPARATOR
py -3 -m PyInstaller SM3_AUDIO_SEPARATOR.spec --clean --noconfirm
Pop-Location
```

Do not commit `build/`, `dist/`, model weights, game packs, extracted assets, or generated output.
