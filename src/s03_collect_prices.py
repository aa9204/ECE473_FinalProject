"""Step 3 - Public price history for the first outcome token of each market.

Used as the reference price path for markouts (how far the price moved in
the trade's direction 1h / 24h later) and as an independent check on the
prices reconstructed from fills.

Output: data/raw/prices.csv  (condition_id, t, p)  where p is the price of
        outcome 0 ("Yes" in most binary markets).
"""
from __future__ import annotations

import pandas as pd

from common import CLOB, get_json, load_config, write_table


def main():
    cfg = load_config()
    markets = pd.read_csv(cfg["paths"]["interim"] / "markets.csv", dtype={"token_0": str})
    fid = cfg["collection"]["price_fidelity_min"]
    frames = []
    for i, m in enumerate(markets.itertuples(), 1):
        try:
            resp = get_json(
                f"{CLOB}/prices-history",
                {"market": m.token_0, "startTs": int(m.start_ts), "endTs": int(m.resolution_ts) + 3600,
                 "fidelity": fid},
                sleep=cfg["collection"]["sleep"],
            )
        except Exception as e:
            print(f"[{i}] {m.condition_id[:10]} failed: {e}")
            continue
        h = pd.DataFrame(resp.get("history", []))
        if h.empty:
            continue
        h["condition_id"] = m.condition_id
        frames.append(h[["condition_id", "t", "p"]])
        if i % 25 == 0:
            print(f"  {i}/{len(markets)} markets")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["condition_id", "t", "p"])
    write_table(df, cfg["paths"]["raw"] / "prices.csv")
    print(f"Price points: {len(df):,} across {df['condition_id'].nunique()} markets")


if __name__ == "__main__":
    main()
