"""Amazon 美国站真实数据采集（在能访问 amazon.com 的电脑上运行）。

采集四类数据：
1. 关键词：Amazon 搜索框下拉联想（autocomplete）—— 真实用户搜索词，按 种子词 + a~z 扩展
2. 搜索结果页：每个关键词首页商品的标题/价格/评分/评论数/"X+ bought in past month"/是否广告
   -> 关键词需求代理 = 首页自然位 "bought in past month" 合计
3. Best Sellers 类目榜：每个类目 Top 50/100 的排名、标题、价格、评分、主图
4. 商品详情页（如截图中的 Curved 9-Drawer Dresser）：品牌/店铺、月销 "200+ bought"、现价/原价、
   颜色和尺寸变体、五点描述、BSR 排名、材质/形状/风格等参数、主图、页面评论

说明：
- Amazon 的月搜索量（Search Volume）不对外公开，要精确值请用 Brand Analytics（品牌备案后台）或
  卖家精灵 / Helium 10 导出 keywords.csv；本模块给的是"联想词 + 销量代理"。
- Amazon 页面结构经常变化，解析函数都做了多重兜底；若某字段长期为空，更新对应选择器即可。
- 请控制频率（默认 5-10 秒随机间隔），仅用于个人市场调研，遵守 Amazon 使用条款。

用法见 README「采集真实 Amazon 数据」。
"""

from __future__ import annotations

import json
import random
import re
import string
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = "https://www.amazon.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
AUTOCOMPLETE = "https://completion.amazon.com/api/2017/suggestions"

_BOUGHT_RE = re.compile(r"([\d.,]+)\s*([KkMm])?\+?\s*bought in past month", re.I)
_STARS_RE = re.compile(r"([\d.]+) out of 5")
_ASIN_RE = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})")


# ---------------------------------------------------------------- 基础解析

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def parse_count(text: str | None) -> int | None:
    """'1,234' / '(206)' / '12K' / '2.5K ratings' -> int"""
    if not text:
        return None
    m = re.search(r"([\d.,]+)\s*([KkMm])?", text.replace("(", " ").replace(")", " "))
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    mult = {"k": 1e3, "m": 1e6}.get((m.group(2) or "").lower(), 1)
    return int(n * mult)


def parse_bought(text: str | None) -> int | None:
    """'200+ bought in past month' -> 200；'1K+ bought in past month' -> 1000"""
    if not text:
        return None
    m = _BOUGHT_RE.search(text)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return int(n * {"k": 1e3, "m": 1e6}.get((m.group(2) or "").lower(), 1))


def parse_stars(text: str | None) -> float | None:
    m = _STARS_RE.search(text or "")
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------- 搜索结果页

def parse_search_html(html: str, keyword: str = "") -> list[dict]:
    soup = _soup(html)
    rows = []
    organic_rank = 0
    for pos, card in enumerate(soup.select('div[data-component-type="s-search-result"][data-asin]'), 1):
        asin = card.get("data-asin")
        if not asin:
            continue
        text = _text(card)
        sponsored = bool(card.select_one(".puis-sponsored-label-text, .s-sponsored-label-text")) or \
            "Sponsored" in text[:200]
        if not sponsored:
            organic_rank += 1
        title_node = card.select_one("h2 span") or card.select_one("h2")
        price_node = card.select_one(".a-price:not(.a-text-price) .a-offscreen")
        list_node = card.select_one(".a-price.a-text-price .a-offscreen")
        img = card.select_one("img.s-image")
        count_node = card.select_one('a[href*="customerReviews"] span, span.s-underline-text')
        rows.append({
            "keyword": keyword,
            "position": pos,
            "organic_rank": None if sponsored else organic_rank,
            "sponsored": sponsored,
            "asin": asin,
            "title": _text(title_node),
            "price": parse_price(_text(price_node)),
            "list_price": parse_price(_text(list_node)),
            "rating": parse_stars(_text(card.select_one("span.a-icon-alt"))),
            "ratings_count": parse_count(_text(count_node)),
            "bought_past_month": parse_bought(text),
            "image": img.get("src") if img else "",
        })
    return rows


# ---------------------------------------------------------------- Best Sellers 榜

