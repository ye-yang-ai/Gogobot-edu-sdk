"""Run a reactive companion patrol demo.

Purpose:
    Demonstrate a sensor-driven routine: stretch wake-up, TOF patrol,
    obstacle detection, short retreat, and whining/tantrum reaction.
Risk level:
    Medium. The robot will walk backward/forward and perform interaction actions.
Dependencies:
    pip install -e .
Run:
    python demo/demo_3_reactive_companion.py --yes
Expected result:
    The robot stretches, patrols forward, detects a close obstacle with TOF,
    retreats briefly, then performs a whining/tantrum reaction.
Exit:
    Wait for completion, or press Ctrl+C. Cleanup stops movement/audio and restores state.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import Action, AiDog, EarAction, ExpressionAction, Movement, Tone


def connect_robot(dog: AiDog, name_prefix: str, address: Optional[str]) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("This demo moves the robot. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def get_front_distance_mm(dog: AiDog) -> Optional[float]:
    tof = dog.get_latest_tof()
    if not tof:
        return None

    front = tof.get("front_mm")
    if isinstance(front, (int, float)):
        return float(front)

    return None


def wake_up_with_stretch(dog: AiDog, timeout_s: float) -> None:
    print("[demo3] wake up: stretch")
    dog.send_ear(EarAction.EAR_STAND)
    dog.send_audio(Tone.WAKE_UP)
    time.sleep(0.3)

    dog.perform_action(Action.STRETCH, timeout_s=timeout_s)

    dog.send_audio(Tone.STOP)
    dog.send_expression(ExpressionAction.HAPPY_03)
    time.sleep(0.5)


def patrol_until_obstacle(
    dog: AiDog,
    *,
    patrol_time_s: float,
    obstacle_mm: float,
    tof_hz: int,
) -> bool:
    print("[demo3] patrol: TOF stream on")
    dog.request_tof_stream(True, hz=tof_hz)

    # Give ae04 notifications a short warm-up window.
    time.sleep(0.8)

    deadline = time.time() + max(0.1, patrol_time_s)
    while time.time() < deadline:
        front_mm = get_front_distance_mm(dog)
        if front_mm is not None:
            print(f"[demo3] TOF front={front_mm:.0f}mm")
            if front_mm <= obstacle_mm:
                print("[demo3] obstacle detected")
                dog.stop_movement()
                return True

        # Short movement pulses keep stop latency low.
        dog.send_expression(ExpressionAction.LOOK_LEFT_AND_RIGHT)
        dog.send_movement(Movement.FORWARD, duration_s=0.4)
        time.sleep(0.1)

    dog.stop_movement()
    print("[demo3] patrol timeout: no obstacle")
    return False


def retreat_then_whine(dog: AiDog, timeout_s: float) -> None:
    print("[demo3] reaction: retreat")
    dog.stop_movement()
    dog.send_audio(Tone.DOUBT)
    dog.send_expression(ExpressionAction.DOUBT_03)
    dog.send_ear(EarAction.EAR_FLICK_RANDOM)
    time.sleep(0.4)

    dog.send_movement(Movement.BACK, duration_s=0.8)
    time.sleep(0.3)

    print("[demo3] reaction: whining tantrum")
    dog.send_audio(Tone.SAD)
    dog.send_expression(ExpressionAction.SAD_03)
    dog.send_ear(EarAction.EAR_DOWN)
    time.sleep(0.2)

    dog.perform_action(Action.WHINING, timeout_s=timeout_s)

    dog.send_audio(Tone.STOP)
    dog.send_expression(ExpressionAction.SHY)
    dog.send_ear(EarAction.EAR_STAND)
    time.sleep(0.5)


def no_obstacle_idle_reaction(dog: AiDog) -> None:
    print("[demo3] idle reaction: curious")
    dog.stop_movement()
    dog.send_expression(ExpressionAction.DOUBT_01)
    dog.send_ear(EarAction.EAR_STAND_LEFT_AND_RIGHT)
    dog.send_audio(Tone.CURIOUS)
    time.sleep(1.2)
    dog.send_audio(Tone.STOP)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Gogobot EDU demo3 reactive patrol")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--patrol-time", type=float, default=8.0, help="max patrol duration in seconds")
    parser.add_argument("--obstacle-mm", type=float, default=250.0, help="front TOF obstacle threshold")
    parser.add_argument("--tof-hz", type=int, default=10, help="requested TOF stream rate")
    parser.add_argument("--timeout", type=float, default=25.0, help="action timeout")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    require_confirmation(args.yes)

    print("[demo3] connecting to robot")
    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)

        try:
            dog.disable_special_detection()
            dog.set_tof_enable(True)

            wake_up_with_stretch(dog, args.timeout)

            found_obstacle = patrol_until_obstacle(
                dog,
                patrol_time_s=args.patrol_time,
                obstacle_mm=args.obstacle_mm,
                tof_hz=max(1, min(200, args.tof_hz)),
            )

            if found_obstacle:
                retreat_then_whine(dog, args.timeout)
            else:
                no_obstacle_idle_reaction(dog)

            print("[demo3] finished")
            return 0

        except KeyboardInterrupt:
            print("\n[demo3] interrupted", file=sys.stderr)
            return 130

        finally:
            try:
                dog.stop_movement()
                dog.send_audio(Tone.STOP)
                dog.request_tof_stream(False)
                dog.set_tof_enable(True)
                dog.enable_special_detection()
                dog.reset()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
