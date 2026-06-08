"""Score persistence for the AIDog balance ball game."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class ScoreStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> int:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return max(0, int(data.get("high_score", 0)))
        except Exception:
            return 0

    def save_if_higher(self, score: int) -> bool:
        current = self.load()
        if int(score) <= current:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "high_score": int(score),
            "updated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
