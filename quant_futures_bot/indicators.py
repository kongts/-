import pandas as pd

MA_SHORT = 10
MA_LONG = 30
RSI_PERIOD = 14
VOLATILITY_PERIOD = 20


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data["ma_short"] = data["close"].rolling(MA_SHORT).mean()
    data["ma_long"] = data["close"].rolling(MA_LONG).mean()
    delta = data["close"].diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs = gain / loss.replace(0, pd.NA)
    data["rsi"] = 100 - (100 / (1 + rs))
    data["ret"] = data["close"].pct_change()
    data["volatility"] = data["ret"].rolling(VOLATILITY_PERIOD).std()
    data["volatility_median"] = data["volatility"].rolling(VOLATILITY_PERIOD).median()
    data["volatility_mean"] = data["volatility"].rolling(VOLATILITY_PERIOD).mean()
    data["trend_strength"] = (data["ma_short"] - data["ma_long"]).abs() / data["close"]
    return data

