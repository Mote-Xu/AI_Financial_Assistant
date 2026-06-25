# AI 财务助手 — Claude Code 项目

> Claude Code 做交互层 + DeepSeek API 做分析 + akshare 获取市场数据
> 最后更新：2026-06-26

---

## 项目架构

```
AI_Financial_Assistant/
├── CLAUDE.md                   # ← 此文件，新会话上下文
├── REQUIREMENTS.md             # 功能需求清单
├── GEMINI_PROMPT.md            # 发给外部 AI 的项目总结
├── PRIVATE.md                  # 🔒 真实财务数据（gitignore）
├── .env                        # 🔒 API Key（gitignore）
├── .gitignore
├── run_auto.bat                # 定时任务入口（自动检测 conda/pip）
├── setup_old_pc.bat            # 老电脑一键部署
├── finance/                    # 财务数据（手动 + 自动）
│   ├── assets.md               #   资产明细
│   ├── income.md               #   营收现金流
│   ├── insurance.md            #   保单
│   ├── liabilities.md          #   负债
│   ├── goals.md                #   财务目标
│   ├── history.csv             #   [自动] 历史净值时序
│   ├── portfolio_snapshot.md   #   [自动] 市值快照
│   └── analysis_*.md           #   [自动] 分析报告
├── scripts/
│   ├── market_data.py          #   行情拉取 + CSV 存档
│   ├── deepseek_analysis.py    #   DeepSeek API 分析
│   ├── auto_runner.py          #   定时全自动流水线
│   ├── history.py              #   历史查询 + 图表（--plot）
│   ├── wecom_push.py           #   企微多段推送
│   ├── wechat_push.py          #   Server酱兜底
│   └── requirements.txt
└── prompts/
    ├── monthly_review.md       #   月度体检
    ├── portfolio_rebalance.md  #   再平衡分析
    ├── insurance_audit.md      #   保障审计
    └── market_event.md         #   市场事件应急
```

---

## 工作流

### Claude Code 自然语言

| 你说 | 发生什么 |
|------|------|
| "做月度体检" | 行情 + 分析 → 企微推完整报告 |
| "要不要调仓" | 再平衡分析 → 企微 |
| "保险够不够" | 保障审计 → 企微 |
| "大跌影响多少" | 行情 → 事件分析 → 企微 |
| "更新行情" | 拉行情 + 存档 CSV |

### 手工 CLI

```bash
conda activate deepseek_v4_api   # 或 pip install -r scripts/requirements.txt

python scripts/market_data.py                      # 行情 + CSV 存档
python scripts/history.py                          # 查看历史
python scripts/history.py --plot                   # 画资产曲线
python scripts/auto_runner.py                      # 全自动（行情→分析→推送）
python scripts/deepseek_analysis.py --prompt prompts/monthly_review.md
```

### 定时自动

- **Windows**：`setup_old_pc.bat` 一键配任务计划程序
- **Ubuntu**（未来）：cron `0 15 * * 1-5 cd /path && python scripts/auto_runner.py`

---

## 环境

| 组件 | 说明 |
|------|------|
| Python | 3.8+，`deepseek_v4_api` conda 或纯 pip |
| 行情 | akshare（ETF: eastmoney / A股: eastmoney+Sina 双源） |
| 分析 | DeepSeek API `deepseek-chat` |
| 推送 | 企微机器人（主，多段拆分）+ Server酱（备） |
| 代理 | 启动时清 `HTTP_PROXY`，eastmoney 被拦截自动切 Sina |

---

## 已知问题

1. **Git Bash 乱码**：UTF-8 中文 GBK 终端显示乱码 → `PYTHONIOENCODING=utf-8`
2. **A 股 eastmoney 被代理拦截**：127.0.0.1:19395 → 已用 Sina fallback
3. **DeepSeek API 120s 超时**：已设 timeout=120
4. **企微 4096 字节限制**：报告拆多段发

---

## 数据隐私

- `finance/*.md` → John Doe 虚构演示数据
- `PRIVATE.md` → 🔒 真实信息（gitignore）
- `.env` → 🔒 API Key + Webhook（gitignore）
- 分析时数据发送至 DeepSeek API（云端推理）

---

## 当前状态

- ✅ A 股 ETF/个股/基金行情全支持
- ✅ 4 类 DeepSeek 分析全链路
- ✅ 企微多段推送 + Server酱兜底
- ✅ 历史净值 CSV 追踪 + 图表
- ✅ 定时自动流水线（auto_runner）
- ⬜ 市场波动预警
- ⬜ 填入真实数据
- ⬜ Ubuntu 部署
