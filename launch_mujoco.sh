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
echo "What do you want to do?"
echo "  1) Watch her in MuJoCo - standing/locomotion (opens an interactive 3D window)"
echo "  2) Watch her in MuJoCo - reach and grasp"
echo "  3) Train/continue - standing balance / locomotion (no window, just logs)"
echo "  4) Train/continue - reach and grasp (no window, just logs)"
echo "  5) Stream her trained motion onto her REAL Godot character"
echo "     (run this, then launch Godot separately - it auto-connects)"
read -r -p "Choose 1-5: " choice

case "$choice" in
    2)
        python3 view.py --task reach_grasp
        ;;
    5)
        echo
        echo "Streaming the standing-balance policy to 127.0.0.1:8766 - leave this"
        echo "running, then launch/re-launch Godot (RetargetBridge retries the"
        echo "connection every 2s, so the order doesn't matter). Ctrl+C to stop."
        python3 retarget_server.py --task stand
        ;;
    3)
        if [ -f checkpoints/stand_latest.zip ]; then
            echo "Resuming from the included checkpoint..."
            python3 train.py --stage stand --timesteps 10000000 --n-envs 4 \
                --resume checkpoints/stand_latest.zip \
                --vecnorm-resume checkpoints/stand_latest_vecnormalize.pkl
        else
            python3 train.py --stage stand --timesteps 10000000 --n-envs 4
        fi
        ;;
    4)
        if [ -f checkpoints/reach_grasp_latest.zip ]; then
            echo "Resuming from the included checkpoint..."
            python3 train_reach_grasp.py --timesteps 3000000 --n-envs 4 \
                --resume checkpoints/reach_grasp_latest.zip \
                --vecnorm-resume checkpoints/reach_grasp_latest_vecnormalize.pkl
        else
            python3 train_reach_grasp.py --timesteps 3000000 --n-envs 4
        fi
        ;;
    *)
        python3 view.py --task stand
        ;;
esac
