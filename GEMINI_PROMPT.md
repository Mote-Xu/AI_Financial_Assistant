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

## 已完成功能

- ✅ **A 股行情**：ETF + 个股 + 基金，eastmoney/Sina 双源
- ✅ **4 类分析**：月度体检 / 再平衡 / 保障审计 / 市场应急
- ✅ **企微推送**：文本多段拆分 + **文件直发**（手机直接下载，无需 GitHub）
- ✅ **Server酱兜底**：普通微信推送
- ✅ **历史净值追踪**：CSV + SQLite，支持 `history.py --plot` 图表
- ✅ **定时自动**：`auto_runner.py` + 计划任务（Windows）→ Ubuntu cron（待部署）
- ✅ **市场波动预警**：`market_alert.py`，持仓单日涨跌超阈值自动推企微
- ✅ **SQLite 数据库**：holdings / prices / snapshots / analysis_log

## 架构：代码与数据分离（已实施）

**机制**：`scripts/config.py` 集中路径配置，读 `FINANCE_DATA_DIR` 环境变量

| 模式 | 数据目录 | Git |
|------|---------|-----|
| Demo（默认） | `finance_demo/` | ✅ 跟踪（John Doe 虚构数据） |
| 真实 | `finance/` 或外部路径 | ❌ gitignore |

- `finance/` 整体 gitignore，真实数据物理隔离
- Repo 已设 **public**，安全展示代码 + 架构 + demo
- `.env.example` 提供配置模板

## 当前卡点：无

~~隐私 vs. 便利~~ → **已解决**：企微文件直发
~~Repo 公开 vs 隐私~~ → **已解决**：代码与数据分离架构

下一步优先做 Flask Dashboard + 企微双向互动。

---

## 技术栈

- Python 3.12 / conda `deepseek_v4_api`
- akshare、OpenAI SDK → DeepSeek、matplotlib、sqlite3
- 企微 Webhook + Server酱
- Claude Code CLI

## 当前数据

`finance_demo/` 下为 John Doe 虚构演示数据（git 跟踪）。真实数据放 `finance/` 或外部路径（gitignore）。

## 下一步候选（待 Gemini 建议优先级）

- FIRE 模拟器
- 定投回测
- 企微双向互动（@机器人 → Flask 回调）
- Ubuntu 24/7 部署
- 本地模型替代 DeepSeek API（GPU: RTX 3050 4GB，不够）
