# Kiara

A physically-simulated 3D digital human, built from a real-world scan
through a scripted Blender pipeline, rigged with a biomechanical skeleton,
and driven by real physics in two engines: Godot (soft-tissue/hair jiggle,
real-time render) and MuJoCo (full-body locomotion, trained with PPO).

This repo currently covers the **body, physics, and render** only. The
"mind" layer (gesture/PAD emotional state, physiology tracking,
vision-language perception, speech/TTS) is intentionally out of scope here
— the MCU bridge and brain-fireable function interface already exist as
integration points (`mcu/`, `agent/`, `godot/scripts/mcu_bridge.gd`) so that
layer can be built against this body without any rework.

## Quick start: Godot (render + soft-body physics)

1. Open `godot/` as a project in Godot 4.3+.
2. Run the project (F5) — the main scene is `scenes/kiara_character.tscn`.
3. What's wired up:
   - `assets/kiara.glb` — the full rigged, textured mesh (real eyeballs
     + eyelids, separated jaw/lips, 160-bone skeleton, hair clumps).
   - `SpringBoneRig` — jiggle physics (breast/belly/glute/hair) driven off
     real per-region stiffness/damping/gravity profiles, attached to the
     imported `Skeleton3D`.
   - `MCUBridge` — a TCP socket client (`127.0.0.1:8765`) that listens for
     brain commands and applies them to the skeleton. No server needs to be
     running for the character to load and stand — this is the deferred
     "mind" layer's attachment point, not a hard dependency.

## Quick start: MuJoCo (locomotion)

```
cd mujoco
python3 train.py --stage stand --timesteps 10000000 --n-envs 4
```

- `kiara_humanoid.xml` — MJCF biomechanical body model (`build_humanoid_mjcf.py`
  generates it from the same proportions as the Blender rig).
- `locomotion_env.py` — gym-style env, 3-stage curriculum (`stand` →
  `walk_slow` → `walk`), each warm-started from the previous stage.
- `train.py` — PPO via stable-baselines3, CPU-only. Uses `VecNormalize`
  (obs+reward normalization) and `target_kl=0.03` — an earlier run without
  these diverged (`approx_kl` ~1.5, action `std` stuck at ~9, saturating
  every actuator every step); with them, `approx_kl` holds ~0.02-0.03 and
  `std` ~1.0-1.1 with `ep_rew_mean` climbing steadily.
- Checkpoints save to `mujoco/checkpoints/*.zip` (+ matching
  `*_vecnormalize_*.pkl` — **always resume with both**, the policy and its
  observation normalization stats are trained together and mismatch if you
  load one without the other):
  ```
  python3 train.py --stage walk_slow --timesteps 3000000 \
      --resume checkpoints/stand_final.zip \
      --vecnorm-resume checkpoints/stand_final_vecnormalize.pkl
  ```
- To retarget a trained MuJoCo policy's joint angles onto the Godot
  skeleton for playback (not yet built — next step after a `stand`/`walk`
  stage finishes): both skeletons use the same bone naming convention
  (`02_build_skeleton.py` for Godot, `build_humanoid_mjcf.py` for MuJoCo)
  specifically so that mapping is a name-matched copy, not a re-rig.

## Pipeline (how she was built)

See `blender_scripts/README.md` for the full `01_retopo.py` →
`11_separate_jaw_lips.py` chain that goes from the raw body scan to
`godot/assets/kiara.glb`. Rerun it end-to-end only if source assets
change — `assets/work/*.blend` are regenerated intermediates, not
versioned.

## Current status

- Body/skeleton/skin/jiggle/hair: done.
- Eyes: real 3D eyeballs + eyelids (anatomically-sized, almond-shaped,
  real-sampled skin-tone lid material), rigged for gaze/blink. One known
  residual: the lid is a separate rigged object, not continuous topology
  with the face, so a faint geometric seam remains under close inspection
  — fixing that needs an interactive sculpt/retopo pass, not more
  procedural scripting (see `blender_scripts/README.md`).
- Jaw/lips: separated into real mesh (not flat texture).
- MuJoCo locomotion: `stand` stage training in progress (healthy/stable,
  see checkpoints above); `walk_slow`/`walk` stages and Godot retargeting
  not started yet.
