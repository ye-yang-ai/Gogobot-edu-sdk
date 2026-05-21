"""
aidog_sdk — Python SDK for the Changba AI-Dog robot.

Quick start::

    from aidog_sdk import AiDog, Action

    with AiDog() as dog:
        dog.connect("Changba-Ai-Dog")
        dog.perform_action("sit_down")
        dog.perform_action(Action.SHAKE_HAND, count=3)
        dog.perform_action("dance", duration=5)
"""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

from .dog import (
    AiDog,
    Movement,
    MODE_AUDIO,
    MODE_EAR,
    MODE_EXPRESSION,
    MODE_INTERACTION,
    MODE_SENSOR,
    MODE_SPORT,
    MODE_STREAM,
    MODE_ROBOT_ADJUST,
    CONFIG_SET_VOLUME,
)
from .actions import (
    ACTION_ALIASES,
    COUNT_BASED,
    EAR_ACTION_NAMES,
    EXPRESSION_ACTION_NAMES,
    INTERACTION_ACTION_NAMES,
    TIMER_BASED,
    TONE_LIST,
    Action,
    EarAction,
    ExpressionAction,
    Tone,
    resolve_action,
)
from .dev_pc_ws import DevPcWebSocketHost, run_dev_pc_websocket_server

__all__ = [
    "AiDog",
    "Movement",
    "MODE_SPORT",
    "MODE_INTERACTION",
    "MODE_EAR",
    "MODE_EXPRESSION",
    "MODE_AUDIO",
    "MODE_SENSOR",
    "MODE_STREAM",
    "MODE_ROBOT_ADJUST",
    "CONFIG_SET_VOLUME",
    "Action",
    "EarAction",
    "ExpressionAction",
    "Tone",
    "INTERACTION_ACTION_NAMES",
    "EAR_ACTION_NAMES",
    "EXPRESSION_ACTION_NAMES",
    "TONE_LIST",
    "ACTION_ALIASES",
    "TIMER_BASED",
    "COUNT_BASED",
    "resolve_action",
    "DevPcWebSocketHost",
    "run_dev_pc_websocket_server",
]

__version__ = "0.1.0"
