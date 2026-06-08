"""Application entry point for the GOGO IMU brick breaker game."""

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


from aidog_sdk.game.brick_breaker.core import CALIBRATING, GAME_OVER, READY, WAIT_IMU, BrickBreakerConfig, BrickBreakerGame
from aidog_sdk.game.brick_breaker.input import (
    BleImuReader,
    KeyboardRollReader,
    LatestRoll,
    RollFilter,
    RollFilterConfig,
    RollToPaddleMapper,
    WsImuReader,
)
from aidog_sdk.game.brick_breaker.pygame_renderer import PygameRenderer
from aidog_sdk.game.brick_breaker.storage import ScoreStore


GAME_ROOT = Path(__file__).resolve().parents[1]
GAME_SCORE_DIR = GAME_ROOT / "scores"
DEFAULT_SCORE_FILE = GAME_SCORE_DIR / "aidog_brick_breaker_score.json"


def build_reader(args: argparse.Namespace, latest_roll: LatestRoll):
    if args.transport == "ws":
        return WsImuReader(latest_roll, args.bind, args.port, args.hz, args.pose_action)
    if args.transport == "ble":
        return BleImuReader(latest_roll, args.name_prefix, args.address, args.hz)
    return KeyboardRollReader(latest_roll)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GOGO IMU brick breaker game")
    parser.add_argument("--transport", choices=("ws", "ble", "keyboard"), default="ws")
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--name-prefix", default="Changba-Ai-Dog")
    parser.add_argument("--address", default=None)
    parser.add_argument("--hz", type=int, default=40)
    parser.add_argument("--dog-facing", choices=("user", "away"), default="user")
    parser.add_argument("--invert-roll", action="store_true")
    parser.add_argument("--sensitivity", type=float, default=1.0)
    parser.add_argument("--max-roll", type=float, default=18.0)
    parser.add_argument("--score-file", type=Path, default=DEFAULT_SCORE_FILE)
    parser.add_argument("--pose-action", default="slow_down")
    return parser.parse_args(argv)


def run_game(args: argparse.Namespace) -> int:
    game_config = BrickBreakerConfig()
    score_store = ScoreStore(args.score_file)
    game = BrickBreakerGame(game_config, high_score=score_store.load())

    try:
        renderer = PygameRenderer(game_config.width, game_config.height)
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
            max_roll_deg=args.max_roll,
            invert=invert_roll,
        )
    )
    mapper = RollToPaddleMapper(game_config.width, game_config.paddle_width, max_roll_deg=args.max_roll)
    calibration_samples: list[float] = []
    calibration_started_s = 0.0
    last_high_score = game.high_score

    try:
        reader.start()
    except Exception as exc:
        print(f"IMU 输入启动失败：{exc}", file=sys.stderr)
        return 1

    pg = renderer.pygame
    running = True
    last_s = time.monotonic()
    last_control_roll = 0.0

    def run_reader_action_async(action_name: str) -> None:
        action = getattr(reader, action_name, None)
        if not callable(action):
            return
        threading.Thread(target=action, daemon=True, name=f"aidog-brick-{action_name}").start()

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
                        game.start_calibration()
                        calibration_samples.clear()
                        calibration_started_s = now_s
                    elif event.key == pg.K_SPACE:
                        if game.state == READY:
                            game.start_running()
                        elif game.state == GAME_OVER:
                            game.ready()
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
                        game.enter_wait_imu()
                    elif pressed == "prepare" and renderer.prepare_button_rect.collidepoint(event.pos):
                        run_reader_action_async("prepare_now")
                        renderer.set_button_feedback("已重新发送准备指令", now_s)

            roll, roll_time_s = latest_roll.snapshot()
            imu_ok = game.has_valid_imu(roll_time_s, now_s)
            if not imu_ok:
                if game.state != WAIT_IMU:
                    game.enter_wait_imu()
                paddle_center_x = mapper.map(0.0)
                last_control_roll = 0.0
            elif roll is not None:
                if game.state == WAIT_IMU:
                    game.start_calibration()
                    calibration_samples.clear()
                    calibration_started_s = now_s
                if game.state == CALIBRATING:
                    calibration_samples.append(float(roll))
                    if now_s - calibration_started_s >= 1.0 and len(calibration_samples) >= 8:
                        roll_filter.reset(sum(calibration_samples) / len(calibration_samples))
                        game.ready()
                last_control_roll = roll_filter.update(roll)
                paddle_center_x = mapper.map(last_control_roll)
            else:
                paddle_center_x = mapper.map(0.0)

            game.update(dt_s, paddle_center_x)
            if game.state == GAME_OVER and game.high_score > last_high_score:
                if score_store.save_if_higher(game.high_score):
                    last_high_score = game.high_score
            renderer.draw(game, last_control_roll, imu_ok)
            renderer.tick(60)
    finally:
        reader.stop()
        pg.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    return run_game(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
