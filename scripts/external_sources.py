"""
外部情报数据源
抓取 CLS 财联社电报 + NewsAPI + akshare 宏观数据 + THS 全球财经
运行: python scripts/external_sources.py
"""

import os
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"]:
    os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

import akshare as ak
import pandas as pd
import requests
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from config import INTELLIGENCE_DIR, FINANCE_DIR, log_warning, log_error

# ── NewsAPI 配置 ───────────────────────────────────────────
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
NEWSAPI_BASE = "https://newsapi.org/v2"

# ── 噪音关键词（阶段 1 剔除） ──────────────────────────────
NOISE_KEYWORDS = [
    # 娱乐/体育/八卦
    "娱乐", "体育", "篮球", "足球", "演唱会", "综艺", "八卦",
    "明星", "电影票房", "选秀",
    # 交易噪音
    "主力净流入", "竞价看点", "龙虎榜", "涨停板", "跌停板",
    "打板", "连板", "炸板", "地板",
    # 无关行业
    "比特币", "NFT", "元宇宙", "Web3",
    # 广告/软文
    "荐股", "加群", "扫码", "领取牛股",
]

# ── 宏观关键词（🅰️ 通道必过） ─────────────────────────────
MACRO_KEYWORDS = [
    # 央行/货币政策
    "央行", "降准", "降息", "加息", "准备金", "LPR", "MLF", "SLF",
    "逆回购", "公开市场", "货币政策", "流动性",
    # 宏观指标
    "CPI", "PPI", "PMI", "GDP", "M2", "社融", "新增贷款",
    "外汇储备", "进出口", "贸易",
    # 财政/政策
    "财政部", "国务院", "证监会", "银保监会", "发改委",
    "减税", "赤字", "专项债", "特别国债",
    # 房地产
    "房贷", "首付", "限购", "公积金", "契税", "房地产税",
    # 国际
    "美联储", "欧央行", "加息", "缩表", "非农",
]

# ── 辅助函数 ────────────────────────────────────────────────

def _make_id(title: str, source: str) -> str:
    """生成新闻唯一 ID（SHA256 前 12 位）"""
    raw = f"{source}:{title}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _normalize_date(d, default: datetime) -> str:
    """将各种日期格式统一为 ISO 字符串"""
    if d is None or (isinstance(d, float) and pd.isna(d)):
        return default.strftime("%Y-%m-%dT%H:%M")
    if isinstance(d, datetime):
        return d.strftime("%Y-%m-%dT%H:%M")
    s = str(d).strip()
    # 尝试多种格式
    for fmt in [
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M",
        "%Y-%m-%d", "%Y%m%d",
    ]:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    # 如果无法解析，返回今天
    return default.strftime("%Y-%m-%dT%H:%M")


