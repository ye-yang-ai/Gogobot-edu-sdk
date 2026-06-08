# 快速开始

本指南用于让 Gogobot EDU / Changba AI-Dog 机器狗完成第一次连接和安全动作测试。

## 1. 准备机器狗

- 将机器狗放在平整、空旷的地面。
- 运行运动示例前，确认周围有足够空间。
- 确认机器狗已开机，并且电脑在蓝牙范围内。
- 运行动作和运动示例时，确保你可以随时停止机器狗。

## 2. 安装 SDK

```bash
cd aidog_sdk
pip install -e .
```

可选依赖：

```bash
pip install -e ".[dev_pc_ws]"
pip install -e ".[bidir_audio]"
```

## 3. 扫描和连接 BLE

扫描设备：

```python
from aidog_sdk import AiDog

with AiDog() as dog:
    devices = dog.scan("Gogobot")
    print(devices)
```

按设备名前缀连接：

```python
from aidog_sdk import AiDog

with AiDog() as dog:
    dog.connect("Gogobot", retries=3, retry_delay_s=1.0)
    print("connected")
```

按已知蓝牙地址连接：

```python
dog.connect(address="AA:BB:CC:DD:EE:FF", retries=3, retry_delay_s=1.0)
```

## 4. 运行一个安全动作

```python
from aidog_sdk import AiDog, Action

with AiDog() as dog:
    dog.connect("Gogobot")
    ok = dog.perform_action(Action.SIT_DOWN, timeout_s=12.0)
    print("action_done:", ok)
```

## 5. 使用 WebSocket 控制

如果固件已经配置 Dev PC WebSocket，PC 侧可以像示例一样启动 WebSocket host，等待机器狗连入：

```python
from aidog_sdk import AiDog, DevPcWebSocketHost, Action, Movement, Tone

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

也可以直接打开 WebSocket 图形上位机：

```bash
python tools/user_control_ws.py
```

该工具的连接方式与 WebSocket examples 一致：PC 侧监听 `0.0.0.0:8766`，机器狗作为 WebSocket client 连入。

## 6. 下一步示例

- `examples/01_connection/bluetooth/ble_scan_and_connect.py`：BLE 扫描和连接。
- `examples/01_connection/websocket/ws_connection_test.py`：等待机器狗连接 PC WebSocket host。
- `examples/02_actions/bluetooth/ble_basic_actions.py`：执行一个高层动作。
- `examples/02_actions/websocket/ws_basic_actions.py`：通过 WebSocket 执行动作。
- `examples/02_actions/bluetooth/ble_ears_expressions_audio.py`：耳朵、表情和提示音。
- `examples/02_actions/websocket/ws_ears_expressions_audio.py`：通过 WebSocket 控制耳朵、表情、音效和特殊状态检测。
- `examples/03_movement/bluetooth/ble_directional_move.py`：BLE 方向运动。
- `examples/03_movement/websocket/ws_directional_move.py`：WebSocket 方向运动。
- `examples/04_sensors/bluetooth/ble_imu_read.py`：BLE IMU 数据流。
- `examples/04_sensors/bluetooth/ble_tof_read.py`：BLE TOF 数据流。
- `examples/04_sensors/websocket/ws_imu_lan_read.py`：WebSocket IMU 数据流。
- `examples/04_sensors/websocket/ws_tof_lan_read.py`：WebSocket TOF 数据流。
- `tools/user_control_ble.py`：BLE 图形上位机。
- `tools/user_control_ws.py`：WebSocket 图形上位机。

运行运动或高级姿态调节示例前，请先阅读 [安全说明](safety.md)。
