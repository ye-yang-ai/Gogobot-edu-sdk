"""Input adapters for the AIDog IMU balance ball game."""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


REWARD_AUDIO_NAMES = ("AGREE", "HENG", "UH", "CURIOUS", "WAKE_UP")
REWARD_EXPRESSION_NAMES = ("HAPPY_01", "HAPPY_02", "LOVE_01", "SMILE_01", "PRIDE")
DANGER_EXPRESSION_NAME = "NERVOUS"
START_AUDIO_NAME = "WAKE_UP"
START_EXPRESSION_NAME = "EYES_FIGHTING"
FINISH_AUDIO_NAME = "SAD"
FINISH_EXPRESSION_NAME = "SHAME"


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
    max_angle_deg: float = 18.0
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
        angle = self.filtered_roll * self.config.sensitivity
        return clamp(angle, -self.config.max_angle_deg, self.config.max_angle_deg)


class WsImuReader:
    def __init__(
        self,
        latest_roll: LatestRoll,
        bind: str,
        port: int,
        hz: int,
        timeout_s: float,
        prepare_robot: bool,
        restore_special_detection: bool,
        pose_action: str,
    ) -> None:
        self.latest_roll = latest_roll
        self.bind = bind
        self.port = int(port)
        self.hz = int(hz)
        self.timeout_s = float(timeout_s)
        self.prepare_robot = bool(prepare_robot)
        self.restore_special_detection = bool(restore_special_detection)
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
                name="aidog-balance-ws-monitor",
            )
            self._monitor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self.dog is not None:
            try:
                self.dog.request_imu_stream(False, transport="ws")
            except Exception:
                pass
            if self.prepare_robot and self.restore_special_detection:
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

    def play_reward_audio(self) -> None:
        self.play_reward_feedback()

    def play_reward_feedback(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._send_random_audio(dog, REWARD_AUDIO_NAMES)
        self._send_random_expression(dog, REWARD_EXPRESSION_NAMES)

    def play_challenge_start_feedback(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._send_audio(dog, START_AUDIO_NAME)
        self._send_expression(dog, START_EXPRESSION_NAME)

    def play_challenge_finish_feedback(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._send_audio(dog, FINISH_AUDIO_NAME)
        self._send_expression(dog, FINISH_EXPRESSION_NAME)

    def play_danger_feedback(self) -> None:
        with self._lock:
            dog = self.dog
            host = self.host
            if dog is None or host is None or not host.is_robot_connected:
                return
        self._send_expression(dog, DANGER_EXPRESSION_NAME)

    def _send_random_audio(self, dog, names: Tuple[str, ...]) -> None:
        self._send_audio(dog, random.choice(names))

    def _send_random_expression(self, dog, names: Tuple[str, ...]) -> None:
        self._send_expression(dog, random.choice(names))

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

    def _on_imu(self, imu: Dict[str, object]) -> None:
        roll = imu.get("roll_deg")
        if isinstance(roll, (int, float)):
            self.latest_roll.update(float(roll))

    def _monitor_connection(self) -> None:
        stream_enabled = False
        deadline_s = time.monotonic() + max(0.0, self.timeout_s)
        while not self._stop_event.is_set():
            host = self.host
            dog = self.dog
            if host is None or dog is None:
                return
            connected = host.is_robot_connected
            if connected and not stream_enabled:
                try:
                    if self.prepare_robot:
                        self._prepare_robot_for_game(dog)
                    dog.request_imu_stream(True, hz=self.hz, transport="ws")
                    stream_enabled = True
                except Exception:
                    stream_enabled = False
            elif not connected:
                stream_enabled = False
                if self.timeout_s > 0.0 and time.monotonic() > deadline_s:
                    deadline_s = time.monotonic() + self.timeout_s
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
            target -= 12.0
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            target += 12.0
        self.roll = self.roll * 0.85 + target * 0.15
        self.latest_roll.update(self.roll)


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))
