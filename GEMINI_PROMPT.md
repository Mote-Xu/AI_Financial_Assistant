# AI 财务助手 — 项目总结（发给外部 AI）

> 发给 Gemini / ChatGPT，请求审查已实现功能的正确性和完备性。
> 最后更新：2026-06-26

---

## 项目概况

AI 财务助手 — 个人理财分析系统。Claude Code CLI 交互 + DeepSeek API 分析 + akshare 行情 + SQLite 存储。

GitHub: `github.com/Mote-Xu/AI_Financial_Assistant`（public，demo 数据，代码与数据分离）

## 请求审查

**重点审查以下方面的正确性和完备性，指出漏洞、边界情况和改进建议。**

---

## 1. 代码与数据分离架构

### config.py（集中路径配置）

```python
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

_env_dir = os.getenv("FINANCE_DATA_DIR", "")
if _env_dir:
    _p = Path(_env_dir)
    if _p.is_absolute():
        FINANCE_DIR = _p
    else:
        FINANCE_DIR = PROJECT_ROOT / _env_dir
else:
    FINANCE_DIR = PROJECT_ROOT / "finance_demo"

FINANCE_DIR.mkdir(parents=True, exist_ok=True)  # ← 副作用：import 时自动建目录

ASSETS_FILE = FINANCE_DIR / "assets.md"
INCOME_FILE = FINANCE_DIR / "income.md"
# ... 等 9 个便捷路径
```

### .gitignore

```
PRIVATE.md
.env
finance/                     # ← 真实数据目录，整体 ignore
finance_demo/finance_data.db # ← 自动生成二进制，不留 git
finance_demo/history_chart.png
```

### ✅ 审查点
- `FINANCE_DIR.mkdir` 在 import 时执行，是否有隐患？
- 真实数据模式下，有没有可能通过某个脚本的 error log 或临时文件泄露路径内容？
- `finance_demo/` 下的 `.md` 文件如果在真实模式下被误写，是否会被 git 追踪到？（答案：不会，写入走 FINANCE_DIR，而真实模式指向 `finance/`）
- 有什么边界情况是 `_env_dir` 判断逻辑遗漏的？

---

## 2. 推送架构（企微 + 微信双通道）

### 核心原则：报告全文直接发到手机，不用下载、不经过 GitHub

### wecom_push.py — 企微推送（分块）

```python
def _clean_for_wecom(text: str) -> str:
    text = text.replace("|", "│")           # 防止表格被解析
    text = re.sub(r"\n{4,}", "\n\n\n", text) # 压缩空行
    return text.strip()

def push_analysis(analysis_file, prompt_name="", send_file=False):
    # 1. 读取报告
    # 2. _clean_for_wecom() 清理格式
    # 3. 按 3500 字节分块（企微限制 4096 字节/条）
    # 4. 逐块发送 markdown 消息
    # 5. 块间 sleep 0.5s 防限流
```

分块逻辑细节：
```python
MAX_BYTES = 3500  # 留余量给分块标记 "(1/3)" 等
body_bytes = text.encode("utf-8")
while pos < total_bytes:
    end = min(pos + MAX_BYTES, total_bytes)
    chunk_text = body_bytes[pos:end].decode("utf-8", errors="ignore")
    # 回退到最后一个完整行
    if end < total_bytes:
        last_nl = chunk_text.rfind("\n")
        if last_nl > len(chunk_text) // 2:
            chunk_text = chunk_text[:last_nl]
    chunks.append(chunk_text.strip())
```

### wechat_push.py — 微信推送（Server酱）

```python
def push_analysis_summary(analysis_file, prompt_name=""):
    content = _clean_for_wechat(raw)
    max_bytes = 28000  # Server酱建议上限
    if len(content.encode("utf-8")) > max_bytes:
        content = content_bytes[:max_bytes - 100].decode("utf-8", errors="ignore")
        content += "\n\n...\n> 内容过长已截断"
    return push_wechat(title=title, content=content, short=f"财务报告已生成 {now}")
```

### auto_runner.py — 双通道独立发送

```python
# 企微 + 微信各自发送，一个挂了不影响另一个
try:
    push_analysis(str(output_path), prompt_name=prompt_name)
    print("📱 企微推送完成")
except Exception as e:
    print(f"⚠️ 企微推送失败: {e}")

try:
    push_analysis_summary(str(output_path), prompt_name=prompt_name)
    print("📱 微信推送完成")
except Exception as e:
    print(f"⚠️ 微信推送失败: {e}")
```

### ✅ 审查点
- 企微分块：`bytes.decode("utf-8", errors="ignore")` 在边界处会不会丢字？`rfind("\n")` 回退逻辑是否正确？
- Server酱 28KB 截断：`content_bytes[:max_bytes - 100]` 然后 decode，会不会在 UTF-8 多字节字符中间截断导致乱码？
- 两个 `_clean_for_wecom` 函数（分别存在 wecom_push 和 wechat_push）是重复代码，是否需要抽到 config？
- 如果企微或微信某一方挂了（比如 webhook 过期），错误处理够吗？会不会静默丢失报告？

