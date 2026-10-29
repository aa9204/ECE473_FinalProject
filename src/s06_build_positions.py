"""Step 6 - Reconstruct wallet x market positions and executions.

Self-trade fills are excluded from everything here.

executions.csv.gz : one row per wallet x tx x token x side x role. Several
    fills in one transaction are one execution (a single taker order that hit
    several resting orders is NOT splitting; it is one decision).
positions.csv.gz  : one row per wallet x market with
    direction      sign of outcome-0 exposure at its largest point
    entry_ts/exit_ts, holding_hours  (exit = last fill if the wallet closed out,
                   otherwise resolution: held to the end)
    pnl, capital   cash flows + payoff of shares still held at resolution;
                   capital = gross USDC spent buying
    correct        direction matched the realized outcome
    n_fills, n_exec, n_build_exec   fills / executions / executions that
                   increased exposure
    build_hhi      Herfindahl of build-execution sizes (1 = one shot,
                   ~1/n = n equal slices)  -> order-splitting measure
    max_exec_share largest build execution / total built
    median_gap_min median minutes between build executions
    incomplete     wallet ended with negative token inventory, i.e. it got
                   shares outside the order book (split/merge/transfer), so
                   its PnL from trades alone is unreliable
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import load_config, write_table


def build_executions(fills: pd.DataFrame) -> pd.DataFrame:
    keys = ["condition_id", "wallet", "tx_hash", "token_id", "outcome_index", "side", "role"]
    g = fills.groupby(keys, sort=False)
    ex = g.agg(timestamp=("timestamp", "min"), size=("size", "sum"), usdc=("usdc", "sum"),
               dir0=("dir0", "first"), n_fills=("size", "size")).reset_index()
    ex["price"] = ex["usdc"] / ex["size"]
    ex["p0"] = np.where(ex["outcome_index"] == 0, ex["price"], 1 - ex["price"])
    ex["signed0"] = ex["dir0"] * ex["size"]          # change in outcome-0 exposure (shares)
    return ex.sort_values(["condition_id", "wallet", "timestamp"]).reset_index(drop=True)


def position_stats(ex: pd.DataFrame, res_ts: float, winner: int) -> dict:
    ex = ex.sort_values("timestamp")
    net = ex["signed0"].cumsum().to_numpy()
    peak_i = int(np.argmax(np.abs(net)))
    direction = int(np.sign(net[peak_i])) or int(np.sign(ex["signed0"].iloc[0]))
    peak = abs(net[peak_i])

    # Shares held per token at the end, and cash.
    sgn = np.where(ex["side"].eq("BUY"), 1, -1)
    shares = (ex.assign(q=sgn * ex["size"]).groupby("outcome_index")["q"].sum())
    cash = float((-sgn * ex["usdc"]).sum())
    payoff = float(shares.get(winner, 0.0))
    incomplete = bool((shares < -1e-6).any())

    closed_out = abs(net[-1]) <= 0.02 * max(peak, 1e-9)
    entry = float(ex["timestamp"].iloc[0])
    exit_ = float(ex["timestamp"].iloc[-1]) if closed_out else float(res_ts)

    build = ex[np.sign(ex["signed0"]) == direction]
    sizes = build["size"].to_numpy()
    tot = sizes.sum()
    gaps = np.diff(build["timestamp"].to_numpy()) / 60.0
    return {
        "direction": direction,
        "peak_shares": peak,
        "entry_ts": entry,
        "exit_ts": exit_,
        "closed_out": int(closed_out),
        "holding_hours": (exit_ - entry) / 3600.0,
        "pnl": cash + payoff,
        "capital": float(ex.loc[ex["side"].eq("BUY"), "usdc"].sum()),
        "volume_usdc": float(ex["usdc"].sum()),
        "taker_share": float(ex.loc[ex["role"].eq("taker"), "usdc"].sum() / ex["usdc"].sum()),
        "n_fills": int(ex["n_fills"].sum()),
        "n_exec": len(ex),
        "n_build_exec": len(build),
        "build_hhi": float(((sizes / tot) ** 2).sum()) if tot > 0 else np.nan,
        "max_exec_share": float(sizes.max() / tot) if tot > 0 else np.nan,
        "median_gap_min": float(np.median(gaps)) if len(gaps) else np.nan,
        "build_span_hours": float((build["timestamp"].max() - build["timestamp"].min()) / 3600) if len(build) else np.nan,
        "incomplete": int(incomplete),
    }


def main():
    cfg = load_config()
    P = cfg["paths"]
    markets = pd.read_csv(P["interim"] / "markets.csv")
    fills = pd.read_csv(P["processed"] / "fills.csv.gz", dtype={"token_id": str})
    fills = fills[fills["self_trade"] == 0]

    ex = build_executions(fills)
    write_table(ex, P["processed"] / "executions.csv.gz")
    print(f"executions: {len(ex):,} from {len(fills):,} non-self-trade fills")

    mk = markets.set_index("condition_id")
    rows = []
    for (cid, w), g in ex.groupby(["condition_id", "wallet"], sort=False):
        m = mk.loc[cid]
        r = position_stats(g, m["resolution_ts"], int(m["winning_index"]))
        r.update(condition_id=cid, wallet=w)
        rows.append(r)
    pos = pd.DataFrame(rows)
    pos = pos.merge(markets[["condition_id", "start_ts", "resolution_ts", "winning_index"]], on="condition_id")
    pos["outcome0"] = (pos["winning_index"] == 0).astype(int)
    pos["correct"] = ((pos["direction"] == 1) == (pos["outcome0"] == 1)).astype(int)
    pos["entry_life"] = (pos["entry_ts"] - pos["start_ts"]) / (pos["resolution_ts"] - pos["start_ts"])
    pos["roi"] = pos["pnl"] / pos["capital"].where(pos["capital"] > 0)
    lead = ["wallet", "condition_id"]
    pos = pos[lead + [c for c in pos.columns if c not in lead]]
    write_table(pos, P["processed"] / "positions.csv.gz")
    print(f"positions: {len(pos):,} wallet-market pairs, {pos['wallet'].nunique():,} wallets, "
          f"{pos['incomplete'].mean():.1%} flagged incomplete")


if __name__ == "__main__":
    main()
