"""Pygame renderer for the AIDog IMU balance ball game."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from .core import BalanceBallGame


GAME_ROOT = Path(__file__).resolve().parents[1]
GAME_ASSET_DIR = GAME_ROOT / "icons"
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
