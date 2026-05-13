from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class BreakoutStrategy:
    def __init__(self, lookback: int = 20) -> None:
        self.lookback = lookback
        self.name = f"Breakout {lookback}"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) <= self.lookback:
            return []
        curr = data.iloc[-1]
        history = data.iloc[-self.lookback - 1 : -1]
        upper = float(history["high"].max())
        lower = float(history["low"].min())
        price = float(curr["close"])
        signals: list[SignalEvent] = []
        if price > upper and current_side != "LONG":
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, price))
        elif price < lower and current_side != "SHORT":
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, price))
        return signals
