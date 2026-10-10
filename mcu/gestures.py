"""
Concrete gesture/posture functions for the Kiara MCU, built on empirically
verified local bone-axis conventions (see the axis-probe check that
preceded this file - Blender's auto-roll doesn't give a convention you
can assume, it has to be measured per bone orientation).

Convention, confirmed by rotating each axis 40deg and watching which way
the bone's tail actually moves:
  - Local Y is ALWAYS the bone's own head-to-tail axis (true for any
    bone by Blender's edit-bone definition), so it never moves the tail
    itself - but it's far from a no-op: for a VERTICAL bone (head, neck,
    spine) that's the YAW axis (turning the whole head/chest left-right),
    for a HORIZONTAL bone (upperarm, forearm) it's twist (pronation/
    supination). The "zero tail delta" only means "look at orientation,
    not position" for that axis.
  - Head/neck (vertical bones): X = nod (pitch), Y = yaw (turn), Z = tilt
    (lateral bend).
  - Arms (horizontal-rest bones): X = raise/lower (same sign both
    sides), Z = forward/back swing (sign FLIPS between L/R - R's
    positive Z swings forward, L's positive Z swings backward, because
    of how the mirrored bone geometry was built).
"""

from kiara_mcu import PartFunction, ease_in_out
import math

FORWARD_SIGN = {"L": -1.0, "R": 1.0}   # sign on arm axis-Z for "swing forward"
RAISE_SIGN = {"L": 1.0, "R": 1.0}      # sign on arm axis-X for "raise up"


def _lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------------
# Gestures (finite duration, non-looping unless noted)
# ---------------------------------------------------------------------

def _wave_curve(t, params):
    side = params.get("side", "R")
    amp = params["amplitude_scale"]
    speed = params["speed_scale"]
    fs = FORWARD_SIGN[side]

    raise_amt = _lerp(0.0, 95.0, ease_in_out(min(1.0, t * 4)))      # quick raise
    settle = ease_in_out(min(1.0, max(0.0, (t - 0.85) * 6)))         # quick lower at the end
    raise_amt = _lerp(raise_amt, 20.0, settle)

    wag_cycles = 4 * speed
    wag = math.sin(t * math.pi * 2 * wag_cycles) * 18.0 * amp if 0.1 < t < 0.85 else 0.0

    return {
        f"upperarm.{side}": (RAISE_SIGN[side] * raise_amt, 0.0, fs * -10.0),
        f"forearm.{side}": (0.0, 0.0, 0.0),
        f"hand.{side}": (0.0, wag, 0.0),
    }


WAVE = PartFunction(
    name="wave", category="gesture", bones=["upperarm.R", "forearm.R", "hand.R"],
    duration=2.2, curve=_wave_curve, description="Raise hand and wave side to side (greeting).",
)


def _nod_curve(t, params):
    amp = params["amplitude_scale"]
    cycles = params.get("cycles", 2)
    angle = math.sin(t * math.pi * 2 * cycles) * 14.0 * amp * math.sin(t * math.pi)
    return {"head": (angle, 0.0, 0.0)}


NOD = PartFunction(
    name="nod", category="gesture", bones=["head"],
    duration=1.4, curve=_nod_curve, description="Nod head (agreement/yes).",
)


def _shake_head_curve(t, params):
    amp = params["amplitude_scale"]
    cycles = params.get("cycles", 2.5)
    angle = math.sin(t * math.pi * 2 * cycles) * 18.0 * amp * math.sin(t * math.pi)
    return {"head": (0.0, angle, 0.0)}


SHAKE_HEAD = PartFunction(
    name="shake_head", category="gesture", bones=["head"],
    duration=1.6, curve=_shake_head_curve, description="Shake head side to side (disagreement/no).",
)


def _head_tilt_curve(t, params):
    direction = params.get("direction", 1.0)  # +1 right, -1 left
    hold = ease_in_out(min(1.0, t * 3)) * (1.0 - ease_in_out(max(0.0, (t - 0.7) * 3.3)))
    return {"head": (3.0 * hold, 0.0, direction * 16.0 * hold)}


HEAD_TILT = PartFunction(
    name="head_tilt", category="gesture", bones=["head"],
    duration=1.8, curve=_head_tilt_curve, description="Tilt head (curious/listening).",
)


def _shrug_curve(t, params):
    amp = params["amplitude_scale"]
    hold = ease_in_out(min(1.0, t * 3)) * (1.0 - ease_in_out(max(0.0, (t - 0.6) * 2.5)))
    raise_amt = 22.0 * amp * hold
    return {
        "clavicle.L": (0.0, 0.0, -raise_amt),
        "clavicle.R": (0.0, 0.0, raise_amt),
        "upperarm.L": (raise_amt * 0.3, 0.0, FORWARD_SIGN["L"] * raise_amt * 0.2),
        "upperarm.R": (raise_amt * 0.3, 0.0, FORWARD_SIGN["R"] * raise_amt * 0.2),
        "head": (raise_amt * 0.15, 0.0, 0.0),
    }


