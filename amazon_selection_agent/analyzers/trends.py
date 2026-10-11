"""趋势分析：月度搜索量 / 销量 / Google Trends 的同比、复合增长、季节性、大促爆发。"""

from __future__ import annotations

import numpy as np
import pandas as pd

MONTH_NAMES = {1: "1月", 2: "2月", 3: "3月", 4: "4月", 5: "5月", 6: "6月",
               7: "7月", 8: "8月", 9: "9月", 10: "10月", 11: "11月", 12: "12月"}

# 美国站大促/节点所在月份
EVENTS = {
    "黑五/网一 (11月)": 11,
    "Prime Day (7月)": 7,
    "返校季 Back to School (8月)": 8,
    "圣诞季 (12月)": 12,
}


def _verdict(yoy: float | None, slope_pct: float | None) -> str:
    if yoy is None:
        return "数据不足（需 ≥24 个月）"
    if yoy >= 0.15 and (slope_pct is None or slope_pct > 0):
        return "增长"
    if yoy <= -0.10 and (slope_pct is None or slope_pct < 0):
        return "下滑"
    if yoy >= 0.05:
        return "温和增长"
    if yoy <= -0.03:
        return "温和下滑"
    return "平稳"


def analyze_series(series: pd.Series, name: str = "") -> dict:
    """series: index 为 pandas Period[M]，值为月度数值。"""
    s = series.dropna().astype(float)
    s = s[s.index.notna()]
    n = len(s)
    out: dict = {"metric": name, "months": n, "start": str(s.index.min()), "end": str(s.index.max())}
    if n < 12:
        out["verdict"] = "数据不足（需 ≥12 个月）"
        return out

    last12 = s.iloc[-12:].sum()
    out["last_12m_total"] = round(float(last12), 1)
    yoy = None
    if n >= 24:
        prev12 = s.iloc[-24:-12].sum()
        yoy = float(last12 / prev12 - 1) if prev12 else None
        out["yoy_last_12m"] = round(yoy, 4) if yoy is not None else None
        # 最近 3 个月同比，看拐点
        recent, prior = s.iloc[-3:].sum(), s.iloc[-15:-12].sum()
        out["yoy_last_3m"] = round(float(recent / prior - 1), 4) if prior else None
    years = n / 12
    first12 = s.iloc[:12].sum()
    if n >= 24 and first12 > 0:
        out["cagr"] = round(float((last12 / first12) ** (1 / (years - 1)) - 1), 4)

    # 12 个月滚动均值的线性斜率（去季节性），表示为每月相对均值的变化
    rolling = s.rolling(12).mean().dropna()
    slope_pct = None
    if len(rolling) >= 3:
        slope = np.polyfit(np.arange(len(rolling)), rolling.values, 1)[0]
        slope_pct = float(slope / rolling.mean())
        out["trend_slope_per_month"] = round(slope_pct, 4)

    # 季节性指数：同月份均值 / 整体均值（按年归一，消除增长影响）
    yearly_mean = s.groupby(s.index.year).transform("mean")
    idx = (s / yearly_mean).groupby(s.index.month).mean()
    out["seasonality_index"] = {MONTH_NAMES[m]: round(float(v), 2) for m, v in idx.items()}
    peaks = idx.sort_values(ascending=False)
    out["peak_months"] = [MONTH_NAMES[m] for m in peaks.index[:3]]
    out["low_months"] = [MONTH_NAMES[m] for m in peaks.index[-2:]]
    out["seasonality_strength"] = round(float(idx.max() / idx.min()), 2) if idx.min() > 0 else None
    out["verdict"] = _verdict(yoy, slope_pct)
    return out


def event_spikes(series: pd.Series, name: str = "") -> dict:
    """大促爆发系数 = 大促月 / 当年 1-10 月（除 7 月）中位数。≥1.5 视为明显爆发。"""
    s = series.dropna().astype(float)
    per_year: dict = {}
    for year, g in s.groupby(s.index.year):
        by_month = {p.month: v for p, v in g.items()}
        base_months = [v for m, v in by_month.items() if m <= 10 and m not in (7,)]
        if len(base_months) < 6:
            continue
        base = float(np.median(base_months))
        if base <= 0:
            continue
        per_year[int(year)] = {
            label: round(by_month[m] / base, 2) for label, m in EVENTS.items() if m in by_month
        }
    if not per_year:
        return {"metric": name, "verdict": "数据不足"}
    avg = {}
    for label in EVENTS:
        vals = [y[label] for y in per_year.values() if label in y]
        if vals:
            avg[label] = round(float(np.mean(vals)), 2)
    bf = avg.get("黑五/网一 (11月)")
    if bf is None:
        verdict = "无 11 月数据"
    elif bf >= 2.0:
        verdict = "黑五强爆发：必须提前 60-90 天备货 + 秒杀/Coupon 布局"
    elif bf >= 1.5:
        verdict = "黑五明显爆发：建议 9 月底前 FBA 入仓，报名 BFCM 秒杀"
    elif bf >= 1.15:
        verdict = "黑五小幅拉升：常规促销即可"
    else:
        verdict = "黑五无明显爆发：该品不靠大促，按日常节奏备货"
    return {"metric": name, "by_year": per_year, "average": avg, "black_friday_multiplier": bf, "verdict": verdict}


def analyze_category(df: pd.DataFrame) -> dict:
    """category_monthly.csv：month + search_volume / units_sold / revenue（有哪列算哪列）。"""
    df = df.set_index("month")
    out = {}
    for col, label in [("search_volume", "类目月搜索量"), ("units_sold", "类目月销量"), ("revenue", "类目月销售额")]:
        if col in df.columns:
            out[col] = analyze_series(df[col], label)
            out[col]["events"] = event_spikes(df[col], label)
    return out


def analyze_google_trends(df: pd.DataFrame) -> dict:
    """google_trends.csv：month + 每个词一列（0-100 指数）。"""
    df = df.set_index("month")
    terms = {}
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            terms[col] = analyze_series(df[col], f"Google Trends: {col}")
    ranked = sorted(
        ((t, r.get("yoy_last_12m")) for t, r in terms.items() if r.get("yoy_last_12m") is not None),
        key=lambda x: -x[1],
    )
    return {"terms": terms, "ranking_by_yoy": [{"term": t, "yoy": round(y, 4)} for t, y in ranked]}


def fetch_google_trends(terms: list[str], geo: str = "US", timeframe: str = "today 5-y") -> pd.DataFrame:
    """在线拉取 Google Trends（需要 `pip install pytrends` 且能访问 Google）。

    返回月度 DataFrame（month + 每个词一列），可直接交给 analyze_google_trends。
    pytrends 一次最多 5 个词。
    """
    try:
        from pytrends.request import TrendReq
    except ImportError as e:  # pragma: no cover - 可选依赖
        raise RuntimeError("需要先安装 pytrends: pip install pytrends") from e
    pt = TrendReq(hl="en-US", tz=360)
    pt.build_payload(terms[:5], geo=geo, timeframe=timeframe)
    raw = pt.interest_over_time()
    if raw.empty:
        raise RuntimeError("Google Trends 没有返回数据")
    raw = raw.drop(columns=[c for c in ["isPartial"] if c in raw.columns])
    monthly = raw.resample("MS").mean()
    monthly.index = monthly.index.to_period("M")
    monthly.index.name = "month"
    return monthly.reset_index()
