from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone

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
    pnl_summary = realized_pnl_summary(exchange)
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
    print_realized_pnl_summary(pnl_summary)
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


def print_realized_pnl_summary(summary: dict) -> None:
    print("Realized PnL")
    print("-" * 84)
    print(f"{'Period':<10}{'Realized':>14}{'Fee':>14}{'Funding':>14}{'Other':>14}{'Net':>14}")
    print("-" * 84)
    for key, label in (("day", "Today"), ("week", "7 Days"), ("month", "30 Days")):
        item = summary.get(key, {})
        print(
            f"{label:<10}"
            f"{item.get('realized_pnl', 0.0):>14.2f}"
            f"{item.get('commission', 0.0):>14.2f}"
            f"{item.get('funding_fee', 0.0):>14.2f}"
            f"{item.get('other', 0.0):>14.2f}"
            f"{item.get('net', 0.0):>14.2f}"
        )
    if summary.get("error"):
        print(f"Income history unavailable: {summary['error']}")


def realized_pnl_summary(exchange) -> dict:
    now = datetime.now(timezone.utc)
    periods = {
        "day": now - timedelta(days=1),
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
    }
    summary = {key: empty_income_bucket() for key in periods}
    try:
        incomes = fetch_income(exchange, int(periods["month"].timestamp() * 1000))
    except Exception as exc:
        summary["error"] = str(exc)
        return summary
    for item in incomes:
        timestamp = income_timestamp(item)
        if timestamp is None:
            continue
        amount = first_float(item.get("income"), item.get("amount"), 0.0)
        income_type = str(item.get("incomeType") or item.get("type") or "").upper()
        for key, start in periods.items():
            if timestamp >= start:
                add_income(summary[key], income_type, amount)
    for item in summary.values():
        item["net"] = item["realized_pnl"] + item["commission"] + item["funding_fee"] + item["other"]
    return summary


def fetch_income(exchange, start_time_ms: int) -> list[dict]:
    if hasattr(exchange, "fapiPrivateGetIncome"):
        rows = exchange.fapiPrivateGetIncome({"startTime": start_time_ms, "limit": 1000})
        return list(rows or [])
    if hasattr(exchange, "fetch_income"):
        rows = exchange.fetch_income(None, start_time_ms, 1000)
        return list(rows or [])
    raise RuntimeError("exchange does not expose futures income history")


def income_timestamp(item: dict) -> datetime | None:
    raw_time = item.get("time") or item.get("timestamp")
    if raw_time is None:
        return None
    try:
        return datetime.fromtimestamp(float(raw_time) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def empty_income_bucket() -> dict:
    return {"realized_pnl": 0.0, "commission": 0.0, "funding_fee": 0.0, "other": 0.0, "net": 0.0}


def add_income(bucket: dict, income_type: str, amount: float) -> None:
    if income_type == "REALIZED_PNL":
        bucket["realized_pnl"] += amount
    elif income_type == "COMMISSION":
        bucket["commission"] += amount
    elif income_type == "FUNDING_FEE":
        bucket["funding_fee"] += amount
    else:
        bucket["other"] += amount


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
