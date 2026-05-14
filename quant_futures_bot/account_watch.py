from __future__ import annotations

import argparse
import time
from datetime import datetime

from .execution import BinanceTestnetExecution


def main() -> None:
    parser = argparse.ArgumentParser(description="Show Binance Futures Demo/Testnet account positions and PnL")
    parser.add_argument("--interval-seconds", type=float, default=5.0, help="refresh interval")
    parser.add_argument("--watch", action="store_true", help="refresh continuously")
    args = parser.parse_args()

    execution = BinanceTestnetExecution()
    while True:
        print_snapshot(execution.exchange)
        if not args.watch:
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
    margin_ratio = used_margin / equity * 100 if equity > 0 else 0.0

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nAccount Snapshot  {now}")
    print("=" * 72)
    print(f"{'Equity':<16}{equity:>14.2f} USDT")
    print(f"{'Wallet':<16}{wallet:>14.2f} USDT")
    print(f"{'Available':<16}{available:>14.2f} USDT")
    print(f"{'Used Margin':<16}{used_margin:>14.2f} USDT  ({margin_ratio:.2f}%)")
    print(f"{'Unrealized PnL':<16}{unrealized:>14.2f} USDT")
    print(f"{'Positions':<16}{len(positions):>14}")
    print(f"{'Open Orders':<16}{open_orders:>14}")
    print()
    print("Positions")
    print("-" * 112)
    if not positions:
        print("No open positions.", flush=True)
        return
    print(
        f"{'Symbol':<20}{'Side':<7}{'Qty':>14}{'Entry':>14}{'Mark':>14}"
        f"{'Notional':>14}{'Margin':>12}{'PnL':>12}{'PnL%':>9}"
    )
    print("-" * 112)
    for item in sorted(positions, key=lambda row: row["symbol"]):
        pnl_pct = item["unrealized_pnl"] / item["notional_value"] * 100 if item["notional_value"] else 0.0
        print(
            f"{item['symbol']:<20}{item['side']:<7}{item['qty']:>14.8f}"
            f"{item['entry_price']:>14.6f}{item['mark_price']:>14.6f}"
            f"{item['notional_value']:>14.2f}{item['margin_used']:>12.2f}"
            f"{item['unrealized_pnl']:>12.2f}{pnl_pct:>8.2f}%",
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
