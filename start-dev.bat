@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start-dev.ps1" %*
echo.
echo Press any key to close this window.
pause >nul
