@echo off
setlocal
cd /d "%~dp0mujoco"

if not exist venv (
    echo First-time setup: creating a virtual environment and installing
    echo dependencies - torch is a big download, this may take a few minutes.
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install --upgrade pip >nul
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
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
