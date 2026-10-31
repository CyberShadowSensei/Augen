@echo off
REM This script launches the Personal Memory Core components.

echo Starting Personal Memory Core...
echo.

echo [1/2] Launching Backend Listener (main.py)...
start "PMC_Backend" cmd /k "python main.py"

echo [2/2] Launching Frontend Dashboard (app.py)...
timeout /t 2 /nobreak > nul
start "PMC_Frontend" cmd /k "streamlit run app.py"

echo.
echo System deployment initiated. Please check the new terminal windows.
