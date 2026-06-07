"""IMU roll controlled balance ball mini game for Changba AI-Dog."""

from __future__ import annotations

import argparse
import json
import math
import random
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


GAME_ASSET_DIR = Path(__file__).with_name("icons")
GAME_SCORE_DIR = Path(__file__).with_name("scores")
DEFAULT_SCORE_FILE = GAME_SCORE_DIR / "aidog_balance_ball_score.json"
GOGO_LOGO_FILE = GAME_ASSET_DIR / "gogo_logo.png"
GAME_WIDTH = 960
GAME_HEIGHT = 540
BALANCE_CENTER_Y_RATIO = 0.66
PIVOT_HALF_WIDTH = 82
PIVOT_HEIGHT = 110
CHALLENGE_BADGE_TOPRIGHT = (28, 84)
BUTTON_ROW_TOP = 158
RESTART_BUTTON_LEFT = 28
PREPARE_BUTTON_LEFT = 190
GAME_POSE_ACTION = "slow_down"
REWARD_AUDIO_NAMES = ("AGREE", "HENG", "UH", "CURIOUS", "WAKE_UP")
REWARD_EXPRESSION_NAMES = ("HAPPY_01", "HAPPY_02", "LOVE_01", "SMILE_01", "PRIDE")
REWARD_FOOD_TYPES = ("apple", "banana", "carrot", "pumpkin", "chicken", "biscuit", "cheese")
DANGER_EXPRESSION_NAME = "NERVOUS"
START_AUDIO_NAME = "WAKE_UP"
START_EXPRESSION_NAME = "EYES_FIGHTING"
FINISH_AUDIO_NAME = "SAD"
FINISH_EXPRESSION_NAME = "SHAME"
SCORE_MILESTONES = (1000, 2000, 3000, 4000, 5000)
MILESTONE_LABELS = ("Nice!", "Great!", "Excellent!", "Amazing!", "Unbelievable!")
PIVOT_FILL_COLOR = (55, 65, 81)
PIVOT_BORDER_COLOR = (31, 41, 55)
BALL_RADIUS = 21.0
BALL_FILL_COLOR = (55, 65, 81)
BALL_HIGHLIGHT_COLOR = (148, 163, 184)


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
    ball_radius: float = BALL_RADIUS
    gravity_scale: float = 900.0
    damping: float = 0.992
    ready_delay_s: float = 1.0
    base_score_per_s: float = 1.0
    edge_bonus_per_s: float = 11.0
    high_score_zone_ratio: float = 0.65
    danger_zone_ratio: float = 0.90
    reward_score: int = 260
    reward_radius: float = 12.0
    reward_min_ratio: float = 0.35
    reward_max_ratio: float = 0.85


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
        self.edge_ratio = 0.0
        self.difficulty_level = 0
        self.current_gravity_scale = self.config.gravity_scale
        self.current_damping = self.config.damping
        self.reward_x = 0.0
        self.reward_food = "apple"
        self.reward_visible = False
        self.reward_count = 0
        self.reward_event_id = 0
        self.milestone_event_id = 0
        self.milestone_label = ""
        self.last_reward_score = 0
        self._next_milestone_index = 0
        self._reward_side = 1
        self._rng = random.Random()
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
        self.edge_ratio = 0.0
        self.difficulty_level = 0
        self.current_gravity_scale = self.config.gravity_scale
        self.current_damping = self.config.damping
        self.reward_count = 0
        self.reward_event_id = 0
        self.milestone_event_id = 0
        self.milestone_label = ""
        self.last_reward_score = 0
        self._next_milestone_index = 0
        self.reward_visible = False

    def restart_ready(self, now_s: float) -> None:
        self.reset_round()
        self.state = self.READY
        self._ready_started_s = now_s

    def start_running(self) -> None:
        if self.state == self.READY:
            self._spawn_reward()
            self.reward_visible = True
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
            self._add_score(dt * self.config.base_score_per_s)
            return

        angle_rad = math.radians(self.lever_angle_deg)
        self._update_difficulty()
        acc = self.current_gravity_scale * math.sin(angle_rad)
        self.ball_v += acc * dt
        self.ball_v *= self.current_damping
        self.ball_x += self.ball_v * dt

        safe_half = self.config.beam_half - self.config.ball_radius
        self.edge_ratio = min(abs(self.ball_x) / max(1.0, safe_half), 1.0)
        self._add_score(dt * (
            self.config.base_score_per_s + self.edge_ratio * self.config.edge_bonus_per_s
        ))
        self._collect_reward_if_hit(safe_half)

        if abs(self.ball_x) > safe_half:
            self.state = self.GAME_OVER
            final_score = int(self.score)
            if self.score_store.save_if_higher(final_score):
                self.high_score = final_score

    def _spawn_reward(self) -> None:
        safe_half = max(1.0, self.config.beam_half - self.config.ball_radius)
        min_x = safe_half * min(self.config.reward_min_ratio, self.config.reward_max_ratio)
        max_x = safe_half * max(self.config.reward_min_ratio, self.config.reward_max_ratio)
        self._reward_side *= -1
        self.reward_x = self._reward_side * self._rng.uniform(min_x, max_x)
        self.reward_food = self._rng.choice(REWARD_FOOD_TYPES)

    def _collect_reward_if_hit(self, safe_half: float) -> bool:
        if not self.reward_visible:
            return False
        if abs(self.ball_x) > safe_half:
            return False
        hit_distance = self.config.ball_radius + self.config.reward_radius
        if abs(self.ball_x - self.reward_x) > hit_distance:
            return False
        self._add_score(self.config.reward_score)
        self.reward_count += 1
        self.reward_event_id += 1
        self.last_reward_score = self.config.reward_score
        self._spawn_reward()
        self.reward_visible = True
        return True

    def _add_score(self, amount: float) -> None:
        self.score += float(amount)
        while self._next_milestone_index < len(SCORE_MILESTONES):
            target = SCORE_MILESTONES[self._next_milestone_index]
            if self.score < target:
                break
            self.milestone_label = MILESTONE_LABELS[
                min(self._next_milestone_index, len(MILESTONE_LABELS) - 1)
            ]
            self.milestone_event_id += 1
            self._next_milestone_index += 1

    def _update_difficulty(self) -> None:
        self.difficulty_level = sum(1 for target in SCORE_MILESTONES if self.score >= target)
        self.current_gravity_scale = self.config.gravity_scale * (1.0 + self.difficulty_level * 0.08)
        self.current_damping = min(0.998, self.config.damping + self.difficulty_level * 0.0015)

    @property
    def combo_count(self) -> int:
        return max(0, int(self.reward_count))


