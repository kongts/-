from __future__ import annotations

import argparse
import time

from . import config
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
        print(
            f"cycle={cycle + 1} equity={system.portfolio.equity:.2f} "
            f"used_margin={system.portfolio.used_margin:.2f} status={system.pause_manager.status}"
        )
        if cycle < args.cycles - 1:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()

