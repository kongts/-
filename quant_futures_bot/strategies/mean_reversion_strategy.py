from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class MeanReversionStrategy:
    def __init__(self, period: int = 20, z_entry: float = 2.0) -> None:
        self.period = period
        self.z_entry = z_entry
        self.name = f"Mean Reversion {period}/{z_entry:g}"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.copy()
        if len(data) < self.period + 2:
            return []
        data["mr_mid"] = data["close"].rolling(self.period).mean()
        data["mr_std"] = data["close"].rolling(self.period).std()
        data = data.dropna()
        if data.empty:
            return []
        curr = data.iloc[-1]
        price = float(curr["close"])
        mid = float(curr["mr_mid"])
        std = float(curr["mr_std"])
        if std <= 0:
            return []
        z_score = (price - mid) / std
        signals: list[SignalEvent] = []
        if current_side == "LONG" and price >= mid:
            signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
        elif current_side == "SHORT" and price <= mid:
            signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
        elif z_score <= -self.z_entry and current_side != "LONG":
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, price))
        elif z_score >= self.z_entry and current_side != "SHORT":
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, price))
        return signals
