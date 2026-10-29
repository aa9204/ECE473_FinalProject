"""Step 4 (optional, forward-looking) - Record live order-book snapshots.

Polymarket's public API only serves the CURRENT book; there is no public
endpoint for historical books (Dubach built his own 52-day archive). So for
liquidity controls in Milestone 2 you have two options:
  (a) use liquidity proxies built from fills (spread proxies, depth hit per
      fill, Gamma's liquidityNum) - done automatically in s07; or
  (b) start this recorder now on markets that are still OPEN and will resolve
      before your analysis deadline, and add them as a second sample.

Usage:  python src/s04_record_books.py <token_id> [<token_id> ...]
Run it on a schedule (e.g. every 5 minutes via cron) - each call appends one
snapshot per token to data/raw/books.jsonl with best bid/ask, spread and depth.
"""
from __future__ import annotations

import sys
import time

from common import CLOB, append_jsonl, get_json, load_config


def snapshot(token_id: str) -> dict:
    b = get_json(f"{CLOB}/book", {"token_id": token_id})
    bids = sorted(((float(x["price"]), float(x["size"])) for x in b.get("bids", [])), reverse=True)
    asks = sorted((float(x["price"]), float(x["size"])) for x in b.get("asks", []))
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    mid = (best_bid + best_ask) / 2 if bids and asks else None

    def depth(levels, within):
        if mid is None:
            return None
        return sum(p * s for p, s in levels if abs(p - mid) <= within)

    return {
        "ts": int(time.time()),
        "token_id": token_id,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": (best_ask - best_bid) if bids and asks else None,
        "depth_bid_2c": depth(bids, 0.02),
        "depth_ask_2c": depth(asks, 0.02),
        "n_bid_levels": len(bids),
        "n_ask_levels": len(asks),
    }


def main():
    cfg = load_config()
    tokens = sys.argv[1:]
    if not tokens:
        sys.exit(__doc__)
    rows = []
    for t in tokens:
        try:
            rows.append(snapshot(t))
        except Exception as e:
            print(f"{t}: {e}", file=sys.stderr)
    append_jsonl(rows, cfg["paths"]["raw"] / "books.jsonl")
    print(f"recorded {len(rows)} snapshots")


if __name__ == "__main__":
    main()