def parse_bestsellers_html(html: str, category: str = "") -> list[dict]:
    soup = _soup(html)
    rows: list[dict] = []
    # 新版榜单把排名放在 data-client-recs-list 的 JSON 里，先取它保证排名准确
    rank_by_asin: dict[str, int] = {}
    for grid in soup.select("[data-client-recs-list]"):
        try:
            for item in json.loads(grid["data-client-recs-list"]):
                rank = (item.get("metadataMap") or {}).get("render.zg.rank")
                if item.get("id") and rank:
                    rank_by_asin[item["id"]] = int(rank)
        except (ValueError, TypeError):
            continue
    cards = soup.select("#gridItemRoot") or soup.select('[id^="p13n-asin-index-"]')
    for i, card in enumerate(cards, 1):
        holder = card if card.get("data-asin") else card.select_one("[data-asin]")
        asin = holder.get("data-asin") if holder else None
        if not asin:
            link = card.select_one('a[href*="/dp/"]')
            m = _ASIN_RE.search(link["href"]) if link else None
            asin = m.group(1) if m else None
        if not asin:
            continue
        badge = _text(card.select_one(".zg-bdg-text"))
        rank = rank_by_asin.get(asin) or (int(badge.lstrip("#")) if badge.lstrip("#").isdigit() else i)
        img = card.select_one("img")
        title = ""
        for sel in ['a[href*="/dp/"] div[class*="line-clamp"]', 'a[href*="/dp/"] span div', 'a[href*="/dp/"] > span']:
            title = _text(card.select_one(sel))
            if title:
                break
        title = title or (img.get("alt", "") if img else "")
        price_text = next((t for t in card.stripped_strings if "$" in t), None)
        count_node = card.select_one('a[href*="product-reviews"] span, span.a-size-small')
        rows.append({
            "category": category,
            "rank": rank,
            "asin": asin,
            "title": title,
            "price": parse_price(price_text),
            "rating": parse_stars(_text(card.select_one(".a-icon-alt"))),
            "ratings_count": parse_count(_text(count_node)),
            "image": img.get("src") if img else "",
        })
    return sorted(rows, key=lambda r: r["rank"])


def parse_bestseller_subcategories(html: str) -> list[dict]:
    """从 Best Sellers 页面左侧导航中取子类目链接（不用硬编码类目 ID）。"""
    soup = _soup(html)
    seen, out = set(), []
    for a in soup.select('a[href*="/zgbs/"]'):
        href = a.get("href", "").split("/ref=")[0]
        name = _text(a)
        if not name or href in seen or "zgbs" not in href:
            continue
        seen.add(href)
        out.append({"name": name, "url": urljoin(BASE, href)})
    return out


# ---------------------------------------------------------------- 商品详情页

_DETAIL_KEYS = {
    "color": ["color", "colour"],
    "material": ["material", "frame material"],
    "shape": ["shape"],
    "style": ["style"],
    "size": ["size", "product dimensions", "item dimensions"],
    "room_type": ["room type"],
    "brand": ["brand"],
    "mounting": ["mounting type"],
    "date_first_available": ["date first available"],
}


