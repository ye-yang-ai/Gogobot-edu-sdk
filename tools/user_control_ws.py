"""Tkinter WebSocket upper-computer control panel for Changba AI-Dog.

This script intentionally stays outside the SDK boundary: it imports the public
``aidog_sdk`` APIs and reuses the same control layout as ``user_control_ble.py``.
"""

from __future__ import annotations

import math
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Deque, Dict, Iterable, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aidog_sdk import (  # noqa: E402
    AiDog,
    Action,
    DevPcWebSocketHost,
    EarAction,
    ExpressionAction,
    Movement,
    TONE_LIST,
    Tone,
)


DEFAULT_BIND = "0.0.0.0"
DEFAULT_PORT = 8766
DEFAULT_CONNECT_TIMEOUT_S = 60.0
EDU_ENTER_INITIAL_DELAY_S = 0.6
EDU_ENTER_RETRY_DELAY_S = 0.8
EDU_ENTER_RETRY_COUNT = 3
PLOT_HISTORY_SECONDS = 12.0
PLOT_REFRESH_MS = 100
UI_POLL_MS = 80
JOYSTICK_DEADZONE = 18
EAR_SEND_INTERVAL_MS = 60
EAR_SEND_MIN_DELTA = 2
EAR_REPEAT_AFTER_RELEASE_MS = 1000
HIDDEN_INTERACTION_ACTION_IDS = {6, 47, 48, 49, 50, 51}
HIDDEN_EAR_ACTION_IDS = {15}
VOLUME_LEVELS = (0, 1, 2, 3, 4)


class RobotController:
    """Small thread-aware adapter around the public AiDog WebSocket API."""

    def __init__(self, log_queue: "queue.Queue[str]") -> None:
        self.log_queue = log_queue
        self.dog = AiDog(imu_only_notify=True, auto_edu=False)
        self.host: Optional[DevPcWebSocketHost] = None
        self._lock = threading.RLock()
        self._closed = False

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def connect(self, bind: str, port: int, timeout_s: float) -> str:
        with self._lock:
            self.disconnect()
            self.host = DevPcWebSocketHost(host=bind, port=port, dog=self.dog)
            self.dog.attach_ws_control(self.host)
            self.host.start()
        if not self.host.wait_robot_connected(timeout_s=timeout_s):
            with self._lock:
                self.host.stop()
                self.host = None
            raise TimeoutError(f"等待机器狗连接 ws://{bind}:{port} 超时")
        threading.Thread(target=self._enter_edu_mode_async, daemon=True, name="user-control-edu-enter").start()
        return f"ws://{bind}:{port}"

    def _enter_edu_mode_async(self) -> None:
        time.sleep(EDU_ENTER_INITIAL_DELAY_S)
        for attempt in range(1, EDU_ENTER_RETRY_COUNT + 1):
            if not self.is_connected():
                self.log("EDU 模式进入取消: WebSocket 已断开")
                return
            try:
                self.dog.enter_edu_mode(transport="ws")
                self.log("EDU 模式已进入")
                return
            except Exception as exc:
                self.log(f"EDU 模式进入失败({attempt}/{EDU_ENTER_RETRY_COUNT}): {exc}")
                if attempt < EDU_ENTER_RETRY_COUNT:
                    time.sleep(EDU_ENTER_RETRY_DELAY_S)
        self.log("EDU 模式进入失败: 已达到最大重试次数")

    def disconnect(self) -> None:
        with self._lock:
            if self.host is not None:
                self._disable_sensor_streams_unlocked()
                self.dog.exit_edu_mode()
                self.host.stop()
                self.host = None

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        with self._lock:
            try:
                if self.host is not None:
                    self._disable_sensor_streams_unlocked()
                    self.dog.exit_edu_mode()
                    self.host.stop()
                    self.host = None
            except Exception:
                pass
            self.dog.shutdown()

    def is_connected(self) -> bool:
        with self._lock:
            return bool(self.host is not None and self.host.is_robot_connected)

    def start_movement(self, movement: Movement) -> None:
        with self._lock:
            self.dog.start_movement(movement, transport="ws")

    def stop_movement(self) -> None:
        with self._lock:
            self.dog.stop_movement(transport="ws")

    def send_interaction(self, action: Action) -> None:
        with self._lock:
            self.dog.send_interaction(int(action), transport="ws")

    def send_ear(self, action: EarAction) -> None:
        with self._lock:
            self.dog.send_ear(action, transport="ws")

    def send_ear_percentage(self, percentage: int) -> None:
        with self._lock:
            self.dog.send_ear_percentage(percentage, transport="ws")

    def set_special_detection(self, enabled: bool) -> None:
        with self._lock:
            self.dog.set_special_detection(enabled, transport="ws")

    def send_expression(self, expression: ExpressionAction) -> None:
        with self._lock:
            self.dog.send_expression(expression, transport="ws")

    def send_audio(self, tone: int) -> None:
        with self._lock:
            self.dog.send_audio(tone, transport="ws")

    def set_volume(self, volume: int) -> None:
        with self._lock:
            self.dog.set_volume(volume, transport="ws")

    def request_imu_stream(self, enabled: bool, hz: int) -> None:
        with self._lock:
            self.dog.request_imu_stream(enabled, hz=hz, transport="ws")

    def request_tof_stream(self, enabled: bool, hz: int) -> None:
        with self._lock:
            self.dog.request_tof_stream(enabled, hz=hz, transport="ws")

    def add_imu_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        self.dog.add_imu_listener(callback)

    def remove_imu_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        self.dog.remove_imu_listener(callback)

    def add_tof_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        self.dog.add_tof_listener(callback)

    def remove_tof_listener(self, callback: Callable[[Dict[str, object]], None]) -> None:
        self.dog.remove_tof_listener(callback)

    def _disable_sensor_streams_unlocked(self) -> None:
        try:
            self.dog.request_imu_stream(False, transport="ws")
        except Exception:
            pass
        try:
            self.dog.request_tof_stream(False, transport="ws")
        except Exception:
            pass


