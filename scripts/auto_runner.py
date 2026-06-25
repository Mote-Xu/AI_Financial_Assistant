"""
定时自动化脚本 — 更新行情 + 分析 + 推送
用于 Windows Task Scheduler / cron 调用
用法：python scripts/auto_runner.py [--prompt monthly_review]
"""

import sys
import os

# 清除代理环境变量
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from config import PROJECT_ROOT, FINANCE_DIR, SNAPSHOT_FILE, HISTORY_FILE
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from datetime import datetime


def run_market_data():
    """运行行情更新"""
    from market_data import parse_assets_md, fetch_stock_and_etf_prices, \
        fetch_fund_nav, generate_summary, save_history

    print("=" * 50)
    print(f"🤖 定时自动运行 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    holdings = parse_assets_md()
    if not holdings["stocks"] and not holdings["funds"]:
        print("⚠️ 未找到持仓")
        return None

    security_prices = {}
    fund_navs = {}
    if holdings["stocks"]:
        security_prices = fetch_stock_and_etf_prices(
            [s["code"] for s in holdings["stocks"]]
        )
    if holdings["funds"]:
        fund_navs = fetch_fund_nav([f["code"] for f in holdings["funds"]])

    summary, total_value, total_cost, total_pnl, _ = generate_summary(
        holdings, security_prices, fund_navs
    )
    print(summary)

    # 保存快照
    output_file = SNAPSHOT_FILE
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)

    # 追加历史
    save_history(holdings, security_prices, fund_navs, total_value, total_cost, total_pnl)

    return output_file


def run_analysis(prompt_name: str = "monthly_review", skip_git: bool = False):
    """运行分析 + 推送（文件直发为主，GitHub 为备份）"""
    from deepseek_analysis import load_file, build_context, call_deepseek

    prompt_file = f"prompts/{prompt_name}.md"
    try:
        prompt = load_file(prompt_file)
    except FileNotFoundError:
        print(f"⚠️ 提示词不存在: {prompt_file}")
        return None

    print(f"\n📋 提示词: {prompt_file}")
    context = build_context()
    print(f"📊 上下文: {len(context)} 字符")

    try:
        result = call_deepseek(prompt, context)
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        return None

    output_path = FINANCE_DIR / \
        f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 财务分析报告\n> 自动生成: {datetime.now()}\n> 提示词: {prompt_file}\n\n")
        f.write(result)

    print(f"📁 报告已保存: {output_path}")

    # Git 备份（可选，文件直发才是主要推送方式）
    if not skip_git:
        import subprocess
        try:
            rel = output_path.relative_to(PROJECT_ROOT)
            subprocess.run(["git", "add", str(rel)], cwd=PROJECT_ROOT, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Auto: {prompt_name} {output_path.stem}"],
                           cwd=PROJECT_ROOT, capture_output=True)
            subprocess.run(["git", "push"], cwd=PROJECT_ROOT, capture_output=True)
            print("📤 GitHub 备份已推送")
        except Exception as e:
            print(f"⚠️ GitHub 备份失败（非致命，文件直发不受影响）: {e}")

    # 双通道推送（企微 + 微信各自发完整报告）
    try:
        from wecom_push import push_analysis
        push_analysis(str(output_path), prompt_name=prompt_name)
        print("📱 企微推送完成")
    except Exception as e:
        print(f"⚠️ 企微推送失败: {e}")

    try:
        from wechat_push import push_analysis_summary
        push_analysis_summary(str(output_path), prompt_name=prompt_name)
        print("📱 微信推送完成")
    except Exception as e:
        print(f"⚠️ 微信推送失败: {e}")

    return output_path


def main():
    prompt_name = "monthly_review"
    run_alert = False
    skip_git = False
    if "--prompt" in sys.argv:
        idx = sys.argv.index("--prompt")
        prompt_name = sys.argv[idx + 1]
    if "--alert" in sys.argv:
        run_alert = True
    if "--no-git" in sys.argv:
        skip_git = True

    print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始自动运行")
    print(f"   模式: {'预警' if run_alert else '分析'}")
    if skip_git:
        print(f"   Git: 跳过")

    # 预警模式：只查波动
    if run_alert:
        from market_alert import check_alerts, push_alerts
        alerts = check_alerts(threshold=3.0)
        if alerts:
            push_alerts(alerts, threshold=3.0)
        print(f"\n✅ 预警检查完成 — {datetime.now().strftime('%H:%M:%S')}")
        return

    # 完整模式：行情 + 分析 + 推送
    snapshot = run_market_data()
    if snapshot is None:
        print("❌ 行情获取失败，终止")
        sys.exit(1)

    report = run_analysis(prompt_name, skip_git=skip_git)
    if report:
        print(f"\n✅ 自动运行完成 — {datetime.now().strftime('%H:%M:%S')}")
    else:
        print("\n⚠️ 行情已更新，但分析失败")

    print(f"📊 历史记录: {HISTORY_FILE}")


if __name__ == "__main__":
    main()
