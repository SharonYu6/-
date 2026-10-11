"""读取选品数据（CSV）。

一个"数据集"是一个目录，里面放下列文件（列名见 README，缺的文件会被跳过）：

- keywords.csv          关键词月搜索量（卖家精灵 / Helium 10 / Jungle Scout 反查导出后改列名）
- category_monthly.csv  类目月度搜索量 + 销量 + 销售额（至少 24 个月才能算同比）
- google_trends.csv     Google Trends 月度指数（month + 每个词一列）
- competitors.csv       类目 Top N 竞品（ASIN、品牌、价格、月销量、评论数、评分、上架时间）
- reviews.csv           竞品评论（VOC）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

FILES = {
    "keywords": "keywords.csv",
    "category_monthly": "category_monthly.csv",
    "google_trends": "google_trends.csv",
    "competitors": "competitors.csv",
    "reviews": "reviews.csv",
}

REQUIRED_COLUMNS = {
    "keywords": {"keyword"},
    "category_monthly": {"month"},
    "google_trends": {"month"},
    "competitors": {"asin", "price"},
    "reviews": {"rating", "body"},
}


@dataclass
class Dataset:
    name: str
    keywords: pd.DataFrame | None = None
    category_monthly: pd.DataFrame | None = None
    google_trends: pd.DataFrame | None = None
    competitors: pd.DataFrame | None = None
    reviews: pd.DataFrame | None = None
    keyword_volume_basis: str = "月搜索量"

    def available(self) -> list[str]:
        return [k for k in FILES if getattr(self, k) is not None]


def _read(path: Path, kind: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS[kind] - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} 缺少必需列: {sorted(missing)}")
    if "month" in df.columns:
        df["month"] = pd.to_datetime(df["month"]).dt.to_period("M")
        df = df.sort_values("month").reset_index(drop=True)
    return df


def load_dataset(directory: str | Path) -> Dataset:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"数据目录不存在: {directory}")
    ds = Dataset(name=directory.name)
    for kind, filename in FILES.items():
        path = directory / filename
        if path.exists():
            setattr(ds, kind, _read(path, kind))
    if ds.keywords is not None and "search_volume" not in ds.keywords:
        # Amazon 爬虫输出没有真实搜索量，用首页 "bought in past month" 合计作为需求代理
        if "demand_proxy" not in ds.keywords:
            raise ValueError("keywords.csv 需要 search_volume 或 demand_proxy 列")
        ds.keywords = ds.keywords.rename(columns={"demand_proxy": "search_volume"})
        ds.keywords = ds.keywords[ds.keywords["search_volume"] > 0].reset_index(drop=True)
        ds.keyword_volume_basis = "需求代理：Amazon 搜索首页自然位 bought in past month 合计"
    if not ds.available():
        raise FileNotFoundError(f"{directory} 下没有找到任何数据文件，期望: {list(FILES.values())}")
    return ds
