from __future__ import annotations

from . import config
from .events import RiskEvent, SignalEvent, SignalType
from .symbol_config import get_symbol_config


class RiskEngine:
    def __init__(self, portfolio, pause_manager) -> None:
        self.portfolio = portfolio
        self.pause_manager = pause_manager

    def check_signal(self, signal: SignalEvent, latest_row: dict) -> RiskEvent:
        if not self._has_enough_data(latest_row):
            return RiskEvent(signal.symbol, False, "not enough data", signal)
        if self.portfolio.max_drawdown >= config.MAX_DRAWDOWN:
            return RiskEvent(signal.symbol, False, "max drawdown exceeded", signal)
        if self.portfolio.daily_pnl <= -self.portfolio.peak_equity * config.MAX_DAILY_LOSS:
            return RiskEvent(signal.symbol, False, "daily loss exceeded", signal)

        opening = signal.signal_type in {SignalType.OPEN_LONG, SignalType.OPEN_SHORT}
        current_side = self.portfolio.position_side(signal.symbol)
        if opening:
            if not self.pause_manager.can_open_new_position():
                return RiskEvent(signal.symbol, False, f"system {self.pause_manager.status}", signal)
            if self._is_same_direction_duplicate(signal, current_side):
                return RiskEvent(signal.symbol, False, "duplicate same-direction position", signal)
            symbol_cfg = get_symbol_config(signal.symbol)
            leverage = float(symbol_cfg["leverage"])
            if leverage > config.MAX_LEVERAGE:
                return RiskEvent(signal.symbol, False, "leverage exceeds max", signal)
            planned_margin = self.portfolio.equity * float(symbol_cfg["max_margin_ratio"])
            if planned_margin / max(self.portfolio.equity, 1) > float(symbol_cfg["max_margin_ratio"]):
                return RiskEvent(signal.symbol, False, "symbol margin ratio exceeded", signal)
            if (self.portfolio.used_margin + planned_margin) / max(self.portfolio.equity, 1) > config.MAX_TOTAL_MARGIN_RATIO:
                return RiskEvent(signal.symbol, False, "total margin ratio exceeded", signal)
            volatility = float(latest_row.get("volatility", 0) or 0)
            volatility_mean = float(latest_row.get("volatility_mean", 0) or 0)
            if volatility_mean > 0 and volatility > volatility_mean * config.ABNORMAL_VOLATILITY_MULTIPLIER:
                return RiskEvent(signal.symbol, False, "abnormal volatility", signal)
        elif not self.pause_manager.allow_reduce_only():
            return RiskEvent(signal.symbol, False, "reduce-only not allowed", signal)
        return RiskEvent(signal.symbol, True, "approved", signal)

    def order_quantity(self, signal: SignalEvent) -> float:
        pos = self.portfolio.get_position(signal.symbol)
        if signal.signal_type in {SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT, SignalType.CLOSE_POSITION}:
            return pos.qty
        symbol_cfg = get_symbol_config(signal.symbol)
        margin = self.portfolio.equity * float(symbol_cfg["max_margin_ratio"])
        notional = margin * float(symbol_cfg["leverage"])
        return round(notional / signal.price, 8)

    @staticmethod
    def _has_enough_data(latest_row: dict) -> bool:
        required = ["ma_short", "ma_long", "rsi", "volatility", "volatility_median"]
        return all(latest_row.get(key) == latest_row.get(key) for key in required)

    @staticmethod
    def _is_same_direction_duplicate(signal: SignalEvent, current_side: str) -> bool:
        return (
            signal.signal_type == SignalType.OPEN_LONG
            and current_side == "LONG"
            or signal.signal_type == SignalType.OPEN_SHORT
            and current_side == "SHORT"
        )

