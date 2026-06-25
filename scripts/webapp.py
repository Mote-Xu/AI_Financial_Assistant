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

    sig = request.args.get("msg_signature", "")
    ts = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if request.method == "GET":
        # URL 验证
        echostr = request.args.get("echostr", "")
        plain = decrypt(echostr, sig, ts, nonce)
        return plain or "verify failed", 200

    # POST: 接收消息
    body = request.data.decode("utf-8")
    try:
        xml = ET.fromstring(body)
        encrypted = xml.find("Encrypt")
        if encrypted is None:
            return "bad request", 400
        plain = decrypt(encrypted.text, sig, ts, nonce)
        if plain is None:
            return "decrypt failed", 403
    except Exception:
        return "parse error", 400

    # 解析消息内容
    msg_xml = ET.fromstring(plain)
    msg_type = msg_xml.find("MsgType")
    content_el = msg_xml.find("Content")
    from_user = msg_xml.find("FromUserName")
    to_user = msg_xml.find("ToUserName")

    if msg_type is None or content_el is None:
        return "", 200  # 空回复

    msg = content_el.text.strip() if content_el.text else ""
    reply = _handle_command(msg)

    # 加密回复
    encrypted_reply, new_sig, new_ts = encrypt(reply, nonce)

    # 构造 XML 响应
    reply_xml = f"""<xml>
<Encrypt><![CDATA[{encrypted_reply}]]></Encrypt>
<MsgSignature><![CDATA[{new_sig}]]></MsgSignature>
<TimeStamp>{new_ts}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
    return reply_xml, 200, {"Content-Type": "application/xml"}


def _handle_command(msg: str) -> str:
    """命令路由"""
    msg = msg.strip().lower()

    if msg in ("/体检", "/check", "/report", "体检", "月度体检"):
        thread = threading.Thread(target=_run_checkup, daemon=True)
        thread.start()
        return "✅ 月度体检已启动，预计 1-2 分钟后报告将推送到您的手机。请留意消息。"
    elif msg in ("/快照", "/snapshot", "快照", "市值"):
        thread = threading.Thread(target=_run_snapshot, daemon=True)
        thread.start()
        return "✅ 市值快照已启动，即将推送到您的手机。"
    elif msg in ("/预警", "/alert", "预警"):
        thread = threading.Thread(target=_run_alert, daemon=True)
        thread.start()
        return "✅ 正在检查市场波动..."
    elif msg in ("/帮助", "/help", "帮助", "help"):
        return (
            "🤖 AI 财务助手 支持以下命令：\n\n"
            "· /体检 — 更新行情 + AI 分析 + 推送报告\n"
            "· /快照 — 推送最新市值快照\n"
            "· /预警 — 检查持仓波动\n"
            "· /帮助 — 显示本菜单"
        )
    else:
        return (
            f"未识别的命令：「{msg}」\n"
            "发送 /帮助 查看可用命令。"
        )


def _run_checkup():
    """后台运行完整体检"""
    try:
        from auto_runner import run_market_data, run_analysis
        run_market_data()
        run_analysis("monthly_review")
    except Exception as e:
        from config import log_error
        log_error(f"体检失败: {e}")


def _run_snapshot():
    """后台运行市值快照"""
    try:
        from auto_runner import run_market_data
        from wecom_push import push_portfolio_snapshot
        run_market_data()
        push_portfolio_snapshot()
    except Exception as e:
        from config import log_error
        log_error(f"快照失败: {e}")


def _run_alert():
    """后台运行预警"""
    try:
        from market_alert import check_alerts, push_alerts
        alerts = check_alerts(threshold=3.0)
        if alerts:
            push_alerts(alerts, threshold=3.0)
        else:
            from wecom_push import push_wecom
            push_wecom("## ✅ 风平浪静\n\n当前持仓无异常波动。")
    except Exception as e:
        from config import log_error
        log_error(f"预警失败: {e}")


# ── Dashboard (保留，轻量查看) ──────────────────────────

@app.route("/")
def dashboard():
    from scripts.webapp_helpers import _parse_snapshot, _recent_reports, _history_summary
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
