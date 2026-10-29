"""Step 5 - Build the clean, signed fills table.

For every market:
  1. Normalize raw taker rows and all rows to one schema.
  2. Label roles: taker rows come from the taker pull; maker rows are the rows
     of the "all" pull that are not in the taker pull (multiset anti-join on
     tx hash, wallet, token, side, size, price).
  3. Express every fill in outcome-0 terms so YES and NO trading can be pooled:
        dir0 = +1 if the fill raises exposure to outcome 0 (buy token 0, or
               sell token 1), -1 otherwise
        p0   = price of outcome 0 implied by the fill (p, or 1 - p for token 1)
  4. Flag self-trades: a wallet that appears as both taker and maker in the
     same transaction, or that both buys and sells the same token in the same
     transaction (wash / self-cross).

Output: data/processed/fills.csv.gz      one row per wallet-side of a fill
        data/interim/build_log.json      counts used by validation (s08)
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import load_config, normalize_trade, read_jsonl, write_table

KEY = ["tx_hash", "wallet", "token_id", "side", "size", "price"]


def multiset_anti_join(all_rows: pd.DataFrame, taker: pd.DataFrame) -> pd.DataFrame:
    """Rows of all_rows not matched one-for-one by a row in taker."""
    a = all_rows.copy()
    t = taker[KEY].copy()
    a["_k"] = a.groupby(KEY).cumcount()
    t["_k"] = t.groupby(KEY).cumcount()
    m = a.merge(t.assign(_in_taker=True), on=KEY + ["_k"], how="left")
    return m[m["_in_taker"].isna()].drop(columns=["_k", "_in_taker"])


def build_market(m, raw_dir, log) -> pd.DataFrame | None:
    t_raw = read_jsonl(raw_dir / f"{m.condition_id}__taker.jsonl")
    a_raw = read_jsonl(raw_dir / f"{m.condition_id}__all.jsonl")
    if not t_raw:
        log["markets_without_trades"] += 1
        return None
    taker = pd.DataFrame([normalize_trade(r) for r in t_raw]).drop_duplicates()
    allr = pd.DataFrame([normalize_trade(r) for r in a_raw]) if a_raw else taker.iloc[0:0]
    maker = multiset_anti_join(allr, taker)
    log["taker_rows"] += len(taker)
    log["all_rows"] += len(allr)
    log["maker_rows"] += len(maker)

    df = pd.concat([taker.assign(role="taker"), maker.assign(role="maker")], ignore_index=True)
    df["condition_id"] = m.condition_id

    # Outcome index from the token id (more reliable than the outcome label).
    tok = {str(m.token_0): 0, str(m.token_1): 1}
    df["outcome_index"] = df["token_id"].map(tok)
    unknown = df["outcome_index"].isna()
    log["rows_unknown_token"] += int(unknown.sum())
    df = df[~unknown].copy()
    df["outcome_index"] = df["outcome_index"].astype(int)

    bad = (df["size"] <= 0) | ~df["price"].between(0, 1, inclusive="neither")
    log["rows_bad_price_or_size"] += int(bad.sum())
    df = df[~bad].copy()

    buy = df["side"].eq("BUY")
    tok0 = df["outcome_index"].eq(0)
    df["dir0"] = np.where(buy == tok0, 1, -1)
    df["p0"] = np.where(tok0, df["price"], 1 - df["price"])
    df["usdc"] = df["price"] * df["size"]
    df["token_won"] = (df["outcome_index"] == m.winning_index).astype(int)
    df["outcome0"] = int(m.winning_index == 0)

    # Self-trade flags.
    roles = df.groupby(["tx_hash", "wallet"])["role"].transform("nunique")
    sides = df.groupby(["tx_hash", "wallet", "token_id"])["side"].transform("nunique")
    df["self_trade"] = ((roles > 1) | (sides > 1)).astype(int)
    return df


def main():
    cfg = load_config()
    markets = pd.read_csv(cfg["paths"]["interim"] / "markets.csv", dtype={"token_0": str, "token_1": str})
    raw_dir = cfg["paths"]["raw"] / "trades"
    log = {k: 0 for k in ["taker_rows", "all_rows", "maker_rows", "rows_unknown_token",
                          "rows_bad_price_or_size", "markets_without_trades"]}
    frames = []
    for m in markets.itertuples():
        f = build_market(m, raw_dir, log)
        if f is not None:
            frames.append(f)
    fills = pd.concat(frames, ignore_index=True)
    fills = fills.sort_values(["condition_id", "timestamp", "tx_hash", "role"]).reset_index(drop=True)
    cols = ["condition_id", "tx_hash", "timestamp", "wallet", "role", "token_id", "outcome_index",
            "side", "price", "size", "usdc", "dir0", "p0", "token_won", "outcome0", "self_trade"]
    fills = fills[cols]

    log["fills_rows"] = len(fills)
    log["self_trade_rows"] = int(fills["self_trade"].sum())
    log["self_trade_usdc_share"] = float(fills.loc[fills.self_trade == 1, "usdc"].sum() / fills["usdc"].sum())
    write_table(fills, cfg["paths"]["processed"] / "fills.csv.gz")
    with open(cfg["paths"]["interim"] / "build_log.json", "w") as f:
        json.dump(log, f, indent=2)
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
