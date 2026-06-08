"""Pygame renderer for the GOGO space fighter game."""

from __future__ import annotations

import random
from typing import Tuple

from .core import (
    BOSS,
    BOSS_KIND,
    BOSS_WARNING,
    ENEMY_SCOUT,
    ENEMY_SHOOTER,
    ENEMY_TANK,
    GAME_OVER,
    MENU,
    POWERUP_BOMB,
    POWERUP_HEAL,
    POWERUP_SHIELD,
    POWERUP_WEAPON,
    RUNNING,
    STAGE_CLEAR,
    Enemy,
    PowerUp,
    SpaceFighterGame,
)


Color = Tuple[int, int, int]


class PygameRenderer:
    def __init__(self, width: int, height: int) -> None:
        import pygame

        pygame.init()
        pygame.display.set_caption("GOGO Space Fighter")
        self.pygame = pygame
        self.width = int(width)
        self.height = int(height)
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 16)
        self.small_font = pygame.font.SysFont("Microsoft YaHei,SimHei,Arial", 12)
        self.hud_font = pygame.font.SysFont("Segoe UI", 15, bold=True)
        self.score_font = pygame.font.SysFont("Segoe UI", 19, bold=True)
        self.title_font = pygame.font.SysFont("Segoe UI", 42, bold=True)
        self.stars = [(random.randrange(width), random.randrange(height), random.choice((1, 1, 1, 2))) for _ in range(46)]
        self.time_s = 0.0

    def tick(self, fps: int) -> None:
        self.clock.tick(int(fps))
        self.time_s += 1.0 / max(1, fps)

    def draw(self, game: SpaceFighterGame) -> None:
        self._draw_background()
        if game.state == MENU:
            self._draw_menu(game)
        else:
            self._draw_gameplay(game)
        self.pygame.display.flip()

    def _draw_background(self) -> None:
        pg = self.pygame
        self.screen.fill((6, 11, 24))
        for y in range(0, self.height, 6):
            t = y / max(1, self.height - 1)
            color = (int(6 + 5 * t), int(11 + 6 * t), int(24 + 10 * t))
            pg.draw.rect(self.screen, color, (0, y, self.width, 6))
        scroll = int(self.time_s * 36) % self.height
        for x, y, radius in self.stars:
            sy = (y + scroll) % self.height
            shade = 120 + radius * 48
            pg.draw.circle(self.screen, (shade, shade, shade), (x, sy), radius)

    def _draw_menu(self, game: SpaceFighterGame) -> None:
        title = self.title_font.render("STAR", True, (255, 209, 102))
        title2 = self.title_font.render("FIGHTER", True, (255, 209, 102))
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 118))
        self.screen.blit(title2, (self.width // 2 - title2.get_width() // 2, 158))
        subtitle = self.small_font.render("CLASSIC ARCADE MISSION", True, (210, 220, 235))
        self.screen.blit(subtitle, (self.width // 2 - subtitle.get_width() // 2, 210))
        best = self.hud_font.render(f"BEST {game.high_score:04d}", True, (254, 243, 199))
        self.screen.blit(best, (self.width // 2 - best.get_width() // 2, 244))
        self._draw_button("SPACE START", self.width // 2, 302, primary=True)
        self._draw_button("ESC EXIT", self.width // 2, 348, primary=False)
        self._draw_player_ship(self.width // 2, self.height - 132, 1.05)
        hint = self.small_font.render("ARROWS / WASD MOVE, AUTO FIRE", True, (154, 168, 186))
        self.screen.blit(hint, (self.width // 2 - hint.get_width() // 2, self.height - 42))

    def _draw_button(self, text: str, center_x: int, y: int, primary: bool) -> None:
        pg = self.pygame
        rect = pg.Rect(0, y, 168, 36)
        rect.centerx = center_x
        fill = (255, 209, 102) if primary else (20, 28, 42)
        border = (255, 238, 180) if primary else (76, 88, 108)
        text_color = (8, 12, 20) if primary else (235, 240, 248)
        pg.draw.rect(self.screen, fill, rect, border_radius=7)
        pg.draw.rect(self.screen, border, rect, 1, border_radius=7)
        label = self.hud_font.render(text, True, text_color)
        self.screen.blit(label, (rect.centerx - label.get_width() // 2, rect.centery - label.get_height() // 2))

    def _draw_gameplay(self, game: SpaceFighterGame) -> None:
        self._draw_hud(game)
        for powerup in game.powerups:
            self._draw_powerup(powerup)
        for bullet in game.player_bullets:
            self._draw_player_bullet(int(bullet.pos.x), int(bullet.pos.y))
        for bullet in game.enemy_bullets:
            self._draw_enemy_bullet(int(bullet.pos.x), int(bullet.pos.y), int(bullet.radius))
        for enemy in game.enemies:
            self._draw_enemy(enemy)
        if game.boss is not None and game.boss.active:
            self._draw_enemy(game.boss)
        for text in game.floating_texts:
            label = self.hud_font.render(text.text, True, text.color)
            self.screen.blit(label, (int(text.pos.x - label.get_width() * 0.5), int(text.pos.y)))
        if game.invincible_timer_s <= 0.0 or int(self.time_s * 12) % 2 == 0:
            self._draw_player_ship(int(game.player_center.x), int(game.player.y + game.player.h * 0.52), 0.72)
        if game.invincible_timer_s > 0.0:
            self._draw_invincible_ring(int(game.player_center.x), int(game.player_center.y))
        self._draw_state_overlay(game)

    def _draw_hud(self, game: SpaceFighterGame) -> None:
        pg = self.pygame
        panel_h = 24
        life_rect = pg.Rect(12, 12, 62, panel_h)
        self._draw_pill(life_rect)
        for i in range(game.config.max_lives):
            self._draw_life_icon(24 + i * 15, 24, i < game.lives)
        hp_rect = pg.Rect(80, 17, 68, 10)
        pg.draw.rect(self.screen, (8, 12, 20), hp_rect, border_radius=5)
        hp_ratio = max(0.0, min(1.0, game.hp / max(1, game.config.hp_per_life)))
        hp_fill = pg.Rect(hp_rect.x, hp_rect.y, int(hp_rect.w * hp_ratio), hp_rect.h)
        hp_color = (117, 240, 138) if hp_ratio > 0.45 else (255, 209, 102) if hp_ratio > 0.2 else (255, 92, 122)
        pg.draw.rect(self.screen, hp_color, hp_fill, border_radius=5)
        pg.draw.rect(self.screen, (180, 190, 205), hp_rect, 1, border_radius=5)
        hp_text = self.small_font.render(f"{max(0, game.hp):03d}", True, (226, 232, 240))
        self.screen.blit(hp_text, (hp_rect.centerx - hp_text.get_width() // 2, hp_rect.y + 10))
        score_rect = pg.Rect(0, 12, 116, panel_h)
        score_rect.centerx = self.width // 2
        self._draw_pill(score_rect, (255, 209, 102))
        score = self.hud_font.render(f"SCORE {game.score:04d}", True, (255, 209, 102))
        self.screen.blit(score, (score_rect.centerx - score.get_width() // 2, score_rect.centery - score.get_height() // 2))
        weapon_rect = pg.Rect(self.width - 104, 12, 92, panel_h)
        self._draw_pill(weapon_rect)
        weapon = self.hud_font.render(f"WEAPON {game.weapon_level}", True, (245, 248, 252))
        self.screen.blit(weapon, (weapon_rect.centerx - weapon.get_width() // 2, weapon_rect.centery - weapon.get_height() // 2))
        if game.state == BOSS and game.boss is not None:
            self._draw_boss_bar(game.boss)
        elif game.state == RUNNING:
            wave = self.small_font.render(f"WAVE {game.wave:02d} / {game.config.waves_per_stage:02d}", True, (201, 248, 255))
            rect = pg.Rect(0, 46, 128, 22)
            rect.centerx = self.width // 2
            self._draw_pill(rect, (104, 230, 255))
            self.screen.blit(wave, (rect.centerx - wave.get_width() // 2, rect.centery - wave.get_height() // 2))
        elif game.state == BOSS_WARNING:
            warning = self.hud_font.render("WARNING INCOMING", True, (255, 231, 161))
            self.screen.blit(warning, (self.width // 2 - warning.get_width() // 2, 52))

    def _draw_pill(self, rect, accent: Color = (255, 255, 255)) -> None:
        pg = self.pygame
        surface = pg.Surface((rect.w, rect.h), pg.SRCALPHA)
        pg.draw.rect(surface, (0, 0, 0, 88), surface.get_rect(), border_radius=rect.h // 2)
        pg.draw.rect(surface, (*accent, 70), surface.get_rect(), 1, border_radius=rect.h // 2)
        self.screen.blit(surface, rect.topleft)

    def _draw_life_icon(self, x: int, y: int, active: bool) -> None:
        color = (103, 167, 255) if active else (80, 88, 104)
        hi = (244, 251, 255) if active else (115, 122, 137)
        points = [(x, y - 8), (x + 7, y + 8), (x, y + 4), (x - 7, y + 8)]
        self.pygame.draw.polygon(self.screen, color, points)
        self.pygame.draw.polygon(self.screen, hi, [(x, y - 6), (x + 3, y + 3), (x, y + 1), (x - 3, y + 3)])

    def _draw_boss_bar(self, boss: Enemy) -> None:
        pg = self.pygame
        label_rect = pg.Rect(18, 46, 42, 18)
        pg.draw.rect(self.screen, (72, 22, 38), label_rect, border_radius=5)
        pg.draw.rect(self.screen, (255, 92, 122), label_rect, 1, border_radius=5)
        label = self.small_font.render("BOSS", True, (255, 220, 228))
        self.screen.blit(label, (label_rect.centerx - label.get_width() // 2, label_rect.centery - label.get_height() // 2))
        bar = pg.Rect(66, 51, self.width - 84, 8)
        pg.draw.rect(self.screen, (8, 12, 20), bar, border_radius=4)
        hp_ratio = max(0.0, min(1.0, boss.hp / max(1.0, boss.max_hp)))
        fill = pg.Rect(bar.x, bar.y, int(bar.w * hp_ratio), bar.h)
        pg.draw.rect(self.screen, (255, 92, 122), fill, border_radius=4)
        pg.draw.rect(self.screen, (255, 210, 150), bar, 1, border_radius=4)

    def _draw_player_bullet(self, x: int, y: int) -> None:
        pg = self.pygame
        pg.draw.line(self.screen, (255, 246, 200), (x, y + 10), (x, y - 14), 5)
        pg.draw.line(self.screen, (255, 209, 102), (x, y + 10), (x, y - 14), 2)

    def _draw_enemy_bullet(self, x: int, y: int, radius: int) -> None:
        pg = self.pygame
        pg.draw.circle(self.screen, (255, 92, 122), (x, y), radius)
        pg.draw.circle(self.screen, (255, 224, 232), (x - 2, y - 2), max(1, radius // 2))

    def _draw_player_ship(self, center_x: int, center_y: int, scale: float) -> None:
        pg = self.pygame

        def p(dx: float, dy: float) -> tuple[int, int]:
            return (int(center_x + dx * scale), int(center_y + dy * scale))

        flame = [p(0, 46), p(8, 28), p(0, 35), p(-8, 28)]
        pg.draw.polygon(self.screen, (104, 230, 255), flame)
        body = [p(0, -48), p(18, -2), p(40, 42), p(15, 30), p(0, 52), p(-15, 30), p(-40, 42), p(-18, -2)]
        pg.draw.polygon(self.screen, (103, 167, 255), body)
        pg.draw.polygon(self.screen, (232, 244, 255), [p(0, -38), p(11, 28), p(0, 42), p(-11, 28)])
        pg.draw.polygon(self.screen, (20, 43, 80), [p(0, -30), p(8, -2), p(0, 16), p(-8, -2)])
        pg.draw.polygon(self.screen, (255, 209, 102), [p(-25, 26), p(-40, 52), p(-13, 36)])
        pg.draw.polygon(self.screen, (255, 209, 102), [p(25, 26), p(40, 52), p(13, 36)])

    def _draw_invincible_ring(self, center_x: int, center_y: int) -> None:
        pg = self.pygame
        pulse = 22 + int((self.time_s * 18) % 8)
        ring = pg.Surface((pulse * 2 + 4, pulse * 2 + 4), pg.SRCALPHA)
        pg.draw.circle(ring, (104, 230, 255, 90), (pulse + 2, pulse + 2), pulse, 2)
        self.screen.blit(ring, (center_x - pulse - 2, center_y - pulse - 2))

    def _draw_enemy(self, enemy: Enemy) -> None:
        if enemy.kind == BOSS_KIND:
            self._draw_boss(enemy)
        elif enemy.kind == ENEMY_TANK:
            self._draw_tank(enemy)
        elif enemy.kind == ENEMY_SHOOTER:
            self._draw_shooter(enemy)
        else:
            self._draw_scout(enemy)

    def _draw_scout(self, enemy: Enemy) -> None:
        rect = enemy.rect
        cx = int(rect.x + rect.w * 0.5)
        cy = int(rect.y + rect.h * 0.5)
        pts = [(cx, int(rect.y + rect.h)), (int(rect.x + rect.w), int(rect.y + 7)), (cx + 6, cy - 2), (cx, int(rect.y)), (cx - 6, cy - 2), (int(rect.x), int(rect.y + 7))]
        self.pygame.draw.polygon(self.screen, (255, 92, 122), pts)
        self.pygame.draw.polygon(self.screen, (255, 157, 77), [(cx - 7, cy + 8), (cx - 22, cy + 24), (cx - 2, cy + 15)])
        self.pygame.draw.polygon(self.screen, (255, 157, 77), [(cx + 7, cy + 8), (cx + 22, cy + 24), (cx + 2, cy + 15)])

    def _draw_tank(self, enemy: Enemy) -> None:
        rect = enemy.rect
        cx = int(rect.x + rect.w * 0.5)
        cy = int(rect.y + rect.h * 0.5)
        pts = [(cx, int(rect.y)), (int(rect.x + rect.w * 0.78), cy - 5), (int(rect.x + rect.w), cy), (int(rect.x + rect.w * 0.74), cy + 9), (cx, int(rect.y + rect.h)), (int(rect.x + rect.w * 0.26), cy + 9), (int(rect.x), cy), (int(rect.x + rect.w * 0.22), cy - 5)]
        self.pygame.draw.polygon(self.screen, (180, 140, 255), pts)
        self.pygame.draw.polygon(self.screen, (27, 17, 52), [(cx, cy - 17), (cx + 18, cy), (cx, cy + 18), (cx - 18, cy)])
        self.pygame.draw.circle(self.screen, (104, 230, 255), (cx - 18, cy + 10), 4)
        self.pygame.draw.circle(self.screen, (104, 230, 255), (cx + 18, cy + 10), 4)

    def _draw_shooter(self, enemy: Enemy) -> None:
        rect = enemy.rect
        cx = int(rect.x + rect.w * 0.5)
        cy = int(rect.y + rect.h * 0.5)
        pts = [(cx, int(rect.y + rect.h)), (int(rect.x + rect.w), int(rect.y + 10)), (cx + 8, cy - 3), (cx, int(rect.y)), (cx - 8, cy - 3), (int(rect.x), int(rect.y + 10))]
        self.pygame.draw.polygon(self.screen, (255, 157, 77), pts)
        self.pygame.draw.circle(self.screen, (255, 92, 122), (cx - 12, cy + 8), 4)
        self.pygame.draw.circle(self.screen, (255, 92, 122), (cx + 12, cy + 8), 4)

    def _draw_boss(self, enemy: Enemy) -> None:
        rect = enemy.rect
        cx = int(rect.x + rect.w * 0.5)
        cy = int(rect.y + rect.h * 0.5)
        pts = [(cx, int(rect.y)), (int(rect.x + rect.w * 0.70), cy - 20), (int(rect.x + rect.w), cy - 5), (int(rect.x + rect.w * 0.72), cy + 25), (int(rect.x + rect.w * 0.82), int(rect.y + rect.h)), (int(rect.x + rect.w * 0.58), cy + 42), (cx, int(rect.y + rect.h - 4)), (int(rect.x + rect.w * 0.42), cy + 42), (int(rect.x + rect.w * 0.18), int(rect.y + rect.h)), (int(rect.x + rect.w * 0.28), cy + 25), (int(rect.x), cy - 5), (int(rect.x + rect.w * 0.30), cy - 20)]
        self.pygame.draw.polygon(self.screen, (255, 92, 122), pts)
        self.pygame.draw.polygon(self.screen, (36, 18, 42), [(cx, cy - 26), (cx + 28, cy + 3), (cx, cy + 32), (cx - 28, cy + 3)])
        self.pygame.draw.circle(self.screen, (104, 230, 255), (cx - 28, cy + 20), 6)
        self.pygame.draw.circle(self.screen, (104, 230, 255), (cx + 28, cy + 20), 6)
        self.pygame.draw.polygon(self.screen, (255, 240, 164), [(cx - 10, cy + 46), (cx, cy + 70), (cx + 10, cy + 46)])

    def _draw_powerup(self, powerup: PowerUp) -> None:
        cx = int(powerup.rect.x + powerup.rect.w * 0.5)
        cy = int(powerup.rect.y + powerup.rect.h * 0.5)
        if powerup.kind == POWERUP_SHIELD:
            self._draw_shield_icon(cx, cy, int(powerup.rect.w))
        elif powerup.kind == POWERUP_HEAL:
            self._draw_heal_icon(cx, cy, int(powerup.rect.w))
        elif powerup.kind == POWERUP_BOMB:
            self._draw_bomb_icon(cx, cy, int(powerup.rect.w))
        elif powerup.kind == POWERUP_WEAPON:
            self._draw_weapon_icon(cx, cy, int(powerup.rect.w))

    def _draw_weapon_icon(self, cx: int, cy: int, size: int) -> None:
        pg = self.pygame
        r = size // 2
        hex_pts = [(cx, cy - r), (cx + r, cy - r // 2), (cx + r, cy + r // 2), (cx, cy + r), (cx - r, cy + r // 2), (cx - r, cy - r // 2)]
        pg.draw.polygon(self.screen, (255, 209, 102), hex_pts)
        pg.draw.polygon(self.screen, (255, 244, 200), hex_pts, 2)
        pg.draw.polygon(self.screen, (16, 24, 39), [(cx, cy - 12), (cx + 8, cy + 9), (cx, cy + 15), (cx - 8, cy + 9)])
        pg.draw.polygon(self.screen, (255, 244, 200), [(cx, cy - 8), (cx + 4, cy + 7), (cx, cy + 11), (cx - 4, cy + 7)])
        pg.draw.polygon(self.screen, (104, 230, 255), [(cx - 4, cy + 13), (cx, cy + 20), (cx + 4, cy + 13)])

    def _draw_shield_icon(self, cx: int, cy: int, size: int) -> None:
        pg = self.pygame
        r = size // 2
        pts = [(cx, cy - r), (cx + r, cy - r // 2), (cx + r - 3, cy + 5), (cx + 5, cy + r), (cx, cy + r + 3), (cx - 5, cy + r), (cx - r + 3, cy + 5), (cx - r, cy - r // 2)]
        pg.draw.polygon(self.screen, (104, 230, 255), pts)
        pg.draw.polygon(self.screen, (235, 255, 255), pts, 2)
        pg.draw.lines(self.screen, (117, 240, 138), False, [(cx - 8, cy), (cx - 2, cy + 6), (cx + 11, cy - 8)], 4)

    def _draw_heal_icon(self, cx: int, cy: int, size: int) -> None:
        pg = self.pygame
        r = size // 2
        hex_pts = [(cx, cy - r), (cx + r, cy - r // 2), (cx + r, cy + r // 2), (cx, cy + r), (cx - r, cy + r // 2), (cx - r, cy - r // 2)]
        pg.draw.polygon(self.screen, (117, 240, 138), hex_pts)
        pg.draw.polygon(self.screen, (235, 255, 239), hex_pts, 2)
        pg.draw.rect(self.screen, (8, 38, 21), (cx - 4, cy - 13, 8, 26), border_radius=2)
        pg.draw.rect(self.screen, (8, 38, 21), (cx - 13, cy - 4, 26, 8), border_radius=2)

    def _draw_bomb_icon(self, cx: int, cy: int, size: int) -> None:
        pg = self.pygame
        r = size // 2
        hex_pts = [(cx, cy - r), (cx + r, cy - r // 2), (cx + r, cy + r // 2), (cx, cy + r), (cx - r, cy + r // 2), (cx - r, cy - r // 2)]
        pg.draw.polygon(self.screen, (180, 140, 255), hex_pts)
        pg.draw.polygon(self.screen, (239, 229, 255), hex_pts, 2)
        bolt = [(cx + 2, cy - 14), (cx - 8, cy + 2), (cx, cy + 2), (cx - 3, cy + 16), (cx + 12, cy - 5), (cx + 3, cy - 5)]
        pg.draw.polygon(self.screen, (255, 240, 164), bolt)

    def _draw_state_overlay(self, game: SpaceFighterGame) -> None:
        if game.state == RUNNING:
            return
        if game.state == BOSS_WARNING:
            self._draw_center_message("WARNING", "BOSS INCOMING")
        elif game.state == STAGE_CLEAR:
            if game.stage >= game.config.max_stage:
                self._draw_center_message("MISSION CLEAR", "SPACE BACK TO MENU")
            else:
                self._draw_center_message("STAGE CLEAR", "SPACE NEXT STAGE")
        elif game.state == GAME_OVER:
            self._draw_center_message("GAME OVER", "SPACE RETRY / ESC EXIT")

    def _draw_center_message(self, title: str, subtitle: str) -> None:
        pg = self.pygame
        panel = pg.Rect(42, 250, self.width - 84, 126)
        overlay = pg.Surface((panel.w, panel.h), pg.SRCALPHA)
        pg.draw.rect(overlay, (8, 13, 24, 218), overlay.get_rect(), border_radius=8)
        pg.draw.rect(overlay, (255, 209, 102, 90), overlay.get_rect(), 1, border_radius=8)
        self.screen.blit(overlay, panel.topleft)
        title_s = self.title_font.render(title, True, (255, 209, 102))
        sub_s = self.font.render(subtitle, True, (226, 232, 240))
        self.screen.blit(title_s, (panel.centerx - title_s.get_width() // 2, panel.y + 24))
        self.screen.blit(sub_s, (panel.centerx - sub_s.get_width() // 2, panel.y + 82))
