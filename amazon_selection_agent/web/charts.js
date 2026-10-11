/* 轻量 SVG 图表：折线（十字准线 + 提示框）、横向条形、纵向柱、发散条形。
 * 无外部依赖。所有文字通过 textContent 写入（数据来自 CSV / 爬虫，不可信）。 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function h(tag, cls, text, parent) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    if (parent) parent.appendChild(n);
    return n;
  }
  const tip = h("div", "viz-tip");
  document.addEventListener("DOMContentLoaded", () => document.body.appendChild(tip));
  function showTip(evt, rows) {
    tip.replaceChildren();
    rows.forEach(([key, val, color]) => {
      const r = h("div", "viz-tip-row", null, tip);
      if (color) { const k = h("span", "viz-tip-key", null, r); k.style.background = color; }
      h("strong", null, val, r);
      h("span", "viz-tip-label", key, r);
    });
    tip.style.display = "block";
    const x = Math.min(evt.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    const y = Math.max(8, evt.clientY - tip.offsetHeight - 10);
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  function hideTip() { tip.style.display = "none"; }

  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }
  function width(container) { return Math.max(280, container.clientWidth || 600); }

  function legend(container, names, kind) {
    if (names.length < 2) return;
    const lg = h("div", "viz-legend", null, container);
    names.forEach((n, i) => {
      const it = h("span", "viz-legend-item", null, lg);
      const sw = h("span", kind === "line" ? "viz-key-line" : "viz-key-rect", null, it);
      sw.style.background = SERIES[i];
      h("span", null, n, it);
    });
  }

  /* 折线：x 为类目标签数组，series=[{name, values}]，单一 y 轴 */
  function line(container, x, series, fmt) {
    container.replaceChildren();
    legend(container, series.map(s => s.name), "line");
    const W = width(container), H = 240, m = { l: 56, r: 16, t: 12, b: 28 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "viz-svg", role: "img" }, container);
    const max = niceMax(Math.max(...series.flatMap(s => s.values.filter(v => v != null))));
    const xs = i => m.l + (i * (W - m.l - m.r)) / Math.max(1, x.length - 1);
    const ys = v => H - m.b - (v / max) * (H - m.t - m.b);
    for (let k = 0; k <= 4; k++) {
      const v = (max * k) / 4, y = ys(v);
      el("line", { x1: m.l, x2: W - m.r, y1: y, y2: y, class: k ? "viz-grid" : "viz-axis" }, svg);
      el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", class: "viz-tick" }, svg).textContent = fmt(v);
    }
    const step = Math.ceil(x.length / Math.floor((W - m.l) / 70));
    x.forEach((lab, i) => {
      if (i % step === 0 || i === x.length - 1)
        el("text", { x: xs(i), y: H - 8, "text-anchor": "middle", class: "viz-tick" }, svg).textContent = lab;
    });
    series.forEach((s, si) => {
      const d = s.values.map((v, i) => (v == null ? "" : `${i && s.values[i - 1] != null ? "L" : "M"}${xs(i)},${ys(v)}`)).join("");
      el("path", { d, fill: "none", stroke: SERIES[si], "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      const li = s.values.length - 1;
      el("circle", { cx: xs(li), cy: ys(s.values[li]), r: 4, fill: SERIES[si], stroke: "var(--surface-1)", "stroke-width": 2 }, svg);
    });
    const cross = el("line", { y1: m.t, y2: H - m.b, class: "viz-cross", visibility: "hidden" }, svg);
    const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent", tabindex: 0 }, svg);
    const move = evt => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      const i = Math.max(0, Math.min(x.length - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (x.length - 1))));
      cross.setAttribute("x1", xs(i)); cross.setAttribute("x2", xs(i)); cross.setAttribute("visibility", "visible");
      showTip(evt, [[x[i], "", null], ...series.map((s, si) => [s.name, fmt(s.values[i]), SERIES[si]])]);
    };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
    table(container, ["月份", ...series.map(s => s.name)], x.map((lab, i) => [lab, ...series.map(s => fmt(s.values[i]))]));
  }

  /* 横向条形：rows=[{label, value, note}] */
  function hbar(container, rows, fmt, opts = {}) {
    container.replaceChildren();
    if (!rows.length) { h("p", "muted", "无数据", container); return; }
    const max = opts.max || Math.max(...rows.map(r => r.value)) || 1;
    const list = h("div", "hbar", null, container);
    rows.forEach(r => {
      const row = h("div", "hbar-row" + (r.highlight ? " is-hi" : ""), null, list);
      row.tabIndex = 0;
      h("div", "hbar-label", r.label, row);
      const track = h("div", "hbar-track", null, row);
      const bar = h("div", "hbar-bar", null, track);
      bar.style.width = Math.max(0.5, (100 * r.value) / max) + "%";
      if (r.color) bar.style.background = r.color;
      h("div", "hbar-value", fmt(r.value), row);
      if (r.note !== undefined) h("div", "hbar-note", r.note, row);
      const tipRows = [[r.label, fmt(r.value), null]].concat(r.tip || []);
      row.addEventListener("pointermove", e => showTip(e, tipRows));
      row.addEventListener("pointerleave", hideTip);
      row.addEventListener("focus", () => { const b = row.getBoundingClientRect(); showTip({ clientX: b.left + 120, clientY: b.top }, tipRows); });
      row.addEventListener("blur", hideTip);
    });
  }

  /* 纵向柱：labels, values；highlight 索引集合 */
  function columns(container, labels, values, fmt, highlight = []) {
    container.replaceChildren();
    const W = width(container), H = 200, m = { l: 44, r: 8, t: 18, b: 26 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, class: "viz-svg" }, container);
    const max = niceMax(Math.max(...values));
    const bw = (W - m.l - m.r) / labels.length;
    const ys = v => H - m.b - (v / max) * (H - m.t - m.b);
    for (let k = 0; k <= 4; k++) {
      const v = (max * k) / 4;
      el("line", { x1: m.l, x2: W - m.r, y1: ys(v), y2: ys(v), class: k ? "viz-grid" : "viz-axis" }, svg);
      el("text", { x: m.l - 6, y: ys(v) + 4, "text-anchor": "end", class: "viz-tick" }, svg).textContent = fmt(v);
    }
    labels.forEach((lab, i) => {
      const x = m.l + i * bw + 1, y = ys(values[i]), hgt = H - m.b - y;
      const g = el("g", { tabindex: 0 }, svg);
      el("rect", { x: m.l + i * bw, y: m.t, width: bw, height: H - m.t - m.b, fill: "transparent" }, g);
      el("path", { d: roundTop(x, y, bw - 2, hgt, Math.min(4, (bw - 2) / 2)), class: highlight.includes(i) ? "col col-hi" : "col" }, g);
      if (highlight.includes(i))
        el("text", { x: x + (bw - 2) / 2, y: y - 5, "text-anchor": "middle", class: "viz-label" }, svg).textContent = fmt(values[i]);
      el("text", { x: x + (bw - 2) / 2, y: H - 8, "text-anchor": "middle", class: "viz-tick" }, svg).textContent = lab;
      g.addEventListener("pointermove", e => showTip(e, [[lab, fmt(values[i]), null]]));
      g.addEventListener("pointerleave", hideTip);
    });
    table(container, ["", "值"], labels.map((l, i) => [l, fmt(values[i])]));
  }
  function roundTop(x, y, w, hgt, r) {
    if (hgt <= 0) return "";
    r = Math.min(r, hgt);
    return `M${x},${y + hgt}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + hgt}Z`;
  }

  /* 发散条形：正值蓝（需求 > 供给），负值红 */
  function diverging(container, rows, fmt) {
    container.replaceChildren();
    const max = Math.max(...rows.map(r => Math.abs(r.value))) || 1;
    const list = h("div", "dbar", null, container);
    rows.forEach(r => {
      const row = h("div", "dbar-row", null, list);
      h("div", "hbar-label", r.label, row);
      const track = h("div", "dbar-track", null, row);
      h("div", "dbar-mid", null, track);
      const bar = h("div", "dbar-bar " + (r.value >= 0 ? "pos" : "neg"), null, track);
      const pct = (50 * Math.abs(r.value)) / max;
      bar.style.width = pct + "%";
      bar.style.left = r.value >= 0 ? "50%" : 50 - pct + "%";
      h("div", "hbar-value", fmt(r.value), row);
      row.addEventListener("pointermove", e => showTip(e, [[r.label, fmt(r.value), null]].concat(r.tip || [])));
      row.addEventListener("pointerleave", hideTip);
    });
  }

  function table(container, head, rows) {
    const d = h("details", "viz-table", null, container);
    h("summary", null, "表格视图", d);
    const t = h("table", null, null, d);
    const tr = h("tr", null, null, h("thead", null, null, t));
    head.forEach(c => h("th", null, c, tr));
    const tb = h("tbody", null, null, t);
    rows.forEach(r => { const row = h("tr", null, null, tb); r.forEach(c => h("td", null, c == null ? "—" : String(c), row)); });
  }

  window.Viz = { line, hbar, columns, diverging, table, h };
})();
