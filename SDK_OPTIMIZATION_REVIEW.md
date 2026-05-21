# AIDog EDU SDK 对标优化建议

参考日期：2026-05-18  
本报告基于当前仓库 `C:\C_project_3.1\arbitrarion4\aidog_sdk`，并对照以下公开项目：

- Unitree SDK2 Python: <https://github.com/unitreerobotics/unitree_sdk2_python>
- AgiBot X1 Train: <https://github.com/AgibotTech/agibot_x1_train>

## 1. 参考项目给出的信号

### 1.1 Unitree SDK2 Python

宇树的 SDK 文档非常直接，重点不是包装成课程项目，而是让开发者快速接入真实机器人：

- README 首屏先说明项目定位、安装方式和系统依赖。
- 把安装失败的高频问题放进 FAQ，例如 `cyclonedds` 路径、环境变量、源码编译路径。
- 示例按功能域组织：DDS 通信、高层状态与控制、低层状态与电机控制、遥控器状态、前置相机、避障、灯光音量等。
- 文档不断提醒真实机器人运行前的网络配置、网卡名替换、运动服务冲突和安全参数。
- 目录中同时存在 SDK 主包、通信核心、IDL/RPC、工具模块、机器人型号模块、example 模块，结构明确面向长期维护。

对本项目的启发：AIDog SDK 也应强调“真实设备开发入口”和“风险边界”，而不是只展示 API 表。安装、连接、固件兼容、示例运行、安全停机、问题排查要形成闭环。

### 1.2 AgiBot X1 Train

智元项目虽然不是机器狗 SDK，但它的开源工程呈现更接近企业项目：

- README 顶部提供 `English | 中文` 切换，英文和中文文档分离维护。
- 开头有项目简介、产品链接和真实图片，建立产品可信度。
- 快速开始按步骤写清依赖、命令、产物路径。
- 对命令行参数有独立说明，便于开发者理解脚本行为。
- 有“添加新环境”这类扩展指南，不只告诉用户怎么跑，还告诉用户怎么扩展。
- 目录结构单独成章，说明每个目录的职责。
- README 底部保留参考项目，显得工程来源和技术脉络清楚。

对本项目的启发：AIDog EDU SDK 应把中英文 README 分离，并补充产品图、连接拓扑、扩展指南、参数说明和参考资料，而不是把所有内容堆在一个长 README 中。

## 2. 当前仓库观察

当前结构：

```text
aidog_sdk/
├─ aidog_sdk/
│  ├─ __init__.py
│  ├─ _ble.py
│  ├─ actions.py
│  ├─ dev_pc_ws.py
│  └─ dog.py
├─ examples/
├─ tools/
├─ README.md
├─ pyproject.toml
├─ LICENSE
└─ __init__.py
```

优点：

- 包结构轻，核心 API 集中在 `AiDog`，对 EDU 用户友好。
- `examples/` 已覆盖连接、动作、运动、音频、IMU、TOF、舵机控制、局域网传感器等真实功能。
- `pyproject.toml` 已有基础打包配置和可选依赖。
- `python -m compileall aidog_sdk examples tools` 通过，当前语法层面没有阻塞问题。
- README 已包含英文和中文说明、安装、快速开始、示例列表、API 表、BLE 协议参考。

主要不足：

- README 过长，英文和中文混在一个文件里，维护成本高，也不符合智元这类项目的中英文分离习惯。
- 缺少 `docs/` 文档体系，协议、固件配置、故障排查、安全说明、API 参考都堆在 README。
- 示例文件是扁平列表，例如 `07_Servo_Control.py` 命名风格与其他示例不一致，不利于后续扩展成教学/企业 SDK。
- 缺少测试目录、CI、lint、format、类型检查、pre-commit 等工程质量入口。
- SDK 库代码里直接 `print` 状态信息，企业级 SDK 更适合使用 `logging`，让调用方控制输出等级。
- 多处 `except Exception: pass` 会吞掉真实错误，调试 BLE/WebSocket/传感器问题时不够透明。
- `pyproject.toml` 元数据偏少，缺少 `project.urls`、classifiers、authors、keywords、`py.typed` 等发布信号。
- 缺少版本变更记录、贡献说明、安全说明、兼容矩阵和故障排查清单。

