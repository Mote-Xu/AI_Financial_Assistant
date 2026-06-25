# AI 财务助手

> Claude Code（交互层）+ Python（数据层）+ DeepSeek API（分析层）= 个人 AI 理财顾问

---

## 能做什么

- 📊 **一键更新持仓市值** — 自动拉取 A 股 ETF 实时价、基金净值
- 🧠 **AI 财务分析** — 月度体检、资产配置诊断、保险保障审计
- 📉 **市场事件应急** — 大跌时评估对你的实际影响和应对策略
- 📁 **本地数据管理** — 资产、收入、保单、负债、目标全部结构化存储

## 快速开始

```bash
conda activate deepseek_v4_api
pip install -r scripts/requirements.txt

# 拉行情
python scripts/market_data.py

# 月度体检
python scripts/deepseek_analysis.py --prompt prompts/monthly_review.md

# 再平衡分析
python scripts/deepseek_analysis.py --prompt prompts/portfolio_rebalance.md

# 保障审计
python scripts/deepseek_analysis.py --prompt prompts/insurance_audit.md
```

## 在 Claude Code 中直接使用

```
"更新行情并做月度体检"
"分析我的资产配置是否合理"
"我的保险够不够"
"昨天A股大跌，我的持仓受影响多少"
```

## 项目结构

```
finance/          ← 你的财务数据（Markdown，手动编辑）
scripts/          ← Python 脚本（行情拉取、AI 分析）
prompts/          ← 可复用的分析提示词模板
PRIVATE.md        ← 🔒 真实隐私数据（gitignore）
.env              ← 🔒 API Key（gitignore）
```

## 架构

```
finance/*.md ──→ market_data.py ──→ portfolio_snapshot.md
     │                                    │
     └────────────┬───────────────────────┘
                  │
           deepseek_analysis.py ──→ analysis_*.md
                  │
          DeepSeek API (deepseek-chat)
```

## 隐私

- 所有真实数据写入 `PRIVATE.md`，已在 `.gitignore` 排除
- 分析时数据会发送至 DeepSeek API（云端推理）
- 建议初期使用脱敏数据进行测试

## 环境

- Python: `deepseek_v4_api` conda 环境
- 行情数据: `akshare`（免费，无需 API Key）
- AI 分析: DeepSeek API（需配置 `.env`）
