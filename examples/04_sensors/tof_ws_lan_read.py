"""Read TOF data over LAN via Dev PC WebSocket.

Purpose:
    Listen for robot WebSocket text frames containing TOF JSON.
Risk level:
    Low. This example reads sensor data and does not command movement.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Firmware:
    DEV_PC_AUDIO_WS_ENABLE=1 and DEV_PC_AUDIO_WS_URL points to this PC.
Run:
    python examples/04_sensors/tof_ws_lan_read.py --bind 0.0.0.0 --port 8766
    python examples/04_sensors/tof_ws_lan_read.py --ble --hz 40
    python examples/04_sensors/tof_ws_lan_read.py --mode front
    python examples/04_sensors/tof_ws_lan_read.py --mode oblique
Expected result:
    The terminal prints LAN TOF data when the robot connects.
Exit:
    Press Ctrl+C. The script stops the WebSocket host in cleanup.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Callable, Dict

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, DevPcWebSocketHost


def build_tof_printer(mode: str) -> Callable[[Dict[str, object]], None]:
    def print_tof(tof: Dict[str, object]) -> None:
        front = tof.get("front_mm")
        oblique = tof.get("oblique_mm")
        if mode == "front":
            print(f"[LAN TOF] front={front}mm")
        elif mode == "oblique":
            print(f"[LAN TOF] oblique={oblique}mm")
        else:
            print(f"[LAN TOF] front={front}mm;  oblique={oblique}mm")

    return print_tof


def build_ws_connection_handler(dog: AiDog, hz: int, print_tof: Callable[[Dict[str, object]], None]):
    async def handle_connection(ws) -> None:
        await asyncio.sleep(0.2)
        cmd = {"cmd": "sensor_stream", "tof": {"enable": True, "hz": hz}}
        await ws.send(json.dumps(cmd, separators=(",", ":")))
        print(f"[WS] requested TOF stream hz={hz}")

        async for message in ws:
            if not isinstance(message, str):
                continue
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "ack" and data.get("cmd") == "sensor_stream":
                print(f"[WS] ack {data}")
                continue
            dog.feed_sensor_stream_json(message)
            _, _, tof = AiDog.parse_notify_json_text(message)
            if tof is not None:
                print_tof(tof)

    return handle_connection


def main() -> int:
    parser = argparse.ArgumentParser(description="Read TOF via Dev PC WebSocket")
    parser.add_argument("--bind", default="0.0.0.0", help="listen address")
    parser.add_argument("--port", type=int, default=8766, help="listen port")
    parser.add_argument("--ble", action="store_true", help="also connect BLE to request stream rate")
    parser.add_argument("--ws-config", action="store_true", help="send TOF hz config over WebSocket after robot connects")
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog", help="BLE name prefix when --ble")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID when --ble")
    parser.add_argument("--hz", type=int, default=50, help="requested TOF rate for --ble or --ws-config")
    parser.add_argument("--timeout", type=float, default=0.0, help="auto-exit after seconds; 0 runs forever")
    parser.add_argument("--mode", choices=("front", "oblique", "both"), default="both")
    args = parser.parse_args()

    dog = AiDog(imu_only_notify=True)
    tof_printer = build_tof_printer(args.mode)
    hz = max(1, min(200, args.hz))
    host = DevPcWebSocketHost(
        host=args.bind,
        port=args.port,
        dog=None if args.ws_config else dog,
        on_tof=None if args.ws_config else tof_printer,
        connection_handler=build_ws_connection_handler(dog, hz, tof_printer) if args.ws_config else None,
    )

    try:
        host.start()
        print(f"[host] WebSocket listening ws://{args.bind}:{args.port}; waiting for robot")

        if args.ble:
            if args.address:
                dog.connect(address=args.address)
            else:
                dog.connect(args.name_prefix)
            dog.request_tof_stream(True, hz=hz)
            print(f"[BLE] requested TOF stream hz={hz}")

        deadline = time.time() + args.timeout if args.timeout > 0 else None
        while deadline is None or time.time() < deadline:
            time.sleep(1.0)
        return 0
    except KeyboardInterrupt:
        print("\n[host] interrupted")
        return 130
    finally:
        host.stop()
        if args.ble:
            try:
                dog.request_tof_stream(False)
            except Exception:
                pass
            if dog.is_connected:
                dog.disconnect()
        dog.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
