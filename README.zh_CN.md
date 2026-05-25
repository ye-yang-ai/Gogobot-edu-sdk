# Gogobot EDU SDK

[English](README.md) | 中文

<img src="docs/assets/images/logo-text.png" alt="Gogobot EDU Logo" width="260">

**Changba AI-Dog / Gogobot EDU** 机器狗 Python 编程 SDK。它面向教育、课程平台、实验室和开发者，提供蓝牙连接、动作控制、动作编排、传感器读取、局域网 WebSocket、音频链路和高级姿态调节等能力。

![Gogobot EDU 机器狗](docs/assets/images/gogo-readme.jpg)

## 核心能力

- BLE 扫描、连接、控制指令发送和通知解析。
- 动作、耳朵、表情、提示音和方向运动控制。
- 通过 BLE `ae04` 通知读取 IMU / TOF 传感器数据。
- 通过 Dev PC WebSocket 在局域网接收传感器 JSON 和双向 PCM 音频。
- 面向高级动作编排的机身、足端、关节平滑调节 API。
- 面向教师、学生、实验室和课程平台的示例脚本。

## 环境要求

- Python >= 3.9
- 电脑支持蓝牙
- `bleak >= 0.21`
- 可选音频/局域网依赖：
  - `websockets`
  - `sounddevice`
  - `numpy`

## 安装

```bash
cd aidog_sdk
pip install -e .
```

可选依赖：

```bash
pip install -e ".[dev_pc_ws]"
pip install -e ".[bidir_audio]"
```

开发工具依赖：

```bash
pip install -e ".[dev]"
```

常用检查命令：

```bash
pytest
ruff check .
mypy aidog_sdk
python -m build
twine check dist/*
```

## 快速开始

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
    dog.set_volume(3, verify_tone=Tone.BEAT1)
```

详细说明见：[快速开始](docs/quick_start.zh_CN.md)。

## 日志

SDK 库代码使用 Python `logging` 输出信息，默认不主动配置日志处理器。
需要查看连接信息时，可以在应用入口打开日志：

```python
import logging

logging.basicConfig(level=logging.INFO)
```

排查 BLE 扫描和通知订阅细节时，可以改用 `logging.DEBUG`。

## 示例

| 文件 | 用途 | 风险等级 |
|---|---|---|
| `examples/01_connection/scan_and_connect.py` | 扫描、列出设备、按地址连接 | 低 |
| `examples/02_actions/basic_actions.py` | 执行一个高级动作 | 中 |
| `examples/02_actions/ears_expressions_audio.py` | 耳朵、表情、提示音 | 低/中 |
| `examples/03_movement/directional_move.py` | 方向运动 | 中 |
| `examples/04_sensors/imu_ble_read.py` | 通过 BLE `ae04` 订阅 IMU JSON | 低 |
| `examples/04_sensors/tof_ble_read.py` | 通过 BLE `ae04` 订阅 TOF JSON | 低 |
| `examples/04_sensors/imu_ws_lan_read.py` | 通过局域网 WebSocket 接收 IMU | 低 |
| `examples/04_sensors/tof_ws_lan_read.py` | 通过局域网 WebSocket 接收 TOF | 低 |
| `examples/05_audio/bidirectional_pcm_ws_host.py` | 双向 PCM WebSocket 上位机 | 低 |
| `examples/05_audio/set_volume.py` | 通过 BLE 设置扬声器音量 | 低 |
| `examples/06_robot_adjust/safe_pose_adjust.py` | 机身 / 足端 / 关节平滑调节 | 高 |

完整示例索引见：[示例说明](examples/README.md)。

## 文档

- [快速开始](docs/quick_start.zh_CN.md)
- [BLE 连接说明](docs/connection_ble.md)
- [API 参考](docs/api_reference.md)
- [动作参数类型](docs/action_parameter_types.md)
- [BLE 协议参考](docs/protocol_ble.md)
- [Dev PC WebSocket](docs/dev_pc_websocket.md)
- [固件兼容说明](docs/firmware_compatibility.md)
- [安全说明](docs/safety.md)
- [故障排查](docs/troubleshooting.md)

## 项目结构

```text
aidog_sdk/
├─ aidog_sdk/                 # Python SDK 包
├─ examples/                  # 可运行的 EDU 示例
├─ tools/                     # 工具脚本
├─ docs/                      # 用户、协议、安全和素材文档
├─ README.md                  # 英文入口
├─ README.zh_CN.md            # 中文入口
└─ pyproject.toml             # Python 打包元数据
```

## License

Apache-2.0。见 [LICENSE](LICENSE)。
