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
echo Installing MuJoCo / RL dependencies - torch is a big download
echo (a full install needs roughly 2-3 GB free disk space), this can
echo take a few minutes on a slow connection...
pip cache purge >nul 2>nul
pip install --upgrade pip >nul
pip install --no-cache-dir -r mujoco\requirements.txt

echo Verifying the install actually took...
mujoco\venv\Scripts\python.exe -c "import stable_baselines3, mujoco, torch" >nul 2>nul
if errorlevel 1 (
    echo.
    echo WARNING: dependency install did not fully succeed - scroll up to
    echo see pip's actual error. If it says the disk is out of space,
    echo free some room on this drive and re-run install.bat. Otherwise
    echo the "Kiara (Train MuJoCo)" shortcut will retry automatically next
    echo time you use it.
) else (
    echo Dependencies OK.
)
call mujoco\venv\Scripts\deactivate.bat

echo.
where godot >nul 2>nul
if errorlevel 1 (
    echo NOTE: Godot wasn't found on PATH - that's fine, the "Kiara (Godot)"
    echo shortcut also searches your Desktop/Downloads/this folder for it
    echo automatically the first time you use it and remembers what it finds.
    echo If you don't have Godot 4.3+ yet, get it from https://godotengine.org/download
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
