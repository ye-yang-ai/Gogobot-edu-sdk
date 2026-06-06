"""Run one directional movement command over WebSocket control_raw.

Purpose:
    Verify WebSocket mode=0x01 movement uses the same SPORT packet as BLE.
Risk level:
    Medium. The robot will walk or step.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/03_movement/websocket/ws_directional_move.py --direction forward --duration 2 --yes
Expected result:
    The robot moves in the selected direction and then stops.
Exit:
    Wait for the duration to finish, or press Ctrl+C. The script sends STOP in cleanup.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
import time
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, DevPcWebSocketHost, Movement


DIRECTION_TO_STATE = {
    "forward": 0,
    "back": 1,
    "step": 2,
    "right": 3,
    "left": 4,
    "stop": 5,
}
MOVEMENTS = {
    "forward": Movement.FORWARD,
    "back": Movement.BACK,
    "left": Movement.LEFT,
    "right": Movement.RIGHT,
    "step": Movement.STEP,
    "stop": None,
}


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This example moves the robot. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def build_movement_packet(direction: str) -> list[int]:
    if direction not in DIRECTION_TO_STATE:
        raise ValueError(f"Unsupported direction: {direction}")
    data = [1, DIRECTION_TO_STATE[direction]]
    data.extend([100 & 0xFF])
    data.extend([0, 0])
    data.extend([0, 0])
    data.extend([0, 0])
    data.extend([500 >> 8, 500 & 0xFF])
    data.extend([75 & 0xFF])
    data.extend([35 & 0xFF])
    data.extend(struct.pack("<f", 0.5))
    data.extend(struct.pack("<f", 0.5))
    data.extend(struct.pack("<f", 0.01))
    data.extend(struct.pack("<f", 8.0))
    data.extend(struct.pack("<f", 5.0))
    data.extend([0])
    data.extend(struct.pack("<f", 0.5))
    data.extend(struct.pack("<f", math.radians(0)))
    data.extend(struct.pack("<f", math.radians(180)))
    data.extend(struct.pack("<f", math.radians(180)))
    data.extend(struct.pack("<f", math.radians(0)))
    return [int(x) & 0xFF for x in data]


def get_interaction_status(dog: AiDog) -> tuple[int, Optional[int]]:
    with dog._notify_lock:
        return dog._interaction_status_notify_seq, dog._last_interaction_task_status


def wait_status_ready(dog: AiDog, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.1, float(timeout_s))
    while time.time() < deadline:
        seq, _ = get_interaction_status(dog)
        if seq > 0:
            return True
        time.sleep(0.2)
    return False


def send_movement(dog: AiDog, direction: str) -> None:
    if direction == "stop":
        dog.stop_movement(transport="ws")
    else:
        movement = MOVEMENTS[direction]
        if movement is None:
            raise ValueError(f"Unsupported movement direction: {direction}")
        dog.send_movement(movement, transport="ws")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one WebSocket directional movement")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--direction", choices=sorted(MOVEMENTS), default="forward")
    parser.add_argument("--duration", type=float, default=2.0, help="movement duration seconds")
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

        print(f"[movement] {args.direction} for {args.duration:.1f}s")
        send_movement(dog, args.direction)
        if args.direction != "stop":
            time.sleep(max(0.0, args.duration))
            dog.stop_movement(transport="ws")
            print("[movement] stopped")
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
