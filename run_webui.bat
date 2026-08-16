@echo off
chcp 65001 > nul
echo =======================================================
echo 🎯 STARTING LAZER GIMBAL HSS WEB COMMAND CENTER...
echo =======================================================

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

if not exist webui\dist (
    echo 📦 Building WebUI React + Three.js application...
    cd webui
    call npm install
    call npm run build
    cd ..
)

echo 🚀 Launching FastAPI Backend on http://localhost:8000
python web_server.py --port 8000 --host 0.0.0.0
pause
