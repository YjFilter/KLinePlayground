@echo off
setlocal
chcp 65001 >nul
title KLinePlayground Launcher
cd /d "%~dp0"

echo ========================================
echo   KLinePlayground Local Launcher
echo ========================================
echo.

set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [1/3] Creating the Python environment...
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python was not found.
        echo Please install Python 3.11 or 3.12 first.
        pause
        exit /b 1
    )
    python -m venv .venv
    if errorlevel 1 goto :failed
) else (
    echo [1/3] Python environment is ready.
)

"%PYTHON%" -c "import flask, flask_cors, pandas, numpy, requests, akshare, baostock" >nul 2>&1
if errorlevel 1 (
    echo [2/3] Installing dependencies. The first run may take a few minutes...
    "%PYTHON%" -m pip install --upgrade pip --index-url https://pypi.org/simple
    if errorlevel 1 (
        echo Official PyPI was unavailable. Retrying with the Tsinghua mirror...
        "%PYTHON%" -m pip install --upgrade pip --index-url https://pypi.tuna.tsinghua.edu.cn/simple
        if errorlevel 1 goto :failed
    )
    "%PYTHON%" -m pip install -r requirements.txt --index-url https://pypi.org/simple
    if errorlevel 1 (
        echo Official PyPI was unavailable. Retrying with the Tsinghua mirror...
        "%PYTHON%" -m pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple
        if errorlevel 1 goto :failed
    )
) else (
    echo [2/3] Dependencies are ready.
)

set "PORT=8000"
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue) { exit 1 }" >nul 2>&1
if errorlevel 1 set "PORT=5000"
powershell -NoProfile -Command "if (Get-NetTCPConnection -State Listen -LocalPort %PORT% -ErrorAction SilentlyContinue) { exit 1 }" >nul 2>&1
if errorlevel 1 set "PORT=5050"

echo [3/3] Starting http://127.0.0.1:%PORT%/
echo.
echo The browser will open automatically.
echo Close this window or press Ctrl+C to stop the project.
echo ========================================

if defined KLINE_SETUP_ONLY (
    echo Setup check completed successfully.
    exit /b 0
)

if not defined KLINE_NO_BROWSER start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:%PORT%/'"
"%PYTHON%" -m flask --app backend.app_enhanced run --host 0.0.0.0 --port %PORT%
goto :end

:failed
echo.
echo [ERROR] Setup failed. Send the error shown above to Codex.
pause
exit /b 1

:end
echo.
echo KLinePlayground has stopped.
pause