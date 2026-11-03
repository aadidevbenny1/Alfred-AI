@echo off
setlocal

:: Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Running setup first...
    call setup.bat
)

echo Starting Alfred Personal AI Desktop Assistant...
.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo Alfred encountered an issue on exit. Check data\alfred.log for details.
    pause
)

