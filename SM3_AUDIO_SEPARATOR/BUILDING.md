# Building SM3 Audio Separator

SM3 Audio Separator is a separate companion application. It is not embedded in the main Toolkit EXE.

From the repository root:

```powershell
py -3 -m venv .venv-audio
.\.venv-audio\Scripts\python -m pip install --upgrade pip
.\.venv-audio\Scripts\python -m pip install -r SM3_AUDIO_SEPARATOR/requirements.txt
Push-Location SM3_AUDIO_SEPARATOR
..\.venv-audio\Scripts\python -m PyInstaller SM3_AUDIO_SEPARATOR.spec --clean --noconfirm
Pop-Location
```

The result is written under `SM3_AUDIO_SEPARATOR/dist/SM3 Audio Separator/`.

Demucs model weights are downloaded on first use and are intentionally excluded from source and release packages.
