from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone

import websocket

from .macro_monitor import build_monitor
from .websocket_monitor import BINANCE_FUTURES_WS_URL, stream_symbol


class MacroWebSocketMonitor:
    def __init__(
        self,
        top: int = 0,
        candle_limit: int = 300,
        print_seconds: int = 5,
        reconnect_seconds: int = 5,
        maintenance_seconds: int = 30,
        leader_refresh_seconds: int = 60,
        run_initial_cycle: bool = True,
    ) -> None:
        parser = argparse.Namespace(
            top=top,
            candle_limit=candle_limit,
            max_margin_ratio=0.03,
            leverage=2,
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
            crash_watch_drop_pct=0.03,
            crash_watch_breadth_ratio=0.6,
            crash_short_trailing_pct=0.025,
            open_order_timeout_seconds=180,
            close_order_timeout_seconds=60,
            max_order_failures=3,
            max_hold_bars_1h=24,
            max_hold_bars_4h=18,
            extended_hold_bars_1h=12,
            extended_hold_bars_4h=6,
            min_profit_to_extend=0.025,
            trailing_after_max_hold_pct=0.025,
            execution_mode="testnet",
            confirm_exchange_orders="YES",
            order_type="limit",
            maker_offset=0.001,
        )
        self.top = top
        self.print_seconds = max(1, print_seconds)
        self.reconnect_seconds = max(1, reconnect_seconds)
        self.maintenance_seconds = max(5, maintenance_seconds)
        self.leader_refresh_seconds = max(15, leader_refresh_seconds)
        self.monitor = build_monitor(parser)
        self.lock = threading.Lock()
        self.prices: dict[str, float] = {}
        self.last_print_time = 0.0
        self.last_maintenance_time = 0.0
        self.last_leader_refresh_time = 0.0
        self.last_bucket_by_timeframe: dict[str, int] = {}
        self.leaders = self.selected_leaders()
        self.leader_key = self.make_leader_key(self.leaders)
        self.ws = None
        if run_initial_cycle:
            self.run_strategy_cycle("startup")

    def run_forever(self) -> None:
        print(
            f"macro websocket monitor started execution_mode=testnet top={self.top} "
            f"print_seconds={self.print_seconds} maintenance_seconds={self.maintenance_seconds}",
            flush=True,
        )
        while True:
            if not self.leaders:
                print(f"[{self.now()}] macro_websocket_waiting reason=no leaders", flush=True)
                time.sleep(self.leader_refresh_seconds)
                self.refresh_leaders()
                continue
            self.ws = websocket.WebSocketApp(
                self.url(),
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )
            self.ws.run_forever(ping_interval=20, ping_timeout=10)
            time.sleep(self.reconnect_seconds)
            self.refresh_leaders()

    def url(self) -> str:
        streams = [f"{stream_symbol(symbol)}@bookTicker" for symbol in self.symbols()]
        return f"{BINANCE_FUTURES_WS_URL}?streams={'/'.join(streams)}"

    def on_open(self, _ws) -> None:
        print(f"[{self.now()}] macro_websocket=connected streams={self.stream_labels()}", flush=True)

    def on_close(self, _ws, status_code, message) -> None:
        print(f"[{self.now()}] macro_websocket=closed status={status_code} message={message}", flush=True)

    def on_error(self, _ws, error) -> None:
        print(f"[{self.now()}] macro_websocket_error={error}", flush=True)

    def on_message(self, _ws, message: str) -> None:
        payload = json.loads(message)
        stream = payload.get("stream", "")
        data = payload.get("data", {})
        if "@bookTicker" in stream:
            self.handle_book_ticker(stream, data)

    def handle_book_ticker(self, stream: str, data: dict) -> None:
        symbol = self.display_symbol(stream.split("@", 1)[0])
        bid = float(data.get("b") or 0.0)
        ask = float(data.get("a") or 0.0)
        price = (bid + ask) / 2 if bid > 0 and ask > 0 else max(bid, ask)
        if price <= 0:
            return
        with self.lock:
            self.prices[symbol] = price
            now_ts = time.time()
            if now_ts - self.last_print_time >= self.print_seconds:
                self.last_print_time = now_ts
                self.print_tick()
            if now_ts - self.last_maintenance_time >= self.maintenance_seconds:
                self.last_maintenance_time = now_ts
                self.run_maintenance()
            if now_ts - self.last_leader_refresh_time >= self.leader_refresh_seconds:
                self.last_leader_refresh_time = now_ts
                if self.refresh_leaders():
                    if self.ws is not None:
                        self.ws.close()
                    return
        self.check_timeframe_boundaries()

    def check_timeframe_boundaries(self) -> None:
        for timeframe in self.selected_timeframes():
            seconds = self.timeframe_seconds(timeframe)
            bucket = int(datetime.now(timezone.utc).timestamp()) // seconds
            last_bucket = self.last_bucket_by_timeframe.get(timeframe)
            if last_bucket is None:
                self.last_bucket_by_timeframe[timeframe] = bucket
                continue
            if bucket > last_bucket:
                self.last_bucket_by_timeframe[timeframe] = bucket
                self.run_strategy_cycle(f"{timeframe} close")

    def run_strategy_cycle(self, reason: str) -> None:
        try:
            print(f"[{self.now()}] macro_strategy_cycle reason=\"{reason}\"", flush=True)
            self.monitor.run_once()
            self.leaders = self.selected_leaders()
            self.leader_key = self.make_leader_key(self.leaders)
        except Exception as exc:
            print(f"[{self.now()}] macro_strategy_cycle_error reason=\"{reason}\" error={exc}", flush=True)

    def run_maintenance(self) -> None:
        try:
            self.monitor.maintain_orders(self.symbols())
        except Exception as exc:
            print(f"[{self.now()}] macro_maintenance_error={exc}", flush=True)

    def refresh_leaders(self) -> bool:
        leaders = self.selected_leaders()
        leader_key = self.make_leader_key(leaders)
        if leader_key == self.leader_key:
            return False
        old_labels = ",".join(self.symbols()) or "-"
        self.leaders = leaders
        self.leader_key = leader_key
        self.prices = {symbol: price for symbol, price in self.prices.items() if symbol in set(self.symbols())}
        print(f"[{self.now()}] macro_leaders_changed old={old_labels} new={','.join(self.symbols()) or '-'}", flush=True)
        return True

    def print_tick(self) -> None:
        print(
            f"[{self.now()}] macro_account {self.monitor.account_summary()} "
            f"watched_symbols={len(self.symbols())} priced_symbols={len(self.prices)} "
            f"pending_orders={len(self.monitor.pending_orders)} paused_symbols={len(self.monitor.paused_symbols)}",
            flush=True,
        )

    def stream_labels(self) -> str:
        labels = [f"{leader['symbol']}:{leader['strategy_id']}/{leader['timeframe']}:bookTicker" for leader in self.leaders]
        labels.append("strategy_timer=" + ",".join(self.selected_timeframes()))
        labels.append(f"leader_refresh={self.leader_refresh_seconds}s")
        return ",".join(labels)

    def selected_timeframes(self) -> list[str]:
        timeframes = {leader["timeframe"] for leader in self.leaders}
        return sorted(timeframes, key=self.timeframe_seconds)

    def symbols(self) -> list[str]:
        return sorted({leader["symbol"] for leader in self.leaders})

    def selected_leaders(self) -> list[dict]:
        leaders = self.monitor.load_leaders()
        return self.monitor.select_leaders(leaders)

    @staticmethod
    def make_leader_key(leaders: list[dict]) -> tuple[tuple[str, str, str], ...]:
        return tuple((leader["symbol"], leader["strategy_id"], leader["timeframe"]) for leader in leaders)

    @staticmethod
    def timeframe_seconds(timeframe: str) -> int:
        if timeframe.endswith("h"):
            return int(timeframe[:-1]) * 60 * 60
        if timeframe.endswith("m"):
            return int(timeframe[:-1]) * 60
        raise ValueError(f"Unsupported macro websocket timeframe: {timeframe}")

    @staticmethod
    def display_symbol(ws_symbol: str) -> str:
        base = ws_symbol.upper().removesuffix("USDT")
        return f"{base}/USDT:USDT"

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor macro mapped-market strategies with Binance Futures WebSocket")
    parser.add_argument("--top", type=int, default=0, help="number of latest macro leaders to monitor; 0 means all")
    parser.add_argument("--candle-limit", type=int, default=300, help="candles per strategy cycle")
    parser.add_argument("--print-seconds", type=int, default=5, help="seconds between account prints")
    parser.add_argument("--reconnect-seconds", type=int, default=5, help="seconds to wait before reconnecting")
    parser.add_argument("--maintenance-seconds", type=int, default=30, help="seconds between pending-order maintenance checks")
    parser.add_argument("--leader-refresh-seconds", type=int, default=60, help="seconds between strategy leader refresh checks")
    parser.add_argument("--no-initial-cycle", action="store_true", help="do not run strategy immediately on startup")
    args = parser.parse_args()
    monitor = MacroWebSocketMonitor(
        top=args.top,
        candle_limit=args.candle_limit,
        print_seconds=args.print_seconds,
        reconnect_seconds=args.reconnect_seconds,
        maintenance_seconds=args.maintenance_seconds,
        leader_refresh_seconds=args.leader_refresh_seconds,
        run_initial_cycle=not args.no_initial_cycle,
    )
    monitor.run_forever()


if __name__ == "__main__":
    main()

