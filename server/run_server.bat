@echo off
title Vision Back-Camera Stream Server & Proxy
cd /d "%~dp0"
echo ====================================================
echo Starting Vision Back-Camera Stream Server & Proxy...
echo ====================================================
py main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Py launcher exited with code %ERRORLEVEL%. Trying python...
    python main.py
)
pause
