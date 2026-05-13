from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from .account_sync import BinanceAccountSync
from .config import DATA_DIR, FEE_RATE, LOG_DIR
from .data import MarketDataProvider
from .events import OrderStatus, SignalEvent, SignalType
from .execution import BinanceTestnetExecution, PaperExecution
from .indicators import add_indicators
from .market_state import detect_market_state
from .order_manager import OrderManager
from .pause_manager import PauseManager
from .portfolio import Portfolio
from .risk_engine import RiskEngine
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
        top: int = 5,
        candle_limit: int = 220,
        max_margin_ratio: float = 0.03,
        leverage: int = 2,
        stop_loss_pct: float = 0.025,
        take_profit_pct: float = 0.06,
        crash_drop_pct: float = 0.08,
        crash_breadth_ratio: float = 0.6,
        crash_short_trailing_pct: float = 0.03,
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
            state_path = DATA_DIR / "altcoin_testnet_state.json"
            latest_path = DATA_DIR / "altcoin_testnet_latest.json"
            runtime_state_path = DATA_DIR / "altcoin_testnet_runtime_state.json"
        else:
            runtime_state_path = DEFAULT_RUNTIME_STATE_PATH
        self.strategy_path = strategy_path
        self.state_path = state_path
        self.latest_path = latest_path
        self.runtime_state_path = runtime_state_path
        self.execution_mode = execution_mode
        self.order_type = order_type
        self.maker_offset = maker_offset
        self.top = top
        self.candle_limit = candle_limit
        self.max_margin_ratio = max_margin_ratio
        self.leverage = leverage
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.crash_drop_pct = crash_drop_pct
        self.crash_breadth_ratio = crash_breadth_ratio
        self.crash_short_trailing_pct = crash_short_trailing_pct
        self.data_provider = MarketDataProvider(use_exchange=True, fallback_to_synthetic=False)
        self.portfolio = self.load_portfolio()
        runtime_state = self.load_runtime_state()
        self.short_trailing_peaks: dict[str, float] = dict(runtime_state.get("short_trailing_peaks", {}))
        self.pause_manager = PauseManager()
        self.execution = BinanceTestnetExecution() if execution_mode == "testnet" else PaperExecution()
        self.account_sync = BinanceAccountSync(self.execution.exchange) if isinstance(self.execution, BinanceTestnetExecution) else None
        self.order_manager = OrderManager()
        self.exchange_open_order_count = 0
        self.exchange_positions_summary = "-"

    def run_once(self) -> None:
        leaders = self.load_leaders()
        cycle_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log(f"[{cycle_started_at}] start altcoin {self.execution_mode} cycle leaders={len(leaders)} top={self.top}")
        self.sync_exchange_account([leader["symbol"] for leader in leaders[: self.top]])
        signals_created = 0
        orders_created = 0
        fills_created = 0
        rejected = 0
        exchange_order_ids: list[str] = []
        market_contexts: list[dict] = []
        for leader in leaders[: self.top]:
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
        crash_mode = self.detect_crash_mode(market_contexts)
        if crash_mode:
            drops = [context["recent_drop"] for context in market_contexts if context["recent_drop"] is not None]
            avg_drop = sum(drops) / len(drops) if drops else 0.0
            self.log(
                f"crash_mode=ON symbols={len(drops)} avg_recent_drop={avg_drop:.2%} "
                f"trigger_drop={self.crash_drop_pct:.2%} short_trailing={self.crash_short_trailing_pct:.2%}"
            )
        for context in market_contexts:
            symbol = context["symbol"]
            strategy_id = context["strategy_id"]
            timeframe = context["timeframe"]
            try:
                frame = context["frame"]
                price = context["price"]
                latest_row = context["latest_row"]
                exit_signal = self.stop_or_take_profit_signal(symbol, price, crash_mode)
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
                signals = manager.generate(symbol, frame, market_state, current_side)
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
            f"{self.execution_mode}_summary equity={self.portfolio.equity:.2f} used_margin={self.portfolio.used_margin:.2f} "
            f"unrealized={self.portfolio.unrealized_pnl:.2f} realized={self.portfolio.realized_pnl:.2f} "
            f"signals={signals_created} orders={orders_created} fills={fills_created} rejected={rejected} order_type={self.order_type} "
            f"exchange_order_ids={','.join(exchange_order_ids) or '-'} exchange_open_orders={self.exchange_open_order_count} "
            f"exchange_positions={self.exchange_positions_summary} positions={self.format_positions()}"
        )

    def sync_exchange_account(self, symbols: list[str]) -> None:
        if self.account_sync is None:
            self.exchange_open_order_count = 0
            self.exchange_positions_summary = "-"
            return
        snapshot = self.account_sync.fetch(symbols)
        self.exchange_open_order_count = snapshot.open_order_count
        self.portfolio.sync_from_exchange(snapshot.to_portfolio_payload())
        self.exchange_positions_summary = self.format_exchange_positions(snapshot.positions or {})

    def execute_signal(self, signal: SignalEvent, latest_row: dict) -> tuple[bool, bool, list[str]]:
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

    def stop_or_take_profit_signal(self, symbol: str, price: float, crash_mode: bool) -> SignalEvent | None:
        pos = self.portfolio.get_position(symbol)
        if not pos.is_open() or pos.entry_price <= 0:
            self.short_trailing_peaks.pop(symbol, None)
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
            return SignalEvent(symbol, close_type, "Altcoin Paper Stop Loss", price)
        if pos.position_side == "SHORT" and crash_mode:
            peak = max(self.short_trailing_peaks.get(symbol, change), change)
            self.short_trailing_peaks[symbol] = peak
            pullback = peak - change
            if peak >= self.take_profit_pct and pullback >= self.crash_short_trailing_pct:
                self.short_trailing_peaks.pop(symbol, None)
                return SignalEvent(symbol, close_type, "Altcoin Crash Short Trailing Take Profit", price)
            return None
        if change >= self.take_profit_pct:
            self.short_trailing_peaks.pop(symbol, None)
            return SignalEvent(symbol, close_type, "Altcoin Paper Take Profit", price)
        return None

    def recent_drop(self, frame) -> float | None:
        if len(frame) < 5:
            return None
        previous = float(frame.iloc[-5]["close"])
        latest = float(frame.iloc[-1]["close"])
        if previous <= 0:
            return None
        return latest / previous - 1

    def detect_crash_mode(self, market_contexts: list[dict]) -> bool:
        drops = [context["recent_drop"] for context in market_contexts if context["recent_drop"] is not None]
        if not drops:
            return False
        severe_count = sum(1 for drop in drops if drop <= -self.crash_drop_pct)
        breadth = severe_count / len(drops)
        return breadth >= self.crash_breadth_ratio

    def load_leaders(self) -> list[dict]:
        if not self.strategy_path.exists():
            self.log(f"missing_altcoin_strategy_latest path={self.strategy_path}")
            return []
        payload = json.loads(self.strategy_path.read_text(encoding="utf-8"))
        return list(payload.get("leaders", []))

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

    def save_runtime_state(self) -> None:
        self.runtime_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "short_trailing_peaks": self.short_trailing_peaks,
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
            "order_type": self.order_type,
            "crash_drop_pct": self.crash_drop_pct,
            "crash_breadth_ratio": self.crash_breadth_ratio,
            "crash_short_trailing_pct": self.crash_short_trailing_pct,
            "short_trailing_peaks": self.short_trailing_peaks,
            "fee_rate": FEE_RATE,
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
        log_name = "altcoin_testnet.log" if getattr(self, "execution_mode", "paper") == "testnet" else "altcoin_paper.log"
        with (LOG_DIR / log_name).open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paper/testnet trading monitor for latest altcoin aggressive strategies")
    parser.add_argument("--run-once", action="store_true", help="run once and exit")
    parser.add_argument("--interval-minutes", type=float, default=15.0, help="minutes between paper cycles")
    parser.add_argument("--top", type=int, default=5, help="number of latest leaders to paper trade")
    parser.add_argument("--candle-limit", type=int, default=220, help="candles per symbol/timeframe")
    parser.add_argument("--max-margin-ratio", type=float, default=0.03, help="margin ratio per symbol")
    parser.add_argument("--leverage", type=int, default=2, help="paper leverage")
    parser.add_argument("--stop-loss-pct", type=float, default=0.025, help="stop loss percentage")
    parser.add_argument("--take-profit-pct", type=float, default=0.06, help="take profit percentage")
    parser.add_argument("--crash-drop-pct", type=float, default=0.08, help="recent drop percentage that counts as crash")
    parser.add_argument("--crash-breadth-ratio", type=float, default=0.6, help="ratio of traded symbols that must crash")
    parser.add_argument("--crash-short-trailing-pct", type=float, default=0.03, help="short trailing take profit pullback in crash mode")
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
        crash_drop_pct=args.crash_drop_pct,
        crash_breadth_ratio=args.crash_breadth_ratio,
        crash_short_trailing_pct=args.crash_short_trailing_pct,
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
