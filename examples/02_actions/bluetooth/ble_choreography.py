"""Run a short action choreography.

Purpose:
    Demonstrate combining actions, ears, expressions, tones, and movement.
Risk level:
    Medium. The robot will move and perform multiple actions.
Dependencies:
    pip install -e .
Run:
    python examples/02_actions/bluetooth/ble_choreography.py --yes
Expected result:
    The robot performs a short scripted show.
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

from aidog_sdk import Action, AiDog, EarAction, ExpressionAction, Movement, Tone


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This choreography moves the robot. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def forward_with_tone(dog: AiDog, seconds: float, tone: Tone) -> None:
    dog.send_audio(tone)
    time.sleep(0.05)
    dog.send_movement(Movement.FORWARD)
    try:
        time.sleep(seconds)
    finally:
        dog.stop_movement()
        dog.send_audio(Tone.STOP)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a Gogobot EDU choreography")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--timeout", type=float, default=30.0, help="turn/action timeout")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    require_confirmation(args.yes)

    print("[show] connecting to robot")
    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)
        try:
            dog.set_special_detection(False)

            print("[show] ears + expression")
            dog.send_ear(EarAction.EAR_STAND)
            dog.send_expression(ExpressionAction.YAWN)
            time.sleep(1.0)

            print("[show] shake hand")
            dog.perform_action(Action.SHAKE_HAND, count=3, timeout_s=args.timeout)

            print("[show] nod")
            dog.perform_action(Action.NOD, count=3, timeout_s=args.timeout)

            print("[show] forward + tone")
            forward_with_tone(dog, 6.0, Tone.BEAT1)

            print("[show] right turn 180 deg")
            dog.perform_action(
                Action.RIGHT_ANGLE_INTERACTION,
                angle=180,
                timeout_s=args.timeout,
                require_running_state=False,
            )

            print("[show] wag tail")
            dog.perform_action(Action.WAG_TAIL, count=2, timeout_s=args.timeout)

            dog.reset()
            return 0
        except KeyboardInterrupt:
            print("\n[show] interrupted", file=sys.stderr)
            return 130
        finally:
            try:
                dog.stop_movement()
                dog.send_audio(Tone.STOP)
                dog.set_special_detection(True)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
