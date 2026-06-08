"""Pure rules for the GOGO IMU brick breaker game."""

from __future__ import annotations

import math
from dataclasses import dataclass
import random
from typing import List, Optional, Tuple


WAIT_IMU = "WAIT_IMU"
CALIBRATING = "CALIBRATING"
READY = "READY"
RUNNING = "RUNNING"
LEVEL_CLEAR = "LEVEL_CLEAR"
CHALLENGE_CLEAR = "CHALLENGE_CLEAR"
GAME_OVER = "GAME_OVER"

DEFAULT_LEVEL_LAYOUTS: Tuple[Tuple[str, ...], ...] = (
    (
        "XXXXXXXXXXXXXXXX",
        "XXXGXXXXHXXXXGXX",
        "XXXXXXXXXXXXXXXX",
    ),
    (
        "..XXXXXX..XXXX..",
        ".XXXGXXXXHXXXG..",
        "XXXX..XXXX..XXXX",
        "..XX..XXXX..XX..",
    ),
    (
        "....XXXXXXXX....",
        "..XXXXHGGHXXXX..",
        ".XXX..XXXX..XXX.",
        "..XXXXHGGHXXXX..",
        "....XXXXXXXX....",
    ),
)
DEFAULT_STONE_LAYOUTS: Tuple[str, ...] = (
    "SSSSSSSSSSSS......SSSSSSSSSSSS",
    "SSSSSSSSSSS.......SSSSSSSSSSSS",
    "SSSSSSSSS....SSSS....SSSSSSSSS",
)
FRUIT_TYPES: Tuple[str, ...] = ("apple", "banana", "carrot", "pumpkin", "chicken", "biscuit", "cheese")


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
class FruitDrop:
    pos: Vec2
    kind: str = "apple"
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
    stone_top: float = 230.0
    paddle_width: float = 126.0
    paddle_height: float = 12.0
    paddle_bottom: float = 62.0
    ball_radius: float = 9.0
    fruit_radius: float = 12.0
    fruit_drop_speed: float = 145.0
    ball_speed: float = 330.0
    initial_lives: int = 3
    max_balls: int = 8
    split_chances: Tuple[float, ...] = (0.5, 0.6, 0.75)
    max_bounce_angle_deg: float = 60.0
    brick_score: int = 10
    special_brick_score: int = 30
    special_bricks_per_level: int = 4
    level_speed_bonus: float = 24.0
    ready_delay_s: float = 0.6
    score_celebrations: Tuple[Tuple[int, str], ...] = ((100, "Nice!"), (300, "Excellent!"), (500, "Amazing!"))
    level_layouts: Tuple[Tuple[str, ...], ...] = DEFAULT_LEVEL_LAYOUTS
    stone_layouts: Tuple[str, ...] = DEFAULT_STONE_LAYOUTS


