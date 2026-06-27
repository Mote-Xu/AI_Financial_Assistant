"""
家庭财务汇总引擎
读取 family/ 下所有成员数据 + 共有资产，产出脱敏家庭快照
"""

import re
import json
from pathlib import Path
from datetime import datetime

import os
PROJECT_ROOT = Path(__file__).parent.parent
_family_env = os.getenv("FINANCE_FAMILY_DIR", "")
FAMILY_DIR = Path(_family_env) if _family_env else (PROJECT_ROOT / "family_demo")
MEMBERS_DIR = FAMILY_DIR / "members"
HOUSEHOLD_DIR = FAMILY_DIR / "household"
REPORTS_DIR = FAMILY_DIR / "reports"


def load_family_config() -> dict:
    """加载家庭配置"""
    cfg = FAMILY_DIR / "family.json"
    if cfg.exists():
        with open(cfg, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _parse_number(text: str) -> float:
    text = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try: return float(text)
    except ValueError: return 0


def _read_md_section(filepath: Path, section: str) -> list[str]:
    """读取 markdown 文件中某个 ## section 下的表格行"""
    if not filepath.exists():
        return []
    lines = []
    in_section = False
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("## ") and section in s:
                in_section = True
                continue
            if in_section and s.startswith("## "):
                break
            if in_section and s.startswith("|") and "---" not in s:
                lines.append(s)
    return lines


def _read_cash_total(filepath: Path) -> float:
    """读取现金合计"""
    if not filepath.exists():
        return 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "现金合计" in line:
                return _parse_number(line)
    return 0


def _read_snapshot_value(filepath: Path) -> float:
    """读取快照文件中的总市值"""
    if not filepath.exists():
        return 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "总市值" in line:
                nums = re.findall(r"[\d,]+\.?\d*", line)
                if nums:
                    return float(nums[0].replace(",", ""))
    return 0


def aggregate(snapshot_dir: Path = None):
    """
    汇总所有成员数据 → 家庭总览
    snapshot_dir: 个人版的快照目录（如 finance_demo），用来读市值
    """
    cfg = load_family_config()
    members = cfg.get("members", {})
    results = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "members": {},
        "household": {"property_equity": 0, "property_loan": 0},
        "family_total": {"assets": 0, "cash": 0, "investments": 0, "property_equity": 0, "debt": 0},
    }

    # 汇总每个成员
    for m_id, m_info in members.items():
        member_dir = MEMBERS_DIR / m_id
        assets_file = member_dir / "assets.md"

        cash = _read_cash_total(assets_file)
        # 从个人版快照读市值（如果有的话）
        m_snapshot = None
        if snapshot_dir:
            m_snapshot = snapshot_dir / "portfolio_snapshot.md"
        investments = _read_snapshot_value(m_snapshot) if m_snapshot and m_snapshot.exists() else 0

        results["members"][m_id] = {
            "name": m_info["name"],
            "role": m_info["role"],
            "cash": round(cash),
            "investments": round(investments),
            "total": round(cash + investments),
            "detail_visible": True,  # 自己看自己是 True，渲染时控制
        }

        results["family_total"]["cash"] += cash
        results["family_total"]["investments"] += investments

    # 汇总家庭共有资产
    prop_file = HOUSEHOLD_DIR / "property.md"
    if prop_file.exists():
        with open(prop_file, "r", encoding="utf-8") as f:
            for line in f:
                if "估值" in line and "---" not in line:
                    parts = line.split("|")
                    for p in parts:
                        p = p.strip()
                        if "¥" in p or p.replace(",","").replace(".","").isdigit():
                            val = _parse_number(p)
                            if val > 0 and "估值" not in p:
                                results["household"]["property_equity"] = max(
                                    results["household"]["property_equity"], val
                                )
                if "贷款余额" in line:
                    parts = line.split("|")
                    for p in parts:
                        p = p.strip()
                        val = _parse_number(p)
                        if val > 0 and "贷款" not in p and "余额" not in p:
                            results["household"]["property_loan"] = max(
                                results["household"]["property_loan"], val
                            )

    total_assets = (results["family_total"]["cash"] +
                    results["family_total"]["investments"] +
                    results["household"]["property_equity"])
    results["family_total"]["assets"] = round(total_assets)
    results["family_total"]["property_equity"] = results["household"]["property_equity"]
    results["family_total"]["debt"] = results["household"]["property_loan"]
    results["family_total"]["net_worth"] = round(total_assets - results["household"]["property_loan"])

    # 保存到 reports/
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / "family_snapshot.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return results


def format_family_summary(results: dict, viewer: str = "me") -> str:
    """
    根据查看者身份，生成脱敏的家庭文本摘要
    viewer: me/dad/mom — 控制谁能看到谁的明细
    """
    cfg = load_family_config()
    members = cfg.get("members", {})
    visibility = cfg.get("visibility", {})

    lines = [
        f"## 📊 家庭资产总览",
        f"_更新时间: {results['updated']}_",
        "",
    ]

    # 家庭汇总（所有人可见）
    f = results["family_total"]
    lines += [
        f"💰 **家庭总资产**: ¥{f['assets']:,}",
        f"📈 流动资产: ¥{f['cash'] + f['investments']:,}",
        f"🏠 房产净值: ¥{f['property_equity']:,}",
        f"💳 负债: ¥{f['debt']:,}",
        f"📐 **净资产**: ¥{f['net_worth']:,}",
        "",
    ]

    # 成员明细（仅自己可见）
    if visibility.get("self_detail", True):
        for m_id, m in results["members"].items():
            if m_id == viewer:
                lines.append(f"### 👤 {m['name']}（你的详情）")
                lines.append(f"现金: ¥{m['cash']:,}  投资: ¥{m['investments']:,}")
                lines.append("")

    # 其他成员脱敏
    if len(results["members"]) > 1:
        lines.append("### 👥 其他成员（脱敏）")
        for m_id, m in results["members"].items():
            if m_id == viewer:
                continue
            lines.append(f"{m['name']}: 总资产 ¥{m['total']:,} （角色: {m['role']}）")

    return "\n".join(lines)


if __name__ == "__main__":
    # 测试：从 finance_demo 读取投资数据
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from config import FINANCE_DIR as DEMO_DIR
    result = aggregate(snapshot_dir=DEMO_DIR)
    print(format_family_summary(result, viewer="me"))
