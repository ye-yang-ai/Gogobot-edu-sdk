"""Pure rules for the GOGO space fighter mini game."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional


MENU = "MENU"
RUNNING = "RUNNING"
BOSS_WARNING = "BOSS_WARNING"
BOSS = "BOSS"
STAGE_CLEAR = "STAGE_CLEAR"
GAME_OVER = "GAME_OVER"

ENEMY_SCOUT = "scout"
ENEMY_TANK = "tank"
ENEMY_SHOOTER = "shooter"
BOSS_KIND = "boss"

POWERUP_WEAPON = "weapon"
POWERUP_SHIELD = "shield"
POWERUP_HEAL = "heal"
POWERUP_BOMB = "bomb"


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

    def intersects(self, other: "Rect") -> bool:
        return (
            self.x < other.x + other.w
            and self.x + self.w > other.x
            and self.y < other.y + other.h
            and self.y + self.h > other.y
        )


@dataclass
class Bullet:
    pos: Vec2
    velocity: Vec2
    damage: int
    owner: str
    radius: float = 5.0
    active: bool = True

    @property
    def rect(self) -> Rect:
        return Rect(self.pos.x - self.radius, self.pos.y - self.radius, self.radius * 2.0, self.radius * 2.0)


@dataclass
class Enemy:
    kind: str
    rect: Rect
    hp: int
    max_hp: int
    score: int
    vx: float = 0.0
    vy: float = 90.0
    fire_interval_s: float = 0.0
    fire_timer_s: float = 0.0
    active: bool = True


@dataclass
class PowerUp:
    kind: str
    rect: Rect
    vy: float = 110.0
    active: bool = True


@dataclass
class FloatingText:
    text: str
    pos: Vec2
    life_s: float
    color: tuple[int, int, int]


@dataclass
class SpaceFighterConfig:
    width: int = 480
    height: int = 720
    player_w: float = 38.0
    player_h: float = 48.0
    player_speed: float = 290.0
    initial_lives: int = 3
    max_lives: int = 3
    hp_per_life: int = 100
    bullet_damage_to_player: int = 5
    collision_damage_to_player: int = 50
    invincible_s: float = 3.0
    max_weapon_level: int = 4
    fire_interval_s: float = 0.22
    bullet_speed: float = 560.0
    enemy_bullet_speed: float = 210.0
    waves_per_stage: int = 3
    max_stage: int = 5
    warning_s: float = 1.0
    stage_clear_s: float = 1.2
    spawn_interval_s: float = 0.48
    enemy_margin_top: float = 86.0
    powerup_drop_chance: float = 0.25
    heal_amount: int = 30


class SpaceFighterGame:
    def __init__(self, config: SpaceFighterConfig, high_score: int = 0, rng: Optional[random.Random] = None) -> None:
        self.config = config
        self.high_score = max(0, int(high_score))
        self.rng = rng or random.Random()
        self.state = MENU
        self.score = 0
        self.stage = 1
        self.wave = 0
        self.lives = config.initial_lives
        self.hp = config.hp_per_life
        self.invincible_timer_s = 0.0
        self.weapon_level = 1
        self.player = Rect(0.0, 0.0, config.player_w, config.player_h)
        self.enemies: List[Enemy] = []
        self.player_bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []
        self.powerups: List[PowerUp] = []
        self.floating_texts: List[FloatingText] = []
        self.boss: Optional[Enemy] = None
        self.fire_timer_s = 0.0
        self.spawn_timer_s = 0.0
        self.warning_timer_s = 0.0
        self.stage_clear_timer_s = 0.0
        self.new_high_score = False
        self.enemy_destroyed_event_id = 0
        self.powerup_event_id = 0
        self.powerup_collect_event_id = 0
        self.boss_spawn_event_id = 0
        self.boss_defeat_event_id = 0
        self.player_hit_event_id = 0
        self.reset_round()

    def reset_round(self) -> None:
        cfg = self.config
        self.score = 0
        self.stage = 1
        self.wave = 0
        self.lives = max(1, int(cfg.initial_lives))
        self.hp = max(1, int(cfg.hp_per_life))
        self.invincible_timer_s = 0.0
        self.weapon_level = 1
        self.player.x = (cfg.width - cfg.player_w) * 0.5
        self.player.y = cfg.height - cfg.player_h - 34.0
        self.enemies = []
        self.player_bullets = []
        self.enemy_bullets = []
        self.powerups = []
        self.floating_texts = []
        self.boss = None
        self.fire_timer_s = 0.0
        self.spawn_timer_s = 0.0
        self.warning_timer_s = 0.0
        self.stage_clear_timer_s = 0.0
        self.new_high_score = False

    def start_game(self) -> None:
        self.reset_round()
        self.state = RUNNING
        self._spawn_next_wave()

    def restart_to_menu(self) -> None:
        self.state = MENU
        self.reset_round()

    def start_next_stage(self) -> None:
        if self.state != STAGE_CLEAR:
            return
        if self.stage >= self.config.max_stage:
            self.state = MENU
            self.reset_round()
            return
        self.stage += 1
        self.wave = 0
        self.boss = None
        self.enemies = []
        self.player_bullets = []
        self.enemy_bullets = []
        self.powerups = []
        self.floating_texts = []
        self.weapon_level = 1
        self.hp = self.config.hp_per_life
        self.invincible_timer_s = 0.0
        self.fire_timer_s = 0.0
        self.stage_clear_timer_s = 0.0
        self.state = RUNNING
        self._spawn_next_wave()

    @property
    def player_center(self) -> Vec2:
        return Vec2(self.player.x + self.player.w * 0.5, self.player.y + self.player.h * 0.5)

    def update(self, dt_s: float, move_x: float = 0.0, move_y: float = 0.0) -> None:
        dt = clamp(dt_s, 0.0, 0.05)
        self._update_floating_texts(dt)
        self._update_invincible(dt)
        if self.state == MENU or self.state == GAME_OVER:
            return
        if self.state == STAGE_CLEAR:
            self.stage_clear_timer_s += dt
            return
        self._move_player(dt, move_x, move_y)
        self._fire_player_if_ready(dt)
        self._update_player_bullets(dt)
        self._update_enemy_bullets(dt)
        self._update_powerups(dt)

        if self.state == BOSS_WARNING:
            self.warning_timer_s += dt
            if self.warning_timer_s >= self.config.warning_s:
                self._spawn_boss()
            return

        if self.state == BOSS:
            self._update_boss(dt)
        elif self.state == RUNNING:
            self._update_wave_enemies(dt)
            if not self.enemies and self.wave < self.config.waves_per_stage:
                self.spawn_timer_s += dt
                if self.spawn_timer_s >= self.config.spawn_interval_s:
                    self._spawn_next_wave()
            elif not self.enemies and self.wave >= self.config.waves_per_stage:
                self._enter_boss_warning()

        self._collide_player_bullets()
        self._collide_enemy_bullets()
        self._collide_powerups()
        self._cleanup_objects()

    def remaining_minions(self) -> int:
        return sum(1 for enemy in self.enemies if enemy.active)

    def boss_active(self) -> bool:
        return self.state == BOSS and self.boss is not None and self.boss.active

    def _move_player(self, dt: float, move_x: float, move_y: float) -> None:
        cfg = self.config
        self.player.x = clamp(self.player.x + move_x * cfg.player_speed * dt, 0.0, cfg.width - self.player.w)
        top = cfg.height * 0.52
        self.player.y = clamp(self.player.y + move_y * cfg.player_speed * dt, top, cfg.height - self.player.h - 12.0)

    def _fire_player_if_ready(self, dt: float) -> None:
        self.fire_timer_s -= dt
        if self.fire_timer_s > 0.0:
            return
        self.fire_timer_s = max(0.08, self.config.fire_interval_s - (self.weapon_level - 1) * 0.025)
        self._spawn_player_bullets()

    def _spawn_player_bullets(self) -> None:
        center = self.player_center
        patterns = {
            1: ((0.0, 0.0),),
            2: ((-8.0, 0.0), (8.0, 0.0)),
            3: ((0.0, 0.0), (-12.0, -0.22), (12.0, 0.22)),
            4: ((0.0, 0.0), (-13.0, -0.24), (13.0, 0.24), (-24.0, -0.38), (24.0, 0.38)),
        }
        for offset_x, angle in patterns[min(self.weapon_level, self.config.max_weapon_level)]:
            speed = self.config.bullet_speed
            vx = math.sin(angle) * speed
            vy = -math.cos(angle) * speed
            self.player_bullets.append(Bullet(Vec2(center.x + offset_x, self.player.y + 8.0), Vec2(vx, vy), 1, "player"))

    def _update_player_bullets(self, dt: float) -> None:
        for bullet in self.player_bullets:
            bullet.pos.x += bullet.velocity.x * dt
            bullet.pos.y += bullet.velocity.y * dt
            if bullet.pos.y < -24.0 or bullet.pos.x < -24.0 or bullet.pos.x > self.config.width + 24.0:
                bullet.active = False

    def _update_enemy_bullets(self, dt: float) -> None:
        for bullet in self.enemy_bullets:
            bullet.pos.x += bullet.velocity.x * dt
            bullet.pos.y += bullet.velocity.y * dt
            if bullet.pos.y > self.config.height + 24.0 or bullet.pos.x < -24.0 or bullet.pos.x > self.config.width + 24.0:
                bullet.active = False

    def _update_powerups(self, dt: float) -> None:
        for powerup in self.powerups:
            powerup.rect.y += powerup.vy * dt
            if powerup.rect.y > self.config.height + 20.0:
                powerup.active = False

    def _update_invincible(self, dt: float) -> None:
        if self.invincible_timer_s > 0.0:
            self.invincible_timer_s = max(0.0, self.invincible_timer_s - dt)

    def _update_wave_enemies(self, dt: float) -> None:
        for enemy in self.enemies:
            enemy.rect.x += enemy.vx * dt
            enemy.rect.y += enemy.vy * dt
            if enemy.rect.x < 8.0 or enemy.rect.x + enemy.rect.w > self.config.width - 8.0:
                enemy.vx *= -1.0
            if enemy.kind == ENEMY_SHOOTER:
                self._enemy_fire_if_ready(enemy, dt)
            if enemy.rect.y > self.config.height + 32.0:
                enemy.active = False

    def _update_boss(self, dt: float) -> None:
        if self.boss is None or not self.boss.active:
            return
        boss = self.boss
        boss.rect.x += boss.vx * dt
        if boss.rect.x < 28.0 or boss.rect.x + boss.rect.w > self.config.width - 28.0:
            boss.vx *= -1.0
        self._enemy_fire_if_ready(boss, dt)

    def _enemy_fire_if_ready(self, enemy: Enemy, dt: float) -> None:
        if enemy.fire_interval_s <= 0.0:
            return
        enemy.fire_timer_s -= dt
        if enemy.fire_timer_s > 0.0:
            return
        enemy.fire_timer_s = enemy.fire_interval_s
        center_x = enemy.rect.x + enemy.rect.w * 0.5
        y = enemy.rect.y + enemy.rect.h
        if enemy.kind == BOSS_KIND:
            for vx in (-60.0, 0.0, 60.0):
                self.enemy_bullets.append(Bullet(Vec2(center_x, y), Vec2(vx, self._enemy_bullet_speed()), 1, "enemy", radius=6.0))
        else:
            self.enemy_bullets.append(Bullet(Vec2(center_x, y), Vec2(0.0, self._enemy_bullet_speed()), 1, "enemy", radius=5.0))

    def _enemy_bullet_speed(self) -> float:
        return self.config.enemy_bullet_speed * 0.85

    def _spawn_next_wave(self) -> None:
        cfg = self.config
        self.wave += 1
        self.spawn_timer_s = 0.0
        count = 3 + min(4, self.stage - 1) + (self.wave - 1)
        spacing = cfg.width / (count + 1)
        kinds = (ENEMY_SCOUT, ENEMY_SHOOTER, ENEMY_TANK)
        for i in range(count):
            kind = kinds[(self.wave + i) % len(kinds)]
            w, h, hp, score, vy, fire_interval = self._enemy_stats(kind)
            x = spacing * (i + 1) - w * 0.5
            y = cfg.enemy_margin_top + (i % 2) * 46.0
            vx = ((-1) ** i) * (26.0 + self.stage * 4.0) if kind != ENEMY_SCOUT else 0.0
            enemy_hp = hp + max(0, self.stage - 1)
            self.enemies.append(
                Enemy(
                    kind,
                    Rect(x, y, w, h),
                    enemy_hp,
                    enemy_hp,
                    score,
                    vx,
                    vy + (self.stage - 1) * 10.0,
                    self._stage_fire_interval(fire_interval),
                    self._stage_fire_interval(fire_interval) * 0.65,
                )
            )

    def _stage_fire_interval(self, base_interval: float) -> float:
        if base_interval <= 0.0:
            return 0.0
        return max(0.62, base_interval - (self.stage - 1) * 0.12)

    def _enemy_stats(self, kind: str) -> tuple[float, float, int, int, float, float]:
        if kind == ENEMY_TANK:
            return 58.0, 42.0, 3, 35, 62.0, 0.0
        if kind == ENEMY_SHOOTER:
            return 44.0, 38.0, 2, 30, 76.0, 1.35
        return 38.0, 32.0, 1, 15, 102.0, 0.0

    def _enter_boss_warning(self) -> None:
        if self.state != RUNNING:
            return
        self.state = BOSS_WARNING
        self.warning_timer_s = 0.0
        self.enemy_bullets = []
        self.powerups = []

    def _spawn_boss(self) -> None:
        cfg = self.config
        w = 150.0
        h = 96.0
        hp = 38 + (self.stage - 1) * 16
        self.boss = Enemy(
            BOSS_KIND,
            Rect((cfg.width - w) * 0.5, 118.0, w, h),
            hp,
            hp,
            500 + self.stage * 120,
            70.0 + (self.stage - 1) * 9.0,
            0.0,
            max(0.48, 0.85 - (self.stage - 1) * 0.08),
            0.45,
        )
        self.state = BOSS
        self.boss_spawn_event_id += 1

    def _collide_player_bullets(self) -> None:
        targets: List[Enemy] = [enemy for enemy in self.enemies if enemy.active]
        if self.boss is not None and self.boss.active:
            targets.append(self.boss)
        for bullet in self.player_bullets:
            if not bullet.active:
                continue
            for target in targets:
                if target.active and bullet.rect.intersects(target.rect):
                    bullet.active = False
                    target.hp -= bullet.damage
                    if target.hp <= 0:
                        self._destroy_enemy(target)
                    break

    def _destroy_enemy(self, enemy: Enemy) -> None:
        enemy.active = False
        self.score += enemy.score
        self.enemy_destroyed_event_id += 1
        self.floating_texts.append(FloatingText(f"+{enemy.score}", Vec2(enemy.rect.x + enemy.rect.w * 0.5, enemy.rect.y), 0.6, (255, 209, 102)))
        if enemy.kind == BOSS_KIND:
            self._defeat_boss(enemy)
            return
        self._maybe_drop_powerup(enemy)

    def _defeat_boss(self, boss: Enemy) -> None:
        self.boss_defeat_event_id += 1
        self.boss = None
        self.enemy_bullets = []
        self.powerups = []
        self.state = STAGE_CLEAR
        self.stage_clear_timer_s = 0.0
        self._update_high_score()

    def _maybe_drop_powerup(self, enemy: Enemy) -> None:
        if self.rng.random() > self.config.powerup_drop_chance:
            return
        roll = self.rng.random()
        if roll < 0.45:
            kind = POWERUP_WEAPON
        elif roll < 0.70:
            kind = POWERUP_SHIELD
        elif roll < 0.88:
            kind = POWERUP_HEAL
        else:
            kind = POWERUP_BOMB
        size = 30.0
        self.powerups.append(PowerUp(kind, Rect(enemy.rect.x + enemy.rect.w * 0.5 - size * 0.5, enemy.rect.y + enemy.rect.h * 0.5, size, size)))
        self.powerup_event_id += 1

    def _collide_enemy_bullets(self) -> None:
        for bullet in self.enemy_bullets:
            if bullet.active and bullet.rect.intersects(self.player):
                bullet.active = False
                self._damage_player(self.config.bullet_damage_to_player)

        for enemy in self.enemies:
            if enemy.active and enemy.rect.intersects(self.player):
                enemy.active = False
                self._damage_player(self.config.collision_damage_to_player)

        if self.boss is not None and self.boss.active and self.boss.rect.intersects(self.player):
            self._damage_player(self.config.collision_damage_to_player)

    def _damage_player(self, damage: int) -> bool:
        if self.invincible_timer_s > 0.0 or self.state == GAME_OVER:
            return False
        self.hp -= max(0, int(damage))
        self.player_hit_event_id += 1
        if self.hp > 0:
            return True
        self.lives -= 1
        if self.lives <= 0:
            self.lives = 0
            self.hp = 0
            self.state = GAME_OVER
            self._update_high_score()
            return True
        self.hp = self.config.hp_per_life
        self.invincible_timer_s = self.config.invincible_s
        self.floating_texts.append(FloatingText("INVINCIBLE", self.player_center, 0.8, (104, 230, 255)))
        return True

    def _collide_powerups(self) -> None:
        for powerup in self.powerups:
            if not powerup.active or not powerup.rect.intersects(self.player):
                continue
            powerup.active = False
            if powerup.kind == POWERUP_WEAPON:
                self.weapon_level = min(self.config.max_weapon_level, self.weapon_level + 1)
            elif powerup.kind == POWERUP_SHIELD:
                self.invincible_timer_s = max(self.invincible_timer_s, self.config.invincible_s)
            elif powerup.kind == POWERUP_HEAL:
                self.hp = min(self.config.hp_per_life, self.hp + self.config.heal_amount)
            elif powerup.kind == POWERUP_BOMB:
                for enemy in self.enemies:
                    if enemy.active:
                        enemy.active = False
                        self.score += enemy.score
                if self.boss is not None and self.boss.active:
                    self.boss.hp = max(1, self.boss.hp - 8)
                self.enemy_bullets = []
            self.powerup_collect_event_id += 1

    def _cleanup_objects(self) -> None:
        self.enemies = [enemy for enemy in self.enemies if enemy.active]
        self.player_bullets = [bullet for bullet in self.player_bullets if bullet.active]
        self.enemy_bullets = [bullet for bullet in self.enemy_bullets if bullet.active]
        self.powerups = [powerup for powerup in self.powerups if powerup.active]

    def _update_floating_texts(self, dt: float) -> None:
        for text in self.floating_texts:
            text.life_s -= dt
            text.pos.y -= 28.0 * dt
        self.floating_texts = [text for text in self.floating_texts if text.life_s > 0.0]

    def _update_high_score(self) -> None:
        if self.score > self.high_score:
            self.high_score = int(self.score)
            self.new_high_score = True


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
