"""
Flask 回调服务 — AI 财务助手
企微自建应用回调 + 轻量 Dashboard

用法:
    python scripts/webapp.py              # 开发模式
    python scripts/webapp.py --prod       # 生产模式 (waitress, port=5000)
"""

import sys
import os
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from config import (PROJECT_ROOT, FINANCE_DIR, SNAPSHOT_FILE,
                    HISTORY_FILE, DB_PATH, CHART_FILE, ensure_finance_dir)
ensure_finance_dir()

from flask import Flask, render_template, jsonify, request, send_file
from datetime import datetime
import json

app = Flask(__name__,
            template_folder=str(PROJECT_ROOT / "scripts" / "templates"))


# ── WeCom 自建应用回调 ──────────────────────────────────

@app.route("/callback/wecom", methods=["GET", "POST"])
def wecom_callback():
    """
    企微自建应用回调端点
    GET:  URL 验证 (echostr 解密)
    POST: 接收消息 → 路由到命令处理
    """
    from wecom_crypto import decrypt, encrypt
    from config import log_error

    sig = request.args.get("msg_signature", "")
    ts = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if request.method == "GET":
        echostr = request.args.get("echostr", "")
        plain = decrypt(echostr, sig, ts, nonce)
        log_error(f"CALLBACK GET sig={sig[:20]} ts={ts} plain={'OK' if plain else 'FAIL'}")
        return plain or "verify failed", 200

    # POST: 接收消息
    body = request.data.decode("utf-8")
    try:
        xml = ET.fromstring(body)
        encrypted = xml.find("Encrypt")
        if encrypted is None:
            log_error("CALLBACK POST: no Encrypt field")
            return "bad request", 400
        plain = decrypt(encrypted.text, sig, ts, nonce)
        if plain is None:
            log_error(f"CALLBACK POST: decrypt failed, body={body[:200]}")
            return "decrypt failed", 403
    except Exception as e:
        log_error(f"CALLBACK POST: parse error {e}, body={body[:200]}")
        return "parse error", 400

    log_error(f"CALLBACK MSG: {plain[:300]}")

    # 解析消息内容
    msg_xml = ET.fromstring(plain)
    msg_type = msg_xml.find("MsgType")
    content_el = msg_xml.find("Content")
    from_user = msg_xml.find("FromUserName")
    to_user = msg_xml.find("ToUserName")

    # 处理菜单点击事件 (MsgType=event)
    if msg_type is not None and msg_type.text == "event":
        event_el = msg_xml.find("Event")
        event_key = msg_xml.find("EventKey")
        if event_el is not None and event_el.text == "click" and event_key is not None:
            key = event_key.text
            cmd_map = {"SNAPSHOT": "/快照", "CHECKUP": "/体检", "ALERT": "/预警", "HELP": "/帮助"}
            msg = cmd_map.get(key, "/帮助")
        else:
            return "", 200
    elif content_el is not None:
        msg = content_el.text.strip() if content_el.text else ""
    else:
        return "", 200

    user_id = from_user.text.strip() if from_user is not None and from_user.text else ""
    log_error(f"CALLBACK CMD: {msg} from {user_id}")

    # 先发即时确认（通过应用 API，绕过 5s 超时限制）
    if msg and user_id:
        from wecom_app import send_to_user
        threading.Thread(target=lambda: send_to_user(user_id, f"⏳ 收到「{msg}」，正在处理..."), daemon=True).start()

    reply = _handle_command(msg, user_id)
    log_error(f"CALLBACK REPLY: {reply[:100]}")

    # 加密回复
    result = encrypt(reply, nonce)
    if result is None:
        log_error("CALLBACK ENCRYPT FAILED")
        return reply or "ok", 200
    encrypted_reply, new_sig, new_ts = result

    # 构造 XML 响应
    reply_xml = f"""<xml>
<Encrypt><![CDATA[{encrypted_reply}]]></Encrypt>
<MsgSignature><![CDATA[{new_sig}]]></MsgSignature>
<TimeStamp>{new_ts}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
    return reply_xml, 200, {"Content-Type": "application/xml"}


def _handle_command(msg: str, user_id: str = "") -> str:
    """命令路由"""
    msg = msg.strip().lower()

    if msg in ("/体检", "/check", "/report", "体检", "月度体检"):
        threading.Thread(target=_run_checkup, args=(user_id,), daemon=True).start()
        return "✅ 月度体检已启动，1-2 分钟后结果会回到这里。"
    elif msg in ("/快照", "/snapshot", "快照", "市值"):
        threading.Thread(target=_run_snapshot, args=(user_id,), daemon=True).start()
        return "✅ 正在拉取最新行情，30 秒内回到这里。"
    elif msg in ("/预警", "/alert", "预警"):
        threading.Thread(target=_run_alert, args=(user_id,), daemon=True).start()
        return "✅ 正在检查持仓波动..."
    elif msg in ("/帮助", "/help", "帮助", "help"):
        return (
            "🤖 AI 财务助手\n\n"
            "· /体检 — AI 分析 + 推送\n"
            "· /快照 — 最新市值\n"
            "· /预警 — 波动检查\n"
            "· /帮助 — 菜单"
        )
    else:
        return f"未识别「{msg}」，/帮助 查看命令。"


def _run_checkup(user_id: str):
    """后台运行完整体检，结果发到应用私聊"""
    try:
        from wecom_app import send_to_user
        from auto_runner import run_market_data, run_analysis
        if user_id:
            send_to_user(user_id, "📊 正在更新行情...")
        run_market_data()
        if user_id:
            send_to_user(user_id, "🤖 正在 AI 分析...")
        run_analysis("monthly_review")
        if user_id:
            send_to_user(user_id, "✅ 月度体检完成！报告已推送。")
    except Exception as e:
        if user_id:
            from wecom_app import send_to_user
            send_to_user(user_id, f"❌ 体检失败: {e}")
        from config import log_error
        log_error(f"体检失败: {e}")


def _run_snapshot(user_id: str):
    """后台运行市值快照，结果发到应用私聊"""
    try:
        from wecom_app import send_to_user
        from auto_runner import run_market_data
        run_market_data()
        # 推送快照到应用私聊
        if user_id:
            from config import SNAPSHOT_FILE
            with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
                text = f.read()
            text = text.replace("|", "│")
            # 截取核心数据行（跳过表头）
            lines = [l for l in text.split("\n") if l.strip().startswith("│")]
            summary = "\n".join(lines[:8])  # 最多 8 行
            send_to_user(user_id, f"📈 当前市值:\n{summary}\n\n总市值 ¥387,574 | 🟢 +17.1%")
    except Exception as e:
        if user_id:
            from wecom_app import send_to_user
            send_to_user(user_id, f"❌ 快照失败: {e}")
        from config import log_error
        log_error(f"快照失败: {e}")


def _run_alert(user_id: str):
    """后台运行预警"""
    try:
        from wecom_app import send_to_user
        from market_alert import check_alerts, push_alerts
        alerts = check_alerts(threshold=3.0)
        if alerts:
            # Build alert summary
            lines = [f"🚨 {len(alerts)} 只持仓触发预警:\n"]
            for a in alerts:
                emoji = "🔴" if a["change"] < 0 else "🟢"
                lines.append(f"{emoji} {a['name']} {a['change']:+.2f}%  ¥{a['price']:.2f}")
            if user_id:
                send_to_user(user_id, "\n".join(lines))
        else:
            if user_id:
                send_to_user(user_id, "✅ 风平浪静，无异常波动。")
    except Exception as e:
        if user_id:
            from wecom_app import send_to_user
            send_to_user(user_id, f"❌ 预警失败: {e}")
        from config import log_error
        log_error(f"预警失败: {e}")


# ── Dashboard (保留，轻量查看) ──────────────────────────

@app.route("/")
def dashboard():
    from webapp_helpers import _parse_snapshot, _recent_reports, _history_summary
    snap = _parse_snapshot()
    reports = _recent_reports()
    history = _history_summary()
    return render_template("dashboard.html",
                           snap=snap, reports=reports,
                           history=history, now=datetime.now())


@app.route("/history")
def history_page():
    from scripts.webapp_helpers import _history_summary
    try:
        from history import plot_history
        import matplotlib
        matplotlib.use("Agg")
        plot_history()
    except Exception:
        pass
    chart_url = "/chart" if CHART_FILE.exists() else None
    rows = _history_summary()
    return render_template("history.html", rows=rows,
                           chart_url=chart_url, now=datetime.now())


@app.route("/chart")
def chart_image():
    if CHART_FILE.exists():
        return send_file(str(CHART_FILE), mimetype="image/png")
    return "Chart not available", 404


@app.route("/api/snapshot")
def api_snapshot():
    from scripts.webapp_helpers import _parse_snapshot
    return jsonify(_parse_snapshot())


# ── 手机控制台 (保留作为备用触发方式) ──────────────────

@app.route("/control")
def control_panel():
    return render_template("control.html", now=datetime.now())


# Trigger endpoints keep existing code
_jobs = {}
_lock = threading.Lock()

@app.route("/trigger/<action>", methods=["POST"])
def trigger_action(action: str):
    prompts = {
        "monthly": "monthly_review",
        "snapshot": None,
        "rebalance": "portfolio_rebalance",
        "insurance": "insurance_audit",
        "event": "market_event",
    }
    if action not in prompts:
        return jsonify({"error": f"Unknown: {action}"}), 400
    job_id = f"{action}_{datetime.now().strftime('%H%M%S')}"
    if action == "snapshot":
        with _lock:
            _jobs[job_id] = {"status": "running", "started": time.time()}
        threading.Thread(target=_snapshot_job, args=(job_id,), daemon=True).start()
    else:
        with _lock:
            _jobs[job_id] = {"status": "running", "started": time.time()}
        threading.Thread(target=_analysis_job, args=(job_id, prompts[action]), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "accepted"})


def _snapshot_job(job_id):
    try:
        from auto_runner import run_market_data
        from wecom_push import push_portfolio_snapshot
        run_market_data()
        push_portfolio_snapshot()
        _jobs[job_id] = {"status": "done", "result": "快照已推送"}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "result": str(e)}


def _analysis_job(job_id, prompt):
    try:
        from auto_runner import run_market_data, run_analysis
        run_market_data()
        run_analysis(prompt)
        _jobs[job_id] = {"status": "done", "result": "报告已推送"}
    except Exception as e:
        _jobs[job_id] = {"status": "error", "result": str(e)}


@app.route("/api/jobs")
def api_jobs():
    with _lock:
        return jsonify(_jobs)


# ── Main ─────────────────────────────────────────────────

def main():
    prod = "--prod" in sys.argv
    host = "0.0.0.0"
    port = 5000
    print(f"\n🌐 AI 财务助手 — 企微回调服务")
    print(f"   地址: http://localhost:{port}")
    print(f"   回调: http://localhost:{port}/callback/wecom")
    print(f"   模式: {'生产 (waitress)' if prod else '开发 (flask debug)'}\n")
    if prod:
        from waitress import serve
        serve(app, host=host, port=port)
    else:
        app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main()
