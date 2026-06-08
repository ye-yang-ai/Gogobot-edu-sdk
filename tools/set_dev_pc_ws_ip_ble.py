#!/usr/bin/env python3
"""
Configure the robot Dev-PC WebSocket IP dynamically via BLE.

Usage examples:
1) Specify BLE device address:
   python tools/set_dev_pc_ws_ip_ble.py --address AA:BB:CC:DD:EE:FF 192.168.11.23

2) Auto-scan by BLE device name prefix:
   python tools/set_dev_pc_ws_ip_ble.py --name-prefix Gogobot 192.168.11.23

The tool writes a JSON configuration payload to the ae01 characteristic.
"""

import argparse
import asyncio
import ipaddress
import json
import sys
from bleak import BleakClient, BleakScanner

TARGET_CHAR_SUFFIX = "ae01"
SET_DEV_PC_WS_URL_CMD = 20


def validate_ip(ip_str: str) -> str:
    try:
        return str(ipaddress.ip_address(ip_str))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid IP address: {ip_str}") from exc


async def find_device_address(name_prefix: str, timeout: float) -> str:
    devices = await BleakScanner.discover(timeout=timeout)
    for dev in devices:
        if dev.name and dev.name.startswith(name_prefix):
            return dev.address
    return ""


async def find_target_char_uuid(client: BleakClient) -> str:
    services = None
    get_services = getattr(client, "get_services", None)
    if callable(get_services):
        try:
            services = await get_services()
        except Exception:
            services = None
    if services is None:
        services = getattr(client, "services", None)
        if services is None and callable(get_services):
            services = await get_services()
    if services is None:
        return ""
    for service in services:
        for char in service.characteristics:
            if TARGET_CHAR_SUFFIX in char.uuid.lower():
                return char.uuid
    return ""


async def run(args: argparse.Namespace) -> int:
    address = args.address
    if not address:
        print(f"[INFO] Scanning devices, prefix: {args.name_prefix}")
        address = await find_device_address(args.name_prefix, args.scan_timeout)
        if not address:
            print("[ERROR] Target device not found")
            return 1
        print(f"[INFO] Device found: {address}")

    payload = {
        "cmd": SET_DEV_PC_WS_URL_CMD,
        "dev_pc_ip": args.ip,
    }
    # Firmware parse_remote_config_data expects a C-string; appending '\0' is safer.
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\0"

    print(f"[INFO] Connecting BLE device: {address}")
    async with BleakClient(address) as client:
        if not client.is_connected:
            print("[ERROR] BLE connection failed")
            return 1

        char_uuid = await find_target_char_uuid(client)
        if not char_uuid:
            print("[ERROR] ae01 configuration characteristic not found")
            return 1

        await client.write_gatt_char(char_uuid, data, response=False)
        print(f"[OK] Configuration sent: {payload}")
        print("[OK] Device will save to flash and reconnect using the new IP")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Dev-PC WebSocket IP via BLE")
    parser.add_argument("ip", type=validate_ip, help="PC LAN IPv4 address")
    parser.add_argument("--address", help="BLE device address (e.g. AA:BB:CC:DD:EE:FF)")
    parser.add_argument("--name-prefix", default="Gogobot", help="Device name prefix used for scanning")
    parser.add_argument("--scan-timeout", type=float, default=5.0, help="Scan timeout in seconds")
    args = parser.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
