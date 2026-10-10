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

## Easiest start: install + shortcuts

**Windows:** double-click `install.bat`. It creates a Python virtual
environment under `mujoco/venv`, installs the RL dependencies, checks
whether Godot is on your PATH (tells you where to get it if not —
https://godotengine.org/download), and adds two Desktop shortcuts:
*"Kiara (Godot)"* and *"Kiara (Train MuJoCo)"* (the latter asks which
task — locomotion or reach/grasp — and auto-resumes from the included
checkpoint if one's present). Nothing is installed system-wide or needs
admin rights — it all runs in place out of wherever you unzipped this.

**macOS/Linux:** run `./install.sh` once, then `./launch_godot.sh` /
`./launch_mujoco.sh` directly (no desktop-icon step — those vary too
much by distro to do generically; drag the scripts into a dock/launcher
by hand if you want icons).

Everything below describes what those scripts are doing, for running
things by hand instead.

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
   - A `DirectionalLight3D` + sky `WorldEnvironment` and a ground plane
     were added this pass too — the previous scene had neither a camera
     nor a light, so running it showed nothing.

## Controls

She's driven by a single shared `BodyIntent` autoload that any input
source writes into, and `LocomotionController` (on the `CharacterBody3D`
root) reads from — whichever source wrote most recently wins, with no
central mode switch to get wrong.

**Xbox controller** (`GamepadController`, GTA/Rockstar on-foot layout,
polled directly — no gamepad plugged in required, it just stays idle):
| Input | Action |
|---|---|
| Left stick | Move (push past ~85% for a run) |
| Right stick | Camera orbit |
| A | Jump |
| X (hold) | Sprint |
| B | Crouch |
| Y | Wave gesture |
| RT / LT | Grab/interact, right/left hand |

**Mouse / touchscreen** (`TouchInteraction`):
- Click-drag on her = **caress** — a skin-only gesture (`has_skin` on the
  root controller; robots elsewhere in Straygents set this `false` and
  simply never receive it) that reports the stroke's measured speed, so
  a slow drag and a fast swipe can read as different things later.
- **Double-tap and hold** = **grab** — picks her up; dragging while held
  translates/rotates her freely. Releasing re-anchors her at wherever the
  release point raycasts to ("the second click always grabs whatever
  place it landed on").

**When nobody's driving** (`AutonomyDriver`): after 2.5s of silence from
both input sources, she takes over her own movement with a gentle
wander/pause idle loop — not a brain, just a reflex so she's never a
statue. A real decision-making layer (goals, PAD-driven behavior) plugs
in at the same `BodyIntent` point later without touching this script.

**Learning her body from the controller** (`TeleopRecorder` +
`mujoco/teleop_to_commands.py`): while you're actively driving her,
every sample of (stick input, resulting root motion) is logged to
`user://teleop_log.jsonl`. Run `teleop_to_commands.py` on that log to
get a summarized (speed, heading) command trajectory. Wiring that
trajectory into MuJoCo training as a time-varying target (instead of
the fixed scalar `target_speed` stages use now) is the next step — see
the docstrings in both files for exactly what's done vs. not yet.

## Quick start: MuJoCo (locomotion + reach/grasp)

```
cd mujoco
pip install -r requirements.txt
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

**Reach/grasp** ("see and grab things"):
```
python3 train_reach_grasp.py --timesteps 3000000 --n-envs 4
```
- `kiara_reach_grasp.xml` — `kiara_humanoid.xml` plus one free-floating
  target sphere, randomized within right-arm reach each episode.
- `reach_grasp_env.py` — right arm only (pelvis is kinematically pinned
  so this trains reaching, not balance — combining the two is a later
  curriculum stage once both are solid independently). Two deliberate
  stand-ins, spelled out in the module docstring: "seeing" is the
  target's true position fed into the observation (not a camera/pixel
  pipeline — that's the separate, still-pending vision-language task),
  and "grasping" is sustained hand-to-target proximity + low relative
  speed (the hands are bare capsules with no fingers in the MJCF yet, so
  there's nothing to actually close around the object — adding actuated
  fingers is the next step toward a real grasp, and this reward
  structure already expects that extra DOF rather than needing a
  redesign).
- Also training in background now, alongside `stand` — sharing this
  machine's 4 CPU cores across both means each one progresses slower
  than it would alone; that's an acceptable trade for having both moving
  rather than sequencing them.

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
- MuJoCo reach/grasp: training in progress, reach-only reward shaping
  (see Controls section above for what's a stand-in vs. real).
- Godot controls: gamepad (GTA on-foot layout), mouse/touch grab + skin
  caress, idle autonomy, and teleop logging are all wired and smoke-
  tested (ran the full scene headless with no script errors). Not yet
  tested with an actual physical gamepad or on a touchscreen device —
  only verified by code review + a headless no-input run.
