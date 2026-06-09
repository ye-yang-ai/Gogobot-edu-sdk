# Mini Games

The `game/` directory contains three PC-side pygame mini games that can be used as classroom demos for keyboard control, IMU control, and robot feedback.

## Games

| Game | Entry script | Control modes | Notes |
|---|---|---|---|
| Balance Ball | `game/balance_ball/aidog_balance_ball_game.py` | Keyboard, BLE IMU, WebSocket IMU | Keep the ball balanced by tilting the robot. |
| Brick Breaker | `game/brick_breaker/aidog_brick_breaker_game.py` | Keyboard, BLE IMU, WebSocket IMU | Move the paddle with robot roll and clear all bricks. |
| Space Fighter | `game/space_fighter/aidog_space_fighter_game.py` | Keyboard, WebSocket IMU | Move the fighter, defeat waves, and clear boss stages. |

## Screenshots

### Balance Ball

<p align="center">
  <img src="assets/images/balance_ball_game.png" alt="Balance Ball game UI" width="75%">
</p>

### Brick Breaker

<p align="center">
  <img src="assets/images/brick_breaker_game.png" alt="Brick Breaker game UI" width="75%">
</p>

### Space Fighter

<p align="center">
  <img src="assets/images/space_fighter_game.png" alt="Space Fighter game UI" width="75%">
</p>

## Install

Run commands from the `aidog_sdk` project root.

```bash
pip install -e .
pip install pygame
```

For WebSocket IMU control, also install the WebSocket extra:

```bash
pip install -e ".[dev_pc_ws]"
```

## Keyboard Trial

Keyboard mode is the safest first check because it does not require a robot connection.

```bash
python game/balance_ball/aidog_balance_ball_game.py --transport keyboard
python game/brick_breaker/aidog_brick_breaker_game.py --transport keyboard
python game/space_fighter/aidog_space_fighter_game.py
```

## Robot IMU Control

Use WebSocket mode after the robot firmware has been configured to connect to the PC Dev-PC WebSocket host.

```bash
python game/balance_ball/aidog_balance_ball_game.py --transport ws --bind 0.0.0.0 --port 8766
python game/brick_breaker/aidog_brick_breaker_game.py --transport ws --bind 0.0.0.0 --port 8766
python game/space_fighter/aidog_space_fighter_game.py --imu ws --ws-bind 0.0.0.0 --ws-port 8766
```

Balance Ball and Brick Breaker also support BLE IMU input:

```bash
python game/balance_ball/aidog_balance_ball_game.py --transport ble
python game/brick_breaker/aidog_brick_breaker_game.py --transport ble
```

## Common Options

- `--bind` / `--ws-bind`: PC WebSocket listen address.
- `--port` / `--ws-port`: PC WebSocket listen port.
- `--name-prefix`: BLE device name prefix, default `Gogobot`.
- `--address`: BLE address on Windows/Linux or platform UUID on macOS.
- `--dog-facing`: robot facing direction for roll mapping, `user` or `away`.
- `--invert-roll`: invert roll direction when the physical orientation feels reversed.
- `--sensitivity`: tilt sensitivity multiplier.
- `--score-file`: custom score JSON path.

Scores are saved under `game/scores/` by default.

## Safety

Start with keyboard mode, then switch to robot IMU control after the window opens correctly. Put the robot on a flat and stable surface before IMU play. Some games can send a prepare-pose action or feedback actions to the robot, so keep enough space around it and stop the game if the robot posture looks unsafe.
