"""
SQLite 数据库模块 — 结构化存储持仓/价格/快照
单文件数据库，Python 内置 sqlite3，零依赖
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "finance" / "finance_data.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动建表）"""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    _init_schema(db)
    return db


def _init_schema(db: sqlite3.Connection):
    """建表（幂等）"""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS holdings (
            code        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL,   -- ETF / 股票 / 基金
            shares      REAL NOT NULL,
            cost_basis  REAL NOT NULL,
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS prices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            code        TEXT NOT NULL,
            price       REAL NOT NULL,
            change_pct  REAL DEFAULT 0,
            market_value REAL NOT NULL,
            pnl         REAL NOT NULL,
            FOREIGN KEY (code) REFERENCES holdings(code)
        );
        CREATE INDEX IF NOT EXISTS idx_prices_code_date ON prices(code, date);

        CREATE TABLE IF NOT EXISTS snapshots (
            date            TEXT PRIMARY KEY,
            cash            REAL DEFAULT 0,
            total_investment REAL NOT NULL,
            total_cost      REAL NOT NULL,
            total_pnl       REAL NOT NULL,
            pnl_pct         REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS manual_assets (
            date            TEXT PRIMARY KEY,
            cash_detail     TEXT,   -- JSON: [{"name":"活期","amount":50000},...]
            real_estate_equity REAL DEFAULT 0,
            total_liabilities  REAL DEFAULT 0,
            monthly_income  REAL DEFAULT 0,
            monthly_expense REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS analysis_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            prompt      TEXT NOT NULL,
            file_path   TEXT NOT NULL
        );
    """)


# ── 持仓操作 ──────────────────────────────

def sync_holdings(holdings: dict):
    """从 market_data parse 结果同步持仓表"""
    db = get_db()
    for s in holdings.get("stocks", []):
        # 判断类型：纯数字代码=ETF/个股，通过前缀区分
        # 实际上我们的 parse 函数无法区分，这里用外部价格数据辅助
        # 默认策略：5开头沪深、1开头深市 = ETF，6上海、0深圳、3创业板 = 可能是股票
        code = s["code"]
        if code.startswith(("5", "1")):
            stype = "ETF"
        else:
            stype = "股票"  # 6xxxxx, 0xxxxx, 3xxxxx
        db.execute("""
            INSERT OR REPLACE INTO holdings (code, name, type, shares, cost_basis, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'))
        """, (code, s["name"], stype, s["shares"], s["cost"]))
    for f in holdings.get("funds", []):
        db.execute("""
            INSERT OR REPLACE INTO holdings (code, name, type, shares, cost_basis, updated_at)
            VALUES (?, ?, '基金', ?, ?, datetime('now','localtime'))
        """, (f["code"], f["name"], f["shares"], f["cost"]))
    db.commit()
    db.close()


def get_holdings() -> list:
    """获取所有持仓"""
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM holdings ORDER BY type, code")]
    db.close()
    return rows


# ── 价格操作 ──────────────────────────────

def save_prices(prices_data: dict, holdings: dict):
    """保存当日价格快照（每个持仓一行）"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # 删除今天已有（幂等覆盖）
    db.execute("DELETE FROM prices WHERE date = ?", (today,))

    all_holdings = holdings.get("stocks", []) + holdings.get("funds", [])
    for h in all_holdings:
        code = h["code"]
        p = prices_data.get(code, {})
        price = p.get("price", 0)
        if price <= 0:
            nav_info = {}
            if code in [f["code"] for f in holdings.get("funds", [])]:
                nav_info = prices_data.get(code, {})
            price = nav_info.get("nav", 0)
        if price <= 0:
            continue

        mv = price * h["shares"]
        cost = h["cost"] * h["shares"]
        pnl = mv - cost
        change = p.get("change_pct", 0)

        db.execute(
            "INSERT INTO prices (date, code, price, change_pct, market_value, pnl) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (today, code, price, change, mv, pnl),
        )

    db.commit()
    db.close()


def get_price_history(code: str, days: int = 30) -> list:
    """获取单只持仓价格历史"""
    db = get_db()
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM prices WHERE code=? ORDER BY date DESC LIMIT ?", (code, days)
    )]
    db.close()
    return rows


# ── 快照操作 ──────────────────────────────

