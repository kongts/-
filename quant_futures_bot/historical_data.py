from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import DATA_DIR


DEFAULT_START = "2022-01-01"
DEFAULT_END = "2026-01-01"
DEFAULT_TIMEFRAMES = ["15m", "30m", "1h", "4h", "6h"]
DEFAULT_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
DEFAULT_ROOT = DATA_DIR / "historical_ohlcv" / "binance_usdt_futures"
EXCLUDED_ALTCOIN_BASES = {
    "BTC",
    "ETH",
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "XAU",
    "XAG",
    "CL",
    "NATGAS",
    "PAXG",
    "NVDA",
    "TSLA",
    "MSTR",
    "AMD",
    "INTC",
    "EWY",
}


@dataclass
class DownloadSummary:
    symbol: str
    timeframe: str
    path: str
    rows: int
    first_timestamp: str
    last_timestamp: str
    status: str


def parse_utc_date(value: str) -> pd.Timestamp:
    if value.lower() in {"now", "today"}:
        return pd.Timestamp.now(tz="UTC")
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def timeframe_ms(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == "m":
        return value * 60 * 1000
    if unit == "h":
        return value * 60 * 60 * 1000
    if unit == "d":
        return value * 24 * 60 * 60 * 1000
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_")


def ohlcv_path(root: Path, symbol: str, timeframe: str) -> Path:
    return root / timeframe / f"{safe_symbol(symbol)}.csv.gz"


def make_exchange(timeout_ms: int):
    import ccxt

    return ccxt.binanceusdm({"enableRateLimit": True, "timeout": timeout_ms, "options": {"defaultType": "future"}})


def first_float(*values) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def fetch_top_usdt_perpetuals(exchange, top: int, include_majors: bool) -> list[str]:
    markets = exchange.load_markets()
    tickers = exchange.fetch_tickers()
    rows: list[tuple[str, float]] = []
    for symbol, market in markets.items():
        if not market.get("active", True):
            continue
        if not market.get("swap"):
            continue
        if market.get("quote") != "USDT":
            continue
        base = str(market.get("base") or "").upper()
        if not include_majors and base in EXCLUDED_ALTCOIN_BASES:
            continue
        ticker = tickers.get(symbol, {})
        quote_volume = first_float(
            ticker.get("quoteVolume"),
            ticker.get("info", {}).get("quoteVolume"),
            ticker.get("info", {}).get("volume"),
            0.0,
        )
        if quote_volume <= 0:
            continue
        rows.append((symbol, quote_volume))
    rows.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, _quote_volume in rows[:top]]


def rows_to_frame(rows: list[list[float]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame["data_source"] = "exchange"
    return frame


def read_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "data_source"])
    frame = pd.read_csv(path, compression="gzip")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


