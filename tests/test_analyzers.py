import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from amazon_selection_agent.analyzers.keywords import analyze_keywords
from amazon_selection_agent.analyzers.roi import UnitInputs, referral_fee, unit_economics
from amazon_selection_agent.analyzers.text import match_labels, parse_inches, size_bucket
from amazon_selection_agent.analyzers.trends import analyze_series, event_spikes
from amazon_selection_agent.dashboard import build_dashboard, build_research_page
from amazon_selection_agent.data_loader import load_dataset
from amazon_selection_agent.lexicon import COLOR, PATTERN_SHAPE, SCENE
from amazon_selection_agent.pipeline import run_analysis

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "sample_data" / "demo_mirror"


@pytest.fixture(scope="session")
def demo_dir(tmp_path_factory):
    if not DEMO.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_data.py"), str(DEMO)], check=True)
    return DEMO


def test_match_labels_whole_word_and_plural():
    assert match_labels("Wavy Mirror for Small Spaces", SCENE) == ["小空间"]
    assert "波浪纹" in match_labels("white wavy mirror", PATTERN_SHAPE)
    assert match_labels("whitewash frame", COLOR) == []  # 不应误命中 white
    assert "租房" in match_labels("over-the-door mirror no-drill", SCENE)


def test_parse_inches():
    assert parse_inches("wavy mirror 63x20") == (63, 20)
    assert parse_inches('full length mirror 21" x 64"') == (64, 21)
    assert parse_inches("round mirror 24 inch") == 24
    assert parse_inches("arched mirror") is None
    assert size_bucket((63, 20)) == "大号 (48-65in)"


def test_keywords_persona_and_growth():
    df = pd.DataFrame({
        "keyword": ["dorm mirror", "wavy mirror", "round mirror", "mirror for small space"],
        "search_volume": [100, 300, 500, 100],
        "search_volume_last_year": [50, 150, 600, 50],
    })
    r = analyze_keywords(df)
    pattern = {x["label"]: x for x in r["dimensions"]["pattern_shape"]["labels"]}
    assert pattern["波浪纹"]["growth_yoy"] == pytest.approx(1.0)
    assert pattern["圆形"]["growth_yoy"] == pytest.approx(-1 / 6, rel=1e-3)
    personas = [p["persona"] for p in r["persona_signals"]]
    assert "大学生（Back to School 季）" in personas and "城市小户型/租房年轻人" in personas


def test_trend_verdict_and_black_friday():
    months = pd.period_range("2023-01", "2025-12", freq="M")
    vals = [100 * (1.02 ** i) * (2.0 if m.month == 11 else 1.0) for i, m in enumerate(months)]
    s = pd.Series(vals, index=months)
    r = analyze_series(s)
    assert r["verdict"] == "增长"
    assert r["peak_months"][0] == "11月"
    ev = event_spikes(s)
    assert ev["black_friday_multiplier"] > 1.9
    assert ev["verdict"].startswith("黑五强爆发")


def test_roi_math():
    assert referral_fee(300, furniture_tiered=True) == pytest.approx(0.15 * 200 + 0.10 * 100)
    r = unit_economics(UnitInputs(price=100, cogs=20, freight=10, fba_fee=15, tacos=0.1, return_rate=0.05, storage_other=0))
    # 100 - (30 + 15 + 15 + 10 + 5) = 25
    assert r["profit_per_unit"] == pytest.approx(25)
    assert r["roi"] == pytest.approx(25 / 30, rel=1e-3)
    assert r["target_cogs_for_20pct_margin"] == pytest.approx(25)  # 利润 20 时出厂价可到 25


def test_pipeline_and_dashboard(demo_dir, tmp_path):
    result = run_analysis(load_dataset(demo_dir), today="2026-10-11")
    assert result["category_trends"]["units_sold"]["verdict"] in {"增长", "温和增长"}
    assert any(b.get("is_win_band") for b in result["competition"]["price_bands"])
    assert result["voc"]["pain_points"]
    assert "波浪纹" in result["product"]["concept"]
    json.dumps(result, default=str)
    page = build_dashboard(result, tmp_path / "d.html", demo=True)
    html = page.read_text(encoding="utf-8")
    assert "window.DATA" in html and "/*__" not in html


def test_research_page_builds(tmp_path):
    data = json.loads((ROOT / "research" / "home_mirror_curved_2026-10.json").read_text(encoding="utf-8"))
    for row in data["listings"]["rows"]:
        assert row["source"], row
    html = build_research_page(data, tmp_path / "r.html").read_text(encoding="utf-8")
    assert "/*__" not in html and "</script>" in html


def test_keywords_demand_proxy(tmp_path):
    pd.DataFrame({"keyword": ["wavy mirror", "dorm mirror", "x"], "demand_proxy": [900, 300, 0]}).to_csv(tmp_path / "keywords.csv", index=False)
    ds = load_dataset(tmp_path)
    assert list(ds.keywords["search_volume"]) == [900, 300]
    assert "需求代理" in ds.keyword_volume_basis
