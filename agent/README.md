# Kiara agent-loop architecture

This is the connective layer between the two-model brain you described and
the MCU/body built in `mcu/` and `godot/`. Neither of your actual models
(the 1.5B telemetry loop, the 5B conversational model) is wired in here —
that requires your model weights and inference stack, which this sandbox
doesn't have. What's here is the **exact interface contract** both models
need to satisfy, plus a working stub implementation of each so the full
loop is testable end-to-end right now. Swap the stubs for real inference
and nothing else in the pipeline needs to change.

## The two loops, and how they talk to the body

```
┌─────────────────────┐        ┌──────────────────────┐
│   1.5B telemetry     │        │   5B conversational    │
│   (screen, emotion,   │──PAD──▶│   (spine + 1.5B input, │
│   context - runs      │ state  │   synthesizes user      │
│   continuously)        │◀──────│   input + emotion)       │
└──────────┬───────────┘        └───────────┬───────────┘
           │                                 │
           │  {"type":"pad", ...}            │ {"type":"fire", "name":..., "params":...}
           ▼                                 ▼
                    mcu/server.py (TCP, port 8765)
                                │
                                ▼
                    godot/scripts/mcu_bridge.gd
                                │
                                ▼
                 live Skeleton3D bone poses (gestures/posture)
```

The MuJoCo-trained locomotion policy (`mujoco/`) is a **separate** system
that drives the lower-body/root bones directly in Godot once task 12's
retargeting is built - it doesn't go through the MCU at all, since it's a
continuous physics controller, not a discrete fireable function. The two
systems never touch the same bones, so they run concurrently without
conflict.

## Contract: what the 1.5B telemetry loop must produce

Once per tick (suggested: 2-10 Hz - PAD state shouldn't change faster
than emotional state plausibly does), send one message on the MCU socket:

```json
{"type": "pad", "pleasure": -1.0..1.0, "arousal": -1.0..1.0, "dominance": -1.0..1.0}
```

Only include the keys that changed if you want partial updates - see
`PADState` in `mcu/kiara_mcu.py`, all three are optional per-message.

`pad_controller.py` in this directory defines `TelemetrySource`, the
interface your 1.5B model's output should implement: a `sense() -> PADDelta`
method called once per tick. The stub (`MockTelemetrySource`) generates a
slow random walk so the loop is testable without real sensing.

## Contract: what the 5B conversational model must produce

On each user turn, alongside its dialogue text, the model should decide
whether a gesture fits the moment and fire it:

```json
{"type": "fire", "name": "wave", "params": {"side": "R"}}
```

`name` must match a registered function in `mcu/gestures.py`'s registry
(call `{"type": "list_functions"}` on the socket to get the live list with
descriptions - this is what you'd feed the 5B model as its available
"tools", exactly like Claude/GPT tool-calling). Params are gesture-specific
(e.g. `side` for one-armed gestures, `direction` for `head_tilt`).

`brain.py` defines `ConversationalBrain`, the interface your 5B model's
output should implement: a `respond(user_text, pad_state) -> BrainOutput`
method returning `(dialogue_text, gesture_name_or_None, gesture_params)`.
The stub (`MockBrain`) does simple keyword/intent matching (question →
head_tilt, greeting → wave, uncertainty → shrug) so the loop is testable
without real inference - genuinely primitive compared to what the actual
5B model should do, but it exercises the real wire format end to end.

## Running the demo

```
python3 agent/run_loop.py
```

Starts the MCU server, the mock telemetry loop, and a scripted mock
"conversation" - watch the PAD state drift and gestures fire in response,
confirming the whole pipe (telemetry → PAD → MCU → Godot bridge) works
before you plug in real models.
