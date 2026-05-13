from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from . import config


class Database:
    def __init__(self, path: Path = config.DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        statements = [
            """CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT, timestamp TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL,
                data_source TEXT DEFAULT 'unknown'
            )""",
            """CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, symbol TEXT, signal_type TEXT, strategy_name TEXT, price REAL
            )""",
            """CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY, timestamp TEXT, symbol TEXT, side TEXT,
                position_action TEXT, qty REAL, price REAL, reduce_only INTEGER, status TEXT,
                exchange_order_id TEXT DEFAULT ''
            )""",
            """CREATE TABLE IF NOT EXISTS fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT, timestamp TEXT, symbol TEXT, fill_price REAL,
                qty REAL, fee REAL, slippage REAL, position_action TEXT,
                exchange_order_id TEXT DEFAULT ''
            )""",
            """CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY, payload TEXT, updated_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, symbol TEXT, pnl REAL
            )""",
            """CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, equity REAL,
                cash REAL, used_margin REAL, unrealized_pnl REAL, max_drawdown REAL
            )""",
            """CREATE TABLE IF NOT EXISTS pause_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, status TEXT, reason TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, source TEXT, message TEXT
            )""",
        ]
        for statement in statements:
            self.conn.execute(statement)
        self._ensure_column("market_data", "data_source", "TEXT DEFAULT 'unknown'")
        self._ensure_column("orders", "exchange_order_id", "TEXT DEFAULT ''")
        self._ensure_column("fills", "exchange_order_id", "TEXT DEFAULT ''")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def save_market_data(self, symbol: str, df: pd.DataFrame, data_source: str | None = None) -> None:
        rows = df.tail(1)
        for _, row in rows.iterrows():
            source = data_source or str(row.get("data_source", "unknown"))
            self.conn.execute(
                "INSERT INTO market_data(symbol,timestamp,open,high,low,close,volume,data_source) VALUES(?,?,?,?,?,?,?,?)",
                (
                    symbol,
                    str(row["timestamp"]),
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    float(row["volume"]),
                    source,
                ),
            )
        self.conn.commit()

    def save_signal(self, signal) -> None:
        self.conn.execute(
            "INSERT INTO signals(timestamp,symbol,signal_type,strategy_name,price) VALUES(?,?,?,?,?)",
            (signal.timestamp.isoformat(), signal.symbol, signal.signal_type.value, signal.strategy_name, signal.price),
        )
        self.conn.commit()

    def save_order(self, order) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO orders(order_id,timestamp,symbol,side,position_action,qty,price,reduce_only,status,exchange_order_id)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                order.order_id,
                order.timestamp.isoformat(),
                order.symbol,
                order.side,
                order.position_action.value,
                order.qty,
                order.price,
                int(order.reduce_only),
                order.status.value,
                getattr(order, "exchange_order_id", ""),
            ),
        )
        self.conn.commit()

    def save_fill(self, fill) -> None:
        self.conn.execute(
            "INSERT INTO fills(order_id,timestamp,symbol,fill_price,qty,fee,slippage,position_action,exchange_order_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                fill.order_id,
                fill.timestamp.isoformat(),
                fill.symbol,
                fill.fill_price,
                fill.qty,
                fill.fee,
                fill.slippage,
                fill.position_action.value,
                getattr(fill, "exchange_order_id", ""),
            ),
        )
        if getattr(fill, "exchange_order_id", ""):
            self.conn.execute(
                "UPDATE orders SET exchange_order_id = ? WHERE order_id = ?",
                (fill.exchange_order_id, fill.order_id),
            )
        self.conn.commit()

    def save_portfolio(self, portfolio) -> None:
        now = pd.Timestamp.utcnow().isoformat()
        for symbol, position in portfolio.positions.items():
            payload = json.dumps(asdict(position), ensure_ascii=False)
            self.conn.execute(
                "INSERT OR REPLACE INTO positions(symbol,payload,updated_at) VALUES(?,?,?)",
                (symbol, payload, now),
            )
        self.conn.execute(
            "INSERT INTO equity_curve(timestamp,equity,cash,used_margin,unrealized_pnl,max_drawdown) VALUES(?,?,?,?,?,?)",
            (now, portfolio.equity, portfolio.cash, portfolio.used_margin, portfolio.unrealized_pnl, portfolio.max_drawdown),
        )
        self.conn.commit()

    def save_trade(self, timestamp: str, symbol: str, pnl: float) -> None:
        self.conn.execute("INSERT INTO trades(timestamp,symbol,pnl) VALUES(?,?,?)", (timestamp, symbol, pnl))
        self.conn.commit()

    def save_pause(self, pause_event) -> None:
        self.conn.execute(
            "INSERT INTO pause_logs(timestamp,status,reason) VALUES(?,?,?)",
            (pause_event.timestamp.isoformat(), pause_event.status, pause_event.reason),
        )
        self.conn.commit()

    def save_error(self, error_event) -> None:
        self.conn.execute(
            "INSERT INTO error_logs(timestamp,source,message) VALUES(?,?,?)",
            (error_event.timestamp.isoformat(), error_event.source, error_event.message),
        )
        self.conn.commit()

    @staticmethod
    def encode(obj: Any) -> str:
        if is_dataclass(obj):
            return json.dumps(asdict(obj), default=str, ensure_ascii=False)
        return json.dumps(obj, default=str, ensure_ascii=False)
