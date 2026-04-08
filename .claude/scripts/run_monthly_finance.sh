#!/usr/bin/env bash
# Monthly finance report runner for cron/launchd (macOS/Linux)
# Schedule: 1st of each month at 8 AM
# cron example: 0 8 1 * * /path/to/run_monthly_finance.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Run monthly finance report using UV
uv run python memory_monthly_finance.py

# Log the run
echo "$(date '+%Y-%m-%d %H:%M:%S') - Monthly finance report completed" >> monthly_finance_runs.log
