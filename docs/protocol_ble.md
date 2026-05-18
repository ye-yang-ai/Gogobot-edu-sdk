# BLE Protocol Reference

This document records the public protocol details currently exposed by the Python SDK.

## Packet Format

SDK write packet:

```text
[0xAA, 0x55, 0x00, mode, ...data]
```

## Modes

| Constant | Value | Purpose |
|---|---:|---|
| `MODE_EAR` | `0x00` | Ear and special detection commands |
| `MODE_SPORT` | `0x01` | Movement / sport control |
| `MODE_INTERACTION` | `0x02` | High-level action control |
| `MODE_EXPRESSION` | `0x05` | Face expression control |
| `MODE_AUDIO` | `0x06` | Tone / audio control |
| `MODE_SENSOR` | `0x08` | Sensor stream control |
| `MODE_STREAM` | `0x09` | Microphone / speaker stream control |
| `MODE_ROBOT_ADJUST` | `0x0A` | Smooth pose, foot, and joint adjustment |

## Characteristics

| Characteristic | Direction | Purpose |
|---|---|---|
| `ae03` | Host to robot | Write control packets |
| `ae02` | Robot to host | Status notifications |
| `ae04` | Robot to host | Sensor stream notifications, typically IMU / TOF JSON |
| `ae10` | Host reads robot | Optional action definition JSON |

## Notify JSON

Typical fields:

```json
{
  "interaction_task_status": 1,
  "imu": {
    "yaw": -400710,
    "pitch": 630,
    "roll": -206
  },
  "tof": {
    "front_mm": 300,
    "oblique_mm": 420
  }
}
```

`interaction_task_status`:

- `0`: not running / finished
- `1`: running
- `2`: killed / interrupted

IMU angles may be reported by firmware as milli-degrees. The SDK normalizes them into `yaw_deg`, `pitch_deg`, `roll_deg`, and `angle_deg`.
