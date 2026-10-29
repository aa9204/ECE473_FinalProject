"""Step 7 - Behavioral measures and held-out skill labels.

1. Split markets in time: markets resolving at or before the
   `skill_split_quantile` of resolution dates are the ESTIMATION set; the rest
   are the EVALUATION set.  Skill is measured only on the estimation set and
   timing / informativeness / splitting only on the evaluation set, so a
   wallet is never called skilled because of the very trades being studied.

2. Skill (estimation set, complete positions only, wallets with at least
   `min_markets_for_skill` markets):
     skill_t   = mean(per-market ROI) / (sd / sqrt(n))   <- main label
     hit_rate  = share of markets where direction matched the outcome
   Wallets are cut into terciles of skill_t: low / mid / high.

3. Trade-level measures (evaluation set, TAKER executions - the aggressive,
   direction-revealing trades):
     life          (t - open) / (resolution - open), 0..1
     hours_to_res  hours before resolution
     markout_{h}h  dir0 * (p0 at t+h - execution p0), in price units
     markout_res   dir0 * (outcome0 - execution p0) = per-share profit to
                   resolution; positive = trade pointed the right way

Outputs: data/processed/trades_eval.csv.gz   taker executions + measures + skill
         data/processed/wallet_skill.csv     skill estimates (estimation set)
         data/processed/wallet_measures.csv  one row per wallet (evaluation set)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import load_config, write_table


def reference_prices(prices: pd.DataFrame, ex: pd.DataFrame) -> pd.DataFrame:
    """Price path of outcome 0 per market: public history if we have it,
    otherwise the last execution price (fallback for markets with no history)."""
    have = set(prices["condition_id"]) if len(prices) else set()
    fb = ex[~ex["condition_id"].isin(have)][["condition_id", "timestamp", "p0"]]
    fb = fb.rename(columns={"timestamp": "t", "p0": "p"})
    ref = pd.concat([prices[["condition_id", "t", "p"]], fb], ignore_index=True)
    return ref.sort_values("t").reset_index(drop=True)


def add_markouts(tr: pd.DataFrame, ref: pd.DataFrame, hours: list[int]) -> pd.DataFrame:
    tr = tr.sort_values("timestamp").reset_index(drop=True)
    for h in hours:
        q = tr[["condition_id", "timestamp"]].copy()
        q["t"] = (q["timestamp"] + h * 3600).astype("int64")
        q["_row"] = np.arange(len(q))
        q = q.sort_values("t")
        r = ref.assign(t=ref["t"].astype("int64"))
        m = pd.merge_asof(q, r, on="t", by="condition_id", direction="backward")
        m = m.sort_values("_row")
        p_future = m["p"].to_numpy()
        # Horizon past resolution: use the resolved value instead.
        past = (tr["timestamp"] + h * 3600 >= tr["resolution_ts"]).to_numpy()
        p_future = np.where(past, tr["outcome0"], p_future)
        tr[f"markout_{h}h"] = tr["dir0"] * (p_future - tr["p0"])
    tr["markout_res"] = tr["dir0"] * (tr["outcome0"] - tr["p0"])
    return tr


def skill_table(pos: pd.DataFrame, min_n: int) -> pd.DataFrame:
    p = pos[(pos["incomplete"] == 0) & (pos["capital"] > 0)]
    g = p.groupby("wallet")
    sk = g.agg(n_markets_est=("condition_id", "nunique"), pnl_est=("pnl", "sum"),
               capital_est=("capital", "sum"), hit_rate=("correct", "mean"),
               roi_mean=("roi", "mean"), roi_sd=("roi", "std")).reset_index()
    sk = sk[sk["n_markets_est"] >= min_n].copy()
    sk["roi_pooled"] = sk["pnl_est"] / sk["capital_est"]
    sd = sk["roi_sd"].where(sk["roi_sd"] > 0)
    sk["skill_t"] = sk["roi_mean"] / (sd / np.sqrt(sk["n_markets_est"]))
    sk = sk[sk["skill_t"].notna()].copy()
    sk["skill_tercile"] = pd.qcut(sk["skill_t"].rank(method="first"), 3, labels=["low", "mid", "high"]).astype(str)
    return sk


def main():
    cfg = load_config()
    P, M = cfg["paths"], cfg["measures"]
    markets = pd.read_csv(P["interim"] / "markets.csv")
    ex = pd.read_csv(P["processed"] / "executions.csv.gz", dtype={"token_id": str})
    pos = pd.read_csv(P["processed"] / "positions.csv.gz")
    prices = pd.read_csv(P["raw"] / "prices.csv")

    cut = markets["resolution_ts"].quantile(M["skill_split_quantile"])
    markets["set"] = np.where(markets["resolution_ts"] <= cut, "estimation", "evaluation")
    sets = markets.set_index("condition_id")["set"]
    pos["set"] = pos["condition_id"].map(sets)
    print(markets["set"].value_counts().to_string())

    # --- skill on the estimation set --------------------------------------
    sk = skill_table(pos[pos["set"] == "estimation"], M["min_markets_for_skill"])
    write_table(sk, P["processed"] / "wallet_skill.csv")
    print(f"skill labels for {len(sk):,} wallets")

    # --- trade-level measures on the evaluation set -----------------------
    tr = ex[(ex["role"] == "taker") & ex["condition_id"].map(sets).eq("evaluation")].copy()
    tr = tr.merge(markets[["condition_id", "start_ts", "resolution_ts", "winning_index", "volume_gamma"]],
                  on="condition_id")
    tr["outcome0"] = (tr["winning_index"] == 0).astype(int)
    tr = tr[tr["timestamp"] <= tr["resolution_ts"]]
    tr["life"] = ((tr["timestamp"] - tr["start_ts"]) / (tr["resolution_ts"] - tr["start_ts"])).clip(0, 1)
    tr["hours_to_res"] = (tr["resolution_ts"] - tr["timestamp"]) / 3600
    edges = M["life_bins"]
    labels = [f"{a:.0%}–{b:.0%}" for a, b in zip(edges[:-1], edges[1:])]
    tr["life_bin"] = pd.cut(tr["life"], edges, labels=labels, include_lowest=True).astype(str)
    tr = add_markouts(tr, reference_prices(prices, ex), M["markout_hours"])
    tr = tr.merge(sk[["wallet", "skill_t", "skill_tercile"]], on="wallet", how="left")
    tr["skill_tercile"] = tr["skill_tercile"].fillna("unlabeled")
    write_table(tr, P["processed"] / "trades_eval.csv.gz")
    print(f"evaluation taker executions: {len(tr):,}")

    # --- wallet-level summary (evaluation set) ----------------------------
    late = M["life_bins"][-3]  # e.g. last 10% of market life
    tr["is_late"] = (tr["life"] >= late).astype(int)
    tr["w_life"] = tr["life"] * tr["usdc"]
    tr["w_mres"] = tr["markout_res"] * tr["usdc"]
    tr["late_usdc"] = tr["is_late"] * tr["usdc"]
    tw = tr.groupby("wallet").agg(n_taker_exec=("tx_hash", "size"), taker_usdc=("usdc", "sum"),
                                  w_life=("w_life", "sum"), w_mres=("w_mres", "sum"),
                                  late_usdc=("late_usdc", "sum")).reset_index()
    tw["vw_life"] = tw["w_life"] / tw["taker_usdc"]
    tw["vw_markout_res"] = tw["w_mres"] / tw["taker_usdc"]
    tw["late_share"] = tw["late_usdc"] / tw["taker_usdc"]
    tw = tw.drop(columns=["w_life", "w_mres", "late_usdc"])

    pe = pos[pos["set"] == "evaluation"]
    pw = pe.groupby("wallet").agg(n_markets_eval=("condition_id", "nunique"),
                                  mean_n_build_exec=("n_build_exec", "mean"),
                                  mean_build_hhi=("build_hhi", "mean"),
                                  mean_holding_hours=("holding_hours", "mean"),
                                  hit_rate_eval=("correct", "mean"),
                                  pnl_eval=("pnl", "sum")).reset_index()
    wm = pw.merge(tw, on="wallet", how="left").merge(sk, on="wallet", how="left")
    wm["skill_tercile"] = wm["skill_tercile"].fillna("unlabeled")
    write_table(wm, P["processed"] / "wallet_measures.csv")
    print(f"wallet_measures: {len(wm):,} wallets active in evaluation set")


if __name__ == "__main__":
    main()
