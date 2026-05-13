from __future__ import annotations

import argparse
import time

from . import config
from .symbol_config import enabled_symbols
from .trading_system import TradingSystem


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance USDT-M Futures paper trading system")
    parser.add_argument("--cycles", type=int, default=config.MAX_CYCLES, help="number of cycles to run")
    parser.add_argument("--sleep", type=int, default=config.LOOP_SLEEP_SECONDS, help="seconds between cycles")
    parser.add_argument("--offline", action="store_true", help="use synthetic market data")
    args = parser.parse_args()

    system = TradingSystem(use_exchange=not args.offline)
    for cycle in range(args.cycles):
        system.run_cycle()
        sources = ",".join(f"{symbol}={source}" for symbol, source in sorted(system.last_data_sources.items()))
        strategies = ",".join(
            f"{item['symbol']}={system.strategy_manager.strategy_for_symbol(item['symbol'])}/{system.strategy_manager.timeframe_for_symbol(item['symbol'])}"
            for item in enabled_symbols()
        )
        print(
            f"cycle={cycle + 1} equity={system.portfolio.equity:.2f} "
            f"used_margin={system.portfolio.used_margin:.2f} status={system.pause_manager.status} "
            f"execution_mode={config.EXECUTION_MODE} orders_created={system.cycle_orders_created} "
            f"fills_created={system.cycle_fills_created} "
            f"exchange_order_ids={','.join(system.cycle_exchange_order_ids) or '-'} "
            f"strategy={strategies or system.selected_strategy['strategy_id']} data_source={sources}"
        )
        if cycle < args.cycles - 1:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
