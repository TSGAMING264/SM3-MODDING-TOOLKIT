# Security / False Positive Note

The public Windows applications are built with PyInstaller and are currently unsigned. PyInstaller bundles the Python interpreter, Tkinter, and native dependencies. Antivirus and hosting scanners can flag this packaging pattern heuristically, especially for tools that inspect, extract, copy, patch, or rebuild binary files.

This repository publishes the complete Python source and PyInstaller specifications so reviewers can inspect and reproduce both applications.

The source repository contains no compiled EXEs, Spider-Man 3 game files, extracted game assets, or Demucs model weights.

The public release's Visual C++ dependency should be the complete Microsoft-signed offline x64 redistributable from `https://aka.ms/vc14/vc_redist.x64.exe`, not a small web downloader.
