"""Claude 选品 Agent：把各分析模块作为工具交给 Claude，让它像资深家居类目运营一样
调用数据、交叉验证、并写出完整的选品报告（中文）。

需要 ANTHROPIC_API_KEY（或 `ant auth login`）。可选开启 Anthropic 服务器端 web search /
web fetch，在本地拿不到数据时查公开资料（趋势文章、行业报告、Amazon 公开页面）。
"""

from __future__ import annotations

import json

import anthropic
from anthropic import beta_tool

from .analyzers.competition import analyze_competition, category_depth_score
from .analyzers.keywords import analyze_keywords
from .analyzers.product import build_persona, propose_product
from .analyzers.roi import UnitInputs, unit_economics
from .analyzers.trends import analyze_category, analyze_google_trends, fetch_google_trends
from .analyzers.voc import analyze_reviews
from .data_loader import Dataset

MODEL = "claude-opus-5-5"

SYSTEM = """你是一名资深 Amazon 美国站家居类目选品负责人。目标：基于数据找到一个能做成爆款的产品，并判断类目能否深耕。

工作方式：
- 先调用 list_available_data 看有哪些数据，再按需调用分析工具；不要编造工具没有返回的数字。
- 每个结论都写明依据（哪个工具、哪个指标）；数据缺失时明确说“缺数据”，并说明需要什么数据补齐。
- 关键词里的场景词（small space、dorm、apartment、no drill）代表人群：学生、租房族等，要据此做用户分层。
- 颜色/款式（如 wavy 波浪纹）/尺寸要结合 搜索量占比 + 同比增长 + 供需差 判断是趋势还是存量。
- 黑五看大促爆发系数；趋势看同比、CAGR、去季节性斜率。
- 价格看胜率价位，并用 unit_economics 测算利润与 ROI（大件 FBA 费、15% 佣金、广告会显著压缩利润）。

最终报告结构（中文，Markdown）：
1. 一句话结论（做不做、做什么）
2. 市场容量与需求趋势（增长/下滑、季节性、黑五是否爆发）
3. 用户分层：每层的规模、价格带、场景、颜色偏好、痛点/爽点
4. 款式/颜色/尺寸/场景趋势
5. 竞争格局、胜率价位
6. VOC 痛点 → 产品改进点；爽点 → 卖点
7. 爆款产品方案（规格、颜色、尺寸、定价、包装、上新节奏、Listing 埋词）
8. 利润与 ROI 测算（列出假设）
9. 类目深耕判断与产品线规划
10. 风险与下一步需要补的数据"""


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def build_tools(ds: Dataset):
    cache: dict = {}

    def kw():
        if "kw" not in cache:
            cache["kw"] = analyze_keywords(ds.keywords) if ds.keywords is not None else None
        return cache["kw"]

    def trends():
        if "trends" not in cache:
            cache["trends"] = analyze_category(ds.category_monthly) if ds.category_monthly is not None else None
        return cache["trends"]

    def comp():
        if "comp" not in cache:
            cache["comp"] = analyze_competition(ds.competitors, kw()) if ds.competitors is not None else None
        return cache["comp"]

    def voc():
        if "voc" not in cache:
            cache["voc"] = analyze_reviews(ds.reviews) if ds.reviews is not None else None
        return cache["voc"]

    @beta_tool
    def list_available_data() -> str:
        """列出当前数据集里有哪些数据文件，以及关键词量的口径。"""
        return _dump({"dataset": ds.name, "available": ds.available(), "keyword_volume_basis": ds.keyword_volume_basis})

    @beta_tool
    def keyword_analysis() -> str:
        """关键词需求拆解：按 场景/颜色/款式纹理/风格/材质/尺寸/功能 汇总搜索量占比与同比，给出人群信号、上升词和下降词。"""
        return _dump(kw() or {"error": "没有 keywords.csv"})

    @beta_tool
    def category_trend_analysis() -> str:
        """类目月度搜索量/销量/销售额：同比、CAGR、去季节性趋势、季节性指数、黑五/Prime Day/返校季爆发系数。"""
        return _dump(trends() or {"error": "没有 category_monthly.csv"})

    @beta_tool
    def google_trends_analysis(terms: str = "") -> str:
        """Google Trends 分析。默认用数据集里的 google_trends.csv；传入逗号分隔的 terms 时尝试在线拉取（最多 5 个词，需要能访问 Google）。

        Args:
            terms: 可选，逗号分隔的英文关键词，如 "wavy mirror,arched mirror"。
        """
        if terms:
            try:
                return _dump(analyze_google_trends(fetch_google_trends([t.strip() for t in terms.split(",") if t.strip()])))
            except Exception as e:  # 网络/依赖问题时回退到本地数据
                if ds.google_trends is None:
                    return _dump({"error": f"在线拉取失败：{e}"})
        if ds.google_trends is None:
            return _dump({"error": "没有 google_trends.csv"})
        return _dump(analyze_google_trends(ds.google_trends))

    @beta_tool
    def competition_analysis() -> str:
        """竞争格局：品牌集中度 CR3/CR5、新品销量占比、评论壁垒、价格带胜率（胜率价位）、属性供需差、头部竞品。"""
        return _dump(comp() or {"error": "没有 competitors.csv"})

    @beta_tool
    def voc_analysis() -> str:
        """评论 VOC：差评痛点（附原文例子与改进建议）、好评爽点、谁在买、使用场景、差评高频短语。"""
        return _dump(voc() or {"error": "没有 reviews.csv"})

    @beta_tool
    def persona_and_product_draft() -> str:
        """基于规则生成用户画像、类目深耕评分和产品方案草稿，供你校验和深化。"""
        depth = category_depth_score(comp() or {}, trends(), voc())
        return _dump({
            "persona": build_persona(kw(), voc()),
            "category_depth": depth,
            "product_draft": propose_product(kw(), trends(), comp(), voc(), depth),
        })

    @beta_tool
    def unit_economics_calc(price: float, cogs: float, freight: float, fba_fee: float,
                            tacos: float = 0.15, return_rate: float = 0.05,
                            furniture_tiered: bool = False, monthly_units: int = 300) -> str:
        """单品利润与 ROI 测算（Amazon FBA）。返回单件利润、净利率、ROI、盈亏平衡 ACoS、20% 净利目标出厂价。

        Args:
            price: 售价（美元）。
            cogs: 出厂价 FOB（美元/件）。
            freight: 头程（海运+清关+入仓，美元/件）。
            fba_fee: FBA 配送费（美元/件；最长边 >59 英寸进入 Extra-large 档会明显更高）。
            tacos: 广告费占销售额比例，如 0.15。
            return_rate: 退货率，如 0.05。
            furniture_tiered: Furniture 类目佣金阶梯（$200 以内 15%、以上 10%）。
            monthly_units: 预计月销量。
        """
        return _dump(unit_economics(UnitInputs(price=price, cogs=cogs, freight=freight, fba_fee=fba_fee, tacos=tacos,
                                               return_rate=return_rate, furniture_tiered=furniture_tiered,
                                               monthly_units=monthly_units)))

    return [list_available_data, keyword_analysis, category_trend_analysis, google_trends_analysis,
            competition_analysis, voc_analysis, persona_and_product_draft, unit_economics_calc]


