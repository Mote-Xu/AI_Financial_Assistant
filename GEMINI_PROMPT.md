# AI 财务助手 — 项目现状 + 请求审查

> 发给外部 AI（Gemini/ChatGPT），包含关键代码细节。
> 最后更新：2026-06-27

---

## 项目概况

AI 财务助手 — 个人理财分析系统。三层架构：
- **交互层**: 企微自建应用（菜单+@机器人）+ Flask 回调 + cloudflared tunnel
- **分析层**: DeepSeek API 分析 + FIRE 模拟器 + 定投回测
- **数据层**: Markdown 静态文件 + akshare 实时行情 + SQLite

GitHub: `github.com/Mote-Xu/AI_Financial_Assistant`（public，demo 数据）

---

## 请求审查

**所有代码已通过自动化验证（24/24 项）。请审查架构正确性、代码质量、潜在漏洞和改进方向。**

---

## 1. 架构总览

```
手机企微 "📈 快照"
    ↓ POST /callback/wecom (AES-256-CBC encrypted XML)
    ↓ Flask (waitress, :5000)
    ↓ decrypt → route → /快照 handler
    ↓ background thread (avoid 5s timeout)
    ↓ market_data.py → akshare → portfolio_snapshot.md
    ↓ wecom_app.send_to_user() → 企微 API → 手机
```

### 部署架构
```
finance-assistant.mote-pal.xyz (Cloudflare DNS)
         ↓
    Tunnel ff961b4a (HA: Windows + Ubuntu 双活)
    ┌────┴────┐
Windows      Ubuntu Server (mote-home)
 :5000        :5000 (systemd: finance-flask)
              crontab: 14:45 daily auto_runner
```

---

## 2. 核心代码

### config.py — 集中路径 + 文件锁 + 日志

```python
# 数据目录: 环境变量切换 demo/真实/外部路径
_env_dir = os.getenv("FINANCE_DATA_DIR", "")
if _env_dir:
    _p = Path(_env_dir).expanduser().resolve()  # 支持 ~/path
    FINANCE_DIR = _p if _p.is_absolute() else (PROJECT_ROOT / _env_dir).resolve()
else:
    FINANCE_DIR = (PROJECT_ROOT / "finance_demo").resolve()

# 显式创建，避免 import 副作用
def ensure_finance_dir():
    FINANCE_DIR.mkdir(parents=True, exist_ok=True)

# 文件锁: 防止 cron 重叠执行
def acquire_lock():
    if LOCK_FILE.exists(): return False
    LOCK_FILE.touch(); return True

# 错误日志: RotatingFileHandler, 100KB×3
```

### wecom_app.py — 应用 API 推送

```python
def send_to_user(user_id: str, content: str) -> bool:
    token = _get_token()  # 缓存, 7200s TTL
    payload = {
        "touser": user_id,
        "msgtype": "text",
        "agentid": agentid,
        "text": {"content": content},
    }
    r = requests.post(f"/message/send?access_token={token}", json=payload)
    return r.json().get("errcode") == 0
```

### webapp.py — 回调处理 + 命令路由

```python
@app.route("/callback/wecom", methods=["GET", "POST"])
def wecom_callback():
    sig, ts, nonce = request.args["msg_signature"], ...
    if GET: return decrypt(echostr, sig, ts, nonce)  # URL 验证
    # POST: 解密 → 解析 XML → 命令路由
    plain = decrypt(encrypted.text, sig, ts, nonce)
    msg_xml = ET.fromstring(plain)
    # 支持: 文字消息 + 菜单点击事件
    if msg_type == "event": msg = cmd_map.get(event_key)
    else: msg = content_el.text
    # 异步回复（通过应用 API，可靠）
    threading.Thread(target=send_to_user, args=(user_id, _handle_command(msg))).start()
    return "", 200  # 空响应，不走不稳定的加密XML回复

def _handle_command(msg, user_id):
    # /体检 /快照 /预警 /fire /走势 /回测 510300 /帮助
    if "/快照": thread(_run_snapshot, user_id)
    if "/体检": thread(_run_checkup, user_id)  # ← 自己读报告发到私聊，不走群webhook
    if "/fire": thread(_run_fire, user_id)
    if "/回测 510300": thread(_run_backtest, user_id, "510300")
```

