from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class MovingAveragePullbackStrategy:
    def __init__(self, pullback_pct: float = 0.01) -> None:
        self.pullback_pct = pullback_pct
        self.name = f"MA Pullback {pullback_pct:.0%}"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if data.empty:
            return []
        curr = data.iloc[-1]
        price = float(curr["close"])
        ma_short = float(curr["ma_short"])
        ma_long = float(curr["ma_long"])
        signals: list[SignalEvent] = []
        if current_side == "LONG" and ma_short < ma_long:
            signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
        elif current_side == "SHORT" and ma_short > ma_long:
            signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
        elif ma_short > ma_long and price <= ma_short * (1 - self.pullback_pct) and current_side != "LONG":
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, price))
        elif ma_short < ma_long and price >= ma_short * (1 + self.pullback_pct) and current_side != "SHORT":
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, price))
        return signals


class RSIMomentumStrategy:
    def __init__(self, long_threshold: float = 55, short_threshold: float = 45) -> None:
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.name = f"RSI Momentum {long_threshold:g}/{short_threshold:g}"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) < 2:
            return []
        prev = data.iloc[-2]
        curr = data.iloc[-1]
        price = float(curr["close"])
        prev_rsi = float(prev["rsi"])
        rsi = float(curr["rsi"])
        ma_short = float(curr["ma_short"])
        ma_long = float(curr["ma_long"])
        signals: list[SignalEvent] = []
        if prev_rsi <= self.long_threshold < rsi and ma_short > ma_long and current_side != "LONG":
            if current_side == "SHORT":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, self.name, price))
        elif prev_rsi >= self.short_threshold > rsi and ma_short < ma_long and current_side != "SHORT":
            if current_side == "LONG":
                signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, self.name, price))
            signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, self.name, price))
        return signals