SHRUG = PartFunction(
    name="shrug", category="gesture", bones=["clavicle.L", "clavicle.R", "upperarm.L", "upperarm.R", "head"],
    duration=1.4, curve=_shrug_curve, description="Shrug shoulders (uncertain/don't know).",
)


def _point_curve(t, params):
    side = params.get("side", "R")
    fs = FORWARD_SIGN[side]
    extend = ease_in_out(min(1.0, t * 3)) * (1.0 - ease_in_out(max(0.0, (t - 0.75) * 4)))
    return {
        f"upperarm.{side}": (RAISE_SIGN[side] * 10.0 * extend, 0.0, fs * 75.0 * extend),
        f"forearm.{side}": (0.0, 0.0, 0.0),
        f"hand.{side}": (0.0, 0.0, 0.0),
    }


POINT = PartFunction(
    name="point", category="gesture", bones=["upperarm.R", "forearm.R", "hand.R"],
    duration=1.6, curve=_point_curve, description="Point forward/at something.",
)


def _cross_arms_curve(t, params):
    hold = ease_in_out(min(1.0, t * 2.5))
    return {
        "upperarm.L": (RAISE_SIGN["L"] * 15.0 * hold, 20.0 * hold, FORWARD_SIGN["L"] * -60.0 * hold),
        "upperarm.R": (RAISE_SIGN["R"] * 15.0 * hold, -20.0 * hold, FORWARD_SIGN["R"] * -60.0 * hold),
        "forearm.L": (0.0, 0.0, -90.0 * hold),
        "forearm.R": (0.0, 0.0, 90.0 * hold),
    }


CROSS_ARMS = PartFunction(
    name="cross_arms", category="posture", bones=["upperarm.L", "upperarm.R", "forearm.L", "forearm.R"],
    duration=0.0, curve=_cross_arms_curve, description="Hold arms crossed (closed-off/defensive posture).",
)


# ---------------------------------------------------------------------
# Idle/ambient (looping, low amplitude - always-on "alive" behaviors)
# ---------------------------------------------------------------------

def _idle_breathe_curve(t, params):
    amp = params["amplitude_scale"]
    # breathing period independent of gesture speed_scale - should stay
    # roughly physiological (~4s per cycle at rest) regardless of mood,
    # arousal affects amplitude/rate only mildly
    rate = 0.22 + 0.1 * params["pad"].arousal
    angle = math.sin(t * math.pi * 2 * rate * 4) * 2.5 * (0.6 + 0.4 * amp)
    return {"spine_T6": (angle, 0.0, 0.0)}


IDLE_BREATHE = PartFunction(
    name="idle_breathe", category="idle", bones=["spine_T6"],
    duration=4.0, curve=_idle_breathe_curve, loopable=True,
    description="Continuous subtle breathing motion.",
)


def _idle_sway_curve(t, params):
    amp = params["amplitude_scale"]
    angle = math.sin(t * math.pi * 2) * 2.0 * (0.5 + 0.5 * amp)
    return {"spine_L3": (0.0, 0.0, angle)}


IDLE_SWAY = PartFunction(
    name="idle_sway", category="idle", bones=["spine_L3"],
    duration=6.0, curve=_idle_sway_curve, loopable=True,
    description="Continuous subtle weight-shift sway.",
)


def _talk_beat_curve(t, params):
    side = params.get("side", "R")
    amp = params["amplitude_scale"]
    fs = FORWARD_SIGN[side]
    pulse = max(0.0, math.sin(t * math.pi * 2 * 1.8)) ** 2
    return {
        f"upperarm.{side}": (RAISE_SIGN[side] * 8.0 * pulse * amp, 0.0, fs * 15.0 * pulse * amp),
        f"forearm.{side}": (0.0, 0.0, 12.0 * pulse * amp),
    }


TALK_BEAT = PartFunction(
    name="talk_beat", category="gesture", bones=["upperarm.R", "forearm.R"],
    duration=0.6, curve=_talk_beat_curve, loopable=True,
    description="Small rhythmic hand gesture while speaking.",
)


ALL_FUNCTIONS = [
    WAVE, NOD, SHAKE_HEAD, HEAD_TILT, SHRUG, POINT, CROSS_ARMS,
    IDLE_BREATHE, IDLE_SWAY, TALK_BEAT,
]
