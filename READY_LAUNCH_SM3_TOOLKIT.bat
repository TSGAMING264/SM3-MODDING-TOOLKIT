@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title SM3 Modding Toolkit v5.2.182

echo ================================================
echo   SM3 MODDING TOOLKIT v5.2.182
echo   BUILT-IN HOW TO RELEASE
echo ================================================
echo.

set "PYEXE="
set "PYARGS="
set "CACHE_EXE=%~dp0.sm3_python_exe.txt"
set "CACHE_ARGS=%~dp0.sm3_python_args.txt"
set "LEGACY_CACHE=%~dp0.sm3_python_path.txt"

rem 1) Reuse the Python command that already worked.
if exist "%CACHE_EXE%" (
    set /p SAVEDPY=<"%CACHE_EXE%"
    set "SAVEDARGS="
    if exist "%CACHE_ARGS%" set /p SAVEDARGS=<"%CACHE_ARGS%"
    if defined SAVEDPY (
        call :CHECK_PYTHON "%SAVEDPY%" "%SAVEDARGS%"
        if not errorlevel 1 goto START_TOOLKIT
    )
)

rem Compatibility with v5.2.152's one-line path cache.
if exist "%LEGACY_CACHE%" (
    set /p SAVEDPY=<"%LEGACY_CACHE%"
    if defined SAVEDPY (
        call :CHECK_PYTHON "%SAVEDPY%" ""
        if not errorlevel 1 goto START_TOOLKIT
    )
)

rem 2) Normal Windows Python commands.
call :CHECK_PYTHON "py.exe" "-3"
if not errorlevel 1 goto START_TOOLKIT
call :CHECK_PYTHON "python.exe" ""
if not errorlevel 1 goto START_TOOLKIT
call :CHECK_PYTHON "python3.exe" ""
if not errorlevel 1 goto START_TOOLKIT

rem 3) Active environments.
if defined VIRTUAL_ENV (
    call :CHECK_PYTHON "%VIRTUAL_ENV%\Scripts\python.exe" ""
    if not errorlevel 1 goto START_TOOLKIT
)
if defined CONDA_PREFIX (
    call :CHECK_PYTHON "%CONDA_PREFIX%\python.exe" ""
    if not errorlevel 1 goto START_TOOLKIT
)
if defined PYTHONHOME (
    call :CHECK_PYTHON "%PYTHONHOME%\python.exe" ""
    if not errorlevel 1 goto START_TOOLKIT
)

rem 4) Common install folders.
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do call :CHECK_AND_MARK "%%~fD\python.exe"
if defined PYEXE goto START_TOOLKIT
for /d %%D in ("%ProgramFiles%\Python*") do call :CHECK_AND_MARK "%%~fD\python.exe"
if defined PYEXE goto START_TOOLKIT
if exist "%ProgramFiles(x86)%" for /d %%D in ("%ProgramFiles(x86)%\Python*") do call :CHECK_AND_MARK "%%~fD\python.exe"
if defined PYEXE goto START_TOOLKIT
if exist "%USERPROFILE%\miniconda3\python.exe" call :CHECK_PYTHON "%USERPROFILE%\miniconda3\python.exe" ""
if defined PYEXE goto START_TOOLKIT
if exist "%USERPROFILE%\anaconda3\python.exe" call :CHECK_PYTHON "%USERPROFILE%\anaconda3\python.exe" ""
if defined PYEXE goto START_TOOLKIT
if exist "%USERPROFILE%\scoop\apps\python\current\python.exe" call :CHECK_PYTHON "%USERPROFILE%\scoop\apps\python\current\python.exe" ""
if defined PYEXE goto START_TOOLKIT

rem 5) Manual picker only if automatic startup failed.
echo Automatic startup could not locate a working Python 3.10+.
echo Select the python.exe you already have installed.
echo.
set "PICKED="
for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Select your Python 3.10+ python.exe'; $d.Filter='Python executable (python.exe)|python.exe|Executable files (*.exe)|*.exe'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){$d.FileName}" 2^>nul`) do set "PICKED=%%P"
if defined PICKED (
    call :CHECK_PYTHON "%PICKED%" ""
    if not errorlevel 1 goto START_TOOLKIT
)

echo.
echo ERROR: The launcher could not START a Python 3.10+ interpreter.
echo This does NOT mean Python is uninstalled.
echo.
echo Diagnostic commands:
echo     py -0p
echo     where py
echo     where python
echo.
pause
exit /b 1

:START_TOOLKIT
echo Python ready:
echo   %PYEXE% %PYARGS%
"%PYEXE%" %PYARGS% -c "import sys; print('  Version:', sys.version.split()[0]); print('  Executable:', sys.executable)"
echo.

rem tkinter is a separate check; never call this "Python not detected".
"%PYEXE%" %PYARGS% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python works, but tkinter/Tcl-Tk is missing.
    echo Repair/install a standard Python.org build with Tcl/Tk support.
    echo.
    pause
    exit /b 2
)

rem Pillow is used by existing toolkit tabs. Repair it explicitly if missing.
"%PYEXE%" %PYARGS% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Pillow is missing. Installing it now...
    "%PYEXE%" %PYARGS% -m pip install --upgrade Pillow
    if errorlevel 1 (
        echo.
        echo ERROR: Pillow installation failed.
        pause
        exit /b 3
    )
)

echo Starting SM3 Toolkit...
echo.
"%PYEXE%" %PYARGS% "%~dp0SM3_TOOLS.py"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0

echo.
echo ================================================
echo   SM3 TOOLKIT STARTUP FAILED - CODE %RC%
echo ================================================
echo.
if exist "%~dp0SM3_TOOLKIT_STARTUP_ERROR.txt" (
    echo Full Python traceback:
    echo   %~dp0SM3_TOOLKIT_STARTUP_ERROR.txt
    echo.
    type "%~dp0SM3_TOOLKIT_STARTUP_ERROR.txt"
) else (
    echo No startup traceback file was created.
)
echo.
echo Keep this window open or send a screenshot of this error.
pause
exit /b %RC%

:CHECK_AND_MARK
if not exist "%~1" exit /b 1
call :CHECK_PYTHON "%~1" ""
exit /b %ERRORLEVEL%

:CHECK_PYTHON
set "CAND=%~1"
set "CANDARG=%~2"
if "%CAND%"=="" exit /b 1
"%CAND%" %CANDARG% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if errorlevel 1 exit /b 1
set "PYEXE=%CAND%"
set "PYARGS=%CANDARG%"
>"%CACHE_EXE%" echo %CAND%
>"%CACHE_ARGS%" echo %CANDARG%
exit /b 0
