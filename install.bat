@echo off
setlocal
cd /d "%~dp0"

echo === Kiara setup ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/ ^(check
    echo "Add python.exe to PATH" during install^), then run this again.
    pause
    exit /b 1
)

if not exist "mujoco\venv" (
    echo Creating a Python virtual environment for MuJoCo training...
    python -m venv mujoco\venv
)
call mujoco\venv\Scripts\activate.bat
echo Installing MuJoCo / RL dependencies - torch is a big download, this
echo can take a few minutes on a slow connection...
pip install --upgrade pip >nul
pip install -r mujoco\requirements.txt
call mujoco\venv\Scripts\deactivate.bat

echo.
where godot >nul 2>nul
if errorlevel 1 (
    echo NOTE: Godot 4.3+ was not found on PATH.
    echo Download it from https://godotengine.org/download, then either:
    echo   - add godot.exe to your PATH, or
    echo   - copy godot.exe into this folder ^(next to install.bat^)
    echo The "Kiara (Godot)" shortcut will still be created now and will
    echo work as soon as Godot is in either of those two places.
) else (
    echo Godot found on PATH - good.
)

echo.
echo Creating desktop shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcuts.ps1"

echo.
echo === Done ===
echo Two shortcuts were added to your Desktop:
echo   "Kiara (Godot)"         - opens/runs her in Godot
echo   "Kiara (Train MuJoCo)"  - trains or resumes locomotion / reach-and-grasp
pause
