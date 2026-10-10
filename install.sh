#!/usr/bin/env bash
# Sets up the MuJoCo Python environment in place and makes the launcher
# scripts executable. No desktop-shortcut step here (unlike install.bat) -
# macOS/Linux shortcut conventions (.app bundles, .desktop files) vary too
# much by distro to do generically; launch_godot.sh / launch_mujoco.sh are
# meant to be run directly or dragged into a dock/launcher by hand.
set -e
cd "$(dirname "$0")"

echo "=== Kiara setup ==="

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found. Install Python 3.10+ (https://www.python.org/downloads/) and re-run this."
    exit 1
fi

if [ ! -d mujoco/venv ]; then
    echo "Creating a Python virtual environment for MuJoCo training..."
    python3 -m venv mujoco/venv
fi
source mujoco/venv/bin/activate
echo "Installing MuJoCo / RL dependencies - torch is a big download, this can take a few minutes..."
pip install --upgrade pip >/dev/null
pip install -r mujoco/requirements.txt

if python3 -c "import stable_baselines3, mujoco, torch" >/dev/null 2>&1; then
    echo "Dependencies OK."
else
    echo "WARNING: dependency install did not fully succeed - re-run install.sh once your"
    echo "internet connection is stable, or launch_mujoco.sh will retry automatically next time."
fi
deactivate

if ! command -v godot >/dev/null 2>&1 && ! command -v godot4 >/dev/null 2>&1; then
    echo
    echo "NOTE: Godot 4.3+ was not found on PATH."
    echo "Download it from https://godotengine.org/download, then either add it to PATH"
    echo "as 'godot', or place the binary directly in this folder as ./godot."
fi

chmod +x launch_godot.sh launch_mujoco.sh

echo
echo "=== Done ==="
echo "Run ./launch_godot.sh to open her in Godot."
echo "Run ./launch_mujoco.sh to train or resume locomotion / reach-and-grasp."
