@echo off
title Vision Stream Bridge Service Status
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service_manager.ps1" status
echo.
pause
