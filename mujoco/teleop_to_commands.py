"""
Converts a Godot TeleopRecorder session log (JSONL of controller input +
resulting root motion, written to user://teleop_log.jsonl - see
godot/scripts/teleop_recorder.gd) into a command trajectory: a sequence
of (duration, target_speed, target_heading) segments describing how a
real session actually moved her.

This is the capture->summarize half of "she learns her body from how I
move the controller". What's NOT done yet, and is the honest next step:
locomotion_env.py's target_speed is currently a single fixed constant
per training stage - wiring it to replay a command trajectory like the
one this script produces (so PPO is rewarded for matching a REAL
recorded session's speed/heading profile instead of one flat number)
needs a small addition to KiaraLocomotionEnv (an optional schedule
param), which is a clean, additive change but hasn't been made in this
pass to avoid touching the environment the in-progress `stand` training
run is actively using.

Usage:
    # copy the log off the machine running Godot first, e.g.:
    #   cp "%APPDATA%\\Godot\\app_userdata\\Kiara\\teleop_log.jsonl" .
    python3 teleop_to_commands.py teleop_log.jsonl commands.json
"""

from __future__ import annotations
import json
import sys
import math

WINDOW_SECONDS = 1.0  # average input/motion over this long per command segment


def load_log(path: str) -> list[dict]:
    samples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def summarize(samples: list[dict]) -> list[dict]:
    if not samples:
        return []
    segments = []
    window: list[dict] = []
    window_start_t = samples[0]["t"]

    def flush(end_t: float):
        if not window:
            return
        speeds = [math.hypot(s["state"]["vel"][0], s["state"]["vel"][2]) for s in window]
        headings = [s["state"]["yaw"] for s in window]
        avg_speed = sum(speeds) / len(speeds)
        # circular mean for heading, since yaw wraps at +-pi
        sin_sum = sum(math.sin(h) for h in headings)
        cos_sum = sum(math.cos(h) for h in headings)
        avg_heading = math.atan2(sin_sum, cos_sum)
        segments.append({
            "duration": round(end_t - window_start_t, 3),
            "target_speed": round(avg_speed, 3),
            "target_heading": round(avg_heading, 3),
        })

    for s in samples:
        if s["t"] - window_start_t >= WINDOW_SECONDS:
            flush(s["t"])
            window = []
            window_start_t = s["t"]
        window.append(s)
    flush(samples[-1]["t"])
    return segments


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    samples = load_log(sys.argv[1])
    segments = summarize(samples)
    with open(sys.argv[2], "w") as f:
        json.dump(segments, f, indent=2)
    print(f"Read {len(samples)} samples, wrote {len(segments)} command segments to {sys.argv[2]}")


if __name__ == "__main__":
    main()
