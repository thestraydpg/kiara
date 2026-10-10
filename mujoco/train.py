"""
PPO training for the Kiara locomotion policy, staged as a curriculum:
  stage 1: standing balance (target_speed=0) - learn to not fall over
  stage 2: slow walk (target_speed=0.6 m/s)
  stage 3: normal walk (target_speed=1.3 m/s, typical human pace)
Each stage is warm-started from the previous stage's checkpoint, which is
standard practice for humanoid locomotion curricula - jumping straight to
"walk at human pace" from a randomly initialized policy wastes enormous
amounts of compute relearning balance from scratch at every failed step.

This is genuinely CPU-only, 4-core, slow-going training (no GPU in this
environment) - realistic timeline is HOURS of wall-clock per stage to
reach competent behavior, not minutes. Checkpoints save frequently so
progress persists across separate background runs/sessions rather than
needing one unbroken multi-hour process.

Usage:
    python3 train.py --stage stand --timesteps 2000000
    python3 train.py --stage walk_slow --timesteps 3000000 --resume checkpoints/stand_final.zip
"""

from __future__ import annotations
import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from locomotion_env import KiaraLocomotionEnv

CKPT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

STAGES = {
    "stand": dict(target_speed=0.0, episode_seconds=8.0),
    "walk_slow": dict(target_speed=0.6, episode_seconds=10.0),
    "walk": dict(target_speed=1.3, episode_seconds=12.0),
}


def make_env_fn(stage_kwargs: dict, seed: int):
    def _init():
        env = KiaraLocomotionEnv(**stage_kwargs)
        env = Monitor(env)
        env.reset(seed=seed)
        return env
    return _init


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=list(STAGES.keys()), required=True)
    ap.add_argument("--timesteps", type=int, default=2_000_000)
    ap.add_argument("--n-envs", type=int, default=4)
    ap.add_argument("--resume", type=str, default=None, help="checkpoint .zip to warm-start from")
    ap.add_argument("--checkpoint-freq", type=int, default=50_000, help="env steps between checkpoints")
    args = ap.parse_args()

    os.makedirs(CKPT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    stage_kwargs = STAGES[args.stage]
    env_fns = [make_env_fn(stage_kwargs, seed=i) for i in range(args.n_envs)]
    vec_env = SubprocVecEnv(env_fns)

    if args.resume:
        print(f"Resuming from {args.resume}")
        model = PPO.load(args.resume, env=vec_env, device="cpu")
    else:
        model = PPO(
            "MlpPolicy",
            vec_env,
            device="cpu",
            n_steps=2048,
            batch_size=256,
            n_epochs=10,
            gamma=0.99,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.003,
            learning_rate=3e-4,
            policy_kwargs=dict(net_arch=dict(pi=[256, 256], vf=[256, 256])),
            tensorboard_log=LOG_DIR,
            verbose=1,
        )

    checkpoint_callback = CheckpointCallback(
        save_freq=max(1, args.checkpoint_freq // args.n_envs),
        save_path=CKPT_DIR,
        name_prefix=f"{args.stage}",
    )

    print(f"Training stage '{args.stage}' for {args.timesteps} timesteps across {args.n_envs} envs...")
    model.learn(total_timesteps=args.timesteps, callback=checkpoint_callback, progress_bar=False,
                reset_num_timesteps=(args.resume is None))

    final_path = os.path.join(CKPT_DIR, f"{args.stage}_final.zip")
    model.save(final_path)
    print(f"Saved final model: {final_path}")


if __name__ == "__main__":
    main()
