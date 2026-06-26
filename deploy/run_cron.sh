#!/bin/bash
# AI 财务助手 — cron 执行包装
# 用法: crontab -e 添加:
#   45 14 * * 1-5 /mnt/data/finance-assistant/deploy/run_cron.sh --auto
#   55 14 * * 1-5 /mnt/data/finance-assistant/deploy/run_cron.sh --alert

export PYTHONIOENCODING=utf-8
export NO_PROXY=*
export HOME=/home/mote
export PATH="$HOME/.local/bin:$PATH"

# SSH agent
[ -z "$SSH_AUTH_SOCK" ] && eval "$(ssh-agent -s)" 2>/dev/null

cd /home/mote/finance-assistant || exit 1

DATE=$(date '+%Y-%m-%d %H:%M')
echo "[$DATE] Starting $*" >> /home/mote/finance-assistant/cron.log

python3 scripts/auto_runner.py "$@" >> /home/mote/finance-assistant/cron.log 2>&1

CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M')] Exit $CODE" >> /home/mote/finance-assistant/cron.log
