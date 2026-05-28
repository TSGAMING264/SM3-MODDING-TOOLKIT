# Security / False Positive Note

Nexus Mods asked why the tool produced many virus scanner results.

The likely reason is the packaging method, not the Python source behavior:

- The release build may use PyInstaller.
- PyInstaller bundles the Python interpreter/runtime and many binary support files.
- Antivirus engines sometimes flag bundled Python executables heuristically.
- This source package is provided so reviewers can inspect the real Python/Tkinter source directly.

This source package does not include game assets and does not include a compiled EXE.
