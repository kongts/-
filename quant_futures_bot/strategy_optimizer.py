from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from statistics import mean

import pandas as pd

from .backtest import Backtester, BacktestResult
from .data import MarketDataProvider
from .indicators import add_indicators
from .selected_strategy import save_selected_strategy
from .strategy_manager import StrategyManager
from .symbol_config import enabled_symbols

TIMEFRAMES = ["4h", "6h"]


@dataclass
class FoldScore:
    train_return_pct: float
    train_max_drawdown: float
    train_sharpe: float
    train_trade_count: int
    test_return_pct: float
    test_max_drawdown: float
    test_sharpe: float
    test_trade_count: int
    test_score: float


@dataclass
class SymbolStrategyScore:
    symbol: str
    strategy_id: str
    strategy_name: str
    timeframe: str
    folds: int
    avg_test_return_pct: float
    avg_test_drawdown: float
    avg_test_sharpe: float
    total_test_trades: int
    stable_fold_ratio: float
    selected_score: float


def fetch_symbol_frame(provider: MarketDataProvider, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    return add_indicators(provider.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit))


def walk_forward_slices(length: int, train_size: int, test_size: int, step_size: int) -> list[tuple[slice, slice]]:
    slices: list[tuple[slice, slice]] = []
    start = 0
    while start + train_size + test_size <= length:
        train = slice(start, start + train_size)
        test = slice(start + train_size - 80, start + train_size + test_size)
        slices.append((train, test))
        start += step_size
    if not slices and length >= 160:
        train_end = int(length * 0.7)
        slices.append((slice(0, train_end), slice(max(0, train_end - 80), length)))
    return slices


def score_result(result: BacktestResult) -> float:
    if result.trade_count == 0:
        trade_penalty = 25.0
    elif result.trade_count < 3:
        trade_penalty = 10.0
    else:
        trade_penalty = 0.0
    drawdown_penalty = result.max_drawdown * 100 * 2.0
    return result.return_pct + result.sharpe * 0.4 - drawdown_penalty - trade_penalty


def run_symbol_backtest(symbol: str, frame: pd.DataFrame, strategy_id: str, data_source: str) -> BacktestResult:
    return Backtester(
        strategy_id=strategy_id,
        frames={symbol: frame.copy()},
        data_sources={symbol: data_source},
    ).run()


def evaluate_candidate(
    symbol: str,
    strategy_id: str,
    timeframe: str,
    frame: pd.DataFrame,
    data_source: str,
    train_size: int,
    test_size: int,
    step_size: int,
) -> SymbolStrategyScore:
    fold_scores: list[FoldScore] = []
    for train_slice, test_slice in walk_forward_slices(len(frame), train_size, test_size, step_size):
        train_frame = frame.iloc[train_slice].copy()
        test_frame = frame.iloc[test_slice].copy()
        train_result = run_symbol_backtest(symbol, train_frame, strategy_id, data_source)
        test_result = run_symbol_backtest(symbol, test_frame, strategy_id, data_source)
        fold_scores.append(
            FoldScore(
                train_return_pct=train_result.return_pct,
                train_max_drawdown=train_result.max_drawdown,
                train_sharpe=train_result.sharpe,
                train_trade_count=train_result.trade_count,
                test_return_pct=test_result.return_pct,
                test_max_drawdown=test_result.max_drawdown,
                test_sharpe=test_result.sharpe,
                test_trade_count=test_result.trade_count,
                test_score=score_result(test_result),
            )
        )
    if not fold_scores:
        return SymbolStrategyScore(symbol, strategy_id, StrategyManager.available_strategy_names()[strategy_id], timeframe, 0, 0, 0, 0, 0, 0, -999)
    positive_folds = sum(1 for item in fold_scores if item.test_return_pct > 0 and item.test_trade_count >= 3)
    total_trades = sum(item.test_trade_count for item in fold_scores)
    stable_fold_ratio = positive_folds / len(fold_scores)
    avg_test_return = mean(item.test_return_pct for item in fold_scores)
    avg_test_drawdown = mean(item.test_max_drawdown for item in fold_scores)
    avg_test_sharpe = mean(item.test_sharpe for item in fold_scores)
    selected_score = mean(item.test_score for item in fold_scores) + stable_fold_ratio * 3.0
    if total_trades < max(3, len(fold_scores) * 2):
        selected_score -= 8.0
    return SymbolStrategyScore(
        symbol=symbol,
        strategy_id=strategy_id,
        strategy_name=StrategyManager.available_strategy_names()[strategy_id],
        timeframe=timeframe,
        folds=len(fold_scores),
        avg_test_return_pct=avg_test_return,
        avg_test_drawdown=avg_test_drawdown,
        avg_test_sharpe=avg_test_sharpe,
        total_test_trades=total_trades,
        stable_fold_ratio=stable_fold_ratio,
        selected_score=selected_score,
    )


