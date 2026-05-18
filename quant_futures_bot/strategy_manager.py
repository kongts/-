from __future__ import annotations

import pandas as pd

from .events import SignalEvent
from .selected_strategy import load_selected_strategy
from .strategies.altcoin_momentum_strategy import (
    ShortMomentumBreakoutStrategy,
    VolatilityExpansionBreakoutStrategy,
    VolumeBreakoutStrategy,
)
from .strategies.breakout_strategy import BreakoutStrategy
from .strategies.ma_strategy import MAStrategy
from .strategies.mean_reversion_strategy import MeanReversionStrategy
from .strategies.rsi_strategy import RSIStrategy
from .strategies.trend_filter_strategy import MovingAveragePullbackStrategy, RSIMomentumStrategy


class StrategyManager:
    def __init__(self, strategy_id: str | None = None, use_saved_selection: bool = True) -> None:
        self.strategies = self.build_strategies()
        self.use_saved_selection = use_saved_selection
        self.selected_payload = load_selected_strategy() if use_saved_selection else {"per_symbol": {}}
        self.strategy_id = strategy_id or self.selected_payload.get("strategy_id", "regime_ma_rsi")
        self.strategy_name = self.available_strategy_names().get(self.strategy_id, "Regime MA/RSI")

    def generate(self, symbol: str, df: pd.DataFrame, market_state: str, current_side: str) -> list[SignalEvent]:
        strategy_id = self.strategy_for_symbol(symbol)
        if strategy_id in self.strategies:
            return self.strategies[strategy_id].generate(symbol, df, current_side)
        if market_state == "trend":
            return self.strategies["ma_trend"].generate(symbol, df, current_side)
        return self.strategies["rsi_range"].generate(symbol, df, current_side)

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
        return list(StrategyManager.available_strategy_names())

    @staticmethod
    def available_strategy_names() -> dict[str, str]:
        return {
            "regime_ma_rsi": "Regime MA/RSI",
            "ma_trend": "MA Trend",
            "rsi_range": "RSI Range",
            "breakout_10": "Breakout 10",
            "breakout_20": "Breakout 20",
            "breakout_40": "Breakout 40",
            "breakout_80": "Breakout 80",
            "alt_momentum_6": "Alt Momentum Breakout 6",
            "alt_momentum_12": "Alt Momentum Breakout 12",
            "alt_momentum_24": "Alt Momentum Breakout 24",
            "alt_volume_breakout_12_1_5": "Alt Volume Breakout 12/1.5x",
            "alt_volume_breakout": "Alt Volume Breakout 20/2x",
            "alt_volume_breakout_30_3": "Alt Volume Breakout 30/3x",
            "alt_volatility_breakout_12_1_2": "Alt Volatility Expansion Breakout 12/1.2x",
            "alt_volatility_breakout": "Alt Volatility Expansion Breakout 20/1.5x",
            "alt_volatility_breakout_30_2": "Alt Volatility Expansion Breakout 30/2x",
            "ma_pullback_1": "MA Pullback 1%",
            "ma_pullback_2": "MA Pullback 2%",
            "rsi_momentum_55": "RSI Momentum 55/45",
            "rsi_momentum_60": "RSI Momentum 60/40",
            "mean_reversion_10_1_5": "Mean Reversion 10/1.5",
            "mean_reversion_20": "Mean Reversion 20/2",
            "mean_reversion_30": "Mean Reversion 30/2",
        }

    @staticmethod
    def build_strategies() -> dict[str, object]:
        return {
            "ma_trend": MAStrategy(),
            "rsi_range": RSIStrategy(),
            "breakout_10": BreakoutStrategy(10),
            "breakout_20": BreakoutStrategy(20),
            "breakout_40": BreakoutStrategy(40),
            "breakout_80": BreakoutStrategy(80),
            "alt_momentum_6": ShortMomentumBreakoutStrategy(6),
            "alt_momentum_12": ShortMomentumBreakoutStrategy(12),
            "alt_momentum_24": ShortMomentumBreakoutStrategy(24),
            "alt_volume_breakout_12_1_5": VolumeBreakoutStrategy(12, 1.5),
            "alt_volume_breakout": VolumeBreakoutStrategy(20, 2.0),
            "alt_volume_breakout_30_3": VolumeBreakoutStrategy(30, 3.0),
            "alt_volatility_breakout_12_1_2": VolatilityExpansionBreakoutStrategy(12, 1.2),
            "alt_volatility_breakout": VolatilityExpansionBreakoutStrategy(20, 1.5),
            "alt_volatility_breakout_30_2": VolatilityExpansionBreakoutStrategy(30, 2.0),
            "ma_pullback_1": MovingAveragePullbackStrategy(0.01),
            "ma_pullback_2": MovingAveragePullbackStrategy(0.02),
            "rsi_momentum_55": RSIMomentumStrategy(55, 45),
            "rsi_momentum_60": RSIMomentumStrategy(60, 40),
            "mean_reversion_10_1_5": MeanReversionStrategy(10, 1.5),
            "mean_reversion_20": MeanReversionStrategy(20, 2.0),
            "mean_reversion_30": MeanReversionStrategy(30, 2.0),
        }
