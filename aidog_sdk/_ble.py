"""
BLE transport layer — internal module.
Runs an asyncio event loop in a background thread so the public API stays synchronous.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Callable, List, Mapping, Optional, Tuple

from bleak import BleakClient, BleakScanner

logger = logging.getLogger(__name__)

# Characteristic UUID suffixes/prefixes
_UUID_NOTIFY  = "ae02"   # ae02 → subscribe for device→host notifications
_UUID_NOTIFY_IMU = "ae04"  # ae04 → 传感器流（IMU/TOF JSON）
_UUID_WRITE = "ae03"     # ae03 → write commands (binary packet)
_UUID_CONFIG = "ae01"    # ae01 config JSON
_UUID_ACTIONS = "0000ae10-0000-1000-8000-00805f9b34fb"  # read action list

_HEADER = 0xAA55

_SCAN_TIMEOUT    = 5.0   # seconds for BLE scan
_CONNECT_TIMEOUT = 10.0  # seconds for BLE connect
_WRITE_TIMEOUT = 3.0     # seconds per write call
_DEFAULT_CONNECT_RETRIES = 3
_DEFAULT_CONNECT_RETRY_DELAY = 1.0
_DEFAULT_WRITE_RETRIES = 2
_DEFAULT_WRITE_RETRY_DELAY = 0.12
_SCAN_CACHE_TTL = 30.0


class BleTransport:
    """
    Thread-safe, synchronous BLE transport.

    A dedicated asyncio loop runs in a daemon thread. All async operations are
    submitted via ``asyncio.run_coroutine_threadsafe`` and their futures are
    resolved before returning to the caller.
    """

    def __init__(
        self,
        on_notify: Optional[Callable[[bytes], None]] = None,
        *,
        subscribe_ae02: bool = True,
        subscribe_ae04: bool = True,
    ):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="aidog-ble-loop")
        self._thread.start()

        self._client: Optional[BleakClient] = None
        self._config_uuid: Optional[str] = None
        self._write_uuid: Optional[str] = None
        self._notify_uuids: List[str] = []
        self._on_notify = on_notify  # optional raw-bytes callback
        self._subscribe_ae02 = bool(subscribe_ae02)
        self._subscribe_ae04 = bool(subscribe_ae04)
        self._scan_cache: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run(self, coro, timeout: float = 15.0):
        """Submit *coro* to the background loop and block until done."""
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def shutdown(self) -> None:
        """Disconnect (if connected) and stop the background event loop."""
        if self._client:
            try:
                self._run(self._disconnect_async(), timeout=5.0)
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)

    # ------------------------------------------------------------------
    # Scan & Connect
    # ------------------------------------------------------------------

    def scan(self, name_prefix: str) -> List[Tuple[str, str]]:
        """
        Scan for BLE devices whose name starts with *name_prefix*.

        Returns a list of ``(name, address)`` tuples.
        """
        return self._run(self._scan_async(name_prefix), timeout=_SCAN_TIMEOUT + 2)

    async def _scan_async(self, name_prefix: str) -> List[Tuple[str, str]]:
        devices = await BleakScanner.discover(timeout=_SCAN_TIMEOUT)
        matches = [
            (d.name, d.address)
            for d in devices
            if d.name and d.name.startswith(name_prefix)
        ]
        now = time.monotonic()
        for _, address in matches:
            self._scan_cache[address] = now
        return matches

    def connect(
        self,
        address: str,
        *,
        retries: int = _DEFAULT_CONNECT_RETRIES,
        retry_delay_s: float = _DEFAULT_CONNECT_RETRY_DELAY,
    ) -> bool:
        """
        Connect to a device by BLE *address*.

        Discovers services and locates target characteristics.

        Returns ``True`` on success.
        """
        attempts = max(1, int(retries))
        last_exc: Optional[Exception] = None
        for i in range(attempts):
            try:
                return self._run(self._connect_async(address), timeout=_CONNECT_TIMEOUT + 10)
            except Exception as e:
                last_exc = e
                if i < attempts - 1:
                    logger.warning(
                        "BLE connect attempt %s/%s failed: %s. Retrying in %.1fs...",
                        i + 1,
                        attempts,
                        e,
                        retry_delay_s,
                    )
                    time.sleep(max(0.0, retry_delay_s))
        if last_exc:
            raise last_exc
        return False

    async def _connect_async(self, address: str) -> bool:
        # Disconnect from any previous session
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._config_uuid = None
        self._write_uuid = None
        self._notify_uuids = []

        # Windows WinRT BLE backend often needs the device to be present in the
        # scanner cache. If scan() just found this address, reuse that cache and
        # avoid an extra 3-second pre-scan.
        cached_at = self._scan_cache.get(address)
        recently_scanned = cached_at is not None and (time.monotonic() - cached_at) <= _SCAN_CACHE_TTL
        if not recently_scanned:
            logger.debug("BLE pre-scanning to discover %s", address)
            devices = await BleakScanner.discover(timeout=3.0)
            now = time.monotonic()
            for dev in devices:
                if dev.address:
                    self._scan_cache[dev.address] = now

        client = BleakClient(address)
        await client.connect(timeout=_CONNECT_TIMEOUT)

        # Discover services: ae02/ae04 notify + ae03 write
        services = client.services
        if not services:
            get_services = getattr(client, "get_services", None)
            if callable(get_services):
                services = await get_services()

        for svc in services:
            for char in svc.characteristics:
                u = char.uuid.lower()
                props = char.properties or []
                # Bleak sometimes reports "indicate" instead of "notify" depending on backend.
                want_notify = (
                    (self._subscribe_ae02 and _UUID_NOTIFY in u)
                    or (self._subscribe_ae04 and _UUID_NOTIFY_IMU in u)
                )
                if want_notify and ("notify" in props or "indicate" in props):
                    try:
                        await client.start_notify(char.uuid, self._notification_handler)
                        self._notify_uuids.append(char.uuid)
                    except Exception:
                        pass
                if _UUID_CONFIG in u and ("write" in props or "write-without-response" in props):
                    self._config_uuid = char.uuid
                if _UUID_WRITE in u and ("write" in props or "write-without-response" in props):
                    self._write_uuid = char.uuid

        self._client = client
        if self._notify_uuids:
            logger.debug(
                "BLE subscribing notify uuids: %s",
                ", ".join(str(x) for x in self._notify_uuids),
            )
        return client.is_connected

    def disconnect(self) -> None:
        """Disconnect from the current device."""
        if self._client:
            self._run(self._disconnect_async(), timeout=5.0)

    async def _disconnect_async(self) -> None:
        if self._client:
            try:
                for nu in list(self._notify_uuids):
                    try:
                        await self._client.stop_notify(nu)
                    except Exception:
                        pass
                self._notify_uuids = []
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
            self._config_uuid = None
            self._write_uuid = None

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def send_data(
        self,
        mode: int,
        data: List[int],
        *,
        retries: int = _DEFAULT_WRITE_RETRIES,
        retry_delay_s: float = _DEFAULT_WRITE_RETRY_DELAY,
    ) -> None:
        """
        Send binary packet:
        [0xAA, 0x55, 0x00, mode, ...data].
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to a device.")
        if not self._write_uuid:
            raise RuntimeError("Write characteristic (ae03) not found on this device.")

        packet = [_HEADER >> 8, _HEADER & 0xFF, 0x00, mode] + [x & 0xFF for x in data]
        payload = bytes(packet)

        attempts = max(1, int(retries))
        last_exc: Optional[Exception] = None
        for i in range(attempts):
            try:
                self._run(self._write_raw_async(payload), timeout=_WRITE_TIMEOUT)
                return
            except Exception as e:
                last_exc = e
                if i < attempts - 1:
                    time.sleep(max(0.0, retry_delay_s))
        if last_exc:
            raise last_exc

    def send_control_json(
        self,
        payload: Mapping[str, object],
        *,
        retries: int = _DEFAULT_WRITE_RETRIES,
        retry_delay_s: float = _DEFAULT_WRITE_RETRY_DELAY,
    ) -> None:
        """Send remote-control JSON to ae03."""
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to a device.")
        if not self._write_uuid:
            raise RuntimeError("Write characteristic (ae03) not found on this device.")

        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\0"
        attempts = max(1, int(retries))
        last_exc: Optional[Exception] = None
        for i in range(attempts):
            try:
                self._run(self._write_raw_async(data), timeout=_WRITE_TIMEOUT)
                return
            except Exception as e:
                last_exc = e
                if i < attempts - 1:
                    time.sleep(max(0.0, retry_delay_s))
        if last_exc:
            raise last_exc

    async def _write_raw_async(self, payload: bytes) -> None:
        assert self._client and self._write_uuid
        await self._client.write_gatt_char(self._write_uuid, payload, response=False)

    def send_config_json(
        self,
        payload: Mapping[str, object],
        *,
        retries: int = _DEFAULT_WRITE_RETRIES,
        retry_delay_s: float = _DEFAULT_WRITE_RETRY_DELAY,
    ) -> None:
        """Send config JSON to ae01."""
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to a device.")
        if not self._config_uuid:
            raise RuntimeError("Config characteristic (ae01) not found on this device.")

        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\0"
        attempts = max(1, int(retries))
        last_exc: Optional[Exception] = None
        for i in range(attempts):
            try:
                self._run(self._write_config_async(data), timeout=_WRITE_TIMEOUT)
                return
            except Exception as e:
                last_exc = e
                if i < attempts - 1:
                    time.sleep(max(0.0, retry_delay_s))
        if last_exc:
            raise last_exc

    async def _write_config_async(self, payload: bytes) -> None:
        assert self._client and self._config_uuid
        await self._client.write_gatt_char(self._config_uuid, payload, response=False)

    def read_actions(self) -> dict:
        """
        Read the action list from the ae10 characteristic and return a parsed dict.

        The device may split the JSON across multiple reads; this method retries
        up to 10 times and reassembles the fragments before parsing.
        """
        if not self._client or not self._client.is_connected:
            raise ConnectionError("Not connected to a device.")
        return self._run(self._read_actions_async(), timeout=30.0)

    async def _read_actions_async(self) -> dict:
        buf = ""
        for _ in range(10):
            data = await self._client.read_gatt_char(_UUID_ACTIONS)
            buf += data.decode("utf-8", errors="ignore")
            try:
                return json.loads(buf.strip())
            except json.JSONDecodeError:
                await asyncio.sleep(0.2)
        raise ValueError("Could not read a complete JSON from ae10 after 10 attempts.")

    # ------------------------------------------------------------------
    # Notification handler
    # ------------------------------------------------------------------

    def _notification_handler(self, sender, data: bytes) -> None:
        if self._on_notify:
            self._on_notify(data)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)
