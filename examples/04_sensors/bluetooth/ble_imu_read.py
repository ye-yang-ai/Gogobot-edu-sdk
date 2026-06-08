"""Read IMU data from BLE ae04 notifications.

Purpose:
    Print live yaw/pitch/roll or raw accel/gyro data.
Risk level:
    Low. This example reads sensor data and does not command movement.
Dependencies:
    pip install -e .
Run:
    python examples/04_sensors/bluetooth/ble_imu_read.py --hz 20
    python examples/04_sensors/bluetooth/ble_imu_read.py --mode raw --raw both
Expected result:
    The terminal prints IMU data until stopped.
Exit:
    Press Ctrl+C. The script requests IMU stream off in cleanup.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable, Dict

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def build_imu_printer(mode: str, raw: str) -> Callable[[Dict[str, object]], None]:
    def print_imu(imu: Dict[str, object]) -> None:
        if mode == "raw":
            accel = imu.get("accel")
            gyro = imu.get("gyro")
            if raw == "gyro":
                print(f"[IMU] gyro={gyro}")
            elif raw == "both":
                print(f"[IMU] accel={accel};  gyro={gyro}")
            else:
                print(f"[IMU] accel={accel}")
            return

        yaw = imu.get("yaw_deg")
        pitch = imu.get("pitch_deg")
        roll = imu.get("roll_deg")
        if all(isinstance(v, (int, float)) for v in (yaw, pitch, roll)):
            print(
                f"[IMU] yaw={float(yaw):7.3f}deg;   "
                f"pitch={float(pitch):7.3f}deg;   roll={float(roll):7.3f}deg;"
            )
        else:
            print("[IMU]", imu)

    return print_imu


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Gogobot EDU IMU stream")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--hz", type=int, default=20, help="requested IMU stream rate")
    parser.add_argument("--timeout", type=float, default=0.0, help="auto-exit after seconds; 0 runs forever")
    parser.add_argument("--mode", choices=("angles", "raw"), default="angles")
    parser.add_argument("--raw", choices=("accel", "gyro", "both"), default="accel")
    args = parser.parse_args()

    dog = AiDog(imu_only_notify=True)
    try:
        connect_robot(dog, args.name_prefix, args.address)
        dog.add_imu_listener(build_imu_printer(args.mode, args.raw))
        dog.request_imu_stream(True, hz=max(1, min(200, args.hz)))
        print(f"[IMU] stream on: hz={args.hz}")

        deadline = time.time() + args.timeout if args.timeout > 0 else None
        while deadline is None or time.time() < deadline:
            time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        print("\n[IMU] interrupted")
        return 130
    finally:
        try:
            dog.request_imu_stream(False)
        except Exception:
            pass
        if dog.is_connected:
            dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
