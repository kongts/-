import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "quant_bot.db"
STATE_PATH = DATA_DIR / "state.json"
ERROR_LOG_PATH = LOG_DIR / "error.log"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv(PROJECT_DIR / ".env")

INITIAL_CASH = 10_000.0
TIMEFRAME = "1h"
KLINE_LIMIT = 200
LOOP_SLEEP_SECONDS = 60
MAX_CYCLES = 1

EXECUTION_MODE = os.getenv("EXECUTION_MODE", "paper").lower()
SLIPPAGE_RATE = 0.0005
MAKER_FEE_RATE = 0.0002
TAKER_FEE_RATE = 0.0005
FEE_RATE = TAKER_FEE_RATE
FUNDING_COST_RATE_PER_8H = 0.0001
BINANCE_TESTNET_API_KEY = os.getenv("BINANCE_TESTNET_API_KEY", "")
BINANCE_TESTNET_API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET", "")

MAX_TOTAL_MARGIN_RATIO = 0.30
MAX_LEVERAGE = 3
MAX_DRAWDOWN = 0.10
MAX_DAILY_LOSS = 0.05
MAX_CONSECUTIVE_LOSSES = 3
MIN_RECENT_WIN_RATE = 0.30
RECENT_TRADE_WINDOW = 10
ABNORMAL_VOLATILITY_MULTIPLIER = 3.0

BINANCE_FUTURES_TESTNET_REST_URL = "https://demo-fapi.binance.com"
