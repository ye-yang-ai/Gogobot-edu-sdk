"""Application entry point for the GOGO space fighter game."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from aidog_sdk.game.space_fighter.core import GAME_OVER, MENU, STAGE_CLEAR, SpaceFighterConfig, SpaceFighterGame
from aidog_sdk.game.space_fighter.input import (
    INPUT_AIDOG,
    INPUT_KEYBOARD,
    ImuControlConfig,
    ImuMoveMapper,
    LatestImuAngles,
    WsImuReader,
    imu_status,
    merge_keyboard_and_imu,
    read_imu_move,
)
from aidog_sdk.game.space_fighter.pygame_renderer import PygameRenderer
from aidog_sdk.game.space_fighter.storage import ScoreStore


GAME_ROOT = Path(__file__).resolve().parents[1]
GAME_SCORE_DIR = GAME_ROOT / "scores"
DEFAULT_SCORE_FILE = GAME_SCORE_DIR / "aidog_space_fighter_score.json"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GOGO space fighter game")
    parser.add_argument("--score-file", type=Path, default=DEFAULT_SCORE_FILE)
    parser.add_argument("--imu", choices=("off", "ws"), default="off", help="Initial robot IMU control mode")
    parser.add_argument("--ws-bind", default="0.0.0.0", help="WebSocket listen address")
    parser.add_argument("--ws-port", type=int, default=8766, help="WebSocket listen port")
    parser.add_argument("--imu-hz", type=int, default=50, help="Requested IMU stream rate")
    parser.add_argument("--imu-deadzone", type=float, default=1.5, help="Tilt deadzone in degrees")
    parser.add_argument("--imu-sensitivity", type=float, default=1.0, help="Tilt sensitivity multiplier")
    parser.add_argument("--imu-max-tilt", type=float, default=18.0, help="Tilt mapped to full movement")
    parser.add_argument("--dog-facing", choices=("user", "away"), default="user", help="Robot facing direction for roll mapping")
    parser.add_argument("--invert-pitch", action="store_true", help="Invert pitch movement")
    parser.add_argument("--invert-roll", action="store_true", help="Invert roll movement")
    parser.add_argument("--pose-action", default="slow_down", help="Robot prepare pose action when using AIDOG IMU")
    return parser.parse_args(argv)


def run_game(args: argparse.Namespace) -> int:
    config = SpaceFighterConfig()
    score_store = ScoreStore(args.score_file)
    game = SpaceFighterGame(config, high_score=score_store.load())

    try:
        renderer = PygameRenderer(config.width, config.height)
    except ModuleNotFoundError as exc:
        if exc.name == "pygame":
            print("Missing pygame. Please run: python -m pip install pygame", file=sys.stderr)
            return 2
        raise

    pg = renderer.pygame
    latest_angles = LatestImuAngles()
    imu_mapper = _build_imu_mapper(args)
    imu_reader: Optional[WsImuReader] = None
    input_mode = INPUT_AIDOG if args.imu == "ws" else INPUT_KEYBOARD
    running = True
    last_s = time.monotonic()
    saved_game_over_score = False
    saved_stage_score = False
    ws_lock = threading.Lock()
    ws_starting = False

    def start_ws_async(restart: bool = False) -> None:
        nonlocal imu_reader, ws_starting
        with ws_lock:
            if ws_starting:
                return
            if imu_reader is not None and not restart:
                return
            ws_starting = True

        def worker() -> None:
            nonlocal imu_reader, ws_starting
            try:
                if restart and imu_reader is not None:
                    imu_reader.restart()
                else:
                    reader = WsImuReader(latest_angles, args.ws_bind, args.ws_port, max(1, min(200, args.imu_hz)), args.pose_action)
                    reader.start()
                    imu_reader = reader
                renderer.set_button_feedback("WS LISTENING", time.monotonic())
            except Exception as exc:
                renderer.set_button_feedback("WS START FAILED", time.monotonic())
                print(f"IMU WebSocket failed: {exc}", file=sys.stderr)
            finally:
                with ws_lock:
                    ws_starting = False

        threading.Thread(target=worker, daemon=True, name="aidog-space-fighter-ws-start").start()

    def prepare_dog_async() -> None:
        def worker() -> None:
            reader = imu_reader
            if reader is None:
                renderer.set_button_feedback("WAIT DOG", time.monotonic())
                return
            ok = reader.prepare_now()
            renderer.set_button_feedback("DOG DOWN SENT" if ok else "WAIT DOG", time.monotonic())

        threading.Thread(target=worker, daemon=True, name="aidog-space-fighter-prepare").start()

    if input_mode == INPUT_AIDOG:
        start_ws_async()

    try:
        while running:
            now_s = time.monotonic()
            dt_s = now_s - last_s
            last_s = now_s
            current_imu_status = "STARTING" if ws_starting else imu_status(latest_angles, imu_mapper, imu_reader)

            mouse_pos = pg.mouse.get_pos()
            mouse_over_button = (
                game.state == MENU
                and (
                    renderer.keyboard_button_rect.collidepoint(mouse_pos)
                    or renderer.aidog_button_rect.collidepoint(mouse_pos)
                    or (input_mode == INPUT_AIDOG and renderer.prepare_dog_button_rect.collidepoint(mouse_pos))
                )
            ) or (
                input_mode == INPUT_AIDOG
                and game.state != MENU
                and (renderer.restart_ws_button_rect.collidepoint(mouse_pos) or renderer.recalibrate_button_rect.collidepoint(mouse_pos))
            )
            pg.mouse.set_cursor(pg.SYSTEM_CURSOR_HAND if mouse_over_button else pg.SYSTEM_CURSOR_ARROW)

            for event in pg.event.get():
                if event.type == pg.QUIT:
                    running = False
                elif event.type == pg.KEYDOWN:
                    if event.key == pg.K_ESCAPE:
                        running = False
                    elif event.key == pg.K_SPACE:
                        if game.state in (MENU, GAME_OVER):
                            if input_mode == INPUT_AIDOG:
                                start_ws_async()
                            game.start_game()
                            saved_game_over_score = False
                            saved_stage_score = False
                        elif game.state == STAGE_CLEAR:
                            game.start_next_stage()
                            saved_stage_score = False
                    elif event.key == pg.K_r and input_mode == INPUT_AIDOG:
                        imu_mapper.clear_baseline()
                        renderer.set_button_feedback("RECALIBRATED", now_s)
                elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                    if game.state == MENU:
                        if renderer.keyboard_button_rect.collidepoint(event.pos):
                            input_mode = INPUT_KEYBOARD
                            renderer.pressed_button = "keyboard"
                        elif renderer.aidog_button_rect.collidepoint(event.pos):
                            input_mode = INPUT_AIDOG
                            renderer.pressed_button = "aidog"
                            start_ws_async()
                        elif input_mode == INPUT_AIDOG and renderer.prepare_dog_button_rect.collidepoint(event.pos):
                            renderer.pressed_button = "prepare_dog"
                    elif input_mode == INPUT_AIDOG:
                        if renderer.restart_ws_button_rect.collidepoint(event.pos):
                            renderer.pressed_button = "restart_ws"
                        elif renderer.recalibrate_button_rect.collidepoint(event.pos):
                            renderer.pressed_button = "recalibrate"
                elif event.type == pg.MOUSEBUTTONUP and event.button == 1:
                    pressed = renderer.pressed_button
                    renderer.pressed_button = None
                    if pressed == "prepare_dog" and renderer.prepare_dog_button_rect.collidepoint(event.pos):
                        prepare_dog_async()
                    elif pressed == "restart_ws" and renderer.restart_ws_button_rect.collidepoint(event.pos):
                        latest_angles.clear()
                        imu_mapper.clear_baseline()
                        start_ws_async(restart=True)
                    elif pressed == "recalibrate" and renderer.recalibrate_button_rect.collidepoint(event.pos):
                        imu_mapper.clear_baseline()
                        renderer.set_button_feedback("RECALIBRATED", now_s)

            keyboard_x, keyboard_y = _read_keyboard_move(pg)
            imu_x, imu_y, imu_active = read_imu_move(latest_angles, imu_mapper) if input_mode == INPUT_AIDOG else (0.0, 0.0, False)
            move_x, move_y = merge_keyboard_and_imu(keyboard_x, keyboard_y, imu_x, imu_y, imu_active)

            game.update(dt_s, move_x, move_y)
            if game.state == GAME_OVER and not saved_game_over_score:
                score_store.save_if_higher(game.score)
                saved_game_over_score = True
            if game.state == STAGE_CLEAR and not saved_stage_score:
                score_store.save_if_higher(game.score)
                saved_stage_score = True

            renderer.draw(game, input_mode, current_imu_status)
            renderer.tick(60)
    finally:
        if imu_reader is not None:
            imu_reader.stop()
        pg.quit()
    return 0


def _read_keyboard_move(pg) -> Tuple[float, float]:
    move_x = 0.0
    move_y = 0.0
    keys = pg.key.get_pressed()
    if keys[pg.K_LEFT] or keys[pg.K_a]:
        move_x -= 1.0
    if keys[pg.K_RIGHT] or keys[pg.K_d]:
        move_x += 1.0
    if keys[pg.K_UP] or keys[pg.K_w]:
        move_y -= 1.0
    if keys[pg.K_DOWN] or keys[pg.K_s]:
        move_y += 1.0
    return move_x, move_y


def _build_imu_mapper(args: argparse.Namespace) -> ImuMoveMapper:
    return ImuMoveMapper(
        ImuControlConfig(
            deadzone_deg=max(0.0, args.imu_deadzone),
            sensitivity=max(0.1, args.imu_sensitivity),
            max_tilt_deg=max(1.0, args.imu_max_tilt),
            invert_pitch=args.invert_pitch,
            invert_roll=(args.dog_facing == "user") ^ bool(args.invert_roll),
        )
    )


def main(argv: Optional[list[str]] = None) -> int:
    return run_game(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
