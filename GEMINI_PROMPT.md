# AI 财务助手 — 项目总结（发给外部 AI）

> 发给 Gemini / ChatGPT 的完整项目上下文。
> 最后更新：2026-06-26

---

## 项目概况

AI 财务助手 — 个人理财分析系统，三层架构：

| 层 | 技术 |
|------|------|
| 交互 | Claude Code CLI（自然语言） |
| 数据 | Markdown 静态文件 + akshare 实时行情 + SQLite |
| 分析 | DeepSeek API (`deepseek-chat`) |

GitHub: `github.com/Mote-Xu/AI_Financial_Assistant`（public，demo 数据）

## 架构

```
AI_Financial_Assistant/
├── finance_demo/           ← Demo 数据（John Doe，git 跟踪）
├── finance/                ← 🔒 真实数据（gitignore，FINANCE_DATA_DIR 切换）
├── scripts/
│   ├── config.py           ← 集中路径配置，读环境变量
│   ├── market_data.py      ← 行情拉取（ETF+个股+基金 + CSV+DB）
│   ├── deepseek_analysis.py← DeepSeek 分析
│   ├── auto_runner.py      ← 全自动流水线（行情+分析+双通道推送）
│   ├── market_alert.py     ← 波动预警
│   ├── history.py          ← 历史查询 + 图表
│   ├── database.py         ← SQLite 引擎
│   ├── wecom_push.py       ← 企微推送（分块全文，无链接）
│   └── wechat_push.py      ← 微信推送（Server酱，全文卡片）
└── prompts/                ← 分析提示词（4 类）
```

## 已完成功能（请求审查）

### 1. 市场数据 ✅
- ETF + 个股 + 基金，eastmoney/Sina 双源
- 自动汇总市值、盈亏、配置比例

### 2. AI 分析 ✅
- 4 类分析：月度体检 / 再平衡 / 保障审计 / 市场应急
- DeepSeek API 流式输出，120s timeout

### 3. 推送通知 ✅
- **企微**：报告全文分块发送，手机直接读（不用下载、不经过 GitHub）
- **微信**：Server酱 推送完整报告卡片（上限 28KB）
- 双通道独立发送，各自成功/失败不影响

### 4. 代码与数据分离 ✅
- `FINANCE_DATA_DIR` 环境变量切换 demo ↔ 真实数据
- 默认 `finance_demo/`（git 跟踪），真实数据 `finance/`（gitignore）
- Repo 公开，零隐私风险

### 5. 自动化 ✅
- `auto_runner.py`：行情 → 分析 → 双通道推送
- `market_alert.py`：持仓单日涨跌超阈值自动推企微
- 历史净值 CSV + SQLite + matplotlib 图表

### 6. 数据库 ✅
- SQLite：holdings / prices / snapshots / analysis_log
- `db_query.py` 查询工具

---

## 请求审查：已实现功能的正确性和完备性

### 审查点 1：架构
- `scripts/config.py` 的路径切换逻辑有没有漏洞？
- 真实数据模式（`FINANCE_DATA_DIR=finance`）还有没有可能误提交？

### 审查点 2：推送
- 企微分块逻辑（4096 字节限制）是否正确处理了中文边界？
- Server酱 28KB 截断是否合理？
- 双通道推送的错误处理是否完备（一个挂了另一个继续）？

### 审查点 3：数据安全
- Git ignore 是否覆盖了所有可能的敏感输出？
- `finance_demo/` 里有没有可能意外包含真实数据？
- 分析报告通过 API 发送给 DeepSeek，隐私风险如何评估？

### 审查点 4：功能完备性
- 有没有重要的理财分析维度我们遗漏了？
- 当前系统作为"个人理财助手"，还缺什么关键功能？
- 错误处理（API 挂、网络断、代理拦截）够不够？

### 审查点 5：下一步
- 当前 4 个待做项：Flask Dashboard / 企微双向互动 / FIRE 模拟器 / 定投回测
- 建议优先级？有没有应该加入但没在列表里的？

---

## 技术栈

- Python 3.12 / conda `deepseek_v4_api`
- akshare、OpenAI SDK → DeepSeek、matplotlib、sqlite3
- 企微 Webhook + Server酱
- Claude Code CLI

## 当前数据

`finance_demo/` 下为 John Doe 虚构演示数据。真实数据放 `finance/`（gitignore）。

## 下一步候选

- Flask Dashboard + cloudflared tunnel
- 企微双向互动（@机器人 → Flask 回调）
- FIRE 模拟器
- 定投回测
- Ubuntu 24/7 部署（cron）
