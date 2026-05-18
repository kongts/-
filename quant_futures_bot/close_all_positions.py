from __future__ import annotations

import argparse
from dataclasses import dataclass

from .execution import BinanceTestnetExecution


@dataclass
class ActivePosition:
    symbol: str
    side: str
    qty: float


def main() -> None:
    parser = argparse.ArgumentParser(description="Cancel all open orders and close all Binance Futures Demo/Testnet positions")
    parser.add_argument("--confirm", default="", help="set to YES to submit cancel/close orders")
    parser.add_argument("--skip-cancel", action="store_true", help="do not cancel open orders before closing positions")
    args = parser.parse_args()

    dry_run = args.confirm != "YES"
    execution = BinanceTestnetExecution()
    exchange = execution.exchange
    exchange.options["warnOnFetchOpenOrdersWithoutSymbol"] = False

    if dry_run:
        print("DRY RUN: no orders will be cancelled or submitted. Add --confirm YES to execute.")

    if not args.skip_cancel:
        cancel_open_orders(exchange, dry_run=dry_run)
    close_positions(exchange, dry_run=dry_run)
    print("Done.")


def cancel_open_orders(exchange, dry_run: bool) -> None:
    orders = fetch_open_orders(exchange)
    print(f"Open orders: {len(orders)}")
    for order in orders:
        symbol = str(order.get("symbol") or "")
        order_id = str(order.get("id") or order.get("orderId") or "")
        if not symbol or not order_id:
            continue
        if dry_run:
            print(f"would_cancel symbol={symbol} order={order_id}")
            continue
        try:
            exchange.cancel_order(order_id, symbol)
            print(f"cancelled symbol={symbol} order={order_id}")
        except Exception as exc:
            print(f"cancel_failed symbol={symbol} order={order_id} error={exc}")


def close_positions(exchange, dry_run: bool) -> None:
    positions = active_positions(exchange)
    print(f"Active positions: {len(positions)}")
    for position in positions:
        order_side = "sell" if position.side == "LONG" else "buy"
        amount = float(exchange.amount_to_precision(position.symbol, position.qty))
        if amount <= 0:
            continue
        if dry_run:
            print(
                f"would_close symbol={position.symbol} position_side={position.side} "
                f"order_side={order_side} amount={amount}"
            )
            continue
        try:
            order = exchange.create_order(
                symbol=position.symbol,
                type="market",
                side=order_side,
                amount=amount,
                price=None,
                params={"reduceOnly": True},
            )
            print(
                f"closed symbol={position.symbol} position_side={position.side} "
                f"order_side={order_side} amount={amount} order={order.get('id') or order.get('orderId') or '-'}"
            )
        except Exception as exc:
            print(
                f"close_failed symbol={position.symbol} position_side={position.side} "
                f"order_side={order_side} amount={amount} error={exc}"
            )


def fetch_open_orders(exchange) -> list[dict]:
    try:
        return list(exchange.fetch_open_orders())
    except Exception as exc:
        print(f"fetch_open_orders_all_failed error={exc}")
        return []


def active_positions(exchange) -> list[ActivePosition]:
    positions: list[ActivePosition] = []
    for item in exchange.fetch_positions():
        info = item.get("info", {})
        symbol = str(item.get("symbol") or info.get("symbol") or "")
        raw_amt = first_float(info.get("positionAmt"), item.get("contracts"), 0.0)
        raw_side = str(item.get("side") or "").lower()
        qty = abs(raw_amt)
        if not symbol or qty <= 0:
            continue
        side = "LONG" if raw_amt > 0 or raw_side == "long" else "SHORT"
        positions.append(ActivePosition(symbol=symbol, side=side, qty=qty))
    return positions


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
