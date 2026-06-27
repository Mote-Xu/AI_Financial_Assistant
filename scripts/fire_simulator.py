"""
FIRE 模拟器 — Financial Independence / Retire Early
支持确定性计算 + 蒙特卡洛随机模拟
用法: python scripts/fire_simulator.py [--scenario base|bull|bear]
"""

import re
import math
import random
import sys
from config import FINANCE_DIR, SNAPSHOT_FILE, ASSETS_FILE, INCOME_FILE, GOALS_FILE

# ── 场景预设 ──────────────────────────────────────────────────

SCENARIOS = {
    "bear": {
        "name": "🐻 保守",
        "return_mean": 0.05,
        "return_std": 0.10,
        "inflation_mean": 0.035,
        "inflation_std": 0.02,
    },
    "base": {
        "name": "😐 基准",
        "return_mean": 0.07,
        "return_std": 0.12,
        "inflation_mean": 0.03,
        "inflation_std": 0.015,
    },
    "bull": {
        "name": "🐂 乐观",
        "return_mean": 0.09,
        "return_std": 0.15,
        "inflation_mean": 0.025,
        "inflation_std": 0.01,
    },
}

N_SIMULATIONS = 10_000
MAX_YEARS = 50

# ── 数据读取 ──────────────────────────────────────────────────

def _parse_number(text: str) -> float:
    text = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(text)
    except ValueError:
        return 0


def _read_income():
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


# ── 确定性计算（原逻辑） ──────────────────────────────────────

def simulate_deterministic(return_rate: float = 0.07,
                           inflation: float = 0.03,
                           withdraw_rate: float = 0.04) -> dict:
    """确定性 FIRE 计算（单一结果）"""
    income = _read_income()
    savings_monthly = income["savings"] or (income["income"] - income["expense"])
    expenses_monthly = income["expense"]
    expenses_annual = expenses_monthly * 12
    current_nw = _read_net_worth()

    if expenses_monthly <= 0 or savings_monthly <= 0:
        return {"error": "无法计算：缺少收支数据"}

    real_return = return_rate - inflation
    fi_number = expenses_annual / withdraw_rate

    if real_return <= 0:
        years = (fi_number - current_nw) / (savings_monthly * 12) if savings_monthly > 0 else 999
    else:
        years = math.log(
            1 + (fi_number - current_nw) * real_return / (savings_monthly * 12)
        ) / math.log(1 + real_return)

    years = max(years, 0)

    projections = []
    nw = current_nw
    for y in range(int(years) + 6):
        yr_label = f"第{y}年" if y > 0 else "现在"
        projections.append({
            "year": yr_label, "y": y,
            "net_worth": round(nw),
            "fi_target": round(fi_number),
            "progress": round(min(nw / fi_number * 100, 100), 1),
        })
        nw = nw * (1 + real_return) + savings_monthly * 12

    return {
        "current_nw": round(current_nw),
        "monthly_expense": round(expenses_monthly),
        "monthly_savings": round(savings_monthly),
        "savings_rate": round(savings_monthly / income["income"] * 100, 1) if income["income"] > 0 else 0,
        "fi_number": round(fi_number),
        "withdraw_rate": round(withdraw_rate * 100, 1),
        "years_to_fi": round(years, 1),
        "real_return": round(real_return * 100, 2),
        "projections": projections[:6],
        "fi_year_projection": projections[min(int(years), len(projections) - 1)] if years < 100 else None,
    }


# ── 蒙特卡洛模拟 ──────────────────────────────────────────────

def _run_single_sim(initial_nw, annual_savings, fi_target, return_mean, return_std,
                    inflation_mean, inflation_std) -> int:
    """单次模拟：返回达到 FI 的年数（未达到返回 MAX_YEARS+1）"""
    nw = initial_nw
    for y in range(1, MAX_YEARS + 1):
        r = random.gauss(return_mean, return_std)
        inf = random.gauss(inflation_mean, inflation_std)
        real_r = r - inf
        nw = nw * (1 + real_r) + annual_savings
        if nw >= fi_target:
            return y
    return MAX_YEARS + 1


