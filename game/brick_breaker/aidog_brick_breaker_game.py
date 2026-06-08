"""Run the GOGO IMU brick breaker game."""

from __future__ import annotations

from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from aidog_sdk.game.brick_breaker.app import main


if __name__ == "__main__":
    raise SystemExit(main())
