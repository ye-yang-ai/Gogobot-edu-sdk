# Examples

The examples are organized by feature area and transport. Use Bluetooth examples for direct BLE control, and WebSocket examples when the robot is configured to connect to the PC Dev-PC WebSocket host.

## Risk Levels

| Level | Meaning |
|---|---|
| Low | Reads state or opens a host service; does not command physical robot movement |
| Medium | Runs actions or movement using normal high-level APIs |
| High | Changes body, foot, or joint targets; requires matching firmware and careful supervision |

## Recommended Order

1. `01_connection/bluetooth/ble_scan_and_connect.py`
2. `01_connection/websocket/ws_connection_test.py`
3. `04_sensors/bluetooth/ble_imu_read.py`
4. `04_sensors/websocket/ws_imu_lan_read.py`
5. `02_actions/bluetooth/ble_basic_actions.py`
6. `02_actions/websocket/ws_ears_expressions_audio.py`
7. `02_actions/websocket/ws_basic_actions.py`
8. `03_movement/bluetooth/ble_directional_move.py`
9. `03_movement/websocket/ws_directional_move.py`
10. `05_audio/bidirectional_pcm_ws_host.py`
11. `06_robot_adjust/safe_pose_adjust.py`

## Directory Structure

```text
examples/
  01_connection/
    bluetooth/
      ble_scan_and_connect.py
      ble_connect_by_address.py
    websocket/
      ws_connection_test.py
  02_actions/
    bluetooth/
      ble_basic_actions.py
      ble_choreography.py
      ble_ears_expressions_audio.py
    websocket/
      ws_basic_actions.py
      ws_choreography.py
      ws_ears_expressions_audio.py
  03_movement/
    bluetooth/
      ble_directional_move.py
      ble_timed_move.py
    websocket/
      ws_directional_move.py
      ws_timed_move.py
  04_sensors/
    bluetooth/
      ble_imu_read.py
      ble_tof_read.py
    websocket/
      ws_imu_lan_read.py
      ws_tof_lan_read.py
```

## Index

| Path | Purpose | Risk | Typical command |
|---|---|---|---|
| `01_connection/bluetooth/ble_scan_and_connect.py` | Scan and connect to first matching BLE device | Low | `python examples/01_connection/bluetooth/ble_scan_and_connect.py` |
| `01_connection/bluetooth/ble_connect_by_address.py` | Connect to a known BLE address or UUID | Low | `python examples/01_connection/bluetooth/ble_connect_by_address.py --address AA:BB:CC:DD:EE:FF` |
| `01_connection/websocket/ws_connection_test.py` | Wait for the robot to connect to the PC WebSocket host | Low | `python examples/01_connection/websocket/ws_connection_test.py --bind 0.0.0.0 --port 8766` |
| `02_actions/bluetooth/ble_basic_actions.py` | Run one high-level action over BLE | Medium | `python examples/02_actions/bluetooth/ble_basic_actions.py --action sit_down` |
| `02_actions/bluetooth/ble_ears_expressions_audio.py` | Control ears, expression, and tone over BLE | Low/Medium | `python examples/02_actions/bluetooth/ble_ears_expressions_audio.py` |
| `02_actions/bluetooth/ble_choreography.py` | Run a short BLE scripted show | Medium | `python examples/02_actions/bluetooth/ble_choreography.py --yes` |
| `02_actions/websocket/ws_ears_expressions_audio.py` | Control ears, expression, audio, and special detection over WebSocket | Low/Medium | `python examples/02_actions/websocket/ws_ears_expressions_audio.py --bind 0.0.0.0 --port 8766` |
| `02_actions/websocket/ws_basic_actions.py` | Run one action over WebSocket using `transport="ws"` | Medium | `python examples/02_actions/websocket/ws_basic_actions.py --action sit_down --yes` |
| `02_actions/websocket/ws_choreography.py` | Run action choreography over WebSocket | Medium | `python examples/02_actions/websocket/ws_choreography.py --yes` |
| `03_movement/bluetooth/ble_directional_move.py` | Move in one selected direction over BLE | Medium | `python examples/03_movement/bluetooth/ble_directional_move.py --direction forward --duration 2 --yes` |
| `03_movement/bluetooth/ble_timed_move.py` | Run a timed BLE movement sequence | Medium | `python examples/03_movement/bluetooth/ble_timed_move.py --duration 2 --yes` |
| `03_movement/websocket/ws_directional_move.py` | Move in one selected direction over WebSocket | Medium | `python examples/03_movement/websocket/ws_directional_move.py --direction forward --duration 2 --yes` |
| `03_movement/websocket/ws_timed_move.py` | Run a timed WebSocket movement sequence | Medium | `python examples/03_movement/websocket/ws_timed_move.py --duration 2 --yes` |
| `04_sensors/bluetooth/ble_imu_read.py` | Read BLE IMU stream | Low | `python examples/04_sensors/bluetooth/ble_imu_read.py --hz 20` |
| `04_sensors/bluetooth/ble_tof_read.py` | Read BLE TOF stream | Low | `python examples/04_sensors/bluetooth/ble_tof_read.py --hz 20 --mode both` |
| `04_sensors/websocket/ws_imu_lan_read.py` | Read LAN WebSocket IMU sensor JSON | Low | `python examples/04_sensors/websocket/ws_imu_lan_read.py --bind 0.0.0.0 --port 8766` |
| `04_sensors/websocket/ws_tof_lan_read.py` | Read LAN WebSocket TOF sensor JSON | Low | `python examples/04_sensors/websocket/ws_tof_lan_read.py --bind 0.0.0.0 --port 8766` |
| `05_audio/bidirectional_pcm_ws_host.py` | Run bidirectional PCM audio host | Low | `python examples/05_audio/bidirectional_pcm_ws_host.py --bind 0.0.0.0 --port 8766` |
| `06_robot_adjust/safe_pose_adjust.py` | Run low-amplitude body/foot adjustment | High | `python examples/06_robot_adjust/safe_pose_adjust.py --yes` |
| `06_robot_adjust/custom_action.py` | Run custom sniff-like robot-adjustment action | High | `python examples/06_robot_adjust/custom_action.py --yes` |

## Common Arguments

- `--name-prefix`: BLE advertisement prefix, default `Gogobot`.
- `--address`: BLE address on Windows/Linux or platform UUID on macOS.
- `--timeout`: auto-exit or operation timeout, depending on the example.
- `--hz`: requested sensor stream rate.
- `--bind`: WebSocket bind address.
- `--port`: WebSocket bind port.
- `--yes`: skip interactive confirmation for movement or high-risk examples.

Read `../docs/safety.md` before running medium or high-risk examples.

## Mini Games

PC-side mini games live outside `examples/` in `../game/`. See `../docs/games.md` for Balance Ball, Brick Breaker, and Space Fighter commands.

## Control Panels

- `../tools/user_control_ble.py`: BLE upper-computer panel.
- `../tools/user_control_ws.py`: WebSocket upper-computer panel. It uses the same page layout as the BLE panel and waits for the robot to connect to the PC WebSocket host, including WebSocket volume control through `config_json`.
