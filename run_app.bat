@echo off
chcp 65001 >nul
title SADIR 1798-K Launcher
cd /d "%~dp0"

echo ===================================================
echo              SADIR 1798-K Launcher
echo ===================================================

:: 1. If venv exists, jump to RUN_APP
if exist ".venv\Scripts\python.exe" goto RUN_APP

:: 2. First run: check system Python
where python >nul 2>nul
if %errorlevel% neq 0 goto NO_PYTHON

echo [INFO] First run, automatically creating virtual environment...
python -m venv .venv
if %errorlevel% neq 0 goto VENV_FAIL

echo [INFO] Virtual environment created successfully! Automatically installing dependencies (requirements.txt)...
echo Please keep your network connected, this might take a moment...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 goto PIP_FAIL

echo [SUCCESS] Dependencies installed successfully!
echo ===================================================
goto RUN_APP

:NO_PYTHON
echo [ERROR] Could not find Python interpreter in system PATH!
echo Please install Python 3.10 or higher first, and make sure to check "Add Python to PATH".
echo Download link: https://www.python.org/downloads/
pause
exit /b 1

:VENV_FAIL
echo [ERROR] Failed to create virtual environment!
pause
exit /b 1

:PIP_FAIL
echo [ERROR] Failed to install dependencies, please check your network connection and try again.
pause
exit /b 1

:RUN_APP
echo [INFO] Starting SADIR 1798-K main application...
.venv\Scripts\python.exe main.py
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Application exited abnormally, exit code: %errorlevel%
)
pause

