"""Step 9 - Descriptive statistics, plots, and the preliminary test.

Outputs in output/:
  descriptives.md                    summary tables + regression, ready to paste
  table_*.csv                        the same tables as CSV
  fig1_trades_per_wallet.png         ... fig6_splitting_by_skill.png

Preliminary test (Milestone 1, no controls yet):
  markout_res_i = a + b1*High_i + b2*Late_i + b3*High_i x Late_i + e_i
over evaluation-set taker executions of skill-labeled wallets, with standard
errors clustered by market.  b3 > 0 means high-skill wallets' trades are MORE
informative when placed close to resolution - the pattern the theory predicts.
Milestone 2 adds market/liquidity controls and held-out robustness.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import load_config

# Palette: one hue for single series; an ordinal blue ramp for skill terciles.
BLUE = "#2a78d6"
TERCILE = {"low": "#86b6ef", "mid": "#3987e5", "high": "#1c5cab"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e6e5df"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.bbox": "tight", "font.size": 10,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.titlesize": 11,
    "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED, "legend.frameon": False,
})


def ols_cluster(y, X, groups, names):
    """OLS with CR1 cluster-robust standard errors (no statsmodels needed)."""
    X = np.column_stack([np.ones(len(y)), X])
    names = ["const"] + names
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]))
    G = 0
    for g in np.unique(groups):
        idx = groups == g
        s = X[idx].T @ u[idx]
        meat += np.outer(s, s)
        G += 1
    n, k = X.shape
    c = G / (G - 1) * (n - 1) / (n - k)
    V = c * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    return pd.DataFrame({"coef": beta, "se": se, "t": beta / se}, index=names), n, G


def md_table(df: pd.DataFrame, fmt="{:,.3f}") -> str:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "" if pd.isna(v) else fmt.format(v))
    head = "| " + " | ".join([d.index.name or ""] + list(map(str, d.columns))) + " |"
    sep = "|" + "---|" * (len(d.columns) + 1)
    rows = ["| " + " | ".join([str(i)] + [str(v) for v in r]) + " |" for i, r in zip(d.index, d.values)]
    return "\n".join([head, sep] + rows)


def describe(s: pd.Series) -> dict:
    return {"n": int(s.notna().sum()), "mean": s.mean(), "sd": s.std(), "p10": s.quantile(0.1),
            "median": s.median(), "p90": s.quantile(0.9)}


def main():
    cfg = load_config()
    P = cfg["paths"]
    O = P["output"]
    markets = pd.read_csv(P["interim"] / "markets.csv")
    ex = pd.read_csv(P["processed"] / "executions.csv.gz", dtype={"token_id": str})
    pos = pd.read_csv(P["processed"] / "positions.csv.gz")
    tr = pd.read_csv(P["processed"] / "trades_eval.csv.gz", dtype={"token_id": str})
    wm = pd.read_csv(P["processed"] / "wallet_measures.csv")
    L = ["# Descriptive statistics", ""]

    # ---- Table 1: sample -------------------------------------------------
    life_days = (markets["resolution_ts"] - markets["start_ts"]) / 86400
    t1 = pd.DataFrame({
        "Market lifetime (days)": describe(life_days),
        "Gamma volume (USDC)": describe(markets["volume_gamma"]),
        "Taker executions per market": describe(ex[ex.role == "taker"].groupby("condition_id").size()),
        "Wallets per market": describe(pos.groupby("condition_id")["wallet"].nunique()),
    }).T
    t1.index.name = "Market level"
    t1.to_csv(O / "table_1_markets.csv")
    L += [f"Markets: {len(markets)}  |  wallets: {pos['wallet'].nunique():,}  |  "
          f"positions: {len(pos):,}  |  executions: {len(ex):,}", "", md_table(t1), ""]

    # ---- Table 2: positions ----------------------------------------------
    t2 = pd.DataFrame({
        "Holding period (hours)": describe(pos["holding_hours"]),
        "Executions per position": describe(pos["n_exec"]),
        "Build executions per position": describe(pos["n_build_exec"]),
        "Build-size HHI": describe(pos["build_hhi"]),
        "Entry point (share of market life)": describe(pos["entry_life"]),
        "Position volume (USDC)": describe(pos["volume_usdc"]),
        "ROI": describe(pos["roi"].clip(-1, 5)),
        "Correct direction": describe(pos["correct"]),
    }).T
    t2.index.name = "Position level"
    t2.to_csv(O / "table_2_positions.csv")
    L += [md_table(t2), ""]

    # ---- Table 3: wallets by skill tercile -------------------------------
    lab = wm[wm["skill_tercile"].isin(TERCILE)]
    t3 = lab.groupby("skill_tercile").agg(
        wallets=("wallet", "size"), skill_t=("skill_t", "median"),
        hit_rate_est=("hit_rate", "mean"), hit_rate_eval=("hit_rate_eval", "mean"),
        vw_life=("vw_life", "mean"), late_share=("late_share", "mean"),
        markout_res=("vw_markout_res", "mean"), build_exec=("mean_n_build_exec", "mean"),
        build_hhi=("mean_build_hhi", "mean"), holding_h=("mean_holding_hours", "median"),
    ).reindex(list(TERCILE))
    t3["wallets"] = t3["wallets"].astype(float)
    t3.index.name = "Skill tercile"
    t3.to_csv(O / "table_3_wallets_by_skill.csv")
    L += ["## Wallets by skill tercile (skill from estimation markets, behavior from evaluation markets)",
          "", md_table(t3), "",
          "hit_rate_eval > hit_rate of low tercile is the out-of-sample check that the skill label",
          "means something: if skill does not persist across market sets, the label is noise.", ""]

    # ---- Figures ---------------------------------------------------------
    # 1. trades per wallet
    fig, ax = plt.subplots(figsize=(6, 3.6))
    n_per = ex.groupby("wallet").size()
    bins = np.logspace(0, np.log10(max(n_per.max(), 10)), 30)
    ax.hist(n_per, bins=bins, color=BLUE, edgecolor="white", linewidth=1)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Executions per wallet (log)"); ax.set_ylabel("Wallets (log)")
    ax.set_title("Activity is highly concentrated")
    fig.savefig(O / "fig1_trades_per_wallet.png"); plt.close(fig)

    # 2. holding period
    fig, ax = plt.subplots(figsize=(6, 3.6))
    h = pos["holding_hours"].clip(lower=1 / 60)
    ax.hist(h, bins=np.logspace(np.log10(1 / 60), np.log10(h.max()), 40), color=BLUE,
            edgecolor="white", linewidth=1)
    ax.set_xscale("log"); ax.set_xlabel("Holding period, hours (log)"); ax.set_ylabel("Positions")
    ax.set_title("Holding periods")
    fig.savefig(O / "fig2_holding_period.png"); plt.close(fig)

    # 3. build executions per position
    fig, ax = plt.subplots(figsize=(6, 3.6))
    b = pos["n_build_exec"].clip(upper=30)
    ax.hist(b, bins=np.arange(0.5, 31.5, 1), color=BLUE, edgecolor="white", linewidth=1)
    ax.set_xlabel("Executions used to build the position (30 = 30+)"); ax.set_ylabel("Positions")
    ax.set_title("Order splitting: executions per position")
    fig.savefig(O / "fig3_build_executions.png"); plt.close(fig)

    # 4. taker volume by life bin
    edges = cfg["measures"]["life_bins"]
    order = [f"{a:.0%}–{b:.0%}" for a, b in zip(edges[:-1], edges[1:])]
    vol = tr.groupby("life_bin")["usdc"].sum().reindex(order)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.grid(axis="x", visible=False)
    ax.bar(range(len(vol)), vol / vol.sum(), color=BLUE, width=0.7)
    ax.set_xticks(range(len(vol)), order, rotation=0, fontsize=8)
    ax.set_xlabel("Share of market life elapsed"); ax.set_ylabel("Share of taker volume")
    ax.set_title("When taker volume arrives")
    fig.savefig(O / "fig4_volume_by_life.png"); plt.close(fig)

    # 5. markout by life bin x skill tercile (the preliminary result)
    lt = tr[tr["skill_tercile"].isin(TERCILE)].copy()
    lt["w"] = lt["markout_res"] * lt["usdc"]
    g = lt.groupby(["life_bin", "skill_tercile"]).agg(w=("w", "sum"), u=("usdc", "sum"), n=("w", "size"))
    g["vw_markout"] = g["w"] / g["u"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    x = np.arange(len(order))
    for j, t in enumerate(TERCILE):
        s = g.xs(t, level="skill_tercile")["vw_markout"].reindex(order) if t in g.index.get_level_values(1) else None
        if s is None:
            continue
        ax.plot(x, s.to_numpy(), marker="o", markersize=5, linewidth=2, color=TERCILE[t], label=f"{t} skill")
        ax.annotate(f"{t}", (x[-1], s.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK)
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.set_xticks(x, order, fontsize=8)
    ax.set_xlabel("Share of market life elapsed"); ax.set_ylabel("USDC-weighted markout to resolution")
    ax.set_title("Trade informativeness by timing and skill")
    ax.legend(loc="upper left", fontsize=8)
    fig.savefig(O / "fig5_markout_by_life_skill.png"); plt.close(fig)
    g.reset_index().to_csv(O / "table_4_markout_by_life_skill.csv", index=False)

    # 6. splitting by skill
    pe = pos.merge(wm[["wallet", "skill_tercile"]], on="wallet")
    pe = pe[pe["skill_tercile"].isin(TERCILE)]
    s6 = pe.groupby("skill_tercile")["n_build_exec"].agg(["mean", "sem", "size"]).reindex(list(TERCILE))
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.grid(axis="x", visible=False)
    xs = np.arange(len(s6))
    ax.bar(xs, s6["mean"], color=[TERCILE[t] for t in s6.index], width=0.6)
    ax.errorbar(xs, s6["mean"], yerr=1.96 * s6["sem"], fmt="none", ecolor=INK, elinewidth=1, capsize=4)
    for x_, (m_, n_) in zip(xs, s6[["mean", "size"]].to_numpy()):
        ax.annotate(f"{m_:.2f}\n(n={int(n_):,})", (x_, m_), xytext=(0, -26), textcoords="offset points",
                    ha="center", fontsize=8, color="white")
    ax.set_xticks(xs, [f"{t} skill" for t in s6.index])
    ax.set_ylabel("Mean build executions per position")
    ax.set_title("Order splitting by skill tercile (95% CI)")
    fig.savefig(O / "fig6_splitting_by_skill.png"); plt.close(fig)

    # ---- Preliminary regression -----------------------------------------
    late_cut = cfg["measures"]["life_bins"][-3]
    lt["high"] = (lt["skill_tercile"] == "high").astype(float)
    lt["late"] = (lt["life"] >= late_cut).astype(float)
    lt["high_x_late"] = lt["high"] * lt["late"]
    res, n, G = ols_cluster(lt["markout_res"].to_numpy(), lt[["high", "late", "high_x_late"]].to_numpy(),
                            lt["condition_id"].to_numpy(), ["high", "late", "high_x_late"])
    res.index.name = "markout_res"
    res.to_csv(O / "table_5_preliminary_regression.csv")
    L += ["## Preliminary test (no controls)", "",
          f"Late = last {1 - late_cut:.0%} of market life. Sample: {n:,} taker executions by "
          f"skill-labeled wallets in {G} evaluation markets; SEs clustered by market.", "",
          md_table(res), "",
          "high_x_late > 0: high-skill wallets' late trades are more informative than their early",
          "trades, beyond the general late-trading effect. Treat as descriptive until Milestone 2.", ""]

    (O / "descriptives.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