def _clean_text(text: str) -> str:
    """清洗文本：去 HTML、去多余空白"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── 数据源 1：CLS 财联社电报 ─────────────────────────────────

def fetch_cls_telegraph() -> list[dict]:
    """获取 CLS 财联社全球财经电报"""
    items = []
    try:
        df = ak.stock_info_global_cls()
        if df is None or df.empty:
            log_warning("CLS telegraph returned empty")
            return items

        now = datetime.now()
        for _, row in df.iterrows():
            title = _clean_text(str(row.iloc[0]) if df.columns[0] != "title" else str(row.get("title", "")))
            content = _clean_text(str(row.iloc[1]) if len(df.columns) > 1 else "")

            # 跳过空标题
            if not title or len(title) < 6:
                continue

            published = now
            if len(df.columns) > 2:
                published = _normalize_date(row.iloc[2], now)
            elif "time" in [c.lower() for c in df.columns]:
                published = _normalize_date(row.get("time"), now)

            url = ""
            if len(df.columns) > 3:
                url = str(row.iloc[3]) if row.iloc[3] and not pd.isna(row.iloc[3]) else ""

            items.append({
                "id": _make_id(title, "CLS"),
                "title": title,
                "content": content or title,
                "source": "CLS",
                "source_type": "telegraph",
                "published_at": _normalize_date(published, now),
                "url": url,
                "tags": _extract_tags(title + " " + content),
            })
    except Exception as e:
        log_error(f"CLS telegraph fetch failed: {e}")

    return items


# ── 数据源 2：akshare 宏观数据 ────────────────────────────────

def fetch_macro_data() -> list[dict]:
    """获取宏观数据（PMI/CPI/LPR/M2/GDP），格式化为新闻条目"""
    items = []
    today = datetime.now().strftime("%Y-%m-%d")

    fetchers = [
        ("PMI", lambda: ak.macro_china_pmi(), "制造业 PMI"),
        ("CPI", lambda: ak.macro_china_cpi(), "居民消费价格指数 CPI"),
        ("LPR", lambda: ak.macro_china_lpr(), "贷款市场报价利率 LPR"),
        ("M2", lambda: ak.macro_china_money_supply(), "货币供应量 M2"),
        ("GDP", lambda: ak.macro_china_gdp(), "国内生产总值 GDP"),
    ]

    for name, fetcher, label in fetchers:
        try:
            df = fetcher()
            if df is None or df.empty:
                continue

            # 取最近一行
            latest = df.tail(1).iloc[0]
            # 把整行转成可读文本
            parts = []
            for col in df.columns:
                val = latest[col]
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    parts.append(f"{col}: {val}")
            text = " | ".join(parts)

            items.append({
                "id": _make_id(f"macro_{name}_{today}", "MACRO"),
                "title": f"📊 {label} 最新数据",
                "content": text,
                "source": "MACRO",
                "source_type": "macro",
                "published_at": today + "T08:00",
                "url": "",
                "tags": ["宏观", name],
            })
        except Exception as e:
            log_warning(f"Macro {name} fetch failed: {e}")

    return items


# ── 数据源 3：NewsAPI ─────────────────────────────────────────

def fetch_newsapi() -> list[dict]:
    """获取 NewsAPI 全球新闻"""
    items = []
    if not NEWSAPI_KEY:
        log_warning("NEWSAPI_KEY not set, skipping NewsAPI")
        return items

    try:
        # 查询财经/市场相关，中文
        params = {
            "apiKey": NEWSAPI_KEY,
            "q": "中国 OR 市场 OR 经济 OR 政策 OR 房地产 OR 利率 OR 央行 OR A股",
            "language": "zh",
            "sortBy": "publishedAt",
            "pageSize": 50,
            "from": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        }
        resp = requests.get(f"{NEWSAPI_BASE}/everything", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for article in data.get("articles", []):
            title = _clean_text(article.get("title", ""))
            description = _clean_text(article.get("description", ""))
            if not title or len(title) < 6:
                continue

            items.append({
                "id": _make_id(title, "NewsAPI"),
                "title": title,
                "content": description or title,
                "source": article.get("source", {}).get("name", "NewsAPI"),
                "source_type": "news",
                "published_at": article.get("publishedAt", datetime.now().isoformat()),
                "url": article.get("url", ""),
                "tags": _extract_tags(title + " " + description),
            })
    except requests.RequestException as e:
        log_error(f"NewsAPI fetch failed: {e}")
    except Exception as e:
        log_error(f"NewsAPI unexpected error: {e}")

    return items


# ── 数据源 4：同花顺全球财经（补充） ──────────────────────────

def fetch_ths_global() -> list[dict]:
    """获取同花顺全球财经（作为补充源）"""
    items = []
    try:
        df = ak.stock_info_global_ths()
        if df is None or df.empty:
            return items

        now = datetime.now()
        for _, row in df.iterrows():
            title = _clean_text(str(row.iloc[0]))
            content = _clean_text(str(row.iloc[1])) if len(df.columns) > 1 else ""
            published = now
            url = ""

            if len(df.columns) > 2:
                published = _normalize_date(row.iloc[2], now)
            if len(df.columns) > 3:
                url = str(row.iloc[3]) if not pd.isna(row.iloc[3]) else ""

            if not title or len(title) < 6:
                continue

            items.append({
                "id": _make_id(title, "THS"),
                "title": title,
                "content": content or title,
                "source": "THS",
                "source_type": "news",
                "published_at": _normalize_date(published, now),
                "url": url,
                "tags": _extract_tags(title + " " + content),
            })
    except Exception as e:
        log_error(f"THS global fetch failed: {e}")

    return items


# ── 数据源 5：百度财经（兜底） ─────────────────────────────────

def fetch_baidu_economic_news() -> list[dict]:
    """获取百度财经经济新闻"""
    items = []
    try:
        df = ak.news_economic_baidu()
        if df is None or df.empty:
            return items

        now = datetime.now()
        for _, row in df.iterrows():
            title = _clean_text(str(row.iloc[0]))
            content = ""
            if len(df.columns) > 3:
                content = _clean_text(str(row.iloc[3]))
            published = now

            if not title or len(title) < 6:
                continue

            items.append({
                "id": _make_id(title, "Baidu"),
                "title": title,
                "content": content or title,
                "source": "Baidu",
                "source_type": "news",
                "published_at": _normalize_date(published, now),
                "url": "",
                "tags": _extract_tags(title + " " + content),
            })
    except Exception as e:
        log_error(f"Baidu economic news fetch failed: {e}")

    return items


# ── 标签提取 ──────────────────────────────────────────────────

def _extract_tags(text: str) -> list[str]:
    """从文本中提取关键词标签"""
    tag_patterns = [
        # 宏观
        ("央行", "央行"), ("降准", "降准"), ("降息", "降息"), ("加息", "加息"),
        ("LPR", "LPR"), ("MLF", "MLF"), ("准备金", "准备金"),
        ("CPI", "CPI"), ("PPI", "PPI"), ("PMI", "PMI"), ("GDP", "GDP"),
        ("M2", "M2"), ("社融", "社融"),
        # 政策
        ("国务院", "政策"), ("证监会", "政策"), ("银保监", "政策"), ("财政部", "政策"),
        ("发改委", "政策"),
        # 市场
        ("A股", "A股"), ("沪深300", "指数"), ("科创", "科创板"),
        ("创业板", "创业板"), ("北交所", "北交所"),
        # 行业
        ("房地产", "房地产"), ("房贷", "房地产"), ("楼市", "房地产"),
        ("银行", "银行"), ("保险", "保险"), ("券商", "券商"),
        ("新能源", "新能源"), ("汽车", "汽车"), ("芯片", "芯片"),
        ("半导体", "半导体"), ("AI", "AI"), ("人工智能", "人工智能"),
        ("医药", "医药"), ("消费", "消费"), ("白酒", "白酒"),
        # 国际
        ("美联储", "美联储"), ("欧央行", "欧央行"),
        ("非农", "非农"), ("美股", "美股"),
        # 债券
        ("国债", "债券"), ("企业债", "债券"), ("可转债", "债券"),
        # 商品
        ("黄金", "黄金"), ("原油", "原油"), ("铜", "商品"),
    ]
    tags = []
    text_lower = text.lower()
    for pattern, tag in tag_patterns:
        if pattern.lower() in text_lower:
            if tag not in tags:
                tags.append(tag)
    return tags[:8]  # 限制最多 8 个标签


# ── 主入口 ────────────────────────────────────────────────────

def fetch_all_sources(
    include_cls: bool = True,
    include_macro: bool = True,
    include_newsapi: bool = True,
    include_ths: bool = True,
    include_baidu: bool = True,
) -> list[dict]:
    """
    从所有数据源获取新闻，返回统一格式列表。
    每个源独立运行，一个源失败不影响其他。
    返回按发布时间倒序排列。
    """
    all_items = []

    if include_cls:
        items = fetch_cls_telegraph()
        all_items.extend(items)

    if include_macro:
        items = fetch_macro_data()
        all_items.extend(items)

    if include_newsapi and NEWSAPI_KEY:
        items = fetch_newsapi()
        all_items.extend(items)

    if include_ths:
        items = fetch_ths_global()
        all_items.extend(items)

    if include_baidu:
        items = fetch_baidu_economic_news()
        all_items.extend(items)

    # 去重（按 ID）
    seen = set()
    unique = []
    for item in all_items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)

    # 按发布时间倒序
    unique.sort(key=lambda x: x["published_at"], reverse=True)

    return unique


def stage1_filter(items: list[dict], intelligence_profile: dict = None) -> tuple[list[dict], list[dict], list[dict]]:
    """
    阶段 1 过滤：三通道分类

    Returns:
        (macro_items, profile_hit_items, llm_judge_items)
        - macro_items: 🅰️ 宏观必过
        - profile_hit_items: 🅱️ 画像命中（高相关标记）
        - llm_judge_items: 🅲️ 交给 LLM 判断
    """
    macro_items = []
    profile_hit_items = []
    llm_judge_items = []

    # 构建画像关键词
    profile_keywords = set()
    if intelligence_profile:
        for sector in intelligence_profile.get("sectors", []):
            profile_keywords.add(sector)
        for concern in intelligence_profile.get("concerns", []):
            profile_keywords.add(concern)
        # 持仓名称也加入
        for h in intelligence_profile.get("holdings", []):
            profile_keywords.add(h)
        # 黑名单
        blacklist = set(intelligence_profile.get("keywords_blacklist", []))
    else:
        blacklist = set()

    for item in items:
        text = item["title"] + " " + item["content"]

        # 黑名单检查
        if any(kw in text for kw in blacklist):
            continue

        # 噪音检查
        if any(kw in text for kw in NOISE_KEYWORDS):
            continue

        # 🅰️ 宏观检查
        is_macro = any(kw in text for kw in MACRO_KEYWORDS)

        # 🅱️ 画像命中检查
        is_profile_hit = any(kw in text for kw in profile_keywords) if profile_keywords else False

        if is_macro:
            item["channel"] = "A"
            macro_items.append(item)
        elif is_profile_hit:
            item["channel"] = "B"
            profile_hit_items.append(item)
        else:
            # 纯噪音跳过（无实质内容）
            if len(text) < 20:
                continue
            item["channel"] = "C"
            llm_judge_items.append(item)

    return macro_items, profile_hit_items, llm_judge_items


# ── CLI 测试 ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  外部情报数据源测试")
    print("=" * 60)

    print("\n📡 抓取 CLS 电报...")
    cls_items = fetch_cls_telegraph()
    print(f"   CLS: {len(cls_items)} 条")

    print("📡 抓取宏观数据...")
    macro_items = fetch_macro_data()
    print(f"   Macro: {len(macro_items)} 条")

    print("📡 抓取 NewsAPI...")
    newsapi_items = fetch_newsapi()
    print(f"   NewsAPI: {len(newsapi_items)} 条")

    print("📡 抓取 THS 全球...")
    ths_items = fetch_ths_global()
    print(f"   THS: {len(ths_items)} 条")

    print("\n📡 合并 + 去重...")
    all_items = fetch_all_sources()
    print(f"   总计: {len(all_items)} 条")

    print("\n🔍 阶段 1 过滤...")
    a, b, c = stage1_filter(all_items)
    print(f"   🅰️ 宏观必过: {len(a)} 条")
    print(f"   🅱️ 画像命中: {len(b)} 条")
    print(f"   🅲️ LLM 判断: {len(c)} 条")
    print(f"   送入阶段 2 总计: {len(a) + len(b) + len(c)} 条")

    # 打印宏观样本
    if a:
        print("\n── 🅰️ 宏观样本 ──")
        for item in a[:3]:
            print(f"  [{item['source']}] {item['title'][:80]}")
