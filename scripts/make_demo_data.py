"""生成演示数据集（模拟数据，仅用于跑通流程，不代表真实市场）。

类目：家居镜子（Wall / Floor Mirror），围绕 small space、wavy、dorm 等词构造。
用法：python scripts/make_demo_data.py sample_data/demo_mirror
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

KEYWORDS = [
    # keyword, 当前月搜索量, 同比增长
    ("full length mirror", 410000, 0.04),
    ("wavy mirror", 165000, 0.68),
    ("wavy mirror full length", 74000, 0.82),
    ("mirror for small space", 38000, 0.41),
    ("full length mirror small space", 22000, 0.47),
    ("dorm mirror", 33000, 0.36),
    ("over the door mirror", 88000, 0.12),
    ("over the door mirror no drill", 9500, 0.55),
    ("arched mirror", 96000, 0.21),
    ("arch floor mirror", 41000, 0.18),
    ("irregular mirror", 52000, 0.49),
    ("asymmetrical mirror", 18000, 0.38),
    ("cloud mirror", 15000, 0.61),
    ("round mirror", 120000, -0.06),
    ("rectangle wall mirror", 44000, -0.12),
    ("floor mirror", 135000, 0.03),
    ("standing mirror", 61000, 0.09),
    ("mirror with lights", 72000, 0.15),
    ("led full length mirror", 26000, 0.22),
    ("white wavy mirror", 21000, 0.74),
    ("cream wavy mirror", 6800, 1.15),
    ("pink wavy mirror", 9200, 0.58),
    ("gold arched mirror", 23000, 0.05),
    ("black full length mirror", 31000, -0.02),
    ("wood floor mirror", 19000, 0.11),
    ("wavy mirror aesthetic", 12000, 0.93),
    ("danish pastel mirror", 4100, 0.71),
    ("boho mirror", 28000, -0.08),
    ("vintage mirror", 34000, -0.04),
    ("mirror for bedroom", 47000, 0.14),
    ("bathroom mirror", 180000, 0.02),
    ("entryway mirror", 21000, 0.07),
    ("kids mirror", 8000, 0.10),
    ("apartment mirror", 7600, 0.33),
    ("no drill mirror", 11000, 0.52),
    ("shatterproof mirror", 9900, 0.27),
    ("acrylic wavy mirror", 3800, 0.88),
    ("wavy mirror 63x20", 5400, 0.95),
    ("full length mirror 64x21", 14000, 0.08),
    ("mirror 47x16", 6100, 0.31),
    ("wavy mirror 24x36", 3300, 0.77),
    ("small wavy mirror desk", 4700, 0.66),
    ("rattan mirror", 16000, -0.15),
    ("mirror with storage", 9800, 0.19),
    ("closet mirror", 12500, 0.17),
]

BRANDS = ["Beautypeak", "HARRITPURE", "Americanflat", "Neutype", "Kiayaco", "Hamilton Hills",
          "OGCAU", "Trvone", "Sweetcrispy", "BEAUTYPEAK", "Mirrorize", "NestNook", "WavyCo"]

TITLE_TEMPLATES = [
    "Wavy Full Length Mirror {w}x{h} Irregular Floor Mirror {color} Wave Frame for Bedroom Small Space",
    "Arched Full Length Mirror {w}x{h} {color} Metal Frame Standing Floor Mirror Living Room",
    "Over The Door Mirror Full Length {w}x{h} {color} No Drill Hanging Mirror Dorm",
    "Full Length Mirror {w}x{h} {color} Rectangle Wall Mirror Large Floor Mirror Bedroom",
    "Round Wall Mirror {w} inch {color} Metal Frame Bathroom Vanity Mirror",
    "LED Full Length Mirror with Lights {w}x{h} {color} Lighted Floor Standing Mirror",
    "Irregular Asymmetrical Wall Mirror {color} Cloud Mirror Aesthetic Danish Pastel Decor",
    "Rattan Wall Mirror {w} inch Boho Woven Round Mirror {color}",
]

REVIEW_SNIPPETS = {
    5: ["Love the look, so aesthetic and cute in my dorm room.",
        "Perfect size for my small apartment, fits perfectly behind the door.",
        "Beautiful wavy frame, worth the price. Bought it for my daughter's college dorm.",
        "Gorgeous mirror, the cream color is exactly as pictured. Great value.",
        "Easy to install with the no drill hooks, my landlord won't know."],
    4: ["Pretty mirror and good value, packaging could be better but arrived fine.",
        "Stylish and fits my bedroom. Slightly wobbly on carpet.",
        "Great gift for my daughter, love the look."],
    3: ["Looks nice but the reflection is a bit distorted at the bottom.",
        "Instructions were confusing and the assembly took an hour.",
        "Color is off, looks yellow compared to the photos. Otherwise ok."],
    2: ["Wobbly stand, it tipped over twice. Feels cheaply made plastic frame.",
        "Smaller than expected, dimensions in the listing are misleading.",
        "Adhesive strips fell off after a week and the mirror fell."],
    1: ["Arrived damaged, glass was shattered. Packaging was terrible.",
        "Broken corner and cracked glass on arrival, second one also cracked.",
        "Warped distorted reflection like a funhouse mirror. Cheap plastic, returned.",
        "Strong chemical smell and the frame was peeling."],
}


def make(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)

    kw = pd.DataFrame(KEYWORDS, columns=["keyword", "search_volume", "growth_yoy"])
    kw["search_volume_last_year"] = (kw["search_volume"] / (1 + kw["growth_yoy"])).round().astype(int)
    kw[["keyword", "search_volume", "search_volume_last_year"]].to_csv(out / "keywords.csv", index=False)

    # 36 个月类目数据：温和增长 + 季节性（1 月新年整理、8 月返校、11 月黑五）
    months = pd.period_range("2023-10", "2026-09", freq="M")
    season = {1: 1.15, 2: 0.95, 3: 0.95, 4: 0.92, 5: 0.9, 6: 0.88, 7: 1.12,
              8: 1.3, 9: 1.05, 10: 1.0, 11: 1.75, 12: 1.35}
    t = np.arange(len(months))
    trend = 1.0 * (1.018 ** t)
    sv = np.array([2.6e6 * trend[i] * season[m.month] for i, m in enumerate(months)]) * rng.normal(1, 0.03, len(months))
    units = sv * 0.045 * np.array([1.25 if m.month == 11 else 1.0 for m in months]) * rng.normal(1, 0.04, len(months))
    price = 58 * np.array([0.88 if m.month in (7, 11) else 1.0 for m in months])
    pd.DataFrame({"month": months.astype(str), "search_volume": sv.round(), "units_sold": units.round(),
                  "revenue": (units * price).round()}).to_csv(out / "category_monthly.csv", index=False)

    # Google Trends 指数（0-100）
    gt = pd.DataFrame({"month": months.astype(str)})
    gt["wavy mirror"] = np.clip(18 * (1.045 ** t) * [season[m.month] ** 0.6 for m in months], 0, 100).round()
    gt["arched mirror"] = np.clip(40 * (1.008 ** t) * [season[m.month] ** 0.5 for m in months], 0, 100).round()
    gt["round mirror"] = np.clip(70 * (0.995 ** t) * [season[m.month] ** 0.4 for m in months], 0, 100).round()
    gt["small space decor"] = np.clip(30 * (1.02 ** t) * [season[m.month] ** 0.8 for m in months], 0, 100).round()
    gt.to_csv(out / "google_trends.csv", index=False)

    # 60 个竞品
    colors = ["White", "Black", "Gold", "Cream", "Pink", "Natural Wood", "Silver"]
    rows = []
    for i in range(60):
        tpl = TITLE_TEMPLATES[i % len(TITLE_TEMPLATES)]
        w, h = rng.choice([(63, 20), (64, 21), (59, 16), (47, 16), (65, 22), (36, 24), (24, 24)])
        color = colors[rng.integers(len(colors))]
        is_wavy = "Wavy" in tpl or "Irregular" in tpl
        base_price = {0: 79, 1: 89, 2: 32, 3: 69, 4: 39, 5: 129, 6: 55, 7: 45}[i % len(TITLE_TEMPLATES)]
        sales = int(rng.lognormal(6.3 if not is_wavy else 6.0, 0.8))
        launch = pd.Timestamp("2026-09-30") - pd.Timedelta(days=int(rng.integers(60, 1600 if not is_wavy else 600)))
        rows.append({
            "asin": f"B0DEMO{i:04d}",
            "platform": "amazon",
            "title": tpl.format(w=w, h=h, color=color),
            "brand": BRANDS[int(rng.integers(len(BRANDS)))],
            "price": round(float(base_price * rng.uniform(0.8, 1.25)), 2) - 0.01,
            "monthly_sales": sales,
            "reviews": int(sales * rng.uniform(1.5, 12) * ((pd.Timestamp("2026-09-30") - launch).days / 365)),
            "rating": round(float(np.clip(rng.normal(4.35 if not is_wavy else 4.1, 0.25), 3.4, 4.9)), 1),
            "launch_date": launch.date().isoformat(),
        })
    comp = pd.DataFrame(rows)
    comp.to_csv(out / "competitors.csv", index=False)

    # 600 条评论
    reviews = []
    weights = {5: 0.52, 4: 0.18, 3: 0.1, 2: 0.08, 1: 0.12}
    for _ in range(600):
        r = int(rng.choice(list(weights), p=list(weights.values())))
        body = " ".join(rng.choice(REVIEW_SNIPPETS[r], size=int(rng.integers(1, 3)), replace=False))
        reviews.append({"asin": comp["asin"].iloc[int(rng.integers(len(comp)))], "rating": r, "title": "", "body": body})
    pd.DataFrame(reviews).to_csv(out / "reviews.csv", index=False)
    print(f"demo data written to {out}")


if __name__ == "__main__":
    make(Path(sys.argv[1] if len(sys.argv) > 1 else "sample_data/demo_mirror"))
