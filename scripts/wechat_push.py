"""
微信推送模块 — 通过 Server酱 发送通知
使用方法：
    from wechat_push import push_wechat
    push_wechat("标题", "内容")
"""

import requests
import os
from pathlib import Path

# Server酱 SendKey（从 .env 或环境变量读取）
def _get_sendkey():
    # 先查环境变量
    key = os.environ.get("SERVERCHAN_SENDKEY")
    if key:
        return key

    # 再查 .env 文件
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("SERVERCHAN_SENDKEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def push_wechat(title: str, content: str = "", short: str = "") -> bool:
    """
    推送消息到微信
    - title: 消息标题（必填）
    - content: 消息正文（可选，支持 Markdown）
    - short: 简短摘要（可选，通知栏显示）
    """
    sendkey = _get_sendkey()
    if not sendkey:
        print("⚠️ 未配置 SERVERCHAN_SENDKEY，跳过微信推送")
        return False

    url = f"https://sctapi.ftqq.com/{sendkey}.send"

    payload = {"title": title, "desp": content}
    if short:
        payload["short"] = short

    try:
        resp = requests.post(url, data=payload, timeout=10)
        data = resp.json()
        if data.get("code") == 0:
            print(f"✅ 微信推送成功: {title}")
            return True
        else:
            print(f"⚠️ 微信推送失败: {data.get('message', 'unknown')}")
            return False
    except Exception as e:
        print(f"⚠️ 微信推送异常: {e}")
        return False


def push_portfolio_snapshot(snapshot_file: str = None) -> bool:
    """推送市值快照摘要到微信"""
    from datetime import datetime

    if snapshot_file is None:
        snapshot_file = Path(__file__).parent.parent / "finance" / "portfolio_snapshot.md"

    try:
        with open(snapshot_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return push_wechat("📈 市值快照", "暂无数据，请先运行 market_data.py")

    # 提取关键数据
    lines = content.split("\n")
    summary_lines = []
    capture = False
    for line in lines:
        if "更新时间" in line:
            summary_lines.append(line.strip())
        if "总市值" in line:
            summary_lines.append("\n" + line.strip())
            break

    now = datetime.now().strftime("%m/%d %H:%M")
    return push_wechat(
        title=f"📈 市值快照 {now}",
        content="\n".join(summary_lines) + "\n\n" + content,
        short=f"总市值已更新 {now}",
    )


def push_analysis_summary(analysis_file: str, prompt_name: str = "") -> bool:
    """推送分析报告摘要到微信（提取关键信息，避免超长截断）"""
    import re
    from datetime import datetime

    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return push_wechat("📊 分析报告", "报告生成失败")

    # 提取摘要：资产、现金流、Top 3 行动
    summary_parts = []

    # 提取"一句话总结"
    m = re.search(r"\*\*一句话总结\*\*[：:]\s*(.+?)(?:\n|$)", content)
    if m:
        summary_parts.append(f"📌 {m.group(1).strip()}")

    # 提取行动清单
    action_section = re.search(r"(?:### |## )\s*6\.?\s*行动清单.*?\n(.+?)(?:\n---|\n## |\Z)", content, re.DOTALL)
    if action_section:
        actions = re.findall(r"\d+\.\s+\*\*(.+?)\*\*", action_section.group(1))
        if actions:
            summary_parts.append("\n🎯 本月行动：")
            for a in actions[:3]:
                summary_parts.append(f"  • {a}")

    summary = "\n".join(summary_parts) if summary_parts else content[:400] + "..."

    # 加文件路径提示
    fname = Path(analysis_file).name
    summary += f"\n\n📁 完整报告: {fname}"

    now = datetime.now().strftime("%m/%d %H:%M")
    return push_wechat(
        title=f"📊 [{prompt_name}] {now}",
        content=summary,
        short=f"财务分析已生成 {now}",
    )


# CLI 入口：python scripts/wechat_push.py "标题" "内容"
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        title = sys.argv[1]
        content = sys.argv[2] if len(sys.argv) > 2 else ""
        push_wechat(title, content)
    else:
        print("用法: python wechat_push.py '标题' '内容'")
