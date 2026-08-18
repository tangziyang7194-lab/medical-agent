@echo off
title AI Medical Agent - Cloud Deploy

REM Change to script directory
cd /d "%~dp0"

echo.
echo ========================================
echo   AI Medical Agent - Cloud Deploy
echo ========================================
echo.

echo Select deployment platform:
echo.
echo   1) Render (recommended, free, Python support)
echo   2) Heroku (free, Python platform)
echo   3) PythonAnywhere (free, Python dedicated)
echo   4) Aliyun Lightweight Server (production, 99 CNY/month)
echo   5) Tencent Cloud Lightweight Server (production)
echo.
set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto deploy_render
if "%choice%"=="2" goto deploy_heroku
if "%choice%"=="3" goto deploy_pythonanywhere
if "%choice%"=="4" goto deploy_aliyun
if "%choice%"=="5" goto deploy_tencent
echo [ERROR] Invalid choice
pause
exit /b 1

:deploy_render
echo.
echo ========================================
echo   Render Deployment
echo ========================================
echo.

echo [Step 1/3] Checking required files...
if not exist "app.py" (
    echo [ERROR] app.py not found
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)
echo [OK] Required files found
echo.

echo [Step 2/3] Creating render.yaml...
(
echo services:
echo   - type: web
echo     name: medical-agent
echo     env: python
echo     buildCommand: pip install -r requirements.txt
echo     startCommand: gunicorn app:app --timeout 120
echo     envVars:
echo       - key: ZHIPUAI_API_KEY
echo         value: your_zhipuai_api_key_here
echo       - key: FLASK_HOST
echo         value: 0.0.0.0
echo       - key: FLASK_PORT
echo         value: 5000
) > render.yaml
echo [OK] render.yaml created
echo.

echo [Step 3/3] Deployment instructions:
echo.
echo 1. Push this project to GitHub first (run: upload-to-github.bat)
echo 2. Open browser: https://render.com
echo 3. Sign up / Log in
echo 4. Click "New +" -^> "Web Service"
echo 5. Connect your GitHub repository
echo 6. Render auto-detects render.yaml
echo 7. Set env var: ZHIPUAI_API_KEY=your_api_key
echo 8. Click "Deploy" and wait
echo.
echo [OK] Render deployment configured
echo.
pause
exit /b 0

:deploy_heroku
echo.
echo ========================================
echo   Heroku Deployment
echo ========================================
echo.

echo [Step 1/3] Checking required files...
if not exist "app.py" (
    echo [ERROR] app.py not found
    pause
    exit /b 1
)
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)
echo [OK] Required files found
echo.

echo [Step 2/3] Creating Procfile...
echo web: gunicorn app:app --timeout 120 > Procfile
echo [OK] Procfile created
echo.

echo [Step 3/3] Deployment instructions:
echo.
echo 1. Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
echo 2. Login: heroku login
echo 3. Create app: heroku create your-app-name
echo 4. Set env: heroku config:set ZHIPUAI_API_KEY=your_api_key
echo 5. Deploy: git push heroku main
echo.
echo [OK] Heroku deployment configured
echo.
pause
exit /b 0

:deploy_pythonanywhere
echo.
echo ========================================
echo   PythonAnywhere Deployment
echo ========================================
echo.

echo [Step 1/2] Creating deploy package...
if exist deploy_package rmdir /s /q deploy_package
mkdir deploy_package
copy app.py deploy_package\ >nul
xcopy templates deploy_package\templates\ /E /I /Y >nul 2>nul
xcopy static deploy_package\static\ /E /I /Y >nul 2>nul
copy requirements.txt deploy_package\ >nul
copy .env.example deploy_package\.env >nul
echo [OK] Deploy package created
echo.

echo [Step 2/2] Deployment instructions:
echo.
echo 1. Open browser: https://www.pythonanywhere.com
echo 2. Sign up / Log in
echo 3. Go to "Web" tab, create new web app
echo 4. Choose Flask framework
echo 5. Upload files from deploy_package folder
echo 6. Set WSGI path to app.py
echo 7. Set env: ZHIPUAI_API_KEY=your_api_key
echo.
echo [OK] PythonAnywhere deployment configured
echo.
pause
exit /b 0

:deploy_aliyun
echo.
echo ========================================
echo   Aliyun Lightweight Server Deployment
echo ========================================
echo.

echo Requirements:
echo - Server: 2 core 2GB Ubuntu 22.04
echo - Reset root password
echo - Firewall open ports: 22, 80, 443
echo.
echo [Step 1/2] Upload project:
echo.
echo Use WinSCP or scp to upload project to server:
echo   scp -r . root@your-server-ip:/opt/medical_agent
echo.
echo [Step 2/2] SSH to server and run:
echo.
echo   cd /opt/medical_agent
echo   apt update && apt upgrade -y
echo   apt install python3 python3-pip python3-venv nginx -y
echo   pip install -r requirements.txt
echo   cp .env.example .env
echo   nano .env
echo   python app.py
echo.
echo Or use Docker:
echo   docker-compose up -d
echo.
echo [OK] Aliyun deployment configured
echo.
pause
exit /b 0

:deploy_tencent
echo.
echo ========================================
echo   Tencent Cloud Deployment
echo ========================================
echo.
echo Same as Aliyun deployment (option 4).
echo See CLOUD_DEPLOYMENT_SIMPLE.md for details.
echo.
pause
exit /b 0