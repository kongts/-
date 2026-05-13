from __future__ import annotations

import pandas as pd

from .events import SignalEvent
from .selected_strategy import load_selected_strategy
from .strategies.breakout_strategy import BreakoutStrategy
from .strategies.ma_strategy import MAStrategy
from .strategies.mean_reversion_strategy import MeanReversionStrategy
from .strategies.rsi_strategy import RSIStrategy


class StrategyManager:
    def __init__(self, strategy_id: str | None = None, use_saved_selection: bool = True) -> None:
        self.ma_strategy = MAStrategy()
        self.rsi_strategy = RSIStrategy()
        self.breakout_20 = BreakoutStrategy(20)
        self.breakout_40 = BreakoutStrategy(40)
        self.mean_reversion_20 = MeanReversionStrategy(20, 2.0)
        self.mean_reversion_30 = MeanReversionStrategy(30, 2.0)
        self.use_saved_selection = use_saved_selection
        self.selected_payload = load_selected_strategy() if use_saved_selection else {"per_symbol": {}}
        self.strategy_id = strategy_id or self.selected_payload.get("strategy_id", "regime_ma_rsi")
        self.strategy_name = self.available_strategy_names().get(self.strategy_id, "Regime MA/RSI")

    def generate(self, symbol: str, df: pd.DataFrame, market_state: str, current_side: str) -> list[SignalEvent]:
        strategy_id = self.strategy_for_symbol(symbol)
        if strategy_id == "ma_trend":
            return self.ma_strategy.generate(symbol, df, current_side)
        if strategy_id == "rsi_range":
            return self.rsi_strategy.generate(symbol, df, current_side)
        if strategy_id == "breakout_20":
            return self.breakout_20.generate(symbol, df, current_side)
        if strategy_id == "breakout_40":
            return self.breakout_40.generate(symbol, df, current_side)
        if strategy_id == "mean_reversion_20":
            return self.mean_reversion_20.generate(symbol, df, current_side)
        if strategy_id == "mean_reversion_30":
            return self.mean_reversion_30.generate(symbol, df, current_side)
        if market_state == "trend":
            return self.ma_strategy.generate(symbol, df, current_side)
        return self.rsi_strategy.generate(symbol, df, current_side)

    def strategy_for_symbol(self, symbol: str) -> str:
        if not self.use_saved_selection:
            return self.strategy_id
        per_symbol = self.selected_payload.get("per_symbol", {})
        if symbol in per_symbol:
            return per_symbol[symbol].get("strategy_id", self.strategy_id)
        return self.strategy_id

    def strategy_label_for_symbol(self, symbol: str) -> str:
        strategy_id = self.strategy_for_symbol(symbol)
        return self.available_strategy_names().get(strategy_id, strategy_id)

    def timeframe_for_symbol(self, symbol: str, default: str = "1h") -> str:
        per_symbol = self.selected_payload.get("per_symbol", {})
        if symbol in per_symbol:
            return per_symbol[symbol].get("timeframe", default)
        return self.selected_payload.get("timeframe", default)

    @staticmethod
    def candidate_ids() -> list[str]:
        return [
            "regime_ma_rsi",
            "ma_trend",
            "rsi_range",
            "breakout_20",
            "breakout_40",
            "mean_reversion_20",
            "mean_reversion_30",
        ]

    @staticmethod
    def available_strategy_names() -> dict[str, str]:
        return {
            "regime_ma_rsi": "Regime MA/RSI",
            "ma_trend": "MA Trend",
            "rsi_range": "RSI Range",
            "breakout_20": "Breakout 20",
            "breakout_40": "Breakout 40",
            "mean_reversion_20": "Mean Reversion 20/2",
            "mean_reversion_30": "Mean Reversion 30/2",
        }
