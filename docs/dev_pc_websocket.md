# Dev PC WebSocket

Some firmware builds can connect to a PC-side WebSocket server for LAN sensor data and bidirectional PCM audio.

## Firmware Configuration

In firmware `app_config.h`:

```c
#define DEV_PC_AUDIO_WS_ENABLE 1
#define DEV_PC_AUDIO_WS_URL "ws://<PC_LAN_IP>:8765"
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

host = DevPcWebSocketHost(host="0.0.0.0", port=8765, dog=dog, on_imu=on_imu)
host.start()
```

Example:

```bash
python examples/08_sensor_ws_lan.py --bind 0.0.0.0 --port 8765
```

## Bidirectional PCM Audio

Binary WebSocket frames are raw PCM:

- 16 kHz
- 16-bit signed little-endian
- mono

Example:

```bash
python examples/04_audio_ws_bidirectional_host.py --bind 0.0.0.0 --port 8765
```

Use `python -c "import sounddevice as sd; print(sd.query_devices())"` to inspect audio device indices.
