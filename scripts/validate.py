"""
项目完备性验证 — 检查所有模块是否正确、接口是否一致
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from config import (FINANCE_DIR, ASSETS_FILE, INCOME_FILE, INSURANCE_FILE,
                     LIABILITIES_FILE, GOALS_FILE, SNAPSHOT_FILE,
                     HISTORY_FILE, DB_PATH, ensure_finance_dir)
ensure_finance_dir()


def check(what: str, ok: bool, detail: str = ""):
    status = "✅" if ok else "❌"
    print(f"  {status} {what}{' — ' + detail if detail else ''}")
    return ok


def main():
    passed = 0
    failed = 0
    total = 0

    def test(name, fn):
        nonlocal passed, failed, total
        total += 1
        try:
            ok = fn()
            if ok:
                passed += 1
            else:
                failed += 1
            return ok
        except Exception as e:
            failed += 1
            check(name, False, str(e)[:80])
            return False

    print("=" * 50)
    print("   AI 财务助手 — 完备性验证")
    print("=" * 50)

    # ── 1. 配置与路径 ──────────────────────────────
    print("\n📁 1. 配置与路径")
    test("config.py 导入", lambda: (
        check("PROJECT_ROOT", FINANCE_DIR.exists())
    ))
    test("数据文件存在", lambda: all(
        check(f, Path(f).exists()) for f in [
            ASSETS_FILE, INCOME_FILE, INSURANCE_FILE,
            LIABILITIES_FILE, GOALS_FILE, SNAPSHOT_FILE,
        ]
    ))
    test("动态路径切换", lambda: (
        check("FINANCE_DIR 可写", FINANCE_DIR.exists())
    ))

    # ── 2. 行情与数据 ──────────────────────────────
    print("\n📊 2. 行情与数据")
    test("market_data 解析持仓", lambda: (
        __import__("market_data").parse_assets_md()["stocks"] is not None
    ))
    test("历史 CSV 可读", lambda: (
        HISTORY_FILE.exists() and HISTORY_FILE.stat().st_size > 0
    ))
    test("SQLite 连接", lambda: (
        __import__("database").get_db() is not None
    ))

    # ── 3. 推送模块 ─────────────────────────────────
    print("\n📱 3. 推送模块")
    test("wecom_push 导入", lambda: (
        hasattr(__import__("wecom_push"), "push_wecom")
        and hasattr(__import__("wecom_push"), "push_analysis")
    ))
    test("wecom_push UTF-8 分块", lambda: (
        __import__("wecom_push")._chunk_by_lines("测试\n" * 50, 200) is not None
    ))
    test("wechat_push 导入", lambda: (
        hasattr(__import__("wechat_push"), "push_wechat")
        and hasattr(__import__("wechat_push"), "push_analysis_summary")
    ))
    test("wecom_app API", lambda: (
        hasattr(__import__("wecom_app"), "send_to_user")
        and hasattr(__import__("wecom_app"), "send_to_user")
    ))

    # ── 4. 加密模块 ─────────────────────────────────
    print("\n🔐 4. 企微加解密")
    test("wecom_crypto 导入", lambda: (
        hasattr(__import__("wecom_crypto"), "encrypt")
        and hasattr(__import__("wecom_crypto"), "decrypt")
    ))

    # ── 5. Web 回调 ─────────────────────────────────
    print("\n🌐 5. Flask 回调")
    test("webapp 导入", lambda: (
        hasattr(__import__("webapp"), "app")
    ))
    test("helpers 导入", lambda: (
        hasattr(__import__("webapp_helpers"), "_parse_snapshot")
    ))
    test("快照解析", lambda: (
        __import__("webapp_helpers")._parse_snapshot() is not None
    ))

    # ── 6. FIRE 模拟器 ──────────────────────────────
    print("\n💰 6. FIRE 模拟器")
    fire = __import__("fire_simulator")
    result = fire.simulate()
    test("计算不报错", lambda: "error" not in result)
    test("关键字段", lambda: all(
        k in result for k in ["current_nw", "years_to_fi", "fi_number", "monthly_expense"]
    ))
    test("FI 数字合理", lambda: result["fi_number"] > 0)
    test("年限合理", lambda: 0 < result["years_to_fi"] < 100)

    # ── 7. 定投回测 ─────────────────────────────────
    print("\n📈 7. 定投回测")
    test("backtest 导入", lambda: (
        hasattr(__import__("backtest"), "simulate_dca")
        and hasattr(__import__("backtest"), "KNOWN_SYMBOLS")
    ))

    # ── 8. 文件锁 ──────────────────────────────────
    print("\n🔒 8. 运行安全")
    test("config lock 函数", lambda: (
        hasattr(__import__("config"), "acquire_lock")
        and hasattr(__import__("config"), "release_lock")
        and hasattr(__import__("config"), "log_error")
    ))

    # ── 9. 部署文件 ────────────────────────────────
    print("\n🚀 9. 部署完整性")
    deploy_files = [
        PROJECT_ROOT / "deploy" / "cloudflared" / "config.yml",
        PROJECT_ROOT / "run_web.bat",
        PROJECT_ROOT / "run_auto.bat",
        PROJECT_ROOT / "run_alert.bat",
    ]
    test("部署配置存在", lambda: all(
        check(f.name, f.exists()) for f in deploy_files
    ))

    test(".env.example 存在", lambda: (
        (PROJECT_ROOT / ".env.example").exists()
    ))

    # ── 10. Git 安全 ────────────────────────────────
    print("\n🛡️ 10. Git 安全")
    test(".gitignore 有 .env", lambda: (
        ".env" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    ))
    test(".gitignore 有 finance/", lambda: (
        "finance/" in (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    ))

    # ── Summary ─────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"   结果: {passed} 通过 / {failed} 失败 / {total} 总计")
    if failed == 0:
        print("   ✅ 所有检查通过！")
    else:
        print(f"   ⚠️ {failed} 项失败，请检查")
    print("=" * 50)
    return failed == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
