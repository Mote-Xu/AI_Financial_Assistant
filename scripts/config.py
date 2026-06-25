"""
集中式路径配置 — 所有脚本统一从这里获取路径
通过 FINANCE_DATA_DIR 环境变量切换 demo/真实数据目录

用法:
    from config import FINANCE_DIR, ASSETS_FILE, ...

    # Demo 模式（默认）: FINANCE_DIR → <project>/finance_demo/
    # 真实模式: export FINANCE_DATA_DIR=finance  → <project>/finance/
    # 外部路径: export FINANCE_DATA_DIR=D:/MyData/ → D:/MyData/
"""

import os
from pathlib import Path

# === 项目根目录 (AI_Financial_Assistant/) ===
PROJECT_ROOT = Path(__file__).parent.parent

# === 数据目录 ===
# 优先级: 环境变量 > 默认 finance_demo
_env_dir = os.getenv("FINANCE_DATA_DIR", "")
if _env_dir:
    _p = Path(_env_dir)
    if _p.is_absolute():
        FINANCE_DIR = _p
    else:
        FINANCE_DIR = PROJECT_ROOT / _env_dir
else:
    FINANCE_DIR = PROJECT_ROOT / "finance_demo"

# 确保目录存在（demo 目录由迁移脚本创建，真实目录由用户创建）
FINANCE_DIR.mkdir(parents=True, exist_ok=True)

# === 便捷文件路径 ===
ASSETS_FILE = FINANCE_DIR / "assets.md"
INCOME_FILE = FINANCE_DIR / "income.md"
INSURANCE_FILE = FINANCE_DIR / "insurance.md"
LIABILITIES_FILE = FINANCE_DIR / "liabilities.md"
GOALS_FILE = FINANCE_DIR / "goals.md"
SNAPSHOT_FILE = FINANCE_DIR / "portfolio_snapshot.md"
HISTORY_FILE = FINANCE_DIR / "history.csv"
DB_PATH = FINANCE_DIR / "finance_data.db"
CHART_FILE = FINANCE_DIR / "history_chart.png"


def get_finance_dir_name() -> str:
    """返回数据目录的名称（用于 GitHub URL 拼接）"""
    return FINANCE_DIR.name
