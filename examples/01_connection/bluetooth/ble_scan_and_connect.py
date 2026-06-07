"""Scan and connect over BLE.

Purpose:
    Find nearby Gogobot EDU / Changba AI-Dog devices, connect to one device,
    then wait until the user exits.
Risk level:
    Low. This example does not command physical movement.
Dependencies:
    pip install -e .
Run:
    python examples/01_connection/bluetooth/ble_scan_and_connect.py
    python examples/01_connection/bluetooth/ble_scan_and_connect.py --name-prefix Changba-Ai-Dog
    python examples/01_connection/bluetooth/ble_scan_and_connect.py --address AA:BB:CC:DD:EE:FF
Expected result:
    The terminal lists nearby devices and reports a successful BLE connection.
Exit:
    Press Enter after connection, or Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan and connect to a Gogobot EDU robot")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="skip scan and connect to this BLE address or UUID")
    parser.add_argument("--timeout", type=float, default=0.0, help="reserved for future scan timeout")
    args = parser.parse_args()

    _ = args.timeout
    dog = AiDog()
    try:
        if args.address:
            print(f"[connect] direct address: {args.address}")
            dog.connect(address=args.address)
        else:
            print(f"[scan] name prefix: {args.name_prefix}")
            devices = dog.scan(args.name_prefix)
            if not devices:
                print("[scan] no matching device found")
                return 1

            print(f"[scan] found {len(devices)} device(s):")
            for idx, (name, address) in enumerate(devices, start=1):
                print(f"  {idx}. {name} [{address}]")

            name, address = devices[0]
            print(f"[connect] using first device: {name} [{address}]")
            dog.connect(address=address)

        print("[connect] connected. Press Enter to disconnect.")
        input()
        return 0
    except KeyboardInterrupt:
        print("\n[connect] interrupted")
        return 130
    finally:
        if dog.is_connected:
            dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
