from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from . import config


class MarketDataProvider:
    def __init__(self, use_exchange: bool = True, fallback_to_synthetic: bool = True) -> None:
        self.use_exchange = use_exchange
        self.fallback_to_synthetic = fallback_to_synthetic
        self.exchange = None
        self.last_source_by_symbol: dict[str, str] = {}
        if use_exchange:
            try:
                import ccxt

                self.exchange = ccxt.binance({"options": {"defaultType": "future"}, "enableRateLimit": True})
            except Exception as exc:
                if not fallback_to_synthetic:
                    raise RuntimeError(f"Failed to initialize ccxt Binance exchange: {exc}") from exc
                self.exchange = None

    def fetch_ohlcv(self, symbol: str, timeframe: str = config.TIMEFRAME, limit: int = config.KLINE_LIMIT) -> pd.DataFrame:
        last_error: Exception | None = None
        if self.exchange is not None:
            try:
                rows = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                df = self._to_frame(rows)
                df["data_source"] = "exchange"
                self.last_source_by_symbol[symbol] = "exchange"
                return df
            except Exception as exc:
                last_error = exc
        if self.use_exchange and not self.fallback_to_synthetic:
            detail = f": {last_error}" if last_error else ""
            raise RuntimeError(f"Failed to fetch exchange OHLCV for {symbol}{detail}")
        df = self.synthetic_ohlcv(symbol, limit, timeframe)
        df["data_source"] = "synthetic"
        self.last_source_by_symbol[symbol] = "synthetic"
        return df

    @staticmethod
    def _to_frame(rows: list[list[float]]) -> pd.DataFrame:
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    @staticmethod
    def synthetic_ohlcv(symbol: str, limit: int = config.KLINE_LIMIT, timeframe: str = config.TIMEFRAME) -> pd.DataFrame:
        seed_by_symbol = {
            "BTC/USDT:USDT": 1_001,
            "ETH/USDT:USDT": 1_002,
            "SOL/USDT:USDT": 1_003,
        }
        timeframe_offset = {"4h": 240, "6h": 360}.get(timeframe, 0)
        seed = seed_by_symbol.get(symbol, 9_999) + timeframe_offset
        rng = np.random.default_rng(seed)
        base = {"BTC/USDT:USDT": 65_000, "ETH/USDT:USDT": 3_200, "SOL/USDT:USDT": 150}.get(symbol, 100)
        returns = rng.normal(0.0002, 0.015, limit)
        close = base * np.cumprod(1 + returns)
        open_ = np.r_[close[0], close[:-1]]
        spread = np.abs(rng.normal(0.002, 0.004, limit))
        high = np.maximum(open_, close) * (1 + spread)
        low = np.minimum(open_, close) * (1 - spread)
        volume = rng.uniform(100, 10_000, limit)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        timestamps = [now - timedelta(hours=limit - idx - 1) for idx in range(limit)]
        return pd.DataFrame(
            {
                "timestamp": timestamps,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
