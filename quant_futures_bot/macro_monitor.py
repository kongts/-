from __future__ import annotations

import argparse
import time

from .altcoin_paper_monitor import AltcoinPaperMonitor
from .config import DATA_DIR


MACRO_STRATEGY_PATH = DATA_DIR / "macro_strategy_latest.json"
MACRO_PAPER_STATE_PATH = DATA_DIR / "macro_paper_state.json"
MACRO_PAPER_LATEST_PATH = DATA_DIR / "macro_paper_latest.json"
MACRO_PAPER_RUNTIME_PATH = DATA_DIR / "macro_paper_runtime_state.json"
MACRO_TESTNET_STATE_PATH = DATA_DIR / "macro_testnet_state.json"
MACRO_TESTNET_LATEST_PATH = DATA_DIR / "macro_testnet_latest.json"
MACRO_TESTNET_RUNTIME_PATH = DATA_DIR / "macro_testnet_runtime_state.json"


def build_monitor(args: argparse.Namespace) -> AltcoinPaperMonitor:
    if args.execution_mode == "testnet":
        state_path = MACRO_TESTNET_STATE_PATH
        latest_path = MACRO_TESTNET_LATEST_PATH
        runtime_state_path = MACRO_TESTNET_RUNTIME_PATH
        log_filename = "macro_testnet.log"
    else:
        state_path = MACRO_PAPER_STATE_PATH
        latest_path = MACRO_PAPER_LATEST_PATH
        runtime_state_path = MACRO_PAPER_RUNTIME_PATH
        log_filename = "macro_paper.log"
    return AltcoinPaperMonitor(
        strategy_path=MACRO_STRATEGY_PATH,
        state_path=state_path,
        latest_path=latest_path,
        runtime_state_path=runtime_state_path,
        board_name="macro",
        log_filename=log_filename,
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
        max_hold_bars_1h=args.max_hold_bars_1h,
        max_hold_bars_4h=args.max_hold_bars_4h,
        extended_hold_bars_1h=args.extended_hold_bars_1h,
        extended_hold_bars_4h=args.extended_hold_bars_4h,
        min_profit_to_extend=args.min_profit_to_extend,
        trailing_after_max_hold_pct=args.trailing_after_max_hold_pct,
        execution_mode=args.execution_mode,
        confirm_exchange_orders=args.confirm_exchange_orders,
        order_type=args.order_type,
        maker_offset=args.maker_offset,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paper/testnet monitor for macro mapped-market strategies")
    parser.add_argument("--run-once", action="store_true", help="run once and exit")
    parser.add_argument("--interval-minutes", type=float, default=60.0, help="minutes between cycles")
    parser.add_argument("--top", type=int, default=0, help="number of latest leaders to trade; 0 means all")
    parser.add_argument("--candle-limit", type=int, default=300, help="candles per symbol/timeframe")
    parser.add_argument("--max-margin-ratio", type=float, default=0.03, help="margin ratio per symbol")
    parser.add_argument("--leverage", type=int, default=2, help="leverage")
    parser.add_argument("--stop-loss-pct", type=float, default=0.02, help="stop loss percentage")
    parser.add_argument("--take-profit-pct", type=float, default=0.05, help="take profit percentage")
    parser.add_argument("--crash-watch-drop-pct", type=float, default=0.03, help="recent drop percentage that enables short trailing")
    parser.add_argument("--crash-watch-breadth-ratio", type=float, default=0.6, help="ratio of traded symbols that must drop")
    parser.add_argument("--crash-short-trailing-pct", type=float, default=0.025, help="short trailing take profit pullback in crash watch")
    parser.add_argument("--open-order-timeout-seconds", type=int, default=180, help="cancel unfilled opening limit orders after this many seconds")
    parser.add_argument("--close-order-timeout-seconds", type=int, default=60, help="cancel unfilled closing limit orders after this many seconds")
    parser.add_argument("--max-order-failures", type=int, default=3, help="pause a symbol after this many consecutive order failures")
    parser.add_argument("--max-hold-bars-1h", type=int, default=24, help="max holding bars for 1h strategies")
    parser.add_argument("--max-hold-bars-4h", type=int, default=18, help="max holding bars for 4h strategies")
    parser.add_argument("--extended-hold-bars-1h", type=int, default=12, help="extra bars after profitable max-hold extension for 1h strategies")
    parser.add_argument("--extended-hold-bars-4h", type=int, default=6, help="extra bars after profitable max-hold extension for 4h strategies")
    parser.add_argument("--min-profit-to-extend", type=float, default=0.025, help="profit required to switch max-hold exit to trailing")
    parser.add_argument("--trailing-after-max-hold-pct", type=float, default=0.025, help="trailing pullback after max-hold extension")
    parser.add_argument("--execution-mode", choices=["paper", "testnet"], default="paper", help="paper or Binance testnet execution")
    parser.add_argument("--confirm-exchange-orders", default="", help="set to YES to allow testnet exchange orders")
    parser.add_argument("--order-type", choices=["market", "limit"], default="market", help="market or post-only limit orders")
    parser.add_argument("--maker-offset", type=float, default=0.001, help="limit maker offset")
    args = parser.parse_args()

    monitor = build_monitor(args)
    if args.run_once:
        monitor.run_once()
        return
    while True:
        monitor.run_once()
        time.sleep(max(60, int(args.interval_minutes * 60)))


if __name__ == "__main__":
    main()

