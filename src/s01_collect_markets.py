"""Step 1 - Define the market sample from the Gamma API.

Usage:
  python src/s01_collect_markets.py              download, then filter
  python src/s01_collect_markets.py --from-raw   re-filter the saved download
                                                 (iterate on config.yaml for free)

Output:
  data/raw/markets_raw.jsonl        every market returned, untouched
  data/interim/markets.csv          the sample: one row per market
  data/interim/sample_audit.csv     EVERY candidate market with its topic,
                                    scheduled flag and the reason it was kept
                                    or dropped -> skim this after the pilot
  data/interim/tag_counts.csv       which event tags occur, to tune topics
  data/interim/sample_log.md        filter funnel for the memo

Filters, in order (all set in config.yaml):
  1. Gamma query: closed, end date in window, volume in [volume_min, volume_max]
  2. binary, resolved cleanly to 1/0
  3. lifetime >= min_lifetime_days
  4. topic: event tag or question keyword matches a configured topic
  5. scheduled resolution: question has no "by <date>" phrasing AND the market
     closed within scheduled_tolerance_hours of its scheduled end date (a
     market that closed much earlier was settled by an event, not a schedule)
  6. random draw of at most max_markets with a fixed seed
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

from common import GAMMA, get_json, load_config, write_table


def _parse_list(x):
    if x is None:
        return None
    if isinstance(x, list):
        return x
    try:
        return json.loads(x)
    except Exception:
        return None


def _ts(x):
    try:
        return pd.Timestamp(x).timestamp() if x else np.nan
    except Exception:
        return np.nan


def fetch_closed_markets(cfg, raw_path) -> list[dict]:
    """Cursor-paginated pull from /markets/keyset (plain /markets refuses
    offsets past ~2,000). Each page is appended to raw_path as it arrives, so
    an interrupted run keeps what it already downloaded."""
    s = cfg["sample"]
    params = {
        "closed": "true",
        "end_date_min": s["end_date_min"],
        "end_date_max": s["end_date_max"],
        "volume_num_min": s["volume_min"],
        "volume_num_max": s["volume_max"],
        "include_tag": "true",
        "limit": 100,
        "order": "endDate",
        "ascending": "true",
    }
    raw_path.write_text("")
    out, cursor = [], None
    while True:
        p = dict(params, after_cursor=cursor) if cursor else params
        resp = get_json(f"{GAMMA}/markets/keyset", p, sleep=cfg["collection"]["sleep"])
        if isinstance(resp, list):                      # defensive: bare list
            page, cursor = resp, None
        else:
            page = resp.get("markets") or resp.get("data") or []
            cursor = resp.get("next_cursor")
        with open(raw_path, "a") as f:
            for m in page:
                f.write(json.dumps(m) + "\n")
        out.extend(page)
        print(f"  fetched {len(out)} markets so far")
        if not cursor or not page:
            return out


def market_tags(m: dict) -> list[str]:
    """Tag slugs and labels from the market and its events, lower-cased."""
    tags = []
    for src in [m] + list(m.get("events") or []):
        for t in src.get("tags") or []:
            if isinstance(t, dict):
                tags += [str(t.get("slug") or ""), str(t.get("label") or "")]
            else:
                tags.append(str(t))
        for c in [src.get("category")] + [c.get("label") if isinstance(c, dict) else c
                                         for c in src.get("categories") or []]:
            if c:
                tags.append(str(c))
    return sorted({t.strip().lower() for t in tags if t and t.strip()})


def to_row(m: dict) -> dict | None:
    outcomes = _parse_list(m.get("outcomes"))
    prices = _parse_list(m.get("outcomePrices"))
    # V1 markets carry clobTokenIds (JSON string); V2 markets carry positionIds.
    tokens = _parse_list(m.get("clobTokenIds")) or _parse_list(m.get("positionIds"))
    if not outcomes or not prices or not tokens:
        return None
    prices = [float(p) for p in prices]
    winner = int(np.argmax(prices)) if max(prices) > 0.99 and min(prices) < 0.01 else None
    ev = (m.get("events") or [{}])[0]
    return {
        "condition_id": m["conditionId"],
        "market_id": m.get("id"),
        "slug": m.get("slug"),
        "question": m.get("question") or "",
        "category": m.get("category") or ev.get("category"),
        "tags": "|".join(market_tags(m)),
        "event_slug": ev.get("slug"),
        "neg_risk": bool(ev.get("negRisk", False)),
        "version": m.get("version") or "v1",
        "n_outcomes": len(outcomes),
        "outcome_0": outcomes[0],
        "outcome_1": outcomes[1] if len(outcomes) > 1 else None,
        "token_0": str(tokens[0]),
        "token_1": str(tokens[1]) if len(tokens) > 1 else None,
        "winning_index": winner,
        "start_ts": _ts(m.get("startDate") or m.get("createdAt")),
        "end_ts": _ts(m.get("endDate")),
        "closed_ts": _ts(m.get("closedTime")),
        "volume_gamma": float(m.get("volumeNum") or 0),
        "liquidity_gamma": float(m.get("liquidityNum") or 0),
    }


def assign_topic(row, topics: dict) -> str | None:
    tags = set(row["tags"].split("|")) if row["tags"] else set()
    for name, spec in topics.items():
        if tags & {t.lower() for t in spec.get("tags", [])}:
            return name
    for name, spec in topics.items():
        if any(re.search(k, row["question"], re.I) for k in spec.get("keywords", [])):
            return name
    return None


def apply_filters(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Annotate every candidate with flags and a single drop reason."""
    s = cfg["sample"]
    df = df.copy()
    df["resolution_ts"] = df["closed_ts"].fillna(df["end_ts"])
    df["lifetime_days"] = (df["resolution_ts"] - df["start_ts"]) / 86400
    df["topic"] = df.apply(assign_topic, axis=1, topics=s.get("topics") or {})

    by_date = df["question"].apply(lambda q: any(re.search(p, q, re.I) for p in s.get("by_date_patterns", [])))
    early_h = (df["end_ts"] - df["closed_ts"]) / 3600            # hours closed before schedule
    on_time = early_h.isna() | (early_h.abs() <= s.get("scheduled_tolerance_hours", 48))
    df["by_date_phrase"] = by_date.astype(int)
    df["closed_hours_early"] = early_h.round(1)
    df["scheduled"] = (~by_date & on_time).astype(int)

    tagsets = df["tags"].fillna("").apply(lambda t: set(t.split("|")) - {""})
    ex_tags = {t.lower() for t in s.get("exclude_tags") or []}
    req_tags = {t.lower() for t in s.get("require_any_tags") or []}
    excluded = df["question"].apply(
        lambda q: any(re.search(p, q, re.I) for p in s.get("exclude_keywords") or [])) | \
        tagsets.apply(lambda ts: bool(ts & ex_tags))
    missing_req = tagsets.apply(lambda ts: bool(req_tags) and not (ts & req_tags))

    reason = pd.Series("", index=df.index)
    checks = [
        ("not binary", (df["n_outcomes"] != 2) if s.get("binary_only", True) else pd.Series(False, index=df.index)),
        ("not cleanly resolved", df["winning_index"].isna()),
        ("bad timestamps", ~(df["resolution_ts"] > df["start_ts"])),
        (f"lifetime < {s.get('min_lifetime_days', 0)}d", df["lifetime_days"] < s.get("min_lifetime_days", 0)),
        ("no topic match", df["topic"].isna() if s.get("topics") else pd.Series(False, index=df.index)),
        ("excluded keyword/tag", excluded),
        ("missing required tag", missing_req),
        ("not scheduled", (df["scheduled"] == 0) if s.get("require_scheduled") else pd.Series(False, index=df.index)),
    ]
    for label, mask in checks:
        reason = reason.mask((reason == "") & mask.fillna(True), label)
    df["drop_reason"] = reason
    return df