## 3. 优先级优化清单

### P0：先把“企业级 SDK 门面”立起来

1. 拆分中英文 README。
   - 顶层 `README.md` 保留英文。
   - 新增 `README.zh_CN.md` 保留中文。
   - 两个文件顶部互相链接：`English | 中文`。
   - README 只保留项目介绍、安装、最快连接、示例索引、文档入口，不再承载完整协议手册。

2. 新增 `docs/` 文档目录。

   推荐文件：

   ```text
   docs/
   ├─ quick_start.zh_CN.md
   ├─ quick_start.en.md
   ├─ connection_ble.md
   ├─ dev_pc_websocket.md
   ├─ protocol_ble.md
   ├─ api_reference.md
   ├─ firmware_compatibility.md
   ├─ safety.md
   ├─ troubleshooting.md
   └─ examples.md
   ```

3. 增加安全和真实设备运行说明。
   - 运行前环境：地面空间、低电量、蓝牙距离、急停方式。
   - 低层/舵机/姿态控制示例要标注风险等级。
   - 明确哪些 API 是“普通教学安全入口”，哪些是“高级调试入口”。

4. 增加产品级首屏内容。
   - 加一张真实机器狗图片或连接拓扑图。
   - 说明 SDK 面向谁：教师、学生、算法开发者、课程平台、实验室。
   - 说明核心能力：BLE 控制、动作编排、传感器读取、局域网 WebSocket、音频、底层扩展。

5. 补充机器狗图片和 demo 视频。
   - README 首屏建议放一张真实机器狗主图，不要只放 logo 或纯文字。
   - 快速开始后建议放 1 个 10 到 20 秒的基础动作 demo，例如连接后执行坐下、握手、摇尾、表情、音效。
   - 示例章节建议放多个短视频或 GIF，对应不同能力：动作编排、方向运动、IMU/TOF 读取、WebSocket 局域网数据、双向音频、姿态调节。
   - 视频素材应优先使用真实机器狗实拍，其次才是仿真或渲染图。EDU SDK 的用户需要看到“代码运行后机器狗真实会怎样动”。
   - 每个视频下面建议标注：对应示例文件、运行命令、固件要求、风险等级、是否需要额外依赖。
   - GitHub README 中不建议直接提交过大的 `.mp4`。推荐把短 GIF/WebP 放仓库，较大的 MP4 放 Release assets、对象存储、官网 CDN 或 B 站/YouTube，并在 README 中链接。

推荐素材目录：

```text
docs/
└─ assets/
   ├─ images/
   │  ├─ aidog_hero.jpg
   │  ├─ ble_connection_topology.png
   │  └─ classroom_setup.jpg
   └─ demos/
      ├─ quick_start_actions.gif
      ├─ movement_demo.gif
      ├─ imu_tof_stream.gif
      ├─ dev_pc_websocket_demo.gif
      ├─ bidirectional_audio_demo.gif
      └─ robot_adjust_demo.gif
```

README 中可以这样引用：

```md
![Gogobot EDU Robot](docs/assets/images/gogo-readme.jpg)

## Demo

| Demo | Example | Preview |
|------|---------|---------|
| Quick start actions | `examples/02_actions/basic_actions.py` | See `docs/assets/demos/README.md` |
| Movement control | `examples/03_movement/directional_move.py` | See `docs/assets/demos/README.md` |
| IMU / TOF stream | `examples/04_sensors/imu_read.py` | See `docs/assets/demos/README.md` |
```

建议 demo 清单：

