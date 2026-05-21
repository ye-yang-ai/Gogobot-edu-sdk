# API Reference

This page summarizes the public APIs exported from `aidog_sdk`.

## Connection

| API | Description |
|---|---|
| `scan(name_prefix="Changba-Ai-Dog")` | Scan nearby BLE devices and return `(name, address)` tuples |
| `connect(name_prefix="Changba-Ai-Dog", address=None, retries=3, retry_delay_s=1.0)` | Connect by name prefix or direct address |
| `disconnect()` | Disconnect current BLE device |
| `shutdown()` | Disconnect and stop the background BLE thread |
| `is_connected` | Connection state property |

## Actions and Movement

| API | Description |
|---|---|
| `perform_action(action, duration=None, count=None, timeout_s=20.0)` | Send an interaction action and wait for completion feedback |
| `send_interaction(action_id, param=None)` | Send raw interaction action ID |
| `send_movement(direction, duration_s=None)` | Start movement; optionally auto-stop after a duration |
| `start_movement(direction)` | Start movement in a direction |
| `stop_movement()` | Stop movement |
| `reset()` | Stop movement and send interaction stop |
| `move(direction_deg, velocity=1.0)` | Compatibility wrapper for angle-based movement input |

## Ears, Expression, Audio

| API | Description |
|---|---|
| `send_ear(ear_action_id)` | Ear action |
| `send_ear_percentage(percentage)` | Ear position percentage |
| `enable_special_detection()` | Enable special-state detection |
| `disable_special_detection()` | Disable special-state detection |
| `toggle_special_detection()` | Legacy toggle command |
| `send_expression(expression_id)` | Face expression |
| `send_audio(tone_id)` | Tone or audio control |
| `set_volume(volume, verify_tone=None)` | Set speaker volume level `0-4` over BLE config |

## Sensors

| API | Description |
|---|---|
| `request_imu_stream(enable=True, hz=20)` | Request IMU stream in `ae04` JSON |
| `get_latest_imu()` | Last parsed IMU payload |
| `add_imu_listener(cb)` | Register IMU callback |
| `remove_imu_listener(cb)` | Remove IMU callback |
| `request_tof_stream(enable=True, hz=20)` | Request TOF stream |
| `get_latest_tof()` | Last parsed TOF payload |
| `add_tof_listener(cb)` | Register TOF callback |
| `remove_tof_listener(cb)` | Remove TOF callback |
| `parse_notify_json_text(text)` | Parse one firmware notify JSON line |
| `feed_sensor_stream_json(text)` | Feed LAN/WebSocket sensor JSON into SDK state |

## Robot Adjustment

These APIs require matching firmware support and should be treated as advanced control.

| API | Description |
|---|---|
| `syn_pose_adjust(items, duration_ms)` | Smooth COG / pose adjustment |
| `syn_foot_adjust(items, duration_ms)` | Smooth foot X/Z adjustment |
| `syn_joint_adjust(items, duration_ms)` | Smooth joint delta adjustment |
| `default_pose_output(roll, pitch, x, z)` | Move to a known baseline pose |
| `request_basic_mode()` | Request return to basic mode |

## Low-Level Extension

| API | Description |
|---|---|
| `send_raw(mode, data)` | Send raw protocol packet |
| `get_action_list()` | Read optional action definition JSON from `ae10` |

## Exported Enums

- `Action`
- `Movement`
- `EarAction`
- `ExpressionAction`
- `Tone`
- `INTERACTION_ACTION_NAMES`
- `EAR_ACTION_NAMES`
- `EXPRESSION_ACTION_NAMES`
- `TONE_LIST`
- `ACTION_ALIASES`
- `resolve_action`
