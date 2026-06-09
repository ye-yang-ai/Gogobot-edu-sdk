"""Pure rules for the AIDog IMU balance ball game."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Protocol


BALL_RADIUS = 21.0
REWARD_FOOD_TYPES = ("apple", "banana", "carrot", "pumpkin", "chicken", "biscuit", "cheese")
SCORE_MILESTONES = (1000, 2000, 3000, 4000, 5000)
MILESTONE_LABELS = ("Nice!", "Great!", "Excellent!", "Amazing!", "Unbelievable!")


class ScoreStoreProtocol(Protocol):
    def load(self) -> int:
        ...

    def save_if_higher(self, score: int) -> bool:
        ...


class RollFilterProtocol(Protocol):
    def reset(self, baseline_roll: float) -> None:
        ...


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

    def __init__(self, config: GameConfig, score_store: ScoreStoreProtocol) -> None:
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

    def update_calibration(self, roll_deg: float, now_s: float, roll_filter: RollFilterProtocol) -> None:
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
