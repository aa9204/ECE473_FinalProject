# Sample construction

Gamma query: closed markets, end date 2026-05-01T00:00:00Z to 2026-09-30T23:59:59Z, volume 50,000-3,000,000 USDC -> 79174 markets (79174 parseable).

| outcome | markets |
|---|---|
| lifetime < 3d | 50273 |
| no topic match | 25798 |
| excluded keyword/tag | 1325 |
| not scheduled | 1010 |
| not cleanly resolved | 270 |
| KEPT | 229 |
| not drawn (over 150 per topic) | 142 |
| not drawn (over 3 per event) | 127 |

Kept, by topic:

- politics: 150
- economics: 79

Kept, by exchange version:

- v1: 229
