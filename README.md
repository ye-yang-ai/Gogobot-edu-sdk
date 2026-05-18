# Gogobot EDU SDK

[English](README.md) | [中文](README.zh_CN.md)

![Gogobot EDU logo](docs/assets/images/logo-text.png)

Python SDK for the **Changba AI-Dog / Gogobot EDU** quadruped robot. It provides a simple synchronous API for classroom programming, BLE robot control, action choreography, sensor streaming, and optional Dev PC WebSocket audio/sensor workflows.

![Gogobot EDU robot](docs/assets/images/gogo-readme.jpg)

## Highlights

- BLE scan, connect, command, and notification handling.
- High-level actions, ears, expressions, tones, and movement control.
- IMU and TOF sensor streaming through BLE `ae04` notifications.
- Dev PC WebSocket host for LAN sensor JSON and bidirectional PCM audio.
- Smooth pose, foot, and joint adjustment APIs for advanced choreography.
- EDU-oriented examples for teachers, students, labs, and course platforms.

## Requirements

- Python >= 3.9
- BLE support on the host computer
- `bleak >= 0.21`
- Optional audio/LAN dependencies:
  - `websockets`
  - `sounddevice`
  - `numpy`

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

## Quick Start

```python
from aidog_sdk import AiDog, Action, EarAction, ExpressionAction, Tone, Movement

with AiDog() as dog:
    dog.connect("Changba-Ai-Dog", retries=3, retry_delay_s=1.0)

    dog.perform_action(Action.SIT_DOWN)
    dog.perform_action("shake_hand")

    dog.send_movement(Movement.FORWARD, duration_s=2.0)
    dog.stop_movement()

    dog.send_ear(EarAction.EAR_STAND_LEFT)
    dog.send_expression(ExpressionAction.HAPPY_01)
    dog.send_audio(Tone.JEEZ)
```

More setup details: [Quick Start](docs/quick_start.en.md).

## Demo Materials

Real robot images and demo videos should be kept under `docs/assets/` so the SDK landing page shows the actual device behavior, not only API text.

### Image Preview

| Robot | Text Logo | Icon Logo |
|---|---|---|
| ![Gogobot EDU robot](docs/assets/images/gogo-readme.jpg) | ![Gogobot EDU text logo](docs/assets/images/logo-text.png) | ![Gogobot EDU icon logo](docs/assets/images/logo2.png) |

| Material | Purpose | Path |
|---|---|---|
| Product photo, original | High-resolution source image | `docs/assets/images/gogo.png` |
| Product photo, README | Lightweight README preview | `docs/assets/images/gogo-readme.jpg` |
| Text logo | README brand header | `docs/assets/images/logo-text.png` |
| Icon logo | Docs and package branding | `docs/assets/images/logo2.png` |
| Action demo | Sit, shake hand, expression, sound | `docs/assets/demos/quick_start_actions.*` |
| Movement demo | Forward, back, left, right, stop | `docs/assets/demos/movement_demo.*` |
| Sensor demo | IMU / TOF terminal stream with robot motion | `docs/assets/demos/imu_tof_stream.*` |

Video guidance: keep short GIF/WebP previews in the repository when possible; place large MP4 files in release assets, an official CDN, or a video platform and link them from the docs.

## Examples

| File | Purpose | Risk |
|---|---|---|
| `examples/01_connect.py` | Scan, list devices, connect by address | Low |
| `examples/02_actions.py` | Actions, ears, expressions, tones | Medium |
| `examples/03_movement.py` | Directional movement | Medium |
| `examples/04_audio_ws_bidirectional_host.py` | Bidirectional PCM WebSocket host | Low |
| `examples/05_imu_read.py` | Subscribe to IMU JSON on `ae04` | Low |
| `examples/06_tof_read.py` | Subscribe to TOF JSON on `ae04` | Low |
| `examples/07_Servo_Control.py` | Smooth pose / foot / joint adjustment | High |
| `examples/08_sensor_ws_lan.py` | IMU/TOF over LAN via Dev PC WebSocket | Low |

Full example index: [Examples](docs/examples.md).

## Documentation

- [Quick Start](docs/quick_start.en.md)
- [BLE Connection Guide](docs/connection_ble.md)
- [API Reference](docs/api_reference.md)
- [BLE Protocol Reference](docs/protocol_ble.md)
- [Dev PC WebSocket](docs/dev_pc_websocket.md)
- [Firmware Compatibility](docs/firmware_compatibility.md)
- [Safety Guide](docs/safety.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Demo Asset Guide](docs/assets/demos/README.md)

## Project Layout

```text
aidog_sdk/
├─ aidog_sdk/                 # Python SDK package
├─ examples/                  # Runnable EDU examples
├─ tools/                     # Utility scripts
├─ docs/                      # User, protocol, safety, and asset docs
├─ README.md                  # English entry
├─ README.zh_CN.md            # Chinese entry
└─ pyproject.toml             # Packaging metadata
```

## License

Apache-2.0. See [LICENSE](LICENSE).
