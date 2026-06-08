"""Pygame renderer for the GOGO IMU brick breaker game."""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Optional, Tuple

from .core import CALIBRATING, CHALLENGE_CLEAR, GAME_OVER, LEVEL_CLEAR, READY, RUNNING, WAIT_IMU, BrickBreakerGame


@dataclass
class CelebrationParticle:
    x: float
    y: float
    vx: float
    vy: float
    life_s: float
    color: Tuple[int, int, int]


class PygameRenderer:
    def __init__(self, width: int, height: int) -> None:
        import pygame

        pygame.init()
        pygame.display.set_caption("GOGO IMU Brick Breaker")
        self.pygame = pygame
        self.width = int(width)
        self.height = int(height)
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Microsoft YaHei", 18)
        self.small_font = pygame.font.SysFont("Microsoft YaHei", 14)
        self.score_font = pygame.font.SysFont("Segoe UI", 34, bold=True)
        self.title_font = pygame.font.SysFont("Segoe UI", 28, bold=True)
        self.restart_button_rect = pygame.Rect(28, 128, 132, 30)
        self.prepare_button_rect = pygame.Rect(28, 168, 160, 30)
        self.pressed_button: Optional[str] = None
        self.feedback_message = ""
        self.feedback_until_s = 0.0
        self.celebration_label = ""
        self.celebration_until_s = 0.0
        self.particles: list[CelebrationParticle] = []

    def tick(self, fps: int) -> None:
        self.clock.tick(int(fps))

    def set_button_feedback(self, message: str, now_s: float) -> None:
        self.feedback_message = str(message)
        self.feedback_until_s = now_s + 1.2

    def celebrate(self, label: str, now_s: float) -> None:
        self.celebration_label = str(label)
        self.celebration_until_s = now_s + 1.6
        cx = self.width / 2
        cy = self.height * 0.25
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
                    random.uniform(0.65, 1.2),
                    random.choice(colors),
                )
            )

    def draw(self, game: BrickBreakerGame, roll_deg: float, imu_ok: bool) -> None:
        self._draw_background()
        self._draw_hud(game, imu_ok)
        self._draw_buttons(game)
        self._draw_bricks(game)
        self._draw_stones(game)
        self._draw_arena_line()
        self._draw_fruits(game)
        self._draw_balls(game)
        self._draw_paddle(game)
        self._draw_roll_bar(roll_deg)
        self._draw_celebration()
        self._draw_state(game)
        self.pygame.display.flip()

    def _draw_background(self) -> None:
        pg = self.pygame
        self.screen.fill((5, 7, 15))
        for y in range(0, self.height, 18):
            color = (10, 20, 42) if y % 36 else (14, 28, 55)
            pg.draw.line(self.screen, color, (0, y), (self.width, y), 1)
        for x in range(0, self.width, 42):
            pg.draw.line(self.screen, (7, 17, 34), (x, 0), (x, self.height), 1)
        scan = pg.Surface((self.width, self.height), pg.SRCALPHA)
        points = [
            (int(self.width * 0.42), 0),
            (int(self.width * 0.50), 0),
            (int(self.width * 0.70), self.height),
            (int(self.width * 0.61), self.height),
        ]
        pg.draw.polygon(scan, (34, 211, 238, 18), points)
        self.screen.blit(scan, (0, 0))

    def _draw_hud(self, game: BrickBreakerGame, imu_ok: bool) -> None:
        self._draw_label("SCORE", 28, 24)
        score = self.score_font.render(f"{game.score:04d}", True, (248, 250, 252))
        self.screen.blit(score, (28, 42))
        self._draw_lives(game)
        best = self.small_font.render(f"历史最高分：{game.high_score}", True, (254, 243, 199))
        self.screen.blit(best, (self.width - best.get_width() - 28, 30))
        link_text = "LINK OK" if imu_ok else "WAIT IMU"
        link_color = (52, 211, 153) if imu_ok else (251, 113, 133)
        link = self.small_font.render(link_text, True, link_color)
        self.screen.blit(link, (self.width - link.get_width() - 28, 54))
        level = self.small_font.render(f"LEVEL {game.level:02d}", True, (191, 219, 254))
        self.screen.blit(level, (self.width - level.get_width() - 28, 78))

    def _draw_lives(self, game: BrickBreakerGame) -> None:
        pg = self.pygame
        x = 28
        y = 88
        label = self.small_font.render(f"生命值 {game.lives}/{game.config.initial_lives}", True, (203, 213, 225))
        self.screen.blit(label, (28, 82))
        for index in range(max(1, game.config.initial_lives)):
            rect = pg.Rect(x + index * 18, y + 20, 12, 12)
            fill = (251, 191, 36) if index < game.lives else (30, 41, 59)
            border = (254, 243, 199) if index < game.lives else (71, 85, 105)
            pg.draw.rect(self.screen, fill, rect, border_radius=2)
            pg.draw.rect(self.screen, border, rect, 1, border_radius=2)

    def _draw_bricks(self, game: BrickBreakerGame) -> None:
        colors = (
            ((34, 211, 238), (34, 211, 238, 150)),
            ((167, 139, 250), (167, 139, 250, 140)),
            ((251, 191, 36), (251, 191, 36, 155)),
            ((251, 113, 133), (251, 113, 133, 140)),
        )
        for index, brick in enumerate(game.bricks):
            if not brick.alive:
                continue
            fill, glow_color = colors[index % len(colors)]
            rect = self.pygame.Rect(int(brick.rect.x), int(brick.rect.y), int(brick.rect.w), int(brick.rect.h))
            glow = self.pygame.Surface((rect.w + 16, rect.h + 16), self.pygame.SRCALPHA)
            self.pygame.draw.rect(glow, glow_color, (8, 8, rect.w, rect.h))
            self.screen.blit(glow, (rect.x - 8, rect.y - 8))
            self.pygame.draw.rect(self.screen, fill, rect)
            self.pygame.draw.rect(self.screen, (255, 255, 255), rect, 1)
            if brick.kind == "special":
                cx, cy = rect.center
                self.pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 5, 1)
                self.pygame.draw.line(self.screen, (255, 255, 255), (cx - 6, cy), (cx + 6, cy), 1)
                self.pygame.draw.line(self.screen, (255, 255, 255), (cx, cy - 6), (cx, cy + 6), 1)

    def _draw_stones(self, game: BrickBreakerGame) -> None:
        pg = self.pygame
        for stone in game.stones:
            rect = pg.Rect(int(stone.x), int(stone.y), int(stone.w), int(stone.h))
            pg.draw.rect(self.screen, (71, 85, 105), rect)
            pg.draw.rect(self.screen, (148, 163, 184), rect, 1)
            pg.draw.line(self.screen, (30, 41, 59), rect.topleft, rect.bottomright, 2)
            pg.draw.line(self.screen, (100, 116, 139), (rect.left + 4, rect.top + 4), (rect.right - 4, rect.top + 4), 1)

    def _draw_arena_line(self) -> None:
        y = int(self.height * 0.52)
        left = int(self.width * 0.07)
        right = int(self.width * 0.93)
        self.pygame.draw.line(self.screen, (16, 58, 84), (left, y), (right, y), 1)

    def _draw_balls(self, game: BrickBreakerGame) -> None:
        for ball in game.balls:
            self._draw_ball(game, ball.pos.x, ball.pos.y)

    def _draw_fruits(self, game: BrickBreakerGame) -> None:
        for fruit in game.fruits:
            self._draw_fruit(game, fruit.pos.x, fruit.pos.y, fruit.kind)

    def _draw_fruit(self, game: BrickBreakerGame, fruit_x: float, fruit_y: float, food: str) -> None:
        pg = self.pygame
        x = int(fruit_x)
        y = int(fruit_y)
        r = int(game.config.fruit_radius)
        glow = pg.Surface((r * 5, r * 5), pg.SRCALPHA)
        pg.draw.circle(glow, (245, 158, 11, 95), (r * 2, r * 2), r * 2)
        self.screen.blit(glow, (x - r * 2, y - r * 2))
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

    def _draw_ball(self, game: BrickBreakerGame, ball_x: float, ball_y: float) -> None:
        pg = self.pygame
        x = int(ball_x)
        y = int(ball_y)
        radius = int(game.config.ball_radius)
        pg.draw.circle(self.screen, (0, 0, 0), (x + 3, y + 5), radius)
        pg.draw.circle(self.screen, (251, 191, 36), (x, y), radius)
        pg.draw.circle(self.screen, (255, 247, 237), (x - 3, y - 3), max(2, radius // 3))
        pg.draw.circle(self.screen, (249, 115, 22), (x, y), radius, 2)

    def _draw_paddle(self, game: BrickBreakerGame) -> None:
        pg = self.pygame
        rect = pg.Rect(
            int(game.paddle.x),
            int(game.paddle.y),
            int(game.paddle.w),
            int(game.paddle.h),
        )
        glow = pg.Surface((rect.w + 34, rect.h + 28), pg.SRCALPHA)
        pg.draw.rect(glow, (251, 191, 36, 110), (17, 10, rect.w, rect.h + 4))
        self.screen.blit(glow, (rect.x - 17, rect.y - 12))
        self._draw_gradient_rect(rect, (34, 211, 238), (251, 191, 36), (251, 113, 133))
        pg.draw.rect(self.screen, (255, 255, 255), rect, 1)

    def _draw_roll_bar(self, roll_deg: float) -> None:
        pg = self.pygame
        width = 240
        height = 6
        x = (self.width - width) // 2
        y = self.height - 26
        label = self.small_font.render(f"IMU ROLL {roll_deg:+.1f}°", True, (203, 213, 225))
        self.screen.blit(label, ((self.width - label.get_width()) // 2, y - 20))
        track = pg.Rect(x, y, width, height)
        self._draw_gradient_rect(track, (34, 211, 238), (52, 211, 153), (251, 113, 133))
        pg.draw.rect(self.screen, (71, 85, 105), track, 1)
        ratio = max(-1.0, min(1.0, roll_deg / 18.0))
        dot_x = int(x + width * 0.5 + ratio * width * 0.5)
        pg.draw.rect(self.screen, (248, 250, 252), (dot_x - 4, y - 3, 8, 12))

    def buttons_visible(self, game: BrickBreakerGame) -> bool:
        return game.state in (WAIT_IMU, CALIBRATING, READY)

    def _draw_buttons(self, game: BrickBreakerGame) -> None:
        if not self.buttons_visible(game):
            return
        mouse_pos = self.pygame.mouse.get_pos()
        self._draw_button(self.restart_button_rect, "重启WS监听", "restart", mouse_pos)
        self._draw_button(self.prepare_button_rect, "重新准备机器狗", "prepare", mouse_pos)
        if self.feedback_message and time.monotonic() < self.feedback_until_s:
            surface = self.small_font.render(self.feedback_message, True, (251, 191, 36))
            self.screen.blit(surface, (self.prepare_button_rect.x, self.prepare_button_rect.bottom + 1))

    def _draw_button(self, rect, label: str, button_id: str, mouse_pos: Tuple[int, int]) -> None:
        pg = self.pygame
        hovered = rect.collidepoint(mouse_pos)
        pressed = self.pressed_button == button_id
        draw_rect = rect.copy()
        fill = (31, 37, 50) if hovered else (10, 15, 28)
        border = (251, 191, 36) if hovered else (42, 49, 64)
        text_color = (17, 24, 39) if pressed else (248, 250, 252)
        if pressed:
            draw_rect.move_ip(0, 2)
            fill = (251, 191, 36)
            border = (254, 243, 199)
        pg.draw.rect(self.screen, fill, draw_rect, border_radius=6)
        pg.draw.rect(self.screen, border, draw_rect, 2 if hovered or pressed else 1, border_radius=6)
        surface = self.small_font.render(label, True, text_color)
        self.screen.blit(
            surface,
            (
                draw_rect.centerx - surface.get_width() // 2,
                draw_rect.centery - surface.get_height() // 2,
            ),
        )

    def _draw_state(self, game: BrickBreakerGame) -> None:
        messages = {
            WAIT_IMU: "等待 IMU / WebSocket 连接",
            CALIBRATING: "校准中，请保持当前姿态",
            READY: "按空格开始，按 R 重新校准",
            LEVEL_CLEAR: f"LEVEL CLEAR! 第 {game.level} 关完成，按空格进入下一关",
            CHALLENGE_CLEAR: f"CHALLENGE CLEAR! 三关完成，本局 {game.score} 分，按空格重新挑战",
            RUNNING: "",
            GAME_OVER: f"挑战结束，本局 {game.score} 分，按空格重来",
        }
        msg = messages.get(game.state, "")
        if not msg:
            return
        surface = self.font.render(msg, True, (248, 250, 252))
        rect = surface.get_rect(midbottom=(self.width // 2, self.height - 14)).inflate(24, 12)
        self.pygame.draw.rect(self.screen, (10, 15, 28), rect)
        self.pygame.draw.rect(self.screen, (251, 191, 36), rect, 1)
        self.screen.blit(surface, (rect.x + 12, rect.y + 6))

    def _draw_celebration(self) -> None:
        self._draw_particles()
        if not self.celebration_label or time.monotonic() >= self.celebration_until_s:
            return
        surface = self.title_font.render(self.celebration_label, True, (254, 243, 199))
        shadow = self.title_font.render(self.celebration_label, True, (15, 23, 42))
        x = self.width // 2 - surface.get_width() // 2
        y = int(self.height * 0.19)
        self.screen.blit(shadow, (x + 2, y + 2))
        self.screen.blit(surface, (x, y))

    def _draw_particles(self) -> None:
        next_particles: list[CelebrationParticle] = []
        dt = 1.0 / 60.0
        for particle in self.particles:
            particle.life_s -= dt
            if particle.life_s <= 0.0:
                continue
            particle.vy += 180.0 * dt
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            next_particles.append(particle)
            radius = max(2, int(6 * min(1.0, particle.life_s)))
            self.pygame.draw.circle(self.screen, particle.color, (int(particle.x), int(particle.y)), radius)
        self.particles = next_particles

    def _draw_label(self, text: str, x: int, y: int) -> None:
        label = self.small_font.render(text, True, (145, 165, 189))
        self.screen.blit(label, (x, y))

    def _draw_gradient_rect(
        self,
        rect,
        left_color: Tuple[int, int, int],
        mid_color: Tuple[int, int, int],
        right_color: Tuple[int, int, int],
    ) -> None:
        for i in range(max(1, rect.w)):
            ratio = i / max(1, rect.w - 1)
            if ratio < 0.5:
                local = ratio / 0.5
                color = blend(left_color, mid_color, local)
            else:
                local = (ratio - 0.5) / 0.5
                color = blend(mid_color, right_color, local)
            self.pygame.draw.line(self.screen, color, (rect.x + i, rect.y), (rect.x + i, rect.y + rect.h))


def blend(a: Tuple[int, int, int], b: Tuple[int, int, int], ratio: float) -> Tuple[int, int, int]:
    return (
        int(a[0] + (b[0] - a[0]) * ratio),
        int(a[1] + (b[1] - a[1]) * ratio),
        int(a[2] + (b[2] - a[2]) * ratio),
    )
