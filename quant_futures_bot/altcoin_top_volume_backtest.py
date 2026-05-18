from __future__ import annotations

import argparse
import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

import pandas as pd

from . import config
from .backtest import Backtester, BacktestResult
from .data import MarketDataProvider
from .indicators import add_indicators
from .strategy_manager import StrategyManager


DEFAULT_TIMEFRAMES = ["15m", "30m"]
DEFAULT_STRATEGIES = [
    "alt_momentum_6",
    "alt_momentum_12",
    "alt_momentum_24",
    "alt_volume_breakout_12_1_5",
    "alt_volume_breakout",
    "alt_volume_breakout_30_3",
    "alt_volatility_breakout_12_1_2",
    "alt_volatility_breakout",
    "alt_volatility_breakout_30_2",
    "breakout_10",
    "breakout_20",
    "breakout_40",
    "ma_pullback_1",
    "ma_pullback_2",
    "rsi_momentum_55",
    "mean_reversion_10_1_5",
    "mean_reversion_20",
]
EXCLUDED_BASES = {
    "BTC",
    "ETH",
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "XAU",
    "XAG",
    "CL",
    "NATGAS",
    "PAXG",
    "NVDA",
    "TSLA",
    "MSTR",
    "AMD",
    "INTC",
    "EWY",
}


@dataclass
class AltcoinBacktestScore:
    rank: int
    volume_rank: int
    symbol: str
    quote_volume: float
    strategy_id: str
    strategy_name: str
    timeframe: str
    return_pct: float
    max_drawdown: float
    sharpe: float
    trade_count: int
    long_trade_count: int
    short_trade_count: int
    long_pnl: float
    short_pnl: float
    side_balance_ratio: float
    profitable_fold_ratio: float
    win_rate: float
    profit_factor: float
    funding_cost: float
    score: float


def fetch_top_usdt_perpetuals(limit: int = 100, include_majors: bool = False, fetch_timeout_ms: int = 15000) -> list[tuple[str, float]]:
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True, "timeout": fetch_timeout_ms, "options": {"defaultType": "future"}})
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    rows: list[tuple[str, float]] = []
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if not market.get("swap"):
            continue
        if market.get("quote") != "USDT":
            continue
        base = str(market.get("base") or "").upper()
        if not include_majors and base in EXCLUDED_BASES:
            continue
        ticker = tickers.get(symbol, {})
        quote_volume = first_float(
            ticker.get("quoteVolume"),
            ticker.get("info", {}).get("quoteVolume"),
            ticker.get("info", {}).get("volume"),
            0.0,
        )
        if quote_volume <= 0:
            continue
        rows.append((symbol, quote_volume))
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows[:limit]


def run_backtest(
    symbol: str,
    frame: pd.DataFrame,
    strategy_id: str,
    data_source: str,
    max_margin_ratio: float,
    leverage: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_hold_bars: int,
    min_profit_to_extend: float,
    trailing_after_max_hold_pct: float,
    extended_hold_bars: int,
    fee_rate: float,
    funding_cost_rate_per_8h: float,
) -> BacktestResult:
    symbol_configs = {
        symbol: {
            "symbol": symbol,
            "enabled": True,
            "leverage": leverage,
            "max_margin_ratio": max_margin_ratio,
        }
    }
    return Backtester(
        strategy_id=strategy_id,
        frames={symbol: frame.copy()},
        data_sources={symbol: data_source},
        symbol_configs=symbol_configs,
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        max_hold_bars=max_hold_bars,
        min_profit_to_extend=min_profit_to_extend,
        trailing_after_max_hold_pct=trailing_after_max_hold_pct,
        extended_hold_bars=extended_hold_bars,
        fee_rate=fee_rate,
        funding_cost_rate_per_8h=funding_cost_rate_per_8h,
    ).run()


def score_result(
    result: BacktestResult,
    min_trades: int,
    min_side_ratio: float,
    min_profitable_fold_ratio: float,
    fold_count: int,
) -> float:
    if result.trade_count == 0:
        return -999.0
    side_balance = side_balance_ratio(result)
    profitable_folds = profitable_fold_ratio(result.equity_curve, fold_count)
    if result.trade_count < min_trades:
        return -999.0
    if side_balance < min_side_ratio:
        return -999.0
    if profitable_folds < min_profitable_fold_ratio:
        return -999.0
    trade_bonus = min(result.trade_count, 30) * 0.08
    drawdown_penalty = result.max_drawdown * 100 * 2.5
    side_balance_bonus = side_balance * 2.0
    fold_bonus = profitable_folds * 3.0
    return result.return_pct + result.sharpe * 0.35 + trade_bonus + side_balance_bonus + fold_bonus - drawdown_penalty


