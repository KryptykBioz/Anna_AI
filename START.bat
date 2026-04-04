@echo off
title Anna AI GUI - Starting...
color 0A

@echo off
REM Set CUDA paths
set PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.0\bin\x64;C:\Program Files\NVIDIA\CUDNN\v9.16\bin\13.0;%PATH%

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start Anna
python -m BASE.interface.gui_interface

echo Starting Anna AI GUI Interface...
echo.

REM Store original directory
set "ORIGINAL_DIR=%CD%"

REM Get the directory where this batch file is located (Anna_AI/)
set "SCRIPT_DIR=%~dp0"

REM Navigate to the Anna_AI directory (where this script is located)
cd /d "%SCRIPT_DIR%"

REM Check if virtual environment exists in current directory
if not exist "venv\Scripts\activate.bat" (
    color 0C
    echo ERROR: Virtual environment not found at %CD%\venv\Scripts\activate.bat
    echo Current directory: %CD%
    echo.
    echo Please ensure the virtual environment is located at: %CD%\venv\
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment from: %CD%\venv\
call "venv\Scripts\activate.bat"

REM Verify virtual environment is active
python -c "import sys; print('Python executable:', sys.executable)" 2>nul
if errorlevel 1 (
    color 0C
    echo ERROR: Failed to activate virtual environment or Python not found
    pause
    exit /b 1
)

REM Set environment variables for better Python compatibility
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"
set "PYTHONPATH=%CD%;%PYTHONPATH%"

REM Check if BASE directory exists
if not exist "BASE" (
    color 0C
    echo ERROR: BASE directory not found at %CD%\BASE
    echo Current directory: %CD%
    echo.
    echo Directory contents:
    dir /b
    pause
    exit /b 1
)

REM Check if interface directory exists, create if it doesn't
if not exist "BASE\interface" (
    echo Creating interface directory...
    mkdir "BASE\interface"
)

REM Check if GUI interface file exists
if not exist "BASE\interface\gui_interface.py" (
    color 0C
    echo ERROR: gui_interface.py not found at BASE\interface\gui_interface.py
    echo.
    echo Please ensure gui_interface.py is saved in the BASE\interface\ directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Show current working directory and Python info
echo.
echo Current working directory: %CD%
echo Python version:
python --version
echo Virtual environment: %VIRTUAL_ENV%

REM Run the GUI interface
echo.
echo Starting GUI interface...
echo If you encounter issues, check the output below:
echo ================================================
python -u "BASE\interface\gui_interface.py"

REM Check exit code
if errorlevel 1 (
    color 0C
    echo.
    echo ================================================
    echo GUI exited with error code: %errorlevel%
) else (
    color 0A
    echo.
    echo ================================================
    echo GUI exited normally
)

REM Return to original directory
cd /d "%ORIGINAL_DIR%"

echo.
echo Press any key to exit...
pause >nul