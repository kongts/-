from __future__ import annotations

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
