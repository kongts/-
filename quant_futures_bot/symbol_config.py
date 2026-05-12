SYMBOLS = [
    {
        "symbol": "BTC/USDT:USDT",
        "enabled": True,
        "leverage": 2,
        "max_margin_ratio": 0.08,
    },
    {
        "symbol": "ETH/USDT:USDT",
        "enabled": True,
        "leverage": 2,
        "max_margin_ratio": 0.06,
    },
    {
        "symbol": "SOL/USDT:USDT",
        "enabled": True,
        "leverage": 2,
        "max_margin_ratio": 0.04,
    },
]


def enabled_symbols() -> list[dict]:
    return [item for item in SYMBOLS if item.get("enabled", False)]


def get_symbol_config(symbol: str) -> dict:
    for item in SYMBOLS:
        if item["symbol"] == symbol:
            return item
    raise KeyError(f"Unknown symbol: {symbol}")

