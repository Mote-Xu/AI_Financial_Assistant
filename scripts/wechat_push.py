"""
微信推送模块 — 通过 Server酱 发送通知
使用方法：
    from wechat_push import push_wechat
    push_wechat("标题", "内容")
"""

import requests
import os
from pathlib import Path

from config import SNAPSHOT_FILE, get_finance_dir_name

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
        snapshot_file = str(SNAPSHOT_FILE)

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


def _clean_for_wechat(text: str) -> str:
    """清理 Markdown 格式以适应微信显示"""
    text = text.replace("|", "│")
    import re
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def push_analysis_summary(analysis_file: str, prompt_name: str = "") -> bool:
    """
    推送分析报告全文到微信（Server酱）
    微信端直接点击消息卡片即可阅读完整报告，无需下载文件
    超长内容自动截断 + GitHub 链接备份
    """
    from datetime import datetime
    fname = Path(analysis_file).name
    dir_name = get_finance_dir_name()
    github_url = f"https://github.com/Mote-Xu/AI_Financial_Assistant/blob/main/{dir_name}/{fname}"
    now = datetime.now().strftime("%m/%d %H:%M")

    prompt_labels = {
        "monthly_review": "月度体检", "portfolio_rebalance": "再平衡",
        "insurance_audit": "保障审计", "market_event": "市场应急"
    }
    label = prompt_labels.get(prompt_name, prompt_name)

    # 读取报告全文
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return push_wechat(f"📊 {label} {now}", "报告已生成，请稍后查看")

    # 清理格式 + 截断（Server酱建议不超过 30KB）
    content = _clean_for_wechat(raw)
    max_bytes = 28000
    content_bytes = content.encode("utf-8")
    if len(content_bytes) > max_bytes:
        content = content_bytes[:max_bytes - 200].decode("utf-8", errors="ignore")
        content += f"\n\n...\n> ⚠️ 内容过长已截断\n> 👉 [查看完整报告]({github_url})"

    title = f"📊 {label}—{now}"

    return push_wechat(
        title=title,
        content=content,
        short=f"财务报告已生成 {now}",
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
