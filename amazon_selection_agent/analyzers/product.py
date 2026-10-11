"""汇总：用户画像 + 产品开发方案（爆款假设）。

纯规则版，不依赖大模型，保证离线也能出一份可执行方案；agent.py 会在此基础上让 Claude 深化。
"""

from __future__ import annotations

MONTH_ORDER = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]


def _pick(labels: list[dict], gaps: dict[str, float], k: int = 2) -> list[dict]:
    """按 搜索量占比 × (0.1 + 同比增长) × (1 + 2×供需差) 排序选属性。

    (0.1 + 增长) 让"正在新增的需求"主导排序：大而不涨的泛词（如 bathroom mirror）
    会排在小而快涨的细分词（如 small space、wavy）后面；没有同比数据时退化为按搜索量排序。
    """
    scored = []
    for item in labels:
        growth = item.get("growth_yoy") or 0.0
        gap = gaps.get(item["label"], 0.0)
        score = item["share"] * (0.1 + max(growth, 0.0)) * (1 + max(gap, -0.4) * 2)
        scored.append({**item, "supply_gap": round(gap, 4), "score": round(score, 4)})
    return sorted(scored, key=lambda r: -r["score"])[:k]


def build_persona(keywords: dict | None, voc: dict | None) -> dict:
    persona: dict = {"segments": [], "evidence": []}
    if keywords:
        persona["segments"] = keywords.get("persona_signals", [])[:4]
        for row in keywords["dimensions"]["scene"]["labels"][:4]:
            persona["evidence"].append(f"搜索词「{row['label']}」占 {row['share']:.0%} 搜索量，如 {', '.join(row['top_keywords'][:2])}")
    if voc:
        for row in voc.get("who_buys", [])[:4]:
            persona["evidence"].append(f"评论提及「{row['label']}」{row['mentions']} 次（{row['rate']:.0%}）")
        persona["what_they_value"] = [d["theme"] for d in voc.get("delights", [])[:4]]
        persona["what_they_hate"] = [p["theme"] for p in voc.get("pain_points", [])[:4]]
    return persona


def propose_product(keywords: dict | None, trends: dict | None, competition: dict | None,
                    voc: dict | None, depth: dict | None) -> dict:
    gaps: dict[str, float] = {}
    if competition:
        gaps = {g["label"]: g["gap"] for g in competition.get("attribute_gaps", [])}

    spec: dict = {}
    if keywords:
        dims = keywords["dimensions"]
        for dim in ["scene", "pattern_shape", "color", "style", "material", "feature"]:
            spec[dim] = _pick(dims[dim]["labels"], gaps, k=2)
        spec["size"] = dims["size"].get("inch_buckets", [])[:2]
        spec["exact_sizes"] = dims["size"].get("top_exact_sizes", [])[:3]

    price = None
    if competition:
        opp = [b for b in competition.get("price_bands", []) if b.get("is_opportunity")]
        if opp:
            price = {"band": opp[0]["band"], "why": f"该价格带单品平均销量最高（{opp[0]['sales_per_listing']}），竞品 {opp[0]['listings']} 个"}

    improvements = []
    if voc:
        for p in voc.get("pain_points", [])[:5]:
            improvements.append({"pain_point": p["theme"], "negative_mention_rate": p["negative_mention_rate"], "fix": p["improvement"]})

    timing = None
    sv = (trends or {}).get("search_volume") or (trends or {}).get("units_sold")
    if sv and sv.get("seasonality_index"):
        peak = sv["peak_months"][0]
        peak_i = MONTH_ORDER.index(peak)
        timing = {
            "peak_months": sv["peak_months"],
            "launch_by": MONTH_ORDER[(peak_i - 3) % 12],
            "stock_in_fba_by": MONTH_ORDER[(peak_i - 2) % 12],
            "note": "上架后需 6-8 周积累评论和权重，因此在旺季前 3 个月上新",
        }
        bf = sv.get("events", {}).get("black_friday_multiplier")
        if bf:
            timing["black_friday_multiplier"] = bf

    def names(dim: str) -> str:
        return " / ".join(x["label"] for x in spec.get(dim, [])) or "（数据不足）"

    concept = (
        f"面向「{names('scene')}」场景，主打「{names('pattern_shape')}」款式、「{names('color')}」配色"
        + (f"、{spec['size'][0]['label']}" if spec.get("size") else "")
        + (f"，定价 {price['band']}" if price else "")
        + (f"，重点解决「{improvements[0]['pain_point']}」痛点" if improvements else "")
    )

    listing_keywords = []
    if keywords:
        listing_keywords = [k["keyword"] for k in (keywords.get("rising_keywords") or keywords["top_keywords"])[:10]]

    return {
        "concept": concept,
        "spec": spec,
        "price": price,
        "improvements": improvements,
        "launch_timing": timing,
        "listing_keywords": listing_keywords,
        "category_depth": depth,
        "product_line_ideas": _product_line(spec),
    }


def _product_line(spec: dict) -> list[str]:
    """类目深耕：同一视觉语言做 SKU 矩阵。"""
    ideas = []
    shapes = [x["label"] for x in spec.get("pattern_shape", [])]
    colors = [x["label"] for x in spec.get("color", [])]
    if shapes and colors:
        ideas.append(f"主款：{shapes[0]} × {'/'.join(colors)} 多色变体，同一 Listing 合并评论")
    if spec.get("size"):
        ideas.append("尺寸梯度：小号（桌面/挂墙）+ 大号（全身/落地）两个尺寸覆盖不同空间")
    if len(shapes) > 1:
        ideas.append(f"第二款式：{shapes[1]}，复用供应链与包装")
    ideas.append("延伸同风格配套品（如同纹理的置物架/相框/收纳盒），做店铺风格统一的品牌矩阵")
    return ideas
