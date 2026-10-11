/* 交互式 ROI 计算器（与 analyzers/roi.py 同一公式）。
 * Viz.roi(container, scenarios) ; scenarios = [{name, price, cogs, freight, fba_fee, referral_rate, furniture_tiered, tacos, return_rate, storage_other, monthly_units, note}] */
(function () {
  const { h } = Viz;
  const FIELDS = [
    ["price", "售价 $", 0.01],
    ["cogs", "出厂价 FOB $", 0.1],
    ["freight", "头程/件 $", 0.1],
    ["fba_fee", "FBA 配送费 $", 0.1],
    ["tacos", "广告占销售额 %", 1, true],
    ["return_rate", "退货率 %", 1, true],
    ["storage_other", "仓储+其他/件 $", 0.1],
    ["monthly_units", "预计月销量", 10],
  ];
  function referral(p, rate, tiered) { return tiered ? 0.15 * Math.min(p, 200) + 0.10 * Math.max(p - 200, 0) : Math.max(0.3, rate * p); }
  function calc(s) {
    const ref = referral(s.price, s.referral_rate, s.furniture_tiered);
    const ads = s.tacos * s.price, ret = s.return_rate * s.price, landed = s.cogs + s.freight;
    const profit = s.price - (landed + s.fba_fee + ref + ads + ret + s.storage_other);
    const target = s.price * 0.8 - (s.freight + s.fba_fee + ref + ads + ret + s.storage_other);
    return { ref, ads, ret, landed, profit, margin: profit / s.price, roi: profit / landed, be: (profit + ads) / s.price, month: profit * s.monthly_units, target };
  }
  const money = v => (v < 0 ? "-$" : "$") + Math.abs(v).toFixed(2);
  const pct = v => (v * 100).toFixed(0) + "%";

  function roi(container, scenarios) {
    container.replaceChildren();
    const tabs = h("div", "tabs", null, container);
    const body = h("div", "roi-body", null, container);
    let cur = 0;
    const state = scenarios.map(s => Object.assign({}, s));
    function render() {
      [...tabs.children].forEach((b, i) => b.setAttribute("aria-selected", i === cur));
      body.replaceChildren();
      const s = state[cur];
      const grid = h("div", "roi-grid", null, body);
      const form = h("div", "roi-form", null, grid);
      const out = h("div", "roi-out", null, grid);
      FIELDS.forEach(([k, label, step, isPct]) => {
        const row = h("label", "roi-field", null, form);
        h("span", null, label, row);
        const inp = h("input", null, null, row);
        inp.type = "number"; inp.step = step; inp.min = 0;
        inp.value = isPct ? Math.round(s[k] * 100) : s[k];
        inp.addEventListener("input", () => { const v = parseFloat(inp.value) || 0; s[k] = isPct ? v / 100 : v; update(); });
      });
      if (s.note) h("p", "src", s.note, form);
      const kp = h("div", "roi-kpis", null, out);
      const tiles = ["单件利润", "净利率", "ROI", "盈亏平衡 ACoS", "月利润", "20% 净利目标出厂价"].map(l => { const t = h("div", "kpi", null, kp); h("div", "l", l, t); return h("div", "v", "", t); });
      const verdict = h("p", "roi-verdict", "", out);
      const tbl = h("table", null, null, out);
      function update() {
        const r = calc(s);
        tiles[0].textContent = money(r.profit);
        tiles[1].textContent = pct(r.margin);
        tiles[2].textContent = pct(r.roi);
        tiles[3].textContent = pct(r.be);
        tiles[4].textContent = money(r.month).replace(".00", "");
        tiles[5].textContent = money(r.target);
        verdict.textContent = r.margin >= 0.2 && r.roi >= 0.8 ? "✓ 健康：净利率 ≥20%、ROI ≥80%" : r.margin >= 0.12 ? "△ 可做但偏薄：控制广告与退货" : r.margin > 0 ? "! 利润太薄：提价、降本或换尺寸档位" : "✕ 当前假设下亏损";
        tbl.replaceChildren();
        [["售价", s.price], ["佣金", -r.ref], ["FBA 配送", -s.fba_fee], ["广告", -r.ads], ["退货损失", -r.ret], ["仓储/其他", -s.storage_other], ["出厂价", -s.cogs], ["头程", -s.freight], ["单件利润", r.profit]]
          .forEach(([l, v]) => { const tr = h("tr", null, null, tbl); h("td", null, l, tr); h("td", "num", money(v), tr); });
      }
      update();
    }
    scenarios.forEach((s, i) => { const b = h("button", null, s.name, tabs); b.type = "button"; b.onclick = () => { cur = i; render(); }; });
    render();
  }
  Viz.roi = roi;
})();
