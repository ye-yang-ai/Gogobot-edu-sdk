"""Input adapters for the GOGO IMU brick breaker game."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
import random
from typing import Dict, Optional, Tuple


REWARD_AUDIO_NAMES = ("AGREE", "HENG", "UH", "CURIOUS", "WAKE_UP")
REWARD_EXPRESSION_NAMES = ("HAPPY_01", "HAPPY_02", "LOVE_01", "SMILE_01", "PRIDE")
REWARD_EAR_NAMES = (
    "EAR_FLICK_EXCITED",
    "EAR_FLICK_LEFT_AND_RIGHT_UP",
    "EAR_FLICK_RANDOM_POSITIVE",
    "EAR_WIGGLE_SUBTLE_SELF_STABLE",
)


class LatestRoll:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._roll_deg: Optional[float] = None
        self._timestamp_s = 0.0

    def update(self, roll_deg: float) -> None:
        with self._lock:
            self._roll_deg = float(roll_deg)
            self._timestamp_s = time.monotonic()

    def snapshot(self) -> Tuple[Optional[float], float]:
        with self._lock:
            return self._roll_deg, self._timestamp_s

    def clear(self) -> None:
        with self._lock:
            self._roll_deg = None
            self._timestamp_s = 0.0


@dataclass
class RollFilterConfig:
    deadzone_deg: float = 1.0
    alpha: float = 0.25
    sensitivity: float = 1.0
    max_roll_deg: float = 18.0
    invert: bool = False


class RollFilter:
    def __init__(self, config: RollFilterConfig) -> None:
        self.config = config
        self.baseline_roll = 0.0
        self.filtered_roll = 0.0

    def reset(self, baseline_roll: float) -> None:
        self.baseline_roll = float(baseline_roll)
        self.filtered_roll = 0.0

    def update(self, raw_roll_deg: float) -> float:
        roll = float(raw_roll_deg) - self.baseline_roll
        if self.config.invert:
            roll = -roll
        if abs(roll) < self.config.deadzone_deg:
            roll = 0.0
        alpha = min(1.0, max(0.0, self.config.alpha))
        self.filtered_roll = self.filtered_roll * (1.0 - alpha) + roll * alpha
        return clamp(self.filtered_roll * self.config.sensitivity, -self.config.max_roll_deg, self.config.max_roll_deg)


@dataclass
class RollToPaddleMapper:
    screen_width: float
    paddle_width: float
    max_roll_deg: float = 18.0

    def map(self, control_roll_deg: float) -> float:
        max_offset = max(0.0, (self.screen_width - self.paddle_width) * 0.5)
        ratio = clamp(control_roll_deg / max(1.0, self.max_roll_deg), -1.0, 1.0)
        return self.screen_width * 0.5 + ratio * max_offset


class WsImuReader:
    def __init__(self, latest_roll: LatestRoll, bind: str, port: int, hz: int, pose_action: str = "slow_down") -> None:
        self.latest_roll = latest_roll
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
                name="aidog-brick-ws-monitor",
            )
            self._monitor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.dog is not None:
            try:
                self.dog.request_imu_stream(False, transport="ws")
            except Exception:
                pass
            try:
                self.dog.set_special_detection(True, transport="ws")
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
        self.latest_roll.clear()
        self.start()

    def prepare_now(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._prepare_robot_for_game(dog)

    def play_reward_feedback(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._send_random_audio(dog, REWARD_AUDIO_NAMES)
        self._send_random_expression(dog, REWARD_EXPRESSION_NAMES)
        self._send_random_ear(dog, REWARD_EAR_NAMES)

    def _on_imu(self, imu: Dict[str, object]) -> None:
        roll = imu.get("roll_deg")
        if isinstance(roll, (int, float)):
            self.latest_roll.update(float(roll))

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

    def _prepare_robot_for_game(self, dog) -> None:
        from aidog_sdk import resolve_action

        try:
            dog.set_special_detection(False, transport="ws")
        except Exception:
            pass
        pose_action = int(resolve_action(self.pose_action))
        for _ in range(3):
            if self._stop_event.wait(0.25):
                return
            try:
                dog.send_interaction(pose_action, transport="ws")
                return
            except Exception:
                continue

    def _send_random_audio(self, dog, names: Tuple[str, ...]) -> None:
        self._send_audio(dog, random.choice(names))

    def _send_random_expression(self, dog, names: Tuple[str, ...]) -> None:
        self._send_expression(dog, random.choice(names))

    def _send_random_ear(self, dog, names: Tuple[str, ...]) -> None:
        self._send_ear(dog, random.choice(names))

    def _send_audio(self, dog, name: str) -> None:
        try:
            from aidog_sdk import Tone

            dog.send_audio(getattr(Tone, name), transport="ws")
        except Exception:
            pass

    def _send_expression(self, dog, name: str) -> None:
        try:
            from aidog_sdk import ExpressionAction

            dog.send_expression(getattr(ExpressionAction, name), transport="ws")
        except Exception:
            pass

    def _send_ear(self, dog, name: str) -> None:
        try:
            from aidog_sdk import EarAction

            dog.send_ear(getattr(EarAction, name), transport="ws")
        except Exception:
            pass


class BleImuReader:
    def __init__(self, latest_roll: LatestRoll, name_prefix: str, address: Optional[str], hz: int) -> None:
        self.latest_roll = latest_roll
        self.name_prefix = name_prefix
        self.address = address
        self.hz = int(hz)
        self.dog = None

    def start(self) -> None:
        from aidog_sdk import AiDog

        self.dog = AiDog(imu_only_notify=True)
        self.dog.add_imu_listener(self._on_imu)
        if self.address:
            self.dog.connect(address=self.address)
        else:
            self.dog.connect(self.name_prefix)
        self.dog.request_imu_stream(True, hz=self.hz)

    def stop(self) -> None:
        if self.dog is None:
            return
        try:
            self.dog.request_imu_stream(False)
        except Exception:
            pass
        try:
            if self.dog.is_connected:
                self.dog.disconnect()
        except Exception:
            pass
        try:
            self.dog.shutdown()
        except Exception:
            pass
        self.dog = None

    def _on_imu(self, imu: Dict[str, object]) -> None:
        roll = imu.get("roll_deg")
        if isinstance(roll, (int, float)):
            self.latest_roll.update(float(roll))


class KeyboardRollReader:
    def __init__(self, latest_roll: LatestRoll) -> None:
        self.latest_roll = latest_roll
        self.roll = 0.0

    def start(self) -> None:
        self.latest_roll.update(0.0)

    def stop(self) -> None:
        pass

    def update(self, keys, pg) -> None:
        target = 0.0
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            target -= 18.0
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            target += 18.0
        self.roll = self.roll * 0.82 + target * 0.18
        self.latest_roll.update(self.roll)


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))
