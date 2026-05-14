from __future__ import annotations

from dataclasses import dataclass

from .altcoin_top_volume_backtest import first_float


MACRO_ASSET_CLASS_BY_BASE = {
    "PAXG": "gold",
    "XAU": "gold",
    "GOLD": "gold",
    "XAG": "silver",
    "SILVER": "silver",
    "NVDA": "us_equity",
    "TSLA": "us_equity",
    "MSTR": "us_equity",
    "AAPL": "us_equity",
    "AMZN": "us_equity",
    "GOOGL": "us_equity",
    "META": "us_equity",
    "MSFT": "us_equity",
    "AMD": "us_equity",
    "INTC": "us_equity",
    "COIN": "us_equity",
    "SPX": "us_index",
    "SPY": "us_index",
    "NDX": "us_index",
    "QQQ": "us_index",
    "NASDAQ": "us_index",
    "EWY": "us_etf",
    "CL": "commodity",
    "OIL": "commodity",
    "NATGAS": "commodity",
}


@dataclass
class MacroMarket:
    symbol: str
    base: str
    asset_class: str
    quote_volume: float


def fetch_supported_macro_markets(limit: int = 50, fetch_timeout_ms: int = 15000) -> list[MacroMarket]:
    import ccxt

    exchange = ccxt.binanceusdm({"enableRateLimit": True, "timeout": fetch_timeout_ms, "options": {"defaultType": "future"}})
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    rows: list[MacroMarket] = []
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if not market.get("swap"):
            continue
        if market.get("quote") != "USDT":
            continue
        base = str(market.get("base") or "").upper()
        asset_class = MACRO_ASSET_CLASS_BY_BASE.get(base)
        if asset_class is None:
            continue
        ticker = tickers.get(symbol, {})
        quote_volume = first_float(
            ticker.get("quoteVolume"),
            ticker.get("info", {}).get("quoteVolume"),
            ticker.get("info", {}).get("volume"),
            0.0,
        )
        rows.append(MacroMarket(symbol=symbol, base=base, asset_class=asset_class, quote_volume=quote_volume))
    rows.sort(key=lambda item: item.quote_volume, reverse=True)
    return rows[:limit]

