@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title SM3 Toolkit - Install Sound Editor Audio Support

echo =====================================================
echo  SM3 TOOLKIT - SOUND EDITOR AUDIO SUPPORT v5.2.155
echo  Preferred method: Sound Editor ^> Music Replacement
echo  ^> INSTALL / REPAIR AUDIO SUPPORT
echo =====================================================
echo.

set "PYEXE="
set "PYARGS="

if defined VIRTUAL_ENV call :TRY_EXE "%VIRTUAL_ENV%\Scripts\python.exe" ""
if defined PYEXE goto FOUND
if defined CONDA_PREFIX call :TRY_EXE "%CONDA_PREFIX%\python.exe" ""
if defined PYEXE goto FOUND
if defined PYTHONHOME call :TRY_EXE "%PYTHONHOME%\python.exe" ""
if defined PYEXE goto FOUND
call :TRY_EXE "py.exe" "-3"
if defined PYEXE goto FOUND
call :TRY_EXE "python.exe" ""
if defined PYEXE goto FOUND
call :TRY_EXE "python3.exe" ""
if defined PYEXE goto FOUND

for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    call :TRY_EXE "%%B" ""
    if defined PYEXE goto FOUND
)
for /f "tokens=2,*" %%A in ('reg query "HKLM\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    call :TRY_EXE "%%B" ""
    if defined PYEXE goto FOUND
)
for /f "tokens=2,*" %%A in ('reg query "HKLM\Software\WOW6432Node\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    call :TRY_EXE "%%B" ""
    if defined PYEXE goto FOUND
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    call :TRY_EXE "%%~fD\python.exe" ""
    if defined PYEXE goto FOUND
)
for /d %%D in ("%ProgramFiles%\Python*") do (
    call :TRY_EXE "%%~fD\python.exe" ""
    if defined PYEXE goto FOUND
)
if defined ProgramFiles(x86) for /d %%D in ("%ProgramFiles(x86)%\Python*") do (
    call :TRY_EXE "%%~fD\python.exe" ""
    if defined PYEXE goto FOUND
)
call :TRY_EXE "%USERPROFILE%\miniconda3\python.exe" ""
if defined PYEXE goto FOUND
call :TRY_EXE "%USERPROFILE%\anaconda3\python.exe" ""
if defined PYEXE goto FOUND
call :TRY_EXE "%USERPROFILE%\scoop\apps\python\current\python.exe" ""
if defined PYEXE goto FOUND

echo Python was not located automatically. Select your python.exe in the file picker.
set "PICKED="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Locate Python 3.10+ python.exe'; $d.Filter='Python executable (python.exe)|python.exe|Executable files (*.exe)|*.exe'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.FileName}" 2^>nul`) do set "PICKED=%%P"
if defined PICKED call :TRY_EXE "%PICKED%" ""
if defined PYEXE goto FOUND

echo.
echo Could not START a Python 3.10+ interpreter. This is a location/version problem, not proof that Python is uninstalled.
pause
exit /b 1

:FOUND
echo Using exact interpreter:
echo   %PYEXE% %PYARGS%
>"%~dp0.sm3_python_exe.txt" echo %PYEXE%
>"%~dp0.sm3_python_args.txt" echo %PYARGS%
"%PYEXE%" %PYARGS% -c "import sys; print('Version:', sys.version.split()[0]); print('Executable:', sys.executable)"
echo.

"%PYEXE%" %PYARGS% -m pip --version >nul 2>nul
if errorlevel 1 (
    echo pip is missing; trying Python's built-in ensurepip...
    "%PYEXE%" %PYARGS% -m ensurepip --upgrade
    if errorlevel 1 (
        echo Python was found, but pip could not be enabled.
        pause
        exit /b 2
    )
)

"%PYEXE%" %PYARGS% -m pip install --upgrade "imageio-ffmpeg>=0.6.0"
if errorlevel 1 (
    echo.
    echo Python was found, but imageio-ffmpeg installation failed.
    pause
    exit /b 3
)

"%PYEXE%" %PYARGS% -c "import imageio_ffmpeg; print('FFmpeg ready:', imageio_ffmpeg.get_ffmpeg_exe())"
if errorlevel 1 (
    echo Package installed but FFmpeg verification failed. Restart the toolkit and use CHECK/INSTALL inside Sound Editor.
    pause
    exit /b 4
)

echo.
echo SUCCESS - Music Replacement Mode audio support is ready.
pause
exit /b 0

:TRY_EXE
set "_CAND=%~1"
set "_ARGS=%~2"
if "%_CAND%"=="" exit /b 1
"%_CAND%" %_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "PYEXE=%_CAND%"
set "PYARGS=%_ARGS%"
exit /b 0
