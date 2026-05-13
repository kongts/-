from __future__ import annotations

import argparse
import time
from datetime import datetime
from pathlib import Path

from .altcoin_top_volume_backtest import backtest_top_volume, print_summary, write_csv


def run_once(args: argparse.Namespace) -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{started_at}] start altcoin aggressive rolling backtest", flush=True)
    rows = backtest_top_volume(
        top=args.top,
        timeframes=[item.strip() for item in args.timeframes.split(",") if item.strip()],
        strategies=[item.strip() for item in args.strategies.split(",") if item.strip()],
        candle_limit=args.limit,
        include_majors=args.include_majors,
        max_margin_ratio=args.max_margin_ratio,
        leverage=args.leverage,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
    )
    if rows:
        write_csv(Path(args.output), rows)
        print_summary(rows, args.show)
        print(f"csv={args.output}", flush=True)
    else:
        print("no altcoin rows generated", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run top-volume altcoin aggressive backtest every N minutes")
    parser.add_argument("--interval-minutes", type=float, default=30.0, help="minutes between rolling updates")
    parser.add_argument("--run-once", action="store_true", help="run once and exit")
    parser.add_argument("--run-once-first", action="store_true", help="run immediately before waiting")
    parser.add_argument("--top", type=int, default=100, help="number of top-volume USDT perpetual symbols")
    parser.add_argument("--limit", type=int, default=500, help="candles per symbol/timeframe")
    parser.add_argument("--timeframes", default="15m,30m", help="comma-separated timeframes")
    parser.add_argument(
        "--strategies",
        default="alt_momentum_12,alt_volume_breakout,alt_volatility_breakout",
        help="comma-separated strategy ids",
    )
    parser.add_argument("--include-majors", action="store_true", help="include BTC/ETH and stablecoin-like symbols")
    parser.add_argument("--max-margin-ratio", type=float, default=0.03, help="margin ratio per symbol for backtest sizing")
    parser.add_argument("--leverage", type=int, default=2, help="leverage for backtest sizing")
    parser.add_argument("--stop-loss-pct", type=float, default=0.025, help="stop loss percentage, e.g. 0.025 = 2.5%%")
    parser.add_argument("--take-profit-pct", type=float, default=0.06, help="take profit percentage, e.g. 0.06 = 6%%")
    parser.add_argument("--show", type=int, default=30, help="number of rows to print")
    parser.add_argument(
        "--output",
        default="quant_futures_bot/data/altcoin_top100_rolling_backtest.csv",
        help="CSV output path",
    )
    args = parser.parse_args()

    interval_seconds = max(60, int(args.interval_minutes * 60))
    if args.run_once:
        run_once(args)
        return
    if args.run_once_first:
        run_once(args)
    while True:
        next_at = datetime.fromtimestamp(time.time() + interval_seconds).strftime("%Y-%m-%d %H:%M:%S")
        print(f"next altcoin aggressive rolling backtest at {next_at}", flush=True)
        time.sleep(interval_seconds)
        run_once(args)


if __name__ == "__main__":
    main()
