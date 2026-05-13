from __future__ import annotations

import argparse
import time
from datetime import datetime

from . import config
from .symbol_config import enabled_symbols
from .trading_system import TradingSystem


def format_prices(system: TradingSystem) -> str:
    parts = []
    for symbol, row in sorted(system.latest_rows.items()):
        close = row.get("close")
        if close is not None:
            parts.append(f"{symbol}={float(close):.4f}")
    return ",".join(parts) or "-"


def format_sources(system: TradingSystem) -> str:
    return ",".join(f"{symbol}={source}" for symbol, source in sorted(system.last_data_sources.items())) or "-"


def format_strategies(system: TradingSystem) -> str:
    return ",".join(
        f"{item['symbol']}={system.strategy_manager.strategy_for_symbol(item['symbol'])}/"
        f"{system.strategy_manager.timeframe_for_symbol(item['symbol'])}"
        for item in enabled_symbols()
    )


def print_cycle_summary(system: TradingSystem, cycle: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[{now}] cycle={cycle} equity={system.portfolio.equity:.2f} "
        f"used_margin={system.portfolio.used_margin:.2f} status={system.pause_manager.status} "
        f"execution_mode={config.EXECUTION_MODE} signals={system.cycle_signals_created} "
        f"rejected={system.cycle_signals_rejected} orders_created={system.cycle_orders_created} "
        f"fills_created={system.cycle_fills_created} "
        f"exchange_order_ids={','.join(system.cycle_exchange_order_ids) or '-'} "
        f"exchange_open_orders={system.exchange_open_order_count} "
        f"exchange_positions={system.exchange_positions_summary} "
        f"prices={format_prices(system)} strategy={format_strategies(system)} "
        f"data_source={format_sources(system)}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuously monitor market signals and execute current strategy")
    parser.add_argument("--offline", action="store_true", help="use synthetic market data")
    parser.add_argument("--poll-seconds", type=int, default=60, help="seconds between market checks")
    parser.add_argument("--max-cycles", type=int, default=0, help="stop after N cycles; 0 means run forever")
    args = parser.parse_args()

    poll_seconds = max(10, args.poll_seconds)
    system = TradingSystem(use_exchange=not args.offline)
    cycle = 0
    print(
        f"live monitor started execution_mode={config.EXECUTION_MODE} "
        f"poll_seconds={poll_seconds} max_cycles={args.max_cycles or 'forever'}",
        flush=True,
    )
    while True:
        cycle += 1
        try:
            system.run_cycle()
            print_cycle_summary(system, cycle)
        except KeyboardInterrupt:
            print("live monitor stopped by user", flush=True)
            break
        except Exception as exc:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] monitor_error={exc}", flush=True)
        if args.max_cycles and cycle >= args.max_cycles:
            break
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