def main():
    cfg = load_config()
    s = cfg["sample"]
    raw_path = cfg["paths"]["raw"] / "markets_raw.jsonl"
    I = cfg["paths"]["interim"]

    if "--from-raw" in sys.argv:
        markets = [json.loads(l) for l in open(raw_path) if l.strip()]
        print(f"Re-filtering {len(markets)} saved markets")
    else:
        print("Querying Gamma for closed markets...")
        markets = fetch_closed_markets(cfg, raw_path)

    rows = [r for r in (to_row(m) for m in markets) if r]
    df = pd.DataFrame(rows).drop_duplicates("condition_id")
    df = apply_filters(df, cfg)

    # Tag counts among markets that passed every filter: use these to choose
    # require_any_tags / exclude_tags.
    passed = df[df["drop_reason"] == ""]
    pc = Counter(t for ts in passed["tags"].fillna("") for t in ts.split("|") if t)
    pd.DataFrame(pc.most_common(), columns=["tag", "markets"]).to_csv(I / "tag_counts_passed.csv", index=False)

    # Draw the sample from the survivors: shuffle once with the seed, then
    # apply the per-event, per-topic and overall caps in that random order.
    pool = passed.sample(frac=1, random_state=s["seed"])
    cap_e, cap_t = s.get("max_per_event"), s.get("max_per_topic")
    if cap_e:
        ev = pool["event_slug"].fillna(pool["condition_id"])
        over = ev.groupby(ev).cumcount() >= cap_e
        df.loc[pool.index[over.to_numpy()], "drop_reason"] = f"not drawn (over {cap_e} per event)"
        pool = pool[~over.to_numpy()]
    if cap_t:
        over = pool.groupby("topic").cumcount() >= cap_t
        df.loc[pool.index[over.to_numpy()], "drop_reason"] = f"not drawn (over {cap_t} per topic)"
        pool = pool[~over.to_numpy()]
    over = pd.Series(np.arange(len(pool)) >= s["max_markets"], index=pool.index)
    df.loc[over[over].index, "drop_reason"] = "not drawn (over max_markets)"
    df["kept"] = (df["drop_reason"] == "").astype(int)

    audit_cols = ["kept", "drop_reason", "topic", "scheduled", "by_date_phrase", "closed_hours_early",
                  "lifetime_days", "volume_gamma", "question", "tags", "condition_id"]
    write_table(df.sort_values(["kept", "topic", "question"], ascending=[False, True, True])[audit_cols],
                I / "sample_audit.csv")

    tag_counts = Counter(t for ts in df["tags"] for t in ts.split("|") if t)
    pd.DataFrame(tag_counts.most_common(), columns=["tag", "markets"]).to_csv(I / "tag_counts.csv", index=False)

    sample = df[df["kept"] == 1].sort_values("resolution_ts").reset_index(drop=True)
    sample["winning_index"] = sample["winning_index"].astype(int)
    write_table(sample.drop(columns=["drop_reason", "kept"]), I / "markets.csv")

    # Funnel for the memo.
    funnel = df["drop_reason"].replace("", "KEPT").value_counts()
    log = ["# Sample construction", "",
           f"Gamma query: closed markets, end date {s['end_date_min']} to {s['end_date_max']}, "
           f"volume {s['volume_min']:,}-{s['volume_max']:,} USDC -> {len(markets)} markets "
           f"({len(df)} parseable).", "",
           "| outcome | markets |", "|---|---|"] + [f"| {k} | {v} |" for k, v in funnel.items()]
    log += ["", "Kept, by topic:", ""] + [f"- {k}: {v}" for k, v in sample["topic"].value_counts().items()]
    log += ["", "Kept, by exchange version:", ""] + [f"- {k}: {v}" for k, v in sample["version"].value_counts().items()]
    (I / "sample_log.md").write_text("\n".join(log) + "\n")
    print("\n".join(log))
    print("\nNext: skim data/interim/sample_audit.csv (kept rows first) and data/interim/tag_counts.csv")


if __name__ == "__main__":
    main()