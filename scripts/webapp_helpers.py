"""Dashboard 辅助函数 (避免 webapp.py 过长)"""

import csv
import re
from datetime import datetime
from config import FINANCE_DIR, SNAPSHOT_FILE, HISTORY_FILE


def _parse_snapshot():
    """解析 portfolio_snapshot.md 返回结构化数据"""
    if not SNAPSHOT_FILE.exists():
        return None

    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    data = {
        "holdings": [],
        "total_value": 0, "total_cost": 0,
        "total_pnl": 0, "total_pnl_pct": 0,
        "updated": "",
        "config": {"stock_pct": 0, "fund_pct": 0, "etf_pct": 0, "cash": 0},
    }

    for line in text.split("\n"):
        line = line.strip()
        if "更新时间" in line:
            data["updated"] = line.split(":")[-1].strip()
        if "总市值" in line:
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

    in_table = False
    for line in text.split("\n"):
        line = line.strip()
        if "----" in line:
            in_table = not in_table
            continue
        if in_table and line.startswith("|") and "代码" not in line:
            clean = line.replace("│", "|")
            cols = [c.strip() for c in clean.split("|") if c.strip()]
            if len(cols) >= 8:
                data["holdings"].append({
                    "type": cols[0], "code": cols[1], "name": cols[2],
                    "shares": cols[3], "cost": cols[4], "price": cols[5],
                    "value": cols[6], "pnl": cols[7],
                })

    for h in data["holdings"]:
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
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return rows[-10:]
