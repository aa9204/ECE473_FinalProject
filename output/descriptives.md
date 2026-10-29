# Descriptive statistics

Markets: 229  |  wallets: 45,306  |  positions: 106,928  |  executions: 763,038

| Market level | n | mean | sd | p10 | median | p90 |
|---|---|---|---|---|---|---|
| Market lifetime (days) | 229.000 | 106.892 | 84.899 | 17.900 | 86.587 | 239.379 |
| Gamma volume (USDC) | 229.000 | 227,025.767 | 366,450.060 | 56,626.726 | 94,914.716 | 473,571.214 |
| Taker executions per market | 229.000 | 1,347.952 | 1,529.668 | 398.600 | 951.000 | 2,357.400 |
| Wallets per market | 229.000 | 466.934 | 391.387 | 183.800 | 357.000 | 824.400 |

| Position level | n | mean | sd | p10 | median | p90 |
|---|---|---|---|---|---|---|
| Holding period (hours) | 106,928.000 | 491.378 | 913.287 | 0.963 | 115.842 | 1,464.310 |
| Executions per position | 106,928.000 | 7.136 | 25.922 | 1.000 | 2.000 | 14.000 |
| Build executions per position | 106,928.000 | 4.793 | 17.641 | 1.000 | 1.000 | 9.000 |
| Build-size HHI | 106,928.000 | 0.749 | 0.334 | 0.199 | 1.000 | 1.000 |
| Entry point (share of market life) | 106,928.000 | 0.644 | 0.311 | 0.138 | 0.721 | 0.984 |
| Position volume (USDC) | 106,928.000 | 446.131 | 3,543.414 | 1.200 | 20.073 | 655.755 |
| ROI | 105,586.000 | -0.089 | 0.768 | -1.000 | 0.000 | 0.431 |
| Correct direction | 106,928.000 | 0.557 | 0.497 | 0.000 | 1.000 | 1.000 |

## Wallets by skill tercile (skill from estimation markets, behavior from evaluation markets)

| Skill tercile | wallets | skill_t | hit_rate_est | hit_rate_eval | vw_life | late_share | markout_res | build_exec | build_hhi | holding_h |
|---|---|---|---|---|---|---|---|---|---|---|
| low | 336.000 | -1.594 | 0.448 | 0.514 | 0.580 | 0.207 | 0.014 | 7.530 | 0.638 | 432.895 |
| mid | 351.000 | -0.040 | 0.546 | 0.551 | 0.600 | 0.265 | 0.012 | 5.909 | 0.652 | 637.451 |
| high | 245.000 | 1.354 | 0.605 | 0.546 | 0.659 | 0.319 | 0.011 | 6.849 | 0.666 | 435.142 |

hit_rate_eval > hit_rate of low tercile is the out-of-sample check that the skill label
means something: if skill does not persist across market sets, the label is noise.

## Preliminary test (no controls)

Late = last 10% of market life. Sample: 57,274 taker executions by skill-labeled wallets in 114 evaluation markets; SEs clustered by market.

| markout_res | coef | se | t |
|---|---|---|---|
| const | 0.002 | 0.012 | 0.151 |
| high | 0.020 | 0.018 | 1.114 |
| late | 0.022 | 0.012 | 1.821 |
| high_x_late | -0.026 | 0.017 | -1.496 |

high_x_late > 0: high-skill wallets' late trades are more informative than their early
trades, beyond the general late-trading effect. Treat as descriptive until Milestone 2.
