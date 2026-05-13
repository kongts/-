from __future__ import annotations

import json
from pathlib import Path

from . import config

SELECTED_STRATEGY_PATH = config.DATA_DIR / "selected_strategy.json"

DEFAULT_STRATEGY = {
    "strategy_id": "regime_ma_rsi",
    "strategy_name": "Regime MA/RSI",
    "source": "default",
    "per_symbol": {},
}


def load_selected_strategy(path: Path = SELECTED_STRATEGY_PATH) -> dict:
    if not path.exists():
        return DEFAULT_STRATEGY.copy()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "per_symbol" not in payload:
            payload["per_symbol"] = {}
        return payload
    except json.JSONDecodeError:
        return DEFAULT_STRATEGY.copy()


def save_selected_strategy(payload: dict, path: Path = SELECTED_STRATEGY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