def _details(soup: BeautifulSoup) -> dict[str, str]:
    raw: dict[str, str] = {}
    for tr in soup.select("#productOverview_feature_div tr, table[id^=productDetails] tr, .prodDetTable tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) >= 2:
            raw[_text(cells[0]).lower().strip(" :‎‏")] = _text(cells[1])
    for li in soup.select("#detailBullets_feature_div li, #detailBulletsWrapper_feature_div li"):
        parts = _text(li).split(":", 1)
        if len(parts) == 2:
            raw[parts[0].lower().strip(" ‎‏")] = parts[1].strip(" ‎‏")
    return raw


def _variants(soup: BeautifulSoup) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dim in ["color_name", "size_name", "style_name", "pattern_name", "material_name"]:
        values: list[str] = []
        for li in soup.select(f"#variation_{dim} li, #inline-twister-row-{dim} li, #tp-inline-twister-dim-values-container li"):
            v = li.get("title", "").replace("Click to select ", "").strip()
            if not v:
                img = li.select_one("img")
                v = img.get("alt", "").strip() if img else ""
            v = v or _text(li.select_one(".swatch-title-text, .a-button-text, .twisterTextDiv"))
            if v and v not in values:
                values.append(v)
        if values:
            out[dim.replace("_name", "")] = values
    return out


def _bsr(text: str) -> list[dict]:
    m = re.search(r"Best Sellers Rank:?(.*?)(?:Customer Reviews|Date First|$)", text, re.S)
    if not m:
        return []
    return [{"rank": int(r.replace(",", "")), "category": c.strip()}
            for r, c in re.findall(r"#([\d,]+) in ([^(#]+)", m.group(1))]


def parse_product_html(html: str, asin: str = "") -> dict:
    soup = _soup(html)
    page_text = _text(soup)
    details = _details(soup)

    def detail(field: str) -> str:
        for k in _DETAIL_KEYS[field]:
            if k in details:
                return details[k]
        return ""

    landing = soup.select_one("#landingImage, #imgTagWrapperId img")
    image = ""
    if landing:
        image = landing.get("data-old-hires") or landing.get("src", "")
    price = parse_price(_text(soup.select_one(
        "#corePrice_feature_div .a-offscreen, .priceToPay .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen")))
    list_price = parse_price(_text(soup.select_one(".basisPrice .a-offscreen, .a-text-price .a-offscreen")))
    reviews = []
    for r in soup.select('[data-hook="review"]'):
        reviews.append({
            "asin": asin,
            "rating": parse_stars(_text(r.select_one('[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]'))),
            "title": _text(r.select_one('[data-hook="review-title"] span:not(.a-icon-alt)')) or _text(r.select_one('[data-hook="review-title"]')),
            "body": _text(r.select_one('[data-hook="review-body"]')),
            "date": _text(r.select_one('[data-hook="review-date"]')),
        })
    return {
        "asin": asin,
        "title": _text(soup.select_one("#productTitle")),
        "store": _text(soup.select_one("#bylineInfo")).replace("Visit the ", "").replace("Brand: ", ""),
        "brand": detail("brand"),
        "price": price,
        "list_price": list_price,
        "rating": parse_stars(soup.select_one("#acrPopover").get("title", "") if soup.select_one("#acrPopover") else
                              _text(soup.select_one("#averageCustomerReviews .a-icon-alt"))),
        "ratings_count": parse_count(_text(soup.select_one("#acrCustomerReviewText"))),
        "bought_past_month": parse_bought(_text(soup.select_one('[id^="social-proofing-faceout-title"]')) or page_text),
        "variants": _variants(soup),
        "bullets": [_text(li) for li in soup.select("#feature-bullets li span.a-list-item") if _text(li)],
        "color": detail("color"),
        "material": detail("material"),
        "shape": detail("shape"),
        "style": detail("style"),
        "size": detail("size"),
        "room_type": detail("room_type"),
        "date_first_available": detail("date_first_available"),
        "best_sellers_rank": _bsr(details.get("best sellers rank", "") and "Best Sellers Rank: " + details["best sellers rank"]
                                  or page_text),
        "image": image,
        "reviews": [r for r in reviews if r["body"]],
    }


# ---------------------------------------------------------------- 关键词联想

def autocomplete(prefix: str, session: requests.Session | None = None) -> list[str]:
    params = {
        "limit": 11, "prefix": prefix, "suggestion-type": "KEYWORD", "page-type": "Gateway",
        "lop": "en_US", "site-variant": "desktop", "client-info": "amazon-search-ui",
        "mid": "ATVPDKIKX0DER", "alias": "aps",
    }
    s = session or requests.Session()
    r = s.get(AUTOCOMPLETE, params=params, headers={"User-Agent": UA}, timeout=15)
    r.raise_for_status()
    return [x["value"] for x in r.json().get("suggestions", []) if x.get("value")]


def expand_keywords(seeds: list[str], alphabet: bool = True, delay: tuple[float, float] = (0.5, 1.5)) -> pd.DataFrame:
    """种子词 + a~z 联想。suggest_rank 越小越热门（Amazon 按热度排序联想词）。"""
    s = requests.Session()
    rows: dict[str, dict] = {}
    for seed in seeds:
        prefixes = [seed] + ([f"{seed} {c}" for c in string.ascii_lowercase] if alphabet else [])
        for prefix in prefixes:
            try:
                sugg = autocomplete(prefix, s)
            except requests.RequestException as e:
                print(f"[warn] autocomplete '{prefix}': {e}")
                continue
            for rank, kw in enumerate(sugg, 1):
                row = rows.setdefault(kw, {"keyword": kw, "seed": seed, "suggest_rank": rank, "hits": 0})
                row["suggest_rank"] = min(row["suggest_rank"], rank)
                row["hits"] += 1
            time.sleep(random.uniform(*delay))
    df = pd.DataFrame(rows.values())
    return df.sort_values(["suggest_rank", "hits"], ascending=[True, False]).reset_index(drop=True) if not df.empty else df


# ---------------------------------------------------------------- 浏览器抓取

class Browser:
    """Playwright 封装：有头 Chromium，遇到验证码暂停等人工处理。"""

    def __init__(self, headless: bool = False, delay: tuple[float, float] = (5.0, 10.0), save_html: str | None = None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover - 可选依赖
            raise RuntimeError("需要先安装: pip install playwright && playwright install chromium") from e
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=headless)
        ctx = self._browser.new_context(locale="en-US", user_agent=UA, viewport={"width": 1440, "height": 900})
        self.page = ctx.new_page()
        self.delay = delay
        self.save_html = Path(save_html) if save_html else None
        if self.save_html:
            self.save_html.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, name: str = "") -> str:
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self.page.mouse.wheel(0, 5000)
        time.sleep(random.uniform(*self.delay))
        html = self.page.content()
        if "captcha" in html.lower()[:20000] and "validateCaptcha" in html:
            input("[!] Amazon 出现验证码，请在浏览器里完成后按回车继续...")
            html = self.page.content()
        if self.save_html and name:
            (self.save_html / f"{re.sub(r'[^a-zA-Z0-9_-]+', '_', name)[:80]}.html").write_text(html, encoding="utf-8")
        return html

    def close(self) -> None:
        self._browser.close()
        self._pw.stop()


