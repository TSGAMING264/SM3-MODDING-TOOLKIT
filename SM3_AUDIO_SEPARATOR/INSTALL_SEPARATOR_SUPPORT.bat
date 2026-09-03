@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

set "PY="
for %%P in ("%LocalAppData%\Programs\Python\Python313\python.exe" "%LocalAppData%\Programs\Python\Python312\python.exe" "%LocalAppData%\Programs\Python\Python311\python.exe" "%LocalAppData%\Programs\Python\Python310\python.exe") do (
    if exist %%~P set "PY=%%~P"
)
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    where python3 >nul 2>nul && set "PY=python3"
)
if not defined PY (
    echo Python was not found automatically.
    pause
    exit /b 1
)

echo Installing Demucs separator support...
call %PY% -m pip install --upgrade demucs soundfile
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo Install failed with code %ERR%.
    pause
    exit /b %ERR%
)

echo.
echo Install finished.
pause
endlocal
