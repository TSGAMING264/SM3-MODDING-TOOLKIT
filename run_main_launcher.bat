@echo off
setlocal
cd /d "%~dp0"
title SM3 Modding Toolkit v5.2 Beta
echo Starting SM3 Modding Toolkit v5.2 Beta...
py -3 SM3_TOOLS.py
if errorlevel 1 (
  echo.
  echo py launcher failed. Trying python...
  python SM3_TOOLS.py
)
if errorlevel 1 (
  echo.
  echo Python could not start SM3_TOOLS.py.
  echo Install Python 3 with Tkinter enabled, then run this BAT again.
  pause
)
