@echo off
chcp 65001 >nul
title LaserGimbal WebUI Launcher
cd /d "%~dp0"

echo ===================================================
echo       LaserGimbal WebUI HSS Command Center
echo ===================================================

rem 1. Check Python virtual environment
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
    goto CHECK_WEBUI
)

where python >nul 2>nul
if %errorlevel% neq 0 goto NO_PYTHON
set "PYTHON_CMD=python"

:CHECK_WEBUI
rem 2. Check if WebUI build exists
if exist "webui\dist\index.html" goto LAUNCH_BROWSER

echo [INFO] WebUI frontend build not found. Building React + Three.js app...
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] npm not found. Skipping auto-build. Please install Node.js if UI fails to load.
    goto LAUNCH_BROWSER
)

echo [INFO] Installing frontend dependencies (npm install)...
cd webui
call npm install
echo [INFO] Building production bundle (npm run build)...
call npm run build
cd ..

:LAUNCH_BROWSER
rem 3. Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

rem 4. Start FastAPI server
echo ===================================================
echo [INFO] Starting WebUI Server on http://localhost:8000
echo [INFO] Press Ctrl+C to stop server
echo ===================================================
%PYTHON_CMD% web_server.py --port 8000 --host 0.0.0.0

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Server exited with code: %errorlevel%
)
pause
exit /b 0

:NO_PYTHON
echo [ERROR] Python not found in PATH!
echo Please install Python 3.10+ and ensure Add Python to PATH is checked.
echo Download: https://www.python.org/downloads/
pause
exit /b 1
