/* 渲染 pipeline.run_analysis() 的结果。DATA 由 Python 注入。 */
(function () {
  const D = window.DATA;
  const { h } = Viz;
  const pct = v => (v == null ? "—" : (v * 100).toFixed(Math.abs(v) < 0.1 ? 1 : 0) + "%");
  const sgn = v => (v == null ? "—" : (v > 0 ? "+" : "") + pct(v));
  const num = v => (v == null ? "—" : v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v >= 1e3 ? (v / 1e3).toFixed(v >= 1e4 ? 0 : 1) + "K" : String(Math.round(v)));
  const $ = id => document.getElementById(id);
  const hide = id => { const n = $(id); if (n) n.closest("section").hidden = true; };

  $("title").textContent = "选品分析：" + D.dataset;
  $("meta").textContent = `生成于 ${D.generated_at} · 数据：${D.inputs.join(", ")} · 关键词量口径：${D.keyword_volume_basis}`;
  if (D.demo) $("banner").hidden = false;

  // KPI
  const ct = D.category_trends || {};
  const sv = ct.search_volume || ct.units_sold || {};
  const units = ct.units_sold || {};
  const kpis = [
    ["类目趋势", sv.verdict || "—", sv.yoy_last_12m != null ? `近 12 月同比 ${sgn(sv.yoy_last_12m)}` : ""],
    ["销量同比", sgn(units.yoy_last_12m), units.cagr != null ? `CAGR ${pct(units.cagr)}` : ""],
    ["黑五爆发系数", (units.events || sv.events || {}).black_friday_multiplier ? (units.events || sv.events).black_friday_multiplier + "×" : "—", "11 月 ÷ 平日中位数"],
    ["类目深耕评分", D.category_depth ? D.category_depth.score + " / 100" : "—", D.category_depth ? D.category_depth.verdict.split("：")[0] : ""],
    ["CR5 品牌集中度", D.competition && D.competition.cr5 != null ? pct(D.competition.cr5) : "—", "Top5 品牌销售额占比"],
    ["竞品平均评分", D.voc ? D.voc.avg_rating + " ★" : "—", D.voc ? `差评占比 ${pct(D.voc.negative_share)}` : ""],
  ];
  kpis.forEach(([l, v, d]) => { const k = h("div", "kpi", null, $("kpis")); h("div", "l", l, k); h("div", "v", v, k); h("div", "d", d, k); });

  // 产品方案
  const P = D.product;
  $("concept").textContent = P.concept;
  const specList = $("spec");
  const dimName = { scene: "场景", pattern_shape: "款式/纹理", color: "颜色", style: "风格", material: "材质", feature: "功能" };
  Object.entries(dimName).forEach(([k, name]) => {
    const items = (P.spec || {})[k] || [];
    if (!items.length) return;
    const li = h("li", null, null, specList);
    h("strong", null, name + "：", li);
    items.forEach((it, i) => h("span", "tag" + (i === 0 ? " hi" : ""), `${it.label} ${pct(it.share)}${it.growth_yoy != null ? " · " + sgn(it.growth_yoy) : ""}`, li));
  });
  if (P.spec && P.spec.exact_sizes && P.spec.exact_sizes.length) {
    const li = h("li", null, null, specList); h("strong", null, "热门尺寸：", li);
    P.spec.exact_sizes.forEach(s => h("span", "tag", `${s.size} (${num(s.search_volume)})`, li));
  }
  if (P.price) { const li = h("li", null, null, specList); h("strong", null, "定价：", li); h("span", null, `${P.price.band} — ${P.price.why}`, li); }
  if (P.launch_timing) {
    const t = P.launch_timing, li = h("li", null, null, specList);
    h("strong", null, "上新节奏：", li);
    h("span", null, `旺季 ${t.peak_months.join("、")}；${t.launch_by}前上架，${t.stock_in_fba_by}前入仓 FBA`, li);
  }
  (P.improvements || []).forEach(i => { const li = h("li", null, null, $("improve")); h("strong", null, `${i.pain_point}（差评提及 ${pct(i.negative_mention_rate)}）：`, li); h("span", null, i.fix, li); });
  (P.product_line_ideas || []).forEach(t => h("li", null, t, $("line")));
  (P.listing_keywords || []).forEach(k => h("span", "tag", k, $("lk")));

  // 画像
  const pe = D.persona || {};
  Viz.hbar($("persona-chart"), (pe.segments || []).map(s => ({ label: s.persona, value: s.search_share })), pct);
  (pe.evidence || []).forEach(t => h("li", null, t, $("persona-ev")));
  if (pe.what_they_value) { h("p", "sub", "在意：" + pe.what_they_value.join("、"), $("persona-ev").parentNode); }
  if (pe.what_they_hate) { h("p", "sub", "讨厌：" + pe.what_they_hate.join("、"), $("persona-ev").parentNode); }

  // 趋势
  const S = D.series || {};
  if (S.category_monthly) {
    const cm = S.category_monthly;
    if (cm.search_volume) Viz.line($("sv-line"), cm.month, [{ name: "类目月搜索量", values: cm.search_volume }], num); else $("sv-line").closest(".card").hidden = true;
    if (cm.units_sold) Viz.line($("units-line"), cm.month, [{ name: "类目月销量", values: cm.units_sold }], num); else $("units-line").closest(".card").hidden = true;
    const seas = (units.seasonality_index && units) || sv;
    if (seas.seasonality_index) {
      const labels = Object.keys(seas.seasonality_index), vals = Object.values(seas.seasonality_index);
      const hi = seas.peak_months.map(m => labels.indexOf(m));
      Viz.columns($("season"), labels, vals, v => v.toFixed(2), hi);
      $("season-note").textContent = `旺季：${seas.peak_months.join("、")}；淡季：${seas.low_months.join("、")}；季节强度 ${seas.seasonality_strength}×（峰/谷）`;
    }
    const ev = (units.events || sv.events || {});
    if (ev.average) {
      Viz.hbar($("events"), Object.entries(ev.average).map(([k, v]) => ({ label: k, value: v, highlight: k.startsWith("黑五") })), v => v.toFixed(2) + "×");
      $("events-note").textContent = ev.verdict;
    }
  } else hide("sv-line");
  if (S.google_trends) {
    const gt = S.google_trends, names = Object.keys(gt).filter(k => k !== "month").slice(0, 4);
    Viz.line($("gt-line"), gt.month, names.map(n => ({ name: n, values: gt[n] })), v => Math.round(v));
    const rank = (D.google_trends || {}).ranking_by_yoy || [];
    $("gt-note").textContent = rank.length ? "同比：" + rank.map(r => `${r.term} ${sgn(r.yoy)}`).join("；") : "";
  } else $("gt-line").closest(".card").hidden = true;

  // 需求拆解
  const K = D.keywords;
  if (K) {
    const dims = Object.entries(K.dimensions).filter(([, v]) => v.labels.length);
    const tabs = $("dim-tabs");
    const show = key => {
      [...tabs.children].forEach(b => b.setAttribute("aria-selected", b.dataset.k === key));
      const rows = K.dimensions[key].labels.map(r => ({
        label: r.label, value: r.share, note: r.growth_yoy != null ? sgn(r.growth_yoy) : "",
        tip: [["搜索量", num(r.search_volume), null], ["关键词", r.top_keywords.join(", "), null]],
      }));
      Viz.hbar($("dim-chart"), rows, pct);
    };
    dims.forEach(([k, v]) => { const b = h("button", null, v.name, tabs); b.dataset.k = k; b.type = "button"; b.onclick = () => show(k); });
    show(dims[0][0]);
    const rk = K.rising_keywords || K.top_keywords;
    $("rising-title").textContent = K.rising_keywords ? "增长最快的关键词" : "搜索量最高的关键词";
    const tb = $("rising").querySelector("tbody");
    rk.forEach(r => { const tr = h("tr", null, null, tb); h("td", null, r.keyword, tr); h("td", "num", num(r.search_volume), tr); h("td", "num", r.growth_yoy != null ? sgn(r.growth_yoy) : "—", tr); });
  } else hide("dim-chart");

  // 竞争
  const C = D.competition;
  if (C) {
    if (C.attribute_gaps && C.attribute_gaps.length)
      Viz.diverging($("gaps"), C.attribute_gaps.slice(0, 10).map(g => ({ label: g.label, value: g.gap, tip: [["需求占比", pct(g.demand_share), null], ["供给占比", pct(g.supply_share), null], ["在售竞品", String(g.listings), null]] })), sgn);
    else $("gaps").closest(".card").hidden = true;
    Viz.hbar($("bands"), C.price_bands.map(b => ({ label: b.band + (b.is_win_band ? " ★" : ""), value: b.win_rate, note: num(b.sales_per_listing), highlight: b.is_win_band, tip: [["单品平均销量", num(b.sales_per_listing), null], ["竞品数", String(b.listings), null], ["销量占比", pct(b.sales_share), null]] })), pct, { max: 1 });
    const wb = C.price_bands.find(b => b.is_win_band);
    $("bands-note").textContent = `条长 = 胜率（该价格带进入头部 30% 的竞品比例），右列 = 单品平均销量；口径：${C.sales_basis}。★ 胜率价位：${wb ? wb.band : "—"}`;
    if (wb) {
      const price = Math.round(((wb.low + wb.high) / 2)) - 0.01;
      Viz.roi($("roi"), [{ name: "胜率价位 " + wb.band, price, cogs: +(price * 0.22).toFixed(2), freight: +(price * 0.08).toFixed(2), fba_fee: +(price * 0.2).toFixed(2), referral_rate: 0.15, furniture_tiered: false, tacos: 0.15, return_rate: 0.05, storage_other: 1, monthly_units: Math.round(wb.sales_per_listing) || 300, note: "出厂价/头程/FBA 默认按售价比例假设，请替换为工厂报价与 FBA 计算器结果。" }]);
    }
    if (C.top_brands) Viz.hbar($("brands"), C.top_brands.map(b => ({ label: b.brand, value: b.revenue_share })), pct);
    else $("brands").closest(".card").hidden = true;
    const tb = $("listings").querySelector("tbody");
    C.top_listings.forEach(r => { const tr = h("tr", null, null, tb); h("td", null, r.title, tr); h("td", null, r.brand || "", tr); h("td", "num", "$" + r.price.toFixed(2), tr); h("td", "num", num(r.sales), tr); h("td", "num", num(r.reviews), tr); h("td", "num", r.rating ? r.rating.toFixed(1) : "—", tr); });
  } else hide("bands");

  // VOC
  const V = D.voc;
  if (V) {
    Viz.hbar($("pain"), V.pain_points.slice(0, 8).map(p => ({ label: p.theme, value: p.negative_mention_rate, tip: (p.examples || []).slice(0, 1).map(e => ["", e, null]) })), pct);
    Viz.hbar($("delight"), V.delights.map(p => ({ label: p.theme, value: p.positive_mention_rate })), pct);
    Viz.hbar($("who"), V.who_buys.slice(0, 6).map(p => ({ label: p.label, value: p.rate })), pct);
    (V.negative_phrases || []).slice(0, 12).forEach(p => h("span", "tag", `${p.phrase} ×${p.count}`, $("phrases")));
  } else hide("pain");

  // 深耕
  const Dp = D.category_depth;
  if (Dp) {
    Viz.hbar($("depth"), Dp.factors.map(f => ({ label: f.factor, value: f.score, tip: [["", f.reason, null]] })), v => v.toFixed(1), { max: 20 });
    $("depth-verdict").textContent = `${Dp.score} / 100 — ${Dp.verdict}`;
    Dp.factors.forEach(f => h("li", null, `${f.factor}：${f.reason}`, $("depth-reasons")));
  }

})();
