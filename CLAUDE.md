# AI 财务助手 — Claude Code 项目

> 用 Claude Code 做交互层 + DeepSeek API 做分析 + Python 脚本获取市场数据
> 最后更新：2026-06-25

---

## 项目架构

```
AI_Financial_Assistant/
├── CLAUDE.md                   # ← 此文件，项目架构说明
├── REQUIREMENTS.md             # 功能需求清单
├── PRIVATE.md                  # 🔒 真实财务数据（gitignore）
├── .env                        # 🔒 API Key（gitignore）
├── .gitignore
├── finance/                    # 财务数据（可手动编辑）
│   ├── assets.md               #   资产明细
│   ├── income.md               #   营收现金流
│   ├── insurance.md            #   保单
│   ├── liabilities.md          #   负债
│   ├── goals.md                #   财务目标
│   ├── portfolio_snapshot.md   #   [自动生成] 市值快照
│   └── analysis_*.md           #   [自动生成] 分析报告
├── scripts/                    # 可执行脚本
│   ├── market_data.py          #   拉取 A 股 ETF/基金行情
│   ├── deepseek_analysis.py    #   调用 DeepSeek API 分析
│   └── requirements.txt        #   Python 依赖
└── prompts/                    # 可复用的分析提示词
    ├── monthly_review.md       #   月度体检
    ├── portfolio_rebalance.md  #   再平衡分析
    ├── insurance_audit.md      #   保障审计
    └── market_event.md         #   市场事件应急
```

---

## 工作流

### 日常使用（在 Claude Code 中）

直接对我说：
- "更新市场数据并做月度体检" → 我会依次运行 `market_data.py` + `deepseek_analysis.py --prompt monthly_review`
- "分析我的资产配置是否合理" → 我会读取你的 finance/*.md 并给出建议
- "昨天 A 股大跌，我的持仓受影响多少" → 先跑行情脚本，再做事件分析
- "我的保险够不够" → 读取保单 + 目标，做保障缺口分析

### 手工运行

```bash
# 1. 拉取最新行情
python scripts/market_data.py

# 2. 月度体检
python scripts/deepseek_analysis.py --prompt prompts/monthly_review.md

# 3. 再平衡分析
python scripts/deepseek_analysis.py --prompt prompts/portfolio_rebalance.md

# 4. 保障审计
python scripts/deepseek_analysis.py --prompt prompts/insurance_audit.md
```

---

## 环境要求

- **Python** 环境：使用 `deepseek_v4_api` conda 环境
- **API Key**：DeepSeek API Key 写入 `.env` 文件
- **akshare**：用于获取 A 股/基金行情（免费、无需 API Key）

首次使用：
```bash
conda activate deepseek_v4_api
pip install -r scripts/requirements.txt
```

---

## 数据隐私

- `finance/*.md` → 模板为脱敏数据。真实数据请自行替换
- `PRIVATE.md` → 真实个人信息，已在 `.gitignore` 排除
- `.env` → API Key，已在 `.gitignore` 排除
- 分析时，数据会发送至 DeepSeek API（云端推理）
- **不建议将真实财务数据提交到公开仓库**

---

## 当前状态

- ✅ 模板数据填充完毕
- ✅ 行情获取脚本就绪
- ✅ DeepSeek 分析脚本就绪
- ✅ 分析提示词就绪
- ⬜ 待填入真实数据
- ⬜ 待首次运行验证
