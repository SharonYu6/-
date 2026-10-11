"""竞争格局 & 类目深耕评估。

competitors.csv 来自 Amazon（卖家精灵/JS 导出，含 monthly_sales）或 Wayfair 爬虫（无销量，
用评论数作销量代理）。两者可以合并，用 platform 列区分。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..lexicon import ATTRIBUTE_DIMENSIONS
from .text import match_labels


def _sales_col(df: pd.DataFrame) -> tuple[pd.Series, str]:
    if "monthly_sales" in df.columns and df["monthly_sales"].notna().any():
        return df["monthly_sales"].fillna(0).astype(float), "monthly_sales"
    # Wayfair 等不公开销量：评论数作为累计销量代理
    return df.get("reviews", pd.Series(0, index=df.index)).fillna(0).astype(float), "reviews(代理)"


def _price_bands(df: pd.DataFrame, sales: pd.Series) -> list[dict]:
    """价格带分析。胜率 = 该价格带里进入"头部"（销量 ≥ 全体 70 分位）的竞品比例。

    胜率高 + 竞品数适中的价格带 = 新品最容易跑出来的"胜率价位"。
    """
    prices = df["price"].astype(float)
    edges = np.unique(np.quantile(prices, [0, 0.2, 0.4, 0.6, 0.8, 1.0]).round(0))
    if len(edges) < 3:
        edges = np.array([prices.min(), prices.median(), prices.max() + 1])
    edges[-1] += 0.01
    bands = pd.cut(prices, edges, include_lowest=True, right=False)
    head = sales >= sales.quantile(0.7)
    rows = []
    for band, idx in df.groupby(bands, observed=True).groups.items():
        s = sales.loc[idx]
        rows.append({
            "band": f"${band.left:.0f}-{band.right:.0f}",
            "low": float(band.left),
            "high": float(band.right),
            "listings": int(len(idx)),
            "sales": float(s.sum()),
            "sales_share": round(float(s.sum() / sales.sum()), 4) if sales.sum() else 0,
            "sales_per_listing": round(float(s.mean()), 1),
            "win_rate": round(float(head.loc[idx].mean()), 4),
            "avg_rating": round(float(df.loc[idx, "rating"].mean()), 2) if "rating" in df else None,
        })
    if rows:
        best = max(rows, key=lambda r: r["sales_per_listing"])
        best["is_opportunity"] = True
        eligible = [r for r in rows if r["listings"] >= 3] or rows
        win = max(eligible, key=lambda r: (r["win_rate"], r["sales_per_listing"]))
        win["is_win_band"] = True
    return rows


def attribute_supply_demand(competitors: pd.DataFrame, keyword_result: dict | None) -> list[dict]:
    """供需差：关键词搜索量占比（需求） vs 竞品标题中该属性的销量占比（供给）。

    gap > 0 说明有人搜、货不够/不对 -> 蓝海属性。
    """
    if keyword_result is None or "title" not in competitors:
        return []
    sales, _ = _sales_col(competitors)
    total = sales.sum() or 1
    rows = []
    for dim, mapping in ATTRIBUTE_DIMENSIONS.items():
        titles = competitors["title"].map(lambda t, m=mapping: match_labels(t, m))
        for item in keyword_result["dimensions"][dim]["labels"]:
            mask = titles.map(lambda labels, lab=item["label"]: lab in labels)
            supply_share = float(sales[mask].sum() / total)
            rows.append({
                "dimension": dim,
                "label": item["label"],
                "demand_share": item["share"],
                "supply_share": round(supply_share, 4),
                "listings": int(mask.sum()),
                "gap": round(item["share"] - supply_share, 4),
                "growth_yoy": item.get("growth_yoy"),
            })
    return sorted(rows, key=lambda r: -r["gap"])


def analyze_competition(df: pd.DataFrame, keyword_result: dict | None = None, today: str | None = None) -> dict:
    df = df.copy()
    sales, sales_basis = _sales_col(df)
    df["sales_metric"] = sales
    df["revenue_metric"] = sales * df["price"].astype(float)
    total_rev = float(df["revenue_metric"].sum()) or 1.0

    out: dict = {"listings": int(len(df)), "sales_basis": sales_basis}
    if "platform" in df:
        out["platforms"] = df["platform"].value_counts().to_dict()
    out["price"] = {
        "median": round(float(df["price"].median()), 2),
        "p25": round(float(df["price"].quantile(0.25)), 2),
        "p75": round(float(df["price"].quantile(0.75)), 2),
    }
    if sales_basis == "monthly_sales":
        out["market_monthly_units"] = int(sales.sum())
        out["market_monthlyrevenue_metric"] = round(total_rev, 0)

    if "brand" in df:
        brand_rev = df.groupby("brand")["revenue_metric"].sum().sort_values(ascending=False)
        out["brand_count"] = int(brand_rev.size)
        out["cr3"] = round(float(brand_rev.head(3).sum() / total_rev), 4)
        out["cr5"] = round(float(brand_rev.head(5).sum() / total_rev), 4)
        out["top_brands"] = [
            {"brand": b, "revenue_share": round(float(v / total_rev), 4)} for b, v in brand_rev.head(8).items()
        ]

    top10 = df.nlargest(10, "sales_metric")
    if "reviews" in df:
        out["top10_median_reviews"] = int(top10["reviews"].median())
    if "rating" in df:
        out["top10_avg_rating"] = round(float(top10["rating"].mean()), 2)
        out["low_rated_bestsellers"] = [
            {"asin": r.asin, "title": str(getattr(r, "title", ""))[:80], "rating": r.rating, "sales": int(r.sales_metric)}
            for r in df[(df["rating"] < 4.2)].nlargest(5, "sales_metric").itertuples()
        ]

    if "launch_date" in df:
        ref = pd.Timestamp(today) if today else pd.to_datetime(df["launch_date"]).max()
        age_days = (ref - pd.to_datetime(df["launch_date"])).dt.days
        new = age_days <= 365
        out["new_listing_count_12m"] = int(new.sum())
        out["new_listing_sales_share_12m"] = round(float(df.loc[new, "sales_metric"].sum() / (sales.sum() or 1)), 4)

    out["price_bands"] = _price_bands(df, sales)
    out["attribute_gaps"] = attribute_supply_demand(df, keyword_result)[:15]
    out["top_listings"] = [
        {
            "asin": r.asin,
            "title": str(getattr(r, "title", ""))[:90],
            "brand": getattr(r, "brand", None),
            "price": float(r.price),
            "sales": int(r.sales_metric),
            "reviews": int(getattr(r, "reviews", 0) or 0),
            "rating": float(getattr(r, "rating", 0) or 0),
            "platform": getattr(r, "platform", "amazon"),
        }
        for r in top10.itertuples()
    ]
    return out


def category_depth_score(competition: dict, category_trend: dict | None, voc: dict | None) -> dict:
    """类目深耕评分（0-100），每项 0-20 分，附理由。"""
    items = []

    def add(name: str, score: float, reason: str) -> None:
        items.append({"factor": name, "score": round(max(0.0, min(20.0, score)), 1), "reason": reason})

    sv = (category_trend or {}).get("search_volume") or (category_trend or {}).get("units_sold") or {}
    yoy = sv.get("yoy_last_12m")
    if yoy is None:
        add("市场增长", 10, "无同比数据，给中性分")
    else:
        add("市场增长", 10 + yoy * 50, f"近 12 个月同比 {yoy:+.0%}")

    cr5 = competition.get("cr5")
    if cr5 is None:
        add("垄断程度", 10, "无品牌数据")
    else:
        add("垄断程度", 20 * (1 - cr5) / 0.6 if cr5 > 0.4 else 20, f"CR5 品牌销售额占比 {cr5:.0%}（<40% 为分散市场）")

    new_share = competition.get("new_listing_sales_share_12m")
    if new_share is None:
        add("新品机会", 10, "无上架时间数据")
    else:
        add("新品机会", new_share * 80, f"近 12 个月新品拿走 {new_share:.0%} 销量（>25% 说明新品容易起量）")

    med_reviews = competition.get("top10_median_reviews")
    if med_reviews is None:
        add("评论壁垒", 10, "无评论数据")
    else:
        add("评论壁垒", 20 - 20 * min(med_reviews, 5000) / 5000, f"Top10 评论数中位数 {med_reviews}（越低越容易追）")

    if voc and voc.get("pain_points"):
        top = voc["pain_points"][0]
        unsolved = sum(p["negative_mention_rate"] for p in voc["pain_points"][:3])
        add("可改进空间", min(20, unsolved * 60), f"差评前三痛点合计提及率 {unsolved:.0%}，首要痛点：{top['theme']}")
    else:
        add("可改进空间", 10, "无评论数据")

    total = round(sum(i["score"] for i in items), 1)
    if total >= 70:
        verdict = "值得深耕：增长 + 分散 + 痛点明确，可以做系列化产品线"
    elif total >= 55:
        verdict = "可以切入：选准细分属性/价格带打差异化，再视数据决定是否扩线"
    elif total >= 40:
        verdict = "谨慎：只做单品测款，不建议重投入"
    else:
        verdict = "不建议：增长弱或壁垒高"
    return {"score": total, "verdict": verdict, "factors": items}
