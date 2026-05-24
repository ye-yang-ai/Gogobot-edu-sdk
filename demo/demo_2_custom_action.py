"""Run a custom sniff-like robot-adjustment action.

Purpose:
    Demonstrate a firmware-like sniff motion built from foot adjustments,
    expression, and audio.
Risk level:
    High. This script changes foot targets and requires matching firmware.
Dependencies:
    pip install -e .
Run:
    python demo/demo_2_custom_action.py
Expected result:
    The robot moves forward, performs the sniff-like motion, and returns to basic mode.
Exit:
    Wait for completion, or press Ctrl+C.
"""

from __future__ import annotations

import time

from aidog_sdk import AiDog, ExpressionAction, Movement, Tone


def run_sniff_motion(dog: AiDog) -> None:
    # Start from basic mode for a consistent initial posture.
    dog.request_basic_mode()
    time.sleep(0.4)

    dog.default_pose_output(0.0, 0.0, 5.0, 110.0)
    time.sleep(0.4)

    # Shift weight backward with all four feet.
    dog.syn_foot_adjust(
        [
            ("foot_0_x", 35.0),  # right front
            ("foot_2_x", 35.0),  # left front
            ("foot_1_x", 35.0),  # right rear
            ("foot_3_x", 35.0),  # left rear
        ],
        duration_ms=600,
    )
    time.sleep(0.8)


    # Lift the front legs and pull them back slightly.
    dog.syn_foot_adjust(
        [
            ("foot_0_z", 60.0),   # lift right front
            ("foot_2_z", 60.0),   # lift left front
            ("foot_0_x", -30.0),  # pull right front back
            ("foot_2_x", -30.0),  # pull left front back
        ],
        duration_ms=600,
    )
    time.sleep(0.7)


    # Hold the expression and audio effect.
    dog.send_expression(ExpressionAction.EAT_SNACK)
    dog.send_audio(Tone.EATING)
    time.sleep(8.0)
    dog.send_audio(Tone.STOP)


    # Restore the front-leg lift and X adjustment.
    dog.syn_foot_adjust(
        [
            ("foot_0_z", -60.0),
            ("foot_2_z", -60.0),
            ("foot_0_x", 30.0),
            ("foot_2_x", 30.0),
        ],
        duration_ms=600,
    )
    time.sleep(0.8)


    # Restore the backward weight shift.
    dog.syn_foot_adjust(
        [
            ("foot_0_x", -35.0),
            ("foot_2_x", -35.0),
            ("foot_1_x", -35.0),
            ("foot_3_x", -35.0),
        ],
        duration_ms=600,
    )
    time.sleep(1.2)

    dog.request_basic_mode()
    time.sleep(0.4)


def main() -> None:
    with AiDog() as dog:
        # Scan and connect by BLE name prefix.
        dog.connect("Changba-Ai-Dog")
        # Or connect by BLE address / platform UUID.
        # dog.connect(address="xx:xx:xx:xx:xx:xx")

        # Move forward before running the custom adjustment sequence.
        dog.send_movement(Movement.FORWARD, duration_s=1.5)
        dog.send_expression(ExpressionAction.HAPPY_03)
        time.sleep(0.3)
        dog.stop_movement()
        time.sleep(0.3)

        # Disable special detection and TOF avoidance during syn_* adjustments.
        dog.disable_special_detection()
        dog.set_tof_enable(False)
        try:
            run_sniff_motion(dog)
        finally:
            dog.set_tof_enable(True)
            dog.enable_special_detection()
        dog.reset()
        print("sniff motion completed")


if __name__ == "__main__":
    main()
