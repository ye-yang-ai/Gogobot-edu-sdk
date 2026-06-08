"""Read TOF data from BLE ae04 notifications.

Purpose:
    Print live front and/or oblique distance readings.
Risk level:
    Low. This example reads sensor data and does not command movement.
Dependencies:
    pip install -e .
Run:
    python examples/04_sensors/bluetooth/ble_tof_read.py --hz 20 --mode both
Expected result:
    The terminal prints TOF distance readings until stopped.
Exit:
    Press Ctrl+C. The script requests TOF stream off in cleanup.
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


def build_tof_printer(mode: str) -> Callable[[Dict[str, object]], None]:
    def print_tof(tof: Dict[str, object]) -> None:
        front = tof.get("front_mm")
        oblique = tof.get("oblique_mm")
        if mode == "front":
            print(f"[TOF] front={front}mm")
        elif mode == "oblique":
            print(f"[TOF] oblique={oblique}mm")
        else:
            print(f"[TOF] front={front}mm;  oblique={oblique}mm")

    return print_tof


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Gogobot EDU TOF stream")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--hz", type=int, default=20, help="requested TOF stream rate")
    parser.add_argument("--timeout", type=float, default=0.0, help="auto-exit after seconds; 0 runs forever")
    parser.add_argument("--mode", choices=("front", "oblique", "both"), default="both")
    args = parser.parse_args()

    dog = AiDog(imu_only_notify=True)
    try:
        connect_robot(dog, args.name_prefix, args.address)
        dog.add_tof_listener(build_tof_printer(args.mode))
        dog.request_tof_stream(True, hz=max(1, min(200, args.hz)))
        print(f"[TOF] stream on: hz={args.hz}")

        deadline = time.time() + args.timeout if args.timeout > 0 else None
        while deadline is None or time.time() < deadline:
            time.sleep(0.5)
        return 0
    except KeyboardInterrupt:
        print("\n[TOF] interrupted")
        return 130
    finally:
        try:
            dog.request_tof_stream(False)
        except Exception:
            pass
        if dog.is_connected:
            dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
