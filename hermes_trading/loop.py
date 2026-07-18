import asyncio
import json
import time
from pathlib import Path

import numpy as np
import yaml

from hermes_trading.adapters import price as price_adapter

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
TRADES_PATH = STATE_DIR / "trades.jsonl"
STRATEGY_PATH = STATE_DIR / "strategy.yaml"
HEARTBEAT_PATH = STATE_DIR / "heartbeat.json"

POLL_SECONDS = 60
MAX_RETRIES = 3
CIRCUIT_BREAK_AFTER = 5


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains = deltas[deltas > 0].sum() / period
    losses = -deltas[deltas < 0].sum() / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return float(100 - (100 / (1 + rs)))


async def _fetch_with_retry(symbol: str) -> dict:
    delay = 1
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            return await price_adapter.fetch(symbol)
        except Exception as exc:  # noqa: BLE001 - adapter failures are expected transient errors
            last_exc = exc
            print(f"[loop] fetch attempt {attempt + 1}/{MAX_RETRIES} failed: {exc}")
            await asyncio.sleep(delay)
            delay *= 2
    raise last_exc


def _append_trade(trade: dict) -> None:
    with open(TRADES_PATH, "a") as f:
        f.write(json.dumps(trade) + "\n")


def _write_heartbeat(status: str, extra: dict | None = None) -> None:
    payload = {"ts": time.time(), "status": status, **(extra or {})}
    HEARTBEAT_PATH.write_text(json.dumps(payload))


def _load_open_position() -> dict | None:
    if not TRADES_PATH.exists():
        return None
    last_open = None
    with open(TRADES_PATH) as f:
        for line in f:
            trade = json.loads(line)
            if trade["status"] == "open":
                last_open = trade
            elif trade["status"] == "closed" and last_open and trade["id"] == last_open["id"]:
                last_open = None
    return last_open


async def run_loop(asset: str) -> None:
    consecutive_failures = 0
    open_position = _load_open_position()
    trade_counter = sum(1 for _ in open(TRADES_PATH)) if TRADES_PATH.exists() else 0

    print(f"Booting hermes-trading worker for {asset}")

    while True:
        strategy = _load_yaml(STRATEGY_PATH)

        try:
            data = await _fetch_with_retry(asset)
            consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            print(f"[loop] adapter failed {consecutive_failures}/{CIRCUIT_BREAK_AFTER}: {exc}")
            if consecutive_failures >= CIRCUIT_BREAK_AFTER:
                _write_heartbeat("circuit_broken", {"error": str(exc)})
                print("[loop] circuit breaker tripped, halting")
                return
            await asyncio.sleep(POLL_SECONDS)
            continue

        closes = [c[4] for c in data["candles"]]
        last_price = closes[-1]
        rsi = _rsi(closes)

        if open_position is None:
            entry = strategy["entry"]
            fires = (
                entry["indicator"] == "rsi"
                and entry["direction"] == "long"
                and rsi < entry["threshold"]
            )
            if fires:
                trade_counter += 1
                open_position = {
                    "id": trade_counter,
                    "asset": asset,
                    "status": "open",
                    "direction": "long",
                    "entry_price": last_price,
                    "entry_rsi": rsi,
                    "opened_at": time.time(),
                    "stop_loss_pct": strategy["stop_loss_pct"],
                    "position_size_r": strategy["position_size_r"],
                }
                _append_trade(open_position)
                print(f"[loop] opened trade #{trade_counter} @ {last_price} (rsi={rsi:.1f})")
        else:
            change_pct = (last_price - open_position["entry_price"]) / open_position["entry_price"] * 100
            stop = -open_position["stop_loss_pct"]
            take_profit = open_position["stop_loss_pct"] * 2  # 1:2 risk:reward

            if change_pct <= stop or change_pct >= take_profit:
                closed = {
                    **open_position,
                    "status": "closed",
                    "exit_price": last_price,
                    "pnl_pct": change_pct / 100,
                    "closed_at": time.time(),
                }
                _append_trade(closed)
                print(f"[loop] closed trade #{open_position[id]} pnl={change_pct:.2f}%")
                open_position = None

        _write_heartbeat("running", {"asset": asset, "last_price": last_price, "rsi": rsi})
        await asyncio.sleep(POLL_SECONDS)
