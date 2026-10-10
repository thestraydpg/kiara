"""
Gymnasium environment wrapping the Kiara locomotion MJCF model, for PPO
training of standing balance and walking.

Reward design deliberately avoids the classic "maximize forward velocity"
trap, which produces fast but grotesque/inhuman gaits (the textbook
failure mode of naive humanoid RL). Instead it rewards:
  - staying alive / upright (this alone bootstraps standing balance)
  - tracking a TARGET walking speed rather than maximizing speed
  - an energy/effort penalty (discourages twitchy, unnatural motion)
  - a symmetry term between left/right joint activity over a short
    window (discourages limping/one-sided gaits)
  - a smoothness penalty on action deltas frame-to-frame (discourages
    jittery, non-physical-looking control)
These are the standard techniques used to get RL humanoid locomotion to
look like walking rather than "fastest way to fall forward repeatedly"
(which is what pure forward-velocity reward famously produces).
"""

from __future__ import annotations
import os
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import mujoco

MODEL_PATH = os.path.join(os.path.dirname(__file__), "kiara_humanoid.xml")

# left/right actuator name pairs, for the symmetry term
LR_PAIRS = [
    ("m_hip_L_flex", "m_hip_R_flex"), ("m_hip_L_abd", "m_hip_R_abd"), ("m_hip_L_rot", "m_hip_R_rot"),
    ("m_knee_L", "m_knee_R"),
    ("m_ankle_L_flex", "m_ankle_R_flex"), ("m_ankle_L_roll", "m_ankle_R_roll"),
    ("m_shoulder_L_flex", "m_shoulder_R_flex"), ("m_shoulder_L_abd", "m_shoulder_R_abd"),
    ("m_elbow_L", "m_elbow_R"),
]


class KiaraLocomotionEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, target_speed: float = 1.0, episode_seconds: float = 10.0):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(MODEL_PATH)
        self.data = mujoco.MjData(self.model)
        self.target_speed = target_speed
        self.frame_skip = 5  # control at 100Hz given 0.002s sim timestep
        self.max_steps = int(episode_seconds / (self.model.opt.timestep * self.frame_skip))
        self._step_count = 0
        self._prev_action = np.zeros(self.model.nu, dtype=np.float32)

        self._lr_pair_idx = [
            (self.model.actuator(a).id, self.model.actuator(b).id)
            for a, b in LR_PAIRS
        ]

        obs_dim = self._get_obs().shape[0]
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(self.model.nu,), dtype=np.float32)

    def _get_obs(self) -> np.ndarray:
        qpos = self.data.qpos[7:]     # skip the free-joint root position+quat
        qvel = self.data.qvel[6:]     # skip root linear+angular velocity
        root_quat = self.data.qpos[3:7]
        root_lin_vel = self.data.qvel[0:3]
        root_ang_vel = self.data.qvel[3:6]
        root_height = np.array([self.data.qpos[2]])
        return np.concatenate([qpos, qvel, root_quat, root_lin_vel, root_ang_vel, root_height]).astype(np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        # small random perturbation to initial pose so the policy doesn't
        # overfit to one exact starting configuration
        noise = self.np_random.uniform(-0.02, 0.02, size=self.model.nq)
        self.data.qpos[:] = self.model.qpos0 + noise
        mujoco.mj_forward(self.model, self.data)
        self._step_count = 0
        self._prev_action[:] = 0.0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        action = np.clip(action, -1.0, 1.0).astype(np.float32)
        self.data.ctrl[:] = action
        for _ in range(self.frame_skip):
            mujoco.mj_step(self.model, self.data)
        self._step_count += 1

        obs = self._get_obs()
        reward, info = self._compute_reward(action)
        terminated = self._is_terminated()
        truncated = self._step_count >= self.max_steps
        self._prev_action = action
        return obs, reward, terminated, truncated, info

    def _compute_reward(self, action: np.ndarray):
        root_height = self.data.qpos[2]
        root_quat = self.data.qpos[3:7]
        forward_vel = self.data.qvel[0]  # local x is "forward" per our MJCF root orientation at spawn

        # upright bonus - penalize tilt away from vertical (quaternion
        # z-component of the "up" vector rotated into world frame)
        up_world = np.zeros(3)
        mujoco.mju_rotVecQuat(up_world, np.array([0, 0, 1.0]), root_quat)
        upright = max(0.0, up_world[2])  # 1.0 = perfectly upright

        alive_bonus = 1.0
        height_penalty = -5.0 * max(0.0, 0.85 - root_height)  # heavy penalty for crouching/falling
        speed_error = -1.5 * abs(forward_vel - self.target_speed)
        energy_penalty = -0.015 * float(np.sum(action ** 2))
        smoothness_penalty = -0.01 * float(np.sum((action - self._prev_action) ** 2))

        symmetry_penalty = 0.0
        for li, ri in self._lr_pair_idx:
            symmetry_penalty -= 0.002 * abs(abs(self.data.ctrl[li]) - abs(self.data.ctrl[ri]))

        reward = (
            alive_bonus
            + 2.0 * upright
            + height_penalty
            + speed_error
            + energy_penalty
            + smoothness_penalty
            + symmetry_penalty
        )
        info = {
            "upright": upright, "forward_vel": forward_vel, "height": root_height,
        }
        return float(reward), info

    def _is_terminated(self) -> bool:
        root_height = self.data.qpos[2]
        root_quat = self.data.qpos[3:7]
        up_world = np.zeros(3)
        mujoco.mju_rotVecQuat(up_world, np.array([0, 0, 1.0]), root_quat)
        fell = root_height < 0.55 or up_world[2] < 0.3
        return bool(fell)


def make_env(target_speed: float = 1.0):
    return KiaraLocomotionEnv(target_speed=target_speed)
