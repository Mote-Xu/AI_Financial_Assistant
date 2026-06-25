# AI 财务助手 — 项目总结（发给外部 AI）

> 发给 Gemini / ChatGPT 的完整项目上下文。请基于此给出下一步功能建议。
> 最后更新：2026-06-26

---

## 项目概况

AI 财务助手是一个**个人理财分析系统**，Windows 11 本地运行。三层架构：

| 层 | 实现 |
|------|------|
| 交互层 | Claude Code CLI（自然语言驱动） |
| 数据层 | `finance/*.md` 手动维护 + `akshare` 自动拉 A 股行情 |
| 分析层 | DeepSeek API（`deepseek-chat`）生成中文财务报告 |

## 已验证功能

- ✅ **A 股行情**：ETF（4/4）+ 个股（2/2，eastmoney 被代理拦，Sina 备用）
- ✅ **基金净值**：akshare 东方财富接口
- ✅ **4 类分析提示词**：月度体检 / 再平衡 / 保障审计 / 市场应急
- ✅ **企业微信推送**：分析完成后拆条发企微群（4096 字节/条），手机可读完整报告
- ✅ **Server酱兜底**：企微挂了走 Server酱微信推送
- ✅ **隐私保护**：`.env`（API Key）+ `PRIVATE.md` 在 `.gitignore`

## 当前不足

1. **被动触发**：必须说"做月度体检"才跑，没有定时/自动机制
2. **无历史追踪**：每次快照覆盖上次，无法画资产曲线
3. **A 股个股需代理绕行**：eastmoney 接口被系统代理 127.0.0.1:19395 拦截，目前用 Sina 备选
4. **终端编码乱码**：Git Bash 下 GBK 显示 UTF-8 中文乱码（文件写入正常）
5. **数据上云**：财务数据发送至 DeepSeek API，隐私需权衡

## 技术栈

- Python 3.12（conda `deepseek_v4_api`）
- akshare 1.x（A 股/基金行情，免费）
- OpenAI SDK 2.x → DeepSeek API
- Server酱 + 企业微信机器人 Webhook（双通道推送）
- Claude Code（Anthropic CLI）

## 想请 AI 给建议

1. 下一步最该做什么功能？候选：
   - 定时自动体检（每月/每周）
   - 历史净值追踪 + 资产曲线图
   - 市场波动预警（持仓单日跌超 3% 自动推企微）
   - FIRE 模拟器
   - 定投回测
   - 目标进度追踪看板

2. 有没有比 akshare 更稳定的免费 A 股数据源？（akshare 依赖 eastmoney，代理环境下不稳定）

3. 隐私问题：有没有好用的本地部署模型方案，替代 DeepSeek API 做财务分析？Ollama + Qwen？效果差距多大？

4. 架构上有什么值得改进的？（目前是 Markdown 文件 + Python 脚本，没有数据库）

---

## 项目结构

```
AI_Financial_Assistant/
├── finance/                     ← 财务数据（当前为 John Doe 虚构演示数据）
│   ├── assets.md                # 资产（4 ETF + 2 个股 + 2 基金 + 房产）
│   ├── income.md                # 收入支出（月入 43K，月结余 20K）
│   ├── insurance.md             # 保单（定寿+重疾+医疗+意外）
│   ├── liabilities.md           # 负债（房贷 180 万 + 消费贷 3.5 万）
│   ├── goals.md                 # 目标（结婚/换车/换房/FIRE）
│   ├── portfolio_snapshot.md    # [自动] 市值快照
│   └── analysis_*.md × 4       # [自动] 分析报告
├── scripts/
│   ├── market_data.py           # 行情拉取
│   ├── deepseek_analysis.py     # DeepSeek 分析
│   ├── wecom_push.py            # 企微多段推送
│   ├── wechat_push.py           # Server酱推送
│   └── requirements.txt
├── prompts/ × 4                 # 分析提示词模板
├── .env 🔒                      # API Keys
├── PRIVATE.md 🔒                # 真实个人信息
└── README.md                    # GitHub 首页
```

## Git

- 仓库：`github.com/Mote-Xu/AI_Financial_Assistant`
- 分支：`main`
- `.env` 和 `PRIVATE.md` 已排除，当前为脱敏数据