def save_snapshot(cash: float, total_value: float, total_cost: float,
                  total_pnl: float, pnl_pct: float):
    """保存每日总览快照"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    db.execute(
        "INSERT OR REPLACE INTO snapshots "
        "(date, cash, total_investment, total_cost, total_pnl, pnl_pct) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (today, cash, total_value, total_cost, total_pnl, pnl_pct),
    )
    db.commit()
    db.close()


def get_snapshots(limit: int = 60) -> list:
    """获取历史快照"""
    db = get_db()
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM snapshots ORDER BY date DESC LIMIT ?", (limit,)
    )]
    db.close()
    return rows


# ── 手动资产操作 ──────────────────────────

def save_manual_assets(cash_detail: list, real_estate_equity: float,
                       total_liabilities: float, income: float, expense: float):
    """保存手动录入的资产信息（从 MD 提取后写入）"""
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    db.execute(
        "INSERT OR REPLACE INTO manual_assets "
        "(date, cash_detail, real_estate_equity, total_liabilities, monthly_income, monthly_expense) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (today, json.dumps(cash_detail, ensure_ascii=False),
         real_estate_equity, total_liabilities, income, expense),
    )
    db.commit()
    db.close()


def get_latest_manual_assets() -> dict:
    """获取最新手动资产信息"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM manual_assets ORDER BY date DESC LIMIT 1"
    ).fetchone()
    db.close()
    if row:
        d = dict(row)
        d["cash_detail"] = json.loads(d["cash_detail"]) if d["cash_detail"] else []
        return d
    return {}


# ── 分析日志 ──────────────────────────────

def log_analysis(prompt_name: str, file_path: str):
    """记录分析报告"""
    db = get_db()
    db.execute(
        "INSERT INTO analysis_log (date, prompt, file_path) VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M"), prompt_name, file_path),
    )
    db.commit()
    db.close()


def get_recent_analyses(limit: int = 10) -> list:
    """最近分析报告"""
    db = get_db()
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM analysis_log ORDER BY date DESC LIMIT ?", (limit,)
    )]
    db.close()
    return rows


# ── 一键 summary（给分析用的上下文快照）───

def get_context_summary() -> str:
    """生成一段给 LLM 的数据库摘要"""
    db = get_db()

    # 最新快照
    snap = db.execute("SELECT * FROM snapshots ORDER BY date DESC LIMIT 1").fetchone()
    if not snap:
        db.close()
        return ""

    # 最新持仓
    holdings = [dict(r) for r in db.execute(
        "SELECT h.*, p.price as current_price, p.market_value, p.pnl, p.change_pct "
        "FROM holdings h "
        "LEFT JOIN (SELECT code, price, market_value, pnl, change_pct FROM prices "
        "           WHERE date=(SELECT MAX(date) FROM prices)) p ON h.code=p.code"
    )]

    # 手动资产
    manual = db.execute("SELECT * FROM manual_assets ORDER BY date DESC LIMIT 1").fetchone()

    lines = ["## 数据库摘要", f"_快照日期: {snap['date']}_", ""]
    lines.append(f"**总投资**: ¥{snap['total_investment']:,.0f} | "
                 f"**总成本**: ¥{snap['total_cost']:,.0f} | "
                 f"**总盈亏**: ¥{snap['total_pnl']:,.0f} ({snap['pnl_pct']:+.1f}%)")
    if snap["cash"] > 0:
        lines.append(f"**现金**: ¥{snap['cash']:,.0f}")
    if manual:
        d = dict(manual)
        lines.append(f"**月收入**: ¥{d['monthly_income']:,.0f} | "
                     f"**月支出**: ¥{d['monthly_expense']:,.0f} | "
                     f"**负债**: ¥{d['total_liabilities']:,.0f}")

    lines.append("")
    lines.append("| 代码 | 名称 | 类型 | 持仓 | 成本价 | 现价 | 市值 | 盈亏 |")
    lines.append("|------|------|------|------|--------|------|------|------|")
    for h in holdings:
        lines.append(
            f"| {h['code']} | {h['name']} | {h['type']} | {h['shares']:,.0f} | "
            f"¥{h['cost_basis']:.2f} | ¥{h.get('current_price', 0):.2f} | "
            f"¥{h.get('market_value', 0):,.0f} | "
            f"{'🟢' if h.get('pnl', 0) >= 0 else '🔴'} ¥{h.get('pnl', 0):,.0f} |"
        )

    db.close()
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_context_summary())
