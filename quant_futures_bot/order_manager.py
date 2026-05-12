from __future__ import annotations

from uuid import uuid4

from .events import OrderEvent, OrderStatus, SignalEvent, SignalType


class OrderManager:
    def __init__(self) -> None:
        self.orders: dict[str, OrderEvent] = {}

    def create_order(self, signal: SignalEvent, qty: float) -> OrderEvent:
        if signal.signal_type in {SignalType.OPEN_LONG, SignalType.CLOSE_SHORT}:
            side = "BUY"
        else:
            side = "SELL"
        order = OrderEvent(
            order_id=str(uuid4()),
            symbol=signal.symbol,
            side=side,
            position_action=signal.signal_type,
            qty=qty,
            price=signal.price,
            reduce_only=signal.signal_type in {SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT, SignalType.CLOSE_POSITION},
            status=OrderStatus.CREATED,
            timestamp=signal.timestamp,
        )
        self.orders[order.order_id] = order
        return order

    def update_status(self, order_id: str, status: OrderStatus) -> OrderEvent:
        old = self.orders[order_id]
        updated = OrderEvent(
            order_id=old.order_id,
            symbol=old.symbol,
            side=old.side,
            position_action=old.position_action,
            qty=old.qty,
            price=old.price,
            reduce_only=old.reduce_only,
            status=status,
            timestamp=old.timestamp,
        )
        self.orders[order_id] = updated
        return updated