### fire_simulator.py — 4% 规则计算

```python
def simulate(return_rate=0.07, inflation=0.03, withdraw_rate=0.04):
    # FI 目标 = 年支出 / 提取率
    fi_number = expenses_annual / withdraw_rate
    # 到达年数 = ln(1 + (FI-NW)×r / savings) / ln(1+r)
    real_return = return_rate - inflation
    years = log(1 + (fi_number - current_nw) * real_return / (savings_monthly * 12)) / log(1 + real_return)
    # 逐年资产预测
    for y in range(int(years) + 6):
        nw = nw * (1 + real_return) + savings_monthly * 12
```

### backtest.py — 定投回测引擎

```python
def simulate_dca(df, monthly_amount):
    monthly = df.groupby("month").first()  # 每月第一个交易日
    shares = sum(monthly_amount / price for each month)
    final_value = shares * last_price
    cagr = (final_value / total_invested) ** (1 / years) - 1
    # 最大回撤: 跟踪 peak → drawdown
```

### market_alert.py — 波动预警

```python
def check_alerts(threshold=3.0):
    # 获取持仓 → fetch prices → 筛选 |change%| >= threshold
def push_alerts(alerts):  # → 企微 webhook
```

### wecom_push.py — UTF-8 安全分块

```python
def _chunk_by_lines(text, max_bytes):
    # 按行累积，字节数控制。绝不在多字节字符中间截断
    # 单行超长 → 字符级回退。零丢字
```

---

## 3. 数据安全

| 措施 | 实现 |
|------|------|
| 代码/数据分离 | `FINANCE_DATA_DIR` 环境变量 |
| Demo 数据 | `finance_demo/` git 跟踪（John Doe 虚构） |
| 真实数据 | `finance/` gitignore |
| 密钥 | `.env` gitignore, `.env.example` 模板 |
| 私密信息 | `PRIVATE.md` gitignore |
| 日志 | `error.log` 循环写入, `*.log` gitignore |
| 推送 | 应用 API 直发，不经过第三方 |
| 文件锁 | 防 cron 重叠 |

---

## 4. 错误处理

| 场景 | 处理 |
|------|------|
| akshare 全挂 | 异常捕获，不崩溃（未来可加缓存兜底） |
| DeepSeek API 超时 | 120s timeout, 异常不阻塞推送 |
| 企微推送失败 | 双通道独立, 写入 error.log |
| 企微回调超时 | 异步线程，callback 立即返回空 |
| 并发写 SQLite | WAL mode + timeout=30s |
| cron 重叠 | `.runner.lock` 文件锁 |

---

## 5. 验证结果

```
✅ 24/24 检查通过（validate.py）
📁 配置路径、📊 行情数据、📱 推送模块
🔐 加解密、🌐 Flask 回调、💰 FIRE
📈 回测、🔒 运行安全、🚀 部署完整、🛡️ Git 安全
```

---

## 6. 请求审查的具体问题

### 架构
1. 回调用 `threading.Thread` 异步回复，永远返回空 200——这个设计有没有隐患？
2. `send_to_user` 的 token 用模块级字典缓存，多线程安全吗？
3. FIRE 的 `real_return = return_rate - inflation` 过于简化，有没有更好的模型？

### 安全
4. 应用 Secret 在 `wecom_app.py` 的模块级函数中从 `.env` 读取，有没有泄露风险？
5. 文件锁 `LOCK_FILE.touch()` + `unlink(missing_ok=True)` 在进程崩溃时会不会留死锁？

### 功能完备
6. 当前命令: 快照/体检/预警/FIRE/回测/走势/帮助——缺什么吗？
7. 定投回测只支持 3 年、每月 ¥2000，应该参数化吗？
8. 预警阈值固定 3%，是否应该按资产类型差异化？

### 下一步
9. 建议优先级: 多用户支持？自定义策略回测？税务优化？退休规划？
10. 还有什么明显的遗漏？
