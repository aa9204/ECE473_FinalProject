"""Step 3 - Public price history for the first outcome token of each market.

Used as the reference price path for markouts (how far the price moved in
the trade's direction 1h / 24h later) and as an independent check on the
prices reconstructed from fills.

The /prices-history endpoint rejects long windows ("interval is too long"),
so each market is fetched in chunks of `price_chunk_days` (config.yaml); a
chunk that is still rejected is split in half until it succeeds.

Output: data/raw/prices.csv  (condition_id, t, p)  where p is the price of
        outcome 0 ("Yes" in most binary markets).
"""
from __future__ import annotations

import pandas as pd

from common import CLOB, get_json, load_config, write_table


def fetch_window(token: str, a: int, b: int, fid: int, sleep: float, depth: int = 0) -> list[dict]:
    try:
        resp = get_json(f"{CLOB}/prices-history",
                        {"market": token, "startTs": a, "endTs": b, "fidelity": fid}, sleep=sleep)
        return resp.get("history", [])
    except RuntimeError as e:
        if "too long" in str(e) and depth < 8 and b - a > 3600:
            mid = (a + b) // 2
            return (fetch_window(token, a, mid, fid, sleep, depth + 1)
                    + fetch_window(token, mid, b, fid, sleep, depth + 1))
        raise


def main():
    cfg = load_config()
    C = cfg["collection"]
    markets = pd.read_csv(cfg["paths"]["interim"] / "markets.csv", dtype={"token_0": str})
    fid = C["price_fidelity_min"]
    chunk = int(C.get("price_chunk_days", 7) * 86400)
    frames = []
    for i, m in enumerate(markets.itertuples(), 1):
        start, end = int(m.start_ts), int(m.resolution_ts) + 3600
        hist = []
        try:
            for a in range(start, end, chunk):
                hist += fetch_window(m.token_0, a, min(a + chunk, end), fid, C["sleep"])
        except Exception as e:
            print(f"[{i}] {m.condition_id[:10]} failed: {e}")
            continue
        h = pd.DataFrame(hist)
        if h.empty:
            print(f"[{i}] {m.condition_id[:10]} no price history")
            continue
        h["condition_id"] = m.condition_id
        frames.append(h[["condition_id", "t", "p"]].drop_duplicates("t"))
        print(f"[{i}/{len(markets)}] {m.condition_id[:10]}  {len(h):,} points")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["condition_id", "t", "p"])
    df = df.sort_values(["condition_id", "t"])
    write_table(df, cfg["paths"]["raw"] / "prices.csv")
    print(f"Price points: {len(df):,} across {df['condition_id'].nunique()} of {len(markets)} markets")


if __name__ == "__main__":
    main()