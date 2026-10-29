# Validation report

## 1. Row accounting

| item | count |
|---|---|
| taker_rows | 23,033 |
| all_rows | 69,105 |
| maker_rows | 46,072 |
| rows_unknown_token | 0 |
| rows_bad_price_or_size | 12 |
| markets_without_trades | 0 |
| fills_rows | 69,093 |
| self_trade_rows | 890 |
| self_trade_usdc_share | 0.0151 |

Markets in sample: 80; markets with fills: 80.

## 2. Volume reconciliation (our taker USDC / Gamma volumeNum)

10th / 50th / 90th percentile ratio: 0.96 / 1.00 / 1.04.
A stable ratio across markets is what matters. Gamma's definition of volume is not
documented precisely; a median near 1 (or near 0.5 if it counts both sides) means the
pull is complete. Markets far from the median should be re-pulled and inspected.

## 3. Price consistency (|fill p0 - public history|)

Matched 22,589 executions. Median abs diff 0.0060; 90th pct 0.0096. Large gaps point to token-mapping errors.

## 4. Tick-rule vs on-chain signing

Tick rule agrees with the on-chain taker direction on 57.9% of 22,508 executions.
This is why trades are signed from on-chain taker side, not inferred from the price feed.

## 5. Self-trading share of volume by market

Median 1.10%, 90th pct 2.83%, 99th pct 5.51%, max 7.33%. Pooled: 1.51%.

## 6. Position integrity

12.0% of wallet-market positions end with negative token inventory
(shares obtained outside the order book: splits, merges, transfers). These are kept in the
data but excluded from skill estimation.

## 7. Hand spot-checks

Open each profile, find the listed markets, and confirm direction and approximate size.

- https://polymarket.com/profile/0xb00000000000000000000000000000000001cc
    - 0x0000000000... dir=+1 peak_shares=660 pnl=-182.32
    - 0x0000000000... dir=+1 peak_shares=775 pnl=-164.78
    - 0x0000000000... dir=+1 peak_shares=191 pnl=47.87
- https://polymarket.com/profile/0xb00000000000000000000000000000000000eb
    - 0x0000000000... dir=-1 peak_shares=60 pnl=13.29
    - 0x0000000000... dir=+1 peak_shares=2,879 pnl=-78.92
    - 0x0000000000... dir=+1 peak_shares=207 pnl=-68.71
- https://polymarket.com/profile/0xb000000000000000000000000000000000017c
    - 0x0000000000... dir=-1 peak_shares=445 pnl=-112.11
    - 0x0000000000... dir=-1 peak_shares=257 pnl=53.60
    - 0x0000000000... dir=-1 peak_shares=125 pnl=-50.60
- https://polymarket.com/profile/0xa000000000000000000000000000000000003b
    - 0x0000000000... dir=-1 peak_shares=2,126 pnl=680.56
    - 0x0000000000... dir=+1 peak_shares=1,921 pnl=1,150.47
    - 0x0000000000... dir=-1 peak_shares=4,256 pnl=-825.52
- https://polymarket.com/profile/0xb00000000000000000000000000000000000e8
    - 0x0000000000... dir=-1 peak_shares=334 pnl=24.80
    - 0x0000000000... dir=-1 peak_shares=164 pnl=35.70
    - 0x0000000000... dir=+1 peak_shares=283 pnl=-94.10
