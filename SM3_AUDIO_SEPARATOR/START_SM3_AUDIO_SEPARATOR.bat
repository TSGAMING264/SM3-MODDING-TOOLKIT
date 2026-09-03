@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

set "SCRIPT=SM3_AUDIO_SEPARATOR.py"
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
    echo Please install Python 3, or edit this BAT to point to your python.exe.
    pause
    exit /b 1
)

echo Launching %SCRIPT% ...
call %PY% "%SCRIPT%"
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo.
    echo The tool exited with code %ERR%.
)
echo.
pause
endlocal
