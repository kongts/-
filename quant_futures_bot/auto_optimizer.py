from __future__ import annotations

import argparse
import time
from datetime import datetime

from .strategy_optimizer import optimize_by_symbol


def run_once(offline: bool, limit: int, train_size: int, test_size: int, step_size: int) -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{started_at}] start strategy optimization")
    winners, _, data_sources = optimize_by_symbol(
        offline=offline,
        limit=limit,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size,
    )
    for symbol, winner in sorted(winners.items()):
        print(
            f"selected {symbol}: strategy={winner.strategy_id} timeframe={winner.timeframe} "
            f"avg_test_return={winner.avg_test_return_pct:.2f}% avg_test_dd={winner.avg_test_drawdown:.2%} "
            f"avg_test_sharpe={winner.avg_test_sharpe:.2f} trades={winner.total_test_trades} "
            f"stable_folds={winner.stable_fold_ratio:.0%} score={winner.selected_score:.2f}"
        )
    print("data_source=" + ",".join(f"{key}={source}" for key, source in sorted(data_sources.items())))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strategy optimization every N hours")
    parser.add_argument("--offline", action="store_true", help="use synthetic data instead of exchange data")
    parser.add_argument("--interval-hours", type=float, default=4.0, help="hours between optimizations")
    parser.add_argument("--run-once-first", action="store_true", help="run immediately before waiting")
    parser.add_argument("--limit", type=int, default=800, help="number of candles per symbol/timeframe")
    parser.add_argument("--train-size", type=int, default=360, help="walk-forward train candles")
    parser.add_argument("--test-size", type=int, default=120, help="walk-forward test candles")
    parser.add_argument("--step-size", type=int, default=120, help="walk-forward step candles")
    args = parser.parse_args()

    interval_seconds = max(60, int(args.interval_hours * 60 * 60))
    if args.run_once_first:
        run_once(args.offline, args.limit, args.train_size, args.test_size, args.step_size)
    while True:
        next_at = datetime.fromtimestamp(time.time() + interval_seconds).strftime("%Y-%m-%d %H:%M:%S")
        print(f"next strategy optimization at {next_at}")
        time.sleep(interval_seconds)
        run_once(args.offline, args.limit, args.train_size, args.test_size, args.step_size)


if __name__ == "__main__":
    main()
