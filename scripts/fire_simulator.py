"""
FIRE 模拟器 — Financial Independence / Retire Early
计算财务自由时间线 + 多情景推演
"""

import re
import math
from config import FINANCE_DIR, SNAPSHOT_FILE, ASSETS_FILE, INCOME_FILE, GOALS_FILE


def _parse_number(text: str) -> float:
    """从文本中提取数字"""
    text = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(text)
    except ValueError:
        return 0


def _read_income():
    """读取月度收支数据"""
    data = {"income": 0, "expense": 0, "savings": 0}
    if not INCOME_FILE.exists():
        return data

    with open(INCOME_FILE, "r", encoding="utf-8") as f:
        text = f.read()

    for line in text.split("\n"):
        if "月收入合计" in line:
            data["income"] = _parse_number(line.split("¥")[-1] if "¥" in line else "0")
        if "月支出合计" in line:
            data["expense"] = _parse_number(line.split("¥")[-1] if "¥" in line else "0")
        if "月净现金流" in line:
            data["savings"] = _parse_number(line.split("¥")[-1] if "¥" in line else "0")
    return data


def _read_net_worth():
    """从快照读取当前总市值（不含房产）"""
    if not SNAPSHOT_FILE.exists():
        return 0
    with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    for line in text.split("\n"):
        if "总市值" in line:
            nums = re.findall(r"[\d,]+\.?\d*", line)
            if nums:
                return float(nums[0].replace(",", ""))
    return 0


def simulate(return_rate: float = 0.07,
             inflation: float = 0.03,
             withdraw_rate: float = 0.04) -> dict:
    """
    FIRE 模拟
    return_rate: 预期年化收益率（默认 7%）
    inflation: 预期通胀率（默认 3%）
    withdraw_rate: 安全提取率（4% 规则）
    """
    income = _read_income()
    savings_monthly = income["savings"] or (income["income"] - income["expense"])
    expenses_monthly = income["expense"]
    expenses_annual = expenses_monthly * 12
    current_nw = _read_net_worth()

    if expenses_monthly <= 0 or savings_monthly <= 0:
        return {"error": "无法计算：缺少收支数据"}

    # 真实收益率（扣除通胀）
    real_return = return_rate - inflation

    # FI 目标（4% 规则：年支出 / 提取率）
    fi_number = expenses_annual / withdraw_rate

    # 计算到达 FI 需要的年数
    # 公式: n = ln(1 + (FI_target × r) / (savings × 12)) / ln(1 + r)
    if real_return <= 0:
        years = (fi_number - current_nw) / (savings_monthly * 12) if savings_monthly > 0 else 999
    else:
        years = math.log(
            1 + (fi_number - current_nw) * real_return / (savings_monthly * 12)
        ) / math.log(1 + real_return)

    years = max(years, 0)

    # 逐年资产预测
    projections = []
    nw = current_nw
    for y in range(int(years) + 6):
        yr_label = f"第{y}年"
        if y == 0:
            yr_label = "现在"
        projections.append({
            "year": yr_label,
            "net_worth": round(nw),
            "fi_target": round(fi_number),
            "progress": round(min(nw / fi_number * 100, 100), 4),
        })
        nw = nw * (1 + real_return) + savings_monthly * 12

    return {
        "current_nw": round(current_nw),
        "monthly_expense": round(expenses_monthly),
        "monthly_savings": round(savings_monthly),
        "savings_rate": round(savings_monthly / income["income"] * 100, 1) if income["income"] > 0 else 0,
        "fi_number": round(fi_number),
        "withdraw_rate": withdraw_rate * 100,
        "return_rate": return_rate * 100,
        "inflation": inflation * 100,
        "real_return": round(real_return * 100, 2),
        "years_to_fi": round(years, 1),
        "projections": projections[:6],  # 只显示前 6 年 + 到达那年
        "fi_year_projection": projections[min(int(years), len(projections) - 1)] if years < 100 else None,
    }


def format_report(result: dict) -> str:
    """格式化 FIRE 报告为文本"""
    if "error" in result:
        return f"❌ {result['error']}"

    return (
        "🏝️ FIRE 模拟报告\n\n"
        f"💰 当前资产: ¥{result['current_nw']:,}\n"
        f"📊 月支出: ¥{result['monthly_expense']:,}\n"
        f"💾 月储蓄: ¥{result['monthly_savings']:,} (储蓄率 {result['savings_rate']}%)\n\n"
        f"🎯 FI 目标: ¥{result['fi_number']:,}\n"
        f"   (年支出 ¥{result['monthly_expense'] * 12:,} ÷ {result['withdraw_rate']:.0f}% 提取)\n\n"
        f"⏱️ 预计 {result['years_to_fi']} 年达到财务自由\n\n"
        f"📈 参数: 收益率 {result['return_rate']:.0f}%  通胀 {result['inflation']:.0f}%  "
        f"真实收益 {result['real_return']:.1f}%\n\n"
        "📅 资产预测:\n" +
        "\n".join(
            f"  {p['year']:6s} ¥{p['net_worth']:>10,}  ({p['progress']}%)"
            for p in result["projections"]
            if p["progress"] < 100 or p == result["projections"][-1]
        ) +
        "\n\n💡 4% 规则: 每年提取总资产的 4% 用于生活，本金不缩水（Trinity Study）。"
    )


if __name__ == "__main__":
    result = simulate()
    print(format_report(result))
