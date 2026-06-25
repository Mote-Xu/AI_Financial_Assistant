"""
定时自动化脚本 — 更新行情 + 分析 + 推送
用于 Windows Task Scheduler / cron 调用
用法：python scripts/auto_runner.py [--prompt monthly_review]
"""

import sys
import os
from pathlib import Path

# 清除代理环境变量
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
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
    output_file = PROJECT_ROOT / "finance" / "portfolio_snapshot.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(summary)

    # 追加历史
    save_history(holdings, security_prices, fund_navs, total_value, total_cost, total_pnl)

    return output_file


def run_analysis(prompt_name: str = "monthly_review"):
    """运行分析"""
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

    output_path = PROJECT_ROOT / "finance" / \
        f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 财务分析报告\n> 自动生成: {datetime.now()}\n> 提示词: {prompt_file}\n\n")
        f.write(result)

    print(f"📁 报告已保存: {output_path}")

    # 推送
    try:
        from wecom_push import push_analysis
        push_analysis(str(output_path), prompt_name=prompt_name)
    except Exception:
        try:
            from wechat_push import push_analysis_summary
            push_analysis_summary(str(output_path), prompt_name=prompt_name)
        except Exception as e:
            print(f"⚠️ 推送失败: {e}")

    return output_path


def main():
    prompt_name = "monthly_review"
    if "--prompt" in sys.argv:
        idx = sys.argv.index("--prompt")
        prompt_name = sys.argv[idx + 1]

    print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始自动运行\n")

    # 1. 行情
    snapshot = run_market_data()
    if snapshot is None:
        print("❌ 行情获取失败，终止")
        sys.exit(1)

    # 2. 分析 + 推送
    report = run_analysis(prompt_name)
    if report:
        print(f"\n✅ 自动运行完成 — {datetime.now().strftime('%H:%M:%S')}")
    else:
        print("\n⚠️ 行情已更新，但分析失败")

    print(f"📊 历史记录: {PROJECT_ROOT / 'finance' / 'history.csv'}")


if __name__ == "__main__":
    main()
