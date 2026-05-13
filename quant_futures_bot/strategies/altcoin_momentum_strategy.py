from __future__ import annotations

import pandas as pd

from ..events import SignalEvent, SignalType


class ShortMomentumBreakoutStrategy:
    def __init__(self, lookback: int = 12) -> None:
        self.lookback = lookback
        self.name = f"Short Momentum Breakout {lookback}"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) <= self.lookback:
            return []
        curr = data.iloc[-1]
        history = data.iloc[-self.lookback - 1 : -1]
        upper = float(history["high"].max())
        lower = float(history["low"].min())
        price = float(curr["close"])
        return breakout_signals(symbol, self.name, price, upper, lower, current_side)


class VolumeBreakoutStrategy:
    def __init__(self, lookback: int = 20, volume_multiplier: float = 2.0) -> None:
        self.lookback = lookback
        self.volume_multiplier = volume_multiplier
        self.name = f"Volume Breakout {lookback}/{volume_multiplier:g}x"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) <= self.lookback:
            return []
        curr = data.iloc[-1]
        history = data.iloc[-self.lookback - 1 : -1]
        avg_volume = float(history["volume"].mean())
        curr_volume = float(curr["volume"])
        if avg_volume <= 0 or curr_volume < avg_volume * self.volume_multiplier:
            return []
        upper = float(history["high"].max())
        lower = float(history["low"].min())
        price = float(curr["close"])
        return breakout_signals(symbol, self.name, price, upper, lower, current_side)


class VolatilityExpansionBreakoutStrategy:
    def __init__(self, lookback: int = 20, volatility_multiplier: float = 1.5) -> None:
        self.lookback = lookback
        self.volatility_multiplier = volatility_multiplier
        self.name = f"Volatility Expansion Breakout {lookback}/{volatility_multiplier:g}x"

    def generate(self, symbol: str, df: pd.DataFrame, current_side: str = "FLAT") -> list[SignalEvent]:
        data = df.dropna()
        if len(data) <= self.lookback:
            return []
        curr = data.iloc[-1]
        history = data.iloc[-self.lookback - 1 : -1]
        volatility = float(curr.get("volatility", 0) or 0)
        volatility_mean = float(curr.get("volatility_mean", 0) or 0)
        if volatility_mean <= 0 or volatility < volatility_mean * self.volatility_multiplier:
            return []
        upper = float(history["high"].max())
        lower = float(history["low"].min())
        price = float(curr["close"])
        return breakout_signals(symbol, self.name, price, upper, lower, current_side)


def breakout_signals(
    symbol: str,
    strategy_name: str,
    price: float,
    upper: float,
    lower: float,
    current_side: str,
) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    if price > upper and current_side != "LONG":
        if current_side == "SHORT":
            signals.append(SignalEvent(symbol, SignalType.CLOSE_SHORT, strategy_name, price))
        signals.append(SignalEvent(symbol, SignalType.OPEN_LONG, strategy_name, price))
    elif price < lower and current_side != "SHORT":
        if current_side == "LONG":
            signals.append(SignalEvent(symbol, SignalType.CLOSE_LONG, strategy_name, price))
        signals.append(SignalEvent(symbol, SignalType.OPEN_SHORT, strategy_name, price))
    return signals
