"""Step 2 - Pull every fill for each sampled market from the Data API (v2).

Each market is pulled twice:
  * taker_only=true   -> one row per fill, on the TAKER side. The taker is the
                         wallet whose order crossed the spread, so its `side`
                         is the true, on-chain trade direction (no tick-rule
                         guessing; this is the Dubach point).
  * taker_only=false  -> taker rows PLUS the maker rows of the same fills.
                         Rows in this pull that are not in the taker pull are
                         the makers (resting liquidity), which we need for
                         positions and for self-trade detection.

Output: data/raw/trades/<condition_id>__taker.jsonl
        data/raw/trades/<condition_id>__all.jsonl
Re-running skips markets already completed (a .done marker is written last).
"""
from __future__ import annotations

import sys

import pandas as pd

from common import DATA, append_jsonl, get_json, load_config


def pull(condition_id: str, taker_only: bool, path, sleep: float) -> int:
    if path.exists():
        path.unlink()  # restart this market cleanly if a previous run died midway
    params = {
        "condition": condition_id,
        "taker_only": str(taker_only).lower(),
        "filter_amount": 0,   # keep dust fills too; we decide what to drop later
        "limit": 1000,
    }
    n, cursor = 0, None
    while True:
        p = dict(params)
        if cursor:
            p = {"condition": condition_id, "taker_only": str(taker_only).lower(),
                 "filter_amount": 0, "cursor": cursor}
        resp = get_json(f"{DATA}/v2/trades", p, sleep=sleep)
        if isinstance(resp, list):           # defensive: v1-style bare list
            rows, cursor = resp, None
        else:
            rows = resp.get("data", [])
            cursor = (resp.get("pagination") or {}).get("next_cursor")
        append_jsonl(rows, path)
        n += len(rows)
        if not cursor or not rows:
            return n


def main():
    cfg = load_config()
    markets = pd.read_csv(cfg["paths"]["interim"] / "markets.csv")
    out = cfg["paths"]["raw"] / "trades"
    out.mkdir(parents=True, exist_ok=True)
    sleep = cfg["collection"]["sleep"]

    for i, cid in enumerate(markets["condition_id"], 1):
        done = out / f"{cid}.done"
        if done.exists():
            continue
        try:
            nt = pull(cid, True, out / f"{cid}__taker.jsonl", sleep)
            na = pull(cid, False, out / f"{cid}__all.jsonl", sleep)
        except Exception as e:  # keep going; rerun the script to retry failures
            print(f"[{i}/{len(markets)}] {cid[:10]}... FAILED: {e}", file=sys.stderr)
            continue
        done.touch()
        print(f"[{i}/{len(markets)}] {cid[:10]}...  taker rows={nt:,}  all rows={na:,}")


if __name__ == "__main__":
    main()