def simulate_monte_carlo(scenario: str = "base",
                         withdraw_rate: float = 0.04) -> dict:
    """
    蒙特卡洛 FIRE 模拟
    运行 N_SIMULATIONS 次，对年收益率和通胀率随机抽样
    """
    sc = SCENARIOS.get(scenario, SCENARIOS["base"])

    income = _read_income()
    savings_monthly = income["savings"] or (income["income"] - income["expense"])
    expenses_monthly = income["expense"]
    expenses_annual = expenses_monthly * 12
    current_nw = _read_net_worth()

    if expenses_monthly <= 0 or savings_monthly <= 0:
        return {"error": "无法计算：缺少收支数据"}

    fi_number = expenses_annual / withdraw_rate
    annual_savings = savings_monthly * 12

    # 运行模拟
    results = []
    seed = hash(f"{current_nw}_{savings_monthly}_{fi_number}") % (2**31)
    random.seed(seed)  # 可复现

    reached = 0
    for _ in range(N_SIMULATIONS):
        y = _run_single_sim(
            current_nw, annual_savings, fi_number,
            sc["return_mean"], sc["return_std"],
            sc["inflation_mean"], sc["inflation_std"],
        )
        results.append(y)
        if y <= MAX_YEARS:
            reached += 1

    # 统计
    results.sort()
    percentiles = {}
    for p in [10, 25, 50, 75, 90]:
        idx = int(len(results) * p / 100)
        percentiles[f"p{p}"] = results[min(idx, len(results) - 1)]

    # 每年达到 FI 的累积概率
    prob_by_year = {}
    for y in range(1, min(MAX_YEARS + 1, 41)):
        count = sum(1 for r in results if r <= y)
        prob_by_year[y] = round(count / N_SIMULATIONS * 100, 1)

    # 找到关键概率节点
    median_year = percentiles["p50"]
    p90_year = percentiles["p90"]

    return {
        "mode": "monte_carlo",
        "scenario": sc["name"],
        "scenario_key": scenario,
        "simulations": N_SIMULATIONS,
        "current_nw": round(current_nw),
        "monthly_expense": round(expenses_monthly),
        "monthly_savings": round(savings_monthly),
        "annual_savings": round(annual_savings),
        "savings_rate": round(savings_monthly / income["income"] * 100, 1) if income["income"] > 0 else 0,
        "fi_number": round(fi_number),
        "withdraw_rate": round(withdraw_rate * 100, 1),
        "return_mean": round(sc["return_mean"] * 100, 1),
        "return_std": round(sc["return_std"] * 100, 1),
        "inflation_mean": round(sc["inflation_mean"] * 100, 1),
        "success_rate": round(reached / N_SIMULATIONS * 100, 1),
        "median_years": median_year,
        "p10_years": percentiles["p10"],
        "p25_years": percentiles["p25"],
        "p75_years": percentiles["p75"],
        "p90_years": percentiles["p90"],
        "prob_by_year": prob_by_year,
        "percentiles": percentiles,
    }


# ── 格式化输出 ────────────────────────────────────────────────

def format_report(result: dict, compact: bool = False) -> str:
    """格式化 FIRE 报告为文本"""
    if "error" in result:
        return f"❌ {result['error']}"

    if result.get("mode") == "monte_carlo":
        return _format_monte_carlo(result, compact)
    else:
        return _format_deterministic(result)


def _format_deterministic(result: dict) -> str:
    """原有确定性格式"""
    return (
        "🏝️ FIRE 模拟报告\n\n"
        f"💰 当前资产: ¥{result['current_nw']:,}\n"
        f"📊 月支出: ¥{result['monthly_expense']:,}\n"
        f"💾 月储蓄: ¥{result['monthly_savings']:,} (储蓄率 {result['savings_rate']}%)\n\n"
        f"🎯 FI 目标: ¥{result['fi_number']:,}\n"
        f"   (年支出 ¥{result['monthly_expense'] * 12:,} ÷ {result['withdraw_rate']:.0f}% 提取)\n\n"
        f"⏱️ 预计 {result['years_to_fi']} 年达到财务自由\n\n"
        f"📈 参数: 真实收益 {result['real_return']:.1f}%\n\n"
        "📅 资产预测:\n" +
        "\n".join(
            f"  {p['year']:6s} ¥{p['net_worth']:>10,}  ({p['progress']}%)"
            for p in result["projections"]
            if p["progress"] < 100 or p == result["projections"][-1]
        ) +
        "\n\n💡 4% 规则: 每年提取总资产的 4% 用于生活（Trinity Study）。"
    )


def _format_monte_carlo(result: dict, compact: bool = False) -> str:
    """蒙特卡洛格式化"""
    if compact:
        return _format_monte_carlo_compact(result)
    return _format_monte_carlo_full(result)


