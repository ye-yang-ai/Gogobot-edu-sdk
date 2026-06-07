"""Run basic high-level robot actions.

Purpose:
    Demonstrate a small set of safe interaction actions.
Risk level:
    Medium. The robot will move its body and legs.
Dependencies:
    pip install -e .
Run:
    python examples/02_actions/bluetooth/ble_basic_actions.py
    python examples/02_actions/bluetooth/ble_basic_actions.py --address AA:BB:CC:DD:EE:FF --action shake_hand
    python examples/02_actions/bluetooth/ble_basic_actions.py --address AA:BB:CC:DD:EE:FF --action turn_left_angle --angle 90
    python examples/02_actions/bluetooth/ble_basic_actions.py --address AA:BB:CC:DD:EE:FF --action turn_right_angle --angle 180
Expected result:
    The robot performs the requested action and prints completion status.
Exit:
    Wait for the action to finish, or press Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, resolve_action


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a basic Gogobot EDU action")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--action", default="sit_down", help="action name or numeric ID")
    parser.add_argument("--count", type=int, default=None, help="optional repeat count for count actions")
    parser.add_argument("--duration", type=int, default=None, help="optional duration for timed actions")
    parser.add_argument("--angle", type=int, default=None, help="optional angle for angle actions")
    parser.add_argument("--timeout", type=float, default=10.0, help="action wait timeout in seconds")
    args = parser.parse_args()

    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)
        action = resolve_action(int(args.action) if args.action.isdigit() else args.action)
        print(f"[action] running {action.name} ({int(action)})")
        ok = dog.perform_action(
            action,
            count=args.count,
            duration=args.duration,
            angle=args.angle,
            timeout_s=args.timeout,
        )
        print(f"[action] done={ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
