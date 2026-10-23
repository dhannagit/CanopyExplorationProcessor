@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0deployment.ps1" -Mode Remove
exit /b %errorlevel%