---

## 3. 数据流与隐私

### 完整数据流

```
assets.md / income.md / ... (本地 Markdown)
    ↓
market_data.py → akshare API (公开行情)
    ↓
portfolio_snapshot.md + history.csv + SQLite (本地)
    ↓
deepseek_analysis.py → DeepSeek API (分析请求含完整财务数据)
    ↓
analysis_*.md (本地)
    ↓
wecom_push.py → 企微 Webhook (报告全文)
wechat_push.py → Server酱 (报告全文)
```

### ✅ 审查点
- 分析时把完整财务数据（持仓+金额+目标）发给 DeepSeek API，隐私风险如何评估？是否需要做数据脱敏再发送？
- akshare 是公开行情接口，请求内容（股票代码列表）是否可能被关联到个人身份？
- Server酱 作为第三方推送服务，报告全文经过其服务器，是否可接受？
- 有没有我们没考虑到的数据泄露点？（比如 Python exception log 可能打印文件路径/内容）

---

## 4. 功能完备性

### 当前已实现

| 模块 | 功能 |
|------|------|
| market_data.py | ETF + A股 + 基金净值，eastmoney/Sina 双源，代理 fallback |
| deepseek_analysis.py | 4 类提示词分析，流式输出，120s timeout |
| auto_runner.py | 行情→分析→推送 全自动流水线 |
| market_alert.py | 持仓单日涨跌超阈值自动推送（默认 ±3%） |
| history.py | CSV 历史 + matplotlib 图表 |
| database.py | SQLite: holdings/prices/snapshots/analysis_log |
| wecom_push.py | 企微 Markdown + 分块报告 + 图片 + 文件上传 |
| wechat_push.py | Server酱 微信推送，完整报告卡片 |

### 尚未实现

- Flask Dashboard + cloudflared tunnel
- 企微双向互动（@机器人 → Flask 回调）
- FIRE 模拟器
- 定投回测
- Ubuntu 24/7 部署

### ✅ 审查点
- 现有功能有没有明显的理财分析维度遗漏？（比如：税务优化、退休规划、教育金…）
- market_alert.py 的阈值是固定 3%，是否应该根据资产类型差异化？（个股波动大、债券波动小）
- auto_runner.py 错误处理：如果 market_data 成功但 analysis 失败，用户收到什么？如果 analysis 成功但推送失败呢？
- SQLite 写入是否有并发问题？定时任务重叠执行会不会崩？
- Windows 任务计划 vs cron：当前仅 Windows bat 文件，有没有考虑过锁文件防止重复执行？

---

## 5. 错误处理 & 鲁棒性

### 现有措施
- 代理清理：启动时清除 `HTTP_PROXY` 等环境变量
- 双源 fallback：eastmoney 被拦自动切 Sina
- 推送容错：企微失败不影响微信，反之亦然
- DeepSeek API timeout=120s
- 编码：`PYTHONIOENCODING=utf-8`

### ✅ 审查点
- 如果 akshare API 完全挂了（两个源都不可用），系统会怎样？是否需要加入本地缓存/上次数据兜底？
- 如果 DeepSeek API 返回空/超时/乱码，分析结果怎么处理？
- auto_runner 和 market_alert 如果同时被 cron 触发，SQLite 会有锁冲突吗？
- 大量持仓（比如 50+ 只股票）时，akshare 请求会被限流吗？有没有处理？

---

## 6. 下一步优先级

当前待做：
1. Flask Dashboard + cloudflared tunnel
2. 企微双向互动（@机器人 → Flask 回调）
3. FIRE 模拟器
4. 定投回测
5. Ubuntu 24/7 部署

请审查这个优先级排序，并指出是否应该加入其他功能。

---

## 附：项目结构

```
AI_Financial_Assistant/
├── finance_demo/            ← Demo 数据（git 跟踪）
├── finance/                 ← 🔒 真实数据（gitignore）
├── scripts/
│   ├── config.py            ← 集中路径配置
│   ├── market_data.py       ← 行情拉取
│   ├── deepseek_analysis.py ← DeepSeek 分析
│   ├── auto_runner.py       ← 全自动流水线
│   ├── market_alert.py      ← 波动预警
│   ├── history.py           ← 历史 + 图表
│   ├── database.py          ← SQLite 引擎
│   ├── wecom_push.py        ← 企微推送（分块）
│   └── wechat_push.py       ← 微信推送（Server酱）
├── prompts/                 ← 4 类分析提示词
├── .env.example             ← 配置模板
└── .gitignore
```