| 素材 | 内容 | 对应能力 | 建议时长 |
|------|------|----------|----------|
| `aidog_hero.jpg` | 机器狗正面或课堂场景主图 | 产品可信度 | 静态图 |
| `quick_start_actions.gif` | 坐下、握手、表情、音效 | 快速开始 | 10-20 秒 |
| `movement_demo.gif` | 前进、后退、左右、停止 | 运动控制 | 10-15 秒 |
| `imu_tof_stream.gif` | 终端实时输出 IMU/TOF 数据，旁边展示机器狗姿态或遮挡距离变化 | 传感器读取 | 15-25 秒 |
| `dev_pc_websocket_demo.gif` | 局域网 WebSocket 接收传感器 JSON | 上位机通信 | 15-25 秒 |
| `bidirectional_audio_demo.gif` | PC 麦克风/扬声器与机器狗音频链路 | 音频能力 | 15-25 秒 |
| `robot_adjust_demo.gif` | 低幅度姿态/足端调整，带安全提示 | 高级控制 | 10-15 秒 |

素材规范：

- 图片宽度建议 1280px 或 1600px，README 中显示清晰但文件不要过大。
- GIF 建议控制在 5 MB 以内；超过后改用 WebP、MP4 外链或 Release asset。
- 文件名使用小写蛇形命名。
- 不要把无关宣传片塞进 README，demo 应与 SDK 示例一一对应。
- 视频里最好同时出现机器人实拍和终端命令/输出，这比纯动作展示更有开发者说服力。

### P1：重组示例，让用户一眼知道该跑哪个

建议把 `examples/` 从扁平文件改成按功能域组织：

```text
examples/
├─ 01_connection/
│  ├─ scan_and_connect.py
│  └─ connect_by_address.py
├─ 02_actions/
│  ├─ basic_actions.py
│  ├─ ears_expressions_audio.py
│  └─ choreography.py
├─ 03_movement/
│  ├─ directional_move.py
│  └─ timed_move.py
├─ 04_sensors/
│  ├─ imu_read.py
│  ├─ tof_read.py
│  └─ sensor_ws_lan.py
├─ 05_audio/
│  └─ bidirectional_pcm_ws_host.py
├─ 06_robot_adjust/
│  ├─ safe_pose_adjust.py
│  └─ custom_action.py
└─ README.md
```

每个示例建议统一包含：

- 文件顶部说明：用途、风险等级、依赖、运行命令、预期现象、退出方式。
- 支持命令行参数：`--name-prefix`、`--address`、`--timeout`、`--hz`、`--bind`、`--port`。
- 示例不要默认执行高风险动作，先做连接/状态确认，再让用户显式运行动作。
- 将 `07_Servo_Control.py` 改为小写蛇形命名，例如 `safe_pose_adjust.py`。

### P1：工程规范补齐

建议在 `pyproject.toml` 中加入这些质量工具：

```toml
[project.optional-dependencies]
dev = [
  "pytest",
  "pytest-mock",
  "ruff",
  "mypy",
  "build",
  "twine",
]

[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.9"
warn_unused_ignores = true
warn_return_any = true
```

建议新增：

```text
tests/
├─ test_actions.py
├─ test_protocol_packets.py
├─ test_notify_parsing.py
├─ test_sensor_stream.py
└─ test_dev_pc_ws.py

.github/
└─ workflows/
   └─ ci.yml

CHANGELOG.md
CONTRIBUTING.md
SECURITY.md
```

测试优先覆盖：

- `resolve_action` 的英文、中文、非法值。
- BLE packet 拼包格式 `[0xAA, 0x55, 0x00, mode, ...data]`。
- IMU/TOF JSON 解析和角度归一化。
- `perform_action` 的状态机等待逻辑。
- WebSocket 文本帧和二进制 PCM 分流。

### P1：库代码输出改为 logging

