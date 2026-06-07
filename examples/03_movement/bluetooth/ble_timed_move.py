"""Run a timed movement sequence.

Purpose:
    Demonstrate forward, right, back, left, and step movements with pauses.
Risk level:
    Medium. The robot will walk in multiple directions.
Dependencies:
    pip install -e .
Run:
    python examples/03_movement/bluetooth/ble_timed_move.py --duration 2 --yes
Expected result:
    The robot performs each movement direction and stops between commands.
Exit:
    Wait for completion, or press Ctrl+C. The script stops movement in cleanup.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, Movement


SEQUENCE = [
    ("forward", Movement.FORWARD),
    ("right", Movement.RIGHT),
    ("back", Movement.BACK),
    ("left", Movement.LEFT),
    ("step", Movement.STEP),
]


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This example moves the robot in several directions. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run timed movement sequence")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--duration", type=float, default=2.0, help="duration per direction")
    parser.add_argument("--pause", type=float, default=1.0, help="pause between directions")
    parser.add_argument("--timeout", type=float, default=0.0, help="reserved timeout hint")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    _ = args.timeout
    require_confirmation(args.yes)

    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)
        try:
            for name, movement in SEQUENCE:
                print(f"[movement] {name} for {args.duration:.1f}s")
                dog.send_movement(movement, duration_s=args.duration)
                dog.stop_movement()
                time.sleep(max(0.0, args.pause))
            print("[movement] sequence complete")
        finally:
            dog.stop_movement()
            dog.reset()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
