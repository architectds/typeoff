@echo off
cd /d "%~dp0"

REM Auto-setup if first run
if not exist ".venv" call setup.bat

call .venv\Scripts\activate.bat
python typeoff.py
pause
