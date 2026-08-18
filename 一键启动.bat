@echo off
title AI Medical Agent - Quick Start

REM Change to script directory
cd /d "%~dp0"

echo.
echo ========================================
echo   AI Medical Agent - Quick Start
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found
    echo.
    echo Please install Python first:
    echo 1. Visit https://www.python.org/downloads/
    echo 2. Download and install Python 3.8 or higher
    echo 3. Make sure to check "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [1/5] Checking Python...
python --version
echo.

echo [2/5] Installing dependencies...
if not exist requirements.txt (
    echo [ERROR] requirements.txt not found in current directory
    echo Current directory: %cd%
    pause
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo.

echo [3/5] Checking config file...
if not exist .env (
    if exist .env.example (
        copy .env.example .env >nul
        echo [INFO] Created .env file
        echo.
        echo [IMPORTANT] Please edit .env file and set ZHIPUAI_API_KEY
        echo         Get API Key from: https://open.bigmodel.cn/
        echo.
        notepad .env
        echo.
        echo [INFO] Press Enter to continue after configuration...
        pause
    ) else (
        echo [ERROR] .env.example file not found
        pause
        exit /b 1
    )
)
echo.

echo [4/5] Starting server...
echo.
echo ========================================
echo   AI Medical Agent
echo ========================================
echo.
echo   Access URLs:
echo     User: http://localhost:5000
echo     Admin: http://localhost:5000/admin/login
echo.
echo   Press Ctrl+C to stop server
echo ========================================
echo.

python app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Server startup failed
    echo.
    echo Possible reasons:
    echo   1. Port 5000 is occupied
    echo   2. .env file configuration error
    echo   3. Dependencies not installed correctly
    echo.
    pause
    exit /b 1
)

echo.
echo [5/5] Server stopped
pause