def write_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy()
    output["timestamp"] = pd.to_datetime(output["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    output.to_csv(path, index=False, compression="gzip")


def merge_frames(existing: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        merged = fresh
    elif fresh.empty:
        merged = existing
    else:
        merged = pd.concat([existing, fresh], ignore_index=True)
    if merged.empty:
        return merged
    merged["timestamp"] = pd.to_datetime(merged["timestamp"], utc=True)
    merged = merged.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    return merged


def fetch_range(
    exchange,
    symbol: str,
    timeframe: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    limit: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    since_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    step_ms = timeframe_ms(timeframe)
    chunks: list[pd.DataFrame] = []
    batch = 0
    while since_ms < end_ms:
        rows = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not rows:
            break
        filtered = [row for row in rows if int(row[0]) < end_ms]
        if filtered:
            chunks.append(rows_to_frame(filtered))
        last_ms = int(rows[-1][0])
        next_ms = last_ms + step_ms
        if next_ms <= since_ms:
            break
        since_ms = next_ms
        batch += 1
        if batch % 10 == 0:
            print(
                f"progress symbol={symbol} timeframe={timeframe} downloaded_to={pd.to_datetime(last_ms, unit='ms', utc=True)}",
                flush=True,
            )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    if not chunks:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "data_source"])
    return pd.concat(chunks, ignore_index=True)


def download_symbol_timeframe(
    exchange,
    root: Path,
    symbol: str,
    timeframe: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    limit: int,
    sleep_seconds: float,
    resume: bool,
) -> DownloadSummary:
    path = ohlcv_path(root, symbol, timeframe)
    existing = read_existing(path) if resume else pd.DataFrame()
    effective_start = start
    if resume and not existing.empty:
        last_timestamp = pd.to_datetime(existing["timestamp"], utc=True).max()
        next_timestamp = last_timestamp + pd.Timedelta(milliseconds=timeframe_ms(timeframe))
        effective_start = max(start, next_timestamp)
    print(
        f"download symbol={symbol} timeframe={timeframe} start={effective_start.isoformat()} end={end.isoformat()} path={path}",
        flush=True,
    )
    if effective_start >= end:
        merged = merge_frames(existing, pd.DataFrame())
        return summarize(symbol, timeframe, path, merged, "up_to_date")
    fresh = fetch_range(exchange, symbol, timeframe, effective_start, end, limit, sleep_seconds)
    merged = merge_frames(existing, fresh)
    write_frame(path, merged)
    return summarize(symbol, timeframe, path, merged, "downloaded")


def summarize(symbol: str, timeframe: str, path: Path, frame: pd.DataFrame, status: str) -> DownloadSummary:
    if frame.empty:
        return DownloadSummary(symbol, timeframe, str(path), 0, "", "", "empty")
    return DownloadSummary(
        symbol=symbol,
        timeframe=timeframe,
        path=str(path),
        rows=len(frame),
        first_timestamp=pd.to_datetime(frame["timestamp"], utc=True).min().isoformat(),
        last_timestamp=pd.to_datetime(frame["timestamp"], utc=True).max().isoformat(),
        status=status,
    )


def load_symbols_from_latest(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted({str(item.get("symbol") or "") for item in payload.get("leaders", []) if item.get("symbol")})


def load_symbols_file(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict) and "symbols" in payload:
            return [str(item) for item in payload["symbols"]]
        if isinstance(payload, dict) and "leaders" in payload:
            return [str(item.get("symbol") or "") for item in payload["leaders"] if item.get("symbol")]
        raise ValueError(f"Unsupported symbols JSON format: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]


def resolve_symbols(args: argparse.Namespace, exchange=None) -> list[str]:
    symbols: set[str] = set()
    if args.symbols:
        symbols.update(item.strip() for item in args.symbols.split(",") if item.strip())
    if args.symbols_file:
        symbols.update(load_symbols_file(Path(args.symbols_file)))
    if args.include_main:
        symbols.update(DEFAULT_SYMBOLS)
    if args.include_altcoin_latest:
        symbols.update(load_symbols_from_latest(DATA_DIR / "altcoin_strategy_latest.json"))
    if args.include_macro_latest:
        symbols.update(load_symbols_from_latest(DATA_DIR / "macro_strategy_latest.json"))
    if args.include_altcoin_top_volume:
        if exchange is None:
            raise ValueError("exchange is required for --include-altcoin-top-volume")
        symbols.update(fetch_top_usdt_perpetuals(exchange, args.top, args.include_majors))
    return sorted(symbol for symbol in symbols if symbol)


def write_manifest(root: Path, summaries: list[DownloadSummary], start: str, end: str) -> None:
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exchange": "binanceusdm",
        "market_type": "USDT futures",
        "start": start,
        "end": end,
        "storage": "csv.gz",
        "count": len(summaries),
        "items": [asdict(item) for item in summaries],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and store Binance USDT futures OHLCV for local backtests")
    parser.add_argument("--start", default=DEFAULT_START, help="inclusive UTC start date")
    parser.add_argument("--end", default=DEFAULT_END, help="exclusive UTC end date")
    parser.add_argument("--timeframes", default=",".join(DEFAULT_TIMEFRAMES), help="comma-separated timeframes")
    parser.add_argument("--symbols", default="", help="comma-separated symbols; overrides nothing, adds to selected symbols")
    parser.add_argument("--symbols-file", default="", help="text or JSON file with symbols")
    parser.add_argument("--include-main", action=argparse.BooleanOptionalAction, default=True, help="include BTC/ETH/SOL")
    parser.add_argument("--include-altcoin-latest", action="store_true", help="include symbols from altcoin_strategy_latest.json")
    parser.add_argument("--include-altcoin-top-volume", action="store_true", help="include top-volume Binance USDT perpetual symbols")
    parser.add_argument("--include-macro-latest", action="store_true", help="include symbols from macro_strategy_latest.json")
    parser.add_argument("--top", type=int, default=100, help="top-volume symbol count for --include-altcoin-top-volume")
    parser.add_argument("--include-majors", action="store_true", help="include BTC/ETH and stablecoin-like symbols in top-volume selection")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="storage root directory")
    parser.add_argument("--limit", type=int, default=1000, help="ccxt candles per request")
    parser.add_argument("--timeout-ms", type=int, default=20000, help="ccxt timeout in milliseconds")
    parser.add_argument("--sleep-seconds", type=float, default=0.05, help="sleep between paged requests")
    parser.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True, help="resume from existing csv.gz files")
    args = parser.parse_args()

    exchange = make_exchange(args.timeout_ms)
    symbols = resolve_symbols(args, exchange)
    if not symbols:
        raise SystemExit("no symbols selected")
    timeframes = [item.strip() for item in args.timeframes.split(",") if item.strip()]
    start = parse_utc_date(args.start)
    end = parse_utc_date(args.end)
    root = Path(args.root)
    summaries: list[DownloadSummary] = []
    print(
        f"historical_download symbols={len(symbols)} timeframes={','.join(timeframes)} start={start.date()} end={end.date()} root={root}",
        flush=True,
    )
    for symbol in symbols:
        for timeframe in timeframes:
            try:
                summary = download_symbol_timeframe(
                    exchange,
                    root,
                    symbol,
                    timeframe,
                    start,
                    end,
                    args.limit,
                    args.sleep_seconds,
                    args.resume,
                )
                summaries.append(summary)
                print(
                    f"saved symbol={summary.symbol} timeframe={summary.timeframe} rows={summary.rows} "
                    f"first={summary.first_timestamp or '-'} last={summary.last_timestamp or '-'} status={summary.status}",
                    flush=True,
                )
            except Exception as exc:
                print(f"download_error symbol={symbol} timeframe={timeframe} error={exc}", flush=True)
    write_manifest(root, summaries, args.start, args.end)
    print(f"manifest={root / 'manifest.json'}")


if __name__ == "__main__":
    main()
