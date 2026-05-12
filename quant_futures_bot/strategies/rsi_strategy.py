from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class RSIStrategy:
    name = "RSI Range"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if data.empty:
            return []
        curr = data.iloc[-1]
        price = float(curr["close"])
        trend_bias = float(curr["ma_short"] - curr["ma_long"])
        rsi = float(curr["rsi"])
        signals: list[SignalEvent] = []
        if rsi < 30 and trend_bias >= 0 and current_side != "LONG":
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, price))
        elif rsi > 70 and trend_bias <= 0 and current_side != "SHORT":
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, price))
        return signals

