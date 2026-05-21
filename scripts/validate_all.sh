#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Repo root: ${REPO_ROOT}"
cd "${REPO_ROOT}"

make verify
python3 -m src.data_sources --check
python3 -m src.monthly_picks --generate --top-n 5
python3 -m src.track_record --monthly-picks
make dashboard-smoke
