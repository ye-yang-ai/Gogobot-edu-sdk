"""Run a timed movement sequence over WebSocket control_raw.

Purpose:
    Demonstrate forward, right, back, left, and step movement over WebSocket.
Risk level:
    Medium. The robot will walk in multiple directions.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/03_movement/websocket/ws_timed_move.py --duration 2 --yes
Expected result:
    The robot performs each direction and stops between commands.
Exit:
    Wait for completion, or press Ctrl+C. The script sends STOP in cleanup.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, DevPcWebSocketHost
from ws_directional_move import MOVEMENTS, require_confirmation, wait_status_ready


SEQUENCE = ["forward", "right", "back", "left", "step"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WebSocket timed movement sequence")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--duration", type=float, default=2.0, help="duration per direction")
    parser.add_argument("--pause", type=float, default=1.0, help="pause between directions")
    parser.add_argument("--timeout", type=float, default=30.0, help="connection/status wait timeout")
    parser.add_argument("--settle", type=float, default=0.6, help="delay after status ready before sending")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    require_confirmation(args.yes)
    dog = AiDog()
    host = DevPcWebSocketHost(host=args.bind, port=args.port, dog=dog)
    dog.attach_ws_control(host)
    try:
        host.start()
        print(f"[host] listening ws://{args.bind}:{args.port}; waiting for robot")
        if not host.wait_robot_connected(timeout_s=args.timeout):
            print("[host] timeout waiting for robot")
            return 1
        print("[host] robot connected")
        if not wait_status_ready(dog, timeout_s=args.timeout):
            print("[ready] timeout waiting for status JSON")
            return 1
        if args.settle > 0:
            time.sleep(args.settle)

        for direction in SEQUENCE:
            print(f"[movement] {direction} for {args.duration:.1f}s")
            movement = MOVEMENTS[direction]
            if movement is None:
                raise ValueError(f"Unsupported movement direction: {direction}")
            dog.send_movement(movement, transport="ws")
            time.sleep(max(0.0, args.duration))
            dog.stop_movement(transport="ws")
            time.sleep(max(0.0, args.pause))
        print("[movement] sequence complete")
        return 0
    except KeyboardInterrupt:
        print("\n[host] interrupted")
        return 130
    finally:
        try:
            if host.is_robot_connected:
                dog.stop_movement(transport="ws")
        except Exception:
            pass
        host.stop()


if __name__ == "__main__":
    raise SystemExit(main())
