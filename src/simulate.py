"""Simulated test data with the same shape as the real API pulls.

Writes, under $PM_DATA_ROOT (default ./sim):
  data/interim/markets.csv, data/raw/trades/*.jsonl, data/raw/prices.csv
i.e. exactly what steps 1-3 produce, so steps 5-9 can be tested offline.

A known pattern is planted - informed wallets trade in the direction of the
outcome, concentrate late, and split orders - so you can confirm the pipeline
recovers it.  NOTHING produced from this data is a finding.

Usage:  PM_DATA_ROOT=sim python src/simulate.py
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("PM_DATA_ROOT", str(Path(__file__).resolve().parents[1] / "sim"))

import numpy as np
import pandas as pd

from common import append_jsonl, load_config, write_table

rng = np.random.default_rng(7)
N_MKT, N_INFORMED, N_NOISE, N_MAKERS = 80, 60, 600, 15
T0 = pd.Timestamp("2026-05-01", tz="UTC").timestamp()


def wallet(i, kind):
    return f"0x{kind}{i:037x}"[:42]


def price_path(start, end, outcome):
    t = np.arange(start, end + 600, 600)
    life = (t - start) / (end - start)
    drift = 0.5 + (outcome - 0.5) * 0.9 * life ** 2
    noise = np.cumsum(rng.normal(0, 0.006, len(t)))
    noise -= noise[-1] * life  # pin the noise to zero at resolution
    return t, np.clip(drift + noise, 0.02, 0.98)


def main():
    cfg = load_config()
    P = cfg["paths"]
    tdir = P["raw"] / "trades"
    tdir.mkdir(parents=True, exist_ok=True)
    for f in tdir.glob("*"):
        f.unlink()

    informed = [wallet(i, "a") for i in range(N_INFORMED)]
    noise = [wallet(i, "b") for i in range(N_NOISE)]
    makers = [wallet(i, "c") for i in range(N_MAKERS)]

    mrows, prow = [], []
    for k in range(N_MKT):
        cid = f"0x{k:064x}"
        start = T0 + rng.uniform(0, 120) * 86400
        end = start + rng.uniform(10, 40) * 86400
        outcome0 = int(rng.random() < 0.5)
        tok = (str(10**20 + 2 * k), str(10**20 + 2 * k + 1))
        t, p = price_path(start, end, outcome0)
        prow.append(pd.DataFrame({"condition_id": cid, "t": t.astype(int), "p": p.round(4)}))

        def p_at(ts):
            return float(np.interp(ts, t, p))

        taker_rows, maker_rows = [], []
        tx_n = 0

        def emit(w, ts, direction, usdc_target, reduce=False):
            nonlocal tx_n
            tx_n += 1
            tx = f"0x{k:08x}{tx_n:056x}"
            p0 = float(np.clip(p_at(ts) + direction * rng.uniform(0.002, 0.01), 0.01, 0.99))
            # New exposure: BUY the token that pays in that direction
            # (Yes for +1, No for -1). Closing out: SELL the token held.
            held_dir = -direction if reduce else direction
            if held_dir > 0:
                token, oi, price = tok[0], 0, p0
            else:
                token, oi, price = tok[1], 1, 1 - p0
            side = "SELL" if reduce else "BUY"
            size = round(usdc_target / price, 2)
            row = dict(transaction_hash=tx, timestamp=int(ts), condition_id=cid, asset=token,
                       outcome_index=oi, outcome=["Yes", "No"][oi], proxy_wallet=w, side=side,
                       size=size, price=round(price, 4))
            taker_rows.append(row)
            # 1-3 resting orders absorb the taker order.
            parts = rng.dirichlet(np.ones(rng.integers(1, 4))) * size
            for q in parts:
                mk = rng.choice(makers)
                if rng.random() < 0.01:
                    mk = w  # self-trade
                maker_rows.append({**row, "proxy_wallet": mk, "side": "SELL" if side == "BUY" else "BUY",
                                   "size": round(float(q), 2)})

        life_len = end - start
        for w in rng.choice(informed, size=rng.integers(8, 20), replace=False):
            if rng.random() < 0.15:
                continue
            d = (1 if outcome0 else -1) if rng.random() < 0.78 else (-1 if outcome0 else 1)
            ts0 = start + rng.beta(5, 1.4) * life_len * 0.98
            n_ex = rng.integers(4, 15)
            total = rng.lognormal(7, 0.8)
            for s in rng.dirichlet(np.ones(n_ex)) * total:
                ts = min(ts0 + rng.exponential(1800), end - 60)
                ts0 = ts
                emit(w, ts, d, s)
        for w in rng.choice(noise, size=rng.integers(60, 160), replace=False):
            d = rng.choice([-1, 1])
            ts = start + rng.uniform(0, 0.98) * life_len
            total = rng.lognormal(5, 1.0)
            for s in rng.dirichlet(np.ones(rng.integers(1, 3))) * total:
                emit(w, ts, d, s)
                ts = min(ts + rng.exponential(600), end - 60)
            if rng.random() < 0.2:  # close out part of it later
                emit(w, min(ts + rng.uniform(1, 48) * 3600, end - 60), -d, total * 0.4, reduce=True)

        append_jsonl(taker_rows, tdir / f"{cid}__taker.jsonl")
        allr = taker_rows + maker_rows
        rng.shuffle(allr)
        append_jsonl(allr, tdir / f"{cid}__all.jsonl")
        (tdir / f"{cid}.done").touch()

        vol = sum(r["size"] * r["price"] for r in taker_rows)
        mrows.append(dict(condition_id=cid, market_id=k, slug=f"sim-market-{k}", question=f"Sim market {k}?",
                          category="sim", event_slug=None, neg_risk=False, version="v1", n_outcomes=2,
                          outcome_0="Yes", outcome_1="No", token_0=tok[0], token_1=tok[1],
                          winning_index=0 if outcome0 else 1, start_ts=start, end_ts=end, closed_ts=end,
                          volume_gamma=vol * rng.uniform(0.95, 1.05), liquidity_gamma=rng.uniform(1e3, 5e4),
                          resolution_ts=end))

    markets = pd.DataFrame(mrows).sort_values("resolution_ts")
    write_table(markets, P["interim"] / "markets.csv")
    write_table(pd.concat(prow), P["raw"] / "prices.csv")
    print(f"simulated {len(markets)} markets under {os.environ['PM_DATA_ROOT']}")


if __name__ == "__main__":
    main()
