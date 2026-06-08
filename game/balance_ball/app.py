"""Application entry point for the AIDog IMU balance ball game."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from aidog_sdk.game.balance_ball.core import BalanceBallGame, GameConfig
from aidog_sdk.game.balance_ball.input import (
    BleImuReader,
    KeyboardRollReader,
    LatestRoll,
    RollFilter,
    RollFilterConfig,
    WsImuReader,
)
from aidog_sdk.game.balance_ball.pygame_renderer import GAME_HEIGHT, GAME_WIDTH, PygameRenderer
from aidog_sdk.game.balance_ball.storage import ScoreStore


GAME_ROOT = Path(__file__).resolve().parents[1]
GAME_SCORE_DIR = GAME_ROOT / "scores"
DEFAULT_SCORE_FILE = GAME_SCORE_DIR / "aidog_balance_ball_score.json"
GAME_POSE_ACTION = "slow_down"


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
    parser.add_argument("--name-prefix", default="Gogobot")
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
