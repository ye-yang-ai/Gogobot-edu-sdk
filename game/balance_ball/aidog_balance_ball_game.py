"""Run the AIDog IMU balance ball game."""

from __future__ import annotations

from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from aidog_sdk.game.balance_ball.app import DEFAULT_SCORE_FILE, GAME_POSE_ACTION, GAME_ROOT, GAME_SCORE_DIR, build_reader, main, parse_args, run_game
from aidog_sdk.game.balance_ball.core import (
    BALL_RADIUS,
    MILESTONE_LABELS,
    REWARD_FOOD_TYPES,
    SCORE_MILESTONES,
    BalanceBallGame,
    GameConfig,
)
from aidog_sdk.game.balance_ball.input import (
    DANGER_EXPRESSION_NAME,
    FINISH_AUDIO_NAME,
    FINISH_EXPRESSION_NAME,
    REWARD_AUDIO_NAMES,
    REWARD_EXPRESSION_NAMES,
    START_AUDIO_NAME,
    START_EXPRESSION_NAME,
    BleImuReader,
    KeyboardRollReader,
    LatestRoll,
    RollFilter,
    RollFilterConfig,
    WsImuReader,
    clamp,
)
from aidog_sdk.game.balance_ball.pygame_renderer import (
    BALANCE_CENTER_Y_RATIO,
    BUTTON_ROW_TOP,
    CHALLENGE_BADGE_TOPRIGHT,
    GAME_ASSET_DIR,
    GAME_HEIGHT,
    GAME_WIDTH,
    GOGO_LOGO_FILE,
    PREPARE_BUTTON_LEFT,
    PIVOT_HALF_WIDTH,
    PIVOT_HEIGHT,
    RESTART_BUTTON_LEFT,
    CelebrationParticle,
    PygameRenderer,
)
from aidog_sdk.game.balance_ball.storage import ScoreStore


if __name__ == "__main__":
    raise SystemExit(main())
