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
            exchange_order_id="",
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


class BinanceTestnetExecution:
    def __init__(self, fee_rate: float = config.FEE_RATE) -> None:
        if not config.BINANCE_TESTNET_API_KEY or not config.BINANCE_TESTNET_API_SECRET:
            raise RuntimeError(
                "Missing BINANCE_TESTNET_API_KEY or BINANCE_TESTNET_API_SECRET environment variable"
            )
        try:
            import ccxt
        except ImportError as exc:
            raise RuntimeError("ccxt is required for Binance testnet execution") from exc

        self.fee_rate = fee_rate
        self.exchange = ccxt.binanceusdm(
            {
                "apiKey": config.BINANCE_TESTNET_API_KEY,
                "secret": config.BINANCE_TESTNET_API_SECRET,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "future",
                    "fetchCurrencies": False,
                    "adjustForTimeDifference": True,
                },
            }
        )
        self._use_futures_demo_urls()
        self.exchange.has["fetchCurrencies"] = False
        self.exchange.load_markets()
        self._configured_leverage: set[str] = set()

    def _use_futures_demo_urls(self) -> None:
        demo_v1 = config.BINANCE_FUTURES_TESTNET_REST_URL + "/fapi/v1"
        demo_v2 = config.BINANCE_FUTURES_TESTNET_REST_URL + "/fapi/v2"
        demo_v3 = config.BINANCE_FUTURES_TESTNET_REST_URL + "/fapi/v3"
        self.exchange.urls["api"]["fapiPublic"] = demo_v1
        self.exchange.urls["api"]["fapiPrivate"] = demo_v1
        self.exchange.urls["api"]["fapiPublicV2"] = demo_v2
        self.exchange.urls["api"]["fapiPrivateV2"] = demo_v2
        self.exchange.urls["api"]["fapiPublicV3"] = demo_v3
        self.exchange.urls["api"]["fapiPrivateV3"] = demo_v3

    def set_leverage_once(self, symbol: str, leverage: int) -> None:
        if symbol in self._configured_leverage:
            return
        self.exchange.set_leverage(leverage, symbol)
        self._configured_leverage.add(symbol)

    def execute(self, order: OrderEvent, leverage: int | None = None) -> FillEvent:
        if leverage is not None:
            self.set_leverage_once(order.symbol, leverage)
        amount = float(self.exchange.amount_to_precision(order.symbol, order.qty))
        params = {}
        if order.reduce_only:
            params["reduceOnly"] = True
        response = self.exchange.create_order(
            symbol=order.symbol,
            type="market",
            side=order.side.lower(),
            amount=amount,
            price=None,
            params=params,
        )
        fill_price = self._extract_fill_price(response, order.price)
        filled_qty = float(response.get("filled") or amount)
        fee = self._extract_fee(response, fill_price * filled_qty)
        slippage = abs(fill_price - order.price)
        return FillEvent(
            order_id=order.order_id,
            symbol=order.symbol,
            fill_price=fill_price,
            qty=filled_qty,
            fee=fee,
            slippage=slippage,
            position_action=order.position_action,
            exchange_order_id=str(response.get("id") or response.get("orderId") or ""),
            timestamp=order.timestamp,
        )

    def create_limit_order(
        self,
        order: OrderEvent,
        leverage: int | None = None,
        maker_offset: float = 0.001,
        post_only: bool = True,
    ) -> dict:
        if leverage is not None:
            self.set_leverage_once(order.symbol, leverage)
        amount = float(self.exchange.amount_to_precision(order.symbol, order.qty))
        price = self._limit_price(order, maker_offset)
        params = {}
        if order.reduce_only:
            params["reduceOnly"] = True
        if post_only:
            params["timeInForce"] = "GTX"
        return self.exchange.create_order(
            symbol=order.symbol,
            type="limit",
            side=order.side.lower(),
            amount=amount,
            price=price,
            params=params,
        )

    def _limit_price(self, order: OrderEvent, maker_offset: float) -> float:
        raw_price = order.price
        if order.side.upper() == "BUY":
            raw_price = order.price * (1 - maker_offset)
        elif order.side.upper() == "SELL":
            raw_price = order.price * (1 + maker_offset)
        return float(self.exchange.price_to_precision(order.symbol, raw_price))

    def _extract_fill_price(self, response: dict, fallback_price: float) -> float:
        for key in ("average", "price"):
            value = response.get(key)
            if value:
                return float(value)
        return float(fallback_price)

    def _extract_fee(self, response: dict, fallback_notional: float) -> float:
        fee = response.get("fee") or {}
        cost = fee.get("cost")
        if cost is not None:
            return abs(float(cost))
        fees = response.get("fees") or []
        if fees:
            return sum(abs(float(item.get("cost", 0))) for item in fees)
        return fallback_notional * self.fee_rate


def create_execution():
    if config.EXECUTION_MODE == "testnet":
        return BinanceTestnetExecution()
    if config.EXECUTION_MODE != "paper":
        raise RuntimeError(f"Unsupported EXECUTION_MODE: {config.EXECUTION_MODE}")
    return PaperExecution()