@dataclass
class CelebrationParticle:
    x: float
    y: float
    vx: float
    vy: float
    life_s: float
    color: Tuple[int, int, int]


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
        self.small_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 16)
        self.hud_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 26, bold=True)
        self.big_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 38)
        self.title_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 42, bold=True)
        self.restart_button_rect = pygame.Rect(RESTART_BUTTON_LEFT, BUTTON_ROW_TOP, 132, 30)
        self.prepare_button_rect = pygame.Rect(PREPARE_BUTTON_LEFT, BUTTON_ROW_TOP, 160, 30)
        self.pressed_button: Optional[str] = None
        self.feedback_message = ""
        self.feedback_until_s = 0.0
        self.celebration_label = ""
        self.celebration_until_s = 0.0
        self.particles: list[CelebrationParticle] = []
        self.gogo_logo = self._load_gogo_logo()

    def _load_gogo_logo(self):
        if not GOGO_LOGO_FILE.exists():
            return None
        try:
            logo = self.pygame.image.load(str(GOGO_LOGO_FILE)).convert_alpha()
        except Exception:
            return None
        for x in range(logo.get_width()):
            for y in range(logo.get_height()):
                r, g, b, a = logo.get_at((x, y))
                if r > 235 and g > 235 and b > 235:
                    logo.set_at((x, y), (0, 0, 0, 0))
                elif a:
                    logo.set_at((x, y), (229, 231, 235, a))
        return logo

    def tick(self, fps: int = 60) -> float:
        return self.clock.tick(fps) / 1000.0

    def set_button_feedback(self, message: str, now_s: float) -> None:
        self.feedback_message = str(message)
        self.feedback_until_s = now_s + 1.2

    def celebrate(self, label: str, now_s: float) -> None:
        self.celebration_label = str(label)
        self.celebration_until_s = now_s + 1.6
        cx = self.width / 2
        cy = self.height * 0.26
        colors = ((10, 132, 255), (52, 199, 89), (255, 149, 0), (255, 204, 0), (175, 82, 222), (255, 59, 48))
        for i in range(56):
            angle = (math.tau / 56) * i + random.uniform(-0.08, 0.08)
            speed = random.uniform(95.0, 245.0)
            self.particles.append(
                CelebrationParticle(
                    cx,
                    cy,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed,
                    random.uniform(0.7, 1.2),
                    random.choice(colors),
                )
            )

    def draw(self, game: BalanceBallGame) -> None:
        pg = self.pygame
        self._draw_background()
        self._draw_hud(game)
        self._draw_buttons()
        self._draw_balance(game)
        self._draw_state(game)
        self._draw_celebration()
        pg.display.flip()

    def _draw_background(self) -> None:
        top = (16, 17, 20)
        mid = (11, 13, 18)
        bottom = (8, 9, 13)
        for y in range(self.height):
            t = y / max(1, self.height - 1)
            color = self._lerp_color(top, mid if t < 0.55 else bottom, min(1.0, t * 1.35))
            self.pygame.draw.line(self.screen, color, (0, y), (self.width, y))
        pg = self.pygame
        grid_color = (255, 255, 255, 13)
        grid = pg.Surface((self.width, self.height), pg.SRCALPHA)
        for x in range(0, self.width, 30):
            pg.draw.line(grid, grid_color, (x, 0), (x, self.height))
        for y in range(0, self.height, 30):
            pg.draw.line(grid, grid_color, (0, y), (self.width, y))
        self.screen.blit(grid, (0, 0))

    @staticmethod
    def _lerp_color(start: Tuple[int, int, int], end: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
        t = min(1.0, max(0.0, float(t)))
        return tuple(int(a + (b - a) * t) for a, b in zip(start, end))

    def _draw_gradient_rect(
        self,
        rect,
        top_color: Tuple[int, int, int],
        bottom_color: Tuple[int, int, int],
        border_color: Optional[Tuple[int, int, int]] = None,
        radius: int = 0,
    ) -> None:
        pg = self.pygame
        surface = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
        for y in range(rect.height):
            color = self._lerp_color(top_color, bottom_color, y / max(1, rect.height - 1))
            pg.draw.line(surface, color, (0, y), (rect.width, y))
        mask = pg.Surface((rect.width, rect.height), pg.SRCALPHA)
        pg.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
        surface.blit(mask, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
        self.screen.blit(surface, rect)
        if border_color is not None:
            pg.draw.rect(self.screen, border_color, rect, 1, border_radius=radius)

    def _draw_soft_shadow(self, rect, radius: int, alpha: int = 34, offset: Tuple[int, int] = (0, 10)) -> None:
        pg = self.pygame
        shadow = pg.Surface((rect.width + 24, rect.height + 24), pg.SRCALPHA)
        pg.draw.rect(shadow, (15, 23, 42, alpha), shadow.get_rect().inflate(-12, -12), border_radius=radius)
        self.screen.blit(shadow, (rect.x - 12 + offset[0], rect.y - 12 + offset[1]))

    def _draw_hud(self, game: BalanceBallGame) -> None:
        pg = self.pygame
        mark = pg.Rect(22, 18, 34, 34)
        pg.draw.rect(self.screen, (248, 250, 252), mark, border_radius=8)
        go = self.small_font.render("GO", True, (17, 24, 39))
        self.screen.blit(go, (mark.centerx - go.get_width() // 2, mark.centery - go.get_height() // 2))
        brand = self.hud_font.render("GOGO BALANCE", True, (248, 250, 252))
        self.screen.blit(brand, (68, 17))
        subtitle = self.small_font.render("ARCADE CHALLENGE", True, (245, 158, 11))
        self.screen.blit(subtitle, (69, 47))

        score_surface = self.big_font.render(str(int(game.score)), True, (248, 250, 252))
        self.screen.blit(score_surface, (22, 78))
        label_surface = self.small_font.render("SCORE", True, (148, 163, 184))
        self.screen.blit(label_surface, (25, 122))

        best = self.hud_font.render(f"BEST {game.high_score}", True, (212, 212, 216))
        best_rect = best.get_rect(topright=(self.width - 22, 22)).inflate(18, 12)
        pg.draw.rect(self.screen, (15, 23, 42), best_rect)
        pg.draw.rect(self.screen, (63, 70, 87), best_rect, 1)
        self.screen.blit(best, (best_rect.x + 9, best_rect.y + 6))

        combo = game.combo_count
        chips = (
            (f"COMBO x{combo}", True),
            (f"LEVEL {game.difficulty_level + 1:02d}", False),
            (f"ROLL {game.lever_angle_deg:+.1f}°", False),
        )
        x = self.width - 22
        y = best_rect.bottom + 8
        for text, hot in chips:
            y = self._draw_hud_chip(text, x, y, hot)

    def _draw_hud_chip(self, text: str, right: int, top: int, hot: bool) -> int:
        surface = self.hud_font.render(text, True, (17, 24, 39) if hot else (248, 250, 252))
        rect = surface.get_rect(topright=(right, top)).inflate(18, 12)
        fill = (245, 158, 11) if hot else (15, 23, 42)
        border = (251, 191, 36) if hot else (63, 70, 87)
        self.pygame.draw.rect(self.screen, fill, rect)
        self.pygame.draw.rect(self.screen, border, rect, 1)
        self.screen.blit(surface, (rect.x + 9, rect.y + 6))
        return rect.bottom + 8

    def _draw_challenge_badge(self, game: BalanceBallGame) -> None:
        if game.state == BalanceBallGame.RUNNING:
            label = "挑战中"
            color = (22, 163, 74)
        elif game.state == BalanceBallGame.GAME_OVER:
            label = "挑战结束"
            color = (220, 38, 38)
        else:
            label = "挑战未开始"
            color = (100, 116, 139)
        surface = self.font.render(label, True, (255, 255, 255))
        pad_x = 12
        pad_y = 6
        rect = surface.get_rect()
        rect.topright = (self.width - CHALLENGE_BADGE_TOPRIGHT[0], CHALLENGE_BADGE_TOPRIGHT[1])
        rect.inflate_ip(pad_x * 2, pad_y * 2)
        color = (245, 158, 11) if game.state == BalanceBallGame.RUNNING else color
        text_color = (17, 24, 39) if game.state == BalanceBallGame.RUNNING else (255, 255, 255)
        surface = self.font.render(label, True, text_color)
        self.pygame.draw.rect(self.screen, color, rect)
        self.pygame.draw.rect(self.screen, (63, 70, 87), rect, 1)
        self.screen.blit(surface, (rect.x + pad_x, rect.y + pad_y))

    def _draw_buttons(self) -> None:
        mouse_pos = self.pygame.mouse.get_pos()
        self._draw_button(self.restart_button_rect, "重启WS监听", "restart", mouse_pos)
        self._draw_button(self.prepare_button_rect, "重新准备机器狗", "prepare", mouse_pos)
        if self.feedback_message and time.monotonic() < self.feedback_until_s:
            self._draw_text(self.feedback_message, 28, BUTTON_ROW_TOP + 38, (245, 158, 11))

    def _draw_button(self, rect, label: str, button_id: str, mouse_pos: Tuple[int, int]) -> None:
        pg = self.pygame
        hovered = rect.collidepoint(mouse_pos)
        pressed = self.pressed_button == button_id
        draw_rect = rect.copy()
        top_fill = (31, 37, 50) if hovered else (10, 15, 25)
        bottom_fill = (20, 25, 36) if hovered else (10, 15, 25)
        border = (245, 158, 11) if hovered else (42, 49, 64)
        if pressed:
            draw_rect.move_ip(0, 2)
            top_fill = (245, 158, 11)
            bottom_fill = (217, 119, 6)
            border = (251, 191, 36)
        self._draw_gradient_rect(draw_rect, top_fill, bottom_fill, None, 6)
        pg.draw.rect(self.screen, border, draw_rect, 2 if hovered or pressed else 1, border_radius=6)
        surface = self.small_font.render(label, True, (17, 24, 39) if pressed else (248, 250, 252))
        self.screen.blit(
            surface,
            (
                draw_rect.centerx - surface.get_width() // 2,
                draw_rect.centery - surface.get_height() // 2,
            ),
        )

    def _draw_balance(self, game: BalanceBallGame) -> None:
        pg = self.pygame
        cx = self.width // 2
        cy = int(self.height * BALANCE_CENTER_Y_RATIO)
        beam_half = int(game.config.beam_half)
        angle = math.radians(game.lever_angle_deg)
        direction = (math.cos(angle), math.sin(angle))
        normal = (-math.sin(angle), math.cos(angle))
        p1 = (cx - direction[0] * beam_half, cy - direction[1] * beam_half)
        p2 = (cx + direction[0] * beam_half, cy + direction[1] * beam_half)
        pivot = [(cx, cy), (cx - PIVOT_HALF_WIDTH, cy + PIVOT_HEIGHT), (cx + PIVOT_HALF_WIDTH, cy + PIVOT_HEIGHT)]
        shadow_pivot = [(x, y + 10) for x, y in pivot]
        pg.draw.polygon(self.screen, (0, 0, 0), shadow_pivot)
        pg.draw.polygon(self.screen, (39, 39, 42), pivot)
        pg.draw.polygon(self.screen, (82, 82, 91), pivot, 2)
        glow = pg.Surface((self.width, self.height), pg.SRCALPHA)
        pg.draw.line(glow, (245, 158, 11, 90), p1, p2, 17)
        self.screen.blit(glow, (0, 0))
        pg.draw.line(self.screen, (248, 250, 252), p1, p2, 8)
        pg.draw.line(self.screen, (245, 158, 11), p1, p2, 2)
        self._draw_beam_zones(game, cx, cy, direction)
        self._draw_reward(game, cx, cy, direction, normal)

        ball_track = game.ball_x
        bx = cx + direction[0] * ball_track - normal[0] * (game.config.ball_radius + 5)
        by = cy + direction[1] * ball_track - normal[1] * (game.config.ball_radius + 5)
        radius = int(game.config.ball_radius)
        pg.draw.circle(self.screen, (0, 0, 0), (int(bx + 4), int(by + 8)), radius)
        pg.draw.circle(self.screen, (248, 250, 252), (int(bx), int(by)), radius)
        pg.draw.circle(self.screen, (24, 24, 27), (int(bx), int(by)), radius, 2)
        self._draw_ball_logo(game, bx, by)

    def _draw_ball_logo(self, game: BalanceBallGame, bx: float, by: float) -> None:
        if self.gogo_logo is None:
            return
        logo_width = max(16, int(game.config.ball_radius * 1.42))
        logo_height = max(1, int(logo_width * self.gogo_logo.get_height() / self.gogo_logo.get_width()))
        logo = self.pygame.transform.smoothscale(self.gogo_logo, (logo_width, logo_height))
        rotation_deg = -math.degrees(game.ball_x / max(1.0, game.config.ball_radius))
        logo = self.pygame.transform.rotozoom(logo, rotation_deg, 1.0)
        logo_rect = logo.get_rect(center=(int(bx), int(by)))
        self.screen.blit(logo, logo_rect)

    def _draw_beam_zones(
        self,
        game: BalanceBallGame,
        cx: int,
        cy: int,
        direction: Tuple[float, float],
    ) -> None:
        cfg = game.config
        high_start = cfg.beam_half * cfg.high_score_zone_ratio
        danger_start = cfg.beam_half * cfg.danger_zone_ratio
        zones = (
            (-cfg.beam_half, -danger_start, (239, 68, 68), 9),
            (danger_start, cfg.beam_half, (239, 68, 68), 9),
            (-danger_start, -high_start, (245, 158, 11), 10),
            (high_start, danger_start, (245, 158, 11), 10),
        )
        for start, end, color, width in zones:
            p1 = (cx + direction[0] * start, cy + direction[1] * start)
            p2 = (cx + direction[0] * end, cy + direction[1] * end)
            self.pygame.draw.line(self.screen, color, p1, p2, width)

    def _draw_reward(
        self,
        game: BalanceBallGame,
        cx: int,
        cy: int,
        direction: Tuple[float, float],
        normal: Tuple[float, float],
    ) -> None:
        if not game.reward_visible:
            return
        rx = cx + direction[0] * game.reward_x - normal[0] * (game.config.reward_radius + 6)
        ry = cy + direction[1] * game.reward_x - normal[1] * (game.config.reward_radius + 6)
        pg = self.pygame
        x = int(rx)
        y = int(ry)
        r = int(game.config.reward_radius)
        food = game.reward_food
        reward_glow = pg.Surface((r * 5, r * 5), pg.SRCALPHA)
        pg.draw.circle(reward_glow, (245, 158, 11, 95), (r * 2, r * 2), r * 2)
        self.screen.blit(reward_glow, (x - r * 2, y - r * 2))
        if food == "apple":
            pg.draw.circle(self.screen, (239, 68, 68), (x, y + 1), r)
            pg.draw.circle(self.screen, (254, 202, 202), (x - 4, y - 4), 3)
            pg.draw.line(self.screen, (120, 53, 15), (x, y - r), (x + 3, y - r - 6), 3)
            pg.draw.ellipse(self.screen, (34, 197, 94), (x + 2, y - r - 8, 10, 7))
        elif food == "banana":
            arc_rect = (x - r - 3, y - r, (r + 3) * 2, r * 2)
            pg.draw.arc(self.screen, (245, 158, 11), arc_rect, 0.2, 3.9, 8)
            pg.draw.arc(self.screen, (253, 224, 71), arc_rect, 0.3, 3.7, 4)
        elif food == "carrot":
            points = [(x - r, y - 2), (x + r, y - 7), (x - 2, y + r + 3)]
            pg.draw.polygon(self.screen, (249, 115, 22), points)
            pg.draw.polygon(self.screen, (22, 163, 74), [(x + 7, y - 8), (x + 16, y - 18), (x + 12, y - 5)])
        elif food == "pumpkin":
            pg.draw.circle(self.screen, (249, 115, 22), (x, y), r)
            pg.draw.circle(self.screen, (254, 215, 170), (x - 4, y - 4), 3)
            pg.draw.arc(self.screen, (194, 65, 12), (x - r, y - r, r * 2, r * 2), -1.2, 1.2, 2)
            pg.draw.arc(self.screen, (194, 65, 12), (x - r // 2, y - r, r, r * 2), -1.4, 1.4, 2)
            pg.draw.line(self.screen, (101, 67, 33), (x, y - r), (x + 2, y - r - 6), 3)
        elif food == "chicken":
            pg.draw.circle(self.screen, (251, 146, 60), (x - 3, y), r)
            pg.draw.circle(self.screen, (254, 226, 226), (x + r - 2, y - 4), 5)
            pg.draw.circle(self.screen, (254, 226, 226), (x + r + 2, y + 4), 5)
            pg.draw.line(self.screen, (180, 83, 9), (x + 4, y), (x + r + 4, y), 4)
        elif food == "cheese":
            points = [(x - r, y + r), (x + r + 2, y), (x - r, y - r)]
            pg.draw.polygon(self.screen, (250, 204, 21), points)
            for hx, hy in ((x - 4, y - 3), (x, y + 5), (x + 6, y)):
                pg.draw.circle(self.screen, (202, 138, 4), (hx, hy), 2)
        else:
            rect = pg.Rect(x - r, y - r, r * 2, r * 2)
            pg.draw.rect(self.screen, (180, 120, 70), rect, border_radius=6)
            pg.draw.circle(self.screen, (120, 76, 36), (x - 4, y - 2), 2)
            pg.draw.circle(self.screen, (120, 76, 36), (x + 4, y + 3), 2)

    def _draw_celebration(self) -> None:
        now_s = time.monotonic()
        next_particles: list[CelebrationParticle] = []
        for particle in self.particles:
            dt = 1.0 / 60.0
            particle.life_s -= dt
            if particle.life_s <= 0:
                continue
            particle.vy += 180.0 * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            next_particles.append(particle)
            radius = max(2, int(6 * min(1.0, particle.life_s)))
            self.pygame.draw.circle(self.screen, particle.color, (int(particle.x), int(particle.y)), radius)
        self.particles = next_particles
        if self.celebration_label and now_s < self.celebration_until_s:
            surface = self.title_font.render(self.celebration_label.upper(), True, (248, 250, 252))
            x = (self.width - surface.get_width()) // 2
            y = 112
            glow = self.title_font.render(self.celebration_label.upper(), True, (245, 158, 11))
            self.screen.blit(glow, (x + 2, y + 2))
            self.screen.blit(surface, (x, y))
            sub = self.font.render("SNACK BONUS", True, (245, 158, 11))
            self.screen.blit(sub, ((self.width - sub.get_width()) // 2, y + surface.get_height() + 2))

    def _draw_state(self, game: BalanceBallGame) -> None:
        messages = {
            BalanceBallGame.WAIT_IMU: "等待 IMU / WebSocket 连接",
            BalanceBallGame.CALIBRATING: "校准中，请保持当前姿态",
            BalanceBallGame.READY: "按空格开始，按 R 重新校准",
            BalanceBallGame.RUNNING: "",
            BalanceBallGame.GAME_OVER: f"挑战结束，本局 {int(game.score)} 分，按空格重来",
        }
        msg = messages.get(game.state, "")
        if not msg:
            return
        surface = self.font.render(msg, True, (248, 250, 252))
        rect = surface.get_rect(midbottom=(self.width // 2, self.height - 24)).inflate(22, 12)
        self.pygame.draw.rect(self.screen, (15, 23, 42), rect)
        self.pygame.draw.rect(self.screen, (245, 158, 11), rect, 1)
        self.screen.blit(surface, (rect.x + 11, rect.y + 6))

    def _draw_text(self, text: str, x: int, y: int, color: Tuple[int, int, int]) -> None:
        surface = self.font.render(text, True, color)
        self.screen.blit(surface, (x, y))


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))


def build_reader(args: argparse.Namespace, latest_roll: LatestRoll):
    if args.transport == "ws":
        return WsImuReader(
            latest_roll,
            args.bind,
            args.port,
            args.hz,
            args.connect_timeout,
            not args.no_prepare_robot,
            not args.no_restore_special_detection,
            args.pose_action,
        )
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
    parser.add_argument("--dog-facing", choices=("user", "away"), default="user")
    parser.add_argument("--invert-roll", action="store_true")
    parser.add_argument("--sensitivity", type=float, default=1.0)
    parser.add_argument("--max-angle", type=float, default=18.0)
    parser.add_argument("--score-file", type=Path, default=DEFAULT_SCORE_FILE)
    parser.add_argument("--pose-action", default=GAME_POSE_ACTION)
    parser.add_argument("--no-prepare-robot", action="store_true")
    parser.add_argument("--no-restore-special-detection", action="store_true")
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
    invert_roll = (args.dog_facing == "user") ^ bool(args.invert_roll)
    roll_filter = RollFilter(
        RollFilterConfig(
            sensitivity=args.sensitivity,
            max_angle_deg=args.max_angle,
            invert=invert_roll,
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
    handled_reward_event_id = 0
    handled_milestone_event_id = 0
    last_game_state = game.state
    danger_feedback_active = False

    def run_reader_action_async(action_name: str) -> None:
        action = getattr(reader, action_name, None)
        if not callable(action):
            return
        threading.Thread(target=action, daemon=True, name=f"aidog-balance-{action_name}").start()

    try:
        while running:
            now_s = time.monotonic()
            dt_s = now_s - last_s
            last_s = now_s

            if isinstance(reader, KeyboardRollReader):
                reader.update(pg.key.get_pressed(), pg)

            mouse_pos = pg.mouse.get_pos()
            mouse_over_button = (
                renderer.restart_button_rect.collidepoint(mouse_pos)
                or renderer.prepare_button_rect.collidepoint(mouse_pos)
            )
            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_HAND if mouse_over_button else pg.SYSTEM_CURSOR_ARROW)

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
                elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                    if renderer.restart_button_rect.collidepoint(event.pos):
                        renderer.pressed_button = "restart"
                    elif renderer.prepare_button_rect.collidepoint(event.pos):
                        renderer.pressed_button = "prepare"
                elif event.type == pg.MOUSEBUTTONUP and event.button == 1:
                    pressed = renderer.pressed_button
                    renderer.pressed_button = None
                    if pressed == "restart" and renderer.restart_button_rect.collidepoint(event.pos):
                        run_reader_action_async("restart")
                        renderer.set_button_feedback("已重启 WS 监听", now_s)
                        game.state = BalanceBallGame.WAIT_IMU
                    elif pressed == "prepare" and renderer.prepare_button_rect.collidepoint(event.pos):
                        run_reader_action_async("prepare_now")
                        renderer.set_button_feedback("已重新发送准备指令", now_s)

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
            if game.reward_event_id > handled_reward_event_id:
                handled_reward_event_id = game.reward_event_id
                run_reader_action_async("play_reward_feedback")
            elif game.reward_event_id < handled_reward_event_id:
                handled_reward_event_id = game.reward_event_id
            if game.milestone_event_id > handled_milestone_event_id:
                handled_milestone_event_id = game.milestone_event_id
                renderer.celebrate(game.milestone_label, now_s)
            elif game.milestone_event_id < handled_milestone_event_id:
                handled_milestone_event_id = game.milestone_event_id
            if last_game_state != game.state:
                if game.state == BalanceBallGame.RUNNING:
                    run_reader_action_async("play_challenge_start_feedback")
                elif game.state == BalanceBallGame.GAME_OVER:
                    run_reader_action_async("play_challenge_finish_feedback")
                last_game_state = game.state
            danger_active = (
                game.state == BalanceBallGame.RUNNING
                and game.edge_ratio >= game.config.danger_zone_ratio
            )
            if danger_active and not danger_feedback_active:
                run_reader_action_async("play_danger_feedback")
            danger_feedback_active = danger_active
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
