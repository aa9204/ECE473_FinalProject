# Milestone 1: Polymarket wallet-level dataset and behavioral measures

This repo builds, from public data only, a wallet-level dataset for a defined
sample of resolved Polymarket markets, and the behavioral measures the project
needs: trade sequences, positions, holding periods, timing, trade sizes,
forecasting accuracy, order splitting, and a held-out skill label. It ends with
validation checks, descriptive tables, six figures, and the preliminary test.

```
config.yaml              the sample definition and every tuning choice
run_all.sh               rebuilds everything (./run_all.sh  or  ./run_all.sh sim)
src/
  common.py              config, HTTP with retries, field normalization
  s01_collect_markets.py Gamma API  -> the market sample
  s02_collect_trades.py  Data API   -> every fill, taker side + maker side
  s03_collect_prices.py  CLOB API   -> public price history
  s04_record_books.py    CLOB API   -> live order-book snapshots (optional)
  s05_build_fills.py     signed fills, maker/taker roles, self-trade flags
  s06_build_positions.py executions and wallet x market positions
  s07_build_measures.py  held-out skill, timing, markouts, wallet summary
  s08_validate.py        validation report
  s09_descriptives.py    tables, figures, preliminary regression
  simulate.py            fake data with the same shape, for offline testing
DATA_DICTIONARY.md       every column of every table
```

---

## Step 0 — Set up (10 minutes)

```bash
cd polymarket-m1
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then make sure the code works on your machine *before* touching the network:

```bash
./run_all.sh sim
```

This writes fake markets into `sim/` (kept separate from real data) and runs
steps 5–9 on them. You should see the validation report and descriptive
tables print, and six PNGs in `sim/output/`. The simulator plants a known
pattern (informed wallets trade the right way and split orders), and the
pipeline should recover it: the high-skill tercile has higher markouts and
more build executions. **Nothing in `sim/` is a result.** Don't put it in your
write-up.

## Step 1 — Define the sample (`config.yaml`, then `s01`)

Open `config.yaml` and decide the sample. Defaults: binary markets whose end
date is May 1 to Sept 30, 2026, with $50k–$3M lifetime volume, that resolved
cleanly to 1/0, with a random draw of at most 300 markets (seed 42).

**Do a pilot first.** Set `max_markets: 20` and run:

```bash
python src/s01_collect_markets.py
```

Open `data/interim/markets.csv`. Check that the questions look like the
markets you meant, that `winning_index` is 0 or 1, and that `resolution_ts` is
after `start_ts`. Write the inclusion rule into your memo exactly as it is in
`config.yaml`. That rule *is* your sample definition.

Two things to decide and state:
* **The v2 cutover.** Polymarket moved to exchange v2 on April 28, 2026. The
  `version` column shows which markets are which. Either keep both and say so,
  or narrow the dates to one regime.
* **Category.** Pooling sports, politics and crypto mixes very different
  information structures. Nechepurenko's point applies here. Consider adding a
  category filter or reporting results by category.

## Step 2 — Pull fills (`s02`)

```bash
python src/s02_collect_trades.py
```

For each market this calls `GET https://data-api.polymarket.com/v2/trades`
twice:
* `taker_only=true` gives one row per fill on the taker's side. The taker's
  `side` is the real on-chain direction of the trade. This is how you "sign
  trades from on-chain fills" (Dubach) without guessing from prices.
* `taker_only=false` adds the maker rows. The maker is whoever's resting order
  was hit, which is your "resting liquidity as market maker."

Raw responses go to `data/raw/trades/` untouched. The script is restartable:
it skips finished markets, so if it dies, just run it again.

**Sanity check after the pilot.** Open one `__taker.jsonl` file and look at
the first line. `common.normalize_trade` expects fields like `proxy_wallet`,
`side`, `asset`, `size`, `price`, `timestamp` and `transaction_hash` (snake
or camel case both work). If the API returns a field under a different name,
add that name to the matching `_pick(...)` call in `common.py`. That one
function is the only place field names live.

## Step 3 — Pull price history (`s03`)

```bash
python src/s03_collect_prices.py
```

Calls `GET https://clob.polymarket.com/prices-history` for outcome 0 of each
market at 10-minute resolution. This is the reference path for 1h and 24h
markouts, and an independent check on fill prices.

## Step 3b — Order books (optional, read this)

There is no public endpoint for **historical** order books. The API only
returns the book as it is right now (Dubach recorded his own archive). So the
"order-book data" in the plan comes from fills (both sides of every match)
plus Gamma's liquidity figure. If you want true book depth and spreads as
liquidity controls for Milestone 2, start recording now on markets that are
still open and will resolve before your deadline:

```bash
python src/s04_record_books.py <token_id> <token_id> ...   # run every 5 min via cron
```

