"""
企业微信机器人推送模块
- 文本消息：Markdown，单条 4096 字节
- 文件直发：上传文件 → 发送附件，手机直接打开（无需 GitHub 登录）
- 图片消息：支持 base64 图片发送

企微机器人 Webhook API:
- 文本: POST /webhook/send?key=KEY  msgtype=markdown
- 文件: POST /webhook/upload_media?key=KEY&type=file → media_id
         POST /webhook/send?key=KEY  msgtype=file
- 图片: POST /webhook/send?key=KEY  msgtype=image (base64)
"""

import requests
import os
import base64
from pathlib import Path

from config import SNAPSHOT_FILE


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


def upload_file_to_wecom(file_path: str) -> str | None:
    """
    上传文件到企微机器人，返回 media_id
    media_id 有效期 3 天，仅当天有效上传的文件可发送
    文件大小限制：20MB（Markdown 报告通常 < 50KB，远低于限制）
    """
    webhook_url = _get_webhook()
    if not webhook_url:
        print("⚠️ 未配置 WECOM_WEBHOOK_KEY，跳过文件上传")
        return None

    # 从 send URL 推导 upload URL
    # send:    https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=KEY
    # upload:  https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=KEY&type=file
    upload_url = webhook_url.replace("/send?", "/upload_media?") + "&type=file"

    file_name = Path(file_path).name
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                upload_url,
                files={"media": (file_name, f, "application/octet-stream")},
                timeout=30,
            )
        data = resp.json()
        if data.get("errcode") == 0:
            media_id = data.get("media_id")
            print(f"📤 文件上传成功: {file_name} (media_id={media_id[:8]}...)")
            return media_id
        else:
            print(f"⚠️ 文件上传失败: {data.get('errmsg', 'unknown')}")
            return None
    except Exception as e:
        print(f"⚠️ 文件上传异常: {e}")
        return None


