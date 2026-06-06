"""Run a basic robot action over WebSocket control_raw.

Purpose:
    Verify that WebSocket mode=0x02 action commands follow the same firmware path as BLE.
Risk level:
    Medium. The robot will perform the requested body action.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/02_actions/websocket/ws_basic_actions.py --bind 0.0.0.0 --port 8766 --yes
    python examples/02_actions/websocket/ws_basic_actions.py --action shake_hand --count 3 --yes
    python examples/02_actions/websocket/ws_basic_actions.py --action turn_right_angle --angle 90 --yes
Expected result:
    The robot performs the requested action. Completion is observed from existing sensor JSON.
Exit:
    Wait for the action to finish, or press Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import (
    ANGLE_BASED,
    COUNT_BASED,
    TIMER_BASED,
    Action,
    AiDog,
    DevPcWebSocketHost,
    resolve_action,
)


STATUS_NAMES = {
    None: "UNKNOWN",
    0: "IDLE",
    1: "RUNNING",
    2: "KILLED",
}


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This action moves the robot. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def get_interaction_status(dog: AiDog) -> Tuple[int, Optional[int]]:
    with dog._notify_lock:
        return dog._interaction_status_notify_seq, dog._last_interaction_task_status


def wait_status_ready(dog: AiDog, *, timeout_s: float) -> bool:
    deadline = time.time() + max(0.1, float(timeout_s))
    last_marker: Optional[Tuple[int, Optional[int]]] = None
    while time.time() < deadline:
        seq, status = get_interaction_status(dog)
        marker = (seq, status)
        if marker != last_marker:
            print(f"[ready] interaction_task_status={STATUS_NAMES.get(status, status)} seq={seq}")
            last_marker = marker
        if seq > 0 and status == 0:
            return True
        time.sleep(0.2)
    return False


def build_action_data(
    action_arg: str,
    *,
    count: Optional[int] = None,
    duration: Optional[int] = None,
    angle: Optional[int] = None,
) -> Tuple[Action, List[int]]:
    action = resolve_action(int(action_arg) if action_arg.isdigit() else action_arg)
    param: Optional[int] = None
    if count is not None and action in COUNT_BASED:
        param = max(1, min(255, int(count)))
    elif duration is not None and action in TIMER_BASED:
        param = max(1, min(255, int(duration)))
    elif angle is not None and action in ANGLE_BASED:
        param = max(1, min(360, int(angle)))

    data = [int(action) & 0xFF]
    if param is not None:
        if action in ANGLE_BASED:
            data.extend([param & 0xFF, (param >> 8) & 0xFF])
        else:
            data.append(param & 0xFF)
    return action, data


def wait_action_done(
    dog: AiDog,
    *,
    start_seq: int,
    timeout_s: float,
    require_running_state: bool = True,
) -> bool:
    deadline = time.time() + max(0.5, float(timeout_s))
    last_marker: Optional[Tuple[int, Optional[int]]] = None
    seen_running = False
    started = False
    while time.time() < deadline:
        seq, status = get_interaction_status(dog)
        marker = (seq, status)
        if marker != last_marker:
            print(f"[notify] interaction_task_status={STATUS_NAMES.get(status, status)} seq={seq}")
            last_marker = marker
        if status == 1:
            seen_running = True
            started = True
        elif status not in (None, 0):
            started = True
        if status == 0 and seq > start_seq:
            if not require_running_state or seen_running or started:
                return True
        if status == 2:
            return False
        time.sleep(0.2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one WebSocket robot action")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--timeout", type=float, default=20.0, help="action wait timeout in seconds")
    parser.add_argument("--action", default="sit_down", help="action name or numeric ID")
    parser.add_argument("--count", type=int, default=None, help="optional repeat count for count actions")
    parser.add_argument("--duration", type=int, default=None, help="optional duration for timed actions")
    parser.add_argument("--angle", type=int, default=None, help="optional angle for angle actions")
    parser.add_argument("--ready-timeout", type=float, default=5.0, help="wait for status JSON before sending")
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
        if not wait_status_ready(dog, timeout_s=args.ready_timeout):
            print("[ready] timeout waiting for interaction status JSON")
            return 1
        if args.settle > 0:
            time.sleep(args.settle)

        action, data = build_action_data(
            args.action,
            count=args.count,
            duration=args.duration,
            angle=args.angle,
        )
        start_seq, _ = get_interaction_status(dog)
        print(f"[action] {action.name} data={data}")
        done = dog.perform_action(
            action,
            count=args.count,
            duration=args.duration,
            angle=args.angle,
            timeout_s=args.timeout,
            transport="ws",
        )
        if not done:
            done = wait_action_done(dog, start_seq=start_seq, timeout_s=0.5)
        print(f"[action] done={done}")
        return 0 if done else 2
    except KeyboardInterrupt:
        print("\n[host] interrupted")
        return 130
    finally:
        host.stop()


if __name__ == "__main__":
    raise SystemExit(main())
