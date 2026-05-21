# Firmware Compatibility

SDK behavior depends on firmware support. Keep this file updated whenever firmware protocol or characteristic behavior changes.

## Compatibility Matrix

| Feature | Required Firmware Support | SDK Surface |
|---|---|---|
| BLE command write | `ae03` write characteristic | `send_raw`, all control APIs |
| BLE config write | `ae01` write characteristic, config JSON parser | `set_volume()` |
| Device status notify | `ae02` notify / indicate | action completion state |
| IMU / TOF sensor stream | `ae04` notify / indicate JSON | `request_imu_stream`, `request_tof_stream` |
| Action definition read | `ae10` read characteristic | `get_action_list()` |
| Dev PC WebSocket sensor mirror | `DEV_PC_AUDIO_WS_ENABLE`, text JSON mirror | `DevPcWebSocketHost` |
| Bidirectional PCM audio | Dev PC audio WebSocket firmware path | `examples/05_audio/bidirectional_pcm_ws_host.py` |
| Robot adjustment | `MODE_ROBOT_ADJUST = 0x0A` | `syn_pose_adjust`, `syn_foot_adjust`, `syn_joint_adjust` |

## Firmware Notes

- Some older firmware builds may not report `interaction_task_status`; `perform_action()` completion waiting is less reliable without it.
- Some builds tie IMU/TOF reporting to notification routing; the SDK subscribes to both `ae02` and `ae04` by default.
- `set_volume()` requires the firmware config parser to accept `{"cmd":1,"volume":0-4}` on `ae01`.
- `ae10` action list reading is optional and may not exist on all firmware versions.
- WebSocket sensor mirror and bidirectional audio require firmware configuration and LAN reachability.

## Recommended Release Practice

For each SDK release, document:

- Tested robot model.
- Tested firmware version or commit.
- Supported BLE characteristics.
- Supported WebSocket features.
- Known limitations.
