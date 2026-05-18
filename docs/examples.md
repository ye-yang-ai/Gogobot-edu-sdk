# Examples

Examples are intentionally small and runnable. Start with connection and sensor examples before running movement or robot-adjustment scripts.

| File | Purpose | Risk | Notes |
|---|---|---|---|
| `examples/01_connect.py` | Scan, list devices, connect by address | Low | First script to run |
| `examples/02_actions.py` | Actions, ears, expressions, tones | Medium | Keep robot on open floor |
| `examples/03_movement.py` | Directional movement | Medium | Robot will move |
| `examples/04_audio_ws_bidirectional_host.py` | Bidirectional PCM WebSocket host | Low | Requires optional audio deps and firmware config |
| `examples/05_imu_read.py` | Subscribe to IMU JSON on `ae04` | Low | Sensor read |
| `examples/06_tof_read.py` | Subscribe to TOF JSON on `ae04` | Low | Sensor read |
| `examples/07_Servo_Control.py` | Smooth pose / foot / joint adjustment | High | Requires matching firmware; advanced control |
| `examples/08_sensor_ws_lan.py` | IMU/TOF over LAN via Dev PC WebSocket | Low | Requires firmware WebSocket config |
| `examples/demo_1_performance.py` | Performance-style scripted show | Medium | Choreography demo |
| `examples/demo_2_custom_action.py` | Custom action design | High | Advanced choreography |

## Recommended Order

1. `examples/01_connect.py`
2. `examples/05_imu_read.py`
3. `examples/06_tof_read.py`
4. `examples/02_actions.py`
5. `examples/03_movement.py`
6. `examples/08_sensor_ws_lan.py`
7. `examples/04_audio_ws_bidirectional_host.py`
8. `examples/07_Servo_Control.py`

Read [Safety Guide](safety.md) before running medium or high risk examples.
