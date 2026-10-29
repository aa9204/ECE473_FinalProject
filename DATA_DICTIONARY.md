# Data dictionary

All timestamps are Unix seconds (UTC). "Outcome 0" is the first listed outcome (usually "Yes").

## data/interim/markets.csv — the sample (one row per market)
| column | meaning |
|---|---|
| condition_id | market identifier on-chain (join key everywhere) |
| market_id, slug, question, category, event_slug | Gamma metadata |
| neg_risk | market belongs to a multi-outcome (neg-risk) event |
| version | Polymarket exchange version (v1 / v2; v2 launched 2026-04-28) |
| token_0, token_1 | outcome token ids for outcome 0 / outcome 1 |
| winning_index | 0 or 1, the outcome that paid $1 |
| start_ts, end_ts, closed_ts | creation, scheduled end, actual close |
| resolution_ts | closed_ts if present, else end_ts |
| volume_gamma, liquidity_gamma | Gamma's lifetime volume and liquidity figures |

## data/processed/fills.csv.gz — one row per wallet-side of a fill
| column | meaning |
|---|---|
| tx_hash, timestamp | transaction and block time |
| wallet | proxy wallet address (lower-case) |
| role | taker (crossed the spread) or maker (resting order) |
| token_id, outcome_index | token traded and its outcome (0/1) |
| side, price, size, usdc | BUY/SELL of that token, price per share, shares, price × size |
| dir0 | +1 if the fill raises exposure to outcome 0, −1 otherwise |
| p0 | implied price of outcome 0 (price, or 1 − price for token 1) |
| token_won, outcome0 | 1 if this token paid; 1 if outcome 0 won |
| self_trade | 1 if the wallet was on both sides, or bought and sold the same token, in this tx |

## data/processed/executions.csv.gz — fills grouped by wallet × tx × token × side × role
Same direction/price fields as fills, plus `n_fills` (fills in the execution) and `signed0` (dir0 × shares). Self-trades excluded.

## data/processed/positions.csv.gz — one row per wallet × market
| column | meaning |
|---|---|
| direction | sign of outcome-0 exposure at its largest |
| peak_shares | largest absolute outcome-0 exposure |
| entry_ts, exit_ts, closed_out, holding_hours | first fill; last fill if closed out, else resolution |
| entry_life | entry time as share of market life (0 = open, 1 = resolution) |
| pnl, capital, roi | trading cash flow + payoff of shares held at resolution; gross USDC bought; pnl / capital |
| correct | direction matched the outcome |
| volume_usdc, taker_share | total USDC traded; share as taker |
| n_fills, n_exec, n_build_exec | fills; executions; executions that increased exposure |
| build_hhi | Herfindahl of build-execution sizes (1 = one shot) |
| max_exec_share | largest build execution / total built |
| median_gap_min, build_span_hours | spacing and duration of the build |
| incomplete | ended with negative token inventory (shares came from outside the book) |
| set | estimation or evaluation market (added in s07) |

## data/processed/wallet_skill.csv — skill from estimation-set markets
n_markets_est, pnl_est, capital_est, roi_pooled, roi_mean, roi_sd, hit_rate, **skill_t** (mean ROI / standard error), **skill_tercile** (low / mid / high).

## data/processed/trades_eval.csv.gz — evaluation-set taker executions
Execution fields plus: life, hours_to_res, life_bin, markout_1h, markout_24h, markout_res (dir0 × (outcome0 − p0)), skill_t, skill_tercile.

## data/processed/wallet_measures.csv — one row per wallet (evaluation set)
n_markets_eval, mean_n_build_exec, mean_build_hhi, mean_holding_hours, hit_rate_eval, pnl_eval, n_taker_exec, taker_usdc, vw_life (USDC-weighted timing), late_share (share of taker USDC in the last 10% of market life), vw_markout_res, plus the skill columns.
