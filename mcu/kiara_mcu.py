"""
Kiara MCU - the Straygents pattern, scaled to human level.

A "virtual MCU": a registry of named, individually-fireable functions tied
to 3D body parts (bones), the same way a real microcontroller exposes
named servo channels to a higher-level brain. The brain (the 5B
conversational model, conditioned on the 1.5B telemetry model's ongoing
state) fires functions by name - exactly like a tool call - and this
module is the implementation layer that turns a symbolic action
("wave", "nod", "shrug") into an actual time-varying bone pose, modulated
by the character's current PAD emotional state, then streams the result
to Godot every tick.

Division of labor with the rest of the pipeline:
  - This MCU owns the EXPRESSIVE/UPPER-BODY bones (arms, hands, head,
    neck, spine lean) - gestures are semantic, authored, not RL-trained.
  - The MuJoCo-trained locomotion policy owns the LOWER-BODY/root motion
    (hips, knees, ankles, pelvis translation) - that's a physics problem.
  - The existing spring-bone physics (breast/belly/glute/hair jiggle)
    keeps running underneath both, driven by whatever motion the parent
    bones end up with from either system.
These three write to disjoint bone sets, so they compose without
conflict - no blending logic needed between them, just between multiple
MCU functions that might want the SAME bone at once (handled below).
"""

from __future__ import annotations
import time
import math
from dataclasses import dataclass, field
from typing import Callable, Optional


# ---------------------------------------------------------------------
# PAD emotional state (Pleasure-Arousal-Dominance, Mehrabian & Russell).
# This is the shared state the 1.5B telemetry loop updates continuously
# and the 5B conversational model reads/sets alongside dialogue output.
# ---------------------------------------------------------------------
@dataclass
class PADState:
    pleasure: float = 0.0     # -1 (distressed) .. +1 (content)
    arousal: float = 0.0      # -1 (calm/sleepy) .. +1 (excited/alert)
    dominance: float = 0.0    # -1 (submissive/timid) .. +1 (confident/assertive)

    def clamp(self) -> None:
        self.pleasure = max(-1.0, min(1.0, self.pleasure))
        self.arousal = max(-1.0, min(1.0, self.arousal))
        self.dominance = max(-1.0, min(1.0, self.dominance))

    # amplitude/speed scaling derived from PAD - used by every gesture so
    # the SAME "wave" function reads as excited-big or subdued-small
    # depending on emotional state, without needing separate gesture
    # variants per mood.
    @property
    def amplitude_scale(self) -> float:
        # high arousal + high dominance = bigger, more expansive motion
        return 0.55 + 0.45 * max(0.0, (self.arousal + self.dominance) / 2.0 + 0.5)

    @property
    def speed_scale(self) -> float:
        # high arousal = faster movement, independent of amplitude
        return 0.6 + 0.6 * max(0.0, self.arousal * 0.5 + 0.5)

    @property
    def posture_lean(self) -> float:
        # baseline spine pitch: low pleasure/dominance -> slump forward,
        # high dominance -> lean back/upright. Range roughly -15..+8 deg.
        return self.dominance * 8.0 - max(0.0, -self.pleasure) * 15.0


# A single bone's target rotation as Euler degrees (x, y, z), matching
# the convention used in the Blender rig build scripts.
BonePose = dict[str, tuple[float, float, float]]


@dataclass
class PartFunction:
    """One brain-fireable behavior: a named pose-generator over time."""
    name: str
    category: str                        # "gesture" | "posture" | "idle"
    bones: list[str]                      # which bones this writes to
    duration: float                       # seconds, 0 = holds until replaced (postures)
    curve: Callable[[float, dict], BonePose]
    # curve(t_normalized 0..1, params) -> {bone_name: (x_deg,y_deg,z_deg)}
    loopable: bool = False
    description: str = ""


@dataclass
class _ActiveCall:
    fn: PartFunction
    start_time: float
    params: dict
    weight: float = 1.0


class KiaraMCU:
    def __init__(self) -> None:
        self.registry: dict[str, PartFunction] = {}
        self.pad = PADState()
        self._active: dict[str, _ActiveCall] = {}   # keyed by category ("gesture" slot, "posture" slot, ...)
        self._slot_for_bone: dict[str, str] = {}     # bone -> which active-call key currently owns it
        self._t0 = time.monotonic()

    # -- registration --------------------------------------------------
    def register(self, fn: PartFunction) -> None:
        self.registry[fn.name] = fn

    # -- brain-facing API ------------------------------------------------
    def update_pad(self, pleasure: Optional[float] = None,
                    arousal: Optional[float] = None,
                    dominance: Optional[float] = None) -> None:
        if pleasure is not None:
            self.pad.pleasure = pleasure
        if arousal is not None:
            self.pad.arousal = arousal
        if dominance is not None:
            self.pad.dominance = dominance
        self.pad.clamp()

    def fire(self, name: str, **params) -> bool:
        """Fire a function by name - this is what the brain's tool-call
        output invokes. Returns False if the name isn't registered."""
        fn = self.registry.get(name)
        if fn is None:
            return False
        slot = f"{fn.category}:{','.join(sorted(fn.bones))}"
        self._active[slot] = _ActiveCall(fn=fn, start_time=time.monotonic(), params=params)
        return True

    def list_functions(self) -> list[dict]:
        return [
            {"name": f.name, "category": f.category, "bones": f.bones,
             "duration": f.duration, "loopable": f.loopable, "description": f.description}
            for f in self.registry.values()
        ]

    # -- per-tick evaluation ---------------------------------------------
    def tick(self) -> BonePose:
        """Evaluate all active functions at the current time, blend by
        slot ownership, and return the combined bone pose to send to
        Godot this frame."""
        now = time.monotonic()
        out: BonePose = {}
        expired = []

        for slot, call in self._active.items():
            elapsed = now - call.start_time
            fn = call.fn
            if fn.duration > 0 and elapsed >= fn.duration:
                if fn.loopable:
                    elapsed = elapsed % fn.duration
                else:
                    expired.append(slot)
                    continue
            t_norm = 0.0 if fn.duration <= 0 else min(1.0, elapsed / fn.duration)

            params = dict(call.params)
            params["pad"] = self.pad
            params["amplitude_scale"] = self.pad.amplitude_scale
            params["speed_scale"] = self.pad.speed_scale

            pose = fn.curve(t_norm, params)
            for bone, rot in pose.items():
                out[bone] = rot

        for slot in expired:
            del self._active[slot]

        return out


def ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))
