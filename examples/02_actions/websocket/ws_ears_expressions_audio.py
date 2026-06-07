"""Control ears, expression, audio, and special detection over WebSocket.

Purpose:
    Verify non-walking WebSocket control through the Dev-PC WebSocket link.
Risk level:
    Low to medium. The robot may move ears and play audio, but this script does not walk.
Dependencies:
    pip install -e ".[dev_pc_ws]"
Run:
    python examples/02_actions/websocket/ws_ears_expressions_audio.py --bind 0.0.0.0 --port 8766
Expected result:
    The robot changes ear pose, face expression, plays then stops a tone, and toggles special detection.
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

from aidog_sdk import AiDog, DevPcWebSocketHost, EarAction, ExpressionAction, Tone


def send(label: str, fn, delay_s: float) -> None:
    print(label)
    fn()
    if delay_s > 0:
        time.sleep(delay_s)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run WebSocket ears, expression, and audio demo")
    parser.add_argument("--bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--timeout", type=float, default=60.0, help="wait timeout in seconds")
    parser.add_argument(
        "--leave-special-disabled",
        action="store_true",
        help="do not re-enable special detection before exit",
    )
    args = parser.parse_args()

    dog = AiDog()
    host = DevPcWebSocketHost(host=args.bind, port=args.port, dog=dog)
    dog.attach_ws_control(host)
    try:
        host.start()
        print(f"[host] listening ws://{args.bind}:{args.port}; waiting for robot")
        if not host.wait_robot_connected(timeout_s=args.timeout):
            print("[host] timeout waiting for robot")
            return 1
        print("[host] robot connected")

        send("[special] disable", lambda: dog.set_special_detection(False, transport="ws"), 0.8)
        send("[ears] EAR_STAND_LEFT", lambda: dog.send_ear(EarAction.EAR_STAND_LEFT, transport="ws"), 1.2)
        send("[ears] 80 percent", lambda: dog.send_ear_percentage(80, transport="ws"), 1.2)
        send("[expression] HAPPY_01", lambda: dog.send_expression(ExpressionAction.HAPPY_01, transport="ws"), 4.0)
        send("[audio] JEEZ", lambda: dog.send_audio(Tone.JEEZ, transport="ws"), 2.0)
        send("[audio] STOP", lambda: dog.send_audio(Tone.STOP, transport="ws"), 0.3)

        if not args.leave_special_disabled:
            send("[special] enable", lambda: dog.set_special_detection(True, transport="ws"), 0.3)
        return 0
    except KeyboardInterrupt:
        print("\n[host] interrupted")
        return 130
    finally:
        try:
            if host.is_robot_connected:
                dog.send_audio(Tone.STOP, transport="ws")
                if not args.leave_special_disabled:
                    dog.set_special_detection(True, transport="ws")
        except Exception:
            pass
        host.stop()


if __name__ == "__main__":
    raise SystemExit(main())
