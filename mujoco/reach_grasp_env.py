"""
Gymnasium environment for upper-body reach-and-grasp training: "see and
grab things" from the request to get Kiara operating in MuJoCo, not just
standing/walking.

Two honest simplifications, documented rather than hidden:

  1. "Seeing" here is the target's true relative position fed straight
     into the observation vector (perfect simulated vision), not a
     camera/pixel pipeline - that's task #16 (vision-language interface),
     explicitly a separate, later piece of work. This gives the policy
     something to reach toward now without blocking on that.

  2. "Grabbing" is operationalized as sustained proximity + low relative
     velocity between the hand and the target, not finger-actuated
     dexterous grasping - kiara_humanoid.xml's hands are bare capsule
     geoms with a single wrist hinge each, no fingers. A real grasp
     needs actuated fingers added to the MJCF; this reach_grasp task is
     the right place to plug that in later without changing the reward
     structure, which already treats "hold the hand at the target with
     near-zero relative speed for grasp_hold_time" as the success
     condition.

The root is kinematically pinned (qpos/qvel for the pelvis free-joint are
reset every step) so the policy learns reaching, not balance - standing
while reaching is a harder combined task for a future curriculum stage
once this one and `walk` are both solid.
"""

from __future__ import annotations
import os
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import mujoco

MODEL_PATH = os.path.join(os.path.dirname(__file__), "kiara_reach_grasp.xml")

# only the right arm is actuated for this task; everything else (legs,
# left arm, spine, neck) is held at its rest pose by zeroing those
# ctrl entries every step, so the action space is small and the policy
# isn't wasting exploration on joints irrelevant to reaching.
ARM_ACTUATORS = ["m_shoulder_R_flex", "m_shoulder_R_abd", "m_shoulder_R_rot", "m_elbow_R", "m_wrist_R"]

GRASP_RADIUS = 0.06      # meters - hand-to-target distance counted as "touching"
GRASP_MAX_REL_SPEED = 0.4  # m/s - above this it's a swipe/knock, not a controlled grasp
GRASP_HOLD_STEPS = 15     # ~0.3s at 50Hz control - must hold the grasp, not just tag it


class KiaraReachGraspEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, episode_seconds: float = 6.0):
        super().__init__()
        self.model = mujoco.MjModel.from_xml_path(MODEL_PATH)
        self.data = mujoco.MjData(self.model)
        self.frame_skip = 4  # control at 125Hz given 0.002s sim timestep
        self.max_steps = int(episode_seconds / (self.model.opt.timestep * self.frame_skip))
        self._step_count = 0
        self._grasp_hold = 0

        self._arm_act_idx = [self.model.actuator(n).id for n in ARM_ACTUATORS]
        self._all_act_idx = np.arange(self.model.nu)
        self._non_arm_act_idx = np.array([i for i in self._all_act_idx if i not in self._arm_act_idx])

        self._hand_body_id = self.model.body("hand_R").id
        self._target_body_id = self.model.body("target").id
        self._target_qpos_adr = self.model.body(self._target_body_id).jntadr[0]
        self._target_qpos_slice = slice(
            self.model.jnt_qposadr[self._target_qpos_adr],
            self.model.jnt_qposadr[self._target_qpos_adr] + 7,
        )
        # free-joint root pose to pin the pelvis at every step
        self._pinned_qpos0 = None
        self._prev_action = np.zeros(len(self._arm_act_idx), dtype=np.float32)

        obs_dim = self._get_obs().shape[0]
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(obs_dim,), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(len(self._arm_act_idx),), dtype=np.float32)

    def _hand_pos(self) -> np.ndarray:
        return self.data.xpos[self._hand_body_id].copy()

    def _target_pos(self) -> np.ndarray:
        return self.data.xpos[self._target_body_id].copy()

    def _get_obs(self) -> np.ndarray:
        hand_pos = self._hand_pos()
        target_pos = self._target_pos()
        rel = target_pos - hand_pos  # the "vision" stand-in - see module docstring
        arm_qpos = np.array([self.data.qpos[self.model.jnt_qposadr[self.model.joint(j).id]]
                              for j in self._arm_joint_names()], dtype=np.float32).flatten()
        arm_qvel = np.array([self.data.qvel[self.model.jnt_dofadr[self.model.joint(j).id]]
                              for j in self._arm_joint_names()], dtype=np.float32).flatten()
        hand_vel = self.data.cvel[self._hand_body_id][3:6]
        return np.concatenate([rel, hand_vel, arm_qpos, arm_qvel]).astype(np.float32)

    def _arm_joint_names(self):
        return ["shoulder_R_flex", "shoulder_R_abd", "shoulder_R_rot", "elbow_R", "wrist_R"]

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        mujoco.mj_resetData(self.model, self.data)
        if self._pinned_qpos0 is None:
            self._pinned_qpos0 = self.model.qpos0[0:7].copy()

        # randomize the target within right-arm reach each episode, so
        # the policy learns to reach generally rather than memorizing
        # one fixed point
        reach = self.np_random.uniform(
            low=[0.15, -0.35, 0.75], high=[0.45, 0.05, 1.15]
        )
        self.data.qpos[self._target_qpos_slice] = [reach[0], reach[1], reach[2], 1, 0, 0, 0]
        mujoco.mj_forward(self.model, self.data)
        self._step_count = 0
        self._grasp_hold = 0
        self._prev_action[:] = 0.0
        return self._get_obs(), {}

    def step(self, action: np.ndarray):
        action = np.clip(action, -1.0, 1.0).astype(np.float32)
        self.data.ctrl[self._non_arm_act_idx] = 0.0
        self.data.ctrl[self._arm_act_idx] = action

        for _ in range(self.frame_skip):
            # kinematic pin: hold the pelvis free-joint at its rest pose/
            # zero velocity every substep, so this task is pure reaching,
            # not balance (see module docstring)
            self.data.qpos[0:7] = self._pinned_qpos0
            self.data.qvel[0:6] = 0.0
            mujoco.mj_step(self.model, self.data)
        self._step_count += 1

        obs = self._get_obs()
        reward, info = self._compute_reward(action)
        terminated = bool(info["grasped"] and self._grasp_hold >= GRASP_HOLD_STEPS)
        truncated = self._step_count >= self.max_steps
        self._prev_action = action
        return obs, reward, terminated, truncated, info

    def _compute_reward(self, action: np.ndarray):
        hand_pos = self._hand_pos()
        target_pos = self._target_pos()
        dist = float(np.linalg.norm(target_pos - hand_pos))
        hand_speed = float(np.linalg.norm(self.data.cvel[self._hand_body_id][3:6]))

        reach_reward = -1.0 * dist                      # dense distance shaping
        proximity_bonus = 1.5 * np.exp(-dist / 0.08)     # sharp bonus once close
        grasped = dist < GRASP_RADIUS and hand_speed < GRASP_MAX_REL_SPEED
        if grasped:
            self._grasp_hold += 1
        else:
            self._grasp_hold = 0
        grasp_bonus = 3.0 if grasped else 0.0
        success_bonus = 25.0 if (grasped and self._grasp_hold >= GRASP_HOLD_STEPS) else 0.0

        energy_penalty = -0.01 * float(np.sum(action ** 2))
        smoothness_penalty = -0.01 * float(np.sum((action - self._prev_action) ** 2))

        reward = (reach_reward + proximity_bonus + grasp_bonus + success_bonus
                  + energy_penalty + smoothness_penalty)
        info = {"dist": dist, "grasped": grasped, "grasp_hold": self._grasp_hold}
        return float(reward), info


def make_env():
    return KiaraReachGraspEnv()
