# AI 财务助手 — 项目全貌 + 请求验证

> 发给外部 AI（Gemini/ChatGPT）。
> 最后更新：2026-06-27

---

## 项目定位

**个人私有 AI 财务大脑**——手机企微就是界面，看不见的自动化在背后跑。

不需要网页、不需要 App、不需要登录。打开企微点按钮，分析结果直接回到同一对话。

---

## 完整功能矩阵

| 触发方式 | 功能 | 耗时 |
|---------|------|------|
| 📱 企微菜单 `/快照` | 实时行情 → 持仓市值+盈亏表 | ~30s |
| 📱 企微菜单 `/体检` | DeepSeek AI 全面分析（配置+风险+建议） | 1-2min |
| 📱 企微菜单 `/fire` | FIRE 财务自由：当前距 FI 多少年 | ~3s |
| 📱 企微菜单 `/回测 510300` | 历史定投回测：CAGR/回撤/策略对比 | ~15s |
| 📱 企微菜单 `/预警` | 持仓波动检测，超阈值推送 | ~10s |
| 📱 企微菜单 `/走势` | 历史净值走势图（图片直发） | ~10s |
| ⏰ cron 14:45 | 自动执行完整体检 | — |
| ⏰ cron 14:55 | 自动执行波动预警 | — |

---

## 架构

```
手机企微
  ↓ HTTPS (AES-256-CBC encrypted XML)
Cloudflare Tunnel (ff961b4a)
  ↓ HA: Windows + Ubuntu 双活
Flask (waitress, :5000)
  ↓ decrypt → route → background thread (max 4)
  ├─ market_data.py  → akshare (eastmoney/Sina 双源)
  ├─ deepseek_analysis.py → DeepSeek API
  ├─ fire_simulator.py     → 4% 规则计算
  ├─ backtest.py           → 历史定投回测
  └─ wecom_app.py          → 企微 API → 用户手机
      └─ SQLite (WAL, timeout=30s)
```

---

## 请求验证

**请验证以下声明的正确性，指出错误或夸大之处，并给出改进建议。**

### 声明 1: 创新点

1. **企微即界面** — 不用网页/App，企微自建应用就是控制台。菜单+文字命令+图片回复一套闭环
2. **分析-推送同会话返回** — 结果直接回到同一对话，不需要"发命令→去别的地方看结果"
3. **Cloudflare 双活容灾** — Windows + Ubuntu 连同一个 tunnel，任一台挂了 OS 级自动切换
4. **代码数据彻底分离** — `FINANCE_DATA_DIR` 环境变量，demo 公开 git 跟踪，真实数据物理隔离
5. **UTF-8 零丢字分块** — 按行切割，不在多字节字符中间截断
6. **fcntl 不死锁** — Linux 用 OS 内核管理文件锁，进程崩溃自动释放
7. **线程池防雪崩** — max_workers=4 + MsgId 5 分钟去重

> 哪些创新点不成立或夸大？哪些方向还可以深挖？

### 声明 2: 准确性

- 行情数据来自 akshare（东方财富 + 新浪双源），实时性如何？有没有更好的数据源？
- FIRE 计算用 4% 规则 + 复利公式，是否足够专业？蒙特卡洛模拟是否有必要？
- 定投回测用 akshare 历史数据，精度如何？对比专业回测平台（如 JoinQuant）差距在哪？
- DeepSeek API 做财务分析，与专业 CFP 分析差距在哪？

### 声明 3: 完备性

- 当前 7 个命令覆盖了"存量分析+未来规划+风险监控"，作为个人理财系统，还缺什么？
- 错误处理：akshare 全挂、DeepSeek 超时、企微推送失败——覆盖够吗？
- 服务器稳定性：systemd + cron + fcntl + thread pool——有遗漏吗？

### 声明 4: 落地可行性

- 这套架构能否支撑一个真实个人长期使用？
- 用真实数据（非 John Doe demo）跑，最大的风险是什么？
- 从"demo 能跑"到"生产可用"之间还差什么？

---

## 技术栈

Python 3.12 · Flask + waitress · akshare · DeepSeek API · SQLite (WAL) · matplotlib
企微自建应用 API + Webhook · Cloudflare Tunnel · systemd · fcntl

## 数据安全

| 措施 | 实现 |
|------|------|
| 代码数据分离 | `FINANCE_DATA_DIR` 环境变量切换 |
| Demo 公开 | `finance_demo/` git 跟踪（John Doe 虚构） |
| 真实隔离 | `finance/` gitignore |
| 密钥保护 | `.env` gitignore |
| 日志隔离 | `error.log` 循环写入, `*.log` gitignore |
| 第三方最小化 | Server酱 仅通知不含数据；DeepSeek API 承诺不用于训练 |
