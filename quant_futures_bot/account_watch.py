from __future__ import annotations

import argparse
import time
from datetime import datetime

from .execution import BinanceTestnetExecution


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch Binance Futures Demo/Testnet account positions and PnL")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="refresh interval")
    parser.add_argument("--once", action="store_true", help="print once and exit")
    args = parser.parse_args()

    execution = BinanceTestnetExecution()
    while True:
        print_snapshot(execution.exchange)
        if args.once:
            return
        time.sleep(max(1.0, args.interval_seconds))


def print_snapshot(exchange) -> None:
    balance = exchange.fetch_balance()
    positions = active_positions(exchange)
    open_orders = open_orders_count(exchange)
    info = balance.get("info", {})
    total = balance.get("total", {})
    free = balance.get("free", {})
    wallet = first_float(total.get("USDT"), info.get("totalWalletBalance"), 0.0)
    equity = first_float(info.get("totalMarginBalance"), total.get("USDT"), wallet)
    available = first_float(free.get("USDT"), info.get("availableBalance"), wallet)
    unrealized = sum(item["unrealized_pnl"] for item in positions)
    used_margin = max(equity - available, 0.0)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[{now}] equity={equity:.2f} wallet={wallet:.2f} available={available:.2f} "
        f"used_margin={used_margin:.2f} unrealized={unrealized:.2f} "
        f"positions={len(positions)} open_orders={open_orders}",
        flush=True,
    )
    if not positions:
        print("  positions=-", flush=True)
        return
    for item in sorted(positions, key=lambda row: row["symbol"]):
        pnl_pct = item["unrealized_pnl"] / item["notional_value"] * 100 if item["notional_value"] else 0.0
        print(
            "  "
            f"{item['symbol']} {item['side']} qty={item['qty']:.8f} "
            f"entry={item['entry_price']:.6f} mark={item['mark_price']:.6f} "
            f"notional={item['notional_value']:.2f} margin={item['margin_used']:.2f} "
            f"pnl={item['unrealized_pnl']:.2f} pnl_pct={pnl_pct:.2f}%",
            flush=True,
        )


def active_positions(exchange) -> list[dict]:
    positions: list[dict] = []
    for item in exchange.fetch_positions():
        info = item.get("info", {})
        raw_amt = first_float(info.get("positionAmt"), item.get("contracts"), 0.0)
        qty = abs(raw_amt)
        if qty <= 0:
            continue
        raw_side = str(item.get("side") or "").lower()
        side = "LONG" if raw_amt > 0 or raw_side == "long" else "SHORT"
        entry_price = first_float(item.get("entryPrice"), info.get("entryPrice"), 0.0)
        mark_price = first_float(item.get("markPrice"), info.get("markPrice"), entry_price)
        notional = abs(first_float(item.get("notional"), info.get("notional"), mark_price * qty))
        margin = abs(first_float(item.get("initialMargin"), info.get("positionInitialMargin"), 0.0))
        unrealized = first_float(item.get("unrealizedPnl"), info.get("unRealizedProfit"), 0.0)
        positions.append(
            {
                "symbol": item.get("symbol") or info.get("symbol") or "",
                "side": side,
                "qty": qty,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "notional_value": notional,
                "margin_used": margin,
                "unrealized_pnl": unrealized,
            }
        )
    return positions


def open_orders_count(exchange) -> int:
    try:
        return len(exchange.fetch_open_orders())
    except Exception:
        return -1


def first_float(*values) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


if __name__ == "__main__":
    main()
