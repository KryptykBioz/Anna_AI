@echo off
title Anna AI
color 0A

REM Store original directory
set "ORIGINAL_DIR=%CD%"

REM Get the directory where this batch file is located
set "SCRIPT_DIR=%~dp0"

REM Navigate to the Anna_AI directory
cd /d "%SCRIPT_DIR%"

REM Set CUDA paths
set PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64;C:\Program Files\NVIDIA\CUDNN\v9.16\bin\13.0;%PATH%

REM Start Ollama first
echo Starting Ollama...
start "" cmd /c "ollama start"
echo Waiting for Ollama to initialize...
timeout /t 5 /nobreak >nul

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    color 0C
    echo ERROR: Virtual environment not found at %CD%\venv\Scripts\activate.bat
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment from: %CD%\venv\
call "venv\Scripts\activate.bat"

REM Verify Python
python -c "import sys; print('Python executable:', sys.executable)" 2>nul
if errorlevel 1 (
    color 0C
    echo ERROR: Failed to activate virtual environment or Python not found
    pause
    exit /b 1
)

REM Set environment variables
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%CD%;%PYTHONPATH%"

REM Check required directories and files
if not exist "BASE" (
    color 0C
    echo ERROR: BASE directory not found at %CD%\BASE
    pause
    exit /b 1
)

if not exist "BASE\interface" mkdir "BASE\interface"

if not exist "BASE\interface\gui_interface.py" (
    color 0C
    echo ERROR: gui_interface.py not found at BASE\interface\gui_interface.py
    pause
    exit /b 1
)

REM Show info
echo.
echo Current working directory: %CD%
echo Python version:
python --version
echo Virtual environment: %VIRTUAL_ENV%

REM Launch Anna
echo.
echo Starting GUI interface...
echo ================================================
python -u "BASE\interface\gui_interface.py"

if errorlevel 1 (
    color 0C
    echo GUI exited with error code: %errorlevel%
) else (
    color 0A
    echo GUI exited normally
)

cd /d "%ORIGINAL_DIR%"
echo.
pause >nul