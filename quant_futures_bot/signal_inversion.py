from __future__ import annotations

from .events import SignalEvent, SignalType


INVERTED_SIGNAL_TYPES = {
    SignalType.OPEN_LONG: SignalType.OPEN_SHORT,
    SignalType.OPEN_SHORT: SignalType.OPEN_LONG,
    SignalType.CLOSE_LONG: SignalType.CLOSE_SHORT,
    SignalType.CLOSE_SHORT: SignalType.CLOSE_LONG,
}


def opposite_position_side(side: str) -> str:
    if side == "LONG":
        return "SHORT"
    if side == "SHORT":
        return "LONG"
    return side


def invert_signal(signal: SignalEvent) -> SignalEvent:
    inverted_type = INVERTED_SIGNAL_TYPES.get(signal.signal_type, signal.signal_type)
    if inverted_type == signal.signal_type:
        return signal
    strategy_name = signal.strategy_name
    if "Inverted" not in strategy_name:
        strategy_name = f"Inverted {strategy_name}"
    return SignalEvent(
        signal.symbol,
        inverted_type,
        strategy_name,
        signal.price,
        timestamp=signal.timestamp,
    )


def invert_signals(signals: list[SignalEvent]) -> list[SignalEvent]:
    return [invert_signal(signal) for signal in signals]
