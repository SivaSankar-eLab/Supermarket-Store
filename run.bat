@echo off
title SupermarketBot - 1-Click Production Launcher
color 0B
cls

echo ========================================================================
echo       SUPERMARKETBOT - AI-POWERED STORE OPERATIONS AGENT
echo ========================================================================
echo.
echo [1/4] Checking Python environment...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+.
    pause
    exit /b 1
)

echo [2/4] Starting PostgreSQL Database...
if exist "pgsql\bin\pg_ctl.exe" (
    if exist "pgdata" (
        pgsql\bin\pg_ctl.exe status -D pgdata >nul 2>&1
        if %ERRORLEVEL% NEQ 0 (
            echo Starting local PostgreSQL server...
            if exist "pgdata\postmaster.pid" del /f /q "pgdata\postmaster.pid" >nul 2>&1
            pgsql\bin\pg_ctl.exe start -D pgdata -w >nul 2>&1
        ) else (
            echo PostgreSQL server is already active.
        )
    )
)

echo [3/4] Checking dependencies and database migrations...
pip install -r requirements.txt --quiet >nul 2>&1
python -m alembic upgrade head >nul 2>&1
python scripts\seed_data.py >nul 2>&1

echo [4/4] Launching SupermarketBot Services (Web Dashboard + Telegram Bot)...
echo.
echo ------------------------------------------------------------------------
echo   Web Dashboard : http://localhost:8000 (Opening in your browser...)
echo   Telegram Bot  : @mykiranastore_bot
echo ------------------------------------------------------------------------
echo.

python run_all.py

pause
