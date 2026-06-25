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

    # 企微限制 4096 字符
    if len(content) > 4096:
        content = content[:4080] + "\n\n> ⚠️ 内容过长已截断"

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
    """推送分析报告到企微（提取关键摘要 + 完整要点）"""
    import re
    from datetime import datetime

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return push_wecom("📊 财务分析\n\n报告生成失败")

    # 构建精简 Markdown 报告
    parts = [f"## 📊 财务分析 [{prompt_name}]"]
    parts.append("")

    # 一句话总结
    m = re.search(r"\*\*一句话总结\*\*[：:]\s*(.+?)(?:\n|$)", content)
    if m:
        parts.append(f"> 📌 {m.group(1).strip()}")
        parts.append("")

    # 提取 6 大段落的标题 + 关键数字（不取全文，避免超 4096）
    sections = {
        "资产总览": r"(?:\*\*|###\s*)\d\.\s*资产总览",
        "现金流": r"(?:\*\*|###\s*)\d\.\s*现金流健康度",
        "投资组合": r"(?:\*\*|###\s*)\d\.\s*投资组合诊断",
        "保险保障": r"(?:\*\*|###\s*)\d\.\s*保险保障检查",
        "目标进度": r"(?:\*\*|###\s*)\d\.\s*目标进度",
    }

    for label, pattern in sections.items():
        block = re.search(pattern + r".*?(?=(?:\*\*|###\s*)\d\.|###\s*\d\.|\Z)", content, re.DOTALL)
        if block:
            text = block.group(0)
            # 清理格式，压缩长度
            text = re.sub(r"\n\s*\n", "\n", text)  # 去多余空行
            text = re.sub(r"[-*]\s+\*\*", "- **", text)  # 保持列表格式
            if len(text) > 600:
                text = text[:590] + "..."
            parts.append(f"**{label}**")
            parts.append(text.strip())
            parts.append("")

    # 行动清单
    action_section = re.search(r"(?:###\s*|##\s*)6\.?\s*行动清单.*?\n(.+?)(?:\n---|\n## |\Z)", content, re.DOTALL)
    if action_section:
        lines = action_section.group(1).strip().split("\n")
        parts.append("**🎯 本月行动**")
        for line in lines:
            line = line.strip()
            if re.match(r"\d\.", line) or line.startswith("-"):
                parts.append(f"> {line}")
            elif line.startswith("**") and "优先" in line:
                parts.append(f"\n{line}")
        parts.append("")

    now = datetime.now().strftime("%m/%d %H:%M")
    fname = Path(analysis_file).name
    parts.append(f"---\n📁 完整报告: `{fname}` | {now}")

    msg = "\n".join(parts)

    # 截断安全检查
    if len(msg) > 4000:
        msg = msg[:3980] + "\n\n> ⚠️ 报告过长已截断，完整版请查看本地文件"

    return push_wecom(msg)
