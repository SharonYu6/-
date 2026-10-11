"""VOC（Voice of Customer）评论分析：痛点、爽点、用户是谁、用在哪。"""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from ..lexicon import SCENE, VOC_IMPROVEMENT, VOC_THEMES
from .text import match_labels

# 评论里"谁在用 / 买给谁"
WHO = {
    "大学生": ["college", "dorm", "student", "freshman", "university"],
    "女儿/儿子": ["daughter", "son", "kids", "teen", "granddaughter"],
    "送礼": ["gift", "present", "birthday", "christmas"],
    "情侣/夫妻": ["husband", "wife", "boyfriend", "girlfriend", "partner"],
    "租房者": ["apartment", "rental", "renter", "landlord", "lease"],
    "新房/搬家": ["new home", "new house", "moved", "moving"],
}

STOPWORDS = set("""
a an the and or but if to of in on for with at by from is it this that was were be been are i my me we our you your
they them it's its so very just not no too as have has had do did does can will would could should
""".split())


def _bigrams(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z']+", text.lower()) if w not in STOPWORDS and len(w) > 2]
    return [f"{a} {b}" for a, b in zip(words, words[1:])]


def analyze_reviews(df: pd.DataFrame) -> dict:
    df = df.copy()
    title = df["title"].fillna("").astype(str) if "title" in df else pd.Series("", index=df.index)
    df["text"] = (title + ". " + df["body"].fillna("").astype(str)).str.lstrip(". ")
    df["themes"] = df["text"].map(lambda t: match_labels(t, VOC_THEMES))
    df["who"] = df["text"].map(lambda t: match_labels(t, WHO))
    df["scene"] = df["text"].map(lambda t: match_labels(t, SCENE))

    neg = df[df["rating"] <= 3]
    pos = df[df["rating"] >= 4]
    n, n_neg, n_pos = len(df), max(len(neg), 1), max(len(pos), 1)

    theme_rows = []
    for theme in VOC_THEMES:
        neg_hits = int(neg["themes"].map(lambda t, th=theme: th in t).sum())
        pos_hits = int(pos["themes"].map(lambda t, th=theme: th in t).sum())
        theme_rows.append({
            "theme": theme,
            "negative_mentions": neg_hits,
            "negative_mention_rate": round(neg_hits / n_neg, 4),
            "positive_mentions": pos_hits,
            "positive_mention_rate": round(pos_hits / n_pos, 4),
            "improvement": VOC_IMPROVEMENT.get(theme),
        })

    pain = sorted([r for r in theme_rows if r["improvement"] and r["negative_mentions"]],
                  key=lambda r: -r["negative_mentions"])
    delight = sorted([r for r in theme_rows if r["positive_mentions"]], key=lambda r: -r["positive_mentions"])

    for p in pain[:5]:
        examples = neg[neg["themes"].map(lambda t, th=p["theme"]: th in t)]["text"].head(2)
        p["examples"] = [e[:200] for e in examples]

    def _count(col: str, frame: pd.DataFrame) -> list[dict]:
        c = Counter(x for labels in frame[col] for x in labels)
        return [{"label": k, "mentions": v, "rate": round(v / max(len(frame), 1), 4)} for k, v in c.most_common()]

    out = {
        "review_count": n,
        "avg_rating": round(float(df["rating"].mean()), 2),
        "rating_distribution": {int(k): int(v) for k, v in df["rating"].value_counts().sort_index().items()},
        "negative_share": round(len(neg) / max(n, 1), 4),
        "pain_points": pain,
        "delights": delight[:6],
        "who_buys": _count("who", df),
        "usage_scenes": _count("scene", df),
        "negative_phrases": [
            {"phrase": k, "count": v} for k, v in Counter(b for t in neg["text"] for b in _bigrams(t)).most_common(15)
        ],
    }
    if "asin" in df:
        per = df.groupby("asin")["rating"].agg(["count", "mean"]).sort_values("count", ascending=False)
        out["per_listing"] = [
            {"asin": a, "reviews": int(r["count"]), "avg_rating": round(float(r["mean"]), 2)} for a, r in per.head(10).iterrows()
        ]
    return out