def side_balance_ratio(result: BacktestResult) -> float:
    if result.trade_count <= 0:
        return 0.0
    return min(result.long_trade_count, result.short_trade_count) / result.trade_count


def profitable_fold_ratio(equity_curve: list[float], fold_count: int) -> float:
    if not equity_curve or fold_count <= 0:
        return 0.0
    fold_size = max(1, len(equity_curve) // fold_count)
    profitable = 0
    tested = 0
    for idx in range(fold_count):
        start = idx * fold_size
        end = len(equity_curve) if idx == fold_count - 1 else min(len(equity_curve), (idx + 1) * fold_size)
        if end - start < 2:
            continue
        tested += 1
        if equity_curve[end - 1] > equity_curve[start]:
            profitable += 1
    return profitable / tested if tested else 0.0


def backtest_top_volume(
    top: int,
    timeframes: list[str],
    strategies: list[str],
    candle_limit: int,
    include_majors: bool,
    max_margin_ratio: float,
    leverage: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    max_hold_bars_15m: int,
    max_hold_bars_30m: int,
    extended_hold_bars_15m: int,
    extended_hold_bars_30m: int,
    min_profit_to_extend: float,
    trailing_after_max_hold_pct: float,
    fee_rate: float,
    funding_cost_rate_per_8h: float,
    fetch_timeout_ms: int,
    fetch_retries: int,
    min_trades: int,
    min_side_ratio: float,
    fold_count: int,
    min_profitable_fold_ratio: float,
) -> list[AltcoinBacktestScore]:
    provider = MarketDataProvider(use_exchange=True, fallback_to_synthetic=False)
    if provider.exchange is not None:
        provider.exchange.timeout = fetch_timeout_ms
    top_symbols = fetch_top_usdt_perpetuals(top, include_majors=include_majors, fetch_timeout_ms=fetch_timeout_ms)
    scores: list[AltcoinBacktestScore] = []
    volume_rank_by_symbol = {symbol: idx for idx, (symbol, _volume) in enumerate(top_symbols, start=1)}
    quote_volume_by_symbol = dict(top_symbols)
    for idx, (symbol, quote_volume) in enumerate(top_symbols, start=1):
        print(f"fetching {idx}/{len(top_symbols)} {symbol} quote_volume={quote_volume:.0f}", flush=True)
        for timeframe in timeframes:
            print(f"fetching_ohlcv {idx}/{len(top_symbols)} {symbol} timeframe={timeframe} limit={candle_limit}", flush=True)
            try:
                frame = fetch_frame_with_retries(provider, symbol, timeframe, candle_limit, fetch_retries)
            except Exception as exc:
                print(f"symbol_skipped symbol={symbol} timeframe={timeframe} reason=fetch_failed error={exc}", flush=True)
                continue
            data_source = provider.last_source_by_symbol.get(symbol, "exchange")
            max_hold_bars = max_hold_bars_for_timeframe(timeframe, max_hold_bars_15m, max_hold_bars_30m)
            extended_hold_bars = max_hold_bars_for_timeframe(timeframe, extended_hold_bars_15m, extended_hold_bars_30m)
            for strategy_id in strategies:
                try:
                    result = run_backtest(
                        symbol,
                        frame,
                        strategy_id,
                        data_source,
                        max_margin_ratio,
                        leverage,
                        stop_loss_pct,
                        take_profit_pct,
                        max_hold_bars,
                        min_profit_to_extend,
                        trailing_after_max_hold_pct,
                        extended_hold_bars,
                        fee_rate,
                        funding_cost_rate_per_8h,
                    )
                except Exception as exc:
                    print(f"backtest_error symbol={symbol} strategy={strategy_id}/{timeframe} error={exc}", flush=True)
                    continue
                balance = side_balance_ratio(result)
                fold_ratio = profitable_fold_ratio(result.equity_curve, fold_count)
                scores.append(
                    AltcoinBacktestScore(
                        rank=0,
                        volume_rank=volume_rank_by_symbol[symbol],
                        symbol=symbol,
                        quote_volume=quote_volume_by_symbol[symbol],
                        strategy_id=strategy_id,
                        strategy_name=StrategyManager.available_strategy_names()[strategy_id],
                        timeframe=timeframe,
                        return_pct=result.return_pct,
                        max_drawdown=result.max_drawdown,
                        sharpe=result.sharpe,
                        trade_count=result.trade_count,
                        long_trade_count=result.long_trade_count,
                        short_trade_count=result.short_trade_count,
                        long_pnl=result.long_pnl,
                        short_pnl=result.short_pnl,
                        side_balance_ratio=balance,
                        profitable_fold_ratio=fold_ratio,
                        win_rate=result.win_rate,
                        profit_factor=result.profit_factor,
                        funding_cost=result.funding_cost,
                        score=score_result(result, min_trades, min_side_ratio, min_profitable_fold_ratio, fold_count),
                    )
                )
    scores.sort(key=lambda item: item.score, reverse=True)
    for rank, item in enumerate(scores, start=1):
        item.rank = rank
    return scores


def fetch_frame_with_retries(
    provider: MarketDataProvider,
    symbol: str,
    timeframe: str,
    candle_limit: int,
    fetch_retries: int,
) -> pd.DataFrame:
    attempts = max(1, fetch_retries + 1)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return add_indicators(provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=candle_limit))
        except Exception as exc:
            last_error = exc
            print(f"fetch_error symbol={symbol} timeframe={timeframe} attempt={attempt}/{attempts} error={exc}", flush=True)
            if attempt < attempts:
                time.sleep(min(5, attempt * 2))
    raise RuntimeError(str(last_error))