class SensorSeries:
    def __init__(self, maxlen: int = 1200) -> None:
        self.points: Deque[Tuple[float, float]] = deque(maxlen=maxlen)
        self.lock = threading.Lock()

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        ts = time.monotonic() if timestamp is None else timestamp
        with self.lock:
            self.points.append((ts, float(value)))

    def snapshot(self) -> List[Tuple[float, float]]:
        cutoff = time.monotonic() - PLOT_HISTORY_SECONDS
        with self.lock:
            while self.points and self.points[0][0] < cutoff:
                self.points.popleft()
            return list(self.points)

    def clear(self) -> None:
        with self.lock:
            self.points.clear()


class LinePlot(ttk.Frame):
    """A lightweight single-series plot built on Tk Canvas."""

    def __init__(self, parent: tk.Widget, title: str, unit: str) -> None:
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.series = SensorSeries()
        self.value_var = tk.StringVar(value="--")

        header = ttk.Frame(self)
        header.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(header, text=title, font=("Microsoft YaHei UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self.value_var, width=14, anchor=tk.E).pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self, height=130, bg="#ffffff", highlightthickness=1, highlightbackground="#c9ced6")
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        self.series.add(value, timestamp)

    def clear(self) -> None:
        self.series.clear()
        self.value_var.set("--")
        self.canvas.delete("all")

    def redraw(self) -> None:
        points = self.series.snapshot()
        self.canvas.delete("all")

        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        pad_l, pad_r, pad_t, pad_b = 38, 8, 10, 24
        plot_w = max(1, width - pad_l - pad_r)
        plot_h = max(1, height - pad_t - pad_b)

        self._draw_grid(width, height, pad_l, pad_r, pad_t, pad_b)
        if not points:
            self.canvas.create_text(width / 2, height / 2, text="No data", fill="#7b8190")
            return

        latest = points[-1][1]
        self.value_var.set(f"{latest:.2f} {self.unit}".strip())

        now = time.monotonic()
        start = now - PLOT_HISTORY_SECONDS
        values = [v for _, v in points]
        min_v = min(values)
        max_v = max(values)
        if math.isclose(min_v, max_v, abs_tol=1e-9):
            margin = 1.0 if abs(max_v) < 1.0 else abs(max_v) * 0.1
            min_v -= margin
            max_v += margin
        else:
            margin = (max_v - min_v) * 0.12
            min_v -= margin
            max_v += margin

        coords: List[float] = []
        for ts, value in points:
            x = pad_l + ((ts - start) / PLOT_HISTORY_SECONDS) * plot_w
            y = pad_t + (max_v - value) / (max_v - min_v) * plot_h
            coords.extend([x, y])

        if len(coords) >= 4:
            self.canvas.create_line(*coords, fill="#1f6feb", width=2, smooth=False)
        else:
            self.canvas.create_oval(coords[0] - 2, coords[1] - 2, coords[0] + 2, coords[1] + 2, fill="#1f6feb", outline="")

        self.canvas.create_text(3, pad_t, anchor=tk.NW, text=f"{max_v:.1f}", fill="#69707d", font=("Arial", 8))
        self.canvas.create_text(3, height - pad_b - 10, anchor=tk.NW, text=f"{min_v:.1f}", fill="#69707d", font=("Arial", 8))

    def _draw_grid(
        self,
        width: int,
        height: int,
        pad_l: int,
        pad_r: int,
        pad_t: int,
        pad_b: int,
    ) -> None:
        left = pad_l
        right = width - pad_r
        top = pad_t
        bottom = height - pad_b
        for i in range(5):
            y = top + i * (bottom - top) / 4
            self.canvas.create_line(left, y, right, y, fill="#eef1f5")
        for i in range(5):
            x = left + i * (right - left) / 4
            self.canvas.create_line(x, top, x, bottom, fill="#f3f5f8")
        self.canvas.create_line(left, bottom, right, bottom, fill="#c9ced6")
        self.canvas.create_line(left, top, left, bottom, fill="#c9ced6")
        self.canvas.create_text(left, height - 5, anchor=tk.SW, text=f"-{int(PLOT_HISTORY_SECONDS)}s", fill="#69707d", font=("Arial", 8))
        self.canvas.create_text(right, height - 5, anchor=tk.SE, text="now", fill="#69707d", font=("Arial", 8))


class ScrollableGrid(ttk.Frame):
    def __init__(self, parent: tk.Widget, height: int = 420) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor=tk.NW)

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)


class UserControlApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI-Dog User Control")
        self.root.geometry("1180x780")
        self.root.minsize(980, 680)

        self.log_queue: "queue.Queue[str]" = queue.Queue()
        self.ui_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.worker_queue: "queue.Queue[Tuple[str, Callable[[], object], Optional[Callable[[object], None]]]]" = queue.Queue()
        self.controller = RobotController(self.log_queue)
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="user-control-worker")
        self.worker_thread.start()

        self.connected_url: Optional[str] = None
        self.active_movement: Optional[Movement] = None
        self._ear_send_after_id: Optional[str] = None
        self._ear_last_send_ms = 0
        self._ear_pending_percentage: Optional[int] = None
        self._ear_last_sent_percentage: Optional[int] = None
        self._ear_send_seq = 0
        self._ear_repeat_until_ms = 0
        self.imu_enabled = tk.BooleanVar(value=False)
        self.tof_enabled = tk.BooleanVar(value=False)
        self.special_detection_enabled = tk.BooleanVar(value=False)

        self._build_ui()
        self.controller.add_imu_listener(self._on_imu)
        self.controller.add_tof_listener(self._on_tof)

        self.root.after(UI_POLL_MS, self._poll_queues)
        self.root.after(PLOT_REFRESH_MS, self._redraw_plots)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        self._build_connection_bar()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.motion_page = ttk.Frame(self.notebook, padding=10)
        self.ear_page = ttk.Frame(self.notebook, padding=10)
        self.expression_page = ttk.Frame(self.notebook, padding=10)
        self.audio_page = ttk.Frame(self.notebook, padding=10)
        self.volume_page = ttk.Frame(self.notebook, padding=10)
        self.sensor_page = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.motion_page, text="运动控制")
        self.notebook.add(self.ear_page, text="耳朵控制")
        self.notebook.add(self.expression_page, text="表情测试")
        self.notebook.add(self.audio_page, text="音效测试")
        self.notebook.add(self.volume_page, text="音量调节")
        self.notebook.add(self.sensor_page, text="传感器数据")

        self._build_motion_page()
        self._build_ear_page()
        self._build_expression_page()
        self._build_audio_page()
        self._build_volume_page()
        self._build_sensor_page()

    def _build_connection_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 6))
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(7, weight=1)

        ttk.Label(bar, text="监听地址").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
        self.bind_var = tk.StringVar(value=DEFAULT_BIND)
        ttk.Entry(bar, textvariable=self.bind_var, width=16).grid(row=0, column=1, sticky=tk.W, padx=(0, 8))

        ttk.Label(bar, text="端口").grid(row=0, column=2, sticky=tk.W, padx=(0, 6))
        self.port_var = tk.IntVar(value=DEFAULT_PORT)
        ttk.Spinbox(bar, from_=1, to=65535, textvariable=self.port_var, width=7).grid(row=0, column=3, sticky=tk.W, padx=(0, 8))

        ttk.Label(bar, text="等待秒数").grid(row=0, column=4, sticky=tk.W, padx=(0, 6))
        self.timeout_var = tk.DoubleVar(value=DEFAULT_CONNECT_TIMEOUT_S)
        ttk.Spinbox(bar, from_=1, to=600, textvariable=self.timeout_var, width=7).grid(row=0, column=5, sticky=tk.W, padx=(0, 8))

        self.connect_btn = ttk.Button(bar, text="连接", command=self.toggle_connection, width=12)
        self.connect_btn.grid(row=0, column=6, sticky=tk.W, padx=(0, 8))

        self.status_var = tk.StringVar(value="状态: 未连接")
        ttk.Label(bar, textvariable=self.status_var, anchor=tk.W).grid(row=0, column=7, sticky="ew")

    def _build_motion_page(self) -> None:
        self.motion_page.columnconfigure(0, weight=0)
        self.motion_page.columnconfigure(1, weight=1)
        self.motion_page.rowconfigure(0, weight=1)

        left = ttk.Frame(self.motion_page)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 16))

        ttk.Label(left, text="摇杆控制", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor=tk.W)
        self.joystick_canvas = tk.Canvas(left, width=260, height=260, bg="#ffffff", highlightthickness=1, highlightbackground="#c9ced6")
        self.joystick_canvas.pack(pady=(8, 10))
        self.joystick_canvas.bind("<ButtonPress-1>", self._on_joystick_drag)
        self.joystick_canvas.bind("<B1-Motion>", self._on_joystick_drag)
        self.joystick_canvas.bind("<ButtonRelease-1>", self._on_joystick_release)
        self._draw_joystick(130, 130)

        step_btn = ttk.Button(left, text="原地踏步", command=lambda: self._set_movement(Movement.STEP))
        step_btn.pack(fill=tk.X, pady=(0, 6))
        stop_btn = ttk.Button(left, text="停止运动", command=self._stop_movement)
        stop_btn.pack(fill=tk.X)

        special = ttk.LabelFrame(left, text="特殊状态检测")
        special.pack(fill=tk.X, pady=(16, 0))
        ttk.Checkbutton(
            special,
            text="启用特殊状态检测 / 自主交互",
            variable=self.special_detection_enabled,
            command=self._on_special_detection_toggle,
        ).pack(anchor=tk.W, padx=8, pady=8)

        right = ttk.Frame(self.motion_page)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="交互动作", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W)

        grid = ScrollableGrid(right)
        grid.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self._populate_action_buttons(
            grid.inner,
            _unique_enum_members(Action, hidden_ids=HIDDEN_INTERACTION_ACTION_IDS),
            self._send_interaction,
            columns=4,
        )

    def _build_ear_page(self) -> None:
        self.ear_page.columnconfigure(0, weight=1)
        ttk.Label(self.ear_page, text="耳朵位置", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W)

        slider_row = ttk.Frame(self.ear_page)
        slider_row.grid(row=1, column=0, sticky="ew", pady=(8, 14))
        slider_row.columnconfigure(1, weight=1)
        self.ear_percent_var = tk.IntVar(value=0)
        self.ear_percent_label = tk.StringVar(value="0%")
        ttk.Label(slider_row, text="位置").grid(row=0, column=0, padx=(0, 8))
        ear_scale = ttk.Scale(slider_row, from_=0, to=100, orient=tk.HORIZONTAL, command=self._on_ear_scale)
        ear_scale.grid(row=0, column=1, sticky="ew")
        ear_scale.bind("<ButtonRelease-1>", self._on_ear_scale_release)
        ttk.Label(slider_row, textvariable=self.ear_percent_label, width=5, anchor=tk.E).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(self.ear_page, text="耳朵动作", font=("Microsoft YaHei UI", 11, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(0, 8))
        grid = ScrollableGrid(self.ear_page, height=500)
        grid.grid(row=3, column=0, sticky="nsew")
        self.ear_page.rowconfigure(3, weight=1)
        self._populate_action_buttons(
            grid.inner,
            _unique_enum_members(EarAction, hidden_ids=HIDDEN_EAR_ACTION_IDS),
            self._send_ear,
            columns=4,
        )

    def _build_expression_page(self) -> None:
        self.expression_page.columnconfigure(0, weight=1)
        self.expression_page.rowconfigure(1, weight=1)
        ttk.Label(self.expression_page, text="表情测试", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W)
        grid = ScrollableGrid(self.expression_page, height=520)
        grid.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self._populate_action_buttons(grid.inner, _unique_enum_members(ExpressionAction), self._send_expression, columns=5)

    def _build_audio_page(self) -> None:
        self.audio_page.columnconfigure(0, weight=1)
        self.audio_page.rowconfigure(1, weight=1)
        ttk.Label(self.audio_page, text="音效测试", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W)
        audio = ttk.Frame(self.audio_page)
        audio.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        for idx, (tone_id, name) in enumerate([(0, "STOP")] + TONE_LIST):
            btn = ttk.Button(audio, text=f"{tone_id}. {name}", command=lambda value=tone_id: self._send_audio(value))
            btn.grid(row=idx // 5, column=idx % 5, padx=4, pady=4, sticky="ew")
        for col in range(5):
            audio.columnconfigure(col, weight=1)

    def _build_volume_page(self) -> None:
        self.volume_page.columnconfigure(0, weight=1)
        ttk.Label(self.volume_page, text="音量调节", font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, sticky=tk.W)

        panel = ttk.Frame(self.volume_page)
        panel.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        for idx, level in enumerate(VOLUME_LEVELS):
            btn = ttk.Button(panel, text=f"{level} 档", command=lambda value=level: self._set_volume(value))
            btn.grid(row=0, column=idx, sticky="ew", padx=6, pady=4, ipady=12)
            panel.columnconfigure(idx, weight=1)

    def _build_sensor_page(self) -> None:
        self.sensor_page.columnconfigure(0, weight=1)
        self.sensor_page.rowconfigure(1, weight=1)

        controls = ttk.Frame(self.sensor_page)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        self.sensor_hz_var = tk.IntVar(value=20)
        ttk.Checkbutton(controls, text="IMU 数据流", variable=self.imu_enabled, command=self._toggle_imu_stream).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(controls, text="TOF 数据流", variable=self.tof_enabled, command=self._toggle_tof_stream).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(controls, text="采样率 Hz").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Spinbox(controls, from_=1, to=100, textvariable=self.sensor_hz_var, width=6).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(controls, text="应用采样率", command=self._apply_sensor_hz).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(controls, text="清空曲线", command=self._clear_plots).pack(side=tk.LEFT)

        plots = ttk.Frame(self.sensor_page)
        plots.grid(row=1, column=0, sticky="nsew")
        plots.columnconfigure(0, weight=1)
        plots.columnconfigure(1, weight=1)
        for row in range(3):
            plots.rowconfigure(row, weight=1)

        self.imu_yaw_plot = LinePlot(plots, "IMU yaw", "deg")
        self.imu_pitch_plot = LinePlot(plots, "IMU pitch", "deg")
        self.imu_roll_plot = LinePlot(plots, "IMU roll", "deg")
        self.tof_front_plot = LinePlot(plots, "TOF front", "mm")
        self.tof_oblique_plot = LinePlot(plots, "TOF oblique", "mm")

        self.imu_yaw_plot.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.imu_pitch_plot.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=6)
        self.imu_roll_plot.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=(6, 0))
        self.tof_front_plot.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 6))
        self.tof_oblique_plot.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=6)

        log_frame = ttk.LabelFrame(plots, text="日志")
        log_frame.grid(row=2, column=1, sticky="nsew", padx=(6, 0), pady=(6, 0))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

    def _populate_action_buttons(
        self,
        parent: tk.Widget,
        actions: Iterable[Tuple[str, int, object]],
        command: Callable[[object], None],
        *,
        columns: int,
    ) -> None:
        for idx, (name, _value, enum_value) in enumerate(actions):
            btn = ttk.Button(parent, text=name, command=lambda item=enum_value: command(item))
            btn.grid(row=idx // columns, column=idx % columns, sticky="ew", padx=4, pady=4)
        for col in range(columns):
            parent.columnconfigure(col, weight=1)

    def _worker_loop(self) -> None:
        while True:
            label, func, on_success = self.worker_queue.get()
            if label == "__quit__":
                return
            try:
                result = func()
                self.ui_queue.put(("task_ok", (label, result, on_success)))
            except Exception as exc:
                self.ui_queue.put(("task_error", (label, exc)))

    def _submit(self, label: str, func: Callable[[], object], on_success: Optional[Callable[[object], None]] = None) -> None:
        self.worker_queue.put((label, func, on_success))

    def toggle_connection(self) -> None:
        if self.connected_url:
            self.status_var.set("状态: 正在断开...")
            self.connect_btn.configure(state=tk.DISABLED)
            self._submit("断开 WebSocket", self.controller.disconnect, self._on_disconnect_success)
            return

        bind = self.bind_var.get().strip() or DEFAULT_BIND
        try:
            port = max(1, min(65535, int(self.port_var.get())))
        except Exception:
            port = DEFAULT_PORT
            self.port_var.set(port)
        try:
            timeout_s = max(1.0, float(self.timeout_var.get()))
        except Exception:
            timeout_s = DEFAULT_CONNECT_TIMEOUT_S
            self.timeout_var.set(timeout_s)

        self.status_var.set(f"状态: 监听 ws://{bind}:{port}，等待机器狗连接...")
        self.connect_btn.configure(state=tk.DISABLED)
        self._submit(
            "等待 WebSocket 连接",
            lambda: self.controller.connect(bind, port, timeout_s),
            self._on_connect_success,
        )

    def _on_connect_success(self, result: object) -> None:
        self.connected_url = str(result)
        self.status_var.set(f"状态: 机器狗已连接 {self.connected_url}")
        self.connect_btn.configure(text="断开", state=tk.NORMAL)

    def _on_disconnect_success(self, _result: object) -> None:
        self.connected_url = None
        self.active_movement = None
        self.imu_enabled.set(False)
        self.tof_enabled.set(False)
        self.status_var.set("状态: 已断开")
        self.connect_btn.configure(text="等待连接", state=tk.NORMAL)

    def _require_connection(self) -> bool:
        if not self.connected_url or not self.controller.is_connected():
            self._append_log("当前未连接机器狗 WebSocket。")
            return False
        return True

    def _send_command(self, label: str, func: Callable[[], object]) -> None:
        if not self._require_connection():
            return
        self._submit(label, func)

    def _set_movement(self, movement: Movement) -> None:
        if not self._require_connection():
            return
        if self.active_movement == movement:
            return
        self.active_movement = movement
        self._submit(f"运动: {movement.name}", lambda: self.controller.start_movement(movement))

    def _stop_movement(self) -> None:
        if self.active_movement is None:
            return
        self.active_movement = None
        self._draw_joystick(130, 130)
        self._send_command("停止运动", self.controller.stop_movement)

    def _draw_joystick(self, knob_x: float, knob_y: float) -> None:
        canvas = self.joystick_canvas
        canvas.delete("all")
        canvas.create_oval(30, 30, 230, 230, outline="#9aa4b2", width=2, fill="#f8fafc")
        canvas.create_line(130, 42, 130, 218, fill="#d8dde6")
        canvas.create_line(42, 130, 218, 130, fill="#d8dde6")
        canvas.create_text(130, 18, text="前进", fill="#4b5563")
        canvas.create_text(130, 244, text="后退", fill="#4b5563")
        canvas.create_text(16, 130, text="左转", fill="#4b5563", angle=90)
        canvas.create_text(244, 130, text="右转", fill="#4b5563", angle=270)
        canvas.create_oval(knob_x - 24, knob_y - 24, knob_x + 24, knob_y + 24, fill="#1f6feb", outline="#164caa", width=2)

    def _on_joystick_drag(self, event: tk.Event) -> None:
        dx = float(event.x - 130)
        dy = float(event.y - 130)
        dist = math.hypot(dx, dy)
        max_r = 88.0
        if dist > max_r:
            scale = max_r / dist
            dx *= scale
            dy *= scale
            dist = max_r
        self._draw_joystick(130 + dx, 130 + dy)
        if dist < JOYSTICK_DEADZONE:
            self._stop_movement()
            return
        if abs(dx) > abs(dy):
            self._set_movement(Movement.RIGHT if dx > 0 else Movement.LEFT)
        else:
            self._set_movement(Movement.BACK if dy > 0 else Movement.FORWARD)

    def _on_joystick_release(self, _event: tk.Event) -> None:
        self._stop_movement()

    def _send_interaction(self, action: object) -> None:
        assert isinstance(action, Action)
        self._send_command(f"交互动作: {action.name}", lambda: self.controller.send_interaction(action))

    def _send_ear(self, action: object) -> None:
        assert isinstance(action, EarAction)
        self._ear_repeat_until_ms = 0
        self._ear_pending_percentage = None
        if self._ear_send_after_id is not None:
            self.root.after_cancel(self._ear_send_after_id)
            self._ear_send_after_id = None
        self._send_command(f"耳朵动作: {action.name}", lambda: self.controller.send_ear(action))

    def _on_ear_scale(self, value: str) -> None:
        percentage = int(round(float(value)))
        self.ear_percent_var.set(percentage)
        self.ear_percent_label.set(f"{percentage}%")
        self._queue_ear_percentage(percentage, force=True)

    def _on_ear_scale_release(self, _event: object) -> None:
        percentage = max(0, min(100, int(self.ear_percent_var.get())))
        self._ear_repeat_until_ms = int(time.monotonic() * 1000) + EAR_REPEAT_AFTER_RELEASE_MS
        self._queue_ear_percentage(percentage, force=True)

    def _queue_ear_percentage(self, percentage: int, *, force: bool = False) -> None:
        self._ear_pending_percentage = max(0, min(100, int(percentage)))
        now_ms = int(time.monotonic() * 1000)
        elapsed_ms = now_ms - self._ear_last_send_ms
        if elapsed_ms >= EAR_SEND_INTERVAL_MS:
            self._send_current_ear_percentage(force=force)
            return
        if self._ear_send_after_id is None:
            self._ear_send_after_id = self.root.after(
                EAR_SEND_INTERVAL_MS - elapsed_ms,
                lambda: self._send_current_ear_percentage(force=force),
            )

    def _send_current_ear_percentage(self, *, force: bool = False) -> None:
        self._ear_send_after_id = None
        if self._ear_pending_percentage is None:
            return
        percentage = self._ear_pending_percentage
        self._ear_pending_percentage = None
        if self._ear_last_sent_percentage is not None:
            delta = abs(percentage - self._ear_last_sent_percentage)
            if delta < EAR_SEND_MIN_DELTA and not force:
                return
        self._ear_last_send_ms = int(time.monotonic() * 1000)
        self._ear_last_sent_percentage = percentage
        self._ear_send_seq += 1
        seq = self._ear_send_seq
        self._send_command(f"耳朵位置: {percentage}%", lambda: self._send_latest_ear_percentage(seq, percentage))
        if self._ear_repeat_until_ms > self._ear_last_send_ms:
            self._ear_pending_percentage = percentage
            if self._ear_send_after_id is None:
                self._ear_send_after_id = self.root.after(EAR_SEND_INTERVAL_MS, lambda: self._send_current_ear_percentage(force=True))

    def _send_latest_ear_percentage(self, seq: int, percentage: int) -> None:
        if seq == self._ear_send_seq:
            self.controller.send_ear_percentage(percentage)

    def _on_special_detection_toggle(self) -> None:
        enabled = bool(self.special_detection_enabled.get())
        text = "开启" if enabled else "关闭"
        self._send_command(f"{text}特殊状态检测", lambda: self.controller.set_special_detection(enabled))

    def _send_expression(self, expression: object) -> None:
        assert isinstance(expression, ExpressionAction)
        self._send_command(f"表情: {expression.name}", lambda: self.controller.send_expression(expression))

    def _send_audio(self, tone_id: int) -> None:
        name = "STOP" if tone_id == int(Tone.STOP) else str(tone_id)
        self._send_command(f"音效: {name}", lambda: self.controller.send_audio(tone_id))

    def _set_volume(self, level: int) -> None:
        self._send_command(f"音量: {level} 档", lambda: self.controller.set_volume(level))

    def _toggle_imu_stream(self) -> None:
        enabled = bool(self.imu_enabled.get())
        hz = self._sensor_hz()
        self._send_command(f"IMU {'开启' if enabled else '关闭'}", lambda: self.controller.request_imu_stream(enabled, hz))

    def _toggle_tof_stream(self) -> None:
        enabled = bool(self.tof_enabled.get())
        hz = self._sensor_hz()
        self._send_command(f"TOF {'开启' if enabled else '关闭'}", lambda: self.controller.request_tof_stream(enabled, hz))

    def _apply_sensor_hz(self) -> None:
        hz = self._sensor_hz()
        imu_on = bool(self.imu_enabled.get())
        tof_on = bool(self.tof_enabled.get())
        if not imu_on and not tof_on:
            self._append_log("采样率已更新；数据流未开启，暂未发送到固件。")
            return

        def apply() -> None:
            if imu_on:
                self.controller.request_imu_stream(True, hz)
            if tof_on:
                self.controller.request_tof_stream(True, hz)

        streams = []
        if imu_on:
            streams.append("IMU")
        if tof_on:
            streams.append("TOF")
        self._send_command(f"应用采样率 {hz}Hz ({'/'.join(streams)})", apply)

    def _sensor_hz(self) -> int:
        try:
            return max(1, min(100, int(self.sensor_hz_var.get())))
        except Exception:
            return 20

    def _on_imu(self, imu: Dict[str, object]) -> None:
        ts = time.monotonic()
        for key, plot in (
            ("yaw_deg", self.imu_yaw_plot),
            ("pitch_deg", self.imu_pitch_plot),
            ("roll_deg", self.imu_roll_plot),
        ):
            value = imu.get(key)
            if isinstance(value, (int, float)):
                plot.add(float(value), ts)

    def _on_tof(self, tof: Dict[str, object]) -> None:
        ts = time.monotonic()
        front = tof.get("front_mm")
        oblique = tof.get("oblique_mm")
        if isinstance(front, (int, float)):
            self.tof_front_plot.add(float(front), ts)
        if isinstance(oblique, (int, float)):
            self.tof_oblique_plot.add(float(oblique), ts)

    def _redraw_plots(self) -> None:
        for plot in self._all_plots():
            plot.redraw()
        self.root.after(PLOT_REFRESH_MS, self._redraw_plots)

    def _clear_plots(self) -> None:
        for plot in self._all_plots():
            plot.clear()

    def _all_plots(self) -> Tuple[LinePlot, ...]:
        return (
            self.imu_yaw_plot,
            self.imu_pitch_plot,
            self.imu_roll_plot,
            self.tof_front_plot,
            self.tof_oblique_plot,
        )

    def _poll_queues(self) -> None:
        if self.connected_url and not self.controller.is_connected():
            self.connected_url = None
            self.active_movement = None
            self.imu_enabled.set(False)
            self.tof_enabled.set(False)
            self.status_var.set("状态: WebSocket 已断开")
            self.connect_btn.configure(text="等待连接", state=tk.NORMAL)
        self._drain_ui_queue()
        self._drain_log_queue()
        self.root.after(UI_POLL_MS, self._poll_queues)

    def _drain_ui_queue(self) -> None:
        while True:
            try:
                kind, payload = self.ui_queue.get_nowait()
            except queue.Empty:
                return
            if kind == "task_ok":
                label, result, on_success = payload  # type: ignore[misc]
                self._append_log(f"{label}: 完成")
                if on_success:
                    on_success(result)
                if label not in ("等待 WebSocket 连接", "断开 WebSocket"):
                    self._restore_connection_buttons()
            elif kind == "task_error":
                label, exc = payload  # type: ignore[misc]
                self._append_log(f"{label}: 失败 - {exc}")
                if label == "等待 WebSocket 连接":
                    self.connect_btn.configure(state=tk.NORMAL)
                    self.status_var.set("状态: WebSocket 连接失败")
                elif label == "断开 WebSocket":
                    self.connect_btn.configure(state=tk.NORMAL)
                    self.status_var.set("状态: WebSocket 断开失败")

    def _restore_connection_buttons(self) -> None:
        self.connect_btn.configure(state=tk.NORMAL)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                return
            self._append_log(message)

    def _append_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def on_close(self) -> None:
        self.controller.remove_imu_listener(self._on_imu)
        self.controller.remove_tof_listener(self._on_tof)
        try:
            self.controller.shutdown()
        finally:
            self.worker_queue.put(("__quit__", lambda: None, None))
            self.root.destroy()


def _unique_enum_members(
    enum_cls: object,
    *,
    hidden_ids: Optional[set[int]] = None,
) -> List[Tuple[str, int, object]]:
    """Return unique-valued enum members, skipping aliases."""
    members: List[Tuple[str, int, object]] = []
    seen_values = set()
    hidden = hidden_ids or set()
    for name, member in enum_cls.__members__.items():  # type: ignore[attr-defined]
        value = int(member)
        if value in hidden or value in seen_values:
            continue
        seen_values.add(value)
        members.append((name, value, member))
    return members


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    UserControlApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
