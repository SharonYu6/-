"""爬虫解析函数的离线测试（HTML 片段模拟 Amazon / Wayfair 页面结构）。"""

import json

from amazon_selection_agent.scrapers.amazon import (
    parse_bestsellers_html,
    parse_bought,
    parse_count,
    parse_product_html,
    parse_search_html,
)
from amazon_selection_agent.scrapers.wayfair import extract_pdp_links, parse_product_html as parse_wf

SEARCH = """
<div data-component-type="s-search-result" data-asin="B0AAA00001">
  <span class="puis-sponsored-label-text">Sponsored</span>
  <h2><span>Ad Mirror</span></h2>
  <span class="a-price"><span class="a-offscreen">$39.99</span></span>
</div>
<div data-component-type="s-search-result" data-asin="B0BBB00002">
  <h2><a><span>Wavy Full Length Mirror 63x24, White</span></a></h2>
  <i><span class="a-icon-alt">4.5 out of 5 stars</span></i>
  <a href="/dp/B0BBB00002#customerReviews"><span>1,234</span></a>
  <span>1K+ bought in past month</span>
  <span class="a-price"><span class="a-offscreen">$69.99</span></span>
  <span class="a-price a-text-price"><span class="a-offscreen">$89.99</span></span>
  <img class="s-image" src="https://m.media-amazon.com/x.jpg">
</div>
"""

PDP = """
<span id="productTitle"> Curved 9-Drawer Dresser for Bedroom, 63" Wide, Gray Oak </span>
<a id="bylineInfo">Visit the EliteSet Store</a>
<span id="acrPopover" title="4.4 out of 5 stars"></span>
<span id="acrCustomerReviewText">(206)</span>
<span id="social-proofing-faceout-title-tk_bought">200+ bought in past month</span>
<div id="corePrice_feature_div"><span class="a-offscreen">$382.19</span></div>
<span class="basisPrice"><span class="a-offscreen">$419.99</span></span>
<div id="variation_color_name"><ul>
  <li title="Click to select Gray Oak"></li><li title="Click to select Burl Walnut"></li></ul></div>
<div id="variation_size_name"><ul><li title="Click to select 6-Drawer"></li><li title="Click to select 9-Drawer"></li></ul></div>
<div id="feature-bullets"><ul><li><span class="a-list-item">Curved profile design</span></li></ul></div>
<table id="productOverview_feature_div"><tr><td>Color</td><td>Gray Oak</td></tr><tr><td>Material</td><td>Engineered Wood</td></tr></table>
<table id="productDetails_detailBullets_sections1">
 <tr><th>Best Sellers Rank</th><td>#36,595 in Home &amp; Kitchen (See Top 100) #40 in Sofa Tables</td></tr>
 <tr><th>Date First Available</th><td>March 3, 2026</td></tr></table>
<img id="landingImage" data-old-hires="https://m.media-amazon.com/big.jpg">
<div data-hook="review"><i data-hook="review-star-rating"><span class="a-icon-alt">2.0 out of 5 stars</span></i>
  <a data-hook="review-title"><span>Drawers misaligned</span></a>
  <span data-hook="review-body"><span>Assembly took 3 hours and drawers are off track.</span></span></div>
"""

BESTSELLERS = """
<h1>Best Sellers in Floor &amp; Full Length Mirrors</h1>
<div class="p13n-desktop-grid" data-client-recs-list='[{"id":"B0CCC00003","metadataMap":{"render.zg.rank":"1"}},{"id":"B0DDD00004","metadataMap":{"render.zg.rank":"2"}}]'>
 <div id="gridItemRoot"><span class="zg-bdg-text">#1</span><div data-asin="B0CCC00003">
   <a href="/dp/B0CCC00003"><img alt="DUMOS 64x21 Arched Full Length Mirror" src="a.jpg"></a>
   <i class="a-icon-star-small"><span class="a-icon-alt">4.6 out of 5 stars</span></i>
   <span class="a-size-small">12,345</span><span>$59.99</span></div></div>
 <div id="gridItemRoot"><span class="zg-bdg-text">#2</span><div data-asin="B0DDD00004">
   <a href="/dp/B0DDD00004"><img alt="OLIXIS Arched Mirror" src="b.jpg"></a><span>$45.99</span></div></div>
</div>
"""


def test_number_parsers():
    assert parse_bought("200+ bought in past month") == 200
    assert parse_bought("1K+ bought in past month") == 1000
    assert parse_bought("no badge") is None
    assert parse_count("(206)") == 206
    assert parse_count("2.5K ratings") == 2500


def test_parse_search():
    rows = parse_search_html(SEARCH, "wavy mirror")
    assert [r["sponsored"] for r in rows] == [True, False]
    r = rows[1]
    assert r["organic_rank"] == 1 and r["price"] == 69.99 and r["list_price"] == 89.99
    assert r["rating"] == 4.5 and r["ratings_count"] == 1234 and r["bought_past_month"] == 1000


def test_parse_product():
    p = parse_product_html(PDP, "B0TEST0001")
    assert p["title"].startswith("Curved 9-Drawer Dresser")
    assert p["store"] == "EliteSet Store"
    assert p["price"] == 382.19 and p["list_price"] == 419.99
    assert p["rating"] == 4.4 and p["ratings_count"] == 206 and p["bought_past_month"] == 200
    assert p["variants"]["color"] == ["Gray Oak", "Burl Walnut"]
    assert p["variants"]["size"] == ["6-Drawer", "9-Drawer"]
    assert p["material"] == "Engineered Wood"
    assert p["best_sellers_rank"][0] == {"rank": 36595, "category": "Home & Kitchen"}
    assert {"rank": 40, "category": "Sofa Tables"} in p["best_sellers_rank"]
    assert p["image"].endswith("big.jpg")
    assert p["reviews"][0]["rating"] == 2.0 and "off track" in p["reviews"][0]["body"]


def test_parse_bestsellers():
    rows = parse_bestsellers_html(BESTSELLERS, "Floor Mirrors")
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["title"].startswith("DUMOS") and rows[0]["price"] == 59.99
    assert rows[0]["rating"] == 4.6


def test_wayfair_parsers():
    html = '<a href="/decor-pillows/pdp/wavy-mirror-w001234.html?piid=1">x</a><a href="/decor-pillows/pdp/wavy-mirror-w001234.html">y</a>'
    assert extract_pdp_links(html) == ["https://www.wayfair.com/decor-pillows/pdp/wavy-mirror-w001234.html"]
    ld = {
        "@context": "https://schema.org", "@type": "Product", "name": "Wavy Floor Mirror", "sku": "W001234",
        "brand": {"@type": "Brand", "name": "Wade Logan"},
        "offers": {"@type": "Offer", "price": "129.99"},
        "aggregateRating": {"ratingValue": "4.3", "reviewCount": "88"},
        "review": [{"reviewRating": {"ratingValue": "1"}, "reviewBody": "Arrived shattered", "name": "Broken"}],
    }
    page = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    p = parse_wf(page, "https://www.wayfair.com/x/pdp/wavy-mirror-w001234.html")
    assert p.sku == "W001234" and p.brand == "Wade Logan" and p.price == 129.99
    assert p.rating == 4.3 and p.reviews == 88
    assert p.review_items[0]["body"] == "Arrived shattered"
