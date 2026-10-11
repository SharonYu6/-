"""单品利润 & ROI 测算（Amazon FBA）。

费用口径（2026，需用 Seller Central 的 FBA Revenue Calculator 校准）：
- 佣金：Home & Kitchen 15%；Furniture 类目 $200 以内 15%、超出部分 10%
- FBA 配送费：按尺寸分段。大件（Large bulky，最长边约 37–59 英寸）基础费约 $9.35 + $0.38/磅；
  最长边超过 59 英寸进入 Extra-large，费用明显更高——全身镜 64" vs 59" 的尺寸选择会直接影响利润
- 广告：Amazon 平台平均 ACoS 约 28–32%（第三方统计）；这里用 TACoS（广告费 / 总销售额）估算
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class UnitInputs:
    price: float                 # 售价
    cogs: float                  # 出厂价（FOB）
    freight: float               # 头程（海运 + 清关 + 入仓）每件
    fba_fee: float               # FBA 配送费每件
    referral_rate: float = 0.15  # 佣金比例
    furniture_tiered: bool = False  # True: $200 以内 15%、以上 10%
    tacos: float = 0.15          # 广告费占销售额
    return_rate: float = 0.05    # 退货率（按售价全损估算，偏保守）
    storage_other: float = 1.0   # 仓储 + 其他每件
    monthly_units: int = 300     # 预计月销量（用于月利润）


def referral_fee(price: float, rate: float = 0.15, furniture_tiered: bool = False) -> float:
    if furniture_tiered:
        return 0.15 * min(price, 200) + 0.10 * max(price - 200, 0)
    return max(0.30, rate * price)


def unit_economics(inp: UnitInputs) -> dict:
    ref = referral_fee(inp.price, inp.referral_rate, inp.furniture_tiered)
    ads = inp.tacos * inp.price
    returns = inp.return_rate * inp.price
    landed = inp.cogs + inp.freight
    total_cost = landed + inp.fba_fee + ref + ads + returns + inp.storage_other
    profit = inp.price - total_cost
    margin = profit / inp.price if inp.price else 0.0
    roi = profit / landed if landed else 0.0
    # 盈亏平衡 ACoS：所有非广告成本扣完后剩下的部分
    pre_ad_profit = profit + ads
    breakeven_acos = pre_ad_profit / inp.price if inp.price else 0.0
    # 达到目标净利率 20% 时允许的最高出厂价（倒推给工厂议价用）
    target_cogs = inp.price * 0.8 - (inp.freight + inp.fba_fee + ref + ads + returns + inp.storage_other)
    return {
        "inputs": asdict(inp),
        "target_cogs_for_20pct_margin": round(target_cogs, 2),
        "referral_fee": round(ref, 2),
        "ads": round(ads, 2),
        "returns": round(returns, 2),
        "landed_cost": round(landed, 2),
        "profit_per_unit": round(profit, 2),
        "net_margin": round(margin, 4),
        "roi": round(roi, 4),
        "breakeven_acos": round(breakeven_acos, 4),
        "monthly_profit": round(profit * inp.monthly_units, 0),
        "verdict": _verdict(margin, roi),
    }


def _verdict(margin: float, roi: float) -> str:
    if margin >= 0.20 and roi >= 0.8:
        return "健康：净利率 ≥20%、ROI ≥80%，可以做"
    if margin >= 0.12:
        return "可做但偏薄：需要控制广告和退货"
    if margin > 0:
        return "利润太薄：提价、降本或换尺寸档位"
    return "亏损：当前假设下不成立"
