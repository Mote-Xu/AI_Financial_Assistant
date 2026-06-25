"""
市场数据获取脚本
支持 A 股 ETF、基金净值查询，使用 akshare（免费、无 API Key）
运行: python scripts/market_data.py
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FINANCE_DIR = PROJECT_ROOT / "finance"


def parse_assets_md(filepath: str = None) -> dict:
    """解析 assets.md 中的持仓，提取股票/ETF代码和基金代码"""
    if filepath is None:
        filepath = FINANCE_DIR / "assets.md"

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    holdings = {"stocks": [], "funds": []}

    # 解析股票/ETF表格（匹配 | 代码 | 名称 | ...）
    stock_section = False
    fund_section = False

    for line in content.split("\n"):
        if "## 股票 & ETF" in line:
            stock_section = True
            fund_section = False
            continue
        if "## 基金" in line:
            fund_section = True
            stock_section = False
            continue
        if line.startswith("## ") and "股票" not in line and "基金" not in line:
            stock_section = False
            fund_section = False
            continue

        # 匹配表格行：| 510300 | 沪深300 ETF | 2,000 | ...
        if stock_section:
            match = re.match(
                r"\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*([\d.]+)\s*\|", line
            )
            if match:
                holdings["stocks"].append({
                    "code": match.group(1),
                    "name": match.group(2).strip(),
                    "shares": int(match.group(3).replace(",", "")),
                    "cost": float(match.group(4)),
                })

        if fund_section:
            match = re.match(
                r"\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*([\d.]+)\s*\|", line
            )
            if match:
                holdings["funds"].append({
                    "code": match.group(1),
                    "name": match.group(2).strip(),
                    "shares": int(match.group(3).replace(",", "")),
                    "cost": float(match.group(4)),
                })

    return holdings


def fetch_etf_prices(codes: list) -> dict:
    """获取ETF实时价格（akshare）"""
    prices = {}
    print("📊 获取 ETF 行情...")
    try:
        df = ak.fund_etf_spot_em()
        for code in codes:
            match = df[df["代码"] == code]
            if not match.empty:
                row = match.iloc[0]
                prices[code] = {
                    "name": row["名称"],
                    "price": float(row["最新价"]),
                    "change_pct": float(row["涨跌幅"]) if "涨跌幅" in row else 0,
                }
                print(f"  ✅ {code} {row['名称']}: ¥{row['最新价']}")
            else:
                print(f"  ⚠️ 未找到 ETF: {code}")
    except Exception as e:
        print(f"  ❌ ETF 行情获取失败: {e}")
    return prices


def fetch_fund_nav(codes: list) -> dict:
    """获取基金净值（akshare）"""
    navs = {}
    print("📊 获取基金净值...")
    for code in codes:
        try:
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            if not df.empty:
                latest = df.iloc[-1]
                navs[code] = {"name": code, "nav": float(latest["单位净值"]), "date": str(latest["净值日期"])}
                print(f"  ✅ {code}: ¥{latest['单位净值']} ({latest['净值日期']})")
        except Exception as e:
            print(f"  ⚠️ 基金 {code} 净值获取失败: {e}")
    return navs


def generate_summary(holdings: dict, etf_prices: dict, fund_navs: dict) -> str:
    """生成持仓汇总"""
    lines = ["\n## 📈 当前市值汇总", f"_更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]
    lines.append("| 类型 | 代码 | 名称 | 持仓量 | 成本价 | 现价 | 市值 | 盈亏 |")
    lines.append("|------|------|------|--------|--------|------|------|------|")

    total_value = 0
    total_cost = 0

    for s in holdings["stocks"]:
        p = etf_prices.get(s["code"], {})
        price = p.get("price", 0)
        mv = price * s["shares"]
        cost = s["cost"] * s["shares"]
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        lines.append(
            f"| ETF | {s['code']} | {s['name']} | {s['shares']} | "
            f"¥{s['cost']:.2f} | ¥{price:.3f} | ¥{mv:,.0f} | "
            f"{'🟢' if pnl>=0 else '🔴'} ¥{pnl:,.0f} ({pnl_pct:+.1f}%) |"
        )
        total_value += mv
        total_cost += cost

    for f in holdings["funds"]:
        n = fund_navs.get(f["code"], {})
        nav = n.get("nav", 0)
        mv = nav * f["shares"]
        cost = f["cost"] * f["shares"]
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        lines.append(
            f"| 基金 | {f['code']} | {f['name']} | {f['shares']} | "
            f"¥{f['cost']:.2f} | ¥{nav:.4f} | ¥{mv:,.0f} | "
            f"{'🟢' if pnl>=0 else '🔴'} ¥{pnl:,.0f} ({pnl_pct:+.1f}%) |"
        )
        total_value += mv
        total_cost += cost

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
    lines.append(f"\n> **总市值**: ¥{total_value:,.0f}  |  "
                  f"**总成本**: ¥{total_cost:,.0f}  |  "
                  f"**总盈亏**: {'🟢' if total_pnl>=0 else '🔴'} ¥{total_pnl:,.0f} "
                  f"({total_pnl_pct:+.1f}%)")

    return "\n".join(lines)


def main():
    print("=" * 50)
    print("💰 AI 财务助手 — 市场数据更新")
    print("=" * 50)

    # 解析持仓
    holdings = parse_assets_md()

    if not holdings["stocks"] and not holdings["funds"]:
        print("⚠️ assets.md 中未找到持仓，请检查格式。")
        sys.exit(0)

    print(f"📋 找到 {len(holdings['stocks'])} 只 ETF, {len(holdings['funds'])} 只基金\n")

    # 获取行情
    etf_prices = {}
    fund_navs = {}

    if holdings["stocks"]:
        etf_prices = fetch_etf_prices([s["code"] for s in holdings["stocks"]])

    if holdings["funds"]:
        fund_navs = fetch_fund_nav([f["code"] for f in holdings["funds"]])

    # 生成汇总
    summary = generate_summary(holdings, etf_prices, fund_navs)
    print(summary)

    # 输出到文件
    output_file = FINANCE_DIR / "portfolio_snapshot.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n📁 汇总已保存到: {output_file}")

    return holdings, etf_prices, fund_navs


if __name__ == "__main__":
    main()
