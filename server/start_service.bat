@echo off
title Start Vision Stream Bridge Service
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service_manager.ps1" start
pause
