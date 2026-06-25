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
    """推送分析报告到企微——自包含的核心结论 + 关键数字 + 行动，看完即用"""
    import re
    from datetime import datetime

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return push_wecom(f"## 📊 分析完成\n\n报告已生成，请回电脑查看 `{Path(analysis_file).name}`")

    prompt_labels = {
        "monthly_review": "月度体检", "portfolio_rebalance": "再平衡",
        "insurance_audit": "保障审计", "market_event": "市场应急"
    }
    label = prompt_labels.get(prompt_name, prompt_name)
    now = datetime.now().strftime("%m/%d %H:%M")

    lines = [f"## {label} {now}", ""]

    # 关键数字（净资产、月结余、总盈亏）
    numbers = []
    for pat, tag in [
        (r"\*\*总资产\*\*[约]?[为]?\s*[¥￥]?([\d,.]+)万", "总资产"),
        (r"\*\*净资产\*\*[约]?[为]?\s*[¥￥]?([\d,.]+)万", "净资产"),
        (r"月\s*结\s*余[：:]\s*\*?\*?\+?\s*[¥￥]?([\d,]+)", "月结余"),
        (r"总\s*盈\s*亏[：:]\s*.*?[¥￥]([\d,]+)", "总盈亏"),
    ]:
        m = re.search(pat, text)
        if m:
            val = m.group(1).replace(",", "")
            numbers.append(f"{tag} ¥{val}")
    if numbers:
        lines.append(" | ".join(numbers))
        lines.append("")

    # 一句话总结
    m = re.search(r"\*\*一句话总结\*\*[：:]\s*(.+?)(?:\n|$)", text)
    if m:
        # 截短
        summary = m.group(1).strip()
        if len(summary) > 200:
            summary = summary[:195] + "..."
        lines.append(f"> 📌 {summary}")
        lines.append("")

    # 行动清单（带「为什么」）
    action_section = re.search(
        r"(?:###\s*|##\s*)6\.?\s*行动清单.*?\n(.+?)(?:\n---|\n## |\Z)",
        text, re.DOTALL
    )
    if action_section:
        lines.append("**🎯 行动**")
        # 按行动项拆解
        act_blocks = re.split(r"\n(?=\d+\.\s+\*\*)", action_section.group(1))
        for block in act_blocks[:3]:
            block = block.strip()
            # 取行动名
            m_name = re.match(r"\d+\.\s+\*\*(.+?)\*\*", block)
            if not m_name:
                continue
            name = m_name.group(1).strip()
            lines.append(f"- **{name}**")
            # 取操作
            m_op = re.search(r"\*\*操作\*\*[：:]\s*(.+?)(?:\n|$)", block)
            if m_op:
                op = m_op.group(1).strip()[:120]
                lines.append(f"  {op}")
            # 取原因
            m_why = re.search(r"\*\*为什么\*\*[：:]\s*(.+?)(?:\n|$)", block)
            if m_why:
                why = m_why.group(1).strip()[:150]
                lines.append(f"  *{why}*")
        lines.append("")

    msg = "\n".join(lines)
    return push_wecom(msg)
