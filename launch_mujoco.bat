@echo off
setlocal
cd /d "%~dp0mujoco"

if not exist venv (
    echo Creating a virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

rem Don't just trust that venv\ existing means it's actually populated -
rem a cancelled/failed install from before leaves an empty-but-present
rem venv folder, which looked "already set up" and silently skipped
rem straight to ModuleNotFoundError. Actually check the import instead.
venv\Scripts\python.exe -c "import stable_baselines3" >nul 2>nul
if not errorlevel 1 goto menu

echo Installing MuJoCo / RL dependencies - torch is a big download
echo (needs roughly 2-3 GB free disk space), this may take a few minutes...
rem --no-cache-dir + purge first: a failed attempt leaves its downloaded
rem wheels sitting in pip's cache permanently, which can itself be the
rem difference between "just enough" and "out of" disk space on a
rem near-full drive - this reclaims that from any previous failed run too.
pip cache purge >nul 2>nul
pip install --upgrade pip >nul
pip install --no-cache-dir -r requirements.txt
venv\Scripts\python.exe -c "import stable_baselines3" >nul 2>nul
if not errorlevel 1 goto menu

echo.
echo That didn't fully succeed. The virtual environment may now be in a
echo half-broken state from the failed attempt (a package can get
echo removed mid-upgrade and never replaced if the disk fills up right
echo then). Deleting it and trying once more from a clean slate...
call venv\Scripts\deactivate.bat >nul 2>nul
rmdir /s /q venv
python -m venv venv
call venv\Scripts\activate.bat
pip cache purge >nul 2>nul
pip install --upgrade pip >nul
pip install --no-cache-dir -r requirements.txt
venv\Scripts\python.exe -c "import stable_baselines3" >nul 2>nul
if not errorlevel 1 goto menu

echo.
echo Dependency install failed twice - scroll up to see pip's actual error.
echo Most likely cause: not enough free disk space on this drive (a full
echo torch install needs roughly 2-3 GB free). Free some room (Downloads,
echo Recycle Bin, Disk Cleanup / Storage Sense) and run this shortcut again.
pause
exit /b 1

:menu
echo.
echo What do you want to train or continue?
echo   1) Standing balance / locomotion
echo   2) Reach and grasp
choice /c 12 /n /m "Choose 1 or 2: "
if errorlevel 2 goto reach
if errorlevel 1 goto stand

:stand
if exist checkpoints\stand_latest.zip (
    echo Resuming from the included checkpoint...
    python train.py --stage stand --timesteps 10000000 --n-envs 4 ^
        --resume checkpoints\stand_latest.zip ^
        --vecnorm-resume checkpoints\stand_latest_vecnormalize.pkl
) else (
    python train.py --stage stand --timesteps 10000000 --n-envs 4
)
goto end

:reach
if exist checkpoints\reach_grasp_latest.zip (
    echo Resuming from the included checkpoint...
    python train_reach_grasp.py --timesteps 3000000 --n-envs 4 ^
        --resume checkpoints\reach_grasp_latest.zip ^
        --vecnorm-resume checkpoints\reach_grasp_latest_vecnormalize.pkl
) else (
    python train_reach_grasp.py --timesteps 3000000 --n-envs 4
)
goto end

:end
echo.
echo Stopped (Ctrl+C or training finished). Checkpoints are saved under
echo mujoco\checkpoints\ as training runs - safe to close this window.
pause
