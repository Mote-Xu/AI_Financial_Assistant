"""
市场波动预警 — 持仓单日涨跌超阈值自动推企微
支持按资产类型差异化阈值
用法：python scripts/market_alert.py [--threshold 3.0]
"""

import os
import sys
from datetime import datetime

# 清代理
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "*")

from config import PROJECT_ROOT, ensure_finance_dir, acquire_lock, release_lock
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from market_data import parse_assets_md, fetch_stock_and_etf_prices, fetch_fund_nav

# ── 按资产类型的差异化阈值 ────────────────────────────────────
# 股票波动大 → 阈值高，避免噪音；ETF 波动适 → 阈值中；基金净值变动小 → 阈值低

DEFAULT_THRESHOLD_MAP = {
    "ETF": 3.0,        # ETF 日波动通常 1-3%
    "股票": 5.0,       # 个股波动大，5% 以上才告警
    "基金": 2.0,       # 基金净值（场外）变动通常 <2%
}

# 细分 ETF 类别：宽基 vs 行业主题
BROAD_ETF_CODES = {
    "510300", "510050", "510500", "159915",  # 沪深300/上证50/中证500/创业板
    "510880", "513100", "513050",             # 红利/纳指/中概互联
}
# 行业/主题 ETF 波动更大，比宽基高 1%
SECTOR_ETF_THRESHOLD = 4.0


def get_threshold(code: str, asset_type: str = "证券") -> float:
    """根据代码和类型返回对应阈值"""
    if asset_type == "ETF":
        if code in BROAD_ETF_CODES:
            return DEFAULT_THRESHOLD_MAP["ETF"]
        else:
            return SECTOR_ETF_THRESHOLD
    return DEFAULT_THRESHOLD_MAP.get(asset_type, 3.0)


def check_alerts(threshold: float = None):
    """
    检查持仓波动，返回告警列表
    如果指定 threshold，所有资产用同一阈值；否则按类型差异化
    """
    print(f"🔔 市场波动预警 | 模式: {'统一 ¥{:.1f}%'.format(threshold) if threshold else '差异化'}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    holdings = parse_assets_md()
    if not holdings["stocks"] and not holdings["funds"]:
        print("⚠️ 未找到持仓")
        return []

    all_holdings = {}

    if holdings["stocks"]:
        prices = fetch_stock_and_etf_prices([s["code"] for s in holdings["stocks"]])
        for s in holdings["stocks"]:
            code = s["code"]
            if code in prices and prices[code]["price"] > 0:
                change = prices[code].get("change_pct", 0)
                asset_type = prices[code].get("type", "证券")
                t = threshold if threshold else get_threshold(code, asset_type)
                all_holdings[code] = {
                    "name": prices[code]["name"],
                    "price": prices[code]["price"],
                    "change": change,
                    "shares": s["shares"],
                    "mv": prices[code]["price"] * s["shares"],
                    "type": asset_type,
                    "threshold": t,
                }
                marker = "🔴" if change < -t else ("🟡" if change < 0 else "🟢")
                print(f"  {code} {prices[code]['name']:10s} "
                      f"¥{prices[code]['price']:>8.2f}  "
                      f"{marker} {change:+.2f}%  [阈值: ±{t}%]")

    if holdings["funds"]:
        navs = fetch_fund_nav([f["code"] for f in holdings["funds"]])
        for f in holdings["funds"]:
            code = f["code"]
            if code in navs and navs[code]["nav"] > 0:
                t = threshold if threshold else DEFAULT_THRESHOLD_MAP["基金"]
                all_holdings[code] = {
                    "name": f["name"],
                    "price": navs[code]["nav"],
                    "change": 0,  # 基金净值无日内涨跌幅
                    "shares": f["shares"],
                    "mv": navs[code]["nav"] * f["shares"],
                    "type": "基金",
                    "threshold": t,
                }

    # 筛选超阈值
    alerts = []
    for code, h in all_holdings.items():
        t = h["threshold"]
        if abs(h["change"]) >= t and h["change"] != 0:
            direction = "📉 大跌" if h["change"] < 0 else "📈 大涨"
            severity = "🔴" if abs(h["change"]) >= t * 2 else "🟠" if abs(h["change"]) >= t * 1.5 else "🟡"
            alerts.append({
                "code": code,
                "name": h["name"],
                "type": h["type"],
                "price": h["price"],
                "change": h["change"],
                "mv": h["mv"],
                "threshold": t,
                "direction": direction,
                "severity": severity,
            })

    if alerts:
        print(f"\n🚨 {len(alerts)} 项触发预警：")
        for a in alerts:
            print(f"  {a['severity']} {a['direction']} {a['code']} {a['name']}: "
                  f"{a['change']:+.2f}% (阈值 ±{a['threshold']}%, 市值 ¥{a['mv']:,.0f})")
    else:
        print(f"\n✅ 无持仓触发预警阈值")

    return alerts


def push_alerts(alerts: list, threshold: float = None):
    """推送预警到企微"""
    if not alerts:
        return True

    now = datetime.now().strftime("%m/%d %H:%M")
    lines = [f"## 🚨 波动预警 {now}", ""]

    # 按严重程度排序
    alerts_sorted = sorted(alerts, key=lambda a: abs(a["change"]), reverse=True)

    for a in alerts_sorted:
        emoji = a.get("severity", "🔴" if a["change"] < 0 else "🟢")
        lines.append(
            f"{emoji} **{a['name']}** ({a['code']}) "
            f"| {a['change']:+.2f}% | ¥{a['price']:.2f}"
        )
        lines.append(f"> {a['type']} · 市值 ¥{a['mv']:,.0f} · 阈值 ±{a['threshold']}%")
        lines.append("")

    # 分层建议
    severe = [a for a in alerts_sorted if abs(a["change"]) >= a["threshold"] * 2]
    moderate = [a for a in alerts_sorted if a["threshold"] <= abs(a["change"]) < a["threshold"] * 2]

    if severe:
        lines.append("---")
        lines.append(f"🔴 严重预警 ({len(severe)} 项)：跌幅超阈值 2 倍")
        lines.append("> 建议：立即关注个股消息面，检查是否为基本面恶化")
        lines.append("> 如需详细分析，回 Claude Code 说「市场应急」")

    if moderate and not severe:
        lines.append("---")
        lines.append(f"🟠 一般预警 ({len(moderate)} 项)")
        lines.append("> 建议：加入自选观察，暂无需操作")

    msg = "\n".join(lines)

    try:
        from wecom_push import push_wecom
        return push_wecom(msg)
    except Exception:
        try:
            from wechat_push import push_wechat
            return push_wechat("🚨 波动预警", msg)
        except Exception as e:
            print(f"⚠️ 推送失败: {e}")
            return False


def main():
    ensure_finance_dir()
    if not acquire_lock():
        print("❌ 另一个实例正在运行，退出。")
        sys.exit(0)
    try:
        threshold = None
        if "--threshold" in sys.argv:
            idx = sys.argv.index("--threshold")
            threshold = float(sys.argv[idx + 1])

        alerts = check_alerts(threshold)

        if alerts:
            push_alerts(alerts, threshold)
            print("\n📱 预警已推送")
        else:
            print("\n😌 风平浪静")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