def write_csv(path: Path, rows: list[AltcoinBacktestScore]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def print_summary(rows: list[AltcoinBacktestScore], top_n: int) -> None:
    print("altcoin top-volume aggressive strategy backtest")
    for item in rows[:top_n]:
        print(
            f"{item.rank}. volume_rank={item.volume_rank} {item.symbol} "
            f"{item.strategy_id}/{item.timeframe} return={item.return_pct:.2f}% "
            f"dd={item.max_drawdown:.2%} sharpe={item.sharpe:.2f} trades={item.trade_count} "
            f"L/S={item.long_trade_count}/{item.short_trade_count} Lpnl={item.long_pnl:.2f} Spnl={item.short_pnl:.2f} "
            f"side={item.side_balance_ratio:.0%} folds={item.profitable_fold_ratio:.0%} "
            f"win={item.win_rate:.0%} pf={item.profit_factor:.2f} funding={item.funding_cost:.2f} "
            f"score={item.score:.2f}"
        )
    positive = [item for item in rows if item.return_pct > 0 and item.trade_count > 0]
    print(
        f"tested={len(rows)} positive={len(positive)} "
        f"avg_return={mean(item.return_pct for item in rows):.2f}%"
    )


def first_float(*values) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def max_hold_bars_for_timeframe(timeframe: str, max_hold_bars_15m: int, max_hold_bars_30m: int) -> int:
    if timeframe == "15m":
        return max_hold_bars_15m
    if timeframe == "30m":
        return max_hold_bars_30m
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest aggressive strategies on top Binance USDT perpetuals by 24h volume")
    parser.add_argument("--top", type=int, default=100, help="number of top-volume USDT perpetual symbols")
    parser.add_argument("--limit", type=int, default=1000, help="candles per symbol/timeframe")
    parser.add_argument("--timeframes", default="15m,30m", help="comma-separated timeframes")
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES), help="comma-separated strategy ids")
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
    parser.add_argument("--fee-rate", type=float, default=config.MAKER_FEE_RATE, help="estimated fill fee rate for backtest")
    parser.add_argument(
        "--funding-cost-rate-per-8h",
        type=float,
        default=config.FUNDING_COST_RATE_PER_8H,
        help="conservative estimated funding cost per 8h, charged on open notional",
    )
    parser.add_argument("--fetch-timeout-ms", type=int, default=15000, help="ccxt request timeout in milliseconds")
    parser.add_argument("--fetch-retries", type=int, default=1, help="OHLCV fetch retry count per symbol/timeframe")
    parser.add_argument("--min-trades", type=int, default=4, help="minimum closed trades required to qualify")
    parser.add_argument("--min-side-ratio", type=float, default=0.0, help="minimum smaller-side trade ratio; 0 allows one-sided altcoin strategies")
    parser.add_argument("--fold-count", type=int, default=4, help="number of recent equity folds for stability check")
    parser.add_argument("--min-profitable-fold-ratio", type=float, default=0.25, help="minimum ratio of profitable folds")
    parser.add_argument("--show", type=int, default=30, help="number of rows to print")
    parser.add_argument("--output", default="quant_futures_bot/data/altcoin_top_volume_backtest.csv", help="CSV output path")
    args = parser.parse_args()

    timeframes = [item.strip() for item in args.timeframes.split(",") if item.strip()]
    strategies = [item.strip() for item in args.strategies.split(",") if item.strip()]
    rows = backtest_top_volume(
        top=args.top,
        timeframes=timeframes,
        strategies=strategies,
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
        output = Path(args.output)
        write_csv(output, rows)
        print_summary(rows, args.show)
        print(f"csv={output}")
    else:
        print("no symbols tested")


if __name__ == "__main__":
    main()
