@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          ALFRED - Windows 11 Personal AI Setup
echo =======================================================
echo.

:: 1. Check Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python 3.11+ is not found in your PATH.
    echo Please install Python from https://www.python.org/ or the Microsoft Store.
    pause
    exit /b 1
)

:: 2. Create Virtual Environment
if not exist ".venv" (
    echo [*] Creating virtual environment in .venv...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found in .venv.
)

:: 3. Upgrade pip and install dependencies
echo [*] Installing required dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo [WARNING] Some dependencies had warnings during installation.
) else (
    echo [OK] All dependencies installed successfully.
)

:: 4. Ensure .env exists without overwriting existing keys
if not exist ".env" (
    if exist ".env.example" (
        echo [*] Creating .env from .env.example template...
        copy .env.example .env >nul
        echo [OK] Created .env file.
    )
) else (
    echo [OK] Preserving existing .env file.
)

:: 5. Create data folder
if not exist "data" mkdir data

echo.
echo =======================================================
echo              SETUP COMPLETED SUCCESSFULLY
echo =======================================================
echo Next steps:
echo 1. Open the '.env' file in a text editor to add your GEMINI_API_KEY and ELEVENLABS_API_KEY.
echo 2. Run 'run_alfred.bat' to launch Alfred.
echo =======================================================
echo.
pause

