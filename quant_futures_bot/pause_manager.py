from __future__ import annotations

from dataclasses import dataclass

from . import config


@dataclass
class PauseManager:
    status: str = "RUNNING"
    reason: str = ""
    api_error_count: int = 0

    def can_open_new_position(self) -> bool:
        return self.status == "RUNNING"

    def allow_reduce_only(self) -> bool:
        return self.status in {"RUNNING", "PAUSED", "STOPPED"}

    def pause(self, reason: str) -> None:
        self.status = "PAUSED"
        self.reason = reason

    def stop(self, reason: str) -> None:
        self.status = "STOPPED"
        self.reason = reason

    def resume(self) -> None:
        self.status = "RUNNING"
        self.reason = ""

    def record_api_error(self) -> None:
        self.api_error_count += 1
        if self.api_error_count >= 5:
            self.stop("API errors >= 5")

    def check(self, portfolio, latest_rows: dict[str, object]) -> None:
        if portfolio.max_drawdown >= config.MAX_DRAWDOWN:
            self.pause("max drawdown reached")
        elif portfolio.daily_pnl <= -portfolio.peak_equity * config.MAX_DAILY_LOSS:
            self.pause("daily loss reached")
        elif portfolio.consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
            self.pause("consecutive losses reached")
        elif portfolio.recent_win_rate() < config.MIN_RECENT_WIN_RATE and len(portfolio.closed_trade_pnls) >= config.RECENT_TRADE_WINDOW:
            self.pause("recent win rate too low")
        for row in latest_rows.values():
            volatility = float(row.get("volatility", 0) or 0)
            mean = float(row.get("volatility_mean", 0) or 0)
            if mean > 0 and volatility > mean * config.ABNORMAL_VOLATILITY_MULTIPLIER:
                self.pause("abnormal volatility")
                break

