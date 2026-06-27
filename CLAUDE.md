# AI 财务助手 — Claude Code 项目

> Claude Code 交互层 + DeepSeek API 分析 + akshare 行情 + SQLite 存储
> 最后更新：2026-06-27

---

## 项目架构

```
AI_Financial_Assistant/
├── CLAUDE.md                   # ← 新会话自动加载
├── REQUIREMENTS.md             # 功能清单
├── GEMINI_PROMPT.md            # 外部 AI 项目总结
├── PRIVATE.md                  # 🔒 真实数据（gitignore）
├── .env                        # 🔒 API Keys（gitignore）
├── .env.example                # 配置模板（git 跟踪）
├── .gitignore
├── run_auto.bat / run_alert.bat / run_web.bat
├── finance_demo/               # Demo 数据（John Doe，git 跟踪）
├── family_demo/                # 家庭版 Demo 数据（git 跟踪）
│   ├── family.json             # 成员定义 + 权限规则
│   ├── members/{me,dad,mom}/   # 各自独立数据
│   └── household/              # 共有资产 + 目标
├── finance/                    # 🔒 真实数据（gitignore）
├── family/                     # 🔒 真实家庭数据（gitignore）
├── deploy/cloudflared/         # Tunnel 配置 + cron 脚本
├── scripts/
│   ├── config.py               # 集中式路径配置 + 文件锁 + 日志
│   ├── market_data.py          # 行情拉取（ETF+个股+基金）
│   ├── deepseek_analysis.py    # DeepSeek 分析 + 数据校验阀
│   ├── auto_runner.py          # 全自动流水线
│   ├── market_alert.py         # 波动预警
│   ├── history.py              # 历史查询 + matplotlib 图表
│   ├── database.py             # SQLite 引擎 (WAL + timeout=30)
│   ├── db_query.py             # 数据库查询工具
│   ├── wecom_push.py           # 企微推送（UTF-8 安全分块）
│   ├── wecom_app.py            # 企微自建应用 API（token 缓存 + thread lock）
│   ├── wecom_crypto.py         # 企微消息 AES 加解密
│   ├── wechat_push.py          # Server酱推送（仅通知，不含全文）
│   ├── webapp.py               # Flask 服务（回调 + Dashboard + 家庭 API）
│   ├── webapp_helpers.py       # Dashboard 辅助函数
│   ├── family_engine.py        # 家庭引擎（聚合 + 隐私过滤）
│   ├── fire_simulator.py       # FIRE 模拟器（4% 规则）
│   ├── backtest.py             # 定投回测（DCA vs 一次性）
│   ├── health_check.py         # 系统健康检查（5 项，每日推送）
│   ├── backup.py               # 每日数据备份（zip，30 天保留）
│   ├── validate.py             # 24 项自动化验证
│   ├── setup_menu.py           # 企微菜单配置
│   ├── start_tunnel.py         # cloudflared tunnel 启动
│   └── templates/              # HTML 模板 (family.html etc)
└── prompts/
    ├── monthly_review.md       # 月度体检
    ├── portfolio_rebalance.md  # 再平衡
    ├── insurance_audit.md      # 保障审计
    ├── market_event.md         # 市场应急
    └── family_review.md        # 家庭财务体检
```

---

## 使用方式

### Claude Code 自然语言

| 你说 | 执行 |
|------|------|
| "做月度体检" | `auto_runner.py` → 行情+分析+推送 |
| "要不要调仓" | `deepseek_analysis.py --prompt portfolio_rebalance` |
| "启动面板" | `python scripts/webapp.py` → http://localhost:5000 |

### CLI

```bash
conda activate deepseek_v4_api

python scripts/market_data.py                    # 行情 + CSV + DB
python scripts/history.py --plot                 # 走势图
python scripts/market_alert.py --threshold 3.0   # 波动预警
python scripts/auto_runner.py                    # 全自动
python scripts/auto_runner.py --alert            # 仅预警
python scripts/webapp.py                         # Flask (dev)
python scripts/webapp.py --prod                  # Flask (生产)
python scripts/validate.py                       # 24 项验证
python scripts/health_check.py                   # 系统体检
python scripts/backup.py                         # 数据备份
python scripts/fire_simulator.py                 # FIRE 计算
python scripts/backtest.py --code 510300         # 定投回测
python scripts/family_engine.py                  # 家庭数据引擎
```

### 企微自建应用（手机端）

| 命令 | 菜单 |
|------|------|
| 📈 行情 → 快照 / 走势 / 预警 | `/快照` `/走势` `/预警` |
| 🤖 分析 → 体检 / 家庭体检 / FIRE / 回测 | `/体检` `/家庭体检` `/fire` `/回测 510300` |
| ⚙️ 更多 → 帮助 | `/帮助` `/健康` |

### 家庭网页

- `https://finance-assistant.mote-pal.xyz/family` — All-in-one 家庭看板
- `https://finance-assistant.mote-pal.xyz/home` — 爸妈微信看板

---

## 环境

- Python：`deepseek_v4_api` conda 或纯 pip
- 行情：akshare（ETF/eastmoney + A股/Sina 双源）
- 分析：DeepSeek API `deepseek-chat`（timeout=120s）
- 推送：企微自建应用 API + Webhook + Server酱（兜底）
- 部署：主阵地 Ubuntu 24.04 (mote-home) 24/7，Windows 仅作热备
- Tunnel：Cloudflare ff961b4a（HA 双节点，主节点服务器）
- 新功能优先部署在服务器上，利用 24/7 不间断运行

---

## 关键设计决策

1. **代码数据分离** — `FINANCE_DATA_DIR` 环境变量，demo/finance 物理隔离
2. **UTF-8 零丢字** — 按行切分，不在多字节字符中间截断
3. **fcntl 文件锁** — OS 内核管理，进程崩溃自动释放
4. **线程池防雪崩** — max_workers=4 + MsgId 去重
5. **数据校验阀** — 分析前校验快照完整性，脏数据不喂 LLM
6. **家庭隐私隔离** — 三级可见度（自己/家庭汇总/他人脱敏）

---

## 待完成

### 🔨 外部情报系统 v1（grill-me 2026-06-27 确立）

**数据源**：CLS 财联社电报 + NewsAPI + akshare macro_china（主力）；THS 全球财经（补充）
**过滤**：两阶段 — 阶段 1 结构化规则粗筛 → 阶段 2 DeepSeek 摘要+推理+评分
**三通道入 LLM**：🅰️宏观必过 🅱️画像命中 🅲️LLM 自行判断
**输出**：结构化 JSON（category/tags/confidence 1-10/relevance 0-10/actionability 4级/impacted_assets/time_horizon/duplicate_group）
**推送**：Score = 0.45×relevance + 0.35×actionability + 0.20×confidence，≥8 推企微
**调度**：早间 08:30 全量 + 午间 12:30 轻量（仅 `act` 级）
**企微**：`/简报`（缓存秒回）+ `/简报 --refresh`（异步重新生成）
**看板**：家庭看板嵌入简报卡片，可浏览全部

### 📋 后续

- 外部情报 v2：事件聚类引擎 + 追问功能 + 画像自动更新 + 信源扩展
- FIRE 蒙特卡洛模拟升级
- 定投回测参数化交互（`/回测 510300 2000 5年`）
- 预警阈值差异化（按资产类型）

详见 REQUIREMENTS.md P6。

---

## 服务器 cron

- 03:00 每日数据备份
- 08:30 早间简报（全量）
- 09:00 健康检查推送
- 12:30 午间简报补充（仅 `act` 级）
- 14:45 月度体检（工作日）
- 14:55 波动预警（工作日）