Say this in the memo. It's a data limitation, not a mistake.

## Step 4 — Build everything (`s05`–`s07`)

```bash
python src/s05_build_fills.py
python src/s06_build_positions.py
python src/s07_build_measures.py
```

What each step does and why:

**s05: fills.** Maker rows are the rows in the "all" pull that aren't in the
taker pull, matched one-for-one. Every fill gets `dir0` and `p0`: its
direction and price expressed in terms of outcome 0. This lets you pool
"buy Yes" with "sell No," which are economically the same bet. Self-trades
are flagged when a wallet is on both sides of a transaction, or buys and
sells the same token in one transaction.

**s06: executions and positions.** Fills from one transaction are merged into
one *execution*. A single order that sweeps three resting orders is one
decision, not three, so it must not count as splitting. Positions (wallet ×
market) get direction, entry and exit, holding period, PnL, whether the
direction was correct, and the splitting measures:
* `n_build_exec`: how many executions built the position
* `build_hhi`: concentration of execution sizes (1 = all at once)
* `max_exec_share`: the largest slice as a share of the total
* `median_gap_min`: typical spacing between slices

**s07: skill and measures.** Markets are split by resolution date. Skill is
estimated on the earlier half and behavior is measured on the later half.
This keeps it from being circular: if skill and timing came from the same
trades, skilled wallets would "trade informatively" by construction. The skill
measure is `skill_t`, the mean per-market ROI divided by its standard error,
for wallets with at least 5 markets, cut into terciles. Trade informativeness
is the markout, the price move in the trade's direction:
`dir0 × (price later − price paid)`, at 1h, 24h and resolution.

## Step 5 — Validate (`s08`)

```bash
python src/s08_validate.py      # -> output/validation_report.md
```

How to read each check:

| check | what you want to see | if not |
|---|---|---|
| Volume reconciliation | our/Gamma ratio stable across markets | re-pull the outlier markets |
| Price consistency | fill p0 within ~1 cent of public history | token mapping is wrong for that market |
| Tick rule vs on-chain | roughly 60% agreement (Dubach) | report it: this justifies on-chain signing |
| Self-trade share | about 1% median with a heavy tail (Dubach) | inspect the top markets by hand |
| Incomplete positions | a minority, mostly makers | these wallets mint/merge shares outside the book |
| Spot checks | profile pages match direction/size | debug the wallet in `fills.csv.gz` |

On "incomplete" positions: market makers often create Yes+No pairs by
splitting USDC instead of buying in the book, and those splits aren't trades.
Their PnL from trades alone is wrong, so they're excluded from skill
estimation. If it turns out to matter, `/v2/activity?user=<wallet>&type=SPLIT,MERGE`
can recover those flows later.

## Step 6 — Descriptives and the preliminary test (`s09`)

```bash
python src/s09_descriptives.py   # -> output/descriptives.md, table_*.csv, fig*.png
```

* Tables 1–3: market, position and wallet-by-skill statistics
* Fig 1–4: activity concentration, holding periods, executions per position,
  and when volume arrives
* **Fig 5: markout by time-to-resolution × skill tercile.** This is the
  preliminary answer to "do skilled traders trade more informatively near
  resolution"
* Fig 6: order splitting by skill tercile
* Table 5: `markout_res ~ high + late + high×late`, with SEs clustered by
  market. The interaction is the coefficient of interest. No controls yet;
  those come in Milestone 2

Also check `hit_rate_eval` in Table 3. If the high tercile isn't more accurate
than the low tercile on the *evaluation* markets, the skill label isn't
persistent, and you need to say so before interpreting anything else.

## Step 7 — What to hand in

1. **This repo**, with your final `config.yaml`. Someone else should be able
   to run `./run_all.sh` and get your tables.
2. **The data**: `data/interim/markets.csv` and everything in
   `data/processed/`, plus `DATA_DICTIONARY.md`. If the files are too big,
   submit the market list and the processed tables. Raw data can be rebuilt.
3. **A 4–6 page memo**:
   1. Sample and data construction (Steps 1–3, including the order-book limitation)
   2. Measure definitions (the s05–s07 descriptions above, in your words)
   3. Validation (paste and discuss `validation_report.md`)
   4. Descriptives (Tables 1–3, Figs 1–4, 6)
   5. Preliminary result (Fig 5 and Table 5, labeled preliminary)
   6. Issues and next steps for Milestone 2

## Known limitations to state up front

* Historical order books aren't public, so liquidity is proxied unless you record books forward.
* Splits, merges and transfers aren't trades, so some positions are incomplete (flagged).
* The skill split is by calendar time. Wallets that only trade late in the window can't be labeled.
* Proxy wallets aren't people. One trader can run several wallets, and nothing here links them.
* The theory assumes an automated market maker. Here the maker side is resting limit orders, as your proposal says.
