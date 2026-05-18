# Safety Guide

This SDK controls a real quadruped robot. Treat examples as physical robot programs, not just Python scripts.

## Before Running Examples

- Place the robot on a flat, stable, open floor.
- Keep hands, cables, and fragile objects away from the legs.
- Keep the robot within BLE range.
- Make sure battery level is sufficient.
- Confirm how to stop the script and power down the robot.

## Risk Levels

| Level | Meaning | Examples |
|---|---|---|
| Low | Reads state or performs no physical movement | scan, connect, IMU, TOF |
| Medium | Runs normal actions or directional movement | sit, shake hand, walk forward |
| High | Adjusts body, feet, joints, or low-level behavior | robot adjustment, custom choreography |

## Recommended Safe Sequence for Choreography

1. Connect to the robot.
2. Request or ensure `BASIC_MODE`.
3. Disable special detection if autonomous behavior may interfere.
4. Move to a known baseline pose.
5. Run the custom motion sequence.
6. Stop movement.
7. Request `BASIC_MODE` again.
8. Re-enable special detection when appropriate.

## Emergency Stop Behavior

At the SDK level:

```python
dog.stop_movement()
dog.reset()
dog.shutdown()
```

At the script level, use `Ctrl+C` and make sure examples clean up in `finally` blocks.
