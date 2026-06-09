# Gogobot EDU SDK

[English](README.md) | [中文](README.zh_CN.md)

<img src="docs/assets/images/logo-text.png" alt="Gogobot EDU logo" width="260">

Python SDK for the **Changba AI-Dog / Gogobot EDU** quadruped robot. It provides a simple synchronous API for classroom programming, BLE robot control, action choreography, sensor streaming, and optional Dev PC WebSocket audio/sensor workflows.

![Gogobot EDU robot](docs/assets/images/gogo-readme.jpg)

## Highlights

- BLE scan, connect, command, and notification handling.
- High-level actions, ears, expressions, tones, and movement control.
- IMU and TOF sensor streaming through BLE `ae04` notifications.
- Dev PC WebSocket host for LAN sensor JSON and bidirectional PCM audio.
- Smooth pose, foot, and joint adjustment APIs for advanced choreography.
- PC-side pygame mini games for keyboard and robot IMU interaction.
- EDU-oriented examples for teachers, students, labs, and course platforms.

## Requirements

- Python >= 3.9
- BLE support on the host computer
- `bleak >= 0.21`
- Optional audio/LAN dependencies:
  - `websockets`
  - `sounddevice`
  - `numpy`
- Optional mini-game dependency:
  - `pygame`

## Installation

```bash
cd aidog_sdk
pip install -e .
```

Optional extras:

```bash
pip install -e ".[dev_pc_ws]"
pip install -e ".[bidir_audio]"
```

Development tools:

```bash
pip install -e ".[dev]"
```

Common checks:

```bash
pytest
ruff check .
mypy aidog_sdk
python -m build
twine check dist/*
```

## Quick Start

```python
from aidog_sdk import AiDog, Action, EarAction, ExpressionAction, Tone, Movement

with AiDog() as dog:
    dog.connect("Gogobot", retries=3, retry_delay_s=1.0)

    dog.perform_action(Action.SIT_DOWN)
    dog.perform_action("shake_hand")

    dog.send_movement(Movement.FORWARD, duration_s=2.0)
    dog.stop_movement()

    dog.send_ear(EarAction.EAR_STAND_LEFT)
    dog.send_expression(ExpressionAction.HAPPY_01)
    dog.send_audio(Tone.JEEZ)
    dog.set_volume(3, verify_tone=Tone.BEAT1)
```

More setup details: [Quick Start](docs/quick_start.en.md).

## Logging

The SDK uses Python `logging` for library messages and does not configure
handlers by default. Enable logs in your application when needed:

```python
import logging

logging.basicConfig(level=logging.INFO)
```

Use `logging.DEBUG` when troubleshooting BLE discovery and notification setup.

## Examples

| File | Purpose | Risk |
|---|---|---|
| `examples/01_connection/bluetooth/ble_scan_and_connect.py` | Scan, list devices, connect by address | Low |
| `examples/02_actions/bluetooth/ble_basic_actions.py` | Run one high-level action | Medium |
| `examples/02_actions/bluetooth/ble_ears_expressions_audio.py` | Ears, expressions, tones | Low/Medium |
| `examples/03_movement/bluetooth/ble_directional_move.py` | Directional movement | Medium |
| `examples/04_sensors/bluetooth/ble_imu_read.py` | Subscribe to IMU JSON over BLE `ae04` | Low |
| `examples/04_sensors/bluetooth/ble_tof_read.py` | Subscribe to TOF JSON over BLE `ae04` | Low |
| `examples/04_sensors/websocket/ws_imu_lan_read.py` | IMU over LAN via Dev PC WebSocket | Low |
| `examples/04_sensors/websocket/ws_tof_lan_read.py` | TOF over LAN via Dev PC WebSocket | Low |
| `examples/05_audio/bidirectional_pcm_ws_host.py` | Bidirectional PCM WebSocket host | Low |
| `examples/05_audio/set_volume.py` | Set speaker volume over BLE | Low |
| `examples/06_robot_adjust/safe_pose_adjust.py` | Smooth pose / foot / joint adjustment | High |

Full example index: [Examples](examples/README.md).

## Mini Games

The `game/` directory includes Balance Ball, Brick Breaker, and Space Fighter demos. Start with keyboard mode, then switch to BLE or WebSocket IMU control after the window opens correctly.

```bash
pip install pygame
python game/balance_ball/aidog_balance_ball_game.py --transport keyboard
python game/brick_breaker/aidog_brick_breaker_game.py --transport keyboard
python game/space_fighter/aidog_space_fighter_game.py
```

See [Mini Games](docs/games.md) for IMU setup, commands, and common options.

## Documentation

- [Quick Start](docs/quick_start.en.md)
- [Mini Games](docs/games.md)
- [Demo Videos](docs/demo_videos.md)
- [BLE Connection Guide](docs/connection_ble.md)
- [API Reference](docs/api_reference.md)
- [Action Parameter Types](docs/action_parameter_types.md)
- [BLE Protocol Reference](docs/protocol_ble.md)
- [Dev PC WebSocket](docs/dev_pc_websocket.md)
- [Firmware Compatibility](docs/firmware_compatibility.md)
- [Safety Guide](docs/safety.md)
- [Troubleshooting](docs/troubleshooting.md)

## Project Layout

```text
aidog_sdk/
├─ aidog_sdk/                 # Python SDK package
├─ examples/                  # Runnable EDU examples
├─ game/                      # PC-side mini games
├─ tools/                     # Utility scripts
├─ docs/                      # User, protocol, safety, and asset docs
├─ README.md                  # English entry
├─ README.zh_CN.md            # Chinese entry
└─ pyproject.toml             # Packaging metadata
```

## License

Apache-2.0. See [LICENSE](LICENSE).
