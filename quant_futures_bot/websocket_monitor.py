from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone

import websocket

from . import config
from .monitor_output import print_cycle_summary
from .symbol_config import enabled_symbols
from .trading_system import TradingSystem


BINANCE_FUTURES_WS_URL = "wss://fstream.binance.com/stream"


def stream_symbol(symbol: str) -> str:
    return symbol.split("/")[0].lower() + "usdt"


class WebSocketMonitor:
    def __init__(self, print_seconds: int = 5, reconnect_seconds: int = 5, run_initial_cycle: bool = True) -> None:
        self.print_seconds = max(1, print_seconds)
        self.reconnect_seconds = max(1, reconnect_seconds)
        self.system = TradingSystem(use_exchange=True)
        self.prices: dict[str, float] = {}
        self.last_print_time = 0.0
        self.last_bucket_by_timeframe: dict[str, int] = {}
        self.cycle = 0
        self.lock = threading.Lock()
        if run_initial_cycle:
            self.run_strategy_cycle("startup")

    def run_forever(self) -> None:
        print(
            f"websocket monitor started execution_mode={config.EXECUTION_MODE} "
            f"print_seconds={self.print_seconds} reconnect_seconds={self.reconnect_seconds}",
            flush=True,
        )
        while True:
            ws = websocket.WebSocketApp(
                self.url(),
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
            time.sleep(self.reconnect_seconds)

    def url(self) -> str:
        streams: list[str] = []
        for item in enabled_symbols():
            symbol = item["symbol"]
            ws_symbol = stream_symbol(symbol)
            streams.append(f"{ws_symbol}@bookTicker")
        return f"{BINANCE_FUTURES_WS_URL}?streams={'/'.join(streams)}"

    def on_open(self, _ws) -> None:
        print(f"[{self.now()}] websocket=connected streams={self.stream_labels()}", flush=True)

    def on_close(self, _ws, status_code, message) -> None:
        print(f"[{self.now()}] websocket=closed status={status_code} message={message}", flush=True)

    def on_error(self, _ws, error) -> None:
        print(f"[{self.now()}] websocket_error={error}", flush=True)

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
            if time.time() - self.last_print_time >= self.print_seconds:
                self.last_print_time = time.time()
                self.print_tick()
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
                print(f"[{self.now()}] timeframe_closed interval={timeframe}", flush=True)
                self.run_strategy_cycle(f"{timeframe} close")

    def run_strategy_cycle(self, reason: str) -> None:
        with self.lock:
            self.cycle += 1
            cycle = self.cycle
        try:
            self.system.run_cycle()
            print(f"[{self.now()}] strategy_cycle reason=\"{reason}\"", flush=True)
            print_cycle_summary(self.system, cycle)
        except Exception as exc:
            print(f"[{self.now()}] strategy_cycle_error reason=\"{reason}\" error={exc}", flush=True)

    def print_tick(self) -> None:
        prices = ",".join(f"{symbol}={price:.4f}" for symbol, price in sorted(self.prices.items())) or "-"
        print(
            f"[{self.now()}] websocket_tick prices={prices} "
            f"equity={self.system.portfolio.equity:.2f} status={self.system.pause_manager.status} "
            f"exchange_positions={self.system.exchange_positions_summary}",
            flush=True,
        )

    def stream_labels(self) -> str:
        labels = []
        for item in enabled_symbols():
            symbol = item["symbol"]
            labels.append(f"{symbol}:bookTicker")
        labels.append("strategy_timer=" + ",".join(self.selected_timeframes()))
        return ",".join(labels)

    def selected_timeframes(self) -> list[str]:
        timeframes = {
            self.system.strategy_manager.timeframe_for_symbol(item["symbol"], default="4h")
            for item in enabled_symbols()
        }
        return sorted(timeframes, key=self.timeframe_seconds)

    @staticmethod
    def timeframe_seconds(timeframe: str) -> int:
        if timeframe.endswith("h"):
            return int(timeframe[:-1]) * 60 * 60
        if timeframe.endswith("m"):
            return int(timeframe[:-1]) * 60
        raise ValueError(f"Unsupported websocket strategy timeframe: {timeframe}")

    @staticmethod
    def display_symbol(ws_symbol: str) -> str:
        base = ws_symbol.upper().removesuffix("USDT")
        return f"{base}/USDT:USDT"

    @staticmethod
    def now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor Binance Futures prices with WebSocket and run strategy on timeframe close")
    parser.add_argument("--print-seconds", type=int, default=5, help="seconds between real-time price prints")
    parser.add_argument("--reconnect-seconds", type=int, default=5, help="seconds to wait before reconnecting")
    parser.add_argument("--no-initial-cycle", action="store_true", help="do not run strategy immediately on startup")
    args = parser.parse_args()
    monitor = WebSocketMonitor(
        print_seconds=args.print_seconds,
        reconnect_seconds=args.reconnect_seconds,
        run_initial_cycle=not args.no_initial_cycle,
    )
    monitor.run_forever()


if __name__ == "__main__":
    main()
