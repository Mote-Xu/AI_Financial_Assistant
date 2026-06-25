"""
市场波动预警 — 持仓单日跌超阈值自动推企微
用于定时任务（如每日 14:50，收盘前 10 分钟）
用法：python scripts/market_alert.py [--threshold 3.0]
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# 清代理
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "*")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from market_data import parse_assets_md, fetch_stock_and_etf_prices, fetch_fund_nav


def check_alerts(threshold: float = 3.0):
    """检查持仓波动，返回告警列表"""
    print(f"🔔 市场波动预警 | 阈值: ±{threshold}%")
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
                all_holdings[code] = {
                    "name": prices[code]["name"],
                    "price": prices[code]["price"],
                    "change": change,
                    "shares": s["shares"],
                    "mv": prices[code]["price"] * s["shares"],
                    "type": prices[code].get("type", "证券"),
                }
                print(f"  {code} {prices[code]['name']:10s} "
                      f"¥{prices[code]['price']:>8.2f}  "
                      f"{'🟢' if change >= 0 else '🔴'} {change:+.2f}%")

    if holdings["funds"]:
        navs = fetch_fund_nav([f["code"] for f in holdings["funds"]])
        for f in holdings["funds"]:
            code = f["code"]
            if code in navs and navs[code]["nav"] > 0:
                all_holdings[code] = {
                    "name": f["name"],
                    "price": navs[code]["nav"],
                    "change": 0,  # 基金净值无日内涨跌幅
                    "shares": f["shares"],
                    "mv": navs[code]["nav"] * f["shares"],
                    "type": "基金",
                }

    # 筛选超阈值
    alerts = []
    for code, h in all_holdings.items():
        if abs(h["change"]) >= threshold and h["change"] != 0:
            direction = "📉 大跌" if h["change"] < 0 else "📈 大涨"
            alerts.append({
                "code": code,
                "name": h["name"],
                "type": h["type"],
                "price": h["price"],
                "change": h["change"],
                "mv": h["mv"],
                "direction": direction,
            })

    if alerts:
        print(f"\n🚨 {len(alerts)} 项触发预警：")
        for a in alerts:
            print(f"  {a['direction']} {a['code']} {a['name']}: {a['change']:+.2f}% "
                  f"(¥{a['price']:.2f}, 市值 ¥{a['mv']:,.0f})")
    else:
        print(f"\n✅ 无持仓触发 ±{threshold}% 阈值")

    return alerts


def push_alerts(alerts: list, threshold: float = 3.0):
    """推送预警到企微"""
    if not alerts:
        return True

    now = datetime.now().strftime("%m/%d %H:%M")
    lines = [f"## 🚨 波动预警 {now}", ""]

    for a in alerts:
        emoji = "🔴" if a["change"] < 0 else "🟢"
        lines.append(
            f"{emoji} **{a['name']}** ({a['code']}) "
            f"| {a['change']:+.2f}% | ¥{a['price']:.2f}"
        )
        lines.append(f"> 市值 ¥{a['mv']:,.0f} | {a['type']}")
        lines.append("")

    # 加一段建议
    big_drops = [a for a in alerts if a["change"] < 0]
    if big_drops:
        lines.append("---")
        lines.append(f"⚠️ {len(big_drops)} 只持仓跌幅超 {threshold}%")
        lines.append("> 建议：查看消息面，评估是否为系统性风险")
        lines.append("> 如需详细分析，回 Claude Code 说「市场分析」")

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
    threshold = 3.0
    if "--threshold" in sys.argv:
        idx = sys.argv.index("--threshold")
        threshold = float(sys.argv[idx + 1])

    alerts = check_alerts(threshold)

    if alerts:
        push_alerts(alerts, threshold)
        print("\n📱 预警已推送")
    else:
        print("\n😌 风平浪静")


if __name__ == "__main__":
    main()
