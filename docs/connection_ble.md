# BLE Connection Guide

The SDK uses BLE to scan, connect, write robot commands, and subscribe to robot notifications.

## Device Discovery

Default name prefix:

```python
devices = dog.scan("Gogobot")
```

Returned value:

```python
[("Gogobot-001", "AA:BB:CC:DD:EE:FF")]
```

## Connection

```python
dog.connect("Gogobot", retries=3, retry_delay_s=1.0)
```

Direct address connection:

```python
dog.connect(address="AA:BB:CC:DD:EE:FF", retries=3, retry_delay_s=1.0)
```

## Notifications

The SDK subscribes to:

- `ae02`: device-to-host status notifications.
- `ae04`: sensor stream notifications, typically IMU / TOF JSON.

## Common Issues

- If scanning returns no devices, check power, BLE range, host Bluetooth state, and the device name prefix.
- On Windows, the SDK performs a short pre-scan before direct address connection because the WinRT BLE backend often needs a scanner cache.
- If writes fail, reconnect the robot and keep only one host connected at a time.

See [Troubleshooting](troubleshooting.md) for more details.