当前 `AiDog.connect()`、`AiDog.disconnect()`、`BleTransport.connect()` 等库方法直接 `print`。建议改成：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Connected to %s", address)
```

这样 SDK 用户可以在自己的应用里选择：

- 完全静默。
- 输出 INFO 日志。
- 调试 BLE 细节时打开 DEBUG。
- 在 GUI/课程平台中把日志接到自己的面板。

示例脚本可以继续 `print`，库本身建议不要直接向 stdout 写内容。

### P1：异常处理要更透明

当前 BLE、WebSocket、notify callback 中存在多处宽泛的 `except Exception: pass`。建议分层处理：

- 用户 callback 异常：捕获后用 `logger.exception` 记录，但不要中断 SDK。
- BLE 连接/写入异常：保留原始异常链，提供上下文。
- JSON 解析异常：可返回空结果，但 DEBUG 日志记录原始文本长度和错误类型。
- WebSocket 连接异常：记录 peer、方向、帧类型。

企业级 SDK 的关键不是“永不报错”，而是“错误可定位、可复现、可解释”。

### P2：发布与兼容性补齐

建议完善 `pyproject.toml`：

```toml
[project]
authors = [{ name = "Changba AI-Dog Team" }]
keywords = ["robotics", "quadruped", "education", "ble", "sdk"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Intended Audience :: Developers",
  "Intended Audience :: Education",
  "License :: OSI Approved :: Apache Software License",
  "Programming Language :: Python :: 3.9",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Topic :: Scientific/Engineering",
]

[project.urls]
Homepage = "..."
Documentation = "..."
Repository = "..."
Issues = "..."
```

建议增加：

- `aidog_sdk/py.typed`：声明类型提示对外可用。
- `CHANGELOG.md`：按版本记录 API、协议、固件兼容变化。
- `firmware_compatibility.md`：列出固件版本、支持的 characteristic、是否支持 `ae04`、`ae10`、WebSocket sensor mirror。
- `troubleshooting.md`：收集蓝牙扫描不到、连接失败、动作不结束、IMU 无数据、WebSocket 连不上、音频设备不可用等问题。

### P2：API 文档和协议文档分离

当前 README 的 API 表已经有价值，但应迁移到独立文档：

- `docs/api_reference.md`：面向 SDK 用户，按连接、动作、运动、传感器、音频、姿态调节分组。
- `docs/protocol_ble.md`：面向固件/底层开发者，说明 packet、mode、characteristic、notify JSON schema。
- `docs/dev_pc_websocket.md`：说明二进制 PCM 和文本传感器帧格式。

README 只放最常用的 3 到 5 个 API，避免越写越长。

## 4. 推荐目标结构

```text
aidog_sdk/
├─ aidog_sdk/
│  ├─ __init__.py
│  ├─ _ble.py
│  ├─ actions.py
│  ├─ dev_pc_ws.py
│  ├─ dog.py
│  └─ py.typed
├─ examples/
│  ├─ README.md
│  ├─ 01_connection/
│  ├─ 02_actions/
│  ├─ 03_movement/
│  ├─ 04_sensors/
│  ├─ 05_audio/
│  └─ 06_robot_adjust/
├─ docs/
│  ├─ assets/
│  │  ├─ images/
│  │  │  ├─ aidog_hero.jpg
│  │  │  ├─ ble_connection_topology.png
│  │  │  └─ classroom_setup.jpg
│  │  └─ demos/
│  │     ├─ quick_start_actions.gif
│  │     ├─ movement_demo.gif
│  │     ├─ imu_tof_stream.gif
│  │     ├─ dev_pc_websocket_demo.gif
│  │     ├─ bidirectional_audio_demo.gif
│  │     └─ robot_adjust_demo.gif
│  ├─ quick_start.zh_CN.md
│  ├─ quick_start.en.md
│  ├─ api_reference.md
│  ├─ protocol_ble.md
│  ├─ dev_pc_websocket.md
│  ├─ firmware_compatibility.md
│  ├─ safety.md
│  └─ troubleshooting.md
├─ tests/
│  ├─ test_actions.py
│  ├─ test_protocol_packets.py
│  ├─ test_notify_parsing.py
│  └─ test_sensor_stream.py
├─ tools/
├─ .github/
│  └─ workflows/
│     └─ ci.yml
├─ README.md
├─ README.zh_CN.md
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ SECURITY.md
├─ LICENSE
└─ pyproject.toml
```

## 5. README 建议大纲

### English README

```md
# Gogobot EDU SDK

