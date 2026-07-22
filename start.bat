@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   WebSense Security - Unified Setup and Start Script
echo ===================================================
echo.

REM Activate virtual environment if script run directly
if exist .venv\Scripts\activate.bat (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the PyQt6 Desktop App and Backend
echo.
echo [SUCCESS] PhishGuard setup complete!
echo [INFO] Starting PhishGuard Desktop Console...
echo [INFO] Close the console window to minimize it to the system tray.
echo.

python gui.py
