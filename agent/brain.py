"""
Interface for the 5B conversational model's output, plus a mock
implementation for testing the loop without real inference.

The real version of ConversationalBrain wraps your 5B model - "linked to
the Spine and that 1.5B" per the architecture you described, meaning its
prompt should include both the user's input AND the current PAD state
(so its dialogue tone and gesture choice are consistent with the
character's ongoing emotional state, not just reactive to the latest
message). This module only defines the contract: respond() takes user
text + PAD state, returns dialogue text plus an optional gesture to fire.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Protocol

from mcu.kiara_mcu import PADState


@dataclass
class BrainOutput:
    dialogue: str
    gesture_name: Optional[str] = None
    gesture_params: Optional[dict] = None
    # the model can also propose a PAD shift of its own (e.g. the user said
    # something that should visibly affect mood) - applied on top of
    # whatever the telemetry loop is already tracking.
    pad_delta: Optional[dict] = None


class ConversationalBrain(Protocol):
    def respond(self, user_text: str, pad_state: PADState) -> BrainOutput:
        """Called once per user turn. pad_state is the character's
        CURRENT emotional state (as of the last telemetry tick) - the
        real model's prompt should include it alongside user_text so
        dialogue tone and gesture choice stay consistent with how the
        character has been "feeling" over the conversation, not just
        reactive to this one message."""
        ...


class MockBrain:
    """Stand-in for the real 5B model: simple keyword/intent matching,
    genuinely primitive compared to what real inference should do, but it
    exercises the real wire format (dialogue + fire + optional pad_delta)
    end to end. Replace with a class that calls your actual model and
    parses its structured output (tool-call style, same idea as any LLM
    function-calling response) into a BrainOutput."""

    GREETING_RE = re.compile(r"\b(hi|hello|hey|yo)\b", re.I)
    QUESTION_RE = re.compile(r"\?\s*$")
    # checked BEFORE agreement matching, and "not .{0,20}sure" (not just
    # the literal "not sure") so "not totally sure" doesn't fall through
    # to AGREE_RE just because it contains the bare word "sure".
    UNCERTAIN_RE = re.compile(r"\b(don'?t know|not\s+\w*\s*sure|maybe|dunno)\b", re.I)
    AGREE_RE = re.compile(r"\b(yes|yeah|agree|sounds good)\b|^sure\b", re.I)
    DISAGREE_RE = re.compile(r"\b(no|disagree|nah)\b", re.I)

    def respond(self, user_text: str, pad_state: PADState) -> BrainOutput:
        text = user_text.strip()

        if self.GREETING_RE.search(text):
            return BrainOutput(
                dialogue="Hey! Good to see you.",
                gesture_name="wave", gesture_params={"side": "R"},
                pad_delta={"pleasure": min(1.0, pad_state.pleasure + 0.3)},
            )
        if self.UNCERTAIN_RE.search(text):
            return BrainOutput(
                dialogue="Hm, honestly not sure - let me think about that.",
                gesture_name="shrug",
            )
        if self.AGREE_RE.search(text):
            return BrainOutput(dialogue="Right, exactly.", gesture_name="nod")
        if self.DISAGREE_RE.search(text):
            return BrainOutput(dialogue="I don't think so, actually.", gesture_name="shake_head")
        if self.QUESTION_RE.search(text):
            return BrainOutput(
                dialogue="Good question - give me a second.",
                gesture_name="head_tilt", gesture_params={"direction": 1.0},
            )

        return BrainOutput(dialogue="Mm, go on.", gesture_name="talk_beat")
