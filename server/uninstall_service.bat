@echo off
title Uninstall Vision Stream Bridge Background Service
cd /d "%~dp0"

echo ============================================================
echo   Uninstalling Vision Stream Bridge Background Service
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service_manager.ps1" uninstall

echo.
echo ============================================================
echo   Uninstallation finished.
echo ============================================================
pause
