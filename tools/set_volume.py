#!/usr/bin/env python3
"""
Set the robot volume over BLE, with an optional verification tone.

Usage examples:
1) Specify BLE device address:
   python tools/set_volume.py --address AA:BB:CC:DD:EE:FF 3

2) Auto-scan by BLE device name prefix:
   python tools/set_volume.py --name-prefix Gogobot 3

3) Set volume without playing a verification tone:
   python tools/set_volume.py --no-verify 3

The tool writes a JSON configuration payload to the ae01 characteristic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SDK_ROOT = Path(__file__).resolve().parents[1]
if str(SDK_ROOT) not in sys.path:
    sys.path.insert(0, str(SDK_ROOT))

from aidog_sdk import AiDog, Tone  # noqa: E402


def parse_tone(value: str) -> Tone:
    text = value.strip()
    try:
        if text.isdigit():
            return Tone(int(text))
        return Tone[text.upper()]
    except (KeyError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"unknown tone: {value}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Set AI-Dog volume over BLE")
    parser.add_argument("volume", type=int, choices=range(0, 5), metavar="0-4", help="volume level, 0=mute, 4=max")
    parser.add_argument("--address", help="BLE device address, e.g. AA:BB:CC:DD:EE:FF")
    parser.add_argument("--name-prefix", default="Gogobot", help="device name prefix used for scanning")
    parser.add_argument("--tone", type=parse_tone, default=Tone.AGREE, help="verification tone name or id")
    parser.add_argument("--no-verify", action="store_true", help="do not play a verification tone")
    args = parser.parse_args()

    try:
        with AiDog() as dog:
            if args.address:
                dog.connect(address=args.address)
            else:
                dog.connect(args.name_prefix)
            verify_tone = None if args.no_verify else args.tone
            dog.set_volume(args.volume, verify_tone=verify_tone)
            if verify_tone is None:
                print(f"[OK] Volume set to {args.volume}")
            else:
                print(f"[OK] Volume set to {args.volume}, verification tone: {verify_tone.name}")
        return 0
    except (KeyError, ValueError) as exc:
        print(f"[ERROR] Invalid tone: {exc}")
        return 2
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
