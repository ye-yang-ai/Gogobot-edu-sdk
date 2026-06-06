"""Connect to a known BLE address.

Purpose:
    Connect directly to a robot when its BLE address or platform UUID is known.
Risk level:
    Low. This example does not command physical movement.
Dependencies:
    pip install -e .
Run:
    python examples/01_connection/bluetooth/ble_connect_by_address.py --address AA:BB:CC:DD:EE:FF
Expected result:
    The terminal reports a successful BLE connection.
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
    parser = argparse.ArgumentParser(description="Connect to a Gogobot EDU robot by address")
    parser.add_argument("--address", required=True, help="BLE address on Windows/Linux or UUID on macOS")
    parser.add_argument("--timeout", type=float, default=10.0, help="connection timeout hint in seconds")
    args = parser.parse_args()

    _ = args.timeout
    dog = AiDog()
    try:
        print(f"[connect] address: {args.address}")
        dog.connect(address=args.address)
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
