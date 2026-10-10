#!/usr/bin/env bash
cd "$(dirname "$0")/mujoco"

if [ ! -d venv ]; then
    echo "Creating a virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# Don't just trust that venv/ existing means it's populated - a
# cancelled/failed install before leaves an empty-but-present venv that
# looks "already set up" and silently hits ModuleNotFoundError. Check
# the import instead.
if ! python3 -c "import stable_baselines3" >/dev/null 2>&1; then
    echo "Installing MuJoCo / RL dependencies - torch is a big download, this may take a few minutes..."
    pip install --upgrade pip >/dev/null
    pip install -r requirements.txt
    if ! python3 -c "import stable_baselines3" >/dev/null 2>&1; then
        echo
        echo "Dependency install failed. Check your internet connection and try again, or run:"
        echo "  venv/bin/pip install -r requirements.txt"
        echo "directly to see the actual error."
        exit 1
    fi
fi

echo
echo "What do you want to train or continue?"
echo "  1) Standing balance / locomotion"
echo "  2) Reach and grasp"
read -r -p "Choose 1 or 2: " choice

if [ "$choice" = "2" ]; then
    if [ -f checkpoints/reach_grasp_latest.zip ]; then
        echo "Resuming from the included checkpoint..."
        python3 train_reach_grasp.py --timesteps 3000000 --n-envs 4 \
            --resume checkpoints/reach_grasp_latest.zip \
            --vecnorm-resume checkpoints/reach_grasp_latest_vecnormalize.pkl
    else
        python3 train_reach_grasp.py --timesteps 3000000 --n-envs 4
    fi
else
    if [ -f checkpoints/stand_latest.zip ]; then
        echo "Resuming from the included checkpoint..."
        python3 train.py --stage stand --timesteps 10000000 --n-envs 4 \
            --resume checkpoints/stand_latest.zip \
            --vecnorm-resume checkpoints/stand_latest_vecnormalize.pkl
    else
        python3 train.py --stage stand --timesteps 10000000 --n-envs 4
    fi
fi
