"""
系统健康检查 — 每日检测关键组件，异常时推送告警
用法: python scripts/health_check.py
"""

import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from config import (FINANCE_DIR, DB_PATH, SNAPSHOT_FILE,
                    HISTORY_FILE, ensure_finance_dir, log_error)


def check_sqlite() -> dict:
    """检查 SQLite 数据库"""
    try:
        import sqlite3
        db = sqlite3.connect(str(DB_PATH), timeout=5)
        db.execute("SELECT 1")
        rows = db.execute("SELECT COUNT(*) FROM holdings").fetchone()
        db.close()
        count = rows[0] if rows else 0
        return {"ok": True, "detail": f"{count} 条持仓"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:80]}


def check_akshare() -> dict:
    """检查行情数据源"""
    try:
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
            os.environ.pop(k, None)
        import akshare as ak
        df = ak.stock_zh_a_hist(symbol="510300", period="daily",
                                start_date="20260101", end_date="20260115")
        ok = df is not None and len(df) > 0
        return {"ok": ok, "detail": f"{len(df) if df is not None else 0} 条测试数据"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:80]}


def check_deepseek() -> dict:
    """检查 DeepSeek API"""
    try:
        from openai import OpenAI
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            env_file = PROJECT_ROOT / ".env"
            if env_file.exists():
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("DEEPSEEK_API_KEY="):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not api_key:
            return {"ok": False, "detail": "无 API Key"}

        client = OpenAI(api_key=api_key,
                        base_url="https://api.deepseek.com", timeout=30)
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        ok = resp.choices[0].message.content is not None
        return {"ok": ok, "detail": "API 正常"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:80]}


def check_disk() -> dict:
    """检查磁盘空间"""
    try:
        import shutil
        usage = shutil.disk_usage(FINANCE_DIR)
        free_gb = usage.free / (1024 ** 3)
        ok = free_gb > 1
        return {"ok": ok, "detail": f"{free_gb:.1f} GB 可用"}
    except Exception as e:
        return {"ok": False, "detail": str(e)[:80]}


def check_data_files() -> dict:
    """检查数据文件完整性"""
    issues = []
    if not SNAPSHOT_FILE.exists():
        issues.append("快照缺失")
    if not HISTORY_FILE.exists():
        issues.append("历史 CSV 缺失")

    if SNAPSHOT_FILE.exists():
        size = SNAPSHOT_FILE.stat().st_size
        if size < 100:
            issues.append(f"快照过小 ({size}B)")
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            text = f.read()
        if "总市值" not in text or "¥" not in text:
            issues.append("快照格式异常")

    ok = len(issues) == 0
    return {"ok": ok, "detail": "正常" if ok else "; ".join(issues)}


def run_all() -> tuple[list, bool]:
    """运行全部检查，返回 (结果列表, 是否全部通过)"""
    checks = [
        ("SQLite", check_sqlite),
        ("akshare", check_akshare),
        ("DeepSeek", check_deepseek),
        ("磁盘", check_disk),
        ("数据文件", check_data_files),
    ]

    results = []
    all_ok = True
    for name, fn in checks:
        start = time.time()
        try:
            result = fn()
        except Exception as e:
            result = {"ok": False, "detail": str(e)[:80]}
        elapsed = time.time() - start
        if not result["ok"]:
            all_ok = False
            log_error(f"Health check {name} FAIL: {result['detail']}")
        results.append({
            "name": name,
            "ok": result["ok"],
            "detail": result["detail"],
            "time": round(elapsed, 1),
        })
    return results, all_ok


def format_report(results: list, all_ok: bool) -> str:
    """格式化健康报告"""
    status = "✅ 全部正常" if all_ok else "⚠️ 存在异常"
    lines = [f"🏥 系统健康检查 {status}", ""]

    for r in results:
        emoji = "✅" if r["ok"] else "❌"
        lines.append(f"  {emoji} {r['name']:10s} {r['detail']} ({r['time']}s)")

    return "\n".join(lines)


def main():
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    print("Health check running...")
    results, all_ok = run_all()
    print(format_report(results, all_ok))

    # 每天推送健康报告到应用私聊
    try:
        from wecom_app import send_to_user
        send_to_user("XuZiHao", format_report(results, all_ok))
    except Exception:
        pass

    return 0 if all_ok else 1


if __name__ == "__main__":
    main()
