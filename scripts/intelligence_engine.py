"""
外部情报引擎 — 两阶段过滤 + DeepSeek 分析 + 推送
用法:
    python scripts/intelligence_engine.py              # 生成每日简报
    python scripts/intelligence_engine.py --refresh    # 强制重新生成
    python scripts/intelligence_engine.py --midday     # 午间补充（仅 act 级）
    python scripts/intelligence_engine.py --no-push    # 不推送
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import Optional
from openai import OpenAI

# 代理绕过
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

from config import (
    PROJECT_ROOT, FINANCE_DIR, ensure_finance_dir,
    INTELLIGENCE_DIR, BRIEFING_CACHE, BRIEFING_HISTORY, RAW_NEWS_CACHE,
    FAMILY_CONFIG, log_error, log_warning
)
from external_sources import fetch_all_sources, stage1_filter


# ── 评分与推送阈值 ───────────────────────────────────────────

def calculate_push_score(brief: dict) -> float:
    """计算推送综合分"""
    relevance = brief.get("relevance", 0)
    confidence = brief.get("confidence", 5)

    action_map = {"act": 10, "prepare": 7, "watch": 4, "ignore": 0}
    action_score = action_map.get(brief.get("actionability", "ignore"), 0)

    return 0.45 * relevance + 0.35 * action_score + 0.20 * confidence


PUSH_THRESHOLD = 8.0


def should_push(brief: dict) -> bool:
    """判断是否推送企微"""
    if brief.get("actionability") == "act":
        return True  # act 级无条件推送（熔断除外）
    if brief.get("confidence", 5) < 5:
        return False  # 低置信度扣留
    return calculate_push_score(brief) >= PUSH_THRESHOLD


# ── 缓存操作 ──────────────────────────────────────────────────

def load_briefing_cache() -> Optional[dict]:
    """加载今日缓存"""
    if BRIEFING_CACHE.exists():
        try:
            with open(BRIEFING_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 检查是否今日的
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return data
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def save_briefing_cache(data: dict):
    """保存简报缓存"""
    INTELLIGENCE_DIR.mkdir(parents=True, exist_ok=True)
    data["date"] = datetime.now().strftime("%Y-%m-%d")
    data["cached_at"] = datetime.now().isoformat()

    with open(BRIEFING_CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 追加到历史
    with open(BRIEFING_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def merge_midday_briefs(existing: dict, new_briefs: list[dict]) -> dict:
    """午间补充：合并新的 act 级简报到已有缓存"""
    existing_ids = {b["id"] for b in existing.get("briefs", [])}
    added = [b for b in new_briefs if b["id"] not in existing_ids]

    existing["briefs"] = existing.get("briefs", []) + added
    existing["analyzed_count"] = existing.get("analyzed_count", 0) + len(added)
    existing["midday_updated"] = datetime.now().isoformat()
    existing["midday_brief_ids"] = [b["id"] for b in added if should_push(b)]

    return existing


# ── 家庭画像加载 ──────────────────────────────────────────────

def load_intelligence_profile() -> dict:
    """从 family.json 加载 intelligence_profile"""
    if FAMILY_CONFIG.exists():
        try:
            with open(FAMILY_CONFIG, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("intelligence_profile", {})
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


def build_family_context() -> str:
    """构建家庭上下文文本（喂给 AI）"""
    profile = load_intelligence_profile()
    if not profile:
        return "（无家庭画像数据）"

    lines = []
    lines.append("### 家庭持仓标的")
    for h in profile.get("holdings", []):
        lines.append(f"- {h}")
    lines.append("")
    lines.append("### 关注行业")
    lines.append(", ".join(profile.get("sectors", [])))
    lines.append("")
    lines.append("### 资产类别")
    lines.append(", ".join(profile.get("asset_classes", [])))
    lines.append("")
    lines.append("### 核心关注议题")
    for c in profile.get("concerns", []):
        lines.append(f"- {c}")

    return "\n".join(lines)


# ── DeepSeek 调用 ─────────────────────────────────────────────

def call_deepseek_for_briefing(news_text: str, api_key: str = None) -> str:
    """调用 DeepSeek 分析新闻，返回原始 JSON 文本"""
    api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"

    if not api_key:
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("DEEPSEEK_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY")

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=180)

    # 加载提示词
    prompt_path = PROJECT_ROOT / "prompts" / "daily_briefing.md"
    if prompt_path.exists():
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
    else:
        prompt_template = "请分析以下新闻并生成简报。"

    # 填入变量
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    family_context = build_family_context()
    prompt = prompt_template.replace("{current_date}", now.strftime("%Y-%m-%d"))
    prompt = prompt.replace("{weekday}", weekdays[now.weekday()])
    prompt = prompt.replace("{family_context}", family_context)

    system_prompt = """你是家庭首席财务官（Family CFO）的情报分析师。你有以下专业能力：
