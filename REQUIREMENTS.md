# 功能需求清单

> 最后更新：2026-06-27

---

## P0 — 核心功能 ✅

- [x] **市场数据获取**：ETF(eastmoney) + 个股(Sina双源) + 基金净值
- [x] **持仓市值计算**：自动更新资产总值
- [x] **资产配置分析**：占比 + 偏离度 + 目标对比
- [x] **现金流分析**：月收/支/结余 + 应急储备
- [x] **保险保障缺口**：逐风险类型评估

## P1 — 分析引擎 ✅

- [x] **再平衡建议**：偏离检测 + 具体金额 + 标的
- [x] **目标进度追踪**：百分比 + 预计达成时间
- [x] **市场事件应急**：影响评估 + 应对策略
- [x] **月度自动体检**：一键生成 + 推送

## P2 — 自动化 & 存储 ✅

- [x] **推送通知**：企微自建应用 + 群 Webhook + Server酱兜底
- [x] **历史净值追踪**：CSV + SQLite + matplotlib 图表
- [x] **定时自动**：auto_runner + cron
- [x] **市场波动预警**：单日涨跌超阈值推送
- [x] **SQLite 数据库**：holdings/prices/snapshots/analysis_log (WAL mode)

## P3 — 企微双向互动 ✅

- [x] **企微文件直发**：附件推送，手机直接打开
- [x] **代码与数据分离**：config.py + FINANCE_DATA_DIR 切换
- [x] **自建应用回调**：AES-256-CBC 加解密 + 命令路由
- [x] **菜单交互**：📈 行情/🤖 分析/⚙️ 更多
- [x] **8 个命令**：快照 / 体检 / 预警 / FIRE / 回测 / 走势 / 健康 / 家庭体检

## P4 — 生产保障 ✅

- [x] **文件锁**：Linux fcntl.flock（OS 内核管理）
- [x] **线程池**：max_workers=4 + MsgId 去重
- [x] **数据校验**：分析前 validate_context()
- [x] **每日备份**：zip 打包（30 天保留）
- [x] **健康检查**：5 项（SQLite/akshare/DeepSeek/磁盘/数据文件）
- [x] **HA 容灾**：Cloudflare Tunnel 双活
- [x] **Ubuntu 24/7**：systemd + cron 自动化

## P5 — 家庭版 ✅ (demo 阶段)

- [x] **多成员数据模型**：family.json + members/{me,dad,mom}
- [x] **家庭汇总引擎**：隐私过滤 + 脱敏聚合
- [x] **家庭 AI 分析**：6 维度（收入依赖/现金流/保障缺口/资产/目标/改进）
- [x] **家庭网页看板**：All-in-one dashboard (/family)
- [x] **爸妈微信看板**：只读 + 体检按钮 (/home)

## P6 — 下一阶段（grill-me 2026-06-27 确立）

### P6-1 外部情报系统 v1 🔨 本次

- [ ] **数据源**：CLS 财联社电报 + NewsAPI + akshare macro_china（主力）；THS 全球财经（补充）
- [ ] **两阶段过滤**：阶段 1 结构化规则粗筛（去重+去噪音），阶段 2 DeepSeek 摘要+推理+评分
- [ ] **三通道入阶段 2**：🅰️宏观必过 🅱️画像命中（信号增强） 🅲️LLM 自行判断
- [ ] **输出结构化 JSON**：含 category/tags/confidence(1-10)/relevance(0-10)/actionability(4级)/impacted_assets/impacted_members/time_horizon/duplicate_group
- [ ] **综合评分推送**：Score = 0.45×relevance + 0.35×actionability + 0.20×confidence，≥8 推企微
- [ ] **调度**：早间 08:30 全量 + 午间 12:30 轻量（仅 `act` 级）
- [ ] **双通道展示**：企微推送 Top 3 + 家庭看板全部浏览
- [ ] **企微命令**：`/简报`（缓存秒回）+ `/简报 --刷新`（异步重新生成）
- [ ] **sentiment 拆分**：macro/equity/bond/housing 四类

### P6-1 外部情报系统 v2 📋 后续

- [ ] **事件聚类引擎**：TF-IDF + cosine similarity 自动去重，独立于 LLM
- [ ] **追问功能**：看板输入框 + DeepSeek 带简报上下文回答
- [ ] **画像自动更新**：DeepSeek 定期从持仓变动中更新 intelligence_profile
- [ ] **信源扩展**：国务院/央行/财政部公告 + ETF 公告

### P6-2 ~ P6-4

- [ ] **FIRE 蒙特卡洛**：随机模拟升级
- [ ] **定投回测参数化**：`/回测 510300 2000 5年`
- [ ] **预警阈值差异化**：按资产类型

## 非功能需求 ✅

- [x] 真实数据不入 git（代码数据分离）
- [x] 脱敏数据可运行（finance_demo + family_demo）
- [x] 错误处理健壮（API/网络/代理/并发/死锁）
- [x] 输出可读（中文/分层/数字）
- [x] Repo public 安全展示
