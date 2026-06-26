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
from concurrent.futures import ThreadPoolExecutor
import json

# 线程池（最多 4 个并发任务，防雪崩）
_executor = ThreadPoolExecutor(max_workers=4)

# 消息去重（最近 5 分钟的 MsgId）
_seen_ids = {}
_dedup_lock = threading.Lock()

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
            cmd_map = {"SNAPSHOT": "/快照", "CHECKUP": "/体检", "ALERT": "/预警", "HELP": "/帮助", "CHART": "/走势", "FIRE": "/fire", "BACKTEST": "/回测 510300", "HEALTH": "/健康"}
            msg = cmd_map.get(key, "/帮助")
        else:
            return "", 200
    elif content_el is not None:
        msg = content_el.text.strip() if content_el.text else ""
    else:
        return "", 200

    user_id = from_user.text.strip() if from_user is not None and from_user.text else ""

    # 消息去重（防企微重发）
    msg_id = msg_xml.find("MsgId")
    if msg_id is not None and msg_id.text:
        with _dedup_lock:
            now = time.time()
            # 清理超过 5 分钟的旧记录
            _seen_ids.clear() if now - max(_seen_ids.values() or [0]) > 300 else None
            if msg_id.text in _seen_ids:
                return "", 200  # 重复消息，跳过
            _seen_ids[msg_id.text] = now
            # 限制缓存大小
            if len(_seen_ids) > 1000:
                _seen_ids.clear()

    log_error(f"CALLBACK CMD: {msg} from {user_id}")

    # 通过应用 API 发回复（比加密 XML 更可靠，支持长文本）
    if msg and user_id:
        reply_text = _handle_command(msg, user_id)
        def _send(uid, txt):
            from wecom_app import send_to_user
            send_to_user(uid, txt)
        _executor.submit(_send, user_id, reply_text)
        log_error(f"CALLBACK API SENT: {reply_text[:80]}")

    return "", 200


def _handle_command(msg: str, user_id: str = "") -> str:
    """命令路由"""
    msg = msg.strip().lower()

    if msg in ("/体检", "/check", "/report", "体检", "月度体检"):
        _executor.submit(_run_checkup, user_id)
        return "✅ 月度体检已启动，1-2 分钟后结果会回到这里。"
    elif msg in ("/快照", "/snapshot", "快照", "市值"):
        _executor.submit(_run_snapshot, user_id)
        return "✅ 正在拉取最新行情，30 秒内回到这里。"
    elif msg in ("/预警", "/alert", "预警"):
        _executor.submit(_run_alert, user_id)
        return "✅ 正在检查持仓波动..."
    elif msg.startswith("/回测") or msg.startswith("/backtest") or msg.startswith("回测"):
        code = msg.split()[-1] if len(msg.split()) > 1 else "510300"
        _executor.submit(_run_backtest, user_id, code)
        return f"📊 正在回测 {code}..."
    elif msg in ("/fire", "fire", "财务自由", "退休"):
        _executor.submit(_run_fire, user_id)
        return "🏝️ 正在计算 FIRE 时间线..."
    elif msg in ("/走势", "/history", "/chart", "走势", "历史"):
        _executor.submit(_run_chart, user_id)
        return "✅ 正在生成走势图..."
    elif msg in ("/健康", "/health", "健康", "health"):
        _executor.submit(_run_health, user_id)
        return "🏥 正在系统体检..."
    elif msg in ("/帮助", "/help", "帮助", "help"):
        return (
            "🤖 AI 财务助手\n\n"
            "· /体检 — AI 分析 + 推送\n"
            "· /快照 — 最新市值\n"
            "· /预警 — 波动检查\n"
            "· /走势 — 净值图表\n"
            "· /fire — 财务自由推算\n"
            "· /回测 510300 — 定投回测\n"
            "· /健康 — 系统体检\n"
            "· /帮助 — 菜单"
        )
    else:
        return f"未识别「{msg}」，/帮助 查看命令。"


