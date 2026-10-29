"""Shared helpers: config, paths, HTTP with retries, and field normalization.

Polymarket's APIs have changed field casing over time (camelCase in older
responses, snake_case in Data API v2).  `normalize_trade` maps every variant
we know of onto one internal schema so the rest of the pipeline never has to
care which version produced the raw file.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        cfg = yaml.safe_load(f)
    # PM_DATA_ROOT lets the simulated test data live in its own folder so it
    # can never mix with the real pull (see src/simulate.py).
    base = Path(os.environ.get("PM_DATA_ROOT", ROOT))
    for key, rel in cfg["paths"].items():
        p = base / rel
        p.mkdir(parents=True, exist_ok=True)
        cfg["paths"][key] = p
    return cfg


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
_session = requests.Session()
_session.headers.update({"User-Agent": "polymarket-m1-research/1.0"})


def get_json(url: str, params: dict | None = None, retries: int = 6, sleep: float = 0.25):
    """GET with exponential backoff on 429/5xx. Returns parsed JSON."""
    delay = 1.0
    for attempt in range(retries):
        r = _session.get(url, params=params, timeout=30)
        if r.status_code == 200:
            time.sleep(sleep)
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            wait = delay
            try:
                wait = float(r.json().get("retry_after_seconds", delay))
            except Exception:
                pass
            time.sleep(wait)
            delay *= 2
            continue
        raise RuntimeError(f"{r.status_code} for {r.url}: {r.text[:300]}")
    raise RuntimeError(f"gave up after {retries} tries: {url} {params}")


# --------------------------------------------------------------------------
# I/O: gzip CSV keeps dependencies minimal (no pyarrow needed).
# --------------------------------------------------------------------------
def write_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip" if str(path).endswith(".gz") else None)


def read_table(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, **kw)


def append_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# --------------------------------------------------------------------------
# Field normalization
# --------------------------------------------------------------------------
def _pick(row: dict, *names, default=None):
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return default


def normalize_trade(row: dict) -> dict:
    """Map a raw Data API trade row (v1 or v2 casing) to the internal schema."""
    ts = _pick(row, "timestamp", "match_time", "matchTime")
    ts = int(float(ts))
    if ts > 10**12:  # milliseconds
        ts //= 1000
    return {
        "tx_hash": _pick(row, "transaction_hash", "transactionHash", "tx_hash"),
        "timestamp": ts,
        "condition_id": _pick(row, "condition_id", "conditionId", "market"),
        "token_id": str(_pick(row, "asset", "token_id", "tokenId", "asset_id", "assetId")),
        "outcome_index": _pick(row, "outcome_index", "outcomeIndex"),
        "outcome": _pick(row, "outcome"),
        "wallet": str(_pick(row, "proxy_wallet", "proxyWallet", "user", "maker_address")).lower(),
        "side": str(_pick(row, "side")).upper(),
        "size": float(_pick(row, "size", default=0)),
        "price": float(_pick(row, "price", default=float("nan"))),
    }
