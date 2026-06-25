# AI 财务助手 — Claude Code 项目

> Claude Code 交互层 + DeepSeek API 分析 + akshare 行情 + SQLite 存储
> 最后更新：2026-06-26

---

## 项目架构

```
AI_Financial_Assistant/
├── CLAUDE.md                   # ← 新会话自动加载
├── REQUIREMENTS.md             # 功能清单
├── GEMINI_PROMPT.md            # 外部 AI 项目总结
├── PRIVATE.md                  # 🔒 真实数据（gitignore）
├── .env                        # 🔒 API Keys（gitignore）
├── .gitignore
├── run_auto.bat                # 定时体检入口
├── run_alert.bat               # 每日预警入口
├── setup_old_pc.bat            # 老电脑一键部署
├── finance/
│   ├── assets.md               # 资产（当前为 John Doe 演示数据）
│   ├── income.md               # 收入支出
│   ├── insurance.md            # 保单
│   ├── liabilities.md          # 负债
│   ├── goals.md                # 目标
│   ├── history.csv             # [自动] 历史净值
│   ├── portfolio_snapshot.md   # [自动] 市值快照
│   ├── finance_data.db         # [自动] SQLite 数据库（gitignore）
│   └── analysis_*.md           # [自动] 分析报告
├── scripts/
│   ├── market_data.py          # 行情拉取（ETF+个股+基金 + CSV+DB 存档）
│   ├── deepseek_analysis.py    # DeepSeek 分析（--no-push --auto-commit）
│   ├── auto_runner.py          # 全自动流水线（--alert 模式）
│   ├── market_alert.py         # 波动预警（--threshold 3.0）
│   ├── history.py              # 历史查询 + 图表（--plot）
│   ├── database.py             # SQLite 引擎
│   ├── db_query.py             # 数据库查询工具
│   ├── wecom_push.py           # 企微推送（多段拆分）
│   ├── wechat_push.py          # Server酱推送（兜底）
│   └── requirements.txt
└── prompts/
    ├── monthly_review.md       # 月度体检
    ├── portfolio_rebalance.md  # 再平衡
    ├── insurance_audit.md      # 保障审计
    └── market_event.md         # 市场应急
```

---

## 使用方式

### Claude Code 自然语言

| 你说 | 执行 |
|------|------|
| "做月度体检" | `auto_runner.py` → 行情+分析+GitHub推送+企微通知 |
| "要不要调仓" | `deepseek_analysis.py --prompt portfolio_rebalance` |
| "保险够不够" | `deepseek_analysis.py --prompt insurance_audit` |
| "大跌影响" | `deepseek_analysis.py --prompt market_event` |
| "更新行情" | `market_data.py` |
| "跑个预警" | `market_alert.py --threshold 3.0` |

### CLI

```bash
conda activate deepseek_v4_api

python scripts/market_data.py                    # 行情 + CSV + DB
python scripts/history.py                        # 历史摘要
python scripts/history.py --plot                 # 走势图
python scripts/db_query.py                       # DB 总览
python scripts/db_query.py --holding 600519      # 单只详情
python scripts/market_alert.py --threshold 3.0   # 波动预警
python scripts/auto_runner.py                    # 全自动
python scripts/auto_runner.py --alert            # 仅预警
```

---

## 环境

- Python：`deepseek_v4_api` conda 或纯 pip
- 行情：akshare（ETF/eastmoney + A股/Sina 双源）
- 分析：DeepSeek API `deepseek-chat`（timeout=120s）
- 推送：企微 Webhook（主）+ Server酱（备）
- 代理：启动时清 HTTP_PROXY，eastmoney 被拦自动切 Sina

---

## 已知问题

1. Git Bash 终端 UTF-8 中文乱码 → 设 `PYTHONIOENCODING=utf-8`
2. A 股 eastmoney 被代理 127.0.0.1:19395 拦截 → Sina fallback
3. 企微 Markdown 限 4096 字节 → 拆多段

---

## 数据隐私

- 当前数据为 John Doe 虚构演示
- `PRIVATE.md` + `.env` + `finance_data.db` → gitignore
- 分析时数据发送至 DeepSeek API
- 报告暂通过 GitHub Private Repo 链接查看

---

## 下一步

1. 企微文件直发（报告不经过 GitHub）
2. Ubuntu 24/7 部署（cron）
3. Flask Web Dashboard + cloudflared tunnel
4. 企微双向互动（@机器人）
