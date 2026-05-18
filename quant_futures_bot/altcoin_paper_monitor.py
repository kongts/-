from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .account_sync import BinanceAccountSync
from .config import DATA_DIR, FUNDING_COST_RATE_PER_8H, INVERT_EXECUTION_SIGNALS, LOG_DIR, MAKER_FEE_RATE
from .data import MarketDataProvider
from .events import OrderStatus, SignalEvent, SignalType
from .execution import BinanceTestnetExecution, PaperExecution
from .indicators import add_indicators
from .market_state import detect_market_state
from .order_manager import OrderManager
from .pause_manager import PauseManager
from .portfolio import Portfolio
from .risk_engine import RiskEngine
from .signal_inversion import invert_signals, opposite_position_side
from .strategy_manager import StrategyManager


DEFAULT_STRATEGY_PATH = DATA_DIR / "altcoin_strategy_latest.json"
DEFAULT_STATE_PATH = DATA_DIR / "altcoin_paper_state.json"
DEFAULT_LATEST_PATH = DATA_DIR / "altcoin_paper_latest.json"
DEFAULT_RUNTIME_STATE_PATH = DATA_DIR / "altcoin_paper_runtime_state.json"


class AltcoinPaperMonitor:
    def __init__(
        self,
        strategy_path: Path = DEFAULT_STRATEGY_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
        latest_path: Path = DEFAULT_LATEST_PATH,
        runtime_state_path: Path | None = None,
        board_name: str = "altcoin",
        log_filename: str | None = None,
        top: int = 5,
        candle_limit: int = 220,
        max_margin_ratio: float = 0.03,
        leverage: int = 2,
        stop_loss_pct: float = 0.025,
        take_profit_pct: float = 0.06,
        crash_watch_drop_pct: float = 0.03,
        crash_watch_breadth_ratio: float = 0.6,
        crash_short_trailing_pct: float = 0.03,
        open_order_timeout_seconds: int = 180,
        close_order_timeout_seconds: int = 60,
        max_order_failures: int = 3,
        max_hold_bars_15m: int = 8,
        max_hold_bars_30m: int = 6,
        max_hold_bars_1h: int = 24,
        max_hold_bars_4h: int = 18,
        extended_hold_bars_15m: int = 4,
        extended_hold_bars_30m: int = 3,
        extended_hold_bars_1h: int = 12,
        extended_hold_bars_4h: int = 6,
        min_profit_to_extend: float = 0.03,
        trailing_after_max_hold_pct: float = 0.03,
        execution_mode: str = "paper",
        confirm_exchange_orders: str = "",
        order_type: str = "market",
        maker_offset: float = 0.001,
    ) -> None:
        if execution_mode not in {"paper", "testnet"}:
            raise ValueError("execution_mode must be paper or testnet")
        if order_type not in {"market", "limit"}:
            raise ValueError("order_type must be market or limit")
        if execution_mode == "testnet" and confirm_exchange_orders != "YES":
            raise RuntimeError("testnet exchange orders require --confirm-exchange-orders YES")
        if execution_mode == "testnet" and order_type != "limit":
            raise RuntimeError("altcoin testnet exchange orders are limit-only; use --order-type limit")
        if execution_mode == "testnet":
            if state_path == DEFAULT_STATE_PATH:
                state_path = DATA_DIR / "altcoin_testnet_state.json"
            if latest_path == DEFAULT_LATEST_PATH:
                latest_path = DATA_DIR / "altcoin_testnet_latest.json"
            if runtime_state_path is None:
                runtime_state_path = DATA_DIR / "altcoin_testnet_runtime_state.json"
        else:
            runtime_state_path = runtime_state_path or DEFAULT_RUNTIME_STATE_PATH
        self.strategy_path = strategy_path
        self.state_path = state_path
        self.latest_path = latest_path
        self.runtime_state_path = runtime_state_path
        self.board_name = board_name
        self.log_filename = log_filename or ("altcoin_testnet.log" if execution_mode == "testnet" else "altcoin_paper.log")
        self.execution_mode = execution_mode
        self.order_type = order_type
        self.maker_offset = maker_offset
        self.invert_execution_signals = INVERT_EXECUTION_SIGNALS
        self.top = top
        self.candle_limit = candle_limit
        self.max_margin_ratio = max_margin_ratio
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.crash_watch_drop_pct = crash_watch_drop_pct
        self.crash_watch_breadth_ratio = crash_watch_breadth_ratio
        self.crash_short_trailing_pct = crash_short_trailing_pct
        self.open_order_timeout_seconds = open_order_timeout_seconds
        self.close_order_timeout_seconds = close_order_timeout_seconds
        self.max_order_failures = max_order_failures
        self.max_hold_bars_15m = max_hold_bars_15m
        self.max_hold_bars_30m = max_hold_bars_30m
        self.max_hold_bars_1h = max_hold_bars_1h
        self.max_hold_bars_4h = max_hold_bars_4h
        self.extended_hold_bars_15m = extended_hold_bars_15m
        self.extended_hold_bars_30m = extended_hold_bars_30m
        self.extended_hold_bars_1h = extended_hold_bars_1h
        self.extended_hold_bars_4h = extended_hold_bars_4h
        self.min_profit_to_extend = min_profit_to_extend
        self.trailing_after_max_hold_pct = trailing_after_max_hold_pct
        self.data_provider = MarketDataProvider(use_exchange=True, fallback_to_synthetic=False)
        self.portfolio = self.load_portfolio()
        runtime_state = self.load_runtime_state()
        self.short_trailing_peaks: dict[str, float] = dict(runtime_state.get("short_trailing_peaks", {}))
        self.max_hold_profit_peaks: dict[str, float] = dict(runtime_state.get("max_hold_profit_peaks", {}))
        self.pending_orders: dict[str, dict] = dict(runtime_state.get("pending_orders", {}))
        self.order_failures: dict[str, int] = dict(runtime_state.get("order_failures", {}))
        self.paused_symbols: dict[str, str] = dict(runtime_state.get("paused_symbols", {}))
        self.pause_manager = PauseManager()
        self.execution = BinanceTestnetExecution() if execution_mode == "testnet" else PaperExecution()
        self.account_sync = BinanceAccountSync(self.execution.exchange) if isinstance(self.execution, BinanceTestnetExecution) else None
        self.order_manager = OrderManager()
        self.exchange_open_order_count = 0
        self.exchange_positions_summary = "-"
        self.unsupported_symbols_logged: set[str] = set()

    def run_once(self) -> None:
        leaders = self.load_leaders()
        cycle_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        selected_leaders = self.select_leaders(leaders)
        self.log(
            f"[{cycle_started_at}] start {self.board_name} {self.execution_mode} cycle "
            f"leaders={len(leaders)} selected={len(selected_leaders)} top={self.top}"
        )
        sync_symbols = sorted(
            {leader["symbol"] for leader in selected_leaders}
            | set(self.pending_orders)
            | self.local_open_symbols()
        )
        self.sync_exchange_account(sync_symbols)
        self.manage_pending_orders()
        self.sync_exchange_account(sync_symbols)
        signals_created = 0
        orders_created = 0
        fills_created = 0
        rejected = 0
        exchange_order_ids: list[str] = []
        market_contexts: list[dict] = []
        for leader in selected_leaders:
            symbol = leader["symbol"]
            strategy_id = leader["strategy_id"]
            timeframe = leader["timeframe"]
            try:
                frame = add_indicators(self.data_provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=self.candle_limit))
                price = float(frame.iloc[-1]["close"])
                self.portfolio.update_market_price(symbol, price)
                market_contexts.append(
                    {
                        "symbol": symbol,
                        "strategy_id": strategy_id,
                        "timeframe": timeframe,
                        "frame": frame,
                        "price": price,
                        "latest_row": frame.iloc[-1].to_dict(),
                        "recent_drop": self.recent_drop(frame),
                    }
                )
            except Exception as exc:
                self.log(f"symbol_error symbol={symbol} strategy={strategy_id}/{timeframe} error={exc}")
        crash_watch = self.detect_crash_watch(market_contexts)
        if crash_watch:
            drops = [context["recent_drop"] for context in market_contexts if context["recent_drop"] is not None]
            avg_drop = sum(drops) / len(drops) if drops else 0.0
            self.log(
                f"crash_watch=ON symbols={len(drops)} avg_recent_drop={avg_drop:.2%} "
                f"trigger_drop={self.crash_watch_drop_pct:.2%} short_trailing={self.crash_short_trailing_pct:.2%}"
            )
        for context in market_contexts:
            symbol = context["symbol"]
            strategy_id = context["strategy_id"]
            timeframe = context["timeframe"]
            try:
                frame = context["frame"]
                price = context["price"]
                latest_row = context["latest_row"]
                if symbol in self.paused_symbols:
                    self.log(f"symbol_paused symbol={symbol} reason={self.paused_symbols[symbol]}")
                    continue
                if symbol in self.pending_orders:
                    self.log(f"pending_order_wait symbol={symbol} exchange_order_id={self.pending_orders[symbol].get('exchange_order_id', '-')}")
                    continue
                exit_signal = self.stop_or_take_profit_signal(symbol, price, crash_watch, timeframe)
                if exit_signal is not None:
                    ok, filled, order_ids = self.execute_signal(exit_signal, latest_row)
                    signals_created += 1
                    orders_created += 1 if ok else 0
                    fills_created += 1 if filled else 0
                    exchange_order_ids.extend(order_ids)
                    rejected += 0 if ok else 1
                    continue
                manager = StrategyManager(strategy_id=strategy_id, use_saved_selection=False)
                market_state = detect_market_state(frame)
                current_side = self.portfolio.position_side(symbol)
                strategy_side = opposite_position_side(current_side) if self.invert_execution_signals else current_side
                signals = manager.generate(symbol, frame, market_state, strategy_side)
                if self.invert_execution_signals:
                    signals = invert_signals(signals)
                for signal in signals:
                    signals_created += 1
                    ok, filled, order_ids = self.execute_signal(signal, latest_row)
                    orders_created += 1 if ok else 0
                    fills_created += 1 if filled else 0
                    exchange_order_ids.extend(order_ids)
                    rejected += 0 if ok else 1
            except Exception as exc:
                self.log(f"symbol_error symbol={symbol} strategy={strategy_id}/{timeframe} error={exc}")
        self.prune_runtime_state()
        self.save_portfolio()
        self.save_runtime_state()
        self.write_latest(signals_created, orders_created, fills_created, rejected, exchange_order_ids)
        self.log(
            f"{self.execution_mode}_summary {self.account_summary()} "
            f"signals={signals_created} orders={orders_created} fills={fills_created} rejected={rejected} order_type={self.order_type} "
            f"exchange_order_ids={','.join(exchange_order_ids) or '-'} exchange_open_orders={self.exchange_open_order_count} "
            f"pending_orders={len(self.pending_orders)} paused_symbols={len(self.paused_symbols)}"
        )

    def maintain_orders(self, symbols: list[str]) -> None:
        sync_symbols = sorted(set(symbols) | set(self.pending_orders) | self.local_open_symbols())
        self.sync_exchange_account(sync_symbols)
        self.manage_pending_orders()
        self.sync_exchange_account(sync_symbols)
        self.prune_runtime_state()
        self.save_portfolio()
        self.save_runtime_state()
        self.write_latest(0, 0, 0, 0, [])
        self.log(
            f"{self.execution_mode}_maintenance {self.account_summary()} "
            f"exchange_open_orders={self.exchange_open_order_count} pending_orders={len(self.pending_orders)} "
            f"paused_symbols={len(self.paused_symbols)}"
        )

    def sync_exchange_account(self, symbols: list[str]) -> None:
        if self.account_sync is None:
            self.exchange_open_order_count = 0
            self.exchange_positions_summary = "-"
            return
        snapshot = self.account_sync.fetch(self.filter_supported_symbols(symbols))
        self.exchange_open_order_count = snapshot.open_order_count
        self.portfolio.sync_from_exchange(snapshot.to_portfolio_payload())
        self.exchange_positions_summary = self.format_exchange_positions(snapshot.positions or {})

    def execute_signal(self, signal: SignalEvent, latest_row: dict) -> tuple[bool, bool, list[str]]:
        if signal.symbol in self.paused_symbols:
            self.log(f"signal_rejected symbol={signal.symbol} signal={signal.signal_type.value} reason=symbol paused")
            return False, False, []
        if signal.symbol in self.pending_orders:
            self.log(f"signal_rejected symbol={signal.symbol} signal={signal.signal_type.value} reason=pending order exists")
            return False, False, []
        symbol_configs = {
            signal.symbol: {
                "symbol": signal.symbol,
                "enabled": True,
                "leverage": self.leverage,
                "max_margin_ratio": self.max_margin_ratio,
            }
        }
        risk_engine = RiskEngine(self.portfolio, self.pause_manager, symbol_configs=symbol_configs)
        risk = risk_engine.check_signal(signal, latest_row)
        if not risk.approved:
            self.log(f"signal_rejected symbol={signal.symbol} signal={signal.signal_type.value} reason={risk.reason}")
            return False, False, []
        qty = risk_engine.order_quantity(signal)
        if qty <= 0:
            self.log(f"signal_rejected symbol={signal.symbol} signal={signal.signal_type.value} reason=no quantity")
            return False, False, []
        order = self.order_manager.create_order(signal, qty)
        submitted = self.order_manager.update_status(order.order_id, OrderStatus.SUBMITTED)
        if isinstance(self.execution, BinanceTestnetExecution) and self.order_type == "limit":
            response = self.execution.create_limit_order(
                submitted,
                leverage=self.leverage,
                maker_offset=self.maker_offset,
                post_only=True,
            )
            exchange_order_id = str(response.get("id") or response.get("orderId") or "")
            if exchange_order_id:
                self.record_pending_order(submitted, exchange_order_id)
            self.log(
                f"testnet_order symbol={submitted.symbol} action={submitted.position_action.value} type=limit "
                f"side={submitted.side} qty={submitted.qty:.8f} signal_price={submitted.price:.6f} "
                f"exchange_order_id={exchange_order_id or '-'} status=submitted post_only=YES"
            )
            return True, False, [exchange_order_id] if exchange_order_id else []
        if isinstance(self.execution, BinanceTestnetExecution):
            fill = self.execution.execute(submitted, leverage=self.leverage)
        else:
            fill = self.execution.execute(submitted)
        pnl = self.portfolio.apply_fill(fill, leverage=float(self.leverage))
        self.order_manager.update_status(order.order_id, OrderStatus.FILLED)
        self.log(
            f"{self.execution_mode}_fill symbol={fill.symbol} action={fill.position_action.value} "
            f"price={fill.fill_price:.6f} qty={fill.qty:.8f} fee={fill.fee:.4f} pnl={pnl:.4f} "
            f"exchange_order_id={fill.exchange_order_id or '-'}"
        )
        return True, True, [fill.exchange_order_id] if fill.exchange_order_id else []

    def stop_or_take_profit_signal(self, symbol: str, price: float, crash_watch: bool, timeframe: str) -> SignalEvent | None:
        pos = self.portfolio.get_position(symbol)
        if not pos.is_open() or pos.entry_price <= 0:
            self.short_trailing_peaks.pop(symbol, None)
            self.max_hold_profit_peaks.pop(symbol, None)
            return None
        if pos.position_side == "LONG":
            change = price / pos.entry_price - 1
            close_type = SignalType.CLOSE_LONG
            self.short_trailing_peaks.pop(symbol, None)
        else:
            change = pos.entry_price / price - 1
            close_type = SignalType.CLOSE_SHORT
        if change <= -self.stop_loss_pct:
            self.short_trailing_peaks.pop(symbol, None)
            self.max_hold_profit_peaks.pop(symbol, None)
            return SignalEvent(symbol, close_type, f"{self.board_name.title()} Stop Loss", price)
        if pos.position_side == "SHORT" and crash_watch:
            peak = max(self.short_trailing_peaks.get(symbol, change), change)
            self.short_trailing_peaks[symbol] = peak
            pullback = peak - change
            if peak >= self.take_profit_pct and pullback >= self.crash_short_trailing_pct:
                self.short_trailing_peaks.pop(symbol, None)
                self.max_hold_profit_peaks.pop(symbol, None)
                return SignalEvent(symbol, close_type, f"{self.board_name.title()} Crash Short Trailing Take Profit", price)
            return None
        max_hold_seconds = self.max_hold_seconds_for_timeframe(timeframe)
        extended_hold_seconds = self.extended_hold_seconds_for_timeframe(timeframe)
        held_seconds = self.position_age_seconds(pos.open_time)
        if max_hold_seconds > 0 and held_seconds is not None and held_seconds >= max_hold_seconds:
            if change < self.min_profit_to_extend:
                self.max_hold_profit_peaks.pop(symbol, None)
                return SignalEvent(symbol, close_type, f"{self.board_name.title()} Max Hold Time", price)
            peak = max(self.max_hold_profit_peaks.get(symbol, change), change)
            self.max_hold_profit_peaks[symbol] = peak
            if peak - change >= self.trailing_after_max_hold_pct:
                self.max_hold_profit_peaks.pop(symbol, None)
                return SignalEvent(symbol, close_type, f"{self.board_name.title()} Max Hold Trailing Take Profit", price)
            if extended_hold_seconds > 0 and held_seconds >= max_hold_seconds + extended_hold_seconds:
                self.max_hold_profit_peaks.pop(symbol, None)
                return SignalEvent(symbol, close_type, f"{self.board_name.title()} Extended Max Hold Time", price)
            return None
        if change >= self.take_profit_pct:
            self.short_trailing_peaks.pop(symbol, None)
            self.max_hold_profit_peaks.pop(symbol, None)
            return SignalEvent(symbol, close_type, f"{self.board_name.title()} Take Profit", price)
        return None

    def max_hold_seconds_for_timeframe(self, timeframe: str) -> int:
        if timeframe == "15m":
            return self.max_hold_bars_15m * 15 * 60
        if timeframe == "30m":
            return self.max_hold_bars_30m * 30 * 60
        if timeframe == "1h":
            return self.max_hold_bars_1h * 60 * 60
        if timeframe == "4h":
            return self.max_hold_bars_4h * 4 * 60 * 60
        return 0

    def extended_hold_seconds_for_timeframe(self, timeframe: str) -> int:
        if timeframe == "15m":
            return self.extended_hold_bars_15m * 15 * 60
        if timeframe == "30m":
            return self.extended_hold_bars_30m * 30 * 60
        if timeframe == "1h":
            return self.extended_hold_bars_1h * 60 * 60
        if timeframe == "4h":
            return self.extended_hold_bars_4h * 4 * 60 * 60
        return 0

    @staticmethod
    def position_age_seconds(open_time: str) -> float | None:
        opened_at = AltcoinPaperMonitor.parse_datetime(open_time)
        if opened_at is None:
            return None
        return (datetime.now(timezone.utc) - opened_at).total_seconds()

    def recent_drop(self, frame) -> float | None:
        if len(frame) < 5:
            return None
        previous = float(frame.iloc[-5]["close"])
        latest = float(frame.iloc[-1]["close"])
        if previous <= 0:
            return None
        return latest / previous - 1

    def detect_crash_watch(self, market_contexts: list[dict]) -> bool:
        drops = [context["recent_drop"] for context in market_contexts if context["recent_drop"] is not None]
        if not drops:
            return False
        severe_count = sum(1 for drop in drops if drop <= -self.crash_watch_drop_pct)
        breadth = severe_count / len(drops)
        return breadth >= self.crash_watch_breadth_ratio

    def manage_pending_orders(self) -> None:
        if not isinstance(self.execution, BinanceTestnetExecution):
            return
        now = datetime.now(timezone.utc)
        for symbol, pending in list(self.pending_orders.items()):
            exchange_order_id = str(pending.get("exchange_order_id") or "")
            if not exchange_order_id:
                self.pending_orders.pop(symbol, None)
                continue
            try:
                order = self.execution.fetch_order(exchange_order_id, symbol)
            except Exception as exc:
                self.log(f"pending_order_check_error symbol={symbol} exchange_order_id={exchange_order_id} error={exc}")
                continue
            status = str(order.get("status") or "").lower()
            filled = self._first_float(order.get("filled"), 0.0)
            remaining = self._first_float(order.get("remaining"), pending.get("qty"), 0.0)
            if status in {"closed", "filled"} or (filled > 0 and remaining <= 1e-12):
                self.log(
                    f"pending_order_filled symbol={symbol} exchange_order_id={exchange_order_id} "
                    f"status={status or '-'} filled={filled:.8f}"
                )
                self.pending_orders.pop(symbol, None)
                self.order_failures.pop(symbol, None)
                continue
            if status in {"canceled", "cancelled", "expired", "rejected"}:
                self.log(
                    f"pending_order_failed symbol={symbol} exchange_order_id={exchange_order_id} "
                    f"status={status or '-'} filled={filled:.8f}"
                )
                self.pending_orders.pop(symbol, None)
                self.record_order_failure(symbol, f"order {status or 'failed'}")
                continue
            created_at = self.parse_datetime(str(pending.get("created_at") or ""))
            age = (now - created_at).total_seconds() if created_at else 0
            timeout = self.close_order_timeout_seconds if self.is_close_action(str(pending.get("action") or "")) else self.open_order_timeout_seconds
            if age < timeout:
                continue
            try:
                self.execution.cancel_order(exchange_order_id, symbol)
                self.log(
                    f"pending_order_timeout_cancelled symbol={symbol} exchange_order_id={exchange_order_id} "
                    f"action={pending.get('action', '-')} age_seconds={age:.0f} timeout_seconds={timeout} filled={filled:.8f}"
                )
            except Exception as exc:
                self.log(f"pending_order_cancel_error symbol={symbol} exchange_order_id={exchange_order_id} error={exc}")
            self.pending_orders.pop(symbol, None)
            self.record_order_failure(symbol, "timeout")

    def record_pending_order(self, order, exchange_order_id: str) -> None:
        self.pending_orders[order.symbol] = {
            "exchange_order_id": exchange_order_id,
            "symbol": order.symbol,
            "action": order.position_action.value,
            "side": order.side,
            "qty": order.qty,
            "signal_price": order.price,
            "reduce_only": order.reduce_only,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def record_order_failure(self, symbol: str, reason: str) -> None:
        failures = int(self.order_failures.get(symbol, 0)) + 1
        self.order_failures[symbol] = failures
        if failures >= self.max_order_failures:
            self.paused_symbols[symbol] = f"order failures reached {failures}: {reason}"
            self.log(f"symbol_paused symbol={symbol} failures={failures} reason={reason}")
        else:
            self.log(f"order_failure symbol={symbol} failures={failures}/{self.max_order_failures} reason={reason}")

    @staticmethod
    def is_close_action(action: str) -> bool:
        return action in {SignalType.CLOSE_LONG.value, SignalType.CLOSE_SHORT.value, SignalType.CLOSE_POSITION.value}

    @staticmethod
    def parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

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

    def load_leaders(self) -> list[dict]:
        if not self.strategy_path.exists():
            self.log(f"missing_{self.board_name}_strategy_latest path={self.strategy_path}")
            return []
        payload = json.loads(self.strategy_path.read_text(encoding="utf-8"))
        return list(payload.get("leaders", []))

    def select_leaders(self, leaders: list[dict]) -> list[dict]:
        tradable = [leader for leader in leaders if self.is_supported_symbol(str(leader.get("symbol") or ""))]
        if self.top <= 0:
            return tradable
        return tradable[: self.top]

    def filter_supported_symbols(self, symbols: list[str]) -> list[str]:
        return [symbol for symbol in symbols if self.is_supported_symbol(symbol)]

    def is_supported_symbol(self, symbol: str) -> bool:
        if not symbol or not isinstance(self.execution, BinanceTestnetExecution):
            return True
        if symbol in self.execution.exchange.markets:
            return True
        if symbol not in self.unsupported_symbols_logged:
            self.unsupported_symbols_logged.add(symbol)
            self.log(f"symbol_skipped symbol={symbol} reason=not supported by Binance REST market list")
        return False

    def load_portfolio(self) -> Portfolio:
        if self.state_path.exists():
            try:
                return Portfolio.from_dict(json.loads(self.state_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return Portfolio()

    def save_portfolio(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.portfolio.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def load_runtime_state(self) -> dict:
        if self.runtime_state_path.exists():
            try:
                return json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return {}

    def prune_runtime_state(self) -> None:
        for symbol in list(self.short_trailing_peaks):
            pos = self.portfolio.get_position(symbol)
            if not pos.is_open() or pos.position_side != "SHORT":
                self.short_trailing_peaks.pop(symbol, None)
        for symbol in list(self.max_hold_profit_peaks):
            pos = self.portfolio.get_position(symbol)
            if not pos.is_open():
                self.max_hold_profit_peaks.pop(symbol, None)

    def save_runtime_state(self) -> None:
        self.runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "short_trailing_peaks": self.short_trailing_peaks,
            "max_hold_profit_peaks": self.max_hold_profit_peaks,
            "pending_orders": self.pending_orders,
            "order_failures": self.order_failures,
            "paused_symbols": self.paused_symbols,
        }
        self.runtime_state_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_latest(
        self,
        signals_created: int,
        orders_created: int,
        fills_created: int,
        rejected: int,
        exchange_order_ids: list[str],
    ) -> None:
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "mode": self.execution_mode,
            "equity": self.portfolio.equity,
            "cash": self.portfolio.cash,
            "used_margin": self.portfolio.used_margin,
            "available_balance": self.portfolio.available_balance,
            "realized_pnl": self.portfolio.realized_pnl,
            "unrealized_pnl": self.portfolio.unrealized_pnl,
            "max_drawdown": self.portfolio.max_drawdown,
            "signals_created": signals_created,
            "orders_created": orders_created,
            "fills_created": fills_created,
            "rejected": rejected,
            "exchange_order_ids": exchange_order_ids,
            "exchange_open_order_count": self.exchange_open_order_count,
            "exchange_positions_summary": self.exchange_positions_summary,
            "pending_orders": self.pending_orders,
            "order_failures": self.order_failures,
            "paused_symbols": self.paused_symbols,
            "order_type": self.order_type,
            "crash_watch_drop_pct": self.crash_watch_drop_pct,
            "crash_watch_breadth_ratio": self.crash_watch_breadth_ratio,
            "crash_short_trailing_pct": self.crash_short_trailing_pct,
            "max_hold_bars_15m": self.max_hold_bars_15m,
            "max_hold_bars_30m": self.max_hold_bars_30m,
            "max_hold_bars_1h": self.max_hold_bars_1h,
            "max_hold_bars_4h": self.max_hold_bars_4h,
            "extended_hold_bars_15m": self.extended_hold_bars_15m,
            "extended_hold_bars_30m": self.extended_hold_bars_30m,
            "extended_hold_bars_1h": self.extended_hold_bars_1h,
            "extended_hold_bars_4h": self.extended_hold_bars_4h,
            "min_profit_to_extend": self.min_profit_to_extend,
            "trailing_after_max_hold_pct": self.trailing_after_max_hold_pct,
            "short_trailing_peaks": self.short_trailing_peaks,
            "max_hold_profit_peaks": self.max_hold_profit_peaks,
            "fee_rate": MAKER_FEE_RATE if self.order_type == "limit" else self.execution.fee_rate,
            "funding_cost_rate_per_8h": FUNDING_COST_RATE_PER_8H,
            "invert_execution_signals": self.invert_execution_signals,
            "positions": self.portfolio.to_dict()["positions"],
        }
        self.latest_path.parent.mkdir(parents=True, exist_ok=True)
        self.latest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def format_positions(self) -> str:
        active = []
        for symbol, pos in sorted(self.portfolio.positions.items()):
            if pos.is_open():
                active.append(
                    f"{symbol}:{pos.position_side} qty={pos.qty:.6f} entry={pos.entry_price:.6f} pnl={pos.unrealized_pnl:.2f}"
                )
        return ";".join(active) or "-"

    def local_open_symbols(self) -> set[str]:
        return {symbol for symbol, pos in self.portfolio.positions.items() if pos.is_open()}

    def account_summary(self) -> str:
        return (
            f"equity={self.portfolio.equity:.2f} cash={self.portfolio.cash:.2f} "
            f"available={self.portfolio.available_balance:.2f} used_margin={self.portfolio.used_margin:.2f} "
            f"unrealized={self.portfolio.unrealized_pnl:.2f} realized={self.portfolio.realized_pnl:.2f} "
            f"exchange_positions={self.exchange_positions_summary} local_positions={self.format_positions()}"
        )

    @staticmethod
    def format_exchange_positions(positions: dict[str, dict]) -> str:
        active = []
        for symbol, pos in sorted(positions.items()):
            if pos["position_side"] != "FLAT" and pos["qty"] > 0:
                active.append(
                    f"{symbol}:{pos['position_side']} qty={pos['qty']:.6f} "
                    f"entry={pos['entry_price']:.4f} pnl={pos['unrealized_pnl']:.2f}"
                )
        return ";".join(active) or "-"

    def log(self, message: str) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        line = message if message.startswith("[") else f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
        print(line, flush=True)
        with (LOG_DIR / self.log_filename).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paper/testnet trading monitor for latest altcoin aggressive strategies")
    parser.add_argument("--run-once", action="store_true", help="run once and exit")
    parser.add_argument("--interval-minutes", type=float, default=15.0, help="minutes between paper cycles")
    parser.add_argument("--top", type=int, default=5, help="number of latest leaders to trade; 0 means all")
    parser.add_argument("--candle-limit", type=int, default=220, help="candles per symbol/timeframe")
    parser.add_argument("--max-margin-ratio", type=float, default=0.03, help="margin ratio per symbol")
    parser.add_argument("--leverage", type=int, default=2, help="paper leverage")
    parser.add_argument("--stop-loss-pct", type=float, default=0.025, help="stop loss percentage")
    parser.add_argument("--take-profit-pct", type=float, default=0.06, help="take profit percentage")
    parser.add_argument("--crash-watch-drop-pct", type=float, default=0.03, help="recent drop percentage that enables short trailing")
    parser.add_argument("--crash-watch-breadth-ratio", type=float, default=0.6, help="ratio of traded symbols that must drop")
    parser.add_argument("--crash-short-trailing-pct", type=float, default=0.03, help="short trailing take profit pullback in crash watch")
    parser.add_argument("--open-order-timeout-seconds", type=int, default=180, help="cancel unfilled opening limit orders after this many seconds")
    parser.add_argument("--close-order-timeout-seconds", type=int, default=60, help="cancel unfilled closing limit orders after this many seconds")
    parser.add_argument("--max-order-failures", type=int, default=3, help="pause a symbol after this many consecutive order failures")
    parser.add_argument("--max-hold-bars-15m", type=int, default=8, help="max holding bars for 15m strategies")
    parser.add_argument("--max-hold-bars-30m", type=int, default=6, help="max holding bars for 30m strategies")
    parser.add_argument("--max-hold-bars-1h", type=int, default=24, help="max holding bars for 1h strategies")
    parser.add_argument("--max-hold-bars-4h", type=int, default=18, help="max holding bars for 4h strategies")
    parser.add_argument("--extended-hold-bars-15m", type=int, default=4, help="extra bars after profitable max-hold extension for 15m strategies")
    parser.add_argument("--extended-hold-bars-30m", type=int, default=3, help="extra bars after profitable max-hold extension for 30m strategies")
    parser.add_argument("--extended-hold-bars-1h", type=int, default=12, help="extra bars after profitable max-hold extension for 1h strategies")
    parser.add_argument("--extended-hold-bars-4h", type=int, default=6, help="extra bars after profitable max-hold extension for 4h strategies")
    parser.add_argument("--min-profit-to-extend", type=float, default=0.03, help="profit required to switch max-hold exit to trailing")
    parser.add_argument("--trailing-after-max-hold-pct", type=float, default=0.03, help="trailing pullback after max-hold extension")
    parser.add_argument("--execution-mode", choices=["paper", "testnet"], default="paper", help="paper or Binance testnet execution")
    parser.add_argument("--confirm-exchange-orders", default="", help="set to YES to allow testnet exchange orders")
    parser.add_argument("--order-type", choices=["market", "limit"], default="market", help="market or post-only limit orders")
    parser.add_argument("--maker-offset", type=float, default=0.001, help="limit maker offset, e.g. 0.001 = 0.1%% from signal price")
    args = parser.parse_args()

    monitor = AltcoinPaperMonitor(
        top=args.top,
        candle_limit=args.candle_limit,
        max_margin_ratio=args.max_margin_ratio,
        leverage=args.leverage,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        crash_watch_drop_pct=args.crash_watch_drop_pct,
        crash_watch_breadth_ratio=args.crash_watch_breadth_ratio,
        crash_short_trailing_pct=args.crash_short_trailing_pct,
        open_order_timeout_seconds=args.open_order_timeout_seconds,
        close_order_timeout_seconds=args.close_order_timeout_seconds,
        max_order_failures=args.max_order_failures,
        max_hold_bars_15m=args.max_hold_bars_15m,
        max_hold_bars_30m=args.max_hold_bars_30m,
        max_hold_bars_1h=args.max_hold_bars_1h,
        max_hold_bars_4h=args.max_hold_bars_4h,
        extended_hold_bars_15m=args.extended_hold_bars_15m,
        extended_hold_bars_30m=args.extended_hold_bars_30m,
        extended_hold_bars_1h=args.extended_hold_bars_1h,
        extended_hold_bars_4h=args.extended_hold_bars_4h,
        min_profit_to_extend=args.min_profit_to_extend,
        trailing_after_max_hold_pct=args.trailing_after_max_hold_pct,
        execution_mode=args.execution_mode,
        confirm_exchange_orders=args.confirm_exchange_orders,
        order_type=args.order_type,
        maker_offset=args.maker_offset,
    )
    if args.run_once:
        monitor.run_once()
        return
    while True:
        monitor.run_once()
        time.sleep(max(60, int(args.interval_minutes * 60)))


if __name__ == "__main__":
    main()