English | [中文](README.zh_CN.md)

Python SDK for Gogobot EDU / Changba AI-Dog.

![Gogobot EDU Robot](docs/assets/images/gogo-readme.jpg)

## Highlights
- BLE robot control
- Action choreography
- IMU / TOF sensor streaming
- Dev PC WebSocket for LAN sensor and PCM audio
- Educational examples and low-level extension APIs

## Requirements
...

## Installation
...

## Quick Start
...

## Demo
| Demo | Example | Preview |
|------|---------|---------|
| Quick start actions | `examples/02_actions/basic_actions.py` | See `docs/assets/demos/README.md` |
| Movement control | `examples/03_movement/directional_move.py` | See `docs/assets/demos/README.md` |
| IMU / TOF stream | `examples/04_sensors/imu_read.py` | See `docs/assets/demos/README.md` |

## Examples
...

## Documentation
- Quick start
- API reference
- BLE protocol
- Firmware compatibility
- Troubleshooting
- Safety guide

## License
...
```

### 中文 README

```md
# Gogobot EDU SDK

[English](README.md) | 中文

Gogobot EDU / 唱吧 AI-Dog 的 Python 编程 SDK。

![Gogobot EDU 机器狗](docs/assets/images/gogo-readme.jpg)

## 核心能力
...

## 环境要求
...

## 安装
...

## 快速开始
...

## Demo 演示
| 演示 | 示例 | 预览 |
|------|------|------|
| 快速动作 | `examples/02_actions/basic_actions.py` | See `docs/assets/demos/README.md` |
| 方向运动 | `examples/03_movement/directional_move.py` | See `docs/assets/demos/README.md` |
| IMU / TOF 数据流 | `examples/04_sensors/imu_read.py` | See `docs/assets/demos/README.md` |

## 示例
...

## 文档
...
```

## 6. 代码规范建议

建议制定并写进 `CONTRIBUTING.md`：

- Python 文件、函数、变量使用小写蛇形命名。
- 示例文件统一编号和小写命名，避免 `07_Servo_Control.py` 这类混合风格。
- 公共 API 必须有类型注解和 docstring。
- 协议常量集中管理，避免散落在业务逻辑中。
- SDK 库层使用 `logging`，示例层使用 `print`。
- 禁止无记录地吞异常；必要时 DEBUG 日志记录。
- 新增 API 必须有至少一个示例和至少一个单元测试。
- 涉及真实运动控制的示例必须写明风险等级和停机方式。

## 7. 建议执行顺序

1. 拆分 `README.md` / `README.zh_CN.md`，保留双语互链。
2. 新增 `docs/`，把协议、API、固件兼容、故障排查从 README 中迁出。
3. 新增 `docs/assets/images` 和 `docs/assets/demos`，先放主图、连接拓扑图、快速动作 GIF、运动 GIF。
4. 新增 `examples/README.md`，先不大规模搬文件，只建立示例索引、风险等级和 demo 预览。
5. 引入 `ruff`、`pytest`、CI，先覆盖纯函数和协议拼包。
6. 将库层 `print` 替换成 `logging`。
7. 逐步重组 `examples/` 目录。
8. 增补 `CHANGELOG.md`、`CONTRIBUTING.md`、`SECURITY.md` 和发布元数据。

## 8. 最重要的结论

当前 SDK 的功能底子已经有了，但项目呈现还像“把功能先放出来的内部仓库”。如果目标是大企业机器狗 EDU 版本 SDK，最先要补的不是更多动作，而是：

- 清晰的中英文文档体系。
- 面向真实设备的安全与故障排查。
- 可持续维护的示例分层。
- 测试、lint、CI、版本记录。
- 更专业的日志和异常策略。

完成这些后，这个仓库会从“可用的 Python 包”更接近“可信赖的教育机器人 SDK”。
