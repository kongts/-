from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"
    RISK = "RISK"
    PAUSE = "PAUSE"
    ERROR = "ERROR"


class SignalType(str, Enum):
    OPEN_LONG = "OPEN_LONG"
    CLOSE_LONG = "CLOSE_LONG"
    OPEN_SHORT = "OPEN_SHORT"
    CLOSE_SHORT = "CLOSE_SHORT"
    CLOSE_POSITION = "CLOSE_POSITION"


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Event:
    type: EventType
    timestamp: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class MarketEvent(Event):
    symbol: str = ""
    price: float = 0.0
    dataframe: Any = None

    def __init__(self, symbol: str, price: float, dataframe: Any, timestamp: datetime | None = None):
        object.__setattr__(self, "type", EventType.MARKET)
        object.__setattr__(self, "timestamp", timestamp or utc_now())
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "dataframe", dataframe)


@dataclass(frozen=True)
class SignalEvent(Event):
    symbol: str = ""
    signal_type: SignalType = SignalType.CLOSE_POSITION
    strategy_name: str = ""
    price: float = 0.0

    def __init__(
        self,
        symbol: str,
        signal_type: SignalType,
        strategy_name: str,
        price: float,
        timestamp: datetime | None = None,
    ):
        object.__setattr__(self, "type", EventType.SIGNAL)
        object.__setattr__(self, "timestamp", timestamp or utc_now())
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "signal_type", signal_type)
        object.__setattr__(self, "strategy_name", strategy_name)
        object.__setattr__(self, "price", price)


@dataclass(frozen=True)
class OrderEvent(Event):
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    position_action: SignalType = SignalType.CLOSE_POSITION
    qty: float = 0.0
    price: float = 0.0
    reduce_only: bool = False
    status: OrderStatus = OrderStatus.CREATED

    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        position_action: SignalType,
        qty: float,
        price: float,
        reduce_only: bool = False,
        status: OrderStatus = OrderStatus.CREATED,
        timestamp: datetime | None = None,
    ):
        object.__setattr__(self, "type", EventType.ORDER)
        object.__setattr__(self, "timestamp", timestamp or utc_now())
        object.__setattr__(self, "order_id", order_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "position_action", position_action)
        object.__setattr__(self, "qty", qty)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "reduce_only", reduce_only)
        object.__setattr__(self, "status", status)


@dataclass(frozen=True)
class FillEvent(Event):
    order_id: str = ""
    symbol: str = ""
    fill_price: float = 0.0
    qty: float = 0.0
    fee: float = 0.0
    slippage: float = 0.0
    position_action: SignalType = SignalType.CLOSE_POSITION
    exchange_order_id: str = ""

    def __init__(
        self,
        order_id: str,
        symbol: str,
        fill_price: float,
        qty: float,
        fee: float,
        slippage: float,
        position_action: SignalType,
        exchange_order_id: str = "",
        timestamp: datetime | None = None,
    ):
        object.__setattr__(self, "type", EventType.FILL)
        object.__setattr__(self, "timestamp", timestamp or utc_now())
        object.__setattr__(self, "order_id", order_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "fill_price", fill_price)
        object.__setattr__(self, "qty", qty)
        object.__setattr__(self, "fee", fee)
        object.__setattr__(self, "slippage", slippage)
        object.__setattr__(self, "position_action", position_action)
        object.__setattr__(self, "exchange_order_id", exchange_order_id)


@dataclass(frozen=True)
class RiskEvent(Event):
    symbol: str = ""
    approved: bool = False
    reason: str = ""
    signal: SignalEvent | None = None

    def __init__(self, symbol: str, approved: bool, reason: str, signal: SignalEvent | None = None):
        object.__setattr__(self, "type", EventType.RISK)
        object.__setattr__(self, "timestamp", utc_now())
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "approved", approved)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "signal", signal)


@dataclass(frozen=True)
class PauseEvent(Event):
    status: str = ""
    reason: str = ""

    def __init__(self, status: str, reason: str):
        object.__setattr__(self, "type", EventType.PAUSE)
        object.__setattr__(self, "timestamp", utc_now())
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)


@dataclass(frozen=True)
class ErrorEvent(Event):
    source: str = ""
    message: str = ""

    def __init__(self, source: str, message: str):
        object.__setattr__(self, "type", EventType.ERROR)
        object.__setattr__(self, "timestamp", utc_now())
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "message", message)
