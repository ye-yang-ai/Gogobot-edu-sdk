"""
Action definitions for the Changba AI-Dog.

Use :class:`Action` members in application code when possible. String aliases
in ``ACTION_ALIASES`` are accepted by ``resolve_action()`` and
``AiDog.perform_action()`` for examples, scripts, and Chinese/English user
input. ``TIMER_BASED`` actions use a ``duration`` parameter in seconds,
``COUNT_BASED`` actions use a repeat ``count``, and ``ANGLE_BASED`` actions use
an ``angle`` parameter in degrees.

The integer values match the ``QRMotion_TypeDef`` enum in the firmware
(sdk/apps/ai_dog/algorithm/interaction_mode/include/interaction_mode.h).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set, Tuple


class Action(IntEnum):
    """Public robot motions, using firmware QRMotion_TypeDef IDs."""

    IDLE                             = 0
    SLOW_UP                          = 1   # Slowly stand up on all four legs
    SLOW_DOWN                        = 2   # Slowly crouch down (ears lowered)
    SLOW_DOWN_FOR_CHARGE             = 3   # Slowly crouch down (charging posture)
    SLOW_DOWN_FOR_PROGRAM            = 4   # Timed slow crouch (for programming flow)
    UP_AND_DOWN                      = 5   # Repeated slow up-and-down motion

    SIT_DOWN                         = 7   # Sit down
    SIT_DOWN_FOR_PROGRAM             = 8   # Timed sit-down action (for programming flow)
    STAND_UP                         = 9   # Stand up from sitting posture
    SHAKE_HAND                       = 10  # Shake hand
    SHAKE_HAND_WITH_SIT_DOWN         = 11  # Sit down and shake hand directly
    NOD                              = 12  # Nod
    SHAKE_HEAD                       = 13  # Shake head
    STRETCH                          = 14  # Stretch
    PEE                              = 15  # Simulated urination motion
    TWIST                            = 16  # Twist/sway in place
    PUSH_UP                          = 17  # Push-up
    NEW_YEAR                         = 18  # New Year greeting motion
    WAG_TAIL                         = 19  # Wag tail
    STOMP                            = 20  # Stomp right front paw
    SNIFF                            = 21  # Sniff
    CELEBRATE                        = 22  # Celebrate / cheer motion
    JUMP                             = 23  # Jump
    DANCE                            = 24  # Dance
    KICK_BALL                        = 25  # Kick ball
    TOUCH_GROUND_RIGHT               = 26  # Tap ground with right paw
    TOUCH_GROUND_LEFT                = 27  # Tap ground with left paw
    PLAY_DEAD                        = 28  # Play dead

    # --- timed movement actions (duration in seconds) ---
    STEP_INTERACTION                 = 29  # Step in place (timed)
    FORWARD_INTERACTION              = 30  # Move forward (timed)
    BACK_INTERACTION                 = 31  # Move backward (timed)
    LEFT_INTERACTION                 = 32  # Turn left (timed)
    RIGHT_INTERACTION                = 33  # Turn right (timed)
    LOW_FORWARD_AND_BACKWARD_INTERACTION = 34  # Low posture forward/backward
    LOW_FORWARD_INTERACTION              = 35  # Low posture forward
    LOW_BACKWARD_INTERACTION             = 36  # Low posture backward
    LOW_LEFT_INTERACTION                 = 37  # Low posture left turn
    LOW_RIGHT_INTERACTION                = 38  # Low posture right turn

    STOP_INTERACTION                 = 39  # Stop interaction motion
    UP_AND_DOWN_FOR_TEST             = 40  # Up-and-down test motion

    ROLLOVER_RECOVERY_RIGHT          = 41  # Recover from right-side rollover
    ROLLOVER_RECOVERY_LEFT           = 42  # Recover from left-side rollover
    FLAILING                         = 43  # Flailing motion
    STOP_FLAILING                    = 44  # Stop flailing

    LIGHT_ON_INTERACTION             = 45  # Turn flashlight on
    LIGHT_OFF_INTERACTION            = 46  # Turn flashlight off

    SWING_LEFT_AND_RIGHT             = 52  # Swing left and right
    SWING_LEFT                       = 53  # Swing left
    SWING_RIGHT                      = 54  # Swing right
    EXCITED_INSPACE                  = 55  # Excited in-place motion
    LAZY_PAT_PAT                     = 56  # Lazy pat-pat motion
    CHEEKY_PAW                       = 57  # Cheeky paw motion
    WHINING                          = 58  # Whining motion
    SNIFF_FORWARD_INTERACTION        = 59  # Sniff forward (timed)
    SPACE_BACKWARD_INTERACTION       = 60  # Space-walk backward (timed)
    SNIFF_LEFT_INTERACTION           = 61  # Sniff left turn (timed)
    SNIFF_RIGHT_INTERACTION          = 62  # Sniff right turn (timed)
    SNIFF_STEP_INTERACTION           = 63  # Sniff step in place (timed)
    LEFT_ANGLE_INTERACTION           = 64  # Turn left by angle
    RIGHT_ANGLE_INTERACTION          = 65  # Turn right by angle

    # aliases (same numeric IDs)
    LOW_FORWARD_AND_BACKWARD = 34
    LOW_FORWARD = 35
    LOW_BACKWARD = 36
    LOW_LEFT = 37
    LOW_RIGHT = 38
    STEP = 29
    FORWARD = 30
    BACK = 31
    LEFT = 32
    RIGHT = 33
    LEFT_ANGLE = 64
    RIGHT_ANGLE = 65
    STOP = 39
    LIGHT_ON = 45
    LIGHT_OFF = 46


# ---------------------------------------------------------------------------
# Canonical action specs
# ---------------------------------------------------------------------------


class ParameterType(str, Enum):
    TIME = "time"
    COUNT = "count"
    ANGLE = "angle"
    NORMAL = "normal"


@dataclass(frozen=True)
class ActionSpec:
    action: Action
    parameter_type: ParameterType
    default: Optional[int]
    description: str


ACTION_SPECS: Dict[Action, ActionSpec] = {
    Action.IDLE: ActionSpec(Action.IDLE, ParameterType.NORMAL, None, "Idle"),
    Action.SLOW_UP: ActionSpec(Action.SLOW_UP, ParameterType.NORMAL, None, "Slowly stand up"),
    Action.SLOW_DOWN: ActionSpec(Action.SLOW_DOWN, ParameterType.NORMAL, None, "Slowly crouch down"),
    Action.SLOW_DOWN_FOR_CHARGE: ActionSpec(Action.SLOW_DOWN_FOR_CHARGE, ParameterType.NORMAL, None, "Crouch down for charging posture"),
    Action.SLOW_DOWN_FOR_PROGRAM: ActionSpec(Action.SLOW_DOWN_FOR_PROGRAM, ParameterType.TIME, 5, "Slow crouch for programming flows"),
    Action.UP_AND_DOWN: ActionSpec(Action.UP_AND_DOWN, ParameterType.COUNT, 3, "Up-and-down motion"),
    Action.SIT_DOWN: ActionSpec(Action.SIT_DOWN, ParameterType.NORMAL, None, "Sit down"),
    Action.SIT_DOWN_FOR_PROGRAM: ActionSpec(Action.SIT_DOWN_FOR_PROGRAM, ParameterType.TIME, 5, "Sit down for programming flows"),
    Action.STAND_UP: ActionSpec(Action.STAND_UP, ParameterType.NORMAL, None, "Stand up from sitting posture"),
    Action.SHAKE_HAND: ActionSpec(Action.SHAKE_HAND, ParameterType.COUNT, 5, "Shake hand"),
    Action.SHAKE_HAND_WITH_SIT_DOWN: ActionSpec(Action.SHAKE_HAND_WITH_SIT_DOWN, ParameterType.COUNT, 3, "Sit down and shake hand"),
    Action.NOD: ActionSpec(Action.NOD, ParameterType.COUNT, 2, "Nod"),
    Action.SHAKE_HEAD: ActionSpec(Action.SHAKE_HEAD, ParameterType.COUNT, 4, "Shake head"),
    Action.STRETCH: ActionSpec(Action.STRETCH, ParameterType.NORMAL, None, "Stretch"),
    Action.PEE: ActionSpec(Action.PEE, ParameterType.COUNT, 2, "Simulated urination motion"),
    Action.TWIST: ActionSpec(Action.TWIST, ParameterType.COUNT, 3, "Twist"),
    Action.PUSH_UP: ActionSpec(Action.PUSH_UP, ParameterType.COUNT, 3, "Push-up"),
    Action.NEW_YEAR: ActionSpec(Action.NEW_YEAR, ParameterType.COUNT, 3, "New Year greeting"),
    Action.WAG_TAIL: ActionSpec(Action.WAG_TAIL, ParameterType.COUNT, 5, "Wag tail"),
    Action.STOMP: ActionSpec(Action.STOMP, ParameterType.COUNT, 6, "Stomp"),
    Action.SNIFF: ActionSpec(Action.SNIFF, ParameterType.NORMAL, None, "Sniff"),
    Action.CELEBRATE: ActionSpec(Action.CELEBRATE, ParameterType.COUNT, 3, "Celebrate"),
    Action.JUMP: ActionSpec(Action.JUMP, ParameterType.NORMAL, None, "Jump"),
    Action.DANCE: ActionSpec(Action.DANCE, ParameterType.TIME, 3, "Dance"),
    Action.KICK_BALL: ActionSpec(Action.KICK_BALL, ParameterType.NORMAL, None, "Kick ball"),
    Action.TOUCH_GROUND_RIGHT: ActionSpec(Action.TOUCH_GROUND_RIGHT, ParameterType.NORMAL, None, "Touch ground with right paw"),
    Action.TOUCH_GROUND_LEFT: ActionSpec(Action.TOUCH_GROUND_LEFT, ParameterType.NORMAL, None, "Touch ground with left paw"),
    Action.PLAY_DEAD: ActionSpec(Action.PLAY_DEAD, ParameterType.NORMAL, None, "Play dead"),
    Action.STEP_INTERACTION: ActionSpec(Action.STEP_INTERACTION, ParameterType.TIME, 3, "Step in place"),
    Action.FORWARD_INTERACTION: ActionSpec(Action.FORWARD_INTERACTION, ParameterType.TIME, 3, "Move forward"),
    Action.BACK_INTERACTION: ActionSpec(Action.BACK_INTERACTION, ParameterType.TIME, 3, "Move backward"),
    Action.LEFT_INTERACTION: ActionSpec(Action.LEFT_INTERACTION, ParameterType.TIME, 3, "Turn left"),
    Action.RIGHT_INTERACTION: ActionSpec(Action.RIGHT_INTERACTION, ParameterType.TIME, 3, "Turn right"),
    Action.LOW_FORWARD_AND_BACKWARD_INTERACTION: ActionSpec(Action.LOW_FORWARD_AND_BACKWARD_INTERACTION, ParameterType.TIME, 3, "Low posture forward/backward movement"),
    Action.LOW_FORWARD_INTERACTION: ActionSpec(Action.LOW_FORWARD_INTERACTION, ParameterType.TIME, 3, "Low posture forward movement"),
    Action.LOW_BACKWARD_INTERACTION: ActionSpec(Action.LOW_BACKWARD_INTERACTION, ParameterType.TIME, 3, "Low posture backward movement"),
    Action.LOW_LEFT_INTERACTION: ActionSpec(Action.LOW_LEFT_INTERACTION, ParameterType.TIME, 3, "Low posture left turn"),
    Action.LOW_RIGHT_INTERACTION: ActionSpec(Action.LOW_RIGHT_INTERACTION, ParameterType.TIME, 3, "Low posture right turn"),
    Action.STOP_INTERACTION: ActionSpec(Action.STOP_INTERACTION, ParameterType.NORMAL, None, "Stop interaction motion"),
    Action.UP_AND_DOWN_FOR_TEST: ActionSpec(Action.UP_AND_DOWN_FOR_TEST, ParameterType.NORMAL, None, "Up-and-down test motion"),
    Action.ROLLOVER_RECOVERY_RIGHT: ActionSpec(Action.ROLLOVER_RECOVERY_RIGHT, ParameterType.NORMAL, None, "Recover from right-side rollover"),
    Action.ROLLOVER_RECOVERY_LEFT: ActionSpec(Action.ROLLOVER_RECOVERY_LEFT, ParameterType.NORMAL, None, "Recover from left-side rollover"),
    Action.FLAILING: ActionSpec(Action.FLAILING, ParameterType.COUNT, 4, "Flailing motion"),
    Action.STOP_FLAILING: ActionSpec(Action.STOP_FLAILING, ParameterType.NORMAL, None, "Stop flailing"),
    Action.LIGHT_ON_INTERACTION: ActionSpec(Action.LIGHT_ON_INTERACTION, ParameterType.NORMAL, None, "Turn flashlight on"),
    Action.LIGHT_OFF_INTERACTION: ActionSpec(Action.LIGHT_OFF_INTERACTION, ParameterType.NORMAL, None, "Turn flashlight off"),
    Action.SWING_LEFT_AND_RIGHT: ActionSpec(Action.SWING_LEFT_AND_RIGHT, ParameterType.NORMAL, None, "Swing left and right"),
    Action.SWING_LEFT: ActionSpec(Action.SWING_LEFT, ParameterType.NORMAL, None, "Swing left"),
    Action.SWING_RIGHT: ActionSpec(Action.SWING_RIGHT, ParameterType.NORMAL, None, "Swing right"),
    Action.EXCITED_INSPACE: ActionSpec(Action.EXCITED_INSPACE, ParameterType.NORMAL, None, "Excited in-place motion"),
    Action.LAZY_PAT_PAT: ActionSpec(Action.LAZY_PAT_PAT, ParameterType.NORMAL, None, "Lazy pat-pat motion"),
    Action.CHEEKY_PAW: ActionSpec(Action.CHEEKY_PAW, ParameterType.NORMAL, None, "Cheeky paw motion"),
    Action.WHINING: ActionSpec(Action.WHINING, ParameterType.NORMAL, None, "Whining motion"),
    Action.SNIFF_FORWARD_INTERACTION: ActionSpec(Action.SNIFF_FORWARD_INTERACTION, ParameterType.TIME, 3, "Sniff forward"),
    Action.SPACE_BACKWARD_INTERACTION: ActionSpec(Action.SPACE_BACKWARD_INTERACTION, ParameterType.TIME, 3, "Space-walk backward"),
    Action.SNIFF_LEFT_INTERACTION: ActionSpec(Action.SNIFF_LEFT_INTERACTION, ParameterType.TIME, 3, "Sniff left turn"),
    Action.SNIFF_RIGHT_INTERACTION: ActionSpec(Action.SNIFF_RIGHT_INTERACTION, ParameterType.TIME, 3, "Sniff right turn"),
    Action.SNIFF_STEP_INTERACTION: ActionSpec(Action.SNIFF_STEP_INTERACTION, ParameterType.TIME, 3, "Sniff step in place"),
    Action.LEFT_ANGLE_INTERACTION: ActionSpec(Action.LEFT_ANGLE_INTERACTION, ParameterType.ANGLE, 90, "Turn left by a specified angle"),
    Action.RIGHT_ANGLE_INTERACTION: ActionSpec(Action.RIGHT_ANGLE_INTERACTION, ParameterType.ANGLE, 90, "Turn right by a specified angle"),
}


def _actions_by_parameter_type(parameter_type: ParameterType) -> Set[Action]:
    return {spec.action for spec in ACTION_SPECS.values() if spec.parameter_type == parameter_type}


TIMER_BASED: Set[Action] = _actions_by_parameter_type(ParameterType.TIME)
COUNT_BASED: Set[Action] = _actions_by_parameter_type(ParameterType.COUNT)
ANGLE_BASED: Set[Action] = _actions_by_parameter_type(ParameterType.ANGLE)
NORMAL_ACTIONS: Set[Action] = _actions_by_parameter_type(ParameterType.NORMAL)
ACTION_DEFAULTS: Dict[Action, Optional[int]] = {
    action: spec.default for action, spec in ACTION_SPECS.items()
}
ACTION_PARAMETER_TYPES: Dict[Action, ParameterType] = {
    action: spec.parameter_type for action, spec in ACTION_SPECS.items()
}
_HIDDEN_ACTION_ID_MAP: Dict[int, Action] = {
    6: Action.IDLE,
    47: Action.IDLE,
    48: Action.IDLE,
    49: Action.IDLE,
    50: Action.IDLE,
    51: Action.IDLE,
}

# ---------------------------------------------------------------------------
# Human-readable name lookup (supports both English and Chinese aliases)
# ---------------------------------------------------------------------------

# Maps lowercase English / Chinese string → Action enum value
# Developers can pass any of these strings to AiDog.perform_action().
ACTION_ALIASES: Dict[str, Action] = {
    # English names
    "idle":                       Action.IDLE,
    "slow_up":                    Action.SLOW_UP,
    "slow_down":                  Action.SLOW_DOWN,
    "sit_down":                   Action.SIT_DOWN,
    "stand_up":                   Action.STAND_UP,
    "shake_hand":                 Action.SHAKE_HAND,
    "nod":                        Action.NOD,
    "shake_head":                 Action.SHAKE_HEAD,
    "stretch":                    Action.STRETCH,
    "pee":                        Action.PEE,
    "twist":                      Action.TWIST,
    "push_up":                    Action.PUSH_UP,
    "new_year":                   Action.NEW_YEAR,
    "wag_tail":                   Action.WAG_TAIL,
    "stomp":                      Action.STOMP,
    "sniff":                      Action.SNIFF,
    "celebrate":                  Action.CELEBRATE,
    "jump":                       Action.JUMP,
    "dance":                      Action.DANCE,
    "kick_ball":                  Action.KICK_BALL,
    "touch_ground_right":         Action.TOUCH_GROUND_RIGHT,
    "touch_ground_left":          Action.TOUCH_GROUND_LEFT,
    "play_dead":                  Action.PLAY_DEAD,
    "step":                       Action.STEP_INTERACTION,
    "walk_forward":               Action.FORWARD_INTERACTION,
    "walk_back":                  Action.BACK_INTERACTION,
    "turn_left":                  Action.LEFT_INTERACTION,
    "turn_right":                 Action.RIGHT_INTERACTION,
    "turn_left_angle":            Action.LEFT_ANGLE_INTERACTION,
    "turn_right_angle":           Action.RIGHT_ANGLE_INTERACTION,
    "left_angle":                 Action.LEFT_ANGLE_INTERACTION,
    "right_angle":                Action.RIGHT_ANGLE_INTERACTION,
    "low_forward_and_backward":   Action.LOW_FORWARD_AND_BACKWARD_INTERACTION,
    "low_forward":                Action.LOW_FORWARD_INTERACTION,
    "low_backward":               Action.LOW_BACKWARD_INTERACTION,
    "low_left":                   Action.LOW_LEFT_INTERACTION,
    "low_right":                  Action.LOW_RIGHT_INTERACTION,
    "stop":                       Action.STOP_INTERACTION,
    "light_on":                   Action.LIGHT_ON_INTERACTION,
    "light_off":                  Action.LIGHT_OFF_INTERACTION,
    "rollover_recovery_right":    Action.ROLLOVER_RECOVERY_RIGHT,
    "rollover_recovery_left":     Action.ROLLOVER_RECOVERY_LEFT,
    "light_on_interaction":       Action.LIGHT_ON_INTERACTION,
    "light_off_interaction":      Action.LIGHT_OFF_INTERACTION,
    "swing_left_and_right":       Action.SWING_LEFT_AND_RIGHT,
    "swing_left":                 Action.SWING_LEFT,
    "swing_right":                Action.SWING_RIGHT,
    "excited_inspace":            Action.EXCITED_INSPACE,
    "lazy_pat_pat":               Action.LAZY_PAT_PAT,
    "cheeky_paw":                 Action.CHEEKY_PAW,
    "whining":                    Action.WHINING,
    "sniff_forward":              Action.SNIFF_FORWARD_INTERACTION,
    "space_backward":             Action.SPACE_BACKWARD_INTERACTION,
    "sniff_left":                 Action.SNIFF_LEFT_INTERACTION,
    "sniff_right":                Action.SNIFF_RIGHT_INTERACTION,
    "sniff_step":                 Action.SNIFF_STEP_INTERACTION,
    "sniff_forward_interaction":  Action.SNIFF_FORWARD_INTERACTION,
    "space_backward_interaction": Action.SPACE_BACKWARD_INTERACTION,
    "sniff_left_interaction":     Action.SNIFF_LEFT_INTERACTION,
    "sniff_right_interaction":    Action.SNIFF_RIGHT_INTERACTION,
    "sniff_step_interaction":     Action.SNIFF_STEP_INTERACTION,
    # Chinese names
    "坐下":   Action.SIT_DOWN,
    "站起":   Action.STAND_UP,
    "握手":   Action.SHAKE_HAND,
    "点头":   Action.NOD,
    "摇头":   Action.SHAKE_HEAD,
    "伸懒腰": Action.STRETCH,
    "撒尿":   Action.PEE,
    "俯卧撑": Action.PUSH_UP,
    "拜年":   Action.NEW_YEAR,
    "摇尾巴": Action.WAG_TAIL,
    "跺脚":   Action.STOMP,
    "嗅探":   Action.SNIFF,
    "庆祝":   Action.CELEBRATE,
    "跳跃":   Action.JUMP,
    "跳舞":   Action.DANCE,
    "踢球":   Action.KICK_BALL,
    "装死":   Action.PLAY_DEAD,
    "原地踏步": Action.STEP_INTERACTION,
    "前进":   Action.FORWARD_INTERACTION,
    "后退":   Action.BACK_INTERACTION,
    "左转":   Action.LEFT_INTERACTION,
    "右转":   Action.RIGHT_INTERACTION,
    "左转指定角度": Action.LEFT_ANGLE_INTERACTION,
    "右转指定角度": Action.RIGHT_ANGLE_INTERACTION,
    "停止":   Action.STOP_INTERACTION,
    "开灯":   Action.LIGHT_ON,
    "关灯":   Action.LIGHT_OFF,
    "左右摇摆": Action.SWING_LEFT_AND_RIGHT,
    "左摇摆": Action.SWING_LEFT,
    "右摇摆": Action.SWING_RIGHT,
    "太空步后退": Action.SPACE_BACKWARD_INTERACTION,
    "撒娇拍桌面": Action.LAZY_PAT_PAT,
    "脸颊招财": Action.CHEEKY_PAW,
    "撒泼打滚": Action.WHINING,
    "嗅探前进": Action.SNIFF_FORWARD_INTERACTION,
    "嗅探左转": Action.SNIFF_LEFT_INTERACTION,
    "嗅探右转": Action.SNIFF_RIGHT_INTERACTION,
    "嗅探踏步": Action.SNIFF_STEP_INTERACTION,
}

INTERACTION_ACTION_NAMES: List[str] = [
    "IDLE", "SLOW_UP", "SLOW_DOWN", "SLOW_DOWN_FOR_CHARGE", "SLOW_DOWN_FOR_PROGRAM", "UP_AND_DOWN",
    "SIT_DOWN", "SIT_DOWN_FOR_PROGRAM", "STAND_UP", "SHAKE_HAND",
    "SHAKE_HAND_WITH_SIT_DOWN", "NOD", "SHAKE_HEAD", "STRETCH", "PEE", "TWIST", "PUSH_UP", "NEW_YEAR",
    "WAG_TAIL", "STOMP", "SNIFF", "CELEBRATE", "JUMP", "DANCE", "KICK_BALL", "TOUCH_GROUND_RIGHT",
    "TOUCH_GROUND_LEFT", "PLAY_DEAD", "STEP_INTERACTION", "FORWARD_INTERACTION", "BACK_INTERACTION",
    "LEFT_INTERACTION", "RIGHT_INTERACTION", "LOW_FORWARD_AND_BACKWARD_INTERACTION",
    "LOW_FORWARD_INTERACTION", "LOW_BACKWARD_INTERACTION", "LOW_LEFT_INTERACTION",
    "LOW_RIGHT_INTERACTION", "STOP_INTERACTION", "UP_AND_DOWN_FOR_TEST",
    "ROLLOVER_RECOVERY_RIGHT", "ROLLOVER_RECOVERY_LEFT", "FLAILING", "STOP_FLAILING",
    "LIGHT_ON_INTERACTION", "LIGHT_OFF_INTERACTION",
    "SWING_LEFT_AND_RIGHT", "SWING_LEFT", "SWING_RIGHT",
    "EXCITED_INSPACE", "LAZY_PAT_PAT", "CHEEKY_PAW", "WHINING",
    "SNIFF_FORWARD_INTERACTION", "SPACE_BACKWARD_INTERACTION", "SNIFF_LEFT_INTERACTION",
    "SNIFF_RIGHT_INTERACTION", "SNIFF_STEP_INTERACTION", "LEFT_ANGLE_INTERACTION",
    "RIGHT_ANGLE_INTERACTION",
]


class EarAction(IntEnum):
    IDLE = 0
    EAR_SHAKE_ASYN_1_3 = 1
    EAR_SHAKE_ASYN_1_2 = 2
    EAR_SHAKE_SYN = 3
    EAR_SHAKE_SYN_FOR_BLE = 4
    EAR_PEAR1 = 5
    EAR_PEAR2 = 6
    EAR_PEAR3 = 7
    EAR_STAND = 8
    EAR_STAND_LEFT = 9
    EAR_STAND_RIGHT = 10
    EAR_STAND_LEFT_AND_RIGHT = 11
    EAR_FOR_WINK = 12
    EAR_FOR_VIDEO = 13
    EAR_PERCENTAGE_BASIC = 14
    SPECIAL_DETECTION_AND_NOT_OPERATED_TOGGLE_BASIC = 15
    EAR_FLICK_EXCITED = 16
    EAR_FLICK_LEFT_QUICK = 17
    EAR_FLICK_RIGHT_QUICK = 18
    EAR_FLICK_ALTERNATE = 19
    EAR_FLICK_LEFT_AND_RIGHT_UP = 20
    EAR_FLICK_RANDOM = 21
    EAR_WIGGLE_SUBTLE_SELF_STABLE = 22
    EAR_FLICK_RANDOM_NEGATIVE = 23
    EAR_FLICK_RANDOM_POSITIVE = 24
    EAR_BREATHE = 25
    EAR_DOWN = 26

EAR_ACTION_NAMES: List[str] = [
    "EAR_IDLE",
    "EAR_SHAKE_ASYN_1_3", "EAR_SHAKE_ASYN_1_2", "EAR_SHAKE_SYN", "EAR_SHAKE_SYN_FOR_BLE",
    "EAR_PEAR1", "EAR_PEAR2", "EAR_PEAR3",
    "EAR_STAND", "EAR_STAND_LEFT", "EAR_STAND_RIGHT", "EAR_STAND_LEFT_AND_RIGHT",
    "EAR_FOR_WINK", "EAR_FOR_VIDEO",
    "EAR_PERCENTAGE_BASIC", "SPECIAL_DETECTION_AND_NOT_OPERATED_TOGGLE_BASIC",
    "EAR_FLICK_EXCITED", "EAR_FLICK_LEFT_QUICK", "EAR_FLICK_RIGHT_QUICK", "EAR_FLICK_ALTERNATE",
    "EAR_FLICK_LEFT_AND_RIGHT_UP", "EAR_FLICK_RANDOM", "EAR_WIGGLE_SUBTLE_SELF_STABLE",
    "EAR_FLICK_RANDOM_NEGATIVE", "EAR_FLICK_RANDOM_POSITIVE", "EAR_BREATHE", "EAR_DOWN",
]


class ExpressionAction(IntEnum):
    IDLE = 0
    HAPPY_01 = 1
    HAPPY_02 = 2
    HAPPY_03 = 3
    HAPPY_04 = 4
    SMILE_01 = 5
    SMILE_02 = 6
    SMILE_03 = 7
    LOVE_01 = 8
    LOVE_02 = 9
    ANGER_01 = 10
    ANGER_02 = 11
    ANGER_03 = 12
    ANGER_04 = 13
    SAD_01 = 14
    SAD_02 = 15
    SAD_03 = 16
    DOUBLE_SAD_03 = 17
    SAD_04 = 18
    SCARED_01 = 19
    SCARED_02 = 20
    COMFORTABLE_01 = 21
    COMFORTABLE_02 = 22
    DOUBT_01 = 23
    DOUBT_02 = 24
    DOUBT_03 = 25
    NERVOUS = 26
    NERVOUS_COMPLETE = 27
    TIRED = 28
    TIRED_COMPLETE = 29
    SLEEPY = 30
    SLEEPY_COMPLETE = 31
    WINK_FAST = 32
    WINK_NORMAL = 33
    LOOK_RIGHT = 34
    LOOK_LEFT = 35
    LOOK_LEFT_AND_RIGHT = 36
    NOTE_PARTICLE_CIRCLE = 37
    MUSIC = 38
    BASKETBALL = 39
    PINGPONG = 40
    FOOTBALL = 41
    SOUND_0 = 42
    SOUND_25 = 43
    SOUND_50 = 44
    SOUND_75 = 45
    SOUND_100 = 46
    SOUND_CIRCLE = 47
    GET_UP = 48
    EAT_SNACK = 49
    CHARGING = 50
    SUNGLASSES = 51
    EYES_FIGHTING = 52
    TURN_OFF = 53
    CARING = 54
    SHY = 55
    DRINK = 56
    ALERT = 57
    BORING = 58
    NO_WIFI = 59
    SHAME = 60
    SHAME_02 = 61
    SNIFF_EXPRESSION = 62
    DEAD = 63
    PRIDE = 64
    YAWN = 65
    LIGHT_ON = 66
    LIGHT_OFF = 67

    # Backward-compatible alias
    SNIFF = SNIFF_EXPRESSION


EXPRESSION_ACTION_NAMES: List[str] = [
    "IDLE",
    "HAPPY_01", "HAPPY_02", "HAPPY_03", "HAPPY_04",
    "SMILE_01", "SMILE_02", "SMILE_03",
    "LOVE_01", "LOVE_02",
    "ANGER_01", "ANGER_02", "ANGER_03", "ANGER_04",
    "SAD_01", "SAD_02", "SAD_03", "DOUBLE_SAD_03", "SAD_04",
    "SCARED_01", "SCARED_02",
    "COMFORTABLE_01", "COMFORTABLE_02",
    "DOUBT_01", "DOUBT_02", "DOUBT_03",
    "NERVOUS", "NERVOUS_COMPLETE",
    "TIRED", "TIRED_COMPLETE",
    "SLEEPY", "SLEEPY_COMPLETE",
    "WINK_FAST", "WINK_NORMAL",
    "LOOK_RIGHT", "LOOK_LEFT", "LOOK_LEFT_AND_RIGHT",
    "NOTE_PARTICLE_CIRCLE", "MUSIC",
    "BASKETBALL", "PINGPONG", "FOOTBALL",
    "SOUND_0", "SOUND_25", "SOUND_50", "SOUND_75", "SOUND_100", "SOUND_CIRCLE",
    "GET_UP", "EAT_SNACK", "CHARGING", "SUNGLASSES", "EYES_FIGHTING", "TURN_OFF",
    "CARING", "SHY", "DRINK", "ALERT", "BORING", "NO_WIFI", "SHAME", "SHAME_02", "SNIFF_EXPRESSION", "DEAD",
    "PRIDE", "YAWN", "LIGHT_ON", "LIGHT_OFF",
]


TONE_LIST: List[Tuple[int, str]] = [
    (1, "JEEZ"),
    (2, "UH"),
    (3, "EATING"),
    (4, "CHARGING"),
    (5, "CURIOUS"),
    (6, "SLEEPY"),
    (7, "HENG"),
    (8, "SAD"),
    (9, "ANGRY"),
    (10, "DOUBT"),
    (11, "AGREE"),
    (12, "ENHENG"),
    (13, "ALERT"),
    (14, "WAKE_UP"),
    (15, "COMFORT"),
    (16, "SIGH"),
    (17, "SNORE"),
    (18, "SNIFF"),
    (19, "BEAT1"),
    (20, "BEAT2"),
    (21, "BEAT3"),
    (22, "BEAT4"),
    (23, "BEAT5"),
    (24, "BEAT6"),
    (25, "BEAT7"),
]


class Tone(IntEnum):
    STOP = 0
    JEEZ = 1
    UH = 2
    EATING = 3
    CHARGING = 4
    CURIOUS = 5
    SLEEPY = 6
    HENG = 7
    SAD = 8
    ANGRY = 9
    DOUBT = 10
    AGREE = 11
    ENHENG = 12
    ALERT = 13
    WAKE_UP = 14
    COMFORT = 15
    SIGH = 16
    SNORE = 17
    SNIFF = 18
    BEAT1 = 19
    BEAT2 = 20
    BEAT3 = 21
    BEAT4 = 22
    BEAT5 = 23
    BEAT6 = 24
    BEAT7 = 25


def resolve_action(name_or_id) -> Action:
    """
    Convert a string name or integer to an :class:`Action`.

    Accepts:
    - An :class:`Action` enum member (returned as-is).
    - An integer matching a valid Action value.
    - A string key from :data:`ACTION_ALIASES` (case-insensitive for ASCII names).

    Raises :class:`ValueError` for unrecognised inputs.
    """
    if isinstance(name_or_id, Action):
        return name_or_id
    if isinstance(name_or_id, int):
        if name_or_id in _HIDDEN_ACTION_ID_MAP:
            return _HIDDEN_ACTION_ID_MAP[name_or_id]
        return Action(name_or_id)
    if isinstance(name_or_id, str):
        key = name_or_id.lower()
        if key in ACTION_ALIASES:
            return ACTION_ALIASES[key]
        # Try original casing (for Chinese strings that are already lowercase)
        if name_or_id in ACTION_ALIASES:
            return ACTION_ALIASES[name_or_id]
    raise ValueError(
        f"Unknown action {name_or_id!r}. "
        f"Use an Action enum member, an integer ID, or a name from ACTION_ALIASES."
    )
