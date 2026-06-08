"""Run a staged robot performance routine.

Purpose:
    Demonstrate a complete show sequence with actions, movement, angle turning,
    audio, expressions, ears, and lights.
Risk level:
    Medium. The robot will walk, turn, jump, crouch, and move body/legs.
Dependencies:
    pip install -e .
Run:
    python demo/demo_1_performance.py
Expected result:
    The robot performs the scripted routine and returns to its normal state.
Exit:
    Wait for completion, or press Ctrl+C. The script stops audio/movement in cleanup.
"""

from __future__ import annotations

import sys
import time

from aidog_sdk import Action, AiDog, EarAction, ExpressionAction, Movement, Tone


# Configuration.
TURN_TIMEOUT_S = 30.0

# Enable optional expression, ear, light, return-beat, and finale effects.
ENABLE_EXTRAS = True


def forward_seconds_beat(
    dog: AiDog,
    seconds: float,
    tone: Tone,
    *,
    stop_tone_after: bool = True,
) -> None:
    """Move forward for a fixed duration while playing a tone."""
    dog.send_audio(tone)
    time.sleep(0.05)
    dog.send_movement(Movement.FORWARD)
    try:
        time.sleep(float(seconds))
    finally:
        dog.stop_movement()
        time.sleep(0.2)
        if stop_tone_after:
            dog.send_audio(Tone.STOP)


def main() -> int:
    print("[Show] Connecting to robot...")
    with AiDog() as dog:
        # Scan and connect by BLE name prefix.
        dog.connect("Gogobot")
        # Or connect by BLE address / platform UUID.
        # dog.connect(address="xx:xx:xx:xx:xx:xx")

        dog.set_special_detection(False)

        if ENABLE_EXTRAS:
            print("[Show] Ears up")
            dog.send_ear(EarAction.EAR_STAND)
            time.sleep(0.3)
            dog.send_expression(ExpressionAction.YAWN)
            time.sleep(5)

        print("[Show] Shake hand")
        dog.perform_action(Action.SHAKE_HAND, count=3)

        print("[Show] Nod")
        dog.perform_action(Action.NOD, count=2)

        time.sleep(1.0)

        print("[Show] Forward 2s + BEAT1")
        forward_seconds_beat(dog, 2, Tone.BEAT1)

        time.sleep(1.0)

        print("[Show] Jump")
        dog.perform_action(Action.JUMP)

        time.sleep(0.3)

        print("[Show] right turn 180 deg")
        dog.perform_action(
            Action.RIGHT_ANGLE_INTERACTION,
            angle=45,
            timeout_s=TURN_TIMEOUT_S,
            require_running_state=False,
        )

        print("[Show] Slow crouch")
        slow_down_s = 20.0
        # Use non-blocking interaction so later effects can run during crouch.
        dog.send_interaction(int(Action.SLOW_DOWN_FOR_PROGRAM), int(slow_down_s))
        time.sleep(2.0)

        if ENABLE_EXTRAS:
            print("[Show] Sleepy expression")
            dog.send_expression(ExpressionAction.SLEEPY)

        # Wait for the remaining crouch time before the next stage.
        time.sleep(max(0.0, slow_down_s - 2.0))

        print("[Show] Stretch")
        dog.perform_action(Action.STRETCH)

        if ENABLE_EXTRAS:
            print("[Show] Finalize: light tail wag x3")
            dog.perform_action(Action.WAG_TAIL, count=3)

        dog.send_audio(Tone.STOP)
        dog.reset()

        dog.set_special_detection(True)
        time.sleep(0.3)

    print("[Show] Finished.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[Show] Interrupted.", file=sys.stderr)
        raise SystemExit(130)