def _format_monte_carlo_full(result: dict) -> str:
    """完整版（控制台/Dashboard）"""
    lines = [
        f"🏝️ FIRE 蒙特卡洛模拟 — {result['scenario']}",
        f"   模拟 {result['simulations']:,} 次 · 年收益均值 {result['return_mean']}%±{result['return_std']}%",
        "",
        f"💰 当前资产: ¥{result['current_nw']:,}",
        f"📊 月支出: ¥{result['monthly_expense']:,}  月储蓄: ¥{result['monthly_savings']:,}",
        f"💾 储蓄率: {result['savings_rate']}%  年存 ¥{result['annual_savings']:,}",
        "",
        f"🎯 FI 目标: ¥{result['fi_number']:,}",
        f"   (年支出 ¥{result['monthly_expense'] * 12:,} ÷ {result['withdraw_rate']:.0f}% 提取率)",
        "",
        f"📊 {result['simulations']:,} 次模拟中 {result['success_rate']}% 在 {MAX_YEARS} 年内达到 FI",
        "",
        "⏱️ 达到 FI 需要的年数（分位数）:",
        f"  乐观(10%): {result['p10_years']} 年",
        f"  偏乐(25%): {result['p25_years']} 年",
        f"  中位(50%): {result['median_years']} 年  ← 最可能",
        f"  偏悲(75%): {result['p75_years']} 年",
        f"  悲观(90%): {result['p90_years']} 年",
        "",
        "📈 累积概率（达到 FI 的可能性）:",
    ]

    # 挑关键年份展示
    key_years = [3, 5, 10, 15, 20, 25, 30]
    prob = result["prob_by_year"]
    for y in key_years:
        p = prob.get(y, 0)
        bar = "█" * int(p / 5) + "░" * (20 - int(p / 5))
        lines.append(f"  {y:2d}年: {bar} {p:5.1f}%")

    lines.append("")
    lines.append("💡 蒙特卡洛通过随机模拟市场波动，给出概率而非单一数字。")
    lines.append("   中位数是最可能的情况，90%分位是偏悲观的底线。")

    return "\n".join(lines)


def _format_monte_carlo_compact(result: dict) -> str:
    """精简版（企微推送，≤1000字）"""
    lines = [
        f"🏝️ FIRE 模拟 — {result['scenario']}",
        f"   模拟 {result['simulations']:,} 次",
        "",
        f"💰 资产 ¥{result['current_nw']:,}  |  📊 月出 ¥{result['monthly_expense']:,}",
        f"💾 月存 ¥{result['monthly_savings']:,}  |  🎯 FI ¥{result['fi_number']:,}",
        "",
        f"📈 成功率: {result['success_rate']}% (50年内)",
        "",
        "⏱️ 达到 FI 年数:",
        f"  乐观 → {result['p10_years']}年  |  中位 → {result['median_years']}年  |  悲观 → {result['p90_years']}年",
        "",
        "📊 关键节点概率:",
    ]
    for y in [5, 10, 15, 20]:
        p = result["prob_by_year"].get(y, 0)
        lines.append(f"  {y}年内: {p}%")
    lines.append("")
    lines.append("💡 蒙特卡洛模拟通过10,000次随机市场波动，给出概率区间而非单一数字。")
    return "\n".join(lines)


# ── 向后兼容 ─────────────────────────────────────────────────

def simulate(return_rate: float = 0.07,
             inflation: float = 0.03,
             withdraw_rate: float = 0.04,
             scenario: str = None) -> dict:
    """
    FIRE 模拟入口
    - 如果指定 scenario，运行蒙特卡洛
    - 否则运行确定性计算（向后兼容）
    """
    if scenario:
        return simulate_monte_carlo(scenario, withdraw_rate)
    return simulate_deterministic(return_rate, inflation, withdraw_rate)


# ── 概率曲线数据（给网页用） ──────────────────────────────────

def get_probability_curve(result: dict) -> list:
    """返回概率曲线数据点 [[year, prob], ...]"""
    if result.get("mode") != "monte_carlo":
        return []
    prob = result.get("prob_by_year", {})
    return [[y, prob[y]] for y in sorted(prob.keys())]


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    scenario = "base"
    if "--scenario" in sys.argv:
        idx = sys.argv.index("--scenario")
        scenario = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "base"
    if scenario not in SCENARIOS:
        print(f"未知场景: {scenario}，可选: {list(SCENARIOS.keys())}")
        sys.exit(1)

    result = simulate_monte_carlo(scenario)
    print(format_report(result))
