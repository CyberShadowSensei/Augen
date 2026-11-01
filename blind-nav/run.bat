@echo off
echo ================================================
echo   blind-nav  ^|  Windows Launcher
echo ================================================

REM Change to the script directory
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from https://python.org
    pause
    exit /b 1
)

REM Check venv
if not exist ".venv\Scripts\activate.bat" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
)

echo [INFO] Activating environment...
call .venv\Scripts\activate.bat

REM Install deps if not done
if not exist ".venv\.deps_installed" (
    echo [SETUP] Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
    echo. > .venv\.deps_installed
    echo [INFO] Dependencies installed.
)

REM Download models if missing
if not exist "models\yolov8n.pt" (
    echo [SETUP] Downloading models...
    python download_models.py
)

echo.
echo [INFO] Starting blind-nav...
echo.
python run.py %*

pause

