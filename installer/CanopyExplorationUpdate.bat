@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0deployment.ps1" -Mode Update
if errorlevel 1 (
    pause
    exit /b 1
)