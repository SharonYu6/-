"""把分析结果渲染成单文件 HTML 网站（无外部依赖，双击即可打开，也可直接部署）。"""

from __future__ import annotations

import json
from pathlib import Path

WEB = Path(__file__).parent / "web"


def _safe_json(data: dict) -> str:
    # 防止数据中的 "</script>" 提前结束脚本
    return json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")


def render(template: str, data: dict, app_js: str) -> str:
    html = (WEB / template).read_text(encoding="utf-8")
    return (html
            .replace("/*__CSS__*/", (WEB / "style.css").read_text(encoding="utf-8"))
            .replace("/*__DATA__*/", _safe_json(data))
            .replace("/*__CHARTS__*/", (WEB / "charts.js").read_text(encoding="utf-8")
                     + "\n" + (WEB / "roi.js").read_text(encoding="utf-8"))
            .replace("/*__APP__*/", (WEB / app_js).read_text(encoding="utf-8")))


def build_dashboard(result: dict, out_path: str | Path, demo: bool = False) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render("dashboard.html", {**result, "demo": demo}, "dashboard.js"), encoding="utf-8")
    return out


def build_research_page(research: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render("research.html", research, "research.js"), encoding="utf-8")
    return out
