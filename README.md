# Amazon 家居选品 Agent

从关键词、趋势、竞品、评论和费用数据出发，回答以下问题：

- **市场容量 / 需求趋势**：这个类目在增长还是下滑？季节性怎样？黑五有没有爆发？
- **需求拆解**：关键词里的场景词（small space、dorm、apartment、no drill）对应什么人群？哪种颜色、款式（如波浪纹）、尺寸在涨？
- **用户分层**：每层人群的规模、价格带、场景、颜色偏好、痛点和爽点
- **竞争 & 胜率价位**：品牌集中度、新品机会、价格带胜率、供需差（有需求但供给不足的属性）
- **VOC**：差评痛点对应的改进点，好评爽点对应的卖点
- **ROI**：佣金、FBA 大件费、广告、退货都算进去后的单件利润、ROI、盈亏平衡 ACoS，以及达到 20% 净利的目标出厂价
- **产品方案 & 类目深耕**：爆款规格、定价、上新节奏、产品线规划

输出是可以直接打开或部署的**单文件可视化网站**。

## 两个输出页面

| 页面 | 数据 | 生成方式 |
|---|---|---|
| `output/research_report.html` | **真实数据**：Adobe/NRF 等机构数据、Amazon 公开页面信号（bought in past month、榜单、价格）、商品页截图。每条结论都标注来源和可信度 | `python -m amazon_selection_agent research research/home_mirror_curved_2026-10.json` |
| `output/demo_dashboard.html` | **演示数据**（`scripts/make_demo_data.py` 模拟生成），用来展示接入真实导出后的完整量化看板 | `python -m amazon_selection_agent analyze sample_data/demo_mirror --demo` |

## 安装

```bash
pip install -r requirements.txt
playwright install chromium        # 只有采集 Amazon / Wayfair 时需要
```

## 采集真实数据

需要在能访问 amazon.com 的电脑上运行（云端容器通常会被拦截）：

```bash
# 1) Amazon：联想词 + 每个词的搜索页 + Best Sellers 榜单 + Top 详情页（含评论）
python -m amazon_selection_agent amazon-collect "wavy mirror" "full length mirror small space" "curved dresser" "console table" \
    --bestsellers https://www.amazon.com/Best-Sellers-Floor-Full-Length-Mirrors/zgbs/home-garden/3736381 \
                  https://www.amazon.com/Best-Sellers-Dressers-Chests-of-Drawers/zgbs/home-garden/3733261 \
    --max-keywords 30 --max-products 40 --out data/amazon_home

# 浏览器会以有头模式打开；出现验证码时手动完成，然后回车继续。
# 抓到的页面原文保存在 data/amazon_home/html/，之后可以离线重新解析。

# 2) 也可以手动在浏览器里另存页面（Ctrl+S），按 search_<词>.html / bestsellers_<名>.html / dp_<ASIN>.html 命名后解析
python -m amazon_selection_agent amazon-parse ~/Downloads/amazon_pages --out data/amazon_saved

# 3) Google Trends（5 年月度）
python -m amazon_selection_agent google-trends "wavy mirror" "arched mirror" "curved dresser" --out data/amazon_home/google_trends.csv

# 4) Wayfair 竞品 & 评论（会合并进同一个目录，platform=wayfair）
python -m amazon_selection_agent scrape-wayfair "wavy mirror" --pages 2 --out data/amazon_home
```

Amazon 不公开月搜索量。爬虫生成的 `keywords.csv` 用"搜索首页自然位 bought in past month 合计"作为需求代理，页面上会标注这个口径。如果需要精确的搜索量和同比，请从卖家精灵、Helium 10 或 Brand Analytics 导出，列名改成 `keyword, search_volume, search_volume_last_year` 放进同一目录，导出数据会覆盖代理值。

## 分析 + 网站

```bash
python -m amazon_selection_agent analyze data/amazon_home --out output/amazon_home
# → output/amazon_home/dashboard.html（用浏览器打开）和 analysis.json
```

### 数据文件格式（缺哪个就跳过对应模块）

| 文件 | 必需列 | 可选列 |
|---|---|---|
| `keywords.csv` | `keyword` + (`search_volume` 或 `demand_proxy`) | `search_volume_last_year` / `growth_yoy` |
| `category_monthly.csv` | `month` (YYYY-MM) | `search_volume`, `units_sold`, `revenue` |
| `google_trends.csv` | `month` | 每个词一列（0–100） |
| `competitors.csv` | `asin`, `price` | `title`, `brand`, `monthly_sales`, `reviews`, `rating`, `launch_date`, `platform` |
| `reviews.csv` | `rating`, `body` | `asin`, `title` |

## Claude Agent

把各分析模块作为工具交给 Claude，由 Claude 交叉验证数据，写出完整的中文选品报告（市场、分层、胜率价位、VOC、产品方案、ROI、深耕、风险）：

```bash
export ANTHROPIC_API_KEY=...
python -m amazon_selection_agent agent data/amazon_home --web --out output/report.md
```

`--web` 会开启 Anthropic 服务器端的 web search / web fetch，在本地拿不到数据时可以查公开资料。

## 修改词典

颜色、款式、场景、VOC 主题、改进建议都在 `amazon_selection_agent/lexicon.py` 里，是普通的 dict，换类目时直接增删词即可，不需要改代码。

## 项目结构

```
amazon_selection_agent/
  analyzers/   keywords · trends · competition（胜率价位/供需差/深耕评分）· voc · product · roi
  scrapers/    amazon（联想词/搜索/榜单/详情页）· wayfair（JSON-LD）
  web/         单文件网站模板（无外部依赖，支持深色模式和手机）
  agent.py     Claude tool-runner 编排
  cli.py       命令行
research/      网页检索得到的真实数据（带来源）
sample_data/   演示数据
tests/         pytest
```

## 测试

```bash
python -m pytest -q
```
