"""
家庭财务引擎 — 统一数据读取 + 分析 + 隐私控制
为 /family Dashboard 和 AI 分析提供所有数据
"""

import re
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
import os
_env = os.getenv("FINANCE_FAMILY_DIR", "")
FAMILY_DIR = Path(_env) if _env else (PROJECT_ROOT / "family_demo")


def load_config() -> dict:
    cfg = FAMILY_DIR / "family.json"
    if cfg.exists():
        with open(cfg, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _parse_number(text: str) -> float:
    text = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try: return float(text)
    except ValueError: return 0


def _read_md(filepath: Path) -> str:
    if not filepath.exists():
        return ""
    with open(filepath, encoding="utf-8") as f:
        return f.read()


def _parse_table(text: str, section: str = None) -> list[dict]:
    """解析 Markdown 表格为 list[dict]"""
    lines = text.split("\n")
    rows = []
    in_section = not section
    headers = []

    for line in lines:
        s = line.strip()
        if section and s.startswith("## ") and section in s:
            in_section = True
            continue
        if in_section and s.startswith("## "):
            break
        if not in_section:
            continue
        if s.startswith("|") and "---" not in s:
            cols = [c.strip() for c in s.split("|")[1:-1]]
            if "代码" in s or "名称" in s or "金额" in s or "保额" in s:
                headers = cols
            elif headers and len(cols) == len(headers):
                rows.append(dict(zip(headers, cols)))
    return rows


# ── 成员数据 ─────────────────────────────────────────────

def get_member_assets(member_id: str) -> dict:
    """成员的资产数据"""
    p = FAMILY_DIR / "members" / member_id / "assets.md"
    text = _read_md(p)

    # 现金
    cash = 0
    cash_rows = _parse_table(text, "现金")
    if not cash_rows:
        cash_rows = _parse_table(text, "等价物")
    for r in cash_rows:
        # Try "金额 (CNY)" key, then fallback to any key with "金额"
        val = r.get("金额 (CNY)", "") or r.get("金额", "")
        if not val:
            for k, v in r.items():
                if "金额" in k:
                    val = v; break
        cash += _parse_number(val)

    # 股票/ETF
    stocks = _parse_table(text, "股票")

    # 基金
    funds = _parse_table(text, "基金")

    # 黄金等
    gold = _parse_table(text, "黄金")

    return {
        "cash": round(cash),
        "stocks": stocks,
        "funds": funds,
        "gold": gold,
    }


def get_member_income(member_id: str) -> dict:
    """成员的收支数据"""
    p = FAMILY_DIR / "members" / member_id / "income.md"
    text = _read_md(p)

    income = 0
    expense = 0

    income_rows = _parse_table(text, "收入")
    for r in income_rows:
        for k, v in r.items():
            if "金额" in k:
                income += _parse_number(v)

    expense_rows = _parse_table(text, "支出")
    for r in expense_rows:
        for k, v in r.items():
            if "金额" in k:
                expense += _parse_number(v)

    return {
        "monthly_income": round(income),
        "monthly_expense": round(expense),
        "monthly_savings": round(income - expense),
        "income_rows": income_rows,
        "expense_rows": expense_rows,
    }


def get_member_insurance(member_id: str) -> dict:
    """成员的保险数据"""
    p = FAMILY_DIR / "members" / member_id / "insurance.md"
    text = _read_md(p)
    rows = _parse_table(text, "配置")
    total_premium = 0
    coverage = {"寿险": 0, "重疾": 0, "医疗": 0, "意外": 0}

    for r in rows:
        p = 0
        for k, v in r.items():
            if "保费" in k:
                p = _parse_number(v)
        total_premium += p
        # Check if name contains insurance type
        name = ""
        for k, v in r.items():
            if "险种" in k or "保险" in k:
                name = v
        for ck in coverage:
            if ck in name:
                coverage[ck] += _parse_number(r.get("保额", r.get("保额 (CNY)", "0")))

    return {
        "rows": rows,
        "annual_premium": round(total_premium),
        "coverage": coverage,
        "gaps": _find_gaps(coverage),
    }


def _find_gaps(coverage: dict) -> list[str]:
    gaps = []
    if coverage["寿险"] == 0: gaps.append("寿险缺失")
    if coverage["重疾"] == 0: gaps.append("重疾险缺失")
    if coverage["医疗"] == 0: gaps.append("医疗险缺失")
    if coverage["意外"] == 0: gaps.append("意外险缺失")
    return gaps


# ── 家庭聚合 ──────────────────────────────────────────────

def get_family_full(viewer: str = "me") -> dict:
    """
    完整的家庭数据视图
    根据 viewer 身份自动脱敏
    """
    cfg = load_config()
    members_cfg = cfg.get("members", {})
    visibility = cfg.get("visibility", {})

    result = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "family_name": cfg.get("name", "家庭财务"),
        "members": {},
        "household": {},
        "summary": {},
        "alerts": [],
    }

    total_income = 0
    total_expense = 0
    total_cash = 0
    total_premium = 0
    earners = []
    all_coverage = {"寿险": 0, "重疾": 0, "医疗": 0, "意外": 0}

    for m_id, m_info in members_cfg.items():
        assets = get_member_assets(m_id)
        inc = get_member_income(m_id)
        ins = get_member_insurance(m_id)
        is_self = (m_id == viewer)

        member_data = {
            "name": m_info["name"],
            "role": m_info["role"],
            "is_self": is_self,
            "cash": assets["cash"],
            "monthly_income": inc["monthly_income"] if is_self else None,
            "monthly_expense": inc["monthly_expense"] if is_self else None,
            "monthly_savings": inc["monthly_savings"] if is_self else None,
            "total": assets["cash"],
            "insurance": ins if is_self else {"annual_premium": ins["annual_premium"], "coverage": ins["coverage"], "gaps": ins["gaps"]},
        }

        result["members"][m_id] = member_data
        total_cash += assets["cash"]
        total_premium += ins["annual_premium"]

        if is_self or visibility.get("household_summary"):
            total_income += inc["monthly_income"]
            total_expense += inc["monthly_expense"]

        for ck in all_coverage:
            all_coverage[ck] += ins["coverage"][ck]

        if m_info["role"] == "earner":
            earners.append(m_info["name"])

    # 家庭共有资产
    prop_file = FAMILY_DIR / "household" / "property.md"
    property_value = 0
    property_loan = 0
    if prop_file.exists():
        text = _read_md(prop_file)
        for line in text.split("\n"):
            if "估值" in line and "---" not in line:
                cols = [c.strip() for c in line.split("|")]
                for c in cols:
                    v = _parse_number(c)
                    if v > 100000:
                        property_value = max(property_value, v)
            if "贷款余额" in line:
                cols = [c.strip() for c in line.split("|")]
                for c in cols:
                    v = _parse_number(c)
                    if v > 100000:
                        property_loan = max(property_loan, v)

    result["household"] = {
        "property_value": property_value,
        "property_loan": property_loan,
        "property_equity": property_value - property_loan,
    }

    total_assets = total_cash + property_value
    result["summary"] = {
        "total_income": round(total_income),
        "total_expense": round(total_expense),
        "monthly_savings": round(total_income - total_expense),
        "savings_rate": round((total_income - total_expense) / total_income * 100, 1) if total_income > 0 else 0,
        "liquid_assets": total_cash,
        "total_assets": round(total_assets),
        "net_worth": round(total_assets - property_loan),
        "property_equity": property_value - property_loan,
        "total_premium": round(total_premium),
    }

    # 风险告警
    alerts = result["alerts"]

    # 收入依赖
    for m_id, m_data in result["members"].items():
        if m_data["monthly_income"] and total_income > 0:
            pct = m_data["monthly_income"] / total_income * 100
            if pct > 60:
                alerts.append(f"⚠️ 收入依赖: {m_data['name']} 贡献 {pct:.0f}% 家庭收入")

    # 保障缺口
    for m_id, m_data in result["members"].items():
        if m_id == viewer or visibility.get("risk_alerts"):
            for gap in m_data.get("insurance", {}).get("gaps", []):
                alerts.append(f"🛡️ {m_data['name']}: {gap}")

    # 保费占比
    annual_income = total_income * 12
    if annual_income > 0 and total_premium > 0:
        pct = total_premium / annual_income * 100
        if pct > 10:
            alerts.append(f"💰 保费占年收入 {pct:.1f}%，超过 10% 警戒线")

    # 急救资金
    emergency_months = round(total_cash / total_expense, 1) if total_expense > 0 else 99
    result["summary"]["emergency_months"] = emergency_months
    if emergency_months < 6:
        alerts.append(f"🚨 现金仅够 {emergency_months} 个月，不足 6 个月安全线")

    return result


