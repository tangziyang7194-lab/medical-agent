@echo off
title AI Medical Agent - GitHub Upload

REM Change to script directory
cd /d "%~dp0"

echo.
echo ========================================
echo   AI Medical Agent - GitHub Upload
echo ========================================
echo.

echo [Step 1/5] Initializing Git repository...
if not exist ".git" (
    git init
    echo [OK] Git repository initialized
) else (
    echo [INFO] Git repository already exists
)
echo.

echo [Step 2/5] Adding all files...
git add .
echo [OK] Files added
echo.

echo [Step 3/5] Committing files...
set /p commit_msg="Commit message (default: Initial commit): "
if "%commit_msg%"=="" set commit_msg=Initial commit

git commit -m "%commit_msg%"
if %errorlevel% neq 0 (
    echo [INFO] Nothing to commit
) else (
    echo [OK] Files committed
)
echo.

echo [Step 4/5] Creating GitHub repository...
echo.
echo Please follow these steps:
echo.
echo 1. Open browser: https://github.com/new
echo 2. Fill in repository info:
echo    - Repository name: medical-agent
echo    - Description: AI Medical Agent - Intelligent Healthcare
echo    - Choose: Public or Private
echo    - DO NOT check "Initialize this repository with a README"
echo 3. Click "Create repository"
echo.
echo After creating, copy the repository URL:
echo    Example: https://github.com/your-username/medical-agent.git
echo.
pause
echo.

echo [Step 5/5] Connecting and pushing to GitHub...
set /p github_url="Enter GitHub repository URL: "
if "%github_url%"=="" (
    echo [INFO] Skipped remote configuration
    goto end
)

echo Connecting to remote repository...
git remote remove origin 2>nul
git remote add origin "%github_url%"
git branch -M main
echo [OK] Remote repository configured
echo.

echo Pushing to GitHub...
echo.
echo First push may require login:
echo - Username: your GitHub username
echo - Password: your Personal Access Token (NOT your login password)
echo.
echo How to get Personal Access Token:
echo 1. Open: https://github.com/settings/tokens
echo 2. Click "Generate new token (classic)"
echo 3. Check permission: repo
echo 4. Generate and copy the token
echo.

git push -u origin main
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Push failed. Please check:
    echo   1. Repository URL is correct
    echo   2. Personal Access Token is configured
    echo   3. Network connection is working
    echo.
    echo Manual push command:
    echo   git push -u origin main
) else (
    echo.
    echo [OK] Push successful!
    echo Repository: %github_url%
)
echo.

:end
echo ========================================
echo   GitHub Upload Complete
echo ========================================
echo.
pause