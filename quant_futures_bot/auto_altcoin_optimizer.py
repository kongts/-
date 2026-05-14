from __future__ import annotations

import argparse
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

from .altcoin_top_volume_backtest import backtest_top_volume, print_summary, write_csv
from .config import DATA_DIR, FUNDING_COST_RATE_PER_8H, LOG_DIR, MAKER_FEE_RATE


def run_once(args: argparse.Namespace) -> None:
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log(f"[{started_at}] start altcoin aggressive rolling backtest")
    log(
        "config "
        f"top={args.top} limit={args.limit} timeframes={args.timeframes} strategies={args.strategies} "
        f"stop_loss={args.stop_loss_pct:.2%} take_profit={args.take_profit_pct:.2%} "
        f"max_margin_ratio={args.max_margin_ratio:.2%} leverage={args.leverage}x "
        f"max_hold_15m={args.max_hold_bars_15m} max_hold_30m={args.max_hold_bars_30m} "
        f"extended_hold_15m={args.extended_hold_bars_15m} extended_hold_30m={args.extended_hold_bars_30m} "
        f"min_profit_to_extend={args.min_profit_to_extend:.2%} trailing_after_max_hold={args.trailing_after_max_hold_pct:.2%} "
        f"fee_rate={args.fee_rate:.4%} funding_cost_per_8h={args.funding_cost_rate_per_8h:.4%} "
        f"fetch_timeout_ms={args.fetch_timeout_ms} fetch_retries={args.fetch_retries} "
        f"min_trades={args.min_trades} min_side_ratio={args.min_side_ratio:.0%} "
        f"fold_count={args.fold_count} min_profitable_fold_ratio={args.min_profitable_fold_ratio:.0%}"
    )
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
        max_hold_bars_15m=args.max_hold_bars_15m,
        max_hold_bars_30m=args.max_hold_bars_30m,
        extended_hold_bars_15m=args.extended_hold_bars_15m,
        extended_hold_bars_30m=args.extended_hold_bars_30m,
        min_profit_to_extend=args.min_profit_to_extend,
        trailing_after_max_hold_pct=args.trailing_after_max_hold_pct,
        fee_rate=args.fee_rate,
        funding_cost_rate_per_8h=args.funding_cost_rate_per_8h,
        fetch_timeout_ms=args.fetch_timeout_ms,
        fetch_retries=args.fetch_retries,
        min_trades=args.min_trades,
        min_side_ratio=args.min_side_ratio,
        fold_count=args.fold_count,
        min_profitable_fold_ratio=args.min_profitable_fold_ratio,
    )
    if rows:
        write_csv(Path(args.output), rows)
        write_latest_json(rows, Path(args.latest_json), args)
        print_summary(rows, args.show)
        selected = select_latest_leaders(rows, args.min_score, args.max_leaders)
        for item in selected[: args.show]:
            log(
                f"rank={item.rank} volume_rank={item.volume_rank} symbol={item.symbol} "
                f"strategy={item.strategy_id}/{item.timeframe} return={item.return_pct:.2f}% "
                f"dd={item.max_drawdown:.2%} sharpe={item.sharpe:.2f} trades={item.trade_count} "
                f"L/S={item.long_trade_count}/{item.short_trade_count} Lpnl={item.long_pnl:.2f} Spnl={item.short_pnl:.2f} "
                f"side={item.side_balance_ratio:.0%} folds={item.profitable_fold_ratio:.0%} "
                f"win={item.win_rate:.0%} pf={item.profit_factor:.2f} funding={item.funding_cost:.2f} "
                f"score={item.score:.2f}"
            )
        positive = [item for item in rows if item.return_pct > 0 and item.trade_count > 0]
        log(
            f"summary tested={len(rows)} positive={len(positive)} selected={len(selected)} "
            f"min_score={args.min_score:.2f} max_leaders={args.max_leaders} "
            f"csv={args.output} latest_json={args.latest_json}"
        )
    else:
        log("no altcoin rows generated")


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = message if message.startswith("[") else f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    with (LOG_DIR / "altcoin_strategy.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


class RunLock:
    def __init__(self, path: Path, stale_seconds: int) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.fd: int | None = None
        self.acquired = False

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_stale_lock()
        try:
            self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(self.fd, f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}\n".encode("utf-8"))
            self.acquired = True
        except FileExistsError:
            log(f"optimizer_lock_exists path={self.path} action=skip")
            return False
        return True

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fd is not None:
            os.close(self.fd)
        if not self.acquired:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def _remove_stale_lock(self) -> None:
        if not self.path.exists():
            return
        age = time.time() - self.path.stat().st_mtime
        if age >= self.stale_seconds:
            log(f"optimizer_stale_lock_removed path={self.path} age_seconds={age:.0f}")
            self.path.unlink(missing_ok=True)


def select_latest_leaders(rows, min_score: float, max_leaders: int) -> list:
    selected = [item for item in rows if item.score >= min_score]
    if max_leaders > 0:
        return selected[:max_leaders]
    return selected


def write_latest_json(rows, path: Path, args: argparse.Namespace) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    leaders = select_latest_leaders(rows, args.min_score, args.max_leaders)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "selection_mode": "score_threshold",
        "min_score": args.min_score,
        "max_leaders": args.max_leaders,
        "min_trades": args.min_trades,
        "min_side_ratio": args.min_side_ratio,
        "fold_count": args.fold_count,
        "min_profitable_fold_ratio": args.min_profitable_fold_ratio,
        "fee_rate": args.fee_rate,
        "funding_cost_rate_per_8h": args.funding_cost_rate_per_8h,
        "tested_count": len(rows),
        "leader_count": len(leaders),
        "leaders": [
            {
                "rank": item.rank,
                "volume_rank": item.volume_rank,
                "symbol": item.symbol,
                "strategy_id": item.strategy_id,
                "strategy_name": item.strategy_name,
                "timeframe": item.timeframe,
                "return_pct": item.return_pct,
                "max_drawdown": item.max_drawdown,
                "sharpe": item.sharpe,
                "trade_count": item.trade_count,
                "long_trade_count": item.long_trade_count,
                "short_trade_count": item.short_trade_count,
                "long_pnl": item.long_pnl,
                "short_pnl": item.short_pnl,
                "side_balance_ratio": item.side_balance_ratio,
                "profitable_fold_ratio": item.profitable_fold_ratio,
                "win_rate": item.win_rate,
                "profit_factor": finite_or_inf(item.profit_factor),
                "funding_cost": item.funding_cost,
                "score": item.score,
            }
            for item in leaders
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def finite_or_inf(value: float) -> float | str:
    return value if math.isfinite(value) else "inf"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run top-volume altcoin aggressive backtest every N minutes")
    parser.add_argument("--interval-minutes", type=float, default=30.0, help="minutes between rolling updates")
    parser.add_argument("--run-once", action="store_true", help="run once and exit")
    parser.add_argument("--run-once-first", action="store_true", help="run immediately before waiting")
    parser.add_argument("--top", type=int, default=100, help="number of top-volume USDT perpetual symbols")
    parser.add_argument("--limit", type=int, default=1000, help="candles per symbol/timeframe")
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
    parser.add_argument("--max-hold-bars-15m", type=int, default=8, help="max holding bars for 15m strategies")
    parser.add_argument("--max-hold-bars-30m", type=int, default=6, help="max holding bars for 30m strategies")
    parser.add_argument("--extended-hold-bars-15m", type=int, default=4, help="extra bars after profitable max-hold extension for 15m strategies")
    parser.add_argument("--extended-hold-bars-30m", type=int, default=3, help="extra bars after profitable max-hold extension for 30m strategies")
    parser.add_argument("--min-profit-to-extend", type=float, default=0.03, help="profit required to switch max-hold exit to trailing")
    parser.add_argument("--trailing-after-max-hold-pct", type=float, default=0.03, help="trailing pullback after max-hold extension")
    parser.add_argument("--fee-rate", type=float, default=MAKER_FEE_RATE, help="estimated fill fee rate for backtest")
    parser.add_argument(
        "--funding-cost-rate-per-8h",
        type=float,
        default=FUNDING_COST_RATE_PER_8H,
        help="conservative estimated funding cost per 8h, charged on open notional",
    )
    parser.add_argument("--fetch-timeout-ms", type=int, default=15000, help="ccxt request timeout in milliseconds")
    parser.add_argument("--fetch-retries", type=int, default=1, help="OHLCV fetch retry count per symbol/timeframe")
    parser.add_argument("--min-trades", type=int, default=8, help="minimum closed trades required to qualify")
    parser.add_argument("--min-side-ratio", type=float, default=0.20, help="minimum smaller-side trade ratio, e.g. 0.2 prevents one-sided overfit")
    parser.add_argument("--fold-count", type=int, default=4, help="number of recent equity folds for stability check")
    parser.add_argument("--min-profitable-fold-ratio", type=float, default=1.0, help="minimum ratio of profitable folds")
    parser.add_argument("--lock-timeout-minutes", type=float, default=120.0, help="remove optimizer lock after this many minutes")
    parser.add_argument("--show", type=int, default=30, help="number of rows to print")
    parser.add_argument("--min-score", type=float, default=1.0, help="write all rows with score >= this value to latest-json")
    parser.add_argument("--max-leaders", type=int, default=0, help="cap latest-json leaders; 0 means no cap")
    parser.add_argument(
        "--output",
        default="quant_futures_bot/data/altcoin_top100_rolling_backtest.csv",
        help="CSV output path",
    )
    parser.add_argument(
        "--latest-json",
        default="quant_futures_bot/data/altcoin_strategy_latest.json",
        help="latest strategy summary JSON path",
    )
    args = parser.parse_args()

    interval_seconds = max(60, int(args.interval_minutes * 60))
    if args.run_once:
        with RunLock(DATA_DIR / "altcoin_optimizer.lock", int(args.lock_timeout_minutes * 60)) as locked:
            if locked:
                run_once(args)
        return
    if args.run_once_first:
        with RunLock(DATA_DIR / "altcoin_optimizer.lock", int(args.lock_timeout_minutes * 60)) as locked:
            if locked:
                run_once(args)
    while True:
        next_at = datetime.fromtimestamp(time.time() + interval_seconds).strftime("%Y-%m-%d %H:%M:%S")
        print(f"next altcoin aggressive rolling backtest at {next_at}", flush=True)
        time.sleep(interval_seconds)
        with RunLock(DATA_DIR / "altcoin_optimizer.lock", int(args.lock_timeout_minutes * 60)) as locked:
            if locked:
                run_once(args)


if __name__ == "__main__":
    main()
