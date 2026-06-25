"""
SQLite 查询工具
用法：
    python scripts/db_query.py                  # 总览
    python scripts/db_query.py --holding 600519 # 单只持仓详情
    python scripts/db_query.py --history        # 快照历史
    python scripts/db_query.py --analyses       # 分析报告列表
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from database import (
    get_holdings, get_price_history, get_snapshots,
    get_recent_analyses, get_context_summary, get_latest_manual_assets,
)


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def show_overview():
    """总览"""
    print(get_context_summary())


def show_holding_detail(code: str):
    """单只持仓详情 + 价格历史"""
    holdings = get_holdings()
    h = next((h for h in holdings if h["code"] == code), None)
    if not h:
        print(f"⚠️ 未找到持仓: {code}")
        return

    print_header(f"{h['code']} {h['name']}")
    print(f"  类型: {h['type']} | 持仓: {h['shares']:,.0f} | 成本: ¥{h['cost_basis']:.2f}")
    print(f"  成本总额: ¥{h['shares'] * h['cost_basis']:,.0f}")

    prices = get_price_history(code, 30)
    if prices:
        latest = prices[0]
        print(f"  最新价: ¥{latest['price']:.2f} | 市值: ¥{latest['market_value']:,.0f}")
        print(f"  浮动盈亏: {'🟢' if latest['pnl']>=0 else '🔴'} ¥{latest['pnl']:,.0f}")

        print(f"\n  {'日期':<12} {'价格':>10} {'涨跌':>8} {'市值':>12} {'盈亏':>12}")
        print(f"  {'-'*54}")
        for p in prices[:15]:
            print(f"  {p['date']:<12} ¥{p['price']:>8.2f} {p['change_pct']:>+6.2f}% "
                  f"¥{p['market_value']:>10,.0f} {'🟢' if p['pnl']>=0 else '🔴'} ¥{p['pnl']:>10,.0f}")


def show_history():
    """快照历史"""
    snapshots = get_snapshots(60)
    if not snapshots:
        print("暂无快照记录")
        return

    print_header("历史快照")
    print(f"  {'日期':<20} {'总投资':>12} {'总成本':>12} {'盈亏':>12} {'率':>8}")
    print(f"  {'-'*65}")
    for s in snapshots[:30]:
        print(f"  {s['date']:<20} ¥{s['total_investment']:>10,.0f} "
              f"¥{s['total_cost']:>10,.0f} "
              f"{'🟢' if s['total_pnl']>=0 else '🔴'} ¥{s['total_pnl']:>9,.0f} "
              f"{s['pnl_pct']:>+6.1f}%")


def show_analyses():
    """分析报告日志"""
    analyses = get_recent_analyses(20)
    if not analyses:
        print("暂无分析记录")
        return

    print_header("分析报告历史")
    for a in analyses:
        print(f"  {a['date']} | {a['prompt']:<20} | {Path(a['file_path']).name}")


def main():
    if "--holding" in sys.argv:
        idx = sys.argv.index("--holding")
        show_holding_detail(sys.argv[idx + 1])
    elif "--history" in sys.argv:
        show_history()
    elif "--analyses" in sys.argv:
        show_analyses()
    else:
        show_overview()


if __name__ == "__main__":
    main()
