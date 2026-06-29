"""
历史净值追踪 & 可视化
用法：python scripts/history.py [--plot]
"""

import csv
import sys
from pathlib import Path
from datetime import datetime

from config import HISTORY_FILE, CHART_FILE, ensure_finance_dir
# 修复中文显示
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import platform as _platform
if _platform.system() == "Windows":
    _font_list = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "DejaVu Sans"]
else:
    _font_list = ["Noto Sans CJK SC", "WenQuanYi Micro Hei", "Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["font.sans-serif"] = _font_list
plt.rcParams["axes.unicode_minus"] = False


def load_history() -> list:
    """读取历史记录"""
    if not HISTORY_FILE.exists():
        return []
    rows = []
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for k in ["cash", "stock_etf", "fund", "total_investment",
                       "total_cost", "total_pnl", "pnl_pct"]:
                r[k] = float(r[k]) if r[k] else 0.0
            rows.append(r)
    return rows


def print_summary():
    """打印历史摘要"""
    rows = load_history()
    if not rows:
        print("暂无历史记录。请先运行 market_data.py")
        return

    print(f"📊 历史净值追踪 ({len(rows)} 条记录)")
    print(f"{'日期':<20} {'总投资':>12} {'总成本':>12} {'盈亏':>12} {'收益率':>8}")
    print("-" * 65)
    for r in rows[-20:]:  # 最近 20 条
        print(f"{r['date']:<20} ¥{r['total_investment']:>10,.0f} "
              f"¥{r['total_cost']:>10,.0f} "
              f"{'🟢' if r['total_pnl']>=0 else '🔴'} ¥{r['total_pnl']:>9,.0f} "
              f"{r['pnl_pct']:>+6.1f}%")

    # 统计
    if len(rows) >= 2:
        first = rows[0]
        last = rows[-1]
        days = (datetime.strptime(last["date"][:10], "%Y-%m-%d") -
                datetime.strptime(first["date"][:10], "%Y-%m-%d")).days or 1
        change = last["total_investment"] - first["total_investment"]
        print(f"\n📈 期间变动: {'🟢 +' if change>=0 else '🔴 '}¥{change:,.0f} "
              f"(自 {first['date'][:10]} 至 {last['date'][:10]}, {days} 天)")
        if last["total_cost"] > 0:
            print(f"📊 最新收益率: {last['pnl_pct']:+.1f}%")


def plot_history():
    """画资产走势图"""
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("❌ 需要 matplotlib，请执行: pip install matplotlib")
        return

    rows = load_history()
    if len(rows) < 2:
        print("⚠️ 至少需要 2 条记录才能画图")
        return

    dates = [datetime.strptime(r["date"][:10], "%Y-%m-%d") for r in rows]
    investment = [r["total_investment"] for r in rows]
    cost = [r["total_cost"] for r in rows]
    pnl_pct = [r["pnl_pct"] for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # 市值 vs 成本
    ax1.fill_between(dates, cost, investment,
                     where=[i >= c for i, c in zip(investment, cost)],
                     color="green", alpha=0.15, label="浮盈")
    ax1.fill_between(dates, cost, investment,
                     where=[i < c for i, c in zip(investment, cost)],
                     color="red", alpha=0.15, label="浮亏")
    ax1.plot(dates, investment, "b-", linewidth=2, label="市值")
    ax1.plot(dates, cost, "gray", linewidth=1, linestyle="--", label="成本")
    ax1.set_ylabel("金额 (¥)")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    ax1.set_title("投资组合市值走势")

    # 收益率
    colors = ["green" if p >= 0 else "red" for p in pnl_pct]
    ax2.bar(dates, pnl_pct, color=colors, alpha=0.7, width=0.8)
    ax2.axhline(y=0, color="gray", linewidth=0.5)
    ax2.set_ylabel("收益率 (%)")
    ax2.set_xlabel("日期")
    ax2.grid(True, alpha=0.3)
    ax2.set_title("累计收益率变化")

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    fig.autofmt_xdate()
    plt.tight_layout()

    out = CHART_FILE
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"📊 图表已保存: {out}")
    plt.show()


if __name__ == "__main__":
    ensure_finance_dir()
    if "--plot" in sys.argv:
        plot_history()
    else:
        print_summary()
