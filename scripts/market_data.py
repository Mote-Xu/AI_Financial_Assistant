"""
市场数据获取脚本
支持 A 股个股、ETF、基金净值，使用 akshare（免费、无 API Key）
运行: python scripts/market_data.py
"""

import os
# 绕过系统代理（代理 127.0.0.1:19395 未运行，导致 eastmoney 接口超时）
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

import akshare as ak
import pandas as pd
from datetime import datetime
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FINANCE_DIR = PROJECT_ROOT / "finance"


def parse_assets_md(filepath: str = None) -> dict:
    """解析 assets.md 中的持仓"""
    if filepath is None:
        filepath = FINANCE_DIR / "assets.md"

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    holdings = {"stocks": [], "funds": []}
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

        if stock_section:
            match = re.match(
                r"\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*([\d,.]+)\s*\|", line
            )
            if match:
                holdings["stocks"].append({
                    "code": match.group(1),
                    "name": match.group(2).strip(),
                    "shares": int(match.group(3).replace(",", "")),
                    "cost": float(match.group(4).replace(",", "")),
                })

        if fund_section:
            match = re.match(
                r"\|\s*(\d{6})\s*\|\s*(.+?)\s*\|\s*([\d,]+)\s*\|\s*([\d,.]+)\s*\|", line
            )
            if match:
                holdings["funds"].append({
                    "code": match.group(1),
                    "name": match.group(2).strip(),
                    "shares": int(match.group(3).replace(",", "")),
                    "cost": float(match.group(4).replace(",", "")),
                })

    return holdings


def fetch_stock_and_etf_prices(codes: list) -> dict:
    """获取个股 + ETF 实时价格，自动区分"""
    prices = {}
    print("📊 获取股票/ETF 行情...")

    # 先拉 ETF 列表
    etf_codes = set()
    try:
        etf_df = ak.fund_etf_spot_em()
        etf_codes = set(etf_df["代码"].tolist())
    except Exception:
        pass

    # 拉全部 A 股行情（优先 eastmoney，失败则用新浪）
    stock_df = None
    for src_name, src_fn in [
        ("eastmoney", ak.stock_zh_a_spot_em),
        ("sina", ak.stock_zh_a_spot),
    ]:
        try:
            stock_df = src_fn()
            if stock_df is not None and not stock_df.empty:
                break
        except Exception:
            continue

    if stock_df is None:
        print("  ⚠️ 所有 A 股数据源均不可用，仅获取 ETF 行情")

    for code in codes:
        if code in etf_codes:
            try:
                match = etf_df[etf_df["代码"] == code]
                if not match.empty:
                    row = match.iloc[0]
                    prices[code] = {
                        "name": row["名称"],
                        "price": float(row["最新价"]),
                        "change_pct": float(row["涨跌幅"]) if "涨跌幅" in row else 0,
                        "type": "ETF",
                    }
                    print(f"  ✅ [ETF] {code} {row['名称']}: ¥{row['最新价']}")
                    continue
            except Exception:
                pass

        # A 股个股（eastmoney 或 sina）
        if stock_df is not None:
            try:
                # Sina API 代码格式为 sh600519 / sz300750，eastmoney 为纯数字
                match = stock_df[stock_df["代码"] == code]
                if match.empty:
                    # 尝试带前缀匹配
                    prefix = "sh" if code.startswith(("6", "5", "9")) else "sz"
                    match = stock_df[stock_df["代码"] == prefix + code]
                if not match.empty:
                    row = match.iloc[0]
                    price_val = float(row["最新价"])
                    if price_val > 0:
                        change_val = row.get("涨跌幅", 0)
                        try:
                            change_val = float(change_val) if pd.notna(change_val) else 0
                        except (ValueError, TypeError):
                            change_val = 0
                        prices[code] = {
                            "name": row["名称"],
                            "price": price_val,
                            "change_pct": change_val,
                            "type": "股票",
                        }
                        print(f"  ✅ [股票] {code} {row['名称']}: ¥{price_val}")
                        continue
            except Exception:
                pass

        print(f"  ⚠️ 未找到: {code}")

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
                print(f"  ✅ [基金] {code}: ¥{latest['单位净值']} ({latest['净值日期']})")
        except Exception as e:
            print(f"  ⚠️ 基金 {code} 净值获取失败: {e}")
    return navs


def generate_summary(holdings: dict, security_prices: dict, fund_navs: dict) -> str:
    """生成持仓汇总"""
    lines = ["\n## 📈 当前市值汇总", f"_更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n"]
    lines.append("| 类型 | 代码 | 名称 | 持仓量 | 成本价 | 现价 | 市值 | 盈亏 |")
    lines.append("|------|------|------|--------|--------|------|------|------|")

    total_value = 0
    total_cost = 0

    for s in holdings["stocks"]:
        p = security_prices.get(s["code"], {})
        price = p.get("price", 0)
        stype = p.get("type", "证券")
        mv = price * s["shares"]
        cost = s["cost"] * s["shares"]
        pnl = mv - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0
        lines.append(
            f"| {stype} | {s['code']} | {s['name']} | {s['shares']:,} | "
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
            f"| 基金 | {f['code']} | {f['name']} | {f['shares']:,} | "
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

    holdings = parse_assets_md()

    if not holdings["stocks"] and not holdings["funds"]:
        print("⚠️ assets.md 中未找到持仓，请检查格式。")
        sys.exit(0)

    print(f"📋 找到 {len(holdings['stocks'])} 只股票/ETF, {len(holdings['funds'])} 只基金\n")

    security_prices = {}
    fund_navs = {}

    if holdings["stocks"]:
        security_prices = fetch_stock_and_etf_prices([s["code"] for s in holdings["stocks"]])

    if holdings["funds"]:
        fund_navs = fetch_fund_nav([f["code"] for f in holdings["funds"]])

    summary = generate_summary(holdings, security_prices, fund_navs)
    print(summary)

    output_file = FINANCE_DIR / "portfolio_snapshot.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"\n📁 汇总已保存到: {output_file}")

    return holdings, security_prices, fund_navs


if __name__ == "__main__":
    main()
