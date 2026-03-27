@echo off
REM Typeoff setup for Windows — creates venv, installs faster-whisper + deps
cd /d "%~dp0"

echo --- Typeoff Setup ---

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

pip install --upgrade pip -q

echo Installing dependencies (faster-whisper + CUDA/CPU)...
pip install -r requirements-win.txt -q

echo.
echo Setup complete!
echo.
echo To run:
echo   cd typeoff
echo   .venv\Scripts\activate.bat
echo   python typeoff.py
echo.
echo First run downloads Whisper 'small' model (~500MB).
echo Hotkey: Ctrl+Shift+Space
