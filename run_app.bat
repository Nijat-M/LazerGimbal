@echo off
chcp 65001 >nul
title LaserGimbal Pro Launcher
cd /d "%~dp0"

echo ===================================================
echo           LaserGimbal Pro 启动器
echo ===================================================

:: 1. 如果虚拟环境已存在，直接跳转运行
if exist ".venv\Scripts\python.exe" goto RUN_APP

:: 2. 首次运行：检查系统 Python
where python >nul 2>nul
if %errorlevel% neq 0 goto NO_PYTHON

echo [提示] 首次运行，正在为您自动创建虚拟环境...
python -m venv .venv
if %errorlevel% neq 0 goto VENV_FAIL

echo [提示] 虚拟环境创建成功！正在自动安装依赖库 (requirements.txt)...
echo 请保持网络畅通，这可能需要一点时间...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 goto PIP_FAIL

echo [成功] 依赖库安装完成！
echo ===================================================
goto RUN_APP

:NO_PYTHON
echo [错误] 未能在系统 PATH 中找到 Python 解释器！
echo 请先安装 Python 3.10 及以上版本，并务必勾选 "Add Python to PATH"。
echo 下载地址: https://www.python.org/downloads/
pause
exit /b 1

:VENV_FAIL
echo [错误] 创建虚拟环境失败！
pause
exit /b 1

:PIP_FAIL
echo [错误] 依赖包安装失败，请检查网络连接后重试。
pause
exit /b 1

:RUN_APP
echo [信息] 正在启动 LaserGimbal Pro 主程序...
.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo [警告] 程序异常退出，退出码: %errorlevel%
)
pause

