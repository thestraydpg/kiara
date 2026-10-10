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
if errorlevel 1 (
    echo Installing MuJoCo / RL dependencies - torch is a big download,
    echo this may take a few minutes...
    pip install --upgrade pip >nul
    pip install -r requirements.txt
    venv\Scripts\python.exe -c "import stable_baselines3" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo Dependency install failed. Check your internet connection and
        echo try again - if it keeps failing, open this folder in a command
        echo prompt and run: venv\Scripts\pip install -r requirements.txt
        echo to see the actual error.
        pause
        exit /b 1
    )
)

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
