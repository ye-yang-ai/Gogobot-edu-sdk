"""Run a small safe pose adjustment.

Purpose:
    Demonstrate MODE_ROBOT_ADJUST with low-amplitude body, foot, and joint changes.
Risk level:
    High. This example changes body/foot/joint targets and requires matching firmware.
Dependencies:
    pip install -e .
Run:
    python examples/06_robot_adjust/safe_pose_adjust.py --yes
Expected result:
    The robot enters a baseline pose, performs small adjustments, then returns to basic mode.
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

from aidog_sdk import AiDog


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def require_confirmation(yes: bool) -> None:
    if yes:
        return
    answer = input("HIGH RISK: robot adjustment will move body/feet/joints. Type RUN to continue: ").strip()
    if answer != "RUN":
        raise SystemExit("Cancelled.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe low-amplitude robot adjustment")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--timeout", type=float, default=20.0, help="reserved timeout hint")
    parser.add_argument("--yes", action="store_true", help="run without interactive confirmation")
    args = parser.parse_args()

    _ = args.timeout
    require_confirmation(args.yes)

    dog = AiDog()
    try:
        connect_robot(dog, args.name_prefix, args.address)
        dog.request_basic_mode()
        dog.disable_special_detection()

        print("[adjust] baseline pose")
        dog.default_pose_output(0.0, 0.0, 5.0, 110.0)
        time.sleep(0.5)

        print("[adjust] lower COG slightly")
        dog.syn_pose_adjust([{"name": "cog_z", "now": 110.0, "end": 55.0}], duration_ms=1000)
        time.sleep(1.0)

        print("[adjust] restore COG")
        dog.syn_pose_adjust([{"name": "cog_z", "now": 55.0, "end": 110.0}], duration_ms=1000)
        time.sleep(1.0)

        print("[adjust] small foot X shift")
        dog.syn_foot_adjust(
            [
                ("foot_0_x", 30.0),
                ("foot_1_x", 30.0),
                ("foot_2_x", 30.0),
                ("foot_3_x", 30.0),
            ],
            duration_ms=500,
        )
        time.sleep(1.0)

        dog.syn_foot_adjust(
            [
                ("foot_0_x", -30.0),
                ("foot_1_x", -30.0),
                ("foot_2_x", -30.0),
                ("foot_3_x", -30.0),
            ],
            duration_ms=500,
        )
        time.sleep(1.0)

        print("[adjust] complete")
        return 0
    except KeyboardInterrupt:
        print("\n[adjust] interrupted")
        return 130
    finally:
        try:
            dog.request_basic_mode()
            dog.enable_special_detection()
            dog.stop_movement()
        except Exception:
            pass
        if dog.is_connected:
            dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
