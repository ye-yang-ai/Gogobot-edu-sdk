"""Run one directional movement command.

Purpose:
    Move the robot in one selected direction for a short duration.
Risk level:
    Medium. The robot will walk or step.
Dependencies:
    pip install -e .
Run:
    python examples/03_movement/bluetooth/ble_directional_move.py --direction forward --duration 2 --yes
Expected result:
    The robot moves in the selected direction and then stops.
Exit:
    Wait for the duration to finish, or press Ctrl+C. The script stops movement in cleanup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, Movement


MOVEMENTS = {
    "forward": Movement.FORWARD,
    "back": Movement.BACK,
    "left": Movement.LEFT,
    "right": Movement.RIGHT,
    "step": Movement.STEP,
}


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This example moves the robot. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one directional movement")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--direction", choices=sorted(MOVEMENTS), default="forward")
    parser.add_argument("--duration", type=float, default=2.0, help="movement duration seconds")
    parser.add_argument("--timeout", type=float, default=0.0, help="reserved timeout hint")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    _ = args.timeout
    require_confirmation(args.yes)

    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)
        try:
            print(f"[movement] {args.direction} for {args.duration:.1f}s")
            dog.send_movement(MOVEMENTS[args.direction], duration_s=args.duration)
            print("[movement] stopped")
        finally:
            dog.stop_movement()
            dog.reset()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