class BrickBreakerGame:
    def __init__(self, config: BrickBreakerConfig, high_score: int = 0) -> None:
        self.config = config
        self.high_score = max(0, int(high_score))
        self.state = WAIT_IMU
        self.score = 0
        self.level = 1
        self.lives = max(1, int(config.initial_lives))
        self.elapsed_s = 0.0
        self.paddle = Rect(0.0, 0.0, config.paddle_width, config.paddle_height)
        self.balls: List[Ball] = []
        self.bricks: List[Brick] = []
        self.stones: List[Rect] = []
        self.fruits: List[FruitDrop] = []
        self.hit_event_id = 0
        self.multiball_event_id = 0
        self.fruit_event_id = 0
        self.fruit_collect_event_id = 0
        self.level_clear_event_id = 0
        self.challenge_clear_event_id = 0
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
        self.stones = self._build_stones()
        self.fruits = []
        self._normalize_ball_speed(self.balls[0], self._level_ball_speed())

    def reset_round(self) -> None:
        cfg = self.config
        self.score = 0
        self.level = 1
        self.lives = max(1, int(cfg.initial_lives))
        self.elapsed_s = 0.0
        self.new_high_score = False
        self.score_celebration_label = ""
        self._celebrated_score_targets.clear()
        self.paddle.x = (cfg.width - cfg.paddle_width) * 0.5
        self.paddle.y = cfg.height - cfg.paddle_bottom
        self.balls = [self._make_start_ball()]
        self.bricks = self._build_bricks()
        self.stones = self._build_stones()
        self.fruits = []

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
            self._collide_stones(ball)
            self._collide_bricks(ball)
            if ball.pos.y - self.config.ball_radius > self.config.height:
                ball.active = False
        self.balls = [ball for ball in self.balls if ball.active]
        self._update_fruits(dt)
        if not self.balls:
            self._handle_all_balls_lost()

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
        self._maybe_split_ball(ball)
        if hit_brick.kind == "special":
            self.fruit_event_id += 1
            self._spawn_fruit(hit_brick)
        if self.remaining_bricks() == 0:
            self.fruits = []
            if self.level >= self.max_level:
                self._finish_round(CHALLENGE_CLEAR)
            else:
                self.state = LEVEL_CLEAR
                self.level_clear_event_id += 1

    def _first_hit_brick(self, ball: Ball) -> Optional[Brick]:
        for brick in self.bricks:
            if brick.alive and brick.rect.intersects_circle(ball.pos, self.config.ball_radius):
                return brick
        return None

    def _collide_stones(self, ball: Ball) -> None:
        for stone in self.stones:
            if not stone.intersects_circle(ball.pos, self.config.ball_radius):
                continue
            if ball.velocity.y > 0.0:
                ball.pos.y = stone.y - self.config.ball_radius - 0.5
                ball.velocity.y = -abs(ball.velocity.y)
            elif ball.velocity.y < 0.0:
                ball.pos.y = stone.y + stone.h + self.config.ball_radius + 0.5
                ball.velocity.y = abs(ball.velocity.y)
            else:
                ball.velocity.x = -ball.velocity.x
            return

    def _finish_round(self, state: str = GAME_OVER) -> None:
        self.state = state
        if state == CHALLENGE_CLEAR:
            self.challenge_clear_event_id += 1
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_high_score = True

    def _handle_all_balls_lost(self) -> None:
        self.lives -= 1
        if self.lives <= 0:
            self._finish_round()
            return
        self.balls = [self._make_start_ball()]
        self.fruits = []
        self.elapsed_s = 0.0

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
            True,
        )

    def _spawn_extra_ball(self, source_ball: Ball) -> None:
        if len(self.balls) >= self.config.max_balls:
            return
        speed = self._level_ball_speed()
        direction = -1.0 if source_ball.velocity.x >= 0.0 else 1.0
        angle = math.radians(34.0 * direction)
        self.balls.append(
            Ball(
                Vec2(source_ball.pos.x, source_ball.pos.y),
                Vec2(speed * math.sin(angle), -abs(speed * math.cos(angle))),
                True,
            )
        )
        self.multiball_event_id += 1

    def _spawn_extra_balls(self, source_ball: Ball, count: int) -> None:
        for i in range(count):
            if len(self.balls) >= self.config.max_balls:
                return
            direction = -1.0 if i % 2 == 0 else 1.0
            self._spawn_extra_ball_with_direction(source_ball, direction)

    def _spawn_extra_ball_with_direction(self, source_ball: Ball, direction: float) -> None:
        if len(self.balls) >= self.config.max_balls:
            return
        speed = self._level_ball_speed()
        angle = math.radians(34.0 * direction)
        self.balls.append(
            Ball(
                Vec2(source_ball.pos.x, source_ball.pos.y),
                Vec2(speed * math.sin(angle), -abs(speed * math.cos(angle))),
                True,
            )
        )
        self.multiball_event_id += 1

    def _maybe_split_ball(self, source_ball: Ball) -> None:
        if random.random() <= self._split_chance():
            self._spawn_extra_ball(source_ball)

    def _spawn_fruit(self, brick: Brick) -> None:
        self.fruits.append(
            FruitDrop(
                Vec2(brick.rect.x + brick.rect.w * 0.5, brick.rect.y + brick.rect.h * 0.5),
                random.choice(FRUIT_TYPES),
            )
        )

    def _update_fruits(self, dt: float) -> None:
        for fruit in self.fruits:
            if not fruit.active:
                continue
            fruit.pos.y += self.config.fruit_drop_speed * dt
            if self._fruit_hits_paddle(fruit):
                fruit.active = False
                self.fruit_collect_event_id += 1
                if self.balls:
                    self._spawn_extra_balls(self.balls[0], 2)
            elif fruit.pos.y - self.config.fruit_radius > self.config.height:
                fruit.active = False
        self.fruits = [fruit for fruit in self.fruits if fruit.active]

    def _fruit_hits_paddle(self, fruit: FruitDrop) -> bool:
        return self.paddle.intersects_circle(fruit.pos, self.config.fruit_radius)

    def _update_score_celebration(self) -> None:
        for target, label in self.config.score_celebrations:
            if self.score >= target and target not in self._celebrated_score_targets:
                self._celebrated_score_targets.add(target)
                self.score_celebration_label = label
                self.score_celebration_event_id += 1

    def _build_bricks(self) -> List[Brick]:
        cfg = self.config
        layout = self._level_layout()
        cols = max((len(row) for row in layout), default=0)
        total_w = cols * cfg.brick_size + max(0, cols - 1) * cfg.brick_gap
        left = (cfg.width - total_w) * 0.5
        bricks: List[Brick] = []
        for row, tokens in enumerate(layout):
            y = cfg.brick_top + row * (cfg.brick_size + cfg.brick_gap)
            for col, token in enumerate(tokens):
                if token == ".":
                    continue
                x = left + col * (cfg.brick_size + cfg.brick_gap)
                kind = "special" if token == "G" else "normal"
                bricks.append(Brick(Rect(x, y, cfg.brick_size, cfg.brick_size), kind))
        return bricks

    def _build_stones(self) -> List[Rect]:
        cfg = self.config
        layout = self._stone_layout()
        cols = len(layout)
        total_w = cols * cfg.brick_size + max(0, cols - 1) * cfg.brick_gap
        left = (cfg.width - total_w) * 0.5
        stones: List[Rect] = []
        for col, token in enumerate(layout):
            if token != "S":
                continue
            x = left + col * (cfg.brick_size + cfg.brick_gap)
            stones.append(Rect(x, cfg.stone_top, cfg.brick_size, cfg.brick_size))
        return stones

    @property
    def max_level(self) -> int:
        return max(1, len(self.config.level_layouts))

    def _level_layout(self) -> Tuple[str, ...]:
        layouts = self.config.level_layouts or DEFAULT_LEVEL_LAYOUTS
        index = max(0, min(self.level - 1, len(layouts) - 1))
        return layouts[index]

    def _stone_layout(self) -> str:
        layouts = self.config.stone_layouts or DEFAULT_STONE_LAYOUTS
        index = max(0, min(self.level - 1, len(layouts) - 1))
        return layouts[index]

    def _level_ball_speed(self) -> float:
        return self.config.ball_speed + self.config.level_speed_bonus * (self.level - 1)

    def _split_chance(self) -> float:
        chances = self.config.split_chances
        if not chances:
            return 0.0
        index = max(0, min(self.level - 1, len(chances) - 1))
        return clamp(chances[index], 0.0, 1.0)


def clamp(value: float, low: float, high: float) -> float:
    return min(max(float(value), float(low)), float(high))
