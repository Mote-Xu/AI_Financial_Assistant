#!/bin/bash
# 每日情报简报 — 用于 Linux cron
# 用法:
#   bash deploy/briefing.sh           # 早间全量简报
#   bash deploy/briefing.sh --midday  # 午间补充（仅 act 级）

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

PYTHON=python3

MIDDAY_FLAG=""
if [ "$1" = "--midday" ]; then
    MIDDAY_FLAG="--midday"
fi

$PYTHON scripts/auto_runner.py --briefing $MIDDAY_FLAG >> "$SCRIPT_DIR/logs/briefing.log" 2>&1
