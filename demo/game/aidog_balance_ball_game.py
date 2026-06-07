"""IMU roll controlled balance ball mini game for Changba AI-Dog."""

from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


DEFAULT_SCORE_FILE = Path(__file__).with_name("aidog_balance_ball_score.json")
GAME_WIDTH = 960
GAME_HEIGHT = 540


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


class ScoreStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return max(0, int(data.get("high_score", 0)))
        except Exception:
            return 0

    def save_if_higher(self, score: int) -> bool:
        current = self.load()
        if int(score) <= current:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "high_score": int(score),
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True


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


@dataclass
class GameConfig:
    beam_half: float = 320.0
    ball_radius: float = 18.0
    gravity_scale: float = 900.0
    damping: float = 0.992
    ready_delay_s: float = 1.0


class BalanceBallGame:
    WAIT_IMU = "WAIT_IMU"
    CALIBRATING = "CALIBRATING"
    READY = "READY"
    RUNNING = "RUNNING"
    GAME_OVER = "GAME_OVER"

    def __init__(self, config: GameConfig, score_store: ScoreStore) -> None:
        self.config = config
        self.score_store = score_store
        self.high_score = score_store.load()
        self.state = self.WAIT_IMU
        self.ball_x = 0.0
        self.ball_v = 0.0
        self.score = 0.0
        self.elapsed_s = 0.0
        self.lever_angle_deg = 0.0
        self._calibration_samples: list[float] = []
        self._calibration_started_s = 0.0
        self._ready_started_s = 0.0

    def has_valid_imu(self, latest_time_s: float, now_s: float) -> bool:
        return latest_time_s > 0.0 and now_s - latest_time_s < 1.2

    def start_calibration(self, now_s: float) -> None:
        self.state = self.CALIBRATING
        self._calibration_samples.clear()
        self._calibration_started_s = now_s
        self.reset_round()

    def reset_round(self) -> None:
        self.ball_x = 0.0
        self.ball_v = 0.0
        self.score = 0.0
        self.elapsed_s = 0.0
        self.lever_angle_deg = 0.0

    def restart_ready(self, now_s: float) -> None:
        self.reset_round()
        self.state = self.READY
        self._ready_started_s = now_s

    def start_running(self) -> None:
        if self.state == self.READY:
            self.state = self.RUNNING

    def update_calibration(self, roll_deg: float, now_s: float, roll_filter: RollFilter) -> None:
        self._calibration_samples.append(float(roll_deg))
        if now_s - self._calibration_started_s < 1.2 or len(self._calibration_samples) < 8:
            return
        baseline = sum(self._calibration_samples) / len(self._calibration_samples)
        roll_filter.reset(baseline)
        self.restart_ready(now_s)

    def update_physics(self, dt_s: float, lever_angle_deg: float) -> None:
        self.lever_angle_deg = float(lever_angle_deg)
        if self.state != self.RUNNING:
            return
        dt = min(max(float(dt_s), 0.0), 0.05)
        self.elapsed_s += dt
        if self.elapsed_s < self.config.ready_delay_s:
            self.score += dt * 10.0
            return

        angle_rad = math.radians(self.lever_angle_deg)
        acc = self.config.gravity_scale * math.sin(angle_rad)
        self.ball_v += acc * dt
        self.ball_v *= self.config.damping
        self.ball_x += self.ball_v * dt

        safe_half = self.config.beam_half - self.config.ball_radius
        center_ratio = 1.0 - min(abs(self.ball_x) / max(1.0, safe_half), 1.0)
        self.score += dt * (10.0 + center_ratio * 40.0)

        if abs(self.ball_x) > safe_half:
            self.state = self.GAME_OVER
            final_score = int(self.score)
            if self.score_store.save_if_higher(final_score):
                self.high_score = final_score


class WsImuReader:
    def __init__(self, latest_roll: LatestRoll, bind: str, port: int, hz: int, timeout_s: float) -> None:
        self.latest_roll = latest_roll
        self.bind = bind
        self.port = int(port)
        self.hz = int(hz)
        self.timeout_s = float(timeout_s)
        self.dog = None
        self.host = None
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        from aidog_sdk import AiDog, DevPcWebSocketHost

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
                    dog.request_imu_stream(True, hz=self.hz, transport="ws")
                    stream_enabled = True
                except Exception:
                    stream_enabled = False
            elif not connected:
                stream_enabled = False
                if self.timeout_s > 0.0 and time.monotonic() > deadline_s:
                    deadline_s = time.monotonic() + self.timeout_s
            self._stop_event.wait(0.2)


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


