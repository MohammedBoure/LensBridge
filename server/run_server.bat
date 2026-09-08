@echo off
title Vision Dual-Camera Desktop Server
cd /d "%~dp0"
echo ====================================================
echo Starting Vision Dual-Camera Desktop Server...
echo ====================================================
py main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Py launcher exited with code %ERRORLEVEL%. Trying python...
    python main.py
)
pause
