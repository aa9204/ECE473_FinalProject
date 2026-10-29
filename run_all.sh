#!/usr/bin/env bash
# Rebuild everything from scratch.
#   ./run_all.sh          real data (needs internet; steps 1-3 take a while)
#   ./run_all.sh sim      simulated data in ./sim (offline smoke test)
set -euo pipefail
cd "$(dirname "$0")"

if [[ "${1:-}" == "sim" ]]; then
  export PM_DATA_ROOT="$PWD/sim"
  python src/simulate.py
else
  python src/s01_collect_markets.py
  python src/s02_collect_trades.py
  python src/s03_collect_prices.py
fi

python src/s05_build_fills.py
python src/s06_build_positions.py
python src/s07_build_measures.py
python src/s08_validate.py
python src/s09_descriptives.py
echo "Done. See ${PM_DATA_ROOT:-.}/output/"
