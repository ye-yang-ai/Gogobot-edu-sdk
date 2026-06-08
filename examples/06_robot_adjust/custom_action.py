"""Run a custom sniff-like robot-adjustment action.

Purpose:
    Demonstrate a custom action built from foot adjustments, expression, and audio.
Risk level:
    High. This example changes foot targets and requires matching firmware.
Dependencies:
    pip install -e .
Run:
    python examples/06_robot_adjust/custom_action.py --yes
Expected result:
    The robot performs a short sniff-like motion and returns to basic mode.
Exit:
    Wait for completion, or press Ctrl+C. The script requests basic mode in cleanup.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, ExpressionAction, Tone


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("HIGH RISK: custom robot adjustment will move feet. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def run_sniff_motion(dog: AiDog, hold_s: float) -> None:
    dog.request_basic_mode()
    time.sleep(0.4)
    dog.default_pose_output(0.0, 0.0, 5.0, 110.0)
    time.sleep(0.4)

    dog.syn_foot_adjust(
        [
            ("foot_0_x", 25.0),
            ("foot_2_x", 25.0),
            ("foot_1_x", 25.0),
            ("foot_3_x", 25.0),
        ],
        duration_ms=600,
    )
    time.sleep(0.8)

    dog.syn_foot_adjust(
        [
            ("foot_0_z", 40.0),
            ("foot_2_z", 40.0),
            ("foot_0_x", -20.0),
            ("foot_2_x", -20.0),
        ],
        duration_ms=600,
    )
    time.sleep(0.7)

    dog.send_expression(ExpressionAction.EAT_SNACK)
    dog.send_audio(Tone.EATING)
    time.sleep(max(0.0, hold_s))
    dog.send_audio(Tone.STOP)

    dog.syn_foot_adjust(
        [
            ("foot_0_z", -40.0),
            ("foot_2_z", -40.0),
            ("foot_0_x", 20.0),
            ("foot_2_x", 20.0),
        ],
        duration_ms=600,
    )
    time.sleep(0.8)

    dog.syn_foot_adjust(
        [
            ("foot_0_x", -25.0),
            ("foot_2_x", -25.0),
            ("foot_1_x", -25.0),
            ("foot_3_x", -25.0),
        ],
        duration_ms=600,
    )
    time.sleep(0.8)

    dog.request_basic_mode()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run custom robot-adjustment action")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--timeout", type=float, default=20.0, help="reserved timeout hint")
    parser.add_argument("--hold", type=float, default=4.0, help="hold duration during expression/audio")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    _ = args.timeout
    require_confirmation(args.yes)

    dog = AiDog()
    try:
        connect_robot(dog, args.name_prefix, args.address)
        dog.disable_special_detection()
        run_sniff_motion(dog, args.hold)
        print("[custom] sniff motion completed")
        return 0
    except KeyboardInterrupt:
        print("\n[custom] interrupted")
        return 130
    finally:
        try:
            dog.send_audio(Tone.STOP)
            dog.request_basic_mode()
            dog.enable_special_detection()
            dog.reset()
        except Exception:
            pass
        if dog.is_connected:
            dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