def optimize_by_symbol(
    offline: bool = False,
    limit: int = 800,
    train_size: int = 360,
    test_size: int = 120,
    step_size: int = 120,
) -> tuple[dict[str, SymbolStrategyScore], list[SymbolStrategyScore], dict[str, str]]:
    provider = MarketDataProvider(use_exchange=not offline, fallback_to_synthetic=offline)
    all_scores: list[SymbolStrategyScore] = []
    data_sources: dict[str, str] = {}
    for item in enabled_symbols():
        symbol = item["symbol"]
        for timeframe in TIMEFRAMES:
            frame = fetch_symbol_frame(provider, symbol, timeframe, limit)
            source = provider.last_source_by_symbol.get(symbol, "unknown")
            data_sources[f"{symbol}:{timeframe}"] = source
            for strategy_id in StrategyManager.candidate_ids():
                all_scores.append(
                    evaluate_candidate(
                        symbol=symbol,
                        strategy_id=strategy_id,
                        timeframe=timeframe,
                        frame=frame,
                        data_source=source,
                        train_size=train_size,
                        test_size=test_size,
                        step_size=step_size,
                    )
                )
    winners: dict[str, SymbolStrategyScore] = {}
    for item in enabled_symbols():
        symbol = item["symbol"]
        symbol_scores = [score for score in all_scores if score.symbol == symbol]
        symbol_scores.sort(key=lambda score: score.selected_score, reverse=True)
        winners[symbol] = symbol_scores[0]

    payload = {
        "strategy_id": "per_symbol_optimized",
        "strategy_name": "Per-symbol Walk Forward Optimized",
        "source": "strategy_optimizer",
        "optimized_at": datetime.now(timezone.utc).isoformat(),
        "method": (
            "per-symbol multi-timeframe walk-forward; "
            "score = avg(test_return + 0.4*test_sharpe - 2*drawdown_pct - low_trade_penalty) + stable_fold_bonus"
        ),
        "history_limit": limit,
        "timeframes": TIMEFRAMES,
        "walk_forward": {
            "train_size": train_size,
            "test_size": test_size,
            "step_size": step_size,
        },
        "data_sources": data_sources,
        "per_symbol": {
            symbol: {
                "strategy_id": winner.strategy_id,
                "strategy_name": winner.strategy_name,
                "timeframe": winner.timeframe,
                "avg_test_return_pct": winner.avg_test_return_pct,
                "avg_test_drawdown": winner.avg_test_drawdown,
                "avg_test_sharpe": winner.avg_test_sharpe,
                "total_test_trades": winner.total_test_trades,
                "stable_fold_ratio": winner.stable_fold_ratio,
                "selected_score": winner.selected_score,
            }
            for symbol, winner in winners.items()
        },
        "ranking": [asdict(score) for score in sorted(all_scores, key=lambda score: (score.symbol, -score.selected_score))],
    }
    save_selected_strategy(payload)
    return winners, all_scores, data_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize best strategy per symbol with walk-forward backtests")
    parser.add_argument("--offline", action="store_true", help="use synthetic data instead of exchange data")
    parser.add_argument("--limit", type=int, default=800, help="number of candles per symbol/timeframe")
    parser.add_argument("--train-size", type=int, default=360, help="walk-forward train candles")
    parser.add_argument("--test-size", type=int, default=120, help="walk-forward test candles")
    parser.add_argument("--step-size", type=int, default=120, help="walk-forward step candles")
    args = parser.parse_args()
    winners, scores, data_sources = optimize_by_symbol(args.offline, args.limit, args.train_size, args.test_size, args.step_size)
    print("per-symbol strategy optimization")
    for symbol in sorted(winners):
        winner = winners[symbol]
        print(
            f"selected {symbol}: strategy={winner.strategy_id} timeframe={winner.timeframe} "
            f"avg_test_return={winner.avg_test_return_pct:.2f}% avg_test_dd={winner.avg_test_drawdown:.2%} "
            f"avg_test_sharpe={winner.avg_test_sharpe:.2f} trades={winner.total_test_trades} "
            f"stable_folds={winner.stable_fold_ratio:.0%} score={winner.selected_score:.2f}"
        )
        top = [score for score in sorted(scores, key=lambda item: item.selected_score, reverse=True) if score.symbol == symbol][:5]
        for rank, score in enumerate(top, start=1):
            print(
                f"  {rank}. {score.strategy_id}/{score.timeframe} return={score.avg_test_return_pct:.2f}% "
                f"dd={score.avg_test_drawdown:.2%} sharpe={score.avg_test_sharpe:.2f} "
                f"trades={score.total_test_trades} stable={score.stable_fold_ratio:.0%} score={score.selected_score:.2f}"
            )
    print("data_source=" + ",".join(f"{key}={source}" for key, source in sorted(data_sources.items())))


if __name__ == "__main__":
    main()
