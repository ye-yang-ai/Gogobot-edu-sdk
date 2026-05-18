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
    devices = dog.scan("Changba-Ai-Dog")
    print(devices)
```

Connect by name prefix:

```python
from aidog_sdk import AiDog

with AiDog() as dog:
    dog.connect("Changba-Ai-Dog", retries=3, retry_delay_s=1.0)
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
    dog.connect("Changba-Ai-Dog")
    ok = dog.perform_action(Action.SIT_DOWN, timeout_s=12.0)
    print("action_done:", ok)
```

## 5. Next Examples

- `examples/01_connect.py`: BLE scan and connection.
- `examples/02_actions.py`: actions, ears, expressions, and tones.
- `examples/03_movement.py`: directional movement.
- `examples/05_imu_read.py`: IMU stream.
- `examples/06_tof_read.py`: TOF stream.

Read [Safety Guide](safety.md) before running movement or robot adjustment examples.
