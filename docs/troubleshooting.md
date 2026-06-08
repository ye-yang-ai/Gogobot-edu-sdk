# Troubleshooting

## BLE Scan Finds No Device

Check:

- Robot is powered on.
- Robot is close enough to the computer.
- Bluetooth is enabled on the computer.
- Device name prefix matches `Gogobot`.
- No other host is already holding the BLE connection.

## Direct Address Connect Fails

On Windows, direct-address BLE connection can require the device to be present in the scanner cache. The SDK does a short pre-scan before connecting, but if it still fails:

- Run `examples/01_connection/bluetooth/ble_scan_and_connect.py` once.
- Reboot Bluetooth on the host.
- Power cycle the robot.

## Action Does Not Finish

`perform_action()` relies on firmware notify JSON field `interaction_task_status`.

Check:

- Firmware reports `interaction_task_status`.
- The robot is not stuck in another mode.
- Increase `timeout_s` for long actions.
- Use `dog.reset()` before the next action.

## IMU / TOF Has No Data

Check:

- Firmware supports `ae04` sensor JSON.
- Call `request_imu_stream()` or `request_tof_stream()`.
- Add a listener or call `get_latest_imu()` / `get_latest_tof()` after notifications start.

## WebSocket Host Does Not Receive Data

Check:

- `DEV_PC_AUDIO_WS_ENABLE` is enabled in firmware.
- `DEV_PC_AUDIO_WS_URL` points to the PC LAN IP.
- PC and robot are on the same LAN.
- Firewall allows the selected port, for example `8766`.
- Host script is already listening before the robot connects.

## Audio Device Error

Install optional dependencies:

```bash
pip install -e ".[bidir_audio]"
```

Inspect audio devices:

```bash
python -c "import sounddevice as sd; print(sd.query_devices())"
```

Then pass explicit input/output device indices to the audio example.