class PygameRenderer:
    def __init__(self, width: int, height: int) -> None:
        import pygame

        pygame.init()
        pygame.display.set_caption("AIDog IMU Balance Ball")
        self.pygame = pygame
        self.screen = pygame.display.set_mode((width, height))
        self.clock = pygame.time.Clock()
        self.width = width
        self.height = height
        self.font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 24)
        self.big_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 34)

    def tick(self, fps: int = 60) -> float:
        return self.clock.tick(fps) / 1000.0

    def draw(self, game: BalanceBallGame) -> None:
        pg = self.pygame
        self.screen.fill((246, 248, 251))
        self._draw_scores(game)
        self._draw_balance(game)
        self._draw_state(game)
        pg.display.flip()

    def _draw_scores(self, game: BalanceBallGame) -> None:
        self._draw_text(f"当前分数：{int(game.score)}", 28, 24, (31, 41, 55))
        high = f"历史最高分：{game.high_score}"
        surface = self.font.render(high, True, (31, 41, 55))
        self.screen.blit(surface, (self.width - surface.get_width() - 28, 24))

    def _draw_balance(self, game: BalanceBallGame) -> None:
        pg = self.pygame
        cx = self.width // 2
        cy = int(self.height * 0.66)
        beam_half = int(game.config.beam_half)
        angle = math.radians(game.lever_angle_deg)
        direction = (math.cos(angle), math.sin(angle))
        normal = (-math.sin(angle), math.cos(angle))
        p1 = (cx - direction[0] * beam_half, cy - direction[1] * beam_half)
        p2 = (cx + direction[0] * beam_half, cy + direction[1] * beam_half)
        pivot = [(cx, cy - 10), (cx - 82, cy + 110), (cx + 82, cy + 110)]
        pg.draw.polygon(self.screen, (73, 116, 199), pivot)
        pg.draw.polygon(self.screen, (45, 83, 159), pivot, 2)
        pg.draw.line(self.screen, (45, 102, 211), p1, p2, 5)

        ball_track = game.ball_x
        bx = cx + direction[0] * ball_track - normal[0] * (game.config.ball_radius + 5)
        by = cy + direction[1] * ball_track - normal[1] * (game.config.ball_radius + 5)
        pg.draw.circle(self.screen, (67, 114, 196), (int(bx), int(by)), int(game.config.ball_radius))
        pg.draw.circle(self.screen, (37, 78, 148), (int(bx), int(by)), int(game.config.ball_radius), 2)

    def _draw_state(self, game: BalanceBallGame) -> None:
        messages = {
            BalanceBallGame.WAIT_IMU: "等待 IMU / WebSocket 连接",
            BalanceBallGame.CALIBRATING: "校准中，请保持当前姿态",
            BalanceBallGame.READY: "按空格开始，按 R 重新校准",
            BalanceBallGame.RUNNING: "",
            BalanceBallGame.GAME_OVER: "失败，按空格重来，按 R 重新校准",
        }
        msg = messages.get(game.state, "")
        if not msg:
            return
        surface = self.big_font.render(msg, True, (15, 23, 42))
        x = (self.width - surface.get_width()) // 2
        self.screen.blit(surface, (x, 96))

    def _draw_text(self, text: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
        surface = self.font.render(text, True, color)
        self.screen.blit(surface, (x, y))


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))


def build_reader(args: argparse.Namespace, latest_roll: LatestRoll):
    if args.transport == "ws":
        return WsImuReader(latest_roll, args.bind, args.port, args.hz, args.connect_timeout)
    if args.transport == "ble":
        return BleImuReader(latest_roll, args.name_prefix, args.address, args.hz)
    return KeyboardRollReader(latest_roll)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AIDog IMU balance ball game")
    parser.add_argument("--transport", choices=("ws", "ble", "keyboard"), default="ws")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--connect-timeout", type=float, default=60.0)
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog")
    parser.add_argument("--address", default=None)
    parser.add_argument("--hz", type=int, default=40)
    parser.add_argument("--invert-roll", action="store_true")
    parser.add_argument("--sensitivity", type=float, default=1.0)
    parser.add_argument("--max-angle", type=float, default=18.0)
    parser.add_argument("--score-file", type=Path, default=DEFAULT_SCORE_FILE)
    return parser.parse_args(argv)


def run_game(args: argparse.Namespace) -> int:
    try:
        renderer = PygameRenderer(GAME_WIDTH, GAME_HEIGHT)
    except ModuleNotFoundError as exc:
        if exc.name == "pygame":
            print("缺少 pygame，请先执行：python -m pip install pygame", file=sys.stderr)
            return 2
        raise

    latest_roll = LatestRoll()
    reader = build_reader(args, latest_roll)
    roll_filter = RollFilter(
        RollFilterConfig(
            sensitivity=args.sensitivity,
            max_angle_deg=args.max_angle,
            invert=args.invert_roll,
        )
    )
    score_store = ScoreStore(args.score_file)
    game = BalanceBallGame(GameConfig(), score_store)

    try:
        reader.start()
    except Exception as exc:
        print(f"IMU 输入启动失败：{exc}", file=sys.stderr)
        return 1

    pg = renderer.pygame
    running = True
    last_s = time.monotonic()

    try:
        while running:
            now_s = time.monotonic()
            dt_s = now_s - last_s
            last_s = now_s

            if isinstance(reader, KeyboardRollReader):
                reader.update(pg.key.get_pressed(), pg)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.KEYDOWN:
                    if event.key == pg.K_ESCAPE:
                        running = False
                    elif event.key == pg.K_r:
                        game.start_calibration(now_s)
                    elif event.key == pg.K_SPACE:
                        if game.state == BalanceBallGame.READY:
                            game.start_running()
                        elif game.state == BalanceBallGame.GAME_OVER:
                            game.restart_ready(now_s)

            roll, roll_time_s = latest_roll.snapshot()
            imu_ok = game.has_valid_imu(roll_time_s, now_s)
            if not imu_ok:
                if game.state != BalanceBallGame.WAIT_IMU:
                    game.state = BalanceBallGame.WAIT_IMU
                lever_angle = 0.0
            elif roll is not None:
                if game.state == BalanceBallGame.WAIT_IMU:
                    game.start_calibration(now_s)
                if game.state == BalanceBallGame.CALIBRATING:
                    game.update_calibration(roll, now_s, roll_filter)
                lever_angle = roll_filter.update(roll)
            else:
                lever_angle = 0.0

            game.update_physics(dt_s, lever_angle)
            renderer.draw(game)
            renderer.tick(60)
    finally:
        reader.stop()
        pg.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    return run_game(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
