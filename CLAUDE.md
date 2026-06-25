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
├── finance/                    # 财务数据（手动编辑 + 自动生成）
│   ├── assets.md               #   资产明细
│   ├── income.md               #   营收现金流
│   ├── insurance.md            #   保单
│   ├── liabilities.md          #   负债
│   ├── goals.md                #   财务目标
│   ├── portfolio_snapshot.md   #   [自动生成] 市值快照
│   └── analysis_*.md           #   [自动生成] 分析报告
├── scripts/                    # 可执行脚本
│   ├── market_data.py          #   拉取 A 股 ETF/个股/基金行情
│   ├── deepseek_analysis.py    #   DeepSeek API 分析 + 推送
│   ├── wecom_push.py           #   企业微信机器人推送（多段拆分）
│   ├── wechat_push.py          #   Server酱推送（兜底）
│   └── requirements.txt
└── prompts/                    # 可复用的分析提示词
    ├── monthly_review.md       #   月度体检
    ├── portfolio_rebalance.md  #   再平衡分析
    ├── insurance_audit.md      #   保障审计
    └── market_event.md         #   市场事件应急
```

---

## 工作流

### 在 Claude Code 中（自然语言）

| 你说 | 发生什么 |
|------|------|
| "做月度体检" | 行情 + 全部财务数据 → DeepSeek 分析 → 企微推完整报告 |
| "我的资产配置合理吗 / 要不要调仓" | 再平衡分析 → 企微推送 |
| "我的保险够不够" | 保障审计 → 企微推送 |
| "A 股大跌，影响多少" | 行情 → 事件分析 → 企微推送 |
| "更新行情" | 仅拉取实时价，更新快照 |

### 手工运行

```bash
conda activate deepseek_v4_api

# 行情
python scripts/market_data.py

# 分析（会自动推企微，企微失败则走 Server酱）
python scripts/deepseek_analysis.py --prompt prompts/monthly_review.md
python scripts/deepseek_analysis.py --prompt prompts/portfolio_rebalance.md
python scripts/deepseek_analysis.py --prompt prompts/insurance_audit.md
python scripts/deepseek_analysis.py --prompt prompts/market_event.md
```

---

## 环境

- **Python**：`deepseek_v4_api` conda 环境
- **行情**：akshare（免费，无需 API Key），ETF/eastmoney + A 股/Sina 双源
- **分析**：DeepSeek API（`deepseek-chat`）
- **推送**：企业微信机器人（主）+ Server酱（备）
- **代理**：脚本启动时清除 `HTTP_PROXY`，eastmoney 被代理拦截时自动切 Sina

---

## 已知问题

1. **Git Bash 终端乱码**：UTF-8 中文在 GBK 终端显示乱码，文件写入正常 — 设 `PYTHONIOENCODING=utf-8`
2. **A 股 eastmoney 被代理拦截**：127.0.0.1:19395 代理拦截 push2.eastmoney.com，已用 Sina fallback
3. **DeepSeek API 需 120s 超时**：默认太短
4. **企微 Markdown 限制 4096 字节**（~1300 中文字）：报告拆多段发送

---

## 数据隐私

- `finance/*.md` → 当前为 John Doe 虚构演示数据
- `PRIVATE.md` → 🔒 真实个人信息（gitignore）
- `.env` → 🔒 API Key + Webhook Key（gitignore）
- 分析时数据发送至 DeepSeek API（云端推理）

---

## 当前状态

- ✅ A 股 ETF/个股/基金行情全支持
- ✅ 4 类 DeepSeek 分析全链路验证
- ✅ 企微多段推送 + Server酱兜底
- ✅ John Doe 演示数据 + 4 份 demo 报告
- ⬜ 待填入真实数据
- ⬜ 待加定时/自动功能
