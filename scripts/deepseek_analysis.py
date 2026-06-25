"""
DeepSeek API 分析模块
读取本地财务数据 + 市场数据，调用 DeepSeek API 生成分析建议
运行: python scripts/deepseek_analysis.py --prompt prompts/monthly_review.md
"""

import os
import sys
import argparse
from pathlib import Path
from openai import OpenAI

PROJECT_ROOT = Path(__file__).parent.parent


def load_file(filepath: str) -> str:
    """读取文件内容"""
    p = Path(filepath)
    if not p.is_absolute():
        p = PROJECT_ROOT / filepath
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def build_context(
    include_assets: bool = True,
    include_income: bool = True,
    include_insurance: bool = True,
    include_liabilities: bool = True,
    include_goals: bool = True,
    include_snapshot: bool = True,
) -> str:
    """组合所有财务数据为一个上下文"""
    sections = []

    files = []
    if include_assets:
        files.append(("finance/assets.md", "## 资产明细"))
    if include_income:
        files.append(("finance/income.md", "## 营收情况"))
    if include_insurance:
        files.append(("finance/insurance.md", "## 保险保障"))
    if include_liabilities:
        files.append(("finance/liabilities.md", "## 负债情况"))
    if include_goals:
        files.append(("finance/goals.md", "## 财务目标"))
    if include_snapshot:
        snapshot = PROJECT_ROOT / "finance" / "portfolio_snapshot.md"
        if snapshot.exists():
            files.append(("finance/portfolio_snapshot.md", "## 📈 最新市值快照"))

    for path, title in files:
        try:
            content = load_file(path)
            sections.append(f"\n---\n{title}\n---\n{content}")
        except FileNotFoundError:
            pass

    return "\n".join(sections)


def call_deepseek(prompt: str, context: str, api_key: str = None, base_url: str = None) -> str:
    """调用 DeepSeek API 进行分析"""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"

    if not api_key:
        # 尝试从 .env 读取
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY，请设置环境变量或在 .env 中配置")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120)

    system_prompt = """你是一位专业的个人理财顾问（CFP持证人），擅长：
1. 资产配置分析与再平衡建议
2. 保险保障缺口评估
3. 现金流分析与预算优化
4. 基于用户财务目标的个性化规划

分析原则：
- 所有建议基于用户提供的数据，不凭空假设
- 引用具体数字支撑你的分析
- 区分"当前可行的立即行动"和"长期规划"
- 对市场预测保持谨慎，不做确定性承诺
- 使用简体中文输出"""

    full_prompt = f"""以下是我的个人财务数据和市场行情：

{context}

---
{prompt}
---
请基于以上数据给出分析。"""

    print("🤖 正在调用 DeepSeek API...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.7,
        max_tokens=4096,
        stream=True,
    )

    result = []
    for chunk in response:
        if chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
            print(text, end="", flush=True)
            result.append(text)

    print("\n")
    return "".join(result)


def main():
    parser = argparse.ArgumentParser(description="DeepSeek 财务分析")
    parser.add_argument("--prompt", default="prompts/monthly_review.md",
                        help="分析提示词文件路径")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（可选）")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="不包含市值快照")
    args = parser.parse_args()

    print("=" * 50)
    print("🧠 AI 财务分析 — DeepSeek API")
    print("=" * 50)

    # 加载分析提示词
    try:
        prompt = load_file(args.prompt)
        print(f"📋 加载提示词: {args.prompt}")
    except FileNotFoundError:
        print(f"⚠️ 提示词文件不存在: {args.prompt}，使用默认提示词")
        prompt = "请对我的财务状况进行整体评估，指出亮点、风险和下一步行动建议。"

    # 组合数据上下文
    print("📊 汇总财务数据...")
    context = build_context(include_snapshot=not args.no_snapshot)
    print(f"   上下文长度: {len(context)} 字符\n")

    # 调用 DeepSeek
    try:
        result = call_deepseek(prompt, context)
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        sys.exit(1)

    # 保存结果
    if args.output:
        output_path = PROJECT_ROOT / args.output
    else:
        from datetime import datetime
        output_path = PROJECT_ROOT / "finance" / f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 财务分析报告\n> 生成时间: {output_path.stem}\n> 提示词: {args.prompt}\n\n")
        f.write(result)

    print(f"📁 分析报告已保存到: {output_path}")

    # 微信推送
    try:
        from wechat_push import push_analysis_summary
        push_analysis_summary(str(output_path), prompt_name=Path(args.prompt).stem)
    except Exception as e:
        print(f"⚠️ 微信推送跳过: {e}")


if __name__ == "__main__":
    main()
