"""
TCP server wrapping the Kiara MCU: broadcasts the current blended bone
pose as newline-delimited JSON to any connected client (Godot), and
accepts newline-delimited JSON commands back (fire/update_pad) - this is
the actual wire between the Python "brain" process and the Godot "body".

Protocol (both directions, one JSON object per line):
  Server -> Godot, every tick:
    {"type": "pose", "bones": {"head": [x,y,z], ...}}
  Godot/brain -> Server:
    {"type": "fire", "name": "wave", "params": {"side": "R"}}
    {"type": "pad", "pleasure": 0.3, "arousal": 0.6, "dominance": 0.1}
    {"type": "list_functions"}   -> server replies {"type": "functions", "functions": [...]}

Run standalone for manual testing:
    python3 server.py --port 8765
"""

from __future__ import annotations
import argparse
import json
import socket
import threading
import time

from kiara_mcu import KiaraMCU
from gestures import ALL_FUNCTIONS


class MCUServer:
    def __init__(self, mcu: KiaraMCU, host: str = "127.0.0.1", port: int = 8765, tick_hz: float = 30.0):
        self.mcu = mcu
        self.host = host
        self.port = port
        self.tick_interval = 1.0 / tick_hz
        self._clients: list[socket.socket] = []
        self._clients_lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._tick_loop, daemon=True).start()
        # always keep the idle behaviors running
        self.mcu.fire("idle_breathe")
        self.mcu.fire("idle_sway")

    def stop(self) -> None:
        self._running = False

    def _accept_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(4)
        print(f"[MCUServer] listening on {self.host}:{self.port}")
        while self._running:
            try:
                conn, addr = srv.accept()
            except OSError:
                break
            print(f"[MCUServer] client connected: {addr}")
            with self._clients_lock:
                self._clients.append(conn)
            threading.Thread(target=self._client_read_loop, args=(conn,), daemon=True).start()

    def _client_read_loop(self, conn: socket.socket) -> None:
        buf = b""
        try:
            while self._running:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        self._handle_message(line)
        except (ConnectionResetError, OSError):
            pass
        finally:
            with self._clients_lock:
                if conn in self._clients:
                    self._clients.remove(conn)
            conn.close()

    def _handle_message(self, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return
        msg_type = msg.get("type")
        if msg_type == "fire":
            ok = self.mcu.fire(msg["name"], **msg.get("params", {}))
            if not ok:
                print(f"[MCUServer] unknown function fired: {msg.get('name')!r}")
        elif msg_type == "pad":
            self.mcu.update_pad(
                pleasure=msg.get("pleasure"),
                arousal=msg.get("arousal"),
                dominance=msg.get("dominance"),
            )
        elif msg_type == "list_functions":
            self._broadcast({"type": "functions", "functions": self.mcu.list_functions()})

    def _tick_loop(self) -> None:
        while self._running:
            t0 = time.monotonic()
            pose = self.mcu.tick()
            if pose:
                self._broadcast({"type": "pose", "bones": {k: list(v) for k, v in pose.items()}})
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, self.tick_interval - elapsed))

    def _broadcast(self, obj: dict) -> None:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        with self._clients_lock:
            dead = []
            for c in self._clients:
                try:
                    c.sendall(data)
                except OSError:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    mcu = KiaraMCU()
    for fn in ALL_FUNCTIONS:
        mcu.register(fn)

    server = MCUServer(mcu, port=args.port)
    server.start()
    print("[MCUServer] running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
