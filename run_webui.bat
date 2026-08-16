@echo off
chcp 65001 >nul
title LaserGimbal WebUI HSS Command Center
cd /d "%~dp0"

echo ===================================================
echo   🎯 LaserGimbal WebUI HSS Command Center
echo ===================================================

:: 1. 检查 Python 虚拟环境
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %errorlevel% neq 0 goto NO_PYTHON
    set "PYTHON_EXE=python"
)

:: 2. 检查并编译前端 React + Three.js 界面 (若未编译)
if not exist "webui\dist\index.html" (
    echo [INFO] WebUI 静态文件未构建，正在自动打包 React + Three.js 前端...
    where npm >nul 2>nul
    if %errorlevel% neq 0 (
        echo [WARNING] 未检测到 npm 命令，跳过自动构建。如果前端无法加载，请先安装 Node.js。
    ) else (
        echo [INFO] 正在安装前端依赖 (npm install)...
        cd webui
        call npm install
        echo [INFO] 正在编译前端生产包 (npm run build)...
        call npm run build
        cd ..
    )
)

:: 3. 自动在后台启动浏览器打开前端页面 (延迟2秒等待服务就绪)
start "" cmd /c "timeout /t 2 >nul & start http://localhost:8000"

:: 4. 启动 FastAPI 后端服务
echo ===================================================
echo 🚀 正在启动 WebUI 战术指挥服务器: http://localhost:8000
echo 💡 按 Ctrl+C 可停止服务器
echo ===================================================
%PYTHON_EXE% web_server.py --port 8000 --host 0.0.0.0

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] 服务异常退出，错误码: %errorlevel%
)
pause
exit /b 0

:NO_PYTHON
echo [ERROR] 未找到 Python 解释器！
echo 请先安装 Python 3.10+ 并勾选 "Add Python to PATH"。
echo 下载地址: https://www.python.org/downloads/
pause
exit /b 1
