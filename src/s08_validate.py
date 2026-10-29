"""Step 8 - Validation checks.  Writes output/validation_report.md.

Checks
  1. Row accounting: taker rows, maker rows, dropped rows.
  2. Volume reconciliation: our taker-side USDC per market vs Gamma volumeNum.
  3. Price consistency: fill-implied outcome-0 price vs public price history.
  4. Trade signing: tick-rule direction (what you would infer from the public
     price feed) vs the true on-chain taker direction.  Dubach (2026) finds
     roughly 60% agreement; a number in that region is reassuring.
  5. Self-trading: share of each market's volume flagged as self-trade
     (Dubach: typically near 1% with a heavy tail).
  6. Position integrity: share of positions with negative token inventory.
  7. Spot-check list: random wallets to compare by hand with their public
     Polymarket profile page.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import load_config


def tick_rule(p: np.ndarray) -> np.ndarray:
    """+1 on uptick, -1 on downtick, carry last sign on zero tick."""
    d = np.sign(np.diff(p, prepend=np.nan))
    s = pd.Series(d).replace(0, np.nan).ffill().to_numpy()
    return s


def main():
    cfg = load_config()
    P = cfg["paths"]
    markets = pd.read_csv(P["interim"] / "markets.csv")
    fills = pd.read_csv(P["processed"] / "fills.csv.gz", dtype={"token_id": str})
    ex = pd.read_csv(P["processed"] / "executions.csv.gz", dtype={"token_id": str})
    pos = pd.read_csv(P["processed"] / "positions.csv.gz")
    prices = pd.read_csv(P["raw"] / "prices.csv")
    log = json.load(open(P["interim"] / "build_log.json"))
    L = ["# Validation report", ""]

    # 1 ---------------------------------------------------------------------
    L += ["## 1. Row accounting", "", "| item | count |", "|---|---|"]
    L += [f"| {k} | {v:,} |" if isinstance(v, int) else f"| {k} | {v:.4f} |" for k, v in log.items()]
    L += ["", f"Markets in sample: {len(markets)}; markets with fills: {fills['condition_id'].nunique()}.", ""]

    # 2 ---------------------------------------------------------------------
    tv = fills[fills["role"] == "taker"].groupby("condition_id")["usdc"].sum()
    rec = markets.set_index("condition_id")[["volume_gamma"]].join(tv.rename("taker_usdc"), how="inner")
    rec["ratio"] = rec["taker_usdc"] / rec["volume_gamma"]
    q = rec["ratio"].quantile([0.1, 0.5, 0.9])
    L += ["## 2. Volume reconciliation (our taker USDC / Gamma volumeNum)", "",
          f"10th / 50th / 90th percentile ratio: {q[0.1]:.2f} / {q[0.5]:.2f} / {q[0.9]:.2f}.",
          "A stable ratio across markets is what matters. Gamma's definition of volume is not",
          "documented precisely; a median near 1 (or near 0.5 if it counts both sides) means the",
          "pull is complete. Markets far from the median should be re-pulled and inspected.", ""]
    rec.sort_values("ratio").to_csv(P["output"] / "volume_reconciliation.csv")

    # 3 ---------------------------------------------------------------------
    if len(prices):
        e = ex[ex["role"] == "taker"][["condition_id", "timestamp", "p0"]].sort_values("timestamp")
        r = prices.rename(columns={"t": "timestamp", "p": "p_hist"}).sort_values("timestamp")
        e["timestamp"] = e["timestamp"].astype("int64"); r["timestamp"] = r["timestamp"].astype("int64")
        m = pd.merge_asof(e, r, on="timestamp", by="condition_id", direction="nearest",
                          tolerance=cfg["collection"]["price_fidelity_min"] * 60)
        d = (m["p0"] - m["p_hist"]).abs().dropna()
        L += ["## 3. Price consistency (|fill p0 - public history|)", "",
              f"Matched {len(d):,} executions. Median abs diff {d.median():.4f}; "
              f"90th pct {d.quantile(0.9):.4f}. Large gaps point to token-mapping errors.", ""]

    # 4 ---------------------------------------------------------------------
    agree = []
    for cid, g in ex[ex["role"] == "taker"].sort_values("timestamp").groupby("condition_id"):
        tr = tick_rule(g["p0"].to_numpy())
        ok = ~np.isnan(tr)
        agree.append((ok.sum(), (tr[ok] == g["dir0"].to_numpy()[ok]).sum()))
    n, k = map(sum, zip(*agree)) if agree else (0, 0)
    L += ["## 4. Tick-rule vs on-chain signing", "",
          f"Tick rule agrees with the on-chain taker direction on {k / max(n, 1):.1%} of {n:,} executions.",
          "This is why trades are signed from on-chain taker side, not inferred from the price feed.", ""]

    # 5 ---------------------------------------------------------------------
    st = fills.groupby("condition_id").apply(
        lambda g: g.loc[g.self_trade == 1, "usdc"].sum() / g["usdc"].sum(), include_groups=False)
    L += ["## 5. Self-trading share of volume by market", "",
          f"Median {st.median():.2%}, 90th pct {st.quantile(0.9):.2%}, 99th pct {st.quantile(0.99):.2%}, "
          f"max {st.max():.2%}. Pooled: {log['self_trade_usdc_share']:.2%}.", ""]

    # 6 ---------------------------------------------------------------------
    L += ["## 6. Position integrity", "",
          f"{pos['incomplete'].mean():.1%} of wallet-market positions end with negative token inventory",
          "(shares obtained outside the order book: splits, merges, transfers). These are kept in the",
          "data but excluded from skill estimation.", ""]

    # 7 ---------------------------------------------------------------------
    rng = np.random.default_rng(cfg["sample"]["seed"])
    busy = pos.groupby("wallet")["condition_id"].nunique()
    pick = rng.choice(busy[busy >= 3].index.to_numpy(), size=min(5, (busy >= 3).sum()), replace=False)
    L += ["## 7. Hand spot-checks", "",
          "Open each profile, find the listed markets, and confirm direction and approximate size.", ""]
    for w in pick:
        L.append(f"- https://polymarket.com/profile/{w}")
        for r in pos[pos.wallet == w].head(3).itertuples():
            L.append(f"    - {r.condition_id[:12]}... dir={r.direction:+d} peak_shares={r.peak_shares:,.0f} "
                     f"pnl={r.pnl:,.2f}")
    (P["output"] / "validation_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
