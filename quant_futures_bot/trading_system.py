from __future__ import annotations

from .database import Database
from .data import MarketDataProvider
from .events import ErrorEvent, EventType, FillEvent, MarketEvent, OrderStatus, PauseEvent, SignalEvent
from .event_engine import EventEngine
from .execution import PaperExecution
from .indicators import add_indicators
from .logger import setup_logger
from .market_state import detect_market_state
from .order_manager import OrderManager
from .risk_engine import RiskEngine
from .state_manager import StateManager
from .strategy_manager import StrategyManager
from .symbol_config import enabled_symbols, get_symbol_config


class TradingSystem:
    def __init__(self, use_exchange: bool = True) -> None:
        self.logger = setup_logger()
        self.state_manager = StateManager()
        self.portfolio, self.pause_manager = self.state_manager.load()
        self.database = Database()
        self.data_provider = MarketDataProvider(use_exchange=use_exchange)
        self.strategy_manager = StrategyManager()
        self.order_manager = OrderManager()
        self.execution = PaperExecution()
        self.risk_engine = RiskEngine(self.portfolio, self.pause_manager)
        self.engine = EventEngine()
        self.latest_rows: dict[str, dict] = {}
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.engine.register(EventType.MARKET, self.on_market)
        self.engine.register(EventType.SIGNAL, self.on_signal)
        self.engine.register(EventType.FILL, self.on_fill)
        self.engine.register(EventType.PAUSE, self.on_pause)
        self.engine.register(EventType.ERROR, self.on_error)

    def run_cycle(self) -> None:
        for item in enabled_symbols():
            symbol = item["symbol"]
            try:
                df = self.data_provider.fetch_ohlcv(symbol)
                df = add_indicators(df)
                price = float(df.iloc[-1]["close"])
                self.engine.put(MarketEvent(symbol=symbol, price=price, dataframe=df))
            except Exception as exc:
                self.engine.put(ErrorEvent("run_cycle", f"{symbol}: {exc}"))
        self.engine.drain()
        self.pause_manager.check(self.portfolio, self.latest_rows)
        if self.pause_manager.reason:
            self.engine.put(PauseEvent(self.pause_manager.status, self.pause_manager.reason))
            self.engine.drain()
        self.database.save_portfolio(self.portfolio)
        self.state_manager.save(self.portfolio, self.pause_manager)

    def on_market(self, event) -> None:
        assert isinstance(event, MarketEvent)
        self.database.save_market_data(event.symbol, event.dataframe)
        self.portfolio.update_market_price(event.symbol, event.price)
        latest = event.dataframe.iloc[-1].to_dict()
        self.latest_rows[event.symbol] = latest
        market_state = detect_market_state(event.dataframe)
        current_side = self.portfolio.position_side(event.symbol)
        for signal in self.strategy_manager.generate(event.symbol, event.dataframe, market_state, current_side):
            self.engine.put(signal)

    def on_signal(self, event) -> None:
        assert isinstance(event, SignalEvent)
        self.database.save_signal(event)
        risk = self.risk_engine.check_signal(event, self.latest_rows.get(event.symbol, {}))
        if not risk.approved:
            self.logger.info("Signal rejected for %s: %s", event.symbol, risk.reason)
            return
        qty = self.risk_engine.order_quantity(event)
        if qty <= 0:
            self.logger.info("No quantity available for %s %s", event.symbol, event.signal_type.value)
            return
        order = self.order_manager.create_order(event, qty)
        self.database.save_order(order)
        submitted = self.order_manager.update_status(order.order_id, OrderStatus.SUBMITTED)
        self.database.save_order(submitted)
        fill = self.execution.execute(submitted)
        filled = self.order_manager.update_status(order.order_id, OrderStatus.FILLED)
        self.database.save_order(filled)
        self.engine.put(fill)

    def on_fill(self, event) -> None:
        assert isinstance(event, FillEvent)
        leverage = float(get_symbol_config(event.symbol)["leverage"])
        pnl = self.portfolio.apply_fill(event, leverage=leverage)
        self.database.save_fill(event)
        self.database.save_trade(event.timestamp.isoformat(), event.symbol, pnl)
        self.database.save_portfolio(self.portfolio)

    def on_pause(self, event) -> None:
        assert isinstance(event, PauseEvent)
        self.database.save_pause(event)
        self.logger.warning("System %s: %s", event.status, event.reason)

    def on_error(self, event) -> None:
        assert isinstance(event, ErrorEvent)
        self.pause_manager.record_api_error()
        self.database.save_error(event)
        self.logger.error("%s: %s", event.source, event.message)

