"""
企业微信机器人推送模块
支持 Markdown，单条 4096 字符（远超 Server酱 500 字限制）
"""

import requests
import os
from pathlib import Path


def _get_webhook():
    key = os.environ.get("WECOM_WEBHOOK_KEY")
    if key:
        return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"

    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("WECOM_WEBHOOK_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"
    return None


def push_wecom(content: str) -> bool:
    """推送 Markdown 消息到企业微信"""
    url = _get_webhook()
    if not url:
        print("⚠️ 未配置 WECOM_WEBHOOK_KEY，跳过企微推送")
        return False

    # 企微限制 4096 字节（中文字≈3字节/字，实际约1300字）
    max_bytes = 4096
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > max_bytes:
        # 按字节截断
        trimmed = content_bytes[:max_bytes - 80]
        content = trimmed.decode("utf-8", errors="ignore").rstrip()
        content += "\n\n> ⚠️ 内容过长已截断"

    try:
        resp = requests.post(url, json={
            "msgtype": "markdown",
            "markdown": {"content": content}
        }, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            print("✅ 企微推送成功")
            return True
        else:
            print(f"⚠️ 企微推送失败: {data.get('errmsg', 'unknown')}")
            return False
    except Exception as e:
        print(f"⚠️ 企微推送异常: {e}")
        return False


def push_portfolio_snapshot(snapshot_file: str = None) -> bool:
    """推送市值快照"""
    from datetime import datetime

    if snapshot_file is None:
        snapshot_file = Path(__file__).parent.parent / "finance" / "portfolio_snapshot.md"

    try:
        with open(snapshot_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return push_wecom("📈 市值快照\n\n暂无数据，请先运行 `market_data.py`")

    now = datetime.now().strftime("%m/%d %H:%M")
    # 企微 Markdown 不支持表格，转成文本
    content = content.replace("|", "│")  # 用 │ 替代 | 避免格式冲突
    return push_wecom(f"## 📈 市值快照 {now}\n\n{content}")


def push_analysis(analysis_file: str, prompt_name: str = "") -> bool:
    """推送报告链接到企微——手机点链接即可查看完整报告"""
    from datetime import datetime

    # 构建 GitHub 链接（repo 需设为 private 以保护隐私）
    fname = Path(analysis_file).name
    github_url = f"https://github.com/Mote-Xu/AI_Financial_Assistant/blob/main/finance/{fname}"

    prompt_labels = {
        "monthly_review": "月度体检", "portfolio_rebalance": "再平衡",
        "insurance_audit": "保障审计", "market_event": "市场应急"
    }
    label = prompt_labels.get(prompt_name, prompt_name)
    now = datetime.now().strftime("%m/%d %H:%M")

    msg = f"## 📊 {label} {now}\n\n"
    msg += f"[👉 点击查看完整报告]({github_url})\n\n"
    msg += f"> 提示：报告已自动推送到 GitHub，随时可查看"

    return push_wecom(msg)

    # 清理 Markdown 格式 → 纯文本（企微不支持表格等复杂格式）
    text = re.sub(r"\|", "│", text)      # 表格竖线替换
    text = re.sub(r"#{2,4}\s+", "", text) # 去标题标记
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # 去粗体
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)  # 压缩空行
    text = text.strip()

    # 按 ~1000 字节切块（中文约 330 字/块，确保不超 4096 字节限制）
    MAX_BYTES = 3500  # 留余量
    chunks = []
    raw = text.encode("utf-8")
    pos = 0
    chunk_num = 0
    while pos < len(raw):
        chunk_num += 1
        end = min(pos + MAX_BYTES, len(raw))
        # 尽量在换行处切
        chunk_bytes = raw[pos:end]
        chunk_text = chunk_bytes.decode("utf-8", errors="ignore")
        # 回退到最后一个完整行
        if end < len(raw):
            last_nl = chunk_text.rfind("\n")
            if last_nl > len(chunk_text) // 2:
                chunk_text = chunk_text[:last_nl]
                end = pos + len(chunk_text.encode("utf-8"))

        header = f"📊 {label} ({chunk_num}/{chunk_num + max(1, (len(raw)-pos)//MAX_BYTES)}) | {now}\n\n"
        chunks.append(header + chunk_text.strip())
        pos = pos + len(chunk_text.encode("utf-8"))

    # 计算实际分块数
    total_chunks = len(chunks)
    for i, chunk in enumerate(chunks):
        # 更新正确的分块信息
        chunk = re.sub(r"\(\d+/\d+\)", f"({i+1}/{total_chunks})", chunk, count=1)
        ok = push_wecom(chunk)
        if not ok:
            print(f"  ⚠️ 第 {i+1}/{total_chunks} 块推送失败")
            return False
        if i < total_chunks - 1:
            import time
            time.sleep(0.5)  # 避免发太快被限流

    return True