def push_file(file_path: str) -> bool:
    """
    上传文件并推送到企微 — 手机端可直接下载打开
    返回 True/False 表示是否成功
    """
    media_id = upload_file_to_wecom(file_path)
    if not media_id:
        return False

    url = _get_webhook()
    if not url:
        return False

    file_name = Path(file_path).name
    try:
        resp = requests.post(url, json={
            "msgtype": "file",
            "file": {"media_id": media_id},
        }, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            print(f"✅ 文件推送成功: {file_name}")
            return True
        else:
            print(f"⚠️ 文件推送失败: {data.get('errmsg', 'unknown')}")
            return False
    except Exception as e:
        print(f"⚠️ 文件推送异常: {e}")
        return False


def push_image(image_path: str = None, image_base64: str = None, md5: str = None) -> bool:
    """
    推送图片到企微 — 支持 base64 或文件路径
    图片大小限制：base64 编码后不超过 2MB
    """
    url = _get_webhook()
    if not url:
        print("⚠️ 未配置 WECOM_WEBHOOK_KEY，跳过图片推送")
        return False

    if image_path:
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        import hashlib
        md5 = hashlib.md5(open(image_path, "rb").read()).hexdigest()

    if not image_base64:
        print("⚠️ 未提供图片数据")
        return False

    try:
        payload = {
            "msgtype": "image",
            "image": {
                "base64": image_base64,
                "md5": md5 or "",
            },
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if data.get("errcode") == 0:
            print("✅ 图片推送成功")
            return True
        else:
            print(f"⚠️ 图片推送失败: {data.get('errmsg', 'unknown')}")
            return False
    except Exception as e:
        print(f"⚠️ 图片推送异常: {e}")
        return False


def push_portfolio_snapshot(snapshot_file: str = None) -> bool:
    """推送市值快照"""
    from datetime import datetime

    if snapshot_file is None:
        snapshot_file = str(SNAPSHOT_FILE)

    try:
        with open(snapshot_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return push_wecom("📈 市值快照\n\n暂无数据，请先运行 `market_data.py`")

    now = datetime.now().strftime("%m/%d %H:%M")
    # 企微 Markdown 不支持表格，转成文本
    content = content.replace("|", "│")  # 用 │ 替代 | 避免格式冲突
    return push_wecom(f"## 📈 市值快照 {now}\n\n{content}")


def _extract_summary_from_report(file_path: str, max_lines: int = 15) -> str:
    """从分析报告中提取摘要（前几行关键内容），用于企微文本消息预览"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        summary_lines = []
        in_header = True
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过 YAML front matter 和标题行
            if line.startswith("# ") or line.startswith("> "):
                if in_header:
                    summary_lines.append(line)
                    continue
            in_header = False
            # 收集正文（跳过标题标记）
            if line.startswith("## "):
                summary_lines.append(line)
            elif line.startswith("**") or line.startswith("- **"):
                summary_lines.append(line)
            elif len(summary_lines) >= max_lines:
                break

        return "\n".join(summary_lines) if summary_lines else "报告已生成，详情请下载附件查看"
    except Exception:
        return "报告已生成，详情请下载附件查看"


def _chunk_by_lines(text: str, max_bytes: int) -> list:
    """
    UTF-8 安全分块 — 按行累积，绝不在多字节字符中间截断。

    策略:
    1. 逐行累加，跟踪字节数（\n 换行符计入）
    2. 超限 → flush 当前块，开始新块
    3. 单行超长（罕见）→ 按字符回退到安全边界
    """
    # 保留原始末尾换行符 mark，用于精确重建
    ends_with_nl = text.endswith("\n")
    lines = text.split("\n")
    # 去掉 split 产生的末尾空串，后面重建时加回
    if ends_with_nl and lines and lines[-1] == "":
        lines.pop()

    chunks = []
    current_lines = []
    current_bytes = 0

    for i, line in enumerate(lines):
        is_last = (i == len(lines) - 1)
        nl_bytes = 1 if (not is_last or ends_with_nl) else 0
        line_bytes = len(line.encode("utf-8")) + nl_bytes

        if current_bytes + line_bytes > max_bytes and current_lines:
            # flush — 中间块保留末尾 \n（原文中这些行之间有换行）
            chunks.append("\n".join(current_lines) + "\n")
            current_lines = []
            current_bytes = 0

        if line_bytes - nl_bytes > max_bytes:
            # 单行超长 — 逐段切割直到耗尽
            remaining = line
            while remaining:
                safe = ""
                for ch in remaining:
                    if len((safe + ch).encode("utf-8")) > max_bytes - 1:
                        break
                    safe += ch
                chunks.append(safe)
                remaining = remaining[len(safe):]
        else:
            current_lines.append(line)
            current_bytes += line_bytes

    if current_lines:
        chunk = "\n".join(current_lines)
        if ends_with_nl:
            chunk += "\n"
        chunks.append(chunk)

    return chunks


def push_analysis(analysis_file: str, prompt_name: str = "",
                  send_file: bool = False) -> bool:
    """
    推送分析报告全文到企微 — 直接在手机企微里阅读

    超长内容按行分块，UTF-8 安全，绝不丢字。
    """
    from datetime import datetime

    prompt_labels = {
        "monthly_review": "月度体检", "portfolio_rebalance": "再平衡",
        "insurance_audit": "保障审计", "market_event": "市场应急"
    }
    label = prompt_labels.get(prompt_name, prompt_name)
    now = datetime.now().strftime("%m/%d %H:%M")

    # 读取报告
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return push_wecom(f"## 📊 {label} {now}\n\n报告生成完成，请稍后查看")

    # 清理格式
    text = raw.replace("|", "│")  # │ 防止表格被解析
    import re
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.strip()

    # 分块（3500 字节/块，留余量给 header）
    chunks = _chunk_by_lines(text, max_bytes=3500)
    total = len(chunks)

    import time
    ok_count = 0
    for i, chunk in enumerate(chunks):
        header = f"## 📊 {label}"
        if total > 1:
            header += f" ({i + 1}/{total})"
        header += f" | {now}\n\n"
        msg = header + chunk
        if push_wecom(msg):
            ok_count += 1
        else:
            print(f"  ⚠️ 第 {i + 1}/{total} 块推送失败")
        if i < total - 1:
            time.sleep(0.5)

    print(f"📱 企微报告推送: {ok_count}/{total} 块成功")
    return ok_count == total
