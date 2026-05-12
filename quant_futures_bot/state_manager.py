from __future__ import annotations

import json
from pathlib import Path

from . import config
from .pause_manager import PauseManager
from .portfolio import Portfolio


class StateManager:
    def __init__(self, path: Path = config.STATE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> tuple[Portfolio, PauseManager]:
        if not self.path.exists():
            return Portfolio(), PauseManager()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        portfolio = Portfolio.from_dict(data.get("portfolio", {}))
        pause = PauseManager(
            status=data.get("system_status", "RUNNING"),
            reason=data.get("pause_reason", ""),
            api_error_count=int(data.get("api_error_count", 0)),
        )
        return portfolio, pause

    def save(self, portfolio: Portfolio, pause_manager: PauseManager) -> None:
        payload = {
            "portfolio": portfolio.to_dict(),
            "system_status": pause_manager.status,
            "pause_reason": pause_manager.reason,
            "consecutive_losses": portfolio.consecutive_losses,
            "api_error_count": pause_manager.api_error_count,
            "max_drawdown": portfolio.max_drawdown,
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