def build_ai_context(results: dict, viewer: str = "me") -> str:
    """构建给 DeepSeek 的分析上下文"""
    cfg = load_config()
    lines = [
        f"# {results['family_name']} — 家庭财务数据",
        f"更新时间: {results['updated']}\n",
    ]

    s = results["summary"]
    lines += [
        "## 家庭总览",
        f"月收入: ¥{s['total_income']:,}",
        f"月支出: ¥{s['total_expense']:,}",
        f"月储蓄: ¥{s['monthly_savings']:,} (储蓄率 {s['savings_rate']}%)",
        f"流动资产: ¥{s['liquid_assets']:,}",
        f"房产净值: ¥{s['property_equity']:,}",
        f"净资产: ¥{s['net_worth']:,}",
        f"应急资金: {s['emergency_months']} 个月",
        "",
    ]

    lines.append("## 成员详情")
    for m_id, m in results["members"].items():
        lines.append(f"\n### {m['name']} ({m['role']})")
        lines.append(f"现金: ¥{m['cash']:,}")
        if m.get("monthly_income"):
            lines.append(f"月收入: ¥{m['monthly_income']:,}")
            lines.append(f"月支出: ¥{m['monthly_expense']:,}")

    lines.append("\n## 保险矩阵")
    for m_id, m in results["members"].items():
        ins = m.get("insurance", {})
        cov = ins.get("coverage", {})
        gaps = ins.get("gaps", [])
        lines.append(f"{m['name']}: 保费 ¥{ins.get('annual_premium', 0):,} "
                     f"| 寿险 {cov.get('寿险',0)} | 重疾 {cov.get('重疾',0)} "
                     f"| 医疗 {cov.get('医疗',0)} | 漏洞: {', '.join(gaps) if gaps else '无'}")

    # 附加家庭目标
    goals_file = FAMILY_DIR / "household" / "goals.md"
    if goals_file.exists():
        lines.append("\n" + goals_file.read_text(encoding="utf-8"))

    lines.append(f"\n## 风险告警\n" + "\n".join(results["alerts"]) if results["alerts"] else "\n无异常")

    return "\n".join(lines)
