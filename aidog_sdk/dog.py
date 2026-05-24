"""
AiDog — high-level Python API for the Changba AI-Dog robot.

Typical usage::

    from aidog_sdk import AiDog, Action

    dog = AiDog()
    dog.connect("Changba-Ai-Dog")

    dog.perform_action("sit_down")
    dog.perform_action("shake_hand", count=3)
    dog.perform_action("dance", duration=5)

    dog.disconnect()
"""

from __future__ import annotations

import json
import logging
import math
import struct
import threading
import time
from enum import IntEnum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from ._ble import BleTransport
from .actions import (
    ANGLE_BASED,
    COUNT_BASED,
    TIMER_BASED,
    Action,
    EarAction,
    ExpressionAction,
    Tone,
    resolve_action,
)

logger = logging.getLogger(__name__)

# Binary mode constants
MODE_SPORT = 0x01
MODE_INTERACTION = 0x02
MODE_EAR = 0x00
MODE_EXPRESSION = 0x05
MODE_AUDIO = 0x06
MODE_SENSOR = 0x08
MODE_STREAM = 0x09
# Smooth body/foot/joint adjustment (firmware `remote_control.c` mode=0x0A; aligned with `robot_adjust.c`)
MODE_ROBOT_ADJUST = 0x0A
CONFIG_SET_VOLUME = 1
_SPECIAL_DETECTION_TOGGLE = 15
_SPECIAL_DETECTION_ENABLE = 100
_SPECIAL_DETECTION_DISABLE = 101
_APP_UNKNOWN_CONTROL_MODE = 5

_RADJ_SUB_POSE = 0x01
_RADJ_SUB_FOOT = 0x02
_RADJ_SUB_JOINT = 0x03
_RADJ_SUB_RETURN_BASIC = 0x04
_RADJ_SUB_DEFAULT_POSE_FOR_SDK = 0x05

_POSE_PARAM_ORDER = (
    "cog_x",  # Center-of-gravity X coordinate
    "cog_z",  # Center-of-gravity Z coordinate
    "roll",   # Roll angle
    "pitch",  # Pitch angle
)
_FOOT_PARAM_ORDER = (
    "foot_0_x",  # Right-front X coordinate
    "foot_0_z",  # Right-front Z coordinate
    "foot_1_x",  # Right-rear X coordinate
    "foot_1_z",  # Right-rear Z coordinate
    "foot_2_x",  # Left-front X coordinate
    "foot_2_z",  # Left-front Z coordinate
    "foot_3_x",  # Left-rear X coordinate
    "foot_3_z",  # Left-rear Z coordinate
)
_JOINT_PARAM_ORDER = (
    "joint_0_1",  # Right-front thigh joint angle
    "joint_0_2",  # Right-front shin joint angle
    "joint_1_1",  # Right-rear thigh joint angle
    "joint_1_2",  # Right-rear shin joint angle
    "joint_2_1",  # Left-front thigh joint angle
    "joint_2_2",  # Left-front shin joint angle
    "joint_3_1",  # Left-rear thigh joint angle
    "joint_3_2",  # Left-rear shin joint angle
)


class Movement(IntEnum):
    FORWARD = 0x01
    BACK = 0x02
    STEP = 0x10
    RIGHT = 0x08
    LEFT = 0x04


