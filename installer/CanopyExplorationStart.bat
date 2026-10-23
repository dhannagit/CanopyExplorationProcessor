@echo off
setlocal
powershell.exe -NoProfile -File "%~dp0deployment.ps1" -Mode Launch
if errorlevel 1 (
    echo Unable to launch Canopy. See %%LOCALAPPDATA%%\CanopyExplorationProcessor\logs.
    pause
    exit /b 1
)