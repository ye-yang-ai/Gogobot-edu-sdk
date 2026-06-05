# Robot Action Parameter Types

This document lists the interaction actions by parameter type: time based, count based, angle based, and normal.

When using `AiDog.perform_action()`:

| Type | SDK Parameter | Meaning |
|---|---|---|
| time based | `duration` | Duration in seconds |
| count based | `count` | Number of repetitions |
| angle based | `angle` | Turning angle in degrees |
| normal | none | No action parameter |

## Time Based Actions

Time based actions accept a `duration` parameter. If no parameter is provided, the default value below is used.

| ID | Enum | Default `duration` | Description |
|---:|---|---:|---|
| 4 | `SLOW_DOWN_FOR_PROGRAM` | 5 seconds | Slow crouch for programming flows |
| 8 | `SIT_DOWN_FOR_PROGRAM` | 5 seconds | Sit down for programming flows |
| 24 | `DANCE` | 3 seconds | Dance |
| 29 | `STEP_INTERACTION` | 3 seconds | Step in place |
| 30 | `FORWARD_INTERACTION` | 3 seconds | Move forward |
| 31 | `BACK_INTERACTION` | 3 seconds | Move backward |
| 32 | `LEFT_INTERACTION` | 3 seconds | Turn left |
| 33 | `RIGHT_INTERACTION` | 3 seconds | Turn right |

Example:

```python
dog.perform_action(Action.FORWARD_INTERACTION, duration=3)
dog.perform_action(Action.DANCE, duration=5)
```

## Count Based Actions

Count based actions accept a `count` parameter. If no parameter is provided, the default value below is used.

| ID | Enum | Default `count` | Description |
|---:|---|---:|---|
| 5 | `UP_AND_DOWN` | 3 times | Up-and-down motion |
| 10 | `SHAKE_HAND` | 5 times | Shake hand |
| 11 | `SHAKE_HAND_WITH_SIT_DOWN` | 3 times | Sit down and shake hand |
| 12 | `NOD` | 2 times | Nod |
| 13 | `SHAKE_HEAD` | 4 times | Shake head |
| 15 | `PEE` | 2 times | Simulated urination motion |
| 16 | `TWIST` | 3 times | Twist |
| 17 | `PUSH_UP` | 3 times | Push-up |
| 18 | `NEW_YEAR` | 3 times | New Year greeting |
| 19 | `WAG_TAIL` | 5 times | Wag tail |
| 20 | `STOMP` | 6 times | Stomp |
| 22 | `CELEBRATE` | 3 times | Celebrate |
| 43 | `FLAILING` | 4 times | Flailing motion |

Example:

```python
dog.perform_action(Action.SHAKE_HAND, count=2)
dog.perform_action(Action.WAG_TAIL, count=5)
```

## Angle Based Actions

Angle based actions accept an `angle` parameter. If no parameter is provided, the default value is 90 degrees.

| ID | Enum | Default `angle` | Description |
|---:|---|---:|---|
| 64 | `LEFT_ANGLE_INTERACTION` | 90 degrees | Turn left by a specified angle |
| 65 | `RIGHT_ANGLE_INTERACTION` | 90 degrees | Turn right by a specified angle |

Example:

```python
dog.perform_action(Action.LEFT_ANGLE_INTERACTION, angle=90)
dog.perform_action(Action.RIGHT_ANGLE_INTERACTION, angle=180)
```

## Normal Actions

Normal actions do not accept an action parameter.

| ID | Enum | Description |
|---:|---|---|
| 0 | `IDLE` | Idle |
| 1 | `SLOW_UP` | Slowly stand up |
| 2 | `SLOW_DOWN` | Slowly crouch down |
| 3 | `SLOW_DOWN_FOR_CHARGE` | Crouch down for charging posture |
| 7 | `SIT_DOWN` | Sit down |
| 9 | `STAND_UP` | Stand up from sitting posture |
| 14 | `STRETCH` | Stretch |
| 21 | `SNIFF` | Sniff |
| 23 | `JUMP` | Jump |
| 25 | `KICK_BALL` | Kick ball |
| 26 | `TOUCH_GROUND_RIGHT` | Touch ground with right paw |
| 27 | `TOUCH_GROUND_LEFT` | Touch ground with left paw |
| 28 | `PLAY_DEAD` | Play dead |
| 34 | `LOW_FORWARD_AND_BACKWARD_INTERACTION` | Low posture forward/backward movement |
| 35 | `LOW_FORWARD_INTERACTION` | Low posture forward movement |
| 36 | `LOW_BACKWARD_INTERACTION` | Low posture backward movement |
| 37 | `LOW_LEFT_INTERACTION` | Low posture left turn |
| 38 | `LOW_RIGHT_INTERACTION` | Low posture right turn |
| 39 | `STOP_INTERACTION` | Stop interaction motion |
| 40 | `UP_AND_DOWN_FOR_TEST` | Up-and-down test motion |
| 41 | `ROLLOVER_RECOVERY_RIGHT` | Recover from right-side rollover |
| 42 | `ROLLOVER_RECOVERY_LEFT` | Recover from left-side rollover |
| 44 | `STOP_FLAILING` | Stop flailing |
| 45 | `LIGHT_ON_INTERACTION` | Turn flashlight on |
| 46 | `LIGHT_OFF_INTERACTION` | Turn flashlight off |
| 52 | `SWING_LEFT_AND_RIGHT` | Swing left and right |
| 53 | `SWING_LEFT` | Swing left |
| 54 | `SWING_RIGHT` | Swing right |
| 55 | `EXCITED_INSPACE` | Excited in-place motion |
| 56 | `LAZY_PAT_PAT` | Lazy pat-pat motion |
| 57 | `CHEEKY_PAW` | Cheeky paw motion |
| 58 | `WHINING` | Whining motion |
| 59 | `SNIFF_FORWARD_INTERACTION` | Sniff forward |
| 60 | `SPACE_BACKWARD_INTERACTION` | Space-walk backward |
| 61 | `SNIFF_LEFT_INTERACTION` | Sniff left turn |
| 62 | `SNIFF_RIGHT_INTERACTION` | Sniff right turn |
| 63 | `SNIFF_STEP_INTERACTION` | Sniff step in place |
