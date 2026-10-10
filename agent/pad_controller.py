"""
Interface for the 1.5B telemetry model's output, plus a mock
implementation for testing the loop without real inference.

The real version of TelemetrySource wraps whatever your 1.5B model
produces each tick (screen read, detected user emotion, situational
context) and reduces it to a PAD delta. This module doesn't care HOW
that happens - it only defines the contract: sense() returns a PADDelta,
called on a fixed interval by AgentLoop.
"""

from __future__ import annotations
import random
import time
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class PADDelta:
    """Partial PAD update - any field left None is unchanged this tick."""
    pleasure: Optional[float] = None
    arousal: Optional[float] = None
    dominance: Optional[float] = None


class TelemetrySource(Protocol):
    def sense(self) -> PADDelta:
        """Called once per telemetry tick. Return the PAD delta to apply.
        Implementations should run their own model inference here (or in
        a background thread and just return the latest cached result -
        this must not block the tick loop for long)."""
        ...


class MockTelemetrySource:
    """Stand-in for the real 1.5B model: a slow bounded random walk, so
    the rest of the pipeline is testable without real sensing. Replace
    with a class that calls your actual model."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._p, self._a, self._d = 0.0, 0.0, 0.0

    def sense(self) -> PADDelta:
        step = 0.04
        self._p = max(-1.0, min(1.0, self._p + self._rng.uniform(-step, step)))
        self._a = max(-1.0, min(1.0, self._a + self._rng.uniform(-step, step)))
        self._d = max(-1.0, min(1.0, self._d + self._rng.uniform(-step, step)))
        return PADDelta(pleasure=self._p, arousal=self._a, dominance=self._d)


class TelemetryLoop:
    """Drives a TelemetrySource on a fixed interval and reports deltas via
    a callback - this is what you run continuously (its own thread/
    process) alongside the conversational turn-based brain."""

    def __init__(self, source: TelemetrySource, on_update, tick_hz: float = 4.0):
        self.source = source
        self.on_update = on_update
        self.tick_interval = 1.0 / tick_hz
        self._running = False

    def run_forever(self) -> None:
        self._running = True
        while self._running:
            t0 = time.monotonic()
            delta = self.source.sense()
            self.on_update(delta)
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, self.tick_interval - elapsed))

    def stop(self) -> None:
        self._running = False
