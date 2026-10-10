#!/usr/bin/env bash
cd "$(dirname "$0")/mujoco"

if [ ! -d venv ]; then
    echo "First-time setup: creating a virtual environment and installing dependencies..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip >/dev/null
    pip install -r requirements.txt
else
    source venv/bin/activate
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
