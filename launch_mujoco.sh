#!/usr/bin/env bash
cd "$(dirname "$0")/mujoco"

install_deps() {
    pip cache purge >/dev/null 2>&1 || true
    pip install --upgrade pip >/dev/null
    pip install --no-cache-dir -r requirements.txt
}

deps_ok() {
    python3 -c "import stable_baselines3" >/dev/null 2>&1
}

if [ ! -d venv ]; then
    echo "Creating a virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# Don't just trust that venv/ existing means it's populated - a
# cancelled/failed install before leaves an empty-but-present venv that
# looks "already set up" and silently hits ModuleNotFoundError.
if ! deps_ok; then
    echo "Installing MuJoCo / RL dependencies - torch is a big download"
    echo "(needs roughly 2-3 GB free disk space), this may take a few minutes..."
    install_deps
    if ! deps_ok; then
        echo
        echo "That didn't fully succeed. The virtual environment may now be in a"
        echo "half-broken state from the failed attempt - deleting it and trying"
        echo "once more from a clean slate..."
        deactivate
        rm -rf venv
        python3 -m venv venv
        source venv/bin/activate
        install_deps
        if ! deps_ok; then
            echo
            echo "Dependency install failed twice - scroll up for pip's actual error."
            echo "Most likely cause: not enough free disk space (a full torch install"
            echo "needs roughly 2-3 GB free) - free some room and run this again."
            exit 1
        fi
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
