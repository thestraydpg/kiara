"""
End-to-end demo of the agent loop: starts the MCU server, runs the mock
telemetry loop and mock brain as separate socket CLIENTS (matching how
the real 1.5B/5B models would run as separate processes), and drives a
scripted mock conversation so you can see PAD state drift and gestures
fire in response before any real model is wired in.

    python3 agent/run_loop.py
"""

from __future__ import annotations
import json
import os
import socket
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcu"))

from mcu.kiara_mcu import KiaraMCU, PADState
from mcu.gestures import ALL_FUNCTIONS
from mcu.server import MCUServer
from agent.pad_controller import TelemetryLoop, MockTelemetrySource
from agent.brain import MockBrain


class MCUClient:
    """Minimal socket client matching the protocol in mcu/server.py -
    this is the pattern your real 1.5B/5B processes would use to talk to
    the MCU over the network (or localhost) rather than importing it
    directly."""

    def __init__(self, host="127.0.0.1", port=8765):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

    def send(self, obj: dict) -> None:
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def fire(self, name: str, **params) -> None:
        self.send({"type": "fire", "name": name, "params": params})

    def set_pad(self, delta) -> None:
        msg = {"type": "pad"}
        if delta.pleasure is not None:
            msg["pleasure"] = delta.pleasure
        if delta.arousal is not None:
            msg["arousal"] = delta.arousal
        if delta.dominance is not None:
            msg["dominance"] = delta.dominance
        self.send(msg)

    def close(self) -> None:
        self.sock.close()


SCRIPTED_CONVERSATION = [
    "Hey Kiara!",
    "What do you think about this plan?",
    "I'm not totally sure it'll work though.",
    "Yeah, I agree, let's go with it.",
]


def main() -> None:
    mcu = KiaraMCU()
    for fn in ALL_FUNCTIONS:
        mcu.register(fn)
    server = MCUServer(mcu)
    server.start()
    time.sleep(0.5)  # let the listener bind

    telemetry_client = MCUClient()
    brain_client = MCUClient()
    time.sleep(0.2)

    telemetry_source = MockTelemetrySource(seed=42)
    telemetry_loop = TelemetryLoop(telemetry_source, on_update=telemetry_client.set_pad, tick_hz=4.0)
    t = threading.Thread(target=telemetry_loop.run_forever, daemon=True)
    t.start()

    brain = MockBrain()
    print("--- scripted conversation ---")
    for user_text in SCRIPTED_CONVERSATION:
        time.sleep(1.5)  # let telemetry drift a bit between turns
        current_pad = PADState(mcu.pad.pleasure, mcu.pad.arousal, mcu.pad.dominance)
        print(f"\nuser: {user_text}")
        print(f"  [PAD at this turn: pleasure={current_pad.pleasure:.2f} "
              f"arousal={current_pad.arousal:.2f} dominance={current_pad.dominance:.2f}]")
        out = brain.respond(user_text, current_pad)
        print(f"kiara: {out.dialogue}")
        if out.gesture_name:
            brain_client.fire(out.gesture_name, **(out.gesture_params or {}))
            print(f"  [fired gesture: {out.gesture_name}]")
        if out.pad_delta:
            brain_client.send({"type": "pad", **out.pad_delta})
            print(f"  [brain-driven PAD shift: {out.pad_delta}]")

    time.sleep(1.0)
    telemetry_loop.stop()
    print("\n--- conversation complete ---")


if __name__ == "__main__":
    main()
