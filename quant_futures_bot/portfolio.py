from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .config import INITIAL_CASH, RECENT_TRADE_WINDOW
from .events import FillEvent, SignalType


@dataclass
class Position:
    symbol: str
    position_side: str = "FLAT"
    entry_price: float = 0.0
    qty: float = 0.0
    margin_used: float = 0.0
    notional_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_time: str = ""

    def is_open(self) -> bool:
        return self.position_side in {"LONG", "SHORT"} and self.qty > 0


class Portfolio:
    def __init__(self, initial_cash: float = INITIAL_CASH) -> None:
        self.cash = initial_cash
        self.equity = initial_cash
        self.available_balance = initial_cash
        self.used_margin = 0.0
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.peak_equity = initial_cash
        self.max_drawdown = 0.0
        self.daily_pnl = 0.0
        self.positions: dict[str, Position] = {}
        self.closed_trade_pnls: list[float] = []
        self.consecutive_losses = 0

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def position_side(self, symbol: str) -> str:
        return self.get_position(symbol).position_side

    def update_market_price(self, symbol: str, price: float) -> None:
        pos = self.get_position(symbol)
        if not pos.is_open():
            pos.unrealized_pnl = 0.0
        elif pos.position_side == "LONG":
            pos.unrealized_pnl = (price - pos.entry_price) * pos.qty
        else:
            pos.unrealized_pnl = (pos.entry_price - price) * pos.qty
        self.recalculate()

    def apply_fill(self, fill: FillEvent, leverage: float) -> float:
        pos = self.get_position(fill.symbol)
        action = fill.position_action
        pnl = 0.0
        notional = fill.fill_price * fill.qty
        if action == SignalType.OPEN_LONG:
            self._open_position(pos, "LONG", fill.fill_price, fill.qty, notional / leverage, fill.timestamp)
        elif action == SignalType.OPEN_SHORT:
            self._open_position(pos, "SHORT", fill.fill_price, fill.qty, notional / leverage, fill.timestamp)
        elif action in {SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT, SignalType.CLOSE_POSITION}:
            pnl = self._close_position(pos, fill.fill_price, fill.qty)
        self.cash -= fill.fee
        self.realized_pnl += pnl - fill.fee
        self.daily_pnl += pnl - fill.fee
        self._record_closed_trade(pnl - fill.fee, action)
        self.recalculate()
        return pnl - fill.fee

    def _open_position(self, pos: Position, side: str, price: float, qty: float, margin: float, timestamp: datetime) -> None:
        pos.position_side = side
        pos.entry_price = price
        pos.qty = qty
        pos.margin_used = margin
        pos.notional_value = price * qty
        pos.unrealized_pnl = 0.0
        pos.open_time = timestamp.isoformat()

    def _close_position(self, pos: Position, price: float, qty: float) -> float:
        if not pos.is_open():
            return 0.0
        close_qty = min(qty, pos.qty)
        if pos.position_side == "LONG":
            pnl = (price - pos.entry_price) * close_qty
        else:
            pnl = (pos.entry_price - price) * close_qty
        pos.realized_pnl += pnl
        pos.qty -= close_qty
        if pos.qty <= 1e-12:
            pos.position_side = "FLAT"
            pos.entry_price = 0.0
            pos.qty = 0.0
            pos.margin_used = 0.0
            pos.notional_value = 0.0
            pos.unrealized_pnl = 0.0
            pos.open_time = ""
        else:
            pos.notional_value = pos.qty * price
        return pnl

    def _record_closed_trade(self, pnl: float, action: SignalType) -> None:
        if action not in {SignalType.CLOSE_LONG, SignalType.CLOSE_SHORT, SignalType.CLOSE_POSITION}:
            return
        self.closed_trade_pnls.append(pnl)
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else 0

    def recalculate(self) -> None:
        self.used_margin = sum(pos.margin_used for pos in self.positions.values())
        self.unrealized_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
        self.equity = self.cash + self.realized_pnl + self.unrealized_pnl
        self.available_balance = self.equity - self.used_margin
        self.peak_equity = max(self.peak_equity, self.equity)
        if self.peak_equity > 0:
            self.max_drawdown = max(self.max_drawdown, (self.peak_equity - self.equity) / self.peak_equity)

    def sync_from_exchange(self, account: dict) -> None:
        synced_equity = float(account.get("equity", self.equity))
        fresh_default_state = (
            abs(self.cash - INITIAL_CASH) < 1e-9
            and abs(self.equity - INITIAL_CASH) < 1e-9
            and abs(self.peak_equity - INITIAL_CASH) < 1e-9
            and self.max_drawdown == 0.0
            and self.realized_pnl == 0.0
            and self.daily_pnl == 0.0
            and not self.closed_trade_pnls
        )
        self.cash = float(account.get("cash", self.cash))
        self.equity = synced_equity
        self.available_balance = float(account.get("available_balance", self.available_balance))
        self.used_margin = float(account.get("used_margin", self.used_margin))
        self.unrealized_pnl = float(account.get("unrealized_pnl", self.unrealized_pnl))
        if fresh_default_state and self.equity > 0:
            self.peak_equity = self.equity
            self.max_drawdown = 0.0
        else:
            self.peak_equity = max(self.peak_equity, self.equity)
        if self.peak_equity > 0:
            self.max_drawdown = max(self.max_drawdown, (self.peak_equity - self.equity) / self.peak_equity)
        exchange_positions = account.get("positions", {})
        for symbol, payload in exchange_positions.items():
            pos = self.get_position(symbol)
            pos.position_side = payload["position_side"]
            pos.entry_price = payload["entry_price"]
            pos.qty = payload["qty"]
            pos.margin_used = payload["margin_used"]
            pos.notional_value = payload["notional_value"]
            pos.unrealized_pnl = payload["unrealized_pnl"]
            if pos.position_side == "FLAT":
                pos.open_time = ""
            elif not pos.open_time:
                pos.open_time = datetime.now(timezone.utc).isoformat()

    def recent_win_rate(self) -> float:
        recent = self.closed_trade_pnls[-RECENT_TRADE_WINDOW:]
        if not recent:
            return 1.0
        return sum(1 for pnl in recent if pnl > 0) / len(recent)

    def to_dict(self) -> dict:
        return {
            "cash": self.cash,
            "equity": self.equity,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "peak_equity": self.peak_equity,
            "max_drawdown": self.max_drawdown,
            "daily_pnl": self.daily_pnl,
            "consecutive_losses": self.consecutive_losses,
            "closed_trade_pnls": self.closed_trade_pnls,
            "positions": {symbol: asdict(pos) for symbol, pos in self.positions.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        portfolio = cls(float(data.get("cash", INITIAL_CASH)))
        for field in [
            "equity",
            "available_balance",
            "used_margin",
            "realized_pnl",
            "unrealized_pnl",
            "peak_equity",
            "max_drawdown",
            "daily_pnl",
        ]:
            setattr(portfolio, field, float(data.get(field, getattr(portfolio, field))))
        portfolio.consecutive_losses = int(data.get("consecutive_losses", 0))
        portfolio.closed_trade_pnls = list(data.get("closed_trade_pnls", []))
        portfolio.positions = {
            symbol: Position(**pos_data) for symbol, pos_data in data.get("positions", {}).items()
        }
        return portfolio
