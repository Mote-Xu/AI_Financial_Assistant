"""
Flask Web Dashboard — AI 财务助手
用法:
    python scripts/webapp.py              # 开发模式 (debug=True)
    python scripts/webapp.py --prod       # 生产模式 (waitress, port=5000)
"""

import sys
import os
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


# ── Helpers ──────────────────────────────────────────────

def _parse_snapshot():
    """解析 portfolio_snapshot.md 返回结构化数据"""
    if not SNAPSHOT_FILE.exists():
        return None

    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    data = {
        "holdings": [],
        "total_value": 0,
        "total_cost": 0,
        "total_pnl": 0,
        "total_pnl_pct": 0,
        "updated": "",
        "config": {"stock_pct": 0, "fund_pct": 0, "etf_pct": 0, "cash": 0},
    }

    for line in text.split("\n"):
        line = line.strip()
        if "更新时间" in line:
            data["updated"] = line.split(":")[-1].strip()
        if "总市值" in line:
            # 总市值: ¥387,574 | 总成本: ¥331,100 | 总盈亏: 🟢 ¥56,474 (+17.1%)
            import re
            nums = re.findall(r"[\d,]+\.?\d*", line)
            if len(nums) >= 1:
                data["total_value"] = float(nums[0].replace(",", ""))
            if len(nums) >= 2:
                data["total_cost"] = float(nums[1].replace(",", ""))
            if len(nums) >= 3:
                data["total_pnl"] = float(nums[2].replace(",", ""))
            pct_m = re.search(r"\(([+-]?[\d.]+)%\)", line)
            if pct_m:
                data["total_pnl_pct"] = float(pct_m.group(1))

    # 解析持仓表格行 (| 或 │ 分隔)
    in_table = False
    for line in text.split("\n"):
        line = line.strip()
        if "----" in line:
            in_table = not in_table
            continue
        if in_table and line.startswith("|") and "代码" not in line:
            # 统一用 | 处理
            clean = line.replace("│", "|")
            cols = [c.strip() for c in clean.split("|") if c.strip()]
            if len(cols) >= 8:
                try:
                    data["holdings"].append({
                        "type": cols[0],
                        "code": cols[1],
                        "name": cols[2],
                        "shares": cols[3],
                        "cost": cols[4],
                        "price": cols[5],
                        "value": cols[6],
                        "pnl": cols[7],
                    })
                except (IndexError, ValueError):
                    pass

    # 计算配置占比
    for h in data["holdings"]:
        import re
        val_str = re.sub(r"[^\d.]", "", h["value"].replace(",", ""))
        try:
            val = float(val_str)
        except ValueError:
            continue
        t = h["type"].upper()
        if "ETF" in t:
            data["config"]["etf_pct"] += val
        elif "基金" in t or "FUND" in t:
            data["config"]["fund_pct"] += val
        else:
            data["config"]["stock_pct"] += val

    total = data["total_value"] or 1
    for k in ["etf_pct", "fund_pct", "stock_pct"]:
        data["config"][k] = round(data["config"][k] / total * 100, 1)
    data["config"]["cash"] = round(100 - sum(
        data["config"][k] for k in ["etf_pct", "fund_pct", "stock_pct"]
    ), 1)

    return data


def _recent_reports(limit: int = 5):
    """列出最近的分析报告"""
    reports = sorted(FINANCE_DIR.glob("analysis_*.md"), reverse=True)
    result = []
    for r in reports[:limit]:
        stat = r.stat()
        label = r.stem.replace("analysis_", "").replace("_", " ")
        result.append({
            "name": r.name,
            "label": label,
            "time": datetime.fromtimestamp(stat.st_mtime).strftime("%m/%d %H:%M"),
            "size": f"{stat.st_size / 1024:.0f}KB",
        })
    return result


def _history_summary():
    """读取历史 CSV 最近 10 条"""
    rows = []
    if HISTORY_FILE.exists():
        import csv
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return rows[-10:]


# ── Routes ───────────────────────────────────────────────

@app.route("/")
def dashboard():
    """首页：资产总览"""
    snap = _parse_snapshot()
    reports = _recent_reports()
    history = _history_summary()
    return render_template("dashboard.html",
                           snap=snap, reports=reports,
                           history=history, now=datetime.now())


@app.route("/history")
def history_page():
    """历史净值页"""
    # 生成图表
    try:
        from history import plot_history
        import matplotlib
        matplotlib.use("Agg")
        plot_history()
    except Exception:
        pass

    chart_url = None
    if CHART_FILE.exists():
        chart_url = "/chart"

    rows = _history_summary()
    return render_template("history.html", rows=rows,
                           chart_url=chart_url, now=datetime.now())


@app.route("/chart")
def chart_image():
    """返回历史图表 PNG"""
    if CHART_FILE.exists():
        return send_file(str(CHART_FILE), mimetype="image/png")
    return "Chart not available", 404


@app.route("/api/snapshot")
def api_snapshot():
    """JSON API: 当前持仓数据"""
    snap = _parse_snapshot()
    return jsonify(snap)


@app.route("/webhook/wecom", methods=["GET", "POST"])
def wecom_webhook():
    """
    企微机器人回调端点（骨架）
    GET: URL 验证（企微配置时需要）
    POST: 接收消息 → 触发操作
    """
    if request.method == "GET":
        # 企微 URL 验证
        echostr = request.args.get("echostr", "")
        return echostr

    # POST: 解析消息
    try:
        data = request.get_json(force=True, silent=True) or {}
        msg = data.get("text", {}).get("content", "").strip()
    except Exception:
        msg = ""

    # 命令路由
    if msg in ("/体检", "/report", "/check"):
        # 异步触发分析（简化版：直接同步调用）
        try:
            from auto_runner import run_analysis
            # TODO: 改为后台线程执行，避免企微 5s 超时
            report = run_analysis("monthly_review")
            reply = "✅ 月度体检已完成，报告已推送到企微。"
        except Exception as e:
            reply = f"❌ 体检失败: {e}"
    elif msg in ("/快照", "/snapshot"):
        try:
            from wecom_push import push_portfolio_snapshot
            push_portfolio_snapshot()
            reply = "✅ 市值快照已推送。"
        except Exception as e:
            reply = f"❌ 快照失败: {e}"
    else:
        reply = (
            "🤖 AI 财务助手\n\n"
            "支持命令：\n"
            "• /体检 — 运行月度分析\n"
            "• /快照 — 推送市值快照\n"
            "• /帮助 — 显示本菜单"
        )

    return jsonify({
        "msgtype": "text",
        "text": {"content": reply},
    })


# ── Main ─────────────────────────────────────────────────

def main():
    prod = "--prod" in sys.argv
    host = "0.0.0.0"
    port = 5000

    print(f"\n🌐 AI 财务助手 Dashboard")
    print(f"   地址: http://localhost:{port}")
    print(f"   模式: {'生产 (waitress)' if prod else '开发 (flask debug)'}")
    print(f"   数据: {FINANCE_DIR}\n")

    if prod:
        from waitress import serve
        serve(app, host=host, port=port)
    else:
        app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    main()