def run_agent(ds: Dataset, question: str | None = None, web: bool = False, effort: str = "high",
              on_text=print) -> str:
    """运行选品 Agent，返回最终报告（Markdown）。

    web=True 时额外开启 Anthropic 服务器端 web_search / web_fetch（在 Anthropic 侧执行，
    本地网络受限时也能查公开资料）。
    """
    client = anthropic.Anthropic()
    tools: list = build_tools(ds)
    if web:
        tools += [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": 10},
            {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 10},
        ]
    prompt = question or "请基于现有数据完成完整的选品分析，并给出一个可以开发的爆款产品方案。"
    messages: list = [{"role": "user", "content": prompt}]

    final = None
    for _ in range(5):  # 服务器端工具长时间运行时会返回 pause_turn，需要重启 runner 继续
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,  # 非流式请求上限；报告通常 4-8K tokens
            system=SYSTEM,
            tools=tools,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            # 遇到安全分类器拒答时由服务器自动切换到推荐的后备模型
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        for message in runner:
            final = message
            messages.append({"role": "assistant", "content": message.content})
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                messages.append(tool_response)
            for block in message.content:
                if block.type == "tool_use":
                    on_text(f"[tool] {block.name}")
        if final is None or final.stop_reason != "pause_turn":
            break

    if final is None:
        raise RuntimeError("Agent 没有返回结果")
    if final.stop_reason == "refusal":
        raise RuntimeError("请求被模型拒绝（refusal）")
    return "\n".join(b.text for b in final.content if b.type == "text")
