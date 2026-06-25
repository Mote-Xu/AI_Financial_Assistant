# AI 财务助手 — 项目总结（发给外部 AI）

> 发给 Gemini / ChatGPT 的完整项目上下文。
> 最后更新：2026-06-26

---

## 项目概况

AI 财务助手是一个**个人理财分析系统**。三层架构：

| 层 | 技术 |
|------|------|
| 交互 | Claude Code CLI（自然语言） |
| 数据 | Markdown 静态文件 + akshare 实时行情 |
| 分析 | DeepSeek API (`deepseek-chat`) |

## 已验证功能

- ✅ **A 股行情**：4 ETF + 2 个股 + 2 基金，eastmoney/Sina 双源
- ✅ **4 类分析**：月度体检 / 再平衡 / 保障审计 / 市场应急
- ✅ **企微推送**：报告拆多段（4096 字节/条），手机完整可读
- ✅ **Server酱兜底**：企微失败自动切
- ✅ **历史追踪**：每跑行情追加 CSV，支持图表 (`history.py --plot`)
- ✅ **定时自动**：`auto_runner.py` + `run_auto.bat`（Windows Task Scheduler）
- ✅ **隐私**：`.env` 和 `PRIVATE.md` gitignore

## 当前数据

`finance/` 下为 **John Doe 虚构演示数据**（30 岁杭州互联网 P7，总资产 ~213 万）

## 技术栈

- Python 3.12 / conda `deepseek_v4_api`
- akshare、OpenAI SDK → DeepSeek、matplotlib
- 企微 Webhook + Server酱
- Claude Code CLI
- Git: `github.com/Mote-Xu/AI_Financial_Assistant`

## 下一步候选

1. **市场波动预警**：持仓单日跌超 3% 自动推企微
2. **FIRE 模拟器**：不同参数路径模拟
3. **定投回测**：历史数据回测
4. **SQLite 替代纯 MD**：结构化存储 + 复杂查询
5. **Ubuntu cron 24/7 部署**（有老服务器待用）

## 已知问题

- Git Bash 终端 UTF-8 乱码（文件写入正常）
- A 股 eastmoney 被本地代理 127.0.0.1:19395 拦截，已用 Sina fallback
- DeepSeek API 需 120s 超时
- 企微 Markdown 限 4096 字节（~1300 中文字），需拆段
- 财务数据上传 DeepSeek 云端推理（隐私权衡）
