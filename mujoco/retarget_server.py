"""
Streams the trained MuJoCo locomotion policy's motion onto Kiara's real
Godot skeleton, as per-bone local pose rotations - the payoff of doing
"both": MuJoCo's own viewer is always going to show a capsule-ish body
(that's the correct way to train physics, and view.py's skin overlay
only goes so far with its rigid per-body cut), but her REAL skinned/
textured character in Godot can still perform the trained motion.

How a bone's local pose rotation is computed: MuJoCo gives each body's
current WORLD rotation directly (mj_step already resolves the whole
kinematic chain - no manual chaining needed here). Every body's REST
orientation is identity (confirmed separately against qpos0), so that
world rotation IS already the rotation delta away from rest. Godot's
Skeleton3D.set_bone_pose_rotation() expects that same delta, but
expressed in the BONE's own rest-local frame, which has different axes
than MuJoCo's world frame (Blender points each bone's local Y along its
own head->tail direction - unrelated to MuJoCo's hinge axis choices).
Converting between the two is a standard similarity/conjugation:

    local_rotation = rest_basis^T @ world_rotation @ rest_basis

where rest_basis is the bone's rest rotation matrix (from
blender_bone_rest.json, written by blender_scripts/13_export_bone_rest.py)
- orthonormal, so its transpose is its inverse.

MuJoCo's single "spine" body covers what the Blender rig splits into 17
vertebrae (spine_L1-5, spine_T1-12); its single "head" body covers 7
cervical vertebrae plus the head bone. Both get their one computed
rotation raised to a fractional quaternion power (1/17 and 1/8) and
applied to every bone in that chain, so one consolidated MuJoCo
rotation reads as a smooth curve across many vertebrae instead of the
full angle slamming onto a single bone.

Caveat this file can't resolve on its own: everything here was built
and numerically sanity-checked (rest bases pulled directly from
Blender, coordinate frames cross-validated against MuJoCo's own rest
pose - see git log) but never actually SEEN; this sandbox has no
display. If a limb looks like it's bending the wrong way, backwards, or
on the wrong axis once you run it, that's almost certainly a sign/axis
mixup in one specific joint, not the whole approach - say which one and
it's a small, targeted fix, not a redesign.

Wire protocol (deliberately NOT the Euler-degrees format mcu_bridge.gd
uses - that depends on matching Godot's default Euler order exactly,
which is an easy thing to get subtly wrong with no way to visually
check from here): one JSON object per line,
    {"type": "pose", "bones": {"thigh.L": [x, y, z, w], ...}}
quaternion components direct, consumed as Quaternion(x, y, z, w) in
Godot - no Euler order ambiguity possible.

Usage:
    python3 retarget_server.py --task stand
Then in Godot, RetargetBridge (godot/scripts/retarget_bridge.gd)
connects to 127.0.0.1:8766 and applies the stream to her skeleton.
"""

from __future__ import annotations
import argparse
import json
import socket
import time

import numpy as np
import mujoco

from locomotion_env import KiaraLocomotionEnv
from view import find_checkpoint, find_vecnorm

PORT = 8766
TARGET_SPEEDS = {"stand": 0.0, "walk_slow": 0.6, "walk": 1.3}

# MuJoCo body -> single Blender bone (direct 1:1 limb mapping)
DIRECT_MAP = {
    "upperarm_L": "upperarm.L", "forearm_L": "forearm.L", "hand_L": "hand.L",
    "upperarm_R": "upperarm.R", "forearm_R": "forearm.R", "hand_R": "hand.R",
    "thigh_L": "thigh.L", "shank_L": "shin.L", "foot_L": "foot.L",
    "thigh_R": "thigh.R", "shank_R": "shin.R", "foot_R": "foot.R",
    "pelvis": "pelvis",
}
# MuJoCo body -> Blender bone CHAIN (one consolidated rotation, distributed
# evenly across every bone in the chain via fractional quaternion power)
CHAIN_MAP = {
    "spine": [f"spine_L{i}" for i in range(1, 6)] + [f"spine_T{i}" for i in range(1, 13)],
    "head": [f"neck_C{i}" for i in range(1, 8)] + ["head"],
}


def quat_from_matrix(r: np.ndarray) -> np.ndarray:
    """3x3 rotation matrix -> (x, y, z, w), via mujoco's own (robust,
    battle-tested) implementation rather than hand-rolling one."""
    q = np.zeros(4)
    mujoco.mju_mat2Quat(q, r.flatten())
    return np.array([q[1], q[2], q[3], q[0]])  # mujoco is (w,x,y,z) -> (x,y,z,w)


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return np.array([
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ])


def quat_conjugate(q: np.ndarray) -> np.ndarray:
    return np.array([-q[0], -q[1], -q[2], q[3]])