1. 宏观经济学分析（货币政策、财政政策、经济周期）
2. 行业研究（银行、科技、消费、房地产等）
3. 投资组合分析（能评估新闻对具体持仓的影响）
4. 风险评估（区分市场噪音和真实信号）

分析原则：
- 对每一条新闻独立分析，不互相影响
- 置信度评分要诚实，不确定的事标注出来
- 相关性评分从家庭实际持仓和关注点出发
- 行动建议要具体，不说"注意风险"这种空话
- 输出必须是合法 JSON，不要有 markdown 包裹"""

    full_prompt = f"""以下是今日市场新闻和宏观数据：

{news_text}

---
请按照以下要求进行分析并输出 JSON：
{prompt}"""

    print("🤖 正在调用 DeepSeek 分析情报...")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.5,
        max_tokens=8192,
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


# ── JSON 解析 ─────────────────────────────────────────────────

def parse_briefing_json(raw: str) -> dict:
    """从 DeepSeek 返回的文本中解析 JSON"""
    # 尝试直接解析
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 返回错误信息
    return {"error": "JSON 解析失败", "raw": text[:500]}


def validate_briefing_output(data: dict) -> list[str]:
    """校验 DeepSeek 输出质量，返回警告列表"""
    warnings = []

    if "briefs" not in data:
        warnings.append("缺少 briefs 字段")
        return warnings

    briefs = data["briefs"]
    if not briefs:
        warnings.append("briefs 为空")

    # 检查必填字段
    required = ["title", "category", "summary", "relevance", "confidence", "actionability"]
    for i, b in enumerate(briefs):
        for field in required:
            if field not in b:
                warnings.append(f"brief[{i}] 缺少 {field}")

    # 检查 actionability 合法性
    valid_actions = {"act", "prepare", "watch", "ignore"}
    for i, b in enumerate(briefs):
        if b.get("actionability") not in valid_actions:
            warnings.append(f"brief[{i}] actionability={b.get('actionability')} 不合法")

    # 检查 relevance/confidence 范围
    for i, b in enumerate(briefs):
        for field in ["relevance", "confidence"]:
            val = b.get(field, 0)
            if not isinstance(val, (int, float)) or val < 0 or val > 10:
                warnings.append(f"brief[{i}] {field}={val} 超出 0-10 范围")

    return warnings


# ── 主流程 ────────────────────────────────────────────────────

def generate_briefing(refresh: bool = False, midday: bool = False,
                      no_push: bool = False) -> dict:
    """生成每日简报的主流程"""
    ensure_finance_dir()
    INTELLIGENCE_DIR.mkdir(parents=True, exist_ok=True)

    # 检查缓存
    if not refresh and not midday:
        cached = load_briefing_cache()
        if cached:
            print("📋 使用今日缓存简报")
            return cached

    # 1. 抓取新闻
    print("📡 阶段 0：抓取外部数据源...")
    all_items = fetch_all_sources()
    print(f"   原始新闻: {len(all_items)} 条")

    # 2. 阶段 1 过滤
    print("🔍 阶段 1：三通道分类...")
    profile = load_intelligence_profile()
    macro_items, profile_hits, llm_judge = stage1_filter(all_items, profile)
    print(f"   🅰️ 宏观必过: {len(macro_items)}")
    print(f"   🅱️ 画像命中: {len(profile_hits)}")
    print(f"   🅲️ LLM 判断: {len(llm_judge)}")

    # 合并送入阶段 2
    stage2_input = macro_items + profile_hits + llm_judge
    print(f"   送入 DeepSeek 总计: {len(stage2_input)} 条")

    if not stage2_input:
        print("⚠️ 无新闻需要分析，生成空简报")
        empty = {
            "briefs": [], "news_count": len(all_items), "analyzed_count": 0,
            "macro_sentiment": "neutral", "equity_sentiment": "neutral",
            "bond_sentiment": "neutral", "housing_sentiment": "neutral",
            "top_brief_ids": [], "overall_summary": "今日无重大市场新闻"
        }
        if not midday:
            save_briefing_cache(empty)
        return empty

    # 保存原始新闻（调试用）
    try:
        with open(RAW_NEWS_CACHE, "w", encoding="utf-8") as f:
            json.dump(stage2_input, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 3. 格式化新闻文本
    news_text_parts = []
    for item in stage2_input:
        channel_label = {"A": "宏观", "B": "画像命中", "C": "待判断"}.get(item.get("channel", "C"), "")
        news_text_parts.append(
            f"[{item['id']}][{item['source']}][{channel_label}] {item['title']}\n"
            f"  {item.get('content', '')}\n"
            f"  时间: {item.get('published_at', '')}\n"
            f"  URL: {item.get('url', '')}\n"
        )
    news_text = "\n---\n".join(news_text_parts)

    # 4. 调用 DeepSeek
    print(f"\n🧠 阶段 2：DeepSeek 分析（{len(stage2_input)} 条新闻）...")
    try:
        raw_response = call_deepseek_for_briefing(news_text)
    except Exception as e:
        log_error(f"DeepSeek briefing call failed: {e}")
        print(f"❌ DeepSeek 调用失败: {e}")
        return {"error": str(e), "briefs": []}

    # 5. 解析 JSON
    data = parse_briefing_json(raw_response)
    if "error" in data:
        log_error(f"JSON 解析失败: {data.get('error')}")
        print(f"⚠️ JSON 解析失败: {data.get('error')}")
        return data

    # 6. 校验
    warnings = validate_briefing_output(data)
    if warnings:
        for w in warnings:
            log_warning(f"Briefing validation: {w}")
            print(f"⚠️ {w}")

    # 午间模式：只保留 act 级别
    if midday:
        existing = load_briefing_cache()
        if existing:
            data = merge_midday_briefs(existing, data.get("briefs", []))
        else:
            all_briefs = data.get("briefs", [])
            data["briefs"] = [b for b in all_briefs if b.get("actionability") == "act"]
            data["midday_updated"] = datetime.now().isoformat()
    else:
        # 计算推送分数
        for brief in data.get("briefs", []):
            brief["push_score"] = round(calculate_push_score(brief), 2)
            brief["should_push"] = should_push(brief)

        # 保存缓存
        save_briefing_cache(data)

    # 7. 推送
    if not no_push:
        push_briefing(data, midday=midday)

    print(f"\n✅ 简报生成完成: {len(data.get('briefs', []))} 条分析")
    return data


# ── 推送 ──────────────────────────────────────────────────────

def push_briefing(data: dict, midday: bool = False):
    """推送简报到企业微信"""
    briefs = data.get("briefs", [])
    if not briefs:
        return

    if midday:
        # 午间只推 act 级别
        push_items = [b for b in briefs if b.get("actionability") == "act"]
        title = "🔔 午间紧急情报"
    else:
        # 早间推 top 3
        top_ids = data.get("top_brief_ids", [])
        if top_ids:
            id_map = {b.get("id"): b for b in briefs}
            push_items = [id_map[bid] for bid in top_ids if bid in id_map]
        else:
            # 按推送分数排序取前 3
            scored = sorted(briefs, key=lambda b: b.get("push_score", 0), reverse=True)
            push_items = scored[:3]
        title = "📰 每日情报简报"

    if not push_items:
        print("📱 无推送内容")
        return

    # 格式化 Markdown 消息
    now = datetime.now().strftime("%m-%d %H:%M")
    lines = [f"## {title}", f"> {now}  ·  {data.get('overall_summary', '')}", ""]

    for i, b in enumerate(push_items, 1):
        sentiment = data.get("macro_sentiment", "")
        action_emoji = {"act": "🔴", "prepare": "🟡", "watch": "🟢", "ignore": "⚪"}
        emoji = action_emoji.get(b.get("actionability", "watch"), "⚪")
        score = b.get("push_score", 0)

        lines.append(f"### {i}. {emoji} {b.get('title', '')}")
        lines.append(f"{b.get('summary', '')}")
        if b.get("suggested_action"):
            lines.append(f"> 建议：{b['suggested_action']}")
        lines.append(f"> 相关：{', '.join(b.get('impacted_assets', []) or [])}  "
                     f"| 评分：{score:.1f}")
        lines.append("")

    lines.append("---")
    lines.append("📱 [查看完整看板](https://finance-assistant.mote-pal.xyz/family)")
    message = "\n".join(lines)

    # 推送到企微自建应用
    try:
        from wecom_app import send_markdown_to_user
        user_id = os.environ.get("WECOM_APP_USERID", "")
        if user_id:
            send_markdown_to_user(user_id, message)
            print("📱 企微 Markdown 推送完成")
        else:
            # 兜底：用 webhook
            from wecom_push import push_wecom
            push_wecom(message)
            print("📱 企微 Webhook 推送完成")
    except Exception as e:
        log_error(f"Briefing push failed: {e}")
        print(f"⚠️ 推送失败: {e}")


def get_pushable_briefs(data: dict) -> list[dict]:
    """获取缓存中适合推送的简报（给 webapp 用）"""
    briefs = data.get("briefs", [])
    result = []
    for b in briefs:
        b["push_score"] = round(calculate_push_score(b), 2)
        b["should_push"] = should_push(b)
        result.append(b)
    result.sort(key=lambda x: x["push_score"], reverse=True)
    return result


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="外部情报引擎")
    parser.add_argument("--refresh", action="store_true",
                        help="强制重新生成（忽略缓存）")
    parser.add_argument("--midday", action="store_true",
                        help="午间补充模式（仅 check act 级别）")
    parser.add_argument("--no-push", action="store_true",
                        help="不推送")
    args = parser.parse_args()

    print("=" * 60)
    mode = "午间补充" if args.midday else "每日简报"
    print(f"  🔍 外部情报引擎 — {mode}")
    print("=" * 60)

    result = generate_briefing(
        refresh=args.refresh,
        midday=args.midday,
        no_push=args.no_push
    )

    if "error" in result:
        print(f"\n❌ 简报生成异常: {result['error']}")
        sys.exit(1)

    briefs = result.get("briefs", [])
    if not briefs:
        print("\n📭 今日无相关情报")
    else:
        print(f"\n📊 分析结果: {len(briefs)} 条")
        for b in briefs[:5]:
            score = b.get("push_score", 0)
            print(f"  [{b.get('actionability', '?')}] {b.get('title', '')[:60]} "
                  f"→ score={score:.1f}")

        top = [b for b in briefs if b.get("should_push")]
        if top:
            print(f"\n📱 推送 {len(top)} 条到企微")


if __name__ == "__main__":
    main()
