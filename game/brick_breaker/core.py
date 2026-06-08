"""Pure rules for the GOGO IMU brick breaker game."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


WAIT_IMU = "WAIT_IMU"
CALIBRATING = "CALIBRATING"
READY = "READY"
RUNNING = "RUNNING"
LEVEL_CLEAR = "LEVEL_CLEAR"
GAME_OVER = "GAME_OVER"


@dataclass
class Vec2:
    x: float
    y: float


@dataclass
class Rect:
    x: float
    y: float
    w: float
    h: float

    def intersects_circle(self, center: Vec2, radius: float) -> bool:
        nearest_x = clamp(center.x, self.x, self.x + self.w)
        nearest_y = clamp(center.y, self.y, self.y + self.h)
        dx = center.x - nearest_x
        dy = center.y - nearest_y
        return dx * dx + dy * dy <= radius * radius


@dataclass
class Brick:
    rect: Rect
    kind: str = "normal"
    alive: bool = True


@dataclass
class Ball:
    pos: Vec2
    velocity: Vec2
    active: bool = True


@dataclass
class BrickBreakerConfig:
    width: int = 960
    height: int = 540
    brick_cols: int = 16
    brick_rows: int = 3
    brick_size: float = 24.0
    brick_gap: float = 5.0
    brick_top: float = 76.0
    paddle_width: float = 126.0
    paddle_height: float = 12.0
    paddle_bottom: float = 62.0
    ball_radius: float = 9.0
    ball_speed: float = 330.0
    max_bounce_angle_deg: float = 60.0
    brick_score: int = 10
    special_brick_score: int = 30
    special_bricks_per_level: int = 4
    level_speed_bonus: float = 24.0
    ready_delay_s: float = 0.6
    score_celebrations: Tuple[Tuple[int, str], ...] = ((100, "Nice!"), (300, "Excellent!"), (500, "Amazing!"))


class BrickBreakerGame:
    def __init__(self, config: BrickBreakerConfig, high_score: int = 0) -> None:
        self.config = config
        self.high_score = max(0, int(high_score))
        self.state = WAIT_IMU
        self.score = 0
        self.level = 1
        self.elapsed_s = 0.0
        self.paddle = Rect(0.0, 0.0, config.paddle_width, config.paddle_height)
        self.balls: List[Ball] = []
        self.bricks: List[Brick] = []
        self.hit_event_id = 0
        self.multiball_event_id = 0
        self.fruit_event_id = 0
        self.level_clear_event_id = 0
        self.score_celebration_event_id = 0
        self.score_celebration_label = ""
        self._celebrated_score_targets: set[int] = set()
        self.new_high_score = False
        self.reset_round()

    def has_valid_imu(self, latest_time_s: float, now_s: float) -> bool:
        return latest_time_s > 0.0 and now_s - latest_time_s < 1.2

    def enter_wait_imu(self) -> None:
        self.state = WAIT_IMU

    def start_calibration(self) -> None:
        self.state = CALIBRATING
        self.reset_round()

    def ready(self) -> None:
        self.state = READY
        self.reset_round()

    def start_running(self) -> None:
        if self.state == READY:
            self.state = RUNNING

    def start_next_level(self) -> None:
        if self.state != LEVEL_CLEAR:
            return
        self.level += 1
        self.elapsed_s = 0.0
        self.state = RUNNING
        self.balls = [self._make_start_ball()]
        self.bricks = self._build_bricks()
        self._normalize_ball_speed(self.balls[0], self.config.ball_speed + self.config.level_speed_bonus * (self.level - 1))

    def reset_round(self) -> None:
        cfg = self.config
        self.score = 0
        self.elapsed_s = 0.0
        self.new_high_score = False
        self.score_celebration_label = ""
        self._celebrated_score_targets.clear()
        self.paddle.x = (cfg.width - cfg.paddle_width) * 0.5
        self.paddle.y = cfg.height - cfg.paddle_bottom
        self.balls = [self._make_start_ball()]
        self.bricks = self._build_bricks()

    def update(self, dt_s: float, paddle_center_x: float) -> None:
        self._move_paddle(paddle_center_x)
        if self.state != RUNNING:
            self._park_ball_on_paddle()
            return

        dt = clamp(dt_s, 0.0, 0.05)
        self.elapsed_s += dt
        if self.elapsed_s < self.config.ready_delay_s:
            self._park_ball_on_paddle()
            return

        for ball in list(self.balls):
            if not ball.active:
                continue
            ball.pos.x += ball.velocity.x * dt
            ball.pos.y += ball.velocity.y * dt
            self._collide_walls(ball)
            self._collide_paddle(ball)
            self._collide_bricks(ball)
            if ball.pos.y - self.config.ball_radius > self.config.height:
                ball.active = False
        self.balls = [ball for ball in self.balls if ball.active]
        if not self.balls:
            self._finish_round()

    def remaining_bricks(self) -> int:
        return sum(1 for brick in self.bricks if brick.alive)

    @property
    def paddle_center_x(self) -> float:
        return self.paddle.x + self.paddle.w * 0.5

    @property
    def ball(self) -> Vec2:
        return self.balls[0].pos

    @property
    def ball_velocity(self) -> Vec2:
        return self.balls[0].velocity

    def _move_paddle(self, center_x: float) -> None:
        cfg = self.config
        half = cfg.paddle_width * 0.5
        self.paddle.x = clamp(center_x - half, 0.0, cfg.width - cfg.paddle_width)

    def _park_ball_on_paddle(self) -> None:
        if not self.balls:
            self.balls = [self._make_start_ball()]
        self.balls = [self.balls[0]]
        self.ball.x = self.paddle_center_x
        self.ball.y = self.paddle.y - self.config.ball_radius - 1.0

    def _collide_walls(self, ball: Ball) -> None:
        radius = self.config.ball_radius
        if ball.pos.x - radius < 0.0:
            ball.pos.x = radius
            ball.velocity.x = abs(ball.velocity.x)
        elif ball.pos.x + radius > self.config.width:
            ball.pos.x = self.config.width - radius
            ball.velocity.x = -abs(ball.velocity.x)
        if ball.pos.y - radius < 0.0:
            ball.pos.y = radius
            ball.velocity.y = abs(ball.velocity.y)

    def _collide_paddle(self, ball: Ball) -> None:
        if ball.velocity.y <= 0.0:
            return
        if not self.paddle.intersects_circle(ball.pos, self.config.ball_radius):
            return
        cfg = self.config
        hit_offset = (ball.pos.x - self.paddle_center_x) / max(1.0, cfg.paddle_width * 0.5)
        hit_offset = clamp(hit_offset, -1.0, 1.0)
        angle = math.radians(hit_offset * cfg.max_bounce_angle_deg)
        speed = self._ball_speed(ball)
        ball.velocity.x = speed * math.sin(angle)
        ball.velocity.y = -abs(speed * math.cos(angle))
        ball.pos.y = self.paddle.y - cfg.ball_radius - 0.5

    def _collide_bricks(self, ball: Ball) -> None:
        hit_brick = self._first_hit_brick(ball)
        if hit_brick is None:
            return
        hit_brick.alive = False
        self.score += self.config.special_brick_score if hit_brick.kind == "special" else self.config.brick_score
        self.hit_event_id += 1
        self._update_score_celebration()
        ball.velocity.y = -ball.velocity.y
        if hit_brick.kind == "special":
            self.fruit_event_id += 1
            self._spawn_extra_ball(ball)
        if self.remaining_bricks() == 0:
            self.state = LEVEL_CLEAR
            self.level_clear_event_id += 1

    def _first_hit_brick(self, ball: Ball) -> Optional[Brick]:
        for brick in self.bricks:
            if brick.alive and brick.rect.intersects_circle(ball.pos, self.config.ball_radius):
                return brick
        return None

    def _finish_round(self) -> None:
        self.state = GAME_OVER
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_high_score = True

    def _ball_speed(self, ball: Ball) -> float:
        return math.hypot(ball.velocity.x, ball.velocity.y)

    def _normalize_ball_speed(self, ball: Ball, speed: float) -> None:
        current = self._ball_speed(ball)
        if current <= 0.0:
            ball.velocity.x = speed * 0.36
            ball.velocity.y = -speed
            return
        scale = speed / current
        ball.velocity.x *= scale
        ball.velocity.y *= scale

    def _make_start_ball(self) -> Ball:
        cfg = self.config
        return Ball(
            Vec2(cfg.width * 0.5, cfg.height - cfg.paddle_bottom - cfg.ball_radius - 1.0),
            Vec2(cfg.ball_speed * 0.36, -cfg.ball_speed),
        )

    def _spawn_extra_ball(self, source_ball: Ball) -> None:
        speed = self.config.ball_speed * 0.5
        direction = -1.0 if source_ball.velocity.x >= 0.0 else 1.0
        angle = math.radians(34.0 * direction)
        self.balls.append(
            Ball(
                Vec2(source_ball.pos.x, source_ball.pos.y),
                Vec2(speed * math.sin(angle), -abs(speed * math.cos(angle))),
            )
        )
        self.multiball_event_id += 1

    def _update_score_celebration(self) -> None:
        for target, label in self.config.score_celebrations:
            if self.score >= target and target not in self._celebrated_score_targets:
                self._celebrated_score_targets.add(target)
                self.score_celebration_label = label
                self.score_celebration_event_id += 1

    def _build_bricks(self) -> List[Brick]:
        cfg = self.config
        total_w = cfg.brick_cols * cfg.brick_size + (cfg.brick_cols - 1) * cfg.brick_gap
        left = (cfg.width - total_w) * 0.5
        bricks: List[Brick] = []
        special_indexes = self._special_brick_indexes()
        for row in range(cfg.brick_rows):
            y = cfg.brick_top + row * (cfg.brick_size + cfg.brick_gap)
            for col in range(cfg.brick_cols):
                x = left + col * (cfg.brick_size + cfg.brick_gap)
                index = row * cfg.brick_cols + col
                kind = "special" if index in special_indexes else "normal"
                bricks.append(Brick(Rect(x, y, cfg.brick_size, cfg.brick_size), kind))
        return bricks

    def _special_brick_indexes(self) -> set[int]:
        cfg = self.config
        total = cfg.brick_cols * cfg.brick_rows
        count = min(max(0, cfg.special_bricks_per_level), total)
        if count == 0:
            return set()
        middle_row = cfg.brick_rows // 2
        candidates = [
            middle_row * cfg.brick_cols + cfg.brick_cols // 4,
            middle_row * cfg.brick_cols + cfg.brick_cols // 2,
            middle_row * cfg.brick_cols + (cfg.brick_cols * 3) // 4,
            (cfg.brick_rows - 1) * cfg.brick_cols + cfg.brick_cols // 2,
        ]
        return set(candidates[:count])


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))