def quat_power(q: np.ndarray, t: float) -> np.ndarray:
    """Fractional quaternion power via axis-angle (shortest-path safe)."""
    x, y, z, w = q
    if w < 0:  # ensure shortest-path angle in [0, pi]
        x, y, z, w = -x, -y, -z, -w
    w = np.clip(w, -1.0, 1.0)
    angle = 2.0 * np.arccos(w)
    if angle < 1e-8:
        return np.array([0.0, 0.0, 0.0, 1.0])
    axis = np.array([x, y, z]) / np.sin(angle / 2.0)
    half = angle * t / 2.0
    return np.array([*(axis * np.sin(half)), np.cos(half)])


def local_pose_from_world(world_quat_xyzw: np.ndarray, rest_basis: np.ndarray) -> np.ndarray:
    """world_quat_xyzw: the body's rotation delta from rest, in world
    space. rest_basis: the Blender bone's rest rotation matrix (columns
    = local X/Y/Z axes in armature/world space). Returns the equivalent
    local pose quaternion for that bone."""
    r_world = np.zeros(9)
    mujoco.mju_quat2Mat(r_world, [world_quat_xyzw[3], *world_quat_xyzw[:3]])
    r_world = r_world.reshape(3, 3)
    r_local = rest_basis.T @ r_world @ rest_basis
    return quat_from_matrix(r_local)


class Retargeter:
    def __init__(self, bone_rest_path: str):
        rest = json.load(open(bone_rest_path))
        self.rest_basis = {name: np.array(v["basis"]) for name, v in rest.items()}

    def compute_bone_poses(self, model, data) -> dict[str, list[float]]:
        out = {}
        for mj_body, bone in DIRECT_MAP.items():
            bid = model.body(mj_body).id
            wq = data.xquat[bid]  # (w, x, y, z)
            world_quat_xyzw = np.array([wq[1], wq[2], wq[3], wq[0]])
            local = local_pose_from_world(world_quat_xyzw, self.rest_basis[bone])
            out[bone] = local.tolist()
        for mj_body, chain in CHAIN_MAP.items():
            bid = model.body(mj_body).id
            wq = data.xquat[bid]
            world_quat_xyzw = np.array([wq[1], wq[2], wq[3], wq[0]])
            n = len(chain)
            for bone in chain:
                frac_world = quat_power(world_quat_xyzw, 1.0 / n)
                local = local_pose_from_world(frac_world, self.rest_basis[bone])
                out[bone] = local.tolist()
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["stand", "walk_slow", "walk"], default="stand")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--vecnorm", default=None)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--bone-rest", default="blender_bone_rest.json")
    ap.add_argument("--hz", type=float, default=30.0, help="pose stream rate sent to Godot")
    args = ap.parse_args()

    env = KiaraLocomotionEnv(target_speed=TARGET_SPEEDS[args.task], episode_seconds=1_000_000.0)
    retargeter = Retargeter(args.bone_rest)

    model_loaded = None
    vecnorm = None
    ckpt_path = find_checkpoint(args.task, args.checkpoint)
    if ckpt_path:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
        print(f"Loaded policy: {ckpt_path}")
        model_loaded = PPO.load(ckpt_path, device="cpu")
        vn_path = find_vecnorm(ckpt_path, args.vecnorm)
        if vn_path:
            dummy = DummyVecEnv([lambda: env])
            vecnorm = VecNormalize.load(vn_path, dummy)
            vecnorm.training = False
            vecnorm.norm_reward = False
    else:
        print(f"No trained checkpoint for '{args.task}' yet - streaming zero-action rest pose.")

    print(f"Listening on 127.0.0.1:{args.port} for the Godot RetargetBridge to connect...")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(1)

    obs, _ = env.reset()
    sim_dt = env.model.opt.timestep * env.frame_skip
    send_period = 1.0 / args.hz

    while True:
        conn, addr = server.accept()
        print(f"Godot connected from {addr}")
        conn.setblocking(False)
        last_send = 0.0
        try:
            while True:
                step_start = time.time()
                if model_loaded is not None:
                    query_obs = vecnorm.normalize_obs(obs) if vecnorm is not None else obs
                    action, _ = model_loaded.predict(query_obs, deterministic=True)
                else:
                    action = np.zeros(env.action_space.shape, dtype=np.float32)

                obs, _reward, terminated, truncated, _info = env.step(action)
                if terminated or truncated:
                    obs, _ = env.reset()

                now = time.time()
                if now - last_send >= send_period:
                    last_send = now
                    bones = retargeter.compute_bone_poses(env.model, env.data)
                    pelvis_pos = env.data.qpos[0:3].tolist()
                    msg = json.dumps({"type": "pose", "bones": bones, "pelvis_pos": pelvis_pos}) + "\n"
                    conn.send(msg.encode("utf-8"))

                elapsed = time.time() - step_start
                if elapsed < sim_dt:
                    time.sleep(sim_dt - elapsed)
        except (BrokenPipeError, ConnectionResetError):
            print("Godot disconnected, waiting for a new connection...")
            conn.close()


if __name__ == "__main__":
    main()
