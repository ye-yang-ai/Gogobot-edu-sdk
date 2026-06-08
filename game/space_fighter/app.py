"""Application entry point for the GOGO space fighter game."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from aidog_sdk.game.space_fighter.core import GAME_OVER, MENU, STAGE_CLEAR, SpaceFighterConfig, SpaceFighterGame
from aidog_sdk.game.space_fighter.pygame_renderer import PygameRenderer
from aidog_sdk.game.space_fighter.storage import ScoreStore


GAME_ROOT = Path(__file__).resolve().parents[1]
GAME_SCORE_DIR = GAME_ROOT / "scores"
DEFAULT_SCORE_FILE = GAME_SCORE_DIR / "aidog_space_fighter_score.json"


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GOGO space fighter game")
    parser.add_argument("--score-file", type=Path, default=DEFAULT_SCORE_FILE)
    return parser.parse_args(argv)


def run_game(args: argparse.Namespace) -> int:
    config = SpaceFighterConfig()
    score_store = ScoreStore(args.score_file)
    game = SpaceFighterGame(config, high_score=score_store.load())

    try:
        renderer = PygameRenderer(config.width, config.height)
    except ModuleNotFoundError as exc:
        if exc.name == "pygame":
            print("缺少 pygame，请先执行：python -m pip install pygame", file=sys.stderr)
            return 2
        raise

    pg = renderer.pygame
    running = True
    last_s = time.monotonic()
    saved_game_over_score = False
    saved_stage_score = False

    while running:
        now_s = time.monotonic()
        dt_s = now_s - last_s
        last_s = now_s
        move_x = 0.0
        move_y = 0.0

        for event in pg.event.get():
            if event.type == pg.QUIT:
                running = False
            elif event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    running = False
                elif event.key == pg.K_SPACE:
                    if game.state in (MENU, GAME_OVER):
                        game.start_game()
                        saved_game_over_score = False
                        saved_stage_score = False
                    elif game.state == STAGE_CLEAR:
                        game.start_next_stage()
                        saved_stage_score = False

        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            move_x -= 1.0
        if keys[pg.K_RIGHT] or keys[pg.K_d]:
            move_x += 1.0
        if keys[pg.K_UP] or keys[pg.K_w]:
            move_y -= 1.0
        if keys[pg.K_DOWN] or keys[pg.K_s]:
            move_y += 1.0

        game.update(dt_s, move_x, move_y)
        if game.state == GAME_OVER and not saved_game_over_score:
            score_store.save_if_higher(game.score)
            saved_game_over_score = True
        if game.state == STAGE_CLEAR and not saved_stage_score:
            score_store.save_if_higher(game.score)
            saved_stage_score = True

        renderer.draw(game)
        renderer.tick(60)

    pg.quit()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    return run_game(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
