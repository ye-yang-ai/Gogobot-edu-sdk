"""Run a short action-only choreography over WebSocket control_raw.

Purpose:
    Verify normal, count-based, and angle-based action packets over WebSocket.
Risk level:
    Medium. The robot will perform several body actions.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/02_actions/websocket/ws_choreography.py --bind 0.0.0.0 --port 8766 --yes
Expected result:
    The robot runs three actions; each completion is observed from existing sensor JSON.
Exit:
    Wait for completion, or press Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import Action, AiDog, DevPcWebSocketHost
from ws_basic_actions import require_confirmation, wait_status_ready


def send_action(
    dog: AiDog,
    label: str,
    action: Action,
    timeout_s: float,
    *,
    count: Optional[int] = None,
    angle: Optional[int] = None,
) -> bool:
    print(f"[show] {label}: {action.name}")
    done = dog.perform_action(action, count=count, angle=angle, timeout_s=timeout_s, transport="ws")
    print(f"[show] {label} done={done}")
    time.sleep(0.8)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a WebSocket action choreography")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--timeout", type=float, default=30.0, help="action wait timeout in seconds")
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
        if not wait_status_ready(dog, timeout_s=5.0):
            print("[ready] timeout waiting for interaction status JSON")
            return 1

        steps = [
            ("normal", Action.SIT_DOWN, None, None),
            ("count", Action.SHAKE_HAND, 2, None),
            ("angle", Action.RIGHT_ANGLE_INTERACTION, None, 90),
        ]
        ok = True
        for label, action, count, angle in steps:
            ok = send_action(
                dog,
                label,
                action,
                args.timeout,
                count=count,
                angle=angle,
            ) and ok
        return 0 if ok else 2
    except KeyboardInterrupt:
        print("\n[host] interrupted")
        return 130
    finally:
        try:
            if host.is_robot_connected:
                dog.send_interaction(Action.STOP_INTERACTION, transport="ws")
        except Exception:
            pass
        host.stop()


if __name__ == "__main__":
    raise SystemExit(main())