class AiDog:
    """
    Synchronous controller for the Changba AI-Dog robot.

    All methods block until the BLE operation completes (or raise an exception
    on failure). Thread-safety: not guaranteed — use one instance per thread.

    Parameters
    ----------
    on_notify:
        Optional callback invoked on every BLE notification from the device.
        Receives the raw ``bytes`` payload.
    imu_only_notify:
        Keep for backward compatibility. On some firmware builds, IMU ae04
        reporting depends on ae02 CCC being enabled, so SDK always subscribes
        both ae02 and ae04. IMU-only output should be handled in callbacks.
    """

    def __init__(
        self,
        on_notify: Optional[Callable[[bytes], None]] = None,
        *,
        imu_only_notify: bool = False,
    ):
        self._user_on_notify = on_notify
        self._ble = BleTransport(
            on_notify=self._on_notify,
            subscribe_ae02=True,
            subscribe_ae04=True,
        )
        self._last_interaction_task_status: Optional[int] = None
        self._last_imu_data: Optional[Dict[str, object]] = None
        self._last_tof_data: Optional[Dict[str, object]] = None
        # Increments only when a notify JSON includes interaction_task_status (not on IMU/TOF-only packets).
        self._interaction_status_notify_seq = 0
        self._notify_lock = threading.Lock()
        self._imu_callbacks: List[Callable[[Dict[str, object]], None]] = []
        self._tof_callbacks: List[Callable[[Dict[str, object]], None]] = []
        self._special_detection_enabled: Optional[bool] = None

    @staticmethod
    def _normalize_imu_payload(imu: Dict[str, object]) -> Dict[str, object]:
        """
        Normalize firmware IMU payload for host developers.

        Firmware currently reports yaw/pitch/roll as integer milli-degrees
        (deg * 1000). This helper keeps backward compatibility while exposing
        angle values in degrees.
        """
        out: Dict[str, object] = dict(imu)
        raw_angles: Dict[str, float] = {}
        for axis in ("yaw", "pitch", "roll"):
            v = out.get(axis)
            if isinstance(v, (int, float)):
                raw_angles[axis] = float(v)

        # Decide scale once per packet to avoid mixed conversion.
        # Firmware format is typically milli-degrees for all three axes.
        use_milli_deg = False
        if raw_angles:
            max_abs = max(abs(v) for v in raw_angles.values())
            all_int_like = all(abs(v - round(v)) < 1e-9 for v in raw_angles.values())
            if max_abs > 1000.0:
                use_milli_deg = True
            elif all_int_like and max_abs > 180.0:
                use_milli_deg = True

        angle_deg: Dict[str, float] = {}
        for axis in ("yaw", "pitch", "roll"):
            if axis not in raw_angles:
                continue
            fv = raw_angles[axis] / 1000.0 if use_milli_deg else raw_angles[axis]
            angle_deg[axis] = fv
            out[f"{axis}_deg"] = fv
        if angle_deg:
            out["angle_deg"] = angle_deg
        return out

    @staticmethod
    def _parse_notify_dict(
        obj: Dict[str, Any],
    ) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[Dict[str, object]]]:
        """Extract interaction_task_status, imu, tof from one firmware JSON object."""
        parsed_status: Optional[int] = None
        if "interaction_task_status" in obj:
            value = obj.get("interaction_task_status")
            if isinstance(value, int):
                parsed_status = value
        parsed_imu: Optional[Dict[str, object]] = None
        imu = obj.get("imu")
        if isinstance(imu, dict):
            parsed_imu = AiDog._normalize_imu_payload(imu)
        parsed_tof: Optional[Dict[str, object]] = None
        tof = obj.get("tof")
        if isinstance(tof, dict):
            parsed_tof = dict(tof)
        return parsed_status, parsed_imu, parsed_tof

    @staticmethod
    def parse_notify_json_text(
        text: str,
    ) -> Tuple[Optional[int], Optional[Dict[str, object]], Optional[Dict[str, object]]]:
        """
        Parse a single firmware notify line (BLE ae04 or Dev PC WebSocket text frame).

        Returns ``(interaction_task_status | None, imu_dict | None, tof_dict | None)``.
        """
        try:
            t = text.strip()
            if not t.startswith("{") or not t.endswith("}"):
                return None, None, None
            obj = json.loads(t)
            if not isinstance(obj, dict):
                return None, None, None
            return AiDog._parse_notify_dict(obj)
        except Exception:
            return None, None, None

    def _dispatch_parsed_notify(
        self,
        parsed_status: Optional[int],
        parsed_imu: Optional[Dict[str, object]],
        parsed_tof: Optional[Dict[str, object]],
    ) -> None:
        if parsed_status is None and parsed_imu is None and parsed_tof is None:
            return
        with self._notify_lock:
            if parsed_status is not None:
                self._interaction_status_notify_seq += 1
                self._last_interaction_task_status = parsed_status
            if parsed_imu is not None:
                self._last_imu_data = parsed_imu
            if parsed_tof is not None:
                self._last_tof_data = parsed_tof

        if parsed_imu is not None:
            for cb in list(self._imu_callbacks):
                try:
                    cb(parsed_imu)
                except Exception:
                    pass

        if parsed_tof is not None:
            for cb in list(self._tof_callbacks):
                try:
                    cb(parsed_tof)
                except Exception:
                    pass

    def feed_sensor_stream_json(self, text: str) -> None:
        """
        Feed one sensor JSON line from the LAN Dev PC WebSocket (same payload as ``ae04``).

        Updates ``get_latest_imu`` / ``get_latest_tof`` and registered listeners.
        """
        ps, pi, pt = self.parse_notify_json_text(text)
        self._dispatch_parsed_notify(ps, pi, pt)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def scan(self, name_prefix: str = "Changba-Ai-Dog") -> List[Tuple[str, str]]:
        """
        Scan for nearby AI-Dog devices.

        Returns a list of ``(name, address)`` tuples whose BLE advertisement
        name starts with *name_prefix*.

        Example::

            devices = dog.scan()
            # [("Changba-Ai-Dog-001", "AA:BB:CC:DD:EE:FF"), ...]
        """
        return self._ble.scan(name_prefix)

    def connect(
        self,
        name_prefix: str = "Changba-Ai-Dog",
        *,
        address: Optional[str] = None,
        retries: int = 3,
        retry_delay_s: float = 1.0,
    ) -> None:
        """
        Connect to an AI-Dog.

        If *address* is provided the scan step is skipped and the device is
        connected directly.  Otherwise, a BLE scan is performed and the **first**
        device whose name starts with *name_prefix* is selected.

        Parameters
        ----------
        name_prefix:
            BLE advertisement name prefix to match (default ``"Changba-Ai-Dog"``).
        address:
            Optional MAC address (Windows/Linux) or UUID (macOS).  When given,
            *name_prefix* is ignored.
        retries:
            Number of automatic retries when BLE connection fails (default 3).
        retry_delay_s:
            Delay between retries in seconds (default 1.0s).

        Raises
        ------
        RuntimeError
            If no matching device is found during the scan.
        ConnectionError
            If the BLE connect call fails.
        """
        if address is None:
            devices = self._ble.scan(name_prefix)
            if not devices:
                raise RuntimeError(
                    f"No device found with name prefix '{name_prefix}'. "
                    "Make sure the robot is powered on and in range."
                )
            # Pick the first match; surface choices to the caller via scan() if needed
            name, address = devices[0]
            logger.info("Found device: %s (%s)", name, address)

        ok = self._ble.connect(address, retries=retries, retry_delay_s=retry_delay_s)
        if not ok:
            raise ConnectionError(f"Failed to connect to {address}.")
        logger.info("Connected to %s", address)

    def disconnect(self) -> None:
        """Disconnect from the device and release BLE resources."""
        self._ble.disconnect()
        logger.info("Disconnected.")

    def shutdown(self) -> None:
        """Disconnect and stop the background asyncio thread."""
        self._ble.shutdown()

    @property
    def is_connected(self) -> bool:
        """``True`` if currently connected to a device."""
        return self._ble.is_connected

    def perform_action(
        self,
        action: Union[str, int, Action],
        *,
        duration: Optional[int] = None,
        count: Optional[int] = None,
        angle: Optional[int] = None,
        timeout_s: float = 20.0,
        require_running_state: bool = True,
    ) -> bool:
        """
        Send an interaction action and wait for firmware completion feedback.

        This method relies on `interaction_task_status` in notify JSON:
        - 0: NOT_RUN
        - 1: RUNNING
        - 2: KILLED

        Parameters:
        - duration: For TIMER_BASED actions, sent to firmware as action param (uint8 seconds).
        - count: For COUNT_BASED actions, sent to firmware as action param (uint8 repeats).
        - angle: For ANGLE_BASED actions, sent to firmware as action param (uint16 degrees).
        """
        # Ensure previous interaction has reached idle before dispatching a new one.
        # This reduces overlap/race between consecutive interaction actions.
        self._wait_until_interaction_idle(timeout_s=6.0)

        act = resolve_action(action)
        action_param: Optional[int] = None
        is_count_based = False
        is_timer_based = False
        is_angle_based = False
        if count is not None and act in COUNT_BASED:
            action_param = max(1, min(255, int(count)))
            is_count_based = True
        elif duration is not None and act in TIMER_BASED:
            action_param = max(1, min(255, int(duration)))
            is_timer_based = True
        elif angle is not None and act in ANGLE_BASED:
            action_param = max(1, min(360, int(angle)))
            is_angle_based = True

        # With firmware-side param control enabled, one command is enough:
        # - with param -> firmware handles repeat/time internally
        # - without param -> normal interaction thread
        repeat = 1
        wait_timeout = float(timeout_s)
        if action_param is not None and is_timer_based:
            # Timed interactions may legitimately take longer than timeout_s.
            wait_timeout = max(wait_timeout, float(action_param) + 3.0)
        elif action_param is not None and is_count_based:
            # Count-based interactions (e.g. shake_hand xN) can be long.
            # Reserve ~4s per repeat plus small fixed overhead.
            wait_timeout = max(wait_timeout, float(action_param) * 4.0 + 3.0)
        elif action_param is not None and is_angle_based:
            # Firmware angle turn loop has a 12s safety timeout, plus stop settling.
            wait_timeout = max(wait_timeout, 15.0)

        for _ in range(repeat):
            with self._notify_lock:
                start_status_seq = self._interaction_status_notify_seq

            self.send_interaction(int(act), action_param)

            deadline = time.time() + max(0.1, wait_timeout)
            seen_running = False
            started = False
            finished = False
            while time.time() < deadline:
                with self._notify_lock:
                    status = self._last_interaction_task_status
                    status_tick_changed = (
                        self._interaction_status_notify_seq > start_status_seq
                    )

                if status == 1:
                    seen_running = True
                    started = True
                elif status not in (None, 0):
                    # Any non-idle state also means action has started.
                    started = True
                if status == 0 and status_tick_changed:
                    # Require evidence the task actually ran before treating idle as done.
                    # (IMU/TOF-only notifies no longer advance the seq used here.)
                    if (
                        not require_running_state
                        or seen_running
                        or started
                    ):
                        finished = True
                        break
                if status == 2:
                    return False

                # Wait for next notify tick; periodic notify is ~1.5s in firmware
                time.sleep(0.2)

            if not finished:
                return False

        return True

    def _wait_until_interaction_idle(self, timeout_s: float = 6.0) -> bool:
        """Wait until interaction status becomes idle (0)."""
        deadline = time.time() + max(0.2, float(timeout_s))
        while time.time() < deadline:
            with self._notify_lock:
                status = self._last_interaction_task_status
            if status in (None, 0):
                return True
            time.sleep(0.1)
        return False

    def move(
        self,
        direction_deg: float,
        velocity: float = 1.0,
        *,
        walk: bool = False,
        speed: bool = False,
    ) -> None:
        """Compatibility wrapper for angle-based movement input."""
        deg = direction_deg % 360
        if velocity <= 0:
            self.stop_movement()
            return

        if deg <= 45 or deg > 315:
            self.send_movement(Movement.FORWARD)
        elif deg <= 135:
            self.send_movement(Movement.RIGHT)
        elif deg <= 225:
            self.send_movement(Movement.BACK)
        else:
            self.send_movement(Movement.LEFT)

    def stop_movement(self) -> None:
        """Stop movement."""
        self.send_offsets("STOP")

    def reset(self) -> None:
        """
        Compatibility reset API: stop movement + send interaction STOP.
        """
        self.stop_movement()
        self.send_interaction(int(Action.STOP_INTERACTION))

    def start_movement(self, direction: Union[int, Movement]) -> None:
        """Start movement in a given direction."""
        self.send_movement(direction)

    def send_movement(
        self,
        direction: Union[int, Movement],
        *,
        duration_s: Optional[float] = None,
    ) -> None:
        """
        Send directional movement command.

        When ``duration_s`` is provided (>0), the SDK blocks for that duration
        and automatically sends stop afterwards.
        """
        direction_define = {
            int(Movement.FORWARD): "FORWARD",
            int(Movement.BACK): "BACK",
            int(Movement.STEP): "STEP",
            int(Movement.RIGHT): "RIGHT",
            int(Movement.LEFT): "LEFT",
        }
        direction_name = direction_define.get(int(direction))
        if not direction_name:
            raise ValueError(f"Unsupported movement direction: {direction}")
        self.send_offsets(direction_name)
        if duration_s is not None:
            duration = float(duration_s)
            if duration <= 0:
                raise ValueError(f"duration_s must be > 0, got {duration_s!r}")
            try:
                time.sleep(duration)
            finally:
                self.stop_movement()

    def send_offsets(
        self,
        direction: str = "STOP",
    ) -> None:
        """Send full movement parameter packet."""
        gait = 1
        direction_to_state_map = {
            "FORWARD": 0,
            "BACK": 1,
            "STEP": 2,
            "RIGHT": 3,
            "LEFT": 4,
            "STOP": 5,
        }
        if direction not in direction_to_state_map:
            raise ValueError(f"Unsupported direction: {direction}")

        state = direction_to_state_map[direction]
        data: List[int] = [gait, state]
        data.extend([100 & 0xFF])  # height mm
        data.extend([0, 0])  # x offset
        data.extend([0, 0])  # pitch
        data.extend([0, 0])  # roll
        data.extend([500 >> 8, 500 & 0xFF])  # period ms
        data.extend([75 & 0xFF])  # step length mm
        data.extend([35 & 0xFF])  # step height mm
        data.extend(struct.pack("<f", 0.5))
        data.extend(struct.pack("<f", 0.5))
        data.extend(struct.pack("<f", 0.01))
        data.extend(struct.pack("<f", 8.0))
        data.extend(struct.pack("<f", 5.0))
        data.extend([0])  # flag
        data.extend(struct.pack("<f", 0.5))  # duty
        data.extend(struct.pack("<f", math.radians(0)))  # RF
        data.extend(struct.pack("<f", math.radians(180)))  # LF
        data.extend(struct.pack("<f", math.radians(180)))  # RH
        data.extend(struct.pack("<f", math.radians(0)))  # LH
        self._ble.send_data(MODE_SPORT, list(data))

    def send_interaction(self, action_id: int, param: Optional[int] = None) -> None:
        """Send interaction action with optional param."""
        action_value = int(action_id)
        data = [action_value & 0xFF]
        if param is not None:
            try:
                is_angle_action = Action(action_value) in ANGLE_BASED
            except ValueError:
                is_angle_action = False
            if is_angle_action:
                value = max(0, min(65535, int(param)))
                data.extend([value & 0xFF, (value >> 8) & 0xFF])
            else:
                data.append(max(0, min(255, int(param))))
        self._ble.send_data(MODE_INTERACTION, data)

    def send_ear(self, ear_action_id: Union[int, EarAction]) -> None:
        """Send ear action ID (MODE_EAR)."""
        self._ble.send_data(MODE_EAR, [int(ear_action_id) & 0xFF])

    def send_ear_percentage(self, percentage: int) -> None:
        """Send ear position percentage (command 14)."""
        p = max(0, min(100, int(percentage)))
        self._ble.send_data(MODE_EAR, [14, p])

    def toggle_special_detection(self) -> None:
        """Toggle special-state detection / autonomous interaction (command 15)."""
        self._ble.send_data(MODE_EAR, [_SPECIAL_DETECTION_TOGGLE])
        if self._special_detection_enabled is not None:
            self._special_detection_enabled = not self._special_detection_enabled

    def set_special_detection(
        self,
        enable: bool,
        *,
        assume_current: Optional[bool] = None,
    ) -> None:
        """
        Set special-state detection to an explicit ON/OFF target.

        On updated firmware this maps to explicit MODE_EAR commands:
        - 100: enable special detection + non-operated timer
        - 101: disable special detection + non-operated timer

        For backward compatibility, ``assume_current`` is accepted but ignored.
        """
        _ = assume_current
        target = bool(enable)
        cmd = _SPECIAL_DETECTION_ENABLE if target else _SPECIAL_DETECTION_DISABLE
        self._ble.send_data(MODE_EAR, [cmd])
        self._special_detection_enabled = target

    def enable_special_detection(self, *, assume_current: Optional[bool] = None) -> None:
        """Explicitly enable special-state detection."""
        self.set_special_detection(True, assume_current=assume_current)

    def disable_special_detection(self, *, assume_current: Optional[bool] = None) -> None:
        """Explicitly disable special-state detection."""
        self.set_special_detection(False, assume_current=assume_current)

    def set_tof_enable(self, enable: bool) -> None:
        """
        Enable or disable firmware TOF avoidance through remote-control JSON on ae03.

        This is different from ``request_tof_stream()``, which only controls the
        ae04 realtime TOF notification stream.
        """
        self._ble.send_control_json(
            {"mode": _APP_UNKNOWN_CONTROL_MODE, "tof_enable": 1 if enable else 0}
        )

    def send_expression(self, expression_id: Union[int, ExpressionAction]) -> None:
        """Send expression ID."""
        self._ble.send_data(MODE_EXPRESSION, [int(expression_id) & 0xFF])

    def send_audio(self, tone_id: Union[int, Tone]) -> None:
        """Send audio control ID (0=stop, >0=play)."""
        self._ble.send_data(MODE_AUDIO, [int(tone_id) & 0xFF])

    def set_volume(
        self,
        volume: int,
        *,
        verify_tone: Optional[Union[int, Tone]] = None,
        verify_delay_s: float = 0.2,
    ) -> None:
        """
        Set robot volume through the firmware config channel.

        Current firmware uses 5 levels: 0=mute, 4=max. When ``verify_tone`` is
        provided, the SDK plays that tone after the setting is sent.
        """
        level = max(0, min(4, int(volume)))
        self._ble.send_config_json({"cmd": CONFIG_SET_VOLUME, "volume": level})
        if verify_tone is not None:
            delay = max(0.0, float(verify_delay_s))
            if delay:
                time.sleep(delay)
            self.send_audio(verify_tone)

    # ------------------------------------------------------------------
    # Extended low-level APIs (microphone / speaker / servo / IMU)
    # ------------------------------------------------------------------

    def send_raw(self, mode: int, data: List[int]) -> None:
        """
        Send a raw protocol packet: [0xAA, 0x55, 0x00, mode, ...data].

        Useful for quickly integrating new firmware commands beyond high-level APIs.
        """
        self._ble.send_data(int(mode) & 0xFF, data)

    @staticmethod
    def _pose_item_to_tuple(item: Union[Mapping[str, Any], Sequence[Any]]) -> Tuple[str, float, float]:
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("str")
            if name is None:
                raise ValueError('pose item dict must include "name" (or "str")')
            now = float(item["now"])
            end = float(item["end"])
            return str(name), now, end
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            return str(item[0]), float(item[1]), float(item[2])
        raise ValueError(
            "each pose entry must be a dict with name/now/end or a (name, now, end) sequence"
        )

    @staticmethod
    def _delta_item_to_tuple(item: Union[Mapping[str, Any], Sequence[Any]]) -> Tuple[str, float]:
        if isinstance(item, Mapping):
            name = item.get("name") or item.get("str")
            if name is None:
                raise ValueError('item dict must include "name" (or "str")')
            dv = item.get("delta", item.get("diffVal", item.get("diff")))
            if dv is None:
                raise ValueError('foot/joint dict must include "delta", "diffVal", or "diff"')
            return str(name), float(dv)
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            return str(item[0]), float(item[1])
        raise ValueError("each entry must be a dict with name+delta or a (name, delta) sequence")

    def syn_pose_adjust(
        self,
        poses: List[Union[Mapping[str, Any], Sequence[Any]]],
        duration_ms: int,
    ) -> None:
        """
        Use BLE to call the firmware ``syn_pose_adjust``: within *duration_ms*,
        interpolate smoothly from *now* to *end* (same semantics as the firmware
        ``time`` parameter; milliseconds).

        Each entry in *poses* is ``{"name": "cog_z", "now": 0.0, "end": -5.0}`` or
        ``("cog_z", 0.0, -5.0)``.

        *name* supports ``cog_x``, ``cog_z`` (mm), ``roll``, ``pitch`` (degrees).

        On newer firmware, after this motion completes the robot requests
        return to ``BASIC_MODE``.
        """
        if not poses:
            raise ValueError("poses must not be empty")
        mask = 0
        payload = bytearray()
        indexed: List[Tuple[int, float, float]] = []
        used = 0
        for raw in poses:
            name, now_v, end_v = self._pose_item_to_tuple(raw)
            if name not in _POSE_PARAM_ORDER:
                raise ValueError(
                    f"unknown pose name {name!r}; expected one of {_POSE_PARAM_ORDER}"
                )
            idx = _POSE_PARAM_ORDER.index(name)
            bit = 1 << idx
            if used & bit:
                raise ValueError(f"duplicate pose parameter {name!r}")
            used |= bit
            mask |= bit
            indexed.append((idx, now_v, end_v))
        indexed.sort(key=lambda x: x[0])
        for _, now_v, end_v in indexed:
            payload.extend(struct.pack("<ff", now_v, end_v))
        t = max(0, min(65535, int(duration_ms)))
        data = [_RADJ_SUB_POSE, mask & 0xFF, t & 0xFF, (t >> 8) & 0xFF] + list(payload)
        self._ble.send_data(MODE_ROBOT_ADJUST, data)

    def syn_foot_adjust(
        self,
        feet: List[Union[Mapping[str, Any], Sequence[Any]]],
        duration_ms: int,
    ) -> None:
        """
        Call ``syn_foot_adjust``: move the feet along X/Z smoothly by *delta*
        over *duration_ms* (**total displacement** in mm; internally divided
        into 20 ms steps).

        *name* follows ``robot_adjust.h``: ``foot_0_x`` .. ``foot_3_z``, where
        0=right-front, 1=right-rear, 2=left-front, 3=left-rear.

        On newer firmware, after this motion completes the robot requests
        return to ``BASIC_MODE``.
        """
        if not feet:
            raise ValueError("feet must not be empty")
        mask = 0
        payload = bytearray()
        indexed: List[Tuple[int, float]] = []
        used = 0
        for raw in feet:
            name, dv = self._delta_item_to_tuple(raw)
            if name not in _FOOT_PARAM_ORDER:
                raise ValueError(
                    f"unknown foot name {name!r}; expected one of {_FOOT_PARAM_ORDER}"
                )
            idx = _FOOT_PARAM_ORDER.index(name)
            bit = 1 << idx
            if used & bit:
                raise ValueError(f"duplicate foot parameter {name!r}")
            used |= bit
            mask |= bit
            indexed.append((idx, dv))
        indexed.sort(key=lambda x: x[0])
        for _, dv in indexed:
            payload.extend(struct.pack("<f", dv))
        t = max(0, min(65535, int(duration_ms)))
        data = [_RADJ_SUB_FOOT, mask & 0xFF, t & 0xFF, (t >> 8) & 0xFF] + list(payload)
        self._ble.send_data(MODE_ROBOT_ADJUST, data)

    def syn_joint_adjust(
        self,
        joints: List[Union[Mapping[str, Any], Sequence[Any]]],
        duration_ms: int,
    ) -> None:
        """
        Call ``syn_joint_adjust``: rotate selected joints smoothly by *delta*
        relative to the **current angle** over *duration_ms*
        (**total angle** in degrees).

        *name* uses ``joint_0_1`` .. ``joint_3_2`` where 1=thigh and 2=shin.

        On newer firmware, after this motion completes the robot requests
        return to ``BASIC_MODE``.
        """
        if not joints:
            raise ValueError("joints must not be empty")
        mask = 0
        payload = bytearray()
        indexed: List[Tuple[int, float]] = []
        used = 0
        for raw in joints:
            name, dv = self._delta_item_to_tuple(raw)
            if name not in _JOINT_PARAM_ORDER:
                raise ValueError(
                    f"unknown joint name {name!r}; expected one of {_JOINT_PARAM_ORDER}"
                )
            idx = _JOINT_PARAM_ORDER.index(name)
            bit = 1 << idx
            if used & bit:
                raise ValueError(f"duplicate joint parameter {name!r}")
            used |= bit
            mask |= bit
            indexed.append((idx, dv))
        indexed.sort(key=lambda x: x[0])
        for _, dv in indexed:
            payload.extend(struct.pack("<f", dv))
        t = max(0, min(65535, int(duration_ms)))
        data = [_RADJ_SUB_JOINT, mask & 0xFF, t & 0xFF, (t >> 8) & 0xFF] + list(payload)
        self._ble.send_data(MODE_ROBOT_ADJUST, data)

    def request_basic_mode(self) -> None:
        """
        Request the firmware (via ``mode_manager``) to switch back to
        ``BASIC_MODE`` (not part of interpolation).

        On newer firmware, after each ``syn_pose_adjust`` / ``syn_foot_adjust`` /
        ``syn_joint_adjust`` completes, it also sends a return-to-basic request.
        If the robot is still stuck in interaction mode, call this again at the end
        of your script.
        """
        self._ble.send_data(
            MODE_ROBOT_ADJUST,
            [_RADJ_SUB_RETURN_BASIC, 0, 0, 0],
        )

    def default_pose_output(
        self,
        roll: float,
        pitch: float,
        x: float,
        z: float,
    ) -> None:
        """
        Move to a caller-specified default pose for choreography preparation.

        Firmware expects payload:
        ``[sub=0x05, roll(f32 LE), pitch(f32 LE), x(f32 LE), z(f32 LE)]``.
        """
        payload = struct.pack("<ffff", float(roll), float(pitch), float(x), float(z))
        self._ble.send_data(
            MODE_ROBOT_ADJUST,
            [_RADJ_SUB_DEFAULT_POSE_FOR_SDK] + list(payload),
        )

    def request_imu_stream(
        self,
        enable: bool = True,
        *,
        hz: int = 20,
        mode: int = MODE_SENSOR,
        cmd_enable: int = 0x01,
        cmd_disable: int = 0x00,
    ) -> None:
        """
        Request firmware to enable/disable realtime IMU in the **ae04** sensor JSON
        (``"imu"`` field; can be enabled together with ``request_tof_stream``.
        When both streams are on, firmware may include a ``"tof"`` field in the
        same JSON packet).

        Default command format:
        - Enable: [cmd_enable, hz]
        - Disable: [cmd_disable]
        """
        if enable:
            self._ble.send_data(int(mode) & 0xFF, [cmd_enable & 0xFF, max(1, min(200, int(hz)))])
        else:
            self._ble.send_data(int(mode) & 0xFF, [cmd_disable & 0xFF])

    def get_latest_imu(self) -> Optional[Dict[str, object]]:
        """
        Get the latest parsed IMU payload (with angle normalization applied).

        Expected notify JSON example:
        {
          "imu": {
            "yaw": -400710,    # raw firmware value (milli-degrees)
            "yaw_deg": -400.710,  # SDK-normalized angle (degrees)
            "pitch_deg": 0.630,
            "roll_deg": -0.206
          }
        }
        """
        with self._notify_lock:
            if self._last_imu_data is None:
                return None
            return dict(self._last_imu_data)

    def add_imu_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        """Register an IMU callback (triggered on each IMU notify)."""
        if callback not in self._imu_callbacks:
            self._imu_callbacks.append(callback)

    def remove_imu_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        """Remove a previously registered IMU callback."""
        self._imu_callbacks = [cb for cb in self._imu_callbacks if cb != callback]

    def request_tof_stream(
        self,
        enable: bool = True,
        *,
        hz: int = 20,
        mode: int = MODE_SENSOR,
        cmd_enable: int = 0x02,
        cmd_disable: int = 0x03,
    ) -> None:
        """
        Request firmware to enable/disable realtime TOF in the **ae04** sensor JSON
        (``"tof"`` field; may appear together with ``"imu"`` when both streams are on).

        Default command format:
        - Enable: [cmd_enable, hz]
        - Disable: [cmd_disable]
        """
        if enable:
            self._ble.send_data(int(mode) & 0xFF, [cmd_enable & 0xFF, max(1, min(200, int(hz)))])
        else:
            self._ble.send_data(int(mode) & 0xFF, [cmd_disable & 0xFF])

    def get_latest_tof(self) -> Optional[Dict[str, object]]:
        """Get the latest parsed TOF payload."""
        with self._notify_lock:
            if self._last_tof_data is None:
                return None
            return dict(self._last_tof_data)

    def add_tof_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        """Register a TOF callback (triggered on each TOF notify/indicate)."""
        if callback not in self._tof_callbacks:
            self._tof_callbacks.append(callback)

    def remove_tof_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        """Remove a previously registered TOF callback."""
        self._tof_callbacks = [cb for cb in self._tof_callbacks if cb != callback]

    def microphone_start(self, *, sample_rate: int = 16000, mode: int = MODE_STREAM, cmd: int = 0x10) -> None:
        """
        Start robot microphone capture (payload format is firmware-defined).

        Default command format: [cmd, sample_rate_hi, sample_rate_lo]
        """
        sr = max(8000, min(48000, int(sample_rate)))
        self._ble.send_data(int(mode) & 0xFF, [cmd & 0xFF, (sr >> 8) & 0xFF, sr & 0xFF])

    def microphone_stop(self, *, mode: int = MODE_STREAM, cmd: int = 0x11) -> None:
        """Stop robot microphone capture."""
        self._ble.send_data(int(mode) & 0xFF, [cmd & 0xFF])

    def speaker_start(self, *, sample_rate: int = 16000, mode: int = MODE_STREAM, cmd: int = 0x20) -> None:
        """
        Start speaker playback session.

        Default command format: [cmd, sample_rate_hi, sample_rate_lo]
        """
        sr = max(8000, min(48000, int(sample_rate)))
        self._ble.send_data(int(mode) & 0xFF, [cmd & 0xFF, (sr >> 8) & 0xFF, sr & 0xFF])

    def speaker_write_pcm(
        self,
        pcm_chunk: Union[bytes, bytearray],
        *,
        mode: int = MODE_STREAM,
        cmd: int = 0x21,
        max_payload_bytes: int = 120,
    ) -> None:
        """
        Push one PCM frame to the robot speaker.

        BLE payload size is limited; default max is 120 bytes per packet.
        Larger payloads are automatically chunked.
        """
        if not pcm_chunk:
            return
        chunk = bytes(pcm_chunk)
        step = max(1, int(max_payload_bytes))
        for i in range(0, len(chunk), step):
            part = chunk[i : i + step]
            self._ble.send_data(int(mode) & 0xFF, [cmd & 0xFF] + list(part))

    def speaker_stop(self, *, mode: int = MODE_STREAM, cmd: int = 0x22) -> None:
        """Stop speaker playback session."""
        self._ble.send_data(int(mode) & 0xFF, [cmd & 0xFF])

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_action_list(self) -> dict:
        """
        Read the action list advertised by the device (ae10 characteristic).

        Returns the parsed JSON dict, which contains ``interactive_actions``
        and ``programmable_actions`` arrays with firmware action IDs.
        """
        return self._ble.read_actions()

    def _on_notify(self, data: bytes) -> None:
        """
        Internal notify hook:
        - Parse interaction_task_status from firmware JSON notify
        - Forward raw bytes to user callback if provided
        """
        try:
            text = data.decode("utf-8", errors="ignore").strip()
            if text.startswith("{") and text.endswith("}"):
                obj = json.loads(text)
                if isinstance(obj, dict):
                    ps, pi, pt = self._parse_notify_dict(obj)
                    self._dispatch_parsed_notify(ps, pi, pt)
        except Exception:
            pass

        if self._user_on_notify:
            self._user_on_notify(data)

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "AiDog":
        return self

    def __exit__(self, *_) -> None:
        self.shutdown()
