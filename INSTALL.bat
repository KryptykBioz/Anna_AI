@echo off
title Anna AI - Setup & Installation
color 0B

REM ── Check for admin ───────────────────────────────────────────────────────
net session >nul 2>&1
if %errorlevel% NEQ 0 (
    echo.
    echo  [!!] This installer works best when run as Administrator.
    echo       Some steps (GPU drivers, audio cables) may require elevated access.
    echo.
    choice /M "  Continue without admin rights?"
    if errorlevel 2 (
        echo  Right-click INSTALL.bat and select "Run as administrator"
        pause
        exit /b 1
    )
)

REM ── Locate Python 3.11 ───────────────────────────────────────────────────
set "PY311="

REM 1. py launcher
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set "PY311=py -3.11"
    goto :found_python
)

REM 2. python3.11 in PATH
python3.11 --version >nul 2>&1
if not errorlevel 1 (
    set "PY311=python3.11"
    goto :found_python
)

REM 3. python in PATH (accept if 3.11)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
echo %PY_VER% | findstr /B "3.11" >nul 2>&1
if not errorlevel 1 (
    set "PY311=python"
    goto :found_python
)

REM 4. Common install locations
for %%P in (
    "C:\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%PROGRAMFILES%\Python311\python.exe"
) do (
    if exist %%P (
        set "PY311=%%P"
        goto :found_python
    )
)

REM ── Python 3.11 not found ────────────────────────────────────────────────
echo.
echo  ================================================================
echo   ERROR: Python 3.11 not found.
echo  ================================================================
echo.
echo   Anna AI requires Python 3.11.9 specifically.
echo   Download from:
echo     https://www.python.org/downloads/release/python-3119/
echo.
echo   Install options to check during setup:
echo     [x] Add Python 3.11 to PATH
echo     [x] Install for all users
echo.
echo   After installing Python 3.11, re-run this script.
echo  ================================================================
echo.
pause
exit /b 1

:found_python
echo.
echo  [OK] Python found: %PY311%
echo.

REM ── Set working directory to script location ──────────────────────────────
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM ── Check INSTALL.py exists ───────────────────────────────────────────────
if not exist "INSTALL.py" (
    echo.
    echo  [ERR] INSTALL.py not found in %SCRIPT_DIR%
    echo        Place INSTALL.bat and INSTALL.py in the Anna_AI root directory.
    echo.
    pause
    exit /b 1
)

REM ── Bootstrap: install colorama for pretty output (optional) ─────────────
echo  [>>] Checking for colorama (optional, for colored output)...
%PY311% -c "import colorama" >nul 2>&1
if errorlevel 1 (
    echo  [>>] Installing colorama...
    %PY311% -m pip install colorama --quiet --user >nul 2>&1
)

REM ── Launch installer ──────────────────────────────────────────────────────
echo.
echo  ================================================================
echo   Launching Anna AI installer...
echo  ================================================================
echo.

%PY311% -u "INSTALL.py"

set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% EQU 0 (
    color 0A
    echo  ================================================================
    echo   Installation finished. See output above for any warnings.
    echo   Launch Anna AI with: START.bat
    echo  ================================================================
) else (
    color 0C
    echo  ================================================================
    echo   Installation exited with code %EXIT_CODE%.
    echo   Review the output above for errors.
    echo   Consult SETUP.md for troubleshooting.
    echo  ================================================================
)

echo.
pause
exit /b %EXIT_CODE%