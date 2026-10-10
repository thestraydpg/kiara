"""
Interactive MuJoCo viewer - actually watch Kiara in the simulation
instead of only ever training headless. Auto-picks the latest checkpoint
for the chosen task unless told otherwise; if none exists yet, she just
drops into the scene with zero action (no balance/reach behavior, but
you can still see the body/physics/world before any training has run).

Mouse controls (built into MuJoCo's native viewer, nothing custom here):
  left-drag                    - orbit camera
  right-drag / shift+left-drag - pan
  scroll                       - zoom
  ctrl + right-drag on her     - apply a push/perturbation force, to see
      how she reacts/recovers - this is the standard way to "test" a
      standing/balance policy interactively
  double-click a body          - select/focus it
  Space                        - pause/resume
  Backspace                    - reset the simulation

Usage:
    python3 view.py                       # stand, latest checkpoint
    python3 view.py --task reach_grasp
    python3 view.py --task stand --checkpoint checkpoints/stand_latest.zip
    python3 view.py --task stand --no-policy   # physics/body only, zero action
"""

from __future__ import annotations
import argparse
import glob
import os
import re
import time

import numpy as np
import mujoco
import mujoco.viewer

from locomotion_env import KiaraLocomotionEnv
from reach_grasp_env import KiaraReachGraspEnv

CKPT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
TARGET_SPEEDS = {"stand": 0.0, "walk_slow": 0.6, "walk": 1.3}


def find_checkpoint(prefix: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    latest_named = os.path.join(CKPT_DIR, f"{prefix}_latest.zip")
    if os.path.exists(latest_named):
        return latest_named
    candidates = glob.glob(os.path.join(CKPT_DIR, f"{prefix}_*_steps.zip"))
    if not candidates:
        return None

    def step_count(path: str) -> int:
        m = re.search(r"_(\d+)_steps\.zip$", path)
        return int(m.group(1)) if m else -1

    return max(candidates, key=step_count)


def find_vecnorm(checkpoint_path: str, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    d, fname = os.path.split(checkpoint_path)
    if fname.endswith("_latest.zip"):
        candidate = fname[: -len(".zip")] + "_vecnormalize.pkl"
    else:
        m = re.match(r"(.+)_(\d+)_steps\.zip$", fname)
        if not m:
            return None
        candidate = f"{m.group(1)}_vecnormalize_{m.group(2)}_steps.pkl"
    full = os.path.join(d, candidate)
    return full if os.path.exists(full) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["stand", "walk_slow", "walk", "reach_grasp"], default="stand")
    ap.add_argument("--checkpoint", default=None, help="explicit .zip to load instead of auto-picking the latest")
    ap.add_argument("--vecnorm", default=None, help="explicit vecnormalize .pkl to match --checkpoint")
    ap.add_argument("--no-policy", action="store_true", help="skip loading any policy - zero action, physics/body only")
    ap.add_argument("--show-capsules", action="store_true",
                     help="show the plain collision capsules instead of her real skin (debug aid)")
    args = ap.parse_args()

    if args.task == "reach_grasp":
        env = KiaraReachGraspEnv()
        prefix = "reach_grasp"
    else:
        # episode_seconds huge: termination (falling) still resets her,
        # but we don't want the fixed per-stage training episode length
        # cutting the view short and resetting every few seconds.
        env = KiaraLocomotionEnv(target_speed=TARGET_SPEEDS[args.task], episode_seconds=1_000_000.0)
        prefix = args.task

    model = None
    vecnorm = None
    if not args.no_policy:
        ckpt_path = find_checkpoint(prefix, args.checkpoint)
        if ckpt_path:
            from stable_baselines3 import PPO
            from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize

            print(f"Loaded policy: {ckpt_path}")
            model = PPO.load(ckpt_path, device="cpu")
            vecnorm_path = find_vecnorm(ckpt_path, args.vecnorm)
            if vecnorm_path:
                print(f"Loaded observation normalization: {vecnorm_path}")
                dummy = DummyVecEnv([lambda: env])
                vecnorm = VecNormalize.load(vecnorm_path, dummy)
                vecnorm.training = False
                vecnorm.norm_reward = False
        else:
            print(f"No trained checkpoint found yet for '{prefix}' - she'll just sit in her rest")
            print("pose under gravity with zero action. That's expected before training has")
            print("run; the physics/rendering itself still works fine without one.")

    obs, _ = env.reset()
    sim_dt = env.model.opt.timestep * env.frame_skip

    print("Launching viewer - left-drag to orbit, scroll to zoom, ctrl+right-drag")
    print("on her to push her and see how she responds. Close the window to quit.")
    with mujoco.viewer.launch_passive(env.model, env.data) as viewer:
        with viewer.lock():
            # group 1 = her real skin mesh, group 2 = the plain collision
            # capsules underneath it (physics-only; mass=0 visual geoms
            # don't change the trained dynamics either way). Default to
            # showing the real body, not the stick-figure proxy it's
            # actually simulated as.
            viewer.opt.geomgroup[2] = 1 if args.show_capsules else 0

        while viewer.is_running():
            step_start = time.time()

            if model is not None:
                query_obs = vecnorm.normalize_obs(obs) if vecnorm is not None else obs
                action, _ = model.predict(query_obs, deterministic=True)
            else:
                action = np.zeros(env.action_space.shape, dtype=np.float32)

            obs, _reward, terminated, truncated, _info = env.step(action)
            if terminated or truncated:
                obs, _ = env.reset()

            viewer.sync()
            elapsed = time.time() - step_start
            if elapsed < sim_dt:
                time.sleep(sim_dt - elapsed)


if __name__ == "__main__":
    main()
