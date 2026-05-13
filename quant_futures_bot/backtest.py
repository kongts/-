from __future__ import annotations

import argparse
import math
from dataclasses import dataclass

import pandas as pd

from .data import MarketDataProvider
from .events import OrderStatus, SignalEvent, SignalType
from .execution import PaperExecution
from .indicators import add_indicators
from .market_state import detect_market_state
from .order_manager import OrderManager
from .pause_manager import PauseManager
from .portfolio import Portfolio
from .risk_engine import RiskEngine
from .strategy_manager import StrategyManager
from .symbol_config import enabled_symbols, get_symbol_config


@dataclass
class BacktestResult:
    strategy_id: str
    strategy_name: str
    final_equity: float
    return_pct: float
    max_drawdown: float
    sharpe: float
    win_rate: float
    long_win_rate: float
    short_win_rate: float
    trade_count: int
    profit_factor: float
    max_consecutive_losses: int
    pause_count: int
    data_sources: dict[str, str]
    equity_curve: list[float]


class Backtester:
    def __init__(
        self,
        offline: bool = False,
        strategy_id: str | None = None,
        frames: dict[str, pd.DataFrame] | None = None,
        data_sources: dict[str, str] | None = None,
        symbol_configs: dict[str, dict] | None = None,
        stop_loss_pct: float = 0.0,
        take_profit_pct: float = 0.0,
    ) -> None:
        self.data_provider = MarketDataProvider(use_exchange=not offline, fallback_to_synthetic=offline)
        self.strategy_manager = StrategyManager(strategy_id=strategy_id, use_saved_selection=strategy_id is None)
        self.frames = frames
        self.data_sources = data_sources or {}
        self.symbol_configs = symbol_configs or {}
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.order_manager = OrderManager()
        self.execution = PaperExecution()
        self.portfolio = Portfolio()
        self.pause_manager = PauseManager()
        self.risk_engine = RiskEngine(self.portfolio, self.pause_manager, symbol_configs=self.symbol_configs)
        self.trade_sides: list[str] = []
        self.trade_pnls: list[float] = []
        self.pause_count = 0
        self.equity_curve: list[float] = []

    def run(self) -> BacktestResult:
        frames = self.frames or self.load_frames()
        min_len = min(len(df) for df in frames.values())
        for idx in range(40, min_len):
            latest_rows = {}
            for symbol, df in frames.items():
                window = df.iloc[: idx + 1].copy()
                price = float(window.iloc[-1]["close"])
                self.portfolio.update_market_price(symbol, price)
                latest_rows[symbol] = window.iloc[-1].to_dict()
                exit_signal = self._stop_or_take_profit_signal(symbol, price)
                if exit_signal is not None:
                    self._execute_signal(exit_signal, latest_rows[symbol])
                    continue
                market_state = detect_market_state(window)
                side = self.portfolio.position_side(symbol)
                for signal in self.strategy_manager.generate(symbol, window, market_state, side):
                    self._execute_signal(signal, latest_rows[symbol])
            before_status = self.pause_manager.status
            self.pause_manager.check(self.portfolio, latest_rows)
            if before_status == "RUNNING" and self.pause_manager.status == "PAUSED":
                self.pause_count += 1
            self.equity_curve.append(self.portfolio.equity)
        return self._result()

    def load_frames(self, limit: int = 500) -> dict[str, pd.DataFrame]:
        frames = {}
        for item in enabled_symbols():
            symbol = item["symbol"]
            frames[symbol] = add_indicators(self.data_provider.fetch_ohlcv(symbol, limit=limit))
        self.data_sources = dict(self.data_provider.last_source_by_symbol)
        return frames

    def _symbol_config(self, symbol: str) -> dict:
        return self.symbol_configs.get(symbol) or get_symbol_config(symbol)

    def _execute_signal(self, signal: SignalEvent, latest_row: dict) -> None:
        risk = self.risk_engine.check_signal(signal, latest_row)
        if not risk.approved:
            return
        qty = self.risk_engine.order_quantity(signal)
        if qty <= 0:
            return
        order = self.order_manager.create_order(signal, qty)
        submitted = self.order_manager.update_status(order.order_id, OrderStatus.SUBMITTED)
        fill = self.execution.execute(submitted)
        pnl = self.portfolio.apply_fill(fill, float(self._symbol_config(signal.symbol)["leverage"]))
        if fill.position_action.value.startswith("CLOSE"):
            self.trade_sides.append("LONG" if "LONG" in fill.position_action.value else "SHORT")
            self.trade_pnls.append(pnl)
        self.order_manager.update_status(order.order_id, OrderStatus.FILLED)

    def _stop_or_take_profit_signal(self, symbol: str, price: float) -> SignalEvent | None:
        pos = self.portfolio.get_position(symbol)
        if not pos.is_open() or pos.entry_price <= 0:
            return None
        if pos.position_side == "LONG":
            change = price / pos.entry_price - 1
            close_type = SignalType.CLOSE_LONG
        else:
            change = pos.entry_price / price - 1
            close_type = SignalType.CLOSE_SHORT
        if self.stop_loss_pct > 0 and change <= -self.stop_loss_pct:
            return SignalEvent(symbol, close_type, "Stop Loss", price)
        if self.take_profit_pct > 0 and change >= self.take_profit_pct:
            return SignalEvent(symbol, close_type, "Take Profit", price)
        return None

    def _result(self) -> BacktestResult:
        pnls = self.trade_pnls
        wins = [pnl for pnl in pnls if pnl > 0]
        losses = [pnl for pnl in pnls if pnl < 0]
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        sharpe = 0.0 if returns.std() == 0 or returns.empty else float(returns.mean() / returns.std() * math.sqrt(365 * 24))
        profit_factor = float(sum(wins) / abs(sum(losses))) if losses else float("inf") if wins else 0.0
        long_pnls = [p for p, side in zip(pnls, self.trade_sides) if side == "LONG"]
        short_pnls = [p for p, side in zip(pnls, self.trade_sides) if side == "SHORT"]
        return BacktestResult(
            strategy_id=self.strategy_manager.strategy_id,
            strategy_name=self.strategy_manager.strategy_name,
            final_equity=self.portfolio.equity,
            return_pct=(self.portfolio.equity / 10_000.0 - 1) * 100,
            max_drawdown=self.portfolio.max_drawdown,
            sharpe=sharpe,
            win_rate=self._win_rate(pnls),
            long_win_rate=self._win_rate(long_pnls),
            short_win_rate=self._win_rate(short_pnls),
            trade_count=len(pnls),
            profit_factor=profit_factor,
            max_consecutive_losses=self._max_consecutive_losses(pnls),
            pause_count=self.pause_count,
            data_sources=self.data_sources or dict(self.data_provider.last_source_by_symbol),
            equity_curve=self.equity_curve,
        )

    @staticmethod
    def _win_rate(pnls: list[float]) -> float:
        if not pnls:
            return 0.0
        return sum(1 for pnl in pnls if pnl > 0) / len(pnls)

    @staticmethod
    def _max_consecutive_losses(pnls: list[float]) -> int:
        max_losses = current = 0
        for pnl in pnls:
            if pnl < 0:
                current += 1
                max_losses = max(max_losses, current)
            else:
                current = 0
        return max_losses


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paper trading backtest")
    parser.add_argument("--offline", action="store_true", help="use synthetic data instead of exchange historical data")
    parser.add_argument("--strategy", default=None, help="strategy id to backtest")
    args = parser.parse_args()
    result = Backtester(offline=args.offline, strategy_id=args.strategy).run()
    print(f"strategy={result.strategy_id} ({result.strategy_name})")
    print(f"final_equity={result.final_equity:.2f}")
    print(f"return_pct={result.return_pct:.2f}%")
    print(f"max_drawdown={result.max_drawdown:.2%}")
    print(f"sharpe={result.sharpe:.2f}")
    print(f"win_rate={result.win_rate:.2%}")
    print(f"long_win_rate={result.long_win_rate:.2%}")
    print(f"short_win_rate={result.short_win_rate:.2%}")
    print(f"trade_count={result.trade_count}")
    print(f"profit_factor={result.profit_factor:.2f}")
    print(f"max_consecutive_losses={result.max_consecutive_losses}")
    print(f"pause_count={result.pause_count}")
    print("data_source=" + ",".join(f"{symbol}={source}" for symbol, source in sorted(result.data_sources.items())))


if __name__ == "__main__":
    main()
