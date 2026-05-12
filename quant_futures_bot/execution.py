from __future__ import annotations

from . import config
from .events import FillEvent, OrderEvent, SignalType


class PaperExecution:
    def __init__(self, fee_rate: float = config.FEE_RATE, slippage_rate: float = config.SLIPPAGE_RATE) -> None:
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate

    def execute(self, order: OrderEvent) -> FillEvent:
        fill_price = self._slipped_price(order.position_action, order.price)
        notional = fill_price * order.qty
        fee = notional * self.fee_rate
        slippage = abs(fill_price - order.price)
        return FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            fill_price=fill_price,
            qty=order.qty,
            fee=fee,
            slippage=slippage,
            position_action=order.position_action,
            timestamp=order.timestamp,
        )

    def _slipped_price(self, action: SignalType, price: float) -> float:
        if action == SignalType.OPEN_LONG:
            return price * (1 + self.slippage_rate)
        if action == SignalType.CLOSE_LONG:
            return price * (1 - self.slippage_rate)
        if action == SignalType.OPEN_SHORT:
            return price * (1 - self.slippage_rate)
        if action in {SignalType.CLOSE_SHORT, SignalType.CLOSE_POSITION}:
            return price * (1 + self.slippage_rate)
        return price

