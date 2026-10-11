"""把所有分析串起来，输出一个可 JSON 序列化的结果 dict（报告、网站、agent 都用它）。"""

from __future__ import annotations

from datetime import date

from .analyzers.competition import analyze_competition, category_depth_score
from .analyzers.keywords import analyze_keywords
from .analyzers.product import build_persona, propose_product
from .analyzers.trends import analyze_category, analyze_google_trends
from .analyzers.voc import analyze_reviews
from .data_loader import Dataset


def run_analysis(ds: Dataset, today: str | None = None) -> dict:
    kw = analyze_keywords(ds.keywords) if ds.keywords is not None else None
    trends = analyze_category(ds.category_monthly) if ds.category_monthly is not None else None
    gtrends = analyze_google_trends(ds.google_trends) if ds.google_trends is not None else None
    comp = analyze_competition(ds.competitors, kw, today=today) if ds.competitors is not None else None
    voc = analyze_reviews(ds.reviews) if ds.reviews is not None else None
    depth = category_depth_score(comp or {}, trends, voc)
    return {
        "dataset": ds.name,
        "generated_at": today or date.today().isoformat(),
        "inputs": ds.available(),
        "keyword_volume_basis": ds.keyword_volume_basis,
        "keywords": kw,
        "category_trends": trends,
        "google_trends": gtrends,
        "competition": comp,
        "voc": voc,
        "persona": build_persona(kw, voc),
        "product": propose_product(kw, trends, comp, voc, depth),
        "category_depth": depth,
        # 原始时间序列给可视化用
        "series": _series(ds),
    }


def _series(ds: Dataset) -> dict:
    out = {}
    if ds.category_monthly is not None:
        df = ds.category_monthly
        out["category_monthly"] = {"month": [str(m) for m in df["month"]]}
        for col in ["search_volume", "units_sold", "revenue"]:
            if col in df:
                out["category_monthly"][col] = [float(v) for v in df[col]]
    if ds.google_trends is not None:
        df = ds.google_trends
        out["google_trends"] = {"month": [str(m) for m in df["month"]]}
        for col in df.columns:
            if col != "month":
                out["google_trends"][col] = [float(v) for v in df[col]]
    return out
