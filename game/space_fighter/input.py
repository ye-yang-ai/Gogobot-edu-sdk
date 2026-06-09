"""Input adapters for the GOGO space fighter game."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


INPUT_KEYBOARD = "keyboard"
INPUT_AIDOG = "aidog"
POWERUP_FEEDBACK = {
    "weapon": ("AGREE", "PRIDE", "EAR_FLICK_EXCITED"),
    "shield": ("CURIOUS", "HAPPY_01", "EAR_STAND_LEFT_AND_RIGHT"),
    "heal": ("AGREE", "CARING", "EAR_WIGGLE_SUBTLE_SELF_STABLE"),
    "bomb": ("JEEZ", "ALERT", "EAR_FLICK_LEFT_AND_RIGHT_UP"),
}


class LatestImuAngles:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pitch_deg: Optional[float] = None
        self._roll_deg: Optional[float] = None
        self._timestamp_s = 0.0

    def update(self, pitch_deg: float, roll_deg: float) -> None:
        with self._lock:
            self._pitch_deg = float(pitch_deg)
            self._roll_deg = float(roll_deg)
            self._timestamp_s = time.monotonic()

    def snapshot(self) -> Tuple[Optional[float], Optional[float], float]:
        with self._lock:
            return self._pitch_deg, self._roll_deg, self._timestamp_s

    def clear(self) -> None:
        with self._lock:
            self._pitch_deg = None
            self._roll_deg = None
            self._timestamp_s = 0.0


@dataclass
class ImuControlConfig:
    deadzone_deg: float = 1.5
    alpha: float = 0.25
    sensitivity: float = 1.0
    max_tilt_deg: float = 18.0
    stale_s: float = 0.45
    invert_pitch: bool = False
    invert_roll: bool = False


class ImuMoveMapper:
    def __init__(self, config: ImuControlConfig) -> None:
        self.config = config
        self.baseline_pitch = 0.0
        self.baseline_roll = 0.0
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.has_baseline = False

    def reset(self, pitch_deg: float, roll_deg: float) -> None:
        self.baseline_pitch = float(pitch_deg)
        self.baseline_roll = float(roll_deg)
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.has_baseline = True

    def clear_baseline(self) -> None:
        self.baseline_pitch = 0.0
        self.baseline_roll = 0.0
        self.filtered_pitch = 0.0
        self.filtered_roll = 0.0
        self.has_baseline = False

    def update(self, pitch_deg: float, roll_deg: float) -> Tuple[float, float]:
        if not self.has_baseline:
            self.reset(pitch_deg, roll_deg)
        pitch = self._relative(float(pitch_deg), self.baseline_pitch, self.config.invert_pitch)
        roll = self._relative(float(roll_deg), self.baseline_roll, self.config.invert_roll)
        alpha = min(1.0, max(0.0, self.config.alpha))
        self.filtered_pitch = self.filtered_pitch * (1.0 - alpha) + pitch * alpha
        self.filtered_roll = self.filtered_roll * (1.0 - alpha) + roll * alpha
        move_x = self._axis(self.filtered_roll)
        move_y = self._axis(self.filtered_pitch)
        return move_x, move_y

    def _relative(self, value: float, baseline: float, invert: bool) -> float:
        value -= baseline
        if invert:
            value = -value
        if abs(value) < self.config.deadzone_deg:
            return 0.0
        return value

    def _axis(self, value: float) -> float:
        ratio = value * self.config.sensitivity / max(1.0, self.config.max_tilt_deg)
        return clamp(ratio, -1.0, 1.0)


class WsImuReader:
    def __init__(self, latest_angles: LatestImuAngles, bind: str, port: int, hz: int, pose_action: str = "slow_down") -> None:
        self.latest_angles = latest_angles
        self.bind = bind
        self.port = int(port)
        self.hz = int(hz)
        self.pose_action = str(pose_action)
        self.dog = None
        self.host = None
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        from aidog_sdk import AiDog, DevPcWebSocketHost

        with self._lock:
            self.dog = AiDog(imu_only_notify=True)
            self.dog.add_imu_listener(self._on_imu)
            self.host = DevPcWebSocketHost(host=self.bind, port=self.port, dog=self.dog)
            self.dog.attach_ws_control(self.host)
            self.host.start()
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_connection,
                daemon=True,
                name="aidog-space-fighter-ws-monitor",
            )
            self._monitor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.dog is not None:
            try:
                self.dog.request_imu_stream(False, transport="ws")
            except Exception:
                pass
        if self._monitor_thread is not None and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)
        self._monitor_thread = None
        if self.host is not None:
            try:
                self.host.stop()
            except Exception:
                pass
            self.host = None
        if self.dog is not None:
            try:
                self.dog.shutdown()
            except Exception:
                pass
            self.dog = None

    def restart(self) -> None:
        self.stop()
        self.latest_angles.clear()
        self.start()

    def is_connected(self) -> bool:
        host = self.host
        return bool(host is not None and host.is_robot_connected)

    def prepare_now(self) -> bool:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return False
        return self._send_pose_action(dog)

    def play_start_feedback(self) -> bool:
        return self._send_feedback("WAKE_UP", "EYES_FIGHTING", "EAR_STAND")

    def play_powerup_feedback(self, kind: Optional[str]) -> bool:
        audio, expression, ear = POWERUP_FEEDBACK.get(str(kind), ("AGREE", "HAPPY_01", "EAR_FLICK_RANDOM_POSITIVE"))
        return self._send_feedback(audio, expression, ear)

    def play_hit_feedback(self, life_lost: bool = False) -> bool:
        if life_lost:
            return self._send_feedback("JEEZ", "SHAME", "EAR_DOWN")
        return self._send_feedback("HENG", "NERVOUS", "EAR_FLICK_RANDOM_NEGATIVE")

    def play_boss_warning_feedback(self) -> bool:
        return self._send_feedback("WAKE_UP", "ALERT", "EAR_STAND")

    def play_stage_clear_feedback(self, final: bool = False) -> bool:
        if final:
            return self._send_feedback("WAKE_UP", "LOVE_01", "EAR_FLICK_LEFT_AND_RIGHT_UP")
        return self._send_feedback("AGREE", "PRIDE", "EAR_FLICK_RANDOM_POSITIVE")

    def play_game_over_feedback(self) -> bool:
        return self._send_feedback("SAD", "SHAME", "EAR_DOWN")

    def _on_imu(self, imu: Dict[str, object]) -> None:
        pitch = imu.get("pitch_deg")
        roll = imu.get("roll_deg")
        if isinstance(pitch, (int, float)) and isinstance(roll, (int, float)):
            self.latest_angles.update(float(pitch), float(roll))

    def _monitor_connection(self) -> None:
        stream_enabled = False
        while not self._stop_event.is_set():
            host = self.host
            dog = self.dog
            if host is None or dog is None:
                return
            connected = host.is_robot_connected
            if connected and not stream_enabled:
                try:
                    dog.request_imu_stream(True, hz=self.hz, transport="ws")
                    stream_enabled = True
                except Exception:
                    stream_enabled = False
            elif not connected:
                stream_enabled = False
            self._stop_event.wait(0.2)

    def _send_pose_action(self, dog) -> bool:
        try:
            from aidog_sdk import resolve_action

            action = int(resolve_action(self.pose_action))
            dog.send_interaction(action, transport="ws")
            return True
        except Exception:
            return False

    def _send_feedback(self, audio_name: str, expression_name: str, ear_name: str) -> bool:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return False
        ok = self._send_audio(dog, audio_name)
        ok = self._send_expression(dog, expression_name) or ok
        ok = self._send_ear(dog, ear_name) or ok
        return ok

    def _send_audio(self, dog, name: str) -> bool:
        try:
            from aidog_sdk import Tone

            dog.send_audio(getattr(Tone, name), transport="ws")
            return True
        except Exception:
            return False

    def _send_expression(self, dog, name: str) -> bool:
        try:
            from aidog_sdk import ExpressionAction

            dog.send_expression(getattr(ExpressionAction, name), transport="ws")
            return True
        except Exception:
            return False

    def _send_ear(self, dog, name: str) -> bool:
        try:
            from aidog_sdk import EarAction

            dog.send_ear(getattr(EarAction, name), transport="ws")
            return True
        except Exception:
            return False


def read_imu_move(latest_angles: LatestImuAngles, mapper: ImuMoveMapper) -> Tuple[float, float, bool]:
    pitch, roll, timestamp_s = latest_angles.snapshot()
    if pitch is None or roll is None:
        return 0.0, 0.0, False
    if time.monotonic() - timestamp_s > mapper.config.stale_s:
        return 0.0, 0.0, False
    move_x, move_y = mapper.update(pitch, roll)
    return move_x, move_y, True


def imu_status(latest_angles: LatestImuAngles, mapper: ImuMoveMapper, reader: Optional[WsImuReader]) -> str:
    if reader is None:
        return "OFF"
    if not reader.is_connected():
        return "WAIT DOG"
    _, _, timestamp_s = latest_angles.snapshot()
    if timestamp_s <= 0.0:
        return "LINK OK"
    if time.monotonic() - timestamp_s > mapper.config.stale_s:
        return "LINK OK"
    return "IMU READY" if mapper.has_baseline else "CALIBRATING"


def merge_keyboard_and_imu(keyboard_x: float, keyboard_y: float, imu_x: float, imu_y: float, imu_active: bool) -> Tuple[float, float]:
    if not imu_active:
        return keyboard_x, keyboard_y
    return _stronger_axis(keyboard_x, imu_x), _stronger_axis(keyboard_y, imu_y)


def _stronger_axis(first: float, second: float) -> float:
    return second if abs(second) > abs(first) else first


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))