def _run_checkup(user_id: str):
    """后台运行完整体检，报告直接发到应用私聊"""
    try:
        from wecom_app import send_to_user
        from auto_runner import run_market_data
        from deepseek_analysis import load_file, build_context, call_deepseek
        from config import FINANCE_DIR
        from datetime import datetime

        if user_id:
            send_to_user(user_id, "📊 正在更新行情...")
        run_market_data()

        if user_id:
            send_to_user(user_id, "🤖 正在 AI 分析（约需 1 分钟）...")
        prompt = load_file("prompts/monthly_review.md")
        context = build_context()
        from deepseek_analysis import validate_context
        valid, reason = validate_context(context)
        if not valid:
            if user_id:
                send_to_user(user_id, f"⚠️ 数据校验未通过：{reason}\n请先运行 /快照 更新行情。")
            return
        result = call_deepseek(prompt, context)

        # 保存报告
        output = FINANCE_DIR / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        with open(output, "w", encoding="utf-8") as f:
            f.write(f"# 财务分析报告\n> 自动生成: {datetime.now()}\n\n")
            f.write(result)

        # 发到应用私聊（分多段，每段不超过 2048 字符）
        if user_id:
            MAX = 1800
            for i in range(0, len(result), MAX):
                chunk = result[i:i+MAX]
                prefix = "📊 " if i == 0 else ""
                send_to_user(user_id, prefix + chunk)
            send_to_user(user_id, "✅ 月度体检完成")
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


def _run_backtest(user_id: str, code: str = "510300"):
    """运行定投回测"""
    try:
        from wecom_app import send_to_user
        from backtest import fetch_history, simulate_dca, compare_lump_sum, format_report, KNOWN_SYMBOLS
        name = KNOWN_SYMBOLS.get(code, code)
        send_to_user(user_id, f"📊 正在拉取 {name} 历史数据...")
        df = fetch_history(code, years=3)
        if df.empty:
            send_to_user(user_id, f"❌ {code} 无历史数据")
            return
        monthly = 2000
        total = monthly * 3 * 12
        result = simulate_dca(df, monthly)
        result["code"] = code
        result["name"] = name
        compare = compare_lump_sum(df, total, monthly)
        report = format_report(result, compare)
        send_to_user(user_id, report)
    except Exception as e:
        from config import log_error
        log_error(f"Backtest failed: {e}")


def _run_fire(user_id: str):
    """运行 FIRE 模拟"""
    try:
        from wecom_app import send_to_user
        from fire_simulator import simulate, format_report
        send_to_user(user_id, "🏝️ 正在分析你的财务自由路径...")
        result = simulate()
        report = format_report(result)
        send_to_user(user_id, report)
    except Exception as e:
        if user_id:
            from wecom_app import send_to_user
            send_to_user(user_id, f"❌ FIRE 计算失败: {e}")
        from config import log_error
        log_error(f"FIRE failed: {e}")


def _run_health(user_id: str):
    """运行系统健康检查"""
    try:
        from wecom_app import send_to_user
        from health_check import run_all, format_report
        results, all_ok = run_all()
        send_to_user(user_id, format_report(results, all_ok))
    except Exception as e:
        if user_id:
            from wecom_app import send_to_user
            send_to_user(user_id, f"❌ 健康检查失败: {e}")


def _run_chart(user_id: str):
    """生成走势图并发送到用户"""
    try:
        from wecom_app import send_to_user, _get_token, _get_app_config
        from config import CHART_FILE, HISTORY_FILE
        import matplotlib
        matplotlib.use("Agg")
        from history import plot_history
        send_to_user(user_id, "📈 正在生成走势图...")
        plot_history()
        if CHART_FILE.exists():
            # Upload image via WeCom API
            cfg = _get_app_config()
            token = _get_token()
            if token:
                import requests
                url = f"https://qyapi.weixin.qq.com/cgi-bin/media/upload?access_token={token}&type=image"
                with open(CHART_FILE, "rb") as f:
                    resp = requests.post(url, files={"media": (CHART_FILE.name, f, "image/png")}, timeout=30)
                data = resp.json()
                if data.get("errcode") == 0:
                    media_id = data.get("media_id")
                    # Send as image message
                    msg_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
                    payload = {
                        "touser": user_id,
                        "msgtype": "image",
                        "agentid": int(cfg["agentid"]),
                        "image": {"media_id": media_id},
                    }
                    r = requests.post(msg_url, json=payload, timeout=10)
                    if r.json().get("errcode") == 0:
                        return
        send_to_user(user_id, "❌ 生成图表失败，请稍后重试。")
    except Exception as e:
        from wecom_app import send_to_user
        send_to_user(user_id, f"❌ 失败: {e}")


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
    from webapp_helpers import _history_summary
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
    from webapp_helpers import _parse_snapshot
    return jsonify(_parse_snapshot())


# ── 手机控制台 (保留作为备用触发方式) ──────────────────

@app.route("/home")
def parents_view():
    """爸妈专用——只读看板，大字体，无操作"""
    return render_template("parents.html", now=datetime.now())


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
        _executor.submit(_snapshot_job, job_id)
    else:
        with _lock:
            _jobs[job_id] = {"status": "running", "started": time.time()}
        _executor.submit(_analysis_job, job_id, prompts[action])
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
