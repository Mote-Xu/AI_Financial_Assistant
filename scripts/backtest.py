"""
定投回测 — 模拟定期定额投资历史表现
用法: python scripts/backtest.py [--code 510300] [--years 5] [--monthly 2000]
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "*")

import akshare as ak
import pandas as pd

# 常用标的池
KNOWN_SYMBOLS = {
    "510300": "沪深300 ETF",
    "159915": "创业板 ETF",
    "510880": "红利 ETF",
    "513100": "纳指 ETF",
    "510500": "中证500 ETF",
    "588000": "科创50 ETF",
    "000300": "沪深300 指数",
    "SPX": "标普500",
    "600519": "贵州茅台",
    "300750": "宁德时代",
}


def fetch_history(code: str, years: int = 5) -> pd.DataFrame:
    """拉取历史日线"""
    start = (datetime.now() - timedelta(days=years * 365 + 30)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    period = "daily"

    try:
        df = ak.stock_zh_a_hist(symbol=code, period=period,
                                start_date=start, end_date=end, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "收盘": "close"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            return df[["date", "close"]]
    except Exception:
        pass

    # ETF fallback
    try:
        df = ak.fund_etf_hist_em(symbol=code, period=period,
                                 start_date=start, end_date=end, adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={"日期": "date", "收盘": "close"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            return df[["date", "close"]]
    except Exception:
        pass

    return pd.DataFrame()


def simulate_dca(df: pd.DataFrame, monthly_amount: float) -> dict:
    """
    定投模拟：每月定投固定金额，按当月第一个交易日收盘价买入
    """
    if df.empty:
        return {"error": "无历史数据"}

    df = df.copy()
    df["month"] = df["date"].dt.to_period("M")

    # 每月第一天的收盘价
    monthly = df.groupby("month").first().reset_index()
    if len(monthly) < 2:
        return {"error": "数据不足"}

    months = len(monthly)
    total_invested = monthly_amount * months
    shares = sum(monthly_amount / monthly.iloc[i]["close"] for i in range(months))
    final_value = shares * monthly.iloc[-1]["close"]

    # 年化收益率 (CAGR)
    years = months / 12
    cagr = (final_value / total_invested) ** (1 / years) - 1 if years > 0 and total_invested > 0 else 0

    # 逐月统计
    monthly_data = []
    cum_shares = 0
    cum_invested = 0
    for i in range(months):
        price = monthly.iloc[i]["close"]
        cum_shares += monthly_amount / price
        cum_invested += monthly_amount
        mv = cum_shares * price
        monthly_data.append({
            "date": str(monthly.iloc[i]["month"]),
            "price": round(price, 3),
            "invested": cum_invested,
            "value": round(mv),
            "return_pct": round((mv / cum_invested - 1) * 100, 1),
        })

    # 最大回撤
    peak = 0
    max_dd = 0
    for d in monthly_data:
        if d["value"] > peak:
            peak = d["value"]
        dd = (peak - d["value"]) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    return {
        "code": "",
        "name": "",
        "months": months,
        "years": round(years, 1),
        "monthly": monthly_amount,
        "total_invested": round(total_invested),
        "final_value": round(final_value),
        "total_return": round((final_value / total_invested - 1) * 100, 1),
        "cagr": round(cagr * 100, 1),
        "max_drawdown": round(max_dd, 1),
        "latest_price": round(monthly.iloc[-1]["close"], 3),
        "start_price": round(monthly.iloc[0]["close"], 3),
        "monthly_data": monthly_data[-6:],  # 最近 6 个月
    }


def compare_lump_sum(df: pd.DataFrame, total_amount: float, monthly_amount: float) -> dict:
    """
    对比：一次性投入 vs 定投
    """
    if df.empty or len(df) < 2:
        return {}

    months = max(len(df) // 21, 1)  # 估计月数
    first_price = df.iloc[0]["close"]
    last_price = df.iloc[-1]["close"]

    # 一次性投入
    lump_shares = total_amount / first_price
    lump_value = lump_shares * last_price
    lump_return = (lump_value / total_amount - 1) * 100

    # 定投
    dca = simulate_dca(df, monthly_amount)
    if "error" not in dca:
        dca_return = dca["total_return"]
        dca_final = dca["final_value"]
    else:
        dca_return = 0
        dca_final = 0

    return {
        "lump_return": round(lump_return, 1),
        "lump_value": round(lump_value),
        "dca_return": dca_return,
        "dca_value": dca_final,
    }


def format_report(result: dict, compare: dict = None) -> str:
    """格式化回测报告"""
    if "error" in result:
        return f"❌ {result['error']}"

    lines = [
        f"📊 定投回测: {result['name']} ({result['code']})",
        "",
        f"⏱ 回测周期: {result['years']} 年 ({result['months']} 月)",
        f"💵 每月定投: ¥{result['monthly']:,}",
        f"💰 总投入: ¥{result['total_invested']:,}",
        f"📈 最终市值: ¥{result['final_value']:,}",
        f"📊 总收益率: {result['total_return']:+.1f}%",
        f"📐 年化 CAGR: {result['cagr']:+.1f}%",
        f"📉 最大回撤: -{result['max_drawdown']}%",
        f"💹 期间涨跌: {result['start_price']} → {result['latest_price']}",
    ]

    if compare:
        lines += [
            "",
            "⚖️ 策略对比:",
            f"  一次性 ¥{result['total_invested']:,}: "
            f"¥{compare['lump_value']:,} ({compare['lump_return']:+.1f}%)",
            f"  定投 ¥{result['monthly']:,}/月: "
            f"¥{result['final_value']:,} ({result['total_return']:+.1f}%)",
        ]

    lines += [
        "",
        "📅 最近 6 个月:",
    ]
    for d in result["monthly_data"]:
        emoji = "🟢" if d["return_pct"] >= 0 else "🔴"
        lines.append(
            f"  {d['date']}  ¥{d['price']}  "
            f"投入 ¥{d['invested']:,}  市值 ¥{d['value']:,}  "
            f"{emoji} {d['return_pct']:+.1f}%"
        )

    return "\n".join(lines)


def main():
    code = "510300"
    years = 5
    monthly = 2000

    for i, arg in enumerate(sys.argv):
        if arg == "--code" and i + 1 < len(sys.argv):
            code = sys.argv[i + 1]
        if arg == "--years" and i + 1 < len(sys.argv):
            years = int(sys.argv[i + 1])
        if arg == "--monthly" and i + 1 < len(sys.argv):
            monthly = float(sys.argv[i + 1])

    name = KNOWN_SYMBOLS.get(code, code)
    total_lump = monthly * years * 12

    print(f"📊 获取 {code} {name} 近 {years} 年历史数据...")
    df = fetch_history(code, years)
    if df.empty:
        print("❌ 未获取到数据")
        sys.exit(1)

    result = simulate_dca(df, monthly)
    result["code"] = code
    result["name"] = name

    compare = compare_lump_sum(df, total_lump, monthly)

    report = format_report(result, compare)
    print(report)


if __name__ == "__main__":
    main()
