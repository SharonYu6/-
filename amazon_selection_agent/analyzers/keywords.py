"""关键词需求分析：把关键词按 场景/颜色/款式/尺寸/风格/材质/功能 拆解，按搜索量加权。

例：一批词里 "small space" / "dorm" / "apartment" 搜索量占比高 -> 主力人群是学生/租房族；
"wavy" 占比高且同比增长 -> 波浪纹是上升款式。
"""

from __future__ import annotations

import pandas as pd

from ..lexicon import ATTRIBUTE_DIMENSIONS, DIMENSION_LABELS, SCENE_TO_PERSONA
from .text import match_labels, parse_inches, size_bucket


def _keyword_growth(df: pd.DataFrame) -> pd.Series | None:
    if "search_volume_last_year" in df.columns:
        prev = df["search_volume_last_year"].replace(0, pd.NA)
        return (df["search_volume"] / prev - 1).astype(float)
    if "growth_yoy" in df.columns:  # 已经是百分比小数，如 0.35
        return df["growth_yoy"].astype(float)
    return None


def tag_keywords(df: pd.DataFrame) -> pd.DataFrame:
    """给每个关键词打上各维度标签（list 列）以及解析出的尺寸档。"""
    out = df.copy()
    for dim, mapping in ATTRIBUTE_DIMENSIONS.items():
        out[dim] = out["keyword"].map(lambda k, m=mapping: match_labels(k, m))
    out["size_bucket"] = out["keyword"].map(lambda k: size_bucket(parse_inches(k)))
    growth = _keyword_growth(out)
    if growth is not None:
        out["growth_yoy"] = growth
    return out


def _dimension_table(tagged: pd.DataFrame, dim: str, total_volume: float) -> list[dict]:
    exploded = tagged[["keyword", "search_volume", dim] + (["growth_yoy"] if "growth_yoy" in tagged else [])]
    exploded = exploded.explode(dim).dropna(subset=[dim])
    if exploded.empty:
        return []
    rows = []
    for label, g in exploded.groupby(dim):
        vol = float(g["search_volume"].sum())
        row = {
            "label": label,
            "search_volume": int(vol),
            "share": round(vol / total_volume, 4),
            "keyword_count": int(len(g)),
            "top_keywords": g.nlargest(3, "search_volume")["keyword"].tolist(),
        }
        if "growth_yoy" in g and g["growth_yoy"].notna().any():
            w = g.dropna(subset=["growth_yoy"])
            row["growth_yoy"] = round(float((w["growth_yoy"] * w["search_volume"]).sum() / w["search_volume"].sum()), 4)
        rows.append(row)
    return sorted(rows, key=lambda r: r["search_volume"], reverse=True)


def analyze_keywords(df: pd.DataFrame, top_n: int = 8) -> dict:
    tagged = tag_keywords(df)
    total = float(tagged["search_volume"].sum())
    result: dict = {
        "keyword_count": int(len(tagged)),
        "total_monthly_search_volume": int(total),
        "dimensions": {},
    }
    for dim in ATTRIBUTE_DIMENSIONS:
        result["dimensions"][dim] = {
            "name": DIMENSION_LABELS[dim],
            "labels": _dimension_table(tagged, dim, total)[:top_n],
        }

    sized = tagged.dropna(subset=["size_bucket"])
    if not sized.empty:
        sb = sized.groupby("size_bucket")["search_volume"].sum().sort_values(ascending=False)
        result["dimensions"]["size"]["inch_buckets"] = [
            {"label": k, "search_volume": int(v), "share": round(v / total, 4)} for k, v in sb.items()
        ]
        dims = sized["keyword"].map(parse_inches)
        exact = sized.assign(dims=dims)[dims.map(lambda d: isinstance(d, tuple))]
        if not exact.empty:
            top_dims = exact.groupby(exact["dims"].map(lambda d: f"{d[0]}x{d[1]}in"))["search_volume"].sum()
            result["dimensions"]["size"]["top_exact_sizes"] = [
                {"size": k, "search_volume": int(v)} for k, v in top_dims.sort_values(ascending=False).head(5).items()
            ]

    # 人群推断：场景词搜索量占比 -> 画像
    personas: dict[str, float] = {}
    for row in result["dimensions"]["scene"]["labels"]:
        persona = SCENE_TO_PERSONA.get(row["label"])
        if persona:
            personas[persona] = personas.get(persona, 0) + row["share"]
    result["persona_signals"] = [
        {"persona": p, "search_share": round(s, 4)} for p, s in sorted(personas.items(), key=lambda x: -x[1])
    ]

    if "growth_yoy" in tagged:
        g = tagged.dropna(subset=["growth_yoy"])
        g = g[g["search_volume"] >= g["search_volume"].quantile(0.25)]  # 去掉长尾小词的噪音
        result["rising_keywords"] = [
            {"keyword": r.keyword, "search_volume": int(r.search_volume), "growth_yoy": round(float(r.growth_yoy), 3)}
            for r in g.nlargest(10, "growth_yoy").itertuples()
        ]
        result["declining_keywords"] = [
            {"keyword": r.keyword, "search_volume": int(r.search_volume), "growth_yoy": round(float(r.growth_yoy), 3)}
            for r in g.nsmallest(5, "growth_yoy").itertuples()
        ]

    result["top_keywords"] = [
        {"keyword": r.keyword, "search_volume": int(r.search_volume)}
        for r in tagged.nlargest(15, "search_volume").itertuples()
    ]
    return result
