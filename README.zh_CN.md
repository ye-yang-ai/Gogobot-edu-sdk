# Gogobot EDU SDK

[English](README.md) | 中文

![Gogobot EDU Logo](docs/assets/images/logo-text.png)

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
```

详细说明见：[快速开始](docs/quick_start.zh_CN.md)。

## 图片和 Demo 视频

真实机器狗图片和 demo 视频建议统一放在 `docs/assets/` 下。SDK 文档需要让用户看到真实设备和代码运行效果，而不是只有 API 表。

### 图片预览

| 机器狗 | 文字 Logo | 图标 Logo |
|---|---|---|
| ![Gogobot EDU 机器狗](docs/assets/images/gogo-readme.jpg) | ![Gogobot EDU 文字 Logo](docs/assets/images/logo-text.png) | ![Gogobot EDU 图标 Logo](docs/assets/images/logo2.png) |

| 素材 | 用途 | 路径 |
|---|---|---|
| 机器狗整体图原图 | 高清源图 | `docs/assets/images/gogo.png` |
| 机器狗整体图 README 版 | 轻量预览图 | `docs/assets/images/gogo-readme.jpg` |
| 文字 Logo | README 品牌头图 | `docs/assets/images/logo-text.png` |
| 图标 Logo | 文档、包和课程平台标识 | `docs/assets/images/logo2.png` |
| 快速动作 demo | 坐下、握手、表情、音效 | `docs/assets/demos/quick_start_actions.*` |
| 方向运动 demo | 前进、后退、左转、右转、停止 | `docs/assets/demos/movement_demo.*` |
| 传感器 demo | IMU / TOF 终端数据流和机器狗状态 | `docs/assets/demos/imu_tof_stream.*` |

视频建议：短 GIF/WebP 可以放仓库；较大的 MP4 建议放 Release assets、官网 CDN 或视频平台，再从 README 和文档链接过去。

## 示例

| 文件 | 用途 | 风险等级 |
|---|---|---|
| `examples/01_connect.py` | 扫描、列出设备、按地址连接 | 低 |
| `examples/02_actions.py` | 动作、耳朵、表情、提示音 | 中 |
| `examples/03_movement.py` | 方向运动 | 中 |
| `examples/04_audio_ws_bidirectional_host.py` | 双向 PCM WebSocket 上位机 | 低 |
| `examples/05_imu_read.py` | 订阅 `ae04` IMU JSON | 低 |
| `examples/06_tof_read.py` | 订阅 `ae04` TOF JSON | 低 |
| `examples/07_Servo_Control.py` | 机身 / 足端 / 关节平滑调节 | 高 |
| `examples/08_sensor_ws_lan.py` | 局域网 WebSocket 接收 IMU/TOF | 低 |

完整示例索引见：[示例说明](docs/examples.md)。

## 文档

- [快速开始](docs/quick_start.zh_CN.md)
- [BLE 连接说明](docs/connection_ble.md)
- [API 参考](docs/api_reference.md)
- [BLE 协议参考](docs/protocol_ble.md)
- [Dev PC WebSocket](docs/dev_pc_websocket.md)
- [固件兼容说明](docs/firmware_compatibility.md)
- [安全说明](docs/safety.md)
- [故障排查](docs/troubleshooting.md)
- [Demo 素材说明](docs/assets/demos/README.md)

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
