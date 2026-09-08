@echo off
title Install Vision Stream Bridge Background Service
cd /d "%~dp0"

echo ============================================================
echo   Installing Vision Stream Bridge as a 24/7 Background Service
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service_manager.ps1" install

echo.
echo ============================================================
echo   Installation finished!
echo   The service will now run automatically on Windows startup.
echo ============================================================
pause
