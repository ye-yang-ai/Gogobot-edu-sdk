"""Control ears, expressions, and tones.

Purpose:
    Demonstrate non-gait interaction outputs: ears, face expression, and sound.
Risk level:
    Low to medium. The robot may move ears and play audio, but does not walk.
Dependencies:
    pip install -e .
Run:
    python examples/02_actions/bluetooth/ble_ears_expressions_audio.py
Expected result:
    The robot changes ear pose, face expression, and plays then stops a tone.
Exit:
    Wait for the sequence to finish, or press Ctrl+C.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import AiDog, EarAction, ExpressionAction, Tone


def connect_robot(dog: AiDog, name_prefix: str, address: str | None) -> None:
    if address:
        dog.connect(address=address)
    else:
        dog.connect(name_prefix)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ears, expression, and audio demo")
    parser.add_argument("--name-prefix", default="Gogobot", help="BLE name prefix")
    parser.add_argument("--address", default=None, help="BLE address or platform UUID")
    parser.add_argument("--timeout", type=float, default=0.0, help="reserved timeout hint")
    args = parser.parse_args()

    _ = args.timeout
    with AiDog() as dog:
        connect_robot(dog, args.name_prefix, args.address)

        print("[ears] EAR_STAND_LEFT")
        dog.send_ear(EarAction.EAR_STAND_LEFT)
        time.sleep(1.2)

        print("[ears] 80 percent")
        dog.send_ear_percentage(80)
        time.sleep(1.2)

        print("[expression] HAPPY_01")
        dog.send_expression(ExpressionAction.HAPPY_01)
        time.sleep(4.0)

        print("[audio] JEEZ")
        dog.send_audio(Tone.JEEZ)
        time.sleep(2.0)

        print("[audio] STOP")
        dog.send_audio(Tone.STOP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
