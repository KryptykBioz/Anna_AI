@echo off
title Anna AI Setup
color 0B

py -3.11 --version >nul 2>&1
if not errorlevel 1 (
    set "PY311=py -3.11"
    goto found
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "PY311=python"
    goto found
)
echo Python 3.11 not found. Install from python.org/downloads
pause
exit /b 1

:found
echo  [OK] Python found: %PY311%

cd /d "%~dp0"

if not exist "INSTALL.py" (
    echo  [ERR] INSTALL.py not found
    pause
    exit /b 1
)

%PY311% -c "import colorama" >nul 2>&1
if errorlevel 1 %PY311% -m pip install colorama --quiet --user >nul 2>&1

echo.
echo Launching Anna AI installer...
echo.

%PY311% -u "INSTALL.py"
set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% EQU 0 (
    color 0A
    echo  Installation finished. Launch with START.bat
) else (
    color 0C
    echo  Installation failed with code %EXIT_CODE%
)

pause
exit /b %EXIT_CODE%