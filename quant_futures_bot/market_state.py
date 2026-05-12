import pandas as pd


def detect_market_state(df: pd.DataFrame) -> str:
    latest = df.dropna().iloc[-1] if not df.dropna().empty else None
    if latest is None:
        return "range"
    if latest["volatility"] > latest["volatility_median"] and latest["trend_strength"] > 0.003:
        return "trend"
    return "range"

