#!/usr/bin/env bash
# Mesh Barista harness: firmware simulation (always) + dashboard browser test (if Playwright is installed).
set -euo pipefail
cd "$(dirname "$0")"
g++ -std=c++17 -O1 -Istubs -o /tmp/mb_sim test.cpp
/tmp/mb_sim
if python3 -c "import playwright" 2>/dev/null; then python3 pagetest.py
else echo "SKIP pagetest.py (pip install playwright && playwright install chromium)"; fi
