# Descriptive statistics

Markets: 80  |  wallets: 675  |  positions: 10,631  |  executions: 66,191

| Market level | n | mean | sd | p10 | median | p90 |
|---|---|---|---|---|---|---|
| Market lifetime (days) | 80.000 | 26.549 | 8.560 | 14.589 | 28.504 | 36.968 |
| Gamma volume (USDC) | 80.000 | 46,563.572 | 11,015.530 | 33,315.648 | 45,159.600 | 60,945.996 |
| Taker executions per market | 80.000 | 282.363 | 58.617 | 207.600 | 280.500 | 362.300 |
| Wallets per market | 80.000 | 132.887 | 29.462 | 93.900 | 131.000 | 175.100 |

| Position level | n | mean | sd | p10 | median | p90 |
|---|---|---|---|---|---|---|
| Holding period (hours) | 10,631.000 | 342.980 | 231.971 | 63.915 | 302.190 | 691.254 |
| Executions per position | 10,631.000 | 6.226 | 11.439 | 1.000 | 2.000 | 25.000 |
| Build executions per position | 10,631.000 | 3.980 | 5.956 | 1.000 | 2.000 | 13.000 |
| Build-size HHI | 10,631.000 | 0.723 | 0.302 | 0.202 | 0.816 | 1.000 |
| Entry point (share of market life) | 10,631.000 | 0.463 | 0.307 | 0.043 | 0.466 | 0.887 |
| Position volume (USDC) | 10,631.000 | 689.780 | 1,147.385 | 48.629 | 216.522 | 2,238.821 |
| ROI | 10,533.000 | 0.086 | 1.322 | -1.000 | 0.035 | 1.368 |
| Correct direction | 10,631.000 | 0.541 | 0.498 | 0.000 | 1.000 | 1.000 |

## Wallets by skill tercile (skill from estimation markets, behavior from evaluation markets)

| Skill tercile | wallets | skill_t | hit_rate_est | hit_rate_eval | vw_life | late_share | markout_res | build_exec | build_hhi | holding_h |
|---|---|---|---|---|---|---|---|---|---|---|
| low | 187.000 | -1.496 | 0.339 | 0.505 | 0.519 | 0.115 | -0.009 | 1.632 | 0.834 | 340.843 |
| mid | 186.000 | -0.293 | 0.522 | 0.524 | 0.512 | 0.075 | 0.006 | 2.140 | 0.789 | 331.752 |
| high | 185.000 | 0.753 | 0.731 | 0.540 | 0.531 | 0.108 | 0.012 | 2.905 | 0.729 | 327.194 |

hit_rate_eval > hit_rate of low tercile is the out-of-sample check that the skill label
means something: if skill does not persist across market sets, the label is noise.

## Preliminary test (no controls)

Late = last 10% of market life. Sample: 9,840 taker executions by skill-labeled wallets in 40 evaluation markets; SEs clustered by market.

| markout_res | coef | se | t |
|---|---|---|---|
| const | 0.031 | 0.010 | 3.058 |
| high | 0.053 | 0.014 | 3.748 |
| late | -0.032 | 0.015 | -2.215 |
| high_x_late | -0.007 | 0.023 | -0.296 |

high_x_late > 0: high-skill wallets' late trades are more informative than their early
trades, beyond the general late-trading effect. Treat as descriptive until Milestone 2.
