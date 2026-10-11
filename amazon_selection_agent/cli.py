"""命令行入口：python -m amazon_selection_agent <command> ..."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_analyze(a: argparse.Namespace) -> None:
    from .dashboard import build_dashboard
    from .data_loader import load_dataset
    from .pipeline import run_analysis

    ds = load_dataset(a.data)
    result = run_analysis(ds, today=a.today)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    page = build_dashboard(result, out / "dashboard.html", demo=a.demo)
    print(f"结论：{result['product']['concept']}")
    print(f"类目深耕：{result['category_depth']['score']} / 100 — {result['category_depth']['verdict']}")
    print(f"[ok] {out / 'analysis.json'}\n[ok] {page}  ← 用浏览器打开")


def cmd_research(a: argparse.Namespace) -> None:
    from .dashboard import build_research_page

    data = json.loads(Path(a.json).read_text(encoding="utf-8"))
    print(f"[ok] {build_research_page(data, a.out)}")


def cmd_agent(a: argparse.Namespace) -> None:
    from .agent import run_agent
    from .data_loader import load_dataset

    report = run_agent(load_dataset(a.data), question=a.question, web=a.web, effort=a.effort)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[ok] 报告已保存：{a.out}")


def cmd_amazon_collect(a: argparse.Namespace) -> None:
    from .scrapers.amazon import collect

    stats = collect(a.out, seeds=a.seeds, bestseller_urls=a.bestsellers, max_keywords=a.max_keywords,
                    max_products=a.max_products, headless=a.headless, alphabet=not a.no_alphabet)
    print(f"[ok] {stats}")


def cmd_amazon_parse(a: argparse.Namespace) -> None:
    from .scrapers.amazon import parse_saved_html

    print(f"[ok] {parse_saved_html(a.html_dir, a.out)}")


def cmd_amazon_keywords(a: argparse.Namespace) -> None:
    from .scrapers.amazon import expand_keywords

    df = expand_keywords(a.seeds, alphabet=not a.no_alphabet)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(df.head(30).to_string(index=False))
    print(f"[ok] {len(df)} 个联想词 → {a.out}")


def cmd_wayfair(a: argparse.Namespace) -> None:
    from .scrapers.wayfair import save, scrape

    products = scrape(a.keyword, pages=a.pages, max_products=a.max_products, headless=a.headless)
    save(products, a.out, keyword=a.keyword)


def cmd_google_trends(a: argparse.Namespace) -> None:
    from .analyzers.trends import fetch_google_trends

    df = fetch_google_trends(a.terms, geo=a.geo, timeframe=a.timeframe)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"[ok] {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="amazon_selection_agent", description="Amazon 家居选品 Agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("analyze", help="离线分析一个数据目录并生成可视化网站")
    s.add_argument("data", help="数据目录（keywords.csv / category_monthly.csv / competitors.csv / reviews.csv ...）")
    s.add_argument("--out", default="output")
    s.add_argument("--today", default=None, help="分析基准日期 YYYY-MM-DD（计算新品占比用）")
    s.add_argument("--demo", action="store_true", help="在页面顶部标注为演示数据")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("research", help="把 research/*.json（网页检索的真实数据）渲染成网站")
    s.add_argument("json")
    s.add_argument("--out", default="output/research_report.html")
    s.set_defaults(func=cmd_research)

    s = sub.add_parser("agent", help="让 Claude 调用分析工具写完整选品报告（需 ANTHROPIC_API_KEY）")
    s.add_argument("data")
    s.add_argument("--question", default=None)
    s.add_argument("--web", action="store_true", help="开启服务器端 web search / web fetch")
    s.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    s.add_argument("--out", default="output/agent_report.md")
    s.set_defaults(func=cmd_agent)

    s = sub.add_parser("amazon-collect", help="采集 Amazon 联想词 + 搜索页 + Best Sellers + 详情页（需能访问 amazon.com）")
    s.add_argument("seeds", nargs="+", help="种子关键词，如 'wavy mirror' 'small space mirror'")
    s.add_argument("--bestsellers", nargs="*", default=[], help="Best Sellers 类目 URL")
    s.add_argument("--max-keywords", type=int, default=30)
    s.add_argument("--max-products", type=int, default=40)
    s.add_argument("--headless", action="store_true")
    s.add_argument("--no-alphabet", action="store_true", help="不做 a-z 联想扩展")
    s.add_argument("--out", default="data/amazon")
    s.set_defaults(func=cmd_amazon_collect)

    s = sub.add_parser("amazon-parse", help="解析手动另存的 Amazon 页面（search_*.html / bestsellers_*.html / dp_*.html）")
    s.add_argument("html_dir")
    s.add_argument("--out", default="data/amazon_saved")
    s.set_defaults(func=cmd_amazon_parse)

    s = sub.add_parser("amazon-keywords", help="只拉 Amazon 搜索联想词")
    s.add_argument("seeds", nargs="+")
    s.add_argument("--no-alphabet", action="store_true")
    s.add_argument("--out", default="data/autocomplete_keywords.csv")
    s.set_defaults(func=cmd_amazon_keywords)

    s = sub.add_parser("scrape-wayfair", help="抓取 Wayfair 搜索结果与商品页（需能访问 wayfair.com）")
    s.add_argument("keyword")
    s.add_argument("--pages", type=int, default=1)
    s.add_argument("--max-products", type=int, default=40)
    s.add_argument("--headless", action="store_true")
    s.add_argument("--out", default="data/wayfair")
    s.set_defaults(func=cmd_wayfair)

    s = sub.add_parser("google-trends", help="拉取 Google Trends 月度数据（需能访问 Google）")
    s.add_argument("terms", nargs="+")
    s.add_argument("--geo", default="US")
    s.add_argument("--timeframe", default="today 5-y")
    s.add_argument("--out", default="data/google_trends.csv")
    s.set_defaults(func=cmd_google_trends)

    a = p.parse_args(argv)
    try:
        a.func(a)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
