/* 渲染 research/*.json（真实检索数据）。 */
(function () {
  const D = window.DATA;
  const { h } = Viz;
  const $ = id => document.getElementById(id);
  const num = v => (v == null ? "—" : v >= 1e3 ? (v / 1e3).toFixed(v >= 1e4 ? 0 : 1) + "K" : String(Math.round(v)));
  const rows = D.listings.rows;
  const monthly = rows.filter(r => r.bought && r.period === "月");

  $("title").textContent = D.title;
  $("subtitle").textContent = D.subtitle;
  $("method").textContent = "方法：" + D.method;

  function sources(parent, list) {
    const p = h("div", "src", null, parent);
    (list || []).forEach((s, i) => {
      if (i) p.appendChild(document.createTextNode(" · "));
      if (s.url) { const a = h("a", null, s.name, p); a.href = s.url; a.target = "_blank"; a.rel = "noopener"; }
      else h("span", null, s.name, p);
    });
  }
  function finding(parent, f) {
    const li = h("li", null, null, parent);
    if (f.conf) { h("span", "conf", "可信度 " + f.conf, li); li.appendChild(document.createTextNode(" ")); }
    h("span", null, f.text, li);
    sources(li, f.sources);
  }

  // KPI
  D.kpis.forEach(k => { const t = h("div", "kpi", null, $("kpis")); h("div", "l", k.label, t); h("div", "v", k.value, t); h("div", "d", `${k.delta} · ${k.note} · 可信度${k.conf}`, t); });

  // 结论速览
  const sec = Object.fromEntries(D.sections.map(s => [s.id, s]));
  [
    ["市场容量", `线上家具假日季 $31.1B（+6.6%）；宿舍/公寓家居 $14.0B；Sofa Tables 小类前 40 名 ≥ 20,000 件/月（BSR 校准）`],
    ["需求趋势", sec.trend.verdict],
    ["季节 & 黑五", sec.season.verdict],
    ["用户分层", D.segments.rows.map(s => s.name).join(" / ")],
    ["胜率价位", D.win_price.verdict],
    ["ROI", "同一面镜子 $69.99 净利约 19%、ROI 约 76%；跟爆款价 $49.99 只剩约 1%；64\" 进入 Extra-large FBA 档后亏损（出厂价为假设值，见 ⑫ 可调）"],
    ["颜色 & 款式", sec.design.verdict],
    ["VOC", sec.voc.verdict],
    ["产品方案", D.product.name],
    ["深耕", D.depth.verdict],
  ].forEach(([k, v]) => { const li = h("li", null, null, $("summary")); h("strong", null, k + "：", li); h("span", null, v, li); });

  // ① 市场容量
  const byCat = {};
  monthly.forEach(r => { byCat[r.category] = (byCat[r.category] || 0) + r.bought; });
  Viz.hbar($("cap-chart"), Object.entries(byCat).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: k, value: v, tip: monthly.filter(r => r.category === k).map(r => [r.brand + " " + r.product, num(r.bought) + "+", null]) })), v => num(v) + "+");
  $("cap-note").textContent = `只统计检索中出现徽章的 ${monthly.length} 个商品，是严格下限；全身镜主要来自 Delma 一款 3K+。`;
  $("bsr").textContent = D.market.bsr_calibration;
  const b = D.market.bsr_calc;
  [["Sofa Tables 前 40 名月销下限", num(b.rank * b.units) + " 件"], ["月销售额下限", "$" + ((b.rank * b.units * b.price) / 1e6).toFixed(1) + "M"], ["年化下限", "$" + ((b.rank * b.units * b.price * 12) / 1e6).toFixed(0) + "M"]]
    .forEach(([l, v]) => { const t = h("div", "kpi", null, $("bsr-kpis")); h("div", "l", l, t); h("div", "v", v, t); });
  $("dorm-title").textContent = D.dorm_spend.title + "（" + D.dorm_spend.unit + "）";
  Viz.columns($("dorm"), D.dorm_spend.labels, D.dorm_spend.values, v => v.toFixed(1), [D.dorm_spend.labels.length - 1]);
  $("dorm-note").textContent = D.dorm_spend.note;

  // ②③⑧⑨ 文字型章节
  const titles = { trend: "② 需求趋势：增长还是下滑？", season: "③ 季节性 & 黑五是否爆发", design: "⑧ Top 卖家的设计", keywords: "⑨ 搜索关键词" };
  Object.entries(titles).forEach(([id, title]) => {
    const s = sec[id], host = $("sec-" + id);
    h("h2", null, title, host);
    const card = h("div", "card", null, host);
    h("div", "callout", null, card).appendChild(h("strong", null, s.verdict));
    const ul = h("ul", "clean", null, card); ul.style.marginTop = "12px";
    s.findings.forEach(f => finding(ul, f));
    if (s.keywords) {
      const t = h("table", null, null, card); t.style.marginTop = "12px";
      const hr = h("tr", null, null, h("thead", null, null, t));
      ["关键词", "月搜索量", "来源", "可信度"].forEach((c, i) => h("th", i === 1 ? "num" : null, c, hr));
      const tb = h("tbody", null, null, t);
      s.keywords.forEach(k => { const tr = h("tr", null, null, tb); h("td", null, k.keyword, tr); h("td", "num", k.volume.toLocaleString(), tr); h("td", null, k.source, tr); h("td", null, k.conf, tr); });
    }
  });

  // ④ 用户分层
  $("seg-note").textContent = D.segments.note;
  const MAX = 450, track = $("seg-price");
  D.segments.rows.forEach((s, i) => {
    const row = h("div", "range-row", null, track);
    h("div", "hbar-label", s.name, row);
    const tr = h("div", "range-track", null, row);
    if (s.price_low != null) {
      const bar = h("div", "range-bar", null, tr);
      bar.style.left = (100 * s.price_low) / MAX + "%";
      bar.style.width = (100 * (s.price_high - s.price_low)) / MAX + "%";
      bar.style.background = `var(--series-${(i % 4) + 1})`;
    } else h("span", "src", "无可靠价格数据", tr);
    rows.filter(r => r.price && r.segment === s.key).forEach(r => {
      const dot = h("div", "range-dot", null, tr);
      dot.style.left = (100 * r.price) / MAX + "%";
      dot.title = `${r.brand} ${r.product} $${r.price}`;
    });
    h("div", "hbar-value", s.price_low != null ? `$${s.price_low}–${s.price_high}` : "—", row);
  });
  const axis = h("div", "range-axis", null, track);
  [0, 100, 200, 300, 400].forEach(v => { const t = h("span", null, "$" + v, axis); t.style.left = (100 * v) / MAX + "%"; });
  Viz.table(track, ["人群", "价格区间", "依据"], D.segments.rows.map(s => [s.name, s.price_low != null ? `$${s.price_low}–${s.price_high}` : "—", s.price]));
  D.segments.rows.forEach(s => {
    const c = h("div", "card", null, $("seg-cards"));
    h("h3", null, s.name, c);
    const t = h("table", null, null, c);
    [["规模", s.size], ["价格", s.price], ["买什么", s.products], ["用在哪", s.scenes], ["颜色", s.colors], ["痛点", s.pains], ["爽点", s.delights], ["旺季", s.peak], ["可信度", s.conf]]
      .forEach(([k, v]) => { const tr = h("tr", null, null, t); h("th", null, k, tr); h("td", null, v, tr); });
  });

  // ⑤ 胜率价位
  $("win-verdict").textContent = D.win_price.verdict;
  D.win_price.notes.forEach(n => h("li", null, n, $("win-notes")));
  const priced = rows.filter(r => r.price);
  Viz.hbar($("price-sales"), priced.sort((a, b) => a.price - b.price).map(r => ({ label: `$${r.price} ${r.brand}`, value: r.bought || 0, note: r.category, tip: [[r.product, "", null], ["备注", r.badge || "—", null]] })), v => (v ? num(v) + "+/月" : "无徽章"));

  // ⑥ 颜色 & 款式；⑦ 场景
  function weighted(key, multi) {
    const acc = {};
    rows.forEach(r => {
      const vals = multi ? r[key] : [r[key]];
      vals.forEach(v => { if (!v || v === "—") return; acc[v] = acc[v] || { sales: 0, n: 0 }; acc[v].n += 1; if (r.period === "月") acc[v].sales += r.bought || 0; });
    });
    return Object.entries(acc).sort((a, b) => b[1].sales - a[1].sales || b[1].n - a[1].n)
      .map(([k, v]) => ({ label: k, value: v.sales, note: v.n + " 款", tip: [["出现在爆款中", v.n + " 款", null]] }));
  }
  Viz.hbar($("colors"), weighted("color_family"), v => num(v) + "+");
  Viz.hbar($("styles"), weighted("style"), v => num(v) + "+");
  Viz.hbar($("scenes"), weighted("scenes", true), v => num(v) + "+");
  [
    "卧室是所有品类的基础场景，但增量来自“一物多场景”：EliteSet 斗柜标题同时写 Bedroom / Living Room TV Stand / Closet / Nursery / Hallway。",
    "玄关/走廊是玄关桌的核心，也是全身镜的延伸场景（Ultym 标题含 Entryway），可以做“玄关镜 + 玄关桌”组合。",
    "宿舍/门后对应学生：挂门镜和 59x16 窄镜，痛点是清晰度与挂钩。",
    "儿童房（Nursery）出现在大件斗柜标题中：家庭人群把斗柜当尿布台/收纳。"
  ].forEach(t => h("li", null, t, $("scene-notes")));

  // ⑩ VOC
  const pul = h("ul", "clean", null, $("pains"));
  sec.voc.findings.concat(D.pains_extra).forEach(f => finding(pul, f));
  const dul = h("ul", "clean", null, $("delights"));
  D.delights.forEach(f => finding(dul, f));

  // ⑪ 产品
  const P = D.product;
  $("p-name").textContent = P.name;
  $("p-concept").textContent = P.concept;
  P.spec.forEach(([k, v]) => { const tr = h("tr", null, null, $("p-spec")); h("th", null, k, tr); h("td", null, v, tr); });
  P.improvements.forEach(([k, v]) => { const tr = h("tr", null, null, $("p-improve")); h("th", null, k, tr); h("td", null, v, tr); });
  P.line.forEach(t => h("li", null, t, $("p-line")));

  // ⑫ ROI
  $("fees").textContent = D.fees.text;
  sources($("fees").parentNode.insertBefore(h("div"), $("roi")), D.fees.sources);
  Viz.roi($("roi"), D.roi_scenarios);

  // ⑬ 深耕
  $("depth-verdict").textContent = D.depth.verdict;
  D.depth.factors.forEach(f => { const tr = h("tr", null, null, $("depth").querySelector("tbody")); h("td", null, f.factor, tr); h("td", null, f.rating, tr); h("td", null, f.reason, tr); });

  // 全部商品
  $("list-note").textContent = D.listings.note;
  rows.forEach(r => {
    const tr = h("tr", null, null, $("listings").querySelector("tbody"));
    h("td", null, r.category, tr); h("td", null, r.brand, tr); h("td", null, r.product, tr); h("td", null, r.color_family, tr);
    h("td", "num", r.price ? "$" + r.price.toFixed(2) : "—", tr);
    h("td", "num", r.bought ? `${num(r.bought)}+/${r.period}` : "—", tr);
    h("td", null, r.segment, tr); h("td", null, r.badge || "", tr);
    const td = h("td", null, null, tr);
    if (r.url) { const a = h("a", null, r.source, td); a.href = r.url; a.target = "_blank"; a.rel = "noopener"; } else td.textContent = r.source;
  });
  D.gaps.forEach(g => h("li", null, g, $("gaps")));
})();
