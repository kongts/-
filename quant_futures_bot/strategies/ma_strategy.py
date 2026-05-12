from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class MAStrategy:
    name = "MA Trend"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) < 2:
            return []
        prev = data.iloc[-2]
        curr = data.iloc[-1]
        signals: list[SignalEvent] = []
        if prev["ma_short"] <= prev["ma_long"] and curr["ma_short"] > curr["ma_long"]:
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, float(curr["close"])))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, float(curr["close"])))
        elif prev["ma_short"] >= prev["ma_long"] and curr["ma_short"] < curr["ma_long"]:
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, float(curr["close"])))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, float(curr["close"])))
        return signals

