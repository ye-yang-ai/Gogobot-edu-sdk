"""
Dev PC WebSocket host — same socket as bidirectional PCM audio.

Firmware sends **binary** frames (16 kHz mono PCM) and optional **text** frames
with the same sensor JSON as BLE ``ae04`` (``imu`` / ``tof`` fields).
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Awaitable, Callable, Dict, Optional

from .dog import AiDog


def _is_websocket_connection_closed(exc: BaseException) -> bool:
    try:
        from websockets.exceptions import ConnectionClosed
    except Exception:
        return False
    return isinstance(exc, ConnectionClosed)


async def run_dev_pc_websocket_server(
    handler: Callable[[Any], Awaitable[None]],
    host: str,
    port: int,
    *,
    stop: Optional[asyncio.Event] = None,
    ready: Optional[threading.Event] = None,
) -> None:
    """
    Listen for robot WebSocket clients (``DEV_PC_AUDIO_WS_URL``), same defaults as
    :class:`DevPcWebSocketHost` (``max_size=None``).

    * If *stop* is ``None``, run until the coroutine is cancelled (typical for
      ``asyncio.run`` + Ctrl+C).
    * If *stop* is set, exit when that :class:`asyncio.Event` is set (used by
      :class:`DevPcWebSocketHost` in a background thread).
    * *ready* (optional threading event) is set once the server socket is listening.
    """
    import websockets

    async with websockets.serve(handler, host, int(port), max_size=None):
        if ready is not None:
            ready.set()
        if stop is None:
            await asyncio.Future()
        else:
            await stop.wait()


class DevPcWebSocketHost:
    """
    Run a WebSocket server on your PC for the robot to connect to (client mode on device).

    Parameters
    ----------
    host:
        Listen address; use ``0.0.0.0`` so the dog can reach you via LAN IP.
    port:
        Must match firmware ``DEV_PC_AUDIO_WS_URL`` port.
    dog:
        If set, text sensor JSON is passed to ``dog.feed_sensor_stream_json`` so
        ``get_latest_imu`` / listeners stay in sync with BLE semantics.
    on_imu / on_tof:
        Optional extra callbacks (in addition to *dog* listeners).
    on_pcm_from_robot:
        Invoked for each **binary** message from the robot (downlink PCM).
    connection_handler:
        If set, invoked as ``await connection_handler(websocket)`` for each robot
        connection instead of the default receive-only loop. Use for bidirectional
        PCM (e.g. ``examples/04_audio_ws_bidirectional_host.py``). When set,
        *dog*, *on_imu*, *on_tof*, and *on_pcm_from_robot* are not used.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8766,
        *,
        dog: Optional[AiDog] = None,
        on_imu: Optional[Callable[[Dict[str, object]], None]] = None,
        on_tof: Optional[Callable[[Dict[str, object]], None]] = None,
        on_pcm_from_robot: Optional[Callable[[bytes], None]] = None,
        connection_handler: Optional[Callable[[Any], Awaitable[None]]] = None,
    ) -> None:
        self._host = host
        self._port = int(port)
        self._dog = dog
        self._on_imu = on_imu
        self._on_tof = on_tof
        self._on_pcm = on_pcm_from_robot
        self._connection_handler = connection_handler
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_stop_ev: Optional[asyncio.Event] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._active_ws: Optional[Any] = None
        self._active_lock = threading.Lock()
        self._ack_cv = threading.Condition()
        self._acks: Dict[str, Dict[str, object]] = {}

    def _handle_text(self, message: str) -> None:
        try:
            obj = json.loads(message)
            if isinstance(obj, dict) and obj.get("type") == "ack":
                ack_id = obj.get("id")
                if ack_id is not None:
                    with self._ack_cv:
                        self._acks[str(ack_id)] = obj
                        self._ack_cv.notify_all()
                return
        except Exception:
            pass
        if self._dog is not None:
            self._dog.feed_sensor_stream_json(message)
        if self._on_imu is None and self._on_tof is None:
            return
        _, imu, tof = AiDog.parse_notify_json_text(message)
        if imu is not None and self._on_imu is not None:
            self._on_imu(imu)
        if tof is not None and self._on_tof is not None:
            self._on_tof(tof)

    async def _client_loop(self, ws) -> None:
        async for message in ws:
            if isinstance(message, str):
                self._handle_text(message)
            elif isinstance(message, (bytes, bytearray)) and self._on_pcm is not None:
                try:
                    self._on_pcm(bytes(message))
                except Exception:
                    pass

    async def _dispatch_connection(self, ws: Any, *_path: Any) -> None:
        with self._active_lock:
            self._active_ws = ws
        try:
            if self._connection_handler is not None:
                await self._connection_handler(ws)
            else:
                await self._client_loop(ws)
        except Exception as exc:
            if not _is_websocket_connection_closed(exc):
                raise
        finally:
            with self._active_lock:
                if self._active_ws is ws:
                    self._active_ws = None

    def _run(self) -> None:
        async def main() -> None:
            self._async_stop_ev = asyncio.Event()
            await run_dev_pc_websocket_server(
                self._dispatch_connection,
                self._host,
                self._port,
                stop=self._async_stop_ev,
                ready=self._ready,
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(main())
        finally:
            self._loop = None
            self._async_stop_ev = None
            try:
                loop.close()
            except Exception:
                pass

    def start(self, *, wait_ready_s: float = 5.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="aidog-dev-pc-ws")
        self._thread.start()
        if not self._ready.wait(timeout=wait_ready_s):
            raise TimeoutError(
                f"Dev PC WebSocket not listening on {self._host}:{self._port} within {wait_ready_s}s"
            )

    def send_text(self, text: str, *, timeout_s: float = 3.0) -> None:
        loop = self._loop
        with self._active_lock:
            ws = self._active_ws
        if loop is None or ws is None:
            raise ConnectionError("No active robot WebSocket connection.")
        fut = asyncio.run_coroutine_threadsafe(ws.send(str(text)), loop)
        fut.result(timeout=max(0.1, float(timeout_s)))

    def send_control_raw(
        self,
        mode: int,
        data: list[int],
        *,
        command_id: Optional[str] = None,
        timeout_s: float = 3.0,
    ) -> None:
        packet = bytes([0xAA, 0x55, 0x00, int(mode) & 0xFF, *[int(x) & 0xFF for x in data]])
        payload: Dict[str, object] = {"cmd": "control_raw", "packet": packet.hex().upper()}
        if command_id is not None:
            payload["id"] = str(command_id)
        self.send_text(json.dumps(payload, separators=(",", ":")), timeout_s=timeout_s)

    def wait_control_ack(
        self,
        command_id: str,
        *,
        timeout_s: float = 1.0,
    ) -> Optional[Dict[str, object]]:
        import time

        key = str(command_id)
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        with self._ack_cv:
            while True:
                ack = self._acks.pop(key, None)
                if ack is not None:
                    return ack
                remain_s = deadline - time.monotonic()
                if remain_s <= 0:
                    return None
                self._ack_cv.wait(remain_s)

    @property
    def is_robot_connected(self) -> bool:
        with self._active_lock:
            return self._active_ws is not None

    def wait_robot_connected(self, *, timeout_s: float = 30.0, poll_s: float = 0.1) -> bool:
        import time

        deadline = time.monotonic() + max(0.0, float(timeout_s))
        delay = max(0.01, float(poll_s))
        while time.monotonic() < deadline:
            if self.is_robot_connected:
                return True
            time.sleep(delay)
        return self.is_robot_connected

    def stop(self) -> None:
        loop = self._loop
        ev = self._async_stop_ev
        if loop is not None and ev is not None:

            def _set() -> None:
                ev.set()

            try:
                loop.call_soon_threadsafe(_set)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._thread = None
