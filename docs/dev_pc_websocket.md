# Dev PC WebSocket

Some firmware builds can connect to a PC-side WebSocket server for LAN sensor data and bidirectional PCM audio.

## Firmware Configuration

In firmware `app_config.h`:

```c
#define DEV_PC_AUDIO_WS_ENABLE 1
#define DEV_PC_AUDIO_WS_URL "ws://<PC_LAN_IP>:8766"
```

The PC and robot must be on the same LAN, and the port must match the host script.

## Install Dependencies

```bash
pip install -e ".[dev_pc_ws]"
```

For bidirectional audio:

```bash
pip install -e ".[bidir_audio]"
```

## Sensor JSON Host

```python
from aidog_sdk import AiDog, DevPcWebSocketHost

dog = AiDog()

def on_imu(imu: dict):
    print("imu", imu)

host = DevPcWebSocketHost(host="0.0.0.0", port=8766, dog=dog, on_imu=on_imu)
host.start()
```

Examples:

```bash
python examples/04_sensors/websocket/ws_imu_lan_read.py --bind 0.0.0.0 --port 8766
python examples/04_sensors/websocket/ws_tof_lan_read.py --bind 0.0.0.0 --port 8766
```

## Control over WebSocket

WebSocket control uses text JSON frames carrying the same raw packet that BLE writes to `ae03`. The firmware dispatches it through the existing remote-control parser, so action, ear, expression, audio, special detection, movement, and sensor stream commands keep BLE-compatible behavior. Config commands such as volume use `config_json`, which wraps the same JSON payload used by the BLE config channel.

High-level SDK usage:

```python
from aidog_sdk import Action, AiDog, DevPcWebSocketHost, Movement, Tone

dog = AiDog()
host = DevPcWebSocketHost(host="0.0.0.0", port=8766, dog=dog)
host.start()
host.wait_robot_connected()
dog.attach_ws_control(host)

dog.send_audio(Tone.JEEZ, transport="ws")
dog.send_interaction(Action.SHAKE_HAND, transport="ws")
dog.send_movement(Movement.FORWARD, duration_s=2, transport="ws")
dog.stop_movement(transport="ws")
```

The default transport remains BLE, so existing code such as `dog.send_audio(Tone.JEEZ)` is unchanged.

Control examples:

```bash
python examples/02_actions/websocket/ws_ears_expressions_audio.py --bind 0.0.0.0 --port 8766
python examples/02_actions/websocket/ws_basic_actions.py --action sit_down --yes
python examples/03_movement/websocket/ws_directional_move.py --direction forward --duration 2 --yes
```

## WebSocket User Control Panel

`tools/user_control_ws.py` provides a Tkinter upper-computer panel that mirrors the BLE control panel layout while using the Dev-PC WebSocket link.

Run:

```bash
python tools/user_control_ws.py
```

Workflow:

1. Flash firmware with Dev-PC WebSocket enabled and configured to connect to the PC.
2. Start the panel and click `Wait Connect`.
3. The panel listens on `ws://0.0.0.0:8766` by default, matching the WebSocket examples.
4. After the robot connects, use the same pages as the BLE panel for movement, actions, ears, expressions, audio, special detection, and sensor plots.

The volume page uses WebSocket `config_json`, which wraps the same config payload that BLE writes to the firmware config channel.

## Bidirectional PCM Audio

Binary WebSocket frames are raw PCM:

- 16 kHz
- 16-bit signed little-endian
- mono

Example:

```bash
python examples/05_audio/bidirectional_pcm_ws_host.py --bind 0.0.0.0 --port 8766
```

Use `python -c "import sounddevice as sd; print(sd.query_devices())"` to inspect audio device indices.
