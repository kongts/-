from __future__ import annotations

import pandas as pd

from .events import SignalEvent
from .strategies.ma_strategy import MAStrategy
from .strategies.rsi_strategy import RSIStrategy


class StrategyManager:
    def __init__(self) -> None:
        self.ma_strategy = MAStrategy()
        self.rsi_strategy = RSIStrategy()

    def generate(self, symbol: str, df: pd.DataFrame, market_state: str, current_side: str) -> list[SignalEvent]:
        if market_state == "trend":
            return self.ma_strategy.generate(symbol, df, current_side)
        return self.rsi_strategy.generate(symbol, df, current_side)

