# Validation report

## 1. Row accounting

| item | count |
|---|---|
| taker_rows | 308,681 |
| all_rows | 792,709 |
| maker_rows | 484,028 |
| rows_unknown_token | 0 |
| rows_bad_price_or_size | 0 |
| markets_without_trades | 0 |
| fills_rows | 792,709 |
| self_trade_rows | 0 |
| self_trade_usdc_share | 0.0000 |

Markets in sample: 229; markets with fills: 229.

## 2. Volume reconciliation (our taker USDC / Gamma volumeNum)

10th / 50th / 90th percentile ratio: 0.30 / 0.49 / 0.62.
A stable ratio across markets is what matters. Gamma's definition of volume is not
documented precisely; a median near 1 (or near 0.5 if it counts both sides) means the
pull is complete. Markets far from the median should be re-pulled and inspected.

## 3. Price consistency (|fill p0 - public history|)

Matched 307,509 executions. Median abs diff 0.0050; 90th pct 0.0250. Large gaps point to token-mapping errors.

## 4. Tick-rule vs on-chain signing

Tick rule agrees with the on-chain taker direction on 73.2% of 308,389 executions.
This is why trades are signed from on-chain taker side, not inferred from the price feed.

## 5. Self-trading share of volume by market

Median 0.00%, 90th pct 0.00%, 99th pct 0.00%, max 0.00%. Pooled: 0.00%.

## 6. Position integrity

3.1% of wallet-market positions end with negative token inventory
(shares obtained outside the order book: splits, merges, transfers). These are kept in the
data but excluded from skill estimation.

## 7. Hand spot-checks

Open each profile, find the listed markets, and confirm direction and approximate size.

- https://polymarket.com/profile/0xc7fbc818c08e6984542749d351e73578038f8eb0
    - 0x1b56e46dba... dir=+1 peak_shares=150 pnl=-30.45
    - 0x26a6c7e4a9... dir=+1 peak_shares=508 pnl=167.47
    - 0x50456e2e7c... dir=+1 peak_shares=140 pnl=43.40
- https://polymarket.com/profile/0x70b5d001801b207872e105bee8a773e5613d334a
    - 0x1883b6810f... dir=-1 peak_shares=6 pnl=-2.00
    - 0x1b56e46dba... dir=+1 peak_shares=4 pnl=1.57
    - 0xcdee0148ae... dir=-1 peak_shares=3 pnl=0.90
- https://polymarket.com/profile/0xa74d18ea2cfbbc54b83d1aada3a8810bb5568daf
    - 0x1883b6810f... dir=+1 peak_shares=3 pnl=0.94
    - 0xae4336dbd5... dir=+1 peak_shares=6 pnl=-2.00
    - 0xcdee0148ae... dir=-1 peak_shares=3 pnl=0.86
- https://polymarket.com/profile/0x16766b561c2c47f966b5f08acf2021716fcdab19
    - 0x6d6088a604... dir=-1 peak_shares=10 pnl=-5.14
    - 0x92485347d2... dir=+1 peak_shares=10 pnl=-4.95
    - 0x99067da61a... dir=-1 peak_shares=9 pnl=-5.36
- https://polymarket.com/profile/0x6f03f248371549561686dce11355687324c34b88
    - 0x016a4bca73... dir=-1 peak_shares=2 pnl=0.08
    - 0x1cf96ff28b... dir=-1 peak_shares=2 pnl=0.07
    - 0x1daa856d50... dir=+1 peak_shares=2 pnl=0.07
