"""
PPO training for the right-arm reach-and-grasp task (reach_grasp_env.py).
Same stabilization approach as train.py's locomotion stages (VecNormalize
+ target_kl) since this is the same family of problem - a single fixed
hyperparameter set that happened to work for the first naive locomotion
run definitely would not have worked here either without it.

Usage:
    python3 train_reach_grasp.py --timesteps 2000000
"""

from __future__ import annotations
import argparse
import os

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecNormalize
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from reach_grasp_env import KiaraReachGraspEnv

CKPT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")


def make_env_fn(seed: int):
    def _init():
        env = KiaraReachGraspEnv()
        env = Monitor(env)
        env.reset(seed=seed)
        return env
    return _init


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timesteps", type=int, default=2_000_000)
    ap.add_argument("--n-envs", type=int, default=4)
    ap.add_argument("--resume", type=str, default=None)
    ap.add_argument("--vecnorm-resume", type=str, default=None)
    ap.add_argument("--checkpoint-freq", type=int, default=50_000)
    args = ap.parse_args()

    os.makedirs(CKPT_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    env_fns = [make_env_fn(seed=i) for i in range(args.n_envs)]
    vec_env = SubprocVecEnv(env_fns)

    if args.vecnorm_resume:
        vec_env = VecNormalize.load(args.vecnorm_resume, vec_env)
        vec_env.training = True
    else:
        vec_env = VecNormalize(vec_env, norm_obs=True, norm_reward=True, clip_obs=10.0, clip_reward=10.0, gamma=0.99)

    if args.resume:
        model = PPO.load(args.resume, env=vec_env, device="cpu")
    else:
        model = PPO(
            "MlpPolicy",
            vec_env,
            device="cpu",
            n_steps=1024,
            batch_size=256,
            n_epochs=10,
            gamma=0.98,
            gae_lambda=0.95,
            clip_range=0.2,
            ent_coef=0.005,
            learning_rate=3e-4,
            target_kl=0.03,
            policy_kwargs=dict(net_arch=dict(pi=[128, 128], vf=[128, 128])),
            tensorboard_log=LOG_DIR,
            verbose=1,
        )

    checkpoint_callback = CheckpointCallback(
        save_freq=max(1, args.checkpoint_freq // args.n_envs),
        save_path=CKPT_DIR,
        name_prefix="reach_grasp",
        save_vecnormalize=True,
    )

    print(f"Training reach_grasp for {args.timesteps} timesteps across {args.n_envs} envs...")
    model.learn(total_timesteps=args.timesteps, callback=checkpoint_callback, progress_bar=False,
                reset_num_timesteps=(args.resume is None))

    final_path = os.path.join(CKPT_DIR, "reach_grasp_final.zip")
    model.save(final_path)
    vec_env.save(os.path.join(CKPT_DIR, "reach_grasp_final_vecnormalize.pkl"))
    print(f"Saved final model: {final_path}")


if __name__ == "__main__":
    main()
