"""Test the robot Dev-PC WebSocket connection.

Purpose:
    Start a PC-side WebSocket server and wait for the robot to connect.
Risk level:
    Low. This script does not send motion, ear, expression, or audio commands.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/01_connection/websocket/ws_connection_test.py --bind 0.0.0.0 --port 8766
Expected result:
    The script reports that the robot WebSocket connected.
Exit:
    Press Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import DevPcWebSocketHost


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for robot Dev-PC WebSocket connection")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--timeout", type=float, default=60.0, help="wait timeout in seconds")
    args = parser.parse_args()

    host = DevPcWebSocketHost(host=args.bind, port=args.port)
    try:
        host.start()
        print(f"[host] listening ws://{args.bind}:{args.port}; waiting for robot")
        if not host.wait_robot_connected(timeout_s=args.timeout):
            print("[host] timeout waiting for robot")
            return 1
        print("[host] robot connected")
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[host] stopped")
        return 0
    finally:
        host.stop()


if __name__ == "__main__":
    raise SystemExit(main())