def collect(out_dir: str | Path, seeds: list[str], bestseller_urls: list[str] | None = None,
            max_keywords: int = 30, max_products: int = 40, headless: bool = False,
            alphabet: bool = True) -> dict:
    """完整采集流程，写出与分析模块兼容的 CSV：

    keywords.csv     keyword, demand_proxy, suggest_rank, ...（demand_proxy = 首页自然位月销合计）
    search_results.csv  每个关键词首页的所有商品
    bestsellers.csv  类目榜单
    competitors.csv  详情页解析结果（asin, title, brand, price, monthly_sales=bought_past_month, ...）
    reviews.csv      详情页评论
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("[1/4] Amazon 搜索联想词 ...")
    kw = expand_keywords(seeds, alphabet=alphabet)
    kw.to_csv(out / "autocomplete_keywords.csv", index=False)
    targets = list(dict.fromkeys(seeds + kw["keyword"].head(max_keywords).tolist())) if not kw.empty else seeds

    br = Browser(headless=headless, save_html=str(out / "html"))
    try:
        print(f"[2/4] 搜索结果页 x{len(targets)} ...")
        results = []
        for k in targets:
            rows = parse_search_html(br.get(f"{BASE}/s?k={quote_plus(k)}", f"search_{k}"), k)
            print(f"  {k}: {len(rows)} items")
            results.extend(rows)
        sr = pd.DataFrame(results)
        sr.to_csv(out / "search_results.csv", index=False)

        print("[3/4] Best Sellers 榜单 ...")
        bs_rows = []
        for url in bestseller_urls or []:
            html = br.get(url, "bestsellers_" + url.rstrip("/").split("/")[-1])
            title = _text(_soup(html).select_one("h1")) or url
            bs_rows.extend(parse_bestsellers_html(html, title))
            # 榜单第 2 页（51-100 名）
            html2 = br.get(url.split("?")[0] + "?pg=2", "bestsellers_p2_" + url.rstrip("/").split("/")[-1])
            bs_rows.extend(parse_bestsellers_html(html2, title))
        bs = pd.DataFrame(bs_rows)
        if not bs.empty:
            bs = bs.drop_duplicates(subset=["category", "asin"])
            bs.to_csv(out / "bestsellers.csv", index=False)

        print("[4/4] 商品详情页 ...")
        candidates = _pick_detail_asins(sr, bs, max_products)
        products, reviews = [], []
        for i, asin in enumerate(candidates, 1):
            p = parse_product_html(br.get(f"{BASE}/dp/{asin}", f"dp_{asin}"), asin)
            print(f"  [{i}/{len(candidates)}] {p['title'][:60]} ${p['price']} {p['bought_past_month']}+/mo")
            reviews.extend(p.pop("reviews"))
            products.append(p)
    finally:
        br.close()

    _write_analysis_files(out, kw, sr, bs, products, reviews)
    return {"keywords": len(kw), "search_results": len(sr), "bestsellers": len(bs), "products": len(products)}


def _pick_detail_asins(sr: pd.DataFrame, bs: pd.DataFrame, n: int) -> list[str]:
    ranked: list[str] = []
    if not bs.empty:
        ranked += bs.sort_values("rank")["asin"].tolist()
    if not sr.empty:
        org = sr[~sr["sponsored"]].copy()
        org["bought_past_month"] = org["bought_past_month"].fillna(0)
        ranked += org.sort_values(["bought_past_month", "ratings_count"], ascending=False)["asin"].tolist()
    return list(dict.fromkeys(ranked))[:n]


def _write_analysis_files(out: Path, kw: pd.DataFrame, sr: pd.DataFrame, bs: pd.DataFrame,
                          products: list[dict], reviews: list[dict]) -> None:
    if not sr.empty:
        org = sr[~sr["sponsored"]]
        agg = org.groupby("keyword").agg(
            demand_proxy=("bought_past_month", lambda s: int(s.fillna(0).sum())),
            results_with_sales=("bought_past_month", lambda s: int(s.notna().sum())),
            median_price=("price", "median"),
            median_ratings=("ratings_count", "median"),
        ).reset_index()
        if not kw.empty:
            agg = agg.merge(kw[["keyword", "suggest_rank", "hits"]], on="keyword", how="left")
        agg.sort_values("demand_proxy", ascending=False).to_csv(out / "keywords.csv", index=False)

    if products:
        comp = pd.DataFrame([{
            "asin": p["asin"],
            "platform": "amazon",
            "title": p["title"],
            "brand": p["brand"] or p["store"],
            "price": p["price"],
            "list_price": p["list_price"],
            "monthly_sales": p["bought_past_month"],
            "reviews": p["ratings_count"],
            "rating": p["rating"],
            "launch_date": pd.to_datetime(p["date_first_available"], errors="coerce"),
            "color": p["color"],
            "material": p["material"],
            "shape": p["shape"],
            "style": p["style"],
            "size": p["size"],
            "variants_color": " | ".join(p["variants"].get("color", [])),
            "variants_size": " | ".join(p["variants"].get("size", [])),
            "bsr": p["best_sellers_rank"][0]["rank"] if p["best_sellers_rank"] else None,
            "bsr_category": p["best_sellers_rank"][0]["category"] if p["best_sellers_rank"] else "",
            "bullets": " || ".join(p["bullets"]),
            "image": p["image"],
        } for p in products])
        comp = comp.dropna(subset=["price"])
        comp.to_csv(out / "competitors.csv", index=False)
        (out / "products.json").write_text(json.dumps(products, ensure_ascii=False, indent=1, default=str))
    if reviews:
        pd.DataFrame(reviews).to_csv(out / "reviews.csv", index=False)


def parse_saved_html(html_dir: str | Path, out_dir: str | Path) -> dict:
    """不跑浏览器：解析你手动另存的 Amazon 页面（Ctrl+S 保存为 .html）。

    文件名约定：search_<关键词>.html / bestsellers_<任意>.html / dp_<ASIN>.html
    collect() 也会把抓到的页面存在 <out>/html/ 下，可以用它离线重新解析。
    """
    html_dir, out = Path(html_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results, bs_rows, products, reviews = [], [], [], []
    for f in sorted(html_dir.glob("*.htm*")):
        html = f.read_text(encoding="utf-8", errors="ignore")
        stem = f.stem
        if stem.startswith("search_"):
            results.extend(parse_search_html(html, stem[len("search_"):].replace("_", " ")))
        elif stem.startswith("bestsellers"):
            title = _text(_soup(html).select_one("h1")) or stem
            bs_rows.extend(parse_bestsellers_html(html, title))
        elif stem.startswith("dp_"):
            p = parse_product_html(html, stem[3:])
            reviews.extend(p.pop("reviews"))
            products.append(p)
    sr, bs = pd.DataFrame(results), pd.DataFrame(bs_rows)
    if not sr.empty:
        sr.to_csv(out / "search_results.csv", index=False)
    if not bs.empty:
        bs.drop_duplicates(subset=["category", "asin"]).to_csv(out / "bestsellers.csv", index=False)
    _write_analysis_files(out, pd.DataFrame(), sr, bs, products, reviews)
    return {"search_results": len(sr), "bestsellers": len(bs), "products": len(products), "reviews": len(reviews)}
