# Quick Start

This guide gets a Gogobot EDU / Changba AI-Dog robot connected and running a safe first action.

## 1. Prepare the Robot

- Put the robot on a flat, open floor.
- Keep enough space around the robot before running movement examples.
- Make sure the robot is powered on and within BLE range.
- Use action and movement examples only when you can stop the robot safely.

## 2. Install the SDK

```bash
cd aidog_sdk
pip install -e .
```

Optional dependencies:

```bash
pip install -e ".[dev_pc_ws]"
pip install -e ".[bidir_audio]"
```

## 3. Scan and Connect

```python
from aidog_sdk import AiDog

with AiDog() as dog:
    devices = dog.scan("Gogobot")
    print(devices)
```

Connect by name prefix:

```python
from aidog_sdk import AiDog

with AiDog() as dog:
    dog.connect("Gogobot", retries=3, retry_delay_s=1.0)
    print("connected")
```

Connect by known BLE address:

```python
dog.connect(address="AA:BB:CC:DD:EE:FF", retries=3, retry_delay_s=1.0)
```

## 4. Run a Safe Action

```python
from aidog_sdk import AiDog, Action

with AiDog() as dog:
    dog.connect("Gogobot")
    ok = dog.perform_action(Action.SIT_DOWN, timeout_s=12.0)
    print("action_done:", ok)
```

## 5. Next Examples

- `examples/01_connection/bluetooth/ble_scan_and_connect.py`: BLE scan and connection.
- `examples/02_actions/bluetooth/ble_basic_actions.py`: one high-level action.
- `examples/02_actions/bluetooth/ble_ears_expressions_audio.py`: ears, expressions, and tones.
- `examples/03_movement/bluetooth/ble_directional_move.py`: directional movement.
- `examples/04_sensors/bluetooth/ble_imu_read.py`: BLE IMU stream.
- `examples/04_sensors/bluetooth/ble_tof_read.py`: BLE TOF stream.

Read [Safety Guide](safety.md) before running movement or robot adjustment examples.
