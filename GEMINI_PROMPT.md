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

GitHub: `github.com/Mote-Xu/AI_Financial_Assistant`（当前 public，demo 数据）

## 已完成功能

- ✅ **A 股行情**：ETF + 个股 + 基金，eastmoney/Sina 双源
- ✅ **4 类分析**：月度体检 / 再平衡 / 保障审计 / 市场应急
- ✅ **企微推送**：Webhook 多段拆分
- ✅ **Server酱兜底**：普通微信推送
- ✅ **历史净值追踪**：CSV + SQLite，支持 `history.py --plot` 图表
- ✅ **定时自动**：`auto_runner.py` + 计划任务（Windows）→ Ubuntu cron（待部署）
- ✅ **市场波动预警**：`market_alert.py`，持仓单日涨跌超阈值自动推企微
- ✅ **SQLite 数据库**：holdings / prices / snapshots / analysis_log

## 当前卡点：隐私 vs. 便利

**问题**：想让手机微信点击链接就能看完整报告，当前方案是把报告 git push 到 GitHub，然后推送 GitHub 链接。

**风险**：repo 是 public，报告含财务数据 → 隐私泄露。

**候选方案**：
| 方案 | 优点 | 缺点 |
|------|------|------|
| A. repo 设 Private | 最快，链接即用 | 仍需 GitHub 账号登录 |
| B. push 到私有 Gist | 不暴露仓库 | Gist 管理麻烦 |
| C. cloudflared tunnel 到本地 | 数据不出本地 | 需 Ubuntu 服务器 24/7 |
| D. 放弃链接，推送摘要 | 零风险 | 手机看不完整 |

**倾向**：repo 设 Private 最快。但长远看，等 Ubuntu 服务器就绪后用 cloudflared tunnel 把报告托管在本地是最优解。

**想问**：这 4 个方案推荐哪个？有没有更好的第 5 种？

---

## 技术栈

- Python 3.12 / conda `deepseek_v4_api`
- akshare、OpenAI SDK → DeepSeek、matplotlib、sqlite3
- 企微 Webhook + Server酱
- Claude Code CLI

## 当前数据

`finance/` 下为 John Doe 虚构演示数据。真实数据待填入。

## 下一步候选（待 Gemini 建议优先级）

- FIRE 模拟器
- 定投回测
- 企微双向互动（@机器人 → Flask 回调）
- Ubuntu 24/7 部署
- 本地模型替代 DeepSeek API（GPU: RTX 3050 4GB，不够）
