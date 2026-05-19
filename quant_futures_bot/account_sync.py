from __future__ import annotations

from dataclasses import dataclass

from .symbol_config import enabled_symbols


@dataclass
class ExchangeAccountSnapshot:
    cash: float = 0.0
    equity: float = 0.0
    available_balance: float = 0.0
    used_margin: float = 0.0
    unrealized_pnl: float = 0.0
    positions: dict[str, dict] | None = None
    open_order_count: int = 0

    def to_portfolio_payload(self) -> dict:
        return {
            "cash": self.cash,
            "equity": self.equity,
            "available_balance": self.available_balance,
            "used_margin": self.used_margin,
            "unrealized_pnl": self.unrealized_pnl,
            "positions": self.positions or {},
        }


class BinanceAccountSync:
    def __init__(self, exchange, symbols: list[str] | None = None) -> None:
        self.exchange = exchange
        self.symbols = symbols

    def fetch(self, symbols: list[str] | None = None) -> ExchangeAccountSnapshot:
        selected_symbols = symbols or self.symbols or [item["symbol"] for item in enabled_symbols()]
        balance = self.exchange.fetch_balance()
        positions = self._fetch_positions(selected_symbols)
        open_orders = self._fetch_open_orders(selected_symbols)
        total = balance.get("total", {})
        free = balance.get("free", {})
        info = balance.get("info", {})
        cash = self._first_float(total.get("USDT"), info.get("totalWalletBalance"), 0.0)
        equity = self._first_float(info.get("totalMarginBalance"), total.get("USDT"), cash)
        available = self._first_float(free.get("USDT"), info.get("availableBalance"), cash)
        unrealized = sum(position["unrealized_pnl"] for position in positions.values())
        used_margin = max(equity - available, 0.0)
        return ExchangeAccountSnapshot(
            cash=cash,
            equity=equity,
            available_balance=available,
            used_margin=used_margin,
            unrealized_pnl=unrealized,
            positions=positions,
            open_order_count=len(open_orders),
        )

    def _fetch_positions(self, symbols: list[str]) -> dict[str, dict]:
        positions: dict[str, dict] = {
            symbol: {
                "position_side": "FLAT",
                "entry_price": 0.0,
                "qty": 0.0,
                "margin_used": 0.0,
                "notional_value": 0.0,
                "unrealized_pnl": 0.0,
            }
            for symbol in symbols
        }
        try:
            exchange_positions = self.exchange.fetch_positions()
        except Exception:
            exchange_positions = self.exchange.fetch_positions(symbols)
        for item in exchange_positions:
            symbol = item.get("symbol")
            contracts = abs(self._first_float(item.get("contracts"), item.get("contractSize"), 0.0))
            raw_side = str(item.get("side") or "").lower()
            info = item.get("info", {})
            raw_amt = self._first_float(info.get("positionAmt"), item.get("contracts"), 0.0)
            qty = abs(raw_amt) if raw_amt else contracts
            if qty <= 0:
                continue
            side = "LONG" if raw_amt > 0 or raw_side == "long" else "SHORT"
            entry_price = self._first_float(item.get("entryPrice"), info.get("entryPrice"), 0.0)
            notional = abs(self._first_float(item.get("notional"), info.get("notional"), entry_price * qty))
            margin = abs(self._first_float(item.get("initialMargin"), info.get("positionInitialMargin"), 0.0))
            unrealized = self._first_float(item.get("unrealizedPnl"), info.get("unRealizedProfit"), 0.0)
            positions[symbol] = {
                "position_side": side,
                "entry_price": entry_price,
                "qty": qty,
                "margin_used": margin,
                "notional_value": notional,
                "unrealized_pnl": unrealized,
            }
        return positions

    def _fetch_open_orders(self, symbols: list[str]) -> list[dict]:
        orders: list[dict] = []
        for symbol in symbols:
            try:
                orders.extend(self.exchange.fetch_open_orders(symbol))
            except Exception:
                continue
        return orders

    @staticmethod
    def _first_float(*values) -> float:
        for value in values:
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0
