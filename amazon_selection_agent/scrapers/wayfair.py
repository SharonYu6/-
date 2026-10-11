"""Wayfair 竞品 & 评论爬虫（在你自己的电脑上运行）。

Wayfair 有 PerimeterX 反爬，requests 直接请求基本会被拦截，所以这里用 Playwright 驱动真实
Chromium（默认有头模式，遇到人机验证可以手动点一下）。

抓取逻辑：
1. 搜索页 https://www.wayfair.com/keyword.php?keyword=...&curpage=N -> 收集所有 /pdp/ 商品链接
2. 逐个打开商品页，解析 <script type="application/ld+json"> 里的 schema.org Product：
   名称、品牌、SKU、价格、评分、评论数、页面内嵌的评论
   （JSON-LD 是给搜索引擎看的结构化数据，比 CSS class 稳定得多）
3. 输出 competitors.csv / reviews.csv，列名与 Amazon 数据一致（platform=wayfair），
   Wayfair 不公开销量，分析时自动用评论数作为销量代理。

请遵守 Wayfair 的服务条款与 robots.txt，控制频率（默认每页 4-8 秒随机间隔），仅用于个人市场调研。

用法：
    pip install playwright && playwright install chromium
    python -m amazon_selection_agent scrape-wayfair "wavy mirror" --pages 2 --max-products 40 --out data/wayfair_wavy_mirror
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import pandas as pd

BASE = "https://www.wayfair.com"
PDP_RE = re.compile(r"/[^\"'\s]*?/pdp/[^\"'\s?#]+\.html")


@dataclass
class WayfairProduct:
    sku: str
    url: str
    title: str = ""
    brand: str = ""
    price: float | None = None
    rating: float | None = None
    reviews: int | None = None
    color: str = ""
    category: str = ""
    image: str = ""
    review_items: list[dict] = field(default_factory=list)


def search_url(keyword: str, page: int = 1) -> str:
    return f"{BASE}/keyword.php?keyword={quote_plus(keyword)}&curpage={page}"


def extract_pdp_links(html: str) -> list[str]:
    """从搜索页 HTML 中提取去重后的商品详情页链接（保持出现顺序 = 搜索排名）。"""
    seen: dict[str, None] = {}
    for m in PDP_RE.finditer(html):
        url = urljoin(BASE, m.group(0))
        seen.setdefault(url.split("?")[0], None)
    return list(seen)


def _iter_jsonld(html: str):
    for m in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "@graph" in node:
                    stack.extend(node["@graph"])
                yield node


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def parse_product_html(html: str, url: str) -> WayfairProduct | None:
    """解析商品页 JSON-LD。找不到 Product 节点返回 None。"""
    product = next((n for n in _iter_jsonld(html) if "Product" in str(n.get("@type", ""))), None)
    if product is None:
        return None
    sku = str(product.get("sku") or product.get("productID") or urlparse(url).path.split("-")[-1].replace(".html", ""))
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = _num(offers.get("price") or offers.get("lowPrice"))
    agg = product.get("aggregateRating") or {}
    brand = product.get("brand") or ""
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    image = product.get("image") or ""
    if isinstance(image, list):
        image = image[0] if image else ""
    reviews = []
    for r in product.get("review") or []:
        rating = (r.get("reviewRating") or {}).get("ratingValue")
        body = r.get("reviewBody") or r.get("description") or ""
        if rating is None or not body:
            continue
        reviews.append({
            "rating": _num(rating),
            "title": r.get("name") or "",
            "body": body,
            "date": r.get("datePublished") or "",
        })
    return WayfairProduct(
        sku=sku,
        url=url,
        title=product.get("name", ""),
        brand=str(brand),
        price=price,
        rating=_num(agg.get("ratingValue")),
        reviews=int(_num(agg.get("reviewCount") or agg.get("ratingCount")) or 0) or None,
        color=str(product.get("color") or ""),
        category=str(product.get("category") or ""),
        image=str(image),
        review_items=reviews,
    )


def _robots_allows(url: str) -> bool:
    rp = urllib.robotparser.RobotFileParser(urljoin(BASE, "/robots.txt"))
    try:
        rp.read()
    except Exception:  # 读不到 robots.txt 时不阻断，但会在日志中提示
        print("[warn] 无法读取 robots.txt，请自行确认抓取范围合规")
        return True
    return rp.can_fetch("*", url)


def scrape(keyword: str, pages: int = 1, max_products: int = 40, headless: bool = False,
           delay: tuple[float, float] = (4.0, 8.0)) -> list[WayfairProduct]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover - 可选依赖
        raise RuntimeError("需要先安装: pip install playwright && playwright install chromium") from e

    def pause() -> None:
        time.sleep(random.uniform(*delay))

    products: list[WayfairProduct] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        ctx = browser.new_context(locale="en-US", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        links: list[str] = []
        for n in range(1, pages + 1):
            url = search_url(keyword, n)
            if not _robots_allows(url):
                print(f"[skip] robots.txt 不允许: {url}")
                break
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.mouse.wheel(0, 4000)  # 触发懒加载
            pause()
            if "captcha" in page.url.lower() or "Press & Hold" in page.content():
                input("[!] 出现人机验证，请在浏览器中完成后按回车继续...")
            new = [link for link in extract_pdp_links(page.content()) if link not in links]
            print(f"[search] page {n}: {len(new)} products")
            links.extend(new)
            if not new:
                break
        for i, link in enumerate(links[:max_products], 1):
            try:
                page.goto(link, wait_until="domcontentloaded", timeout=60000)
                pause()
                prod = parse_product_html(page.content(), link)
            except Exception as e:  # 单个商品失败不影响整体
                print(f"[error] {link}: {e}")
                continue
            if prod:
                products.append(prod)
                print(f"[pdp {i}/{min(len(links), max_products)}] {prod.title[:60]} ${prod.price} "
                      f"★{prod.rating} ({prod.reviews})")
        browser.close()
    return products


def to_frames(products: list[WayfairProduct], keyword: str = "") -> tuple[pd.DataFrame, pd.DataFrame]:
    comp = pd.DataFrame([{
        "asin": f"WF-{p.sku}",
        "platform": "wayfair",
        "title": p.title,
        "brand": p.brand,
        "price": p.price,
        "reviews": p.reviews,
        "rating": p.rating,
        "color": p.color,
        "category": p.category,
        "search_rank": rank,
        "keyword": keyword,
        "url": p.url,
        "image": p.image,
    } for rank, p in enumerate(products, 1)])
    reviews = pd.DataFrame([
        {"asin": f"WF-{p.sku}", "platform": "wayfair", **r} for p in products for r in p.review_items
    ])
    if not comp.empty:
        comp = comp.dropna(subset=["price"])
    return comp, reviews


def save(products: list[WayfairProduct], out_dir: str | Path, keyword: str = "") -> None:
    """写入 / 合并到数据目录。已有 competitors.csv（比如 Amazon 数据）时按 asin 追加去重。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    comp, reviews = to_frames(products, keyword)
    for name, df, key in [("competitors.csv", comp, ["asin"]), ("reviews.csv", reviews, ["asin", "body"])]:
        if df.empty:
            continue
        path = out / name
        if path.exists():
            df = pd.concat([pd.read_csv(path), df], ignore_index=True).drop_duplicates(subset=key, keep="last")
        df.to_csv(path, index=False)
        print(f"[save] {path} ({len(df)} rows)")
