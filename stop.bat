@echo off
title SupermarketBot - 1-Click Stopper
color 0C
cls

echo ========================================================================
echo               STOPPING ALL SUPERMARKETBOT SERVICES
echo ========================================================================
echo.

echo [1/3] Stopping Python processes (Uvicorn + Telegram Poller)...
taskkill /F /IM python.exe /T >nul 2>&1

echo [2/3] Stopping PostgreSQL server...
if exist "pgsql\bin\pg_ctl.exe" (
    pgsql\bin\pg_ctl.exe stop -D pgdata -m fast >nul 2>&1
)

echo [3/3] Done.
echo.
echo ========================================================================
echo        ALL SUPERMARKETBOT SERVICES STOPPED SUCCESSFULLY
echo ========================================================================
echo.
pause
