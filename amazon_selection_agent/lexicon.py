"""家居类目属性词典。

关键词 / 标题 / 评论里出现的英文词 -> 属性维度 -> 中文标签。
词典刻意写成普通 dict，方便运营直接增删，不需要改分析逻辑。
匹配规则：小写后做整词匹配（支持多词短语），见 analyzers/keywords.py。
"""

# 应用场景 / 空间：small space、dorm 这类词直接指向用户人群
SCENE = {
    "小空间": ["small space", "small spaces", "small apartment", "tiny", "compact", "narrow", "space saving", "slim"],
    "宿舍": ["dorm", "dorm room", "college", "university"],
    "租房": ["renter", "renters", "rental", "apartment", "no drill", "no drilling", "damage free", "renter friendly"],
    "卧室": ["bedroom", "bed room"],
    "客厅": ["living room", "entryway", "hallway", "foyer"],
    "浴室": ["bathroom", "vanity", "shower"],
    "儿童房": ["kids", "nursery", "playroom", "children", "toddler"],
    "办公": ["office", "desk", "workspace", "home office"],
    "门后/挂门": ["over the door", "door", "hanging"],
    "衣帽间": ["closet", "dressing", "wardrobe"],
    "厨房": ["kitchen", "pantry"],
}

# 场景 -> 用户画像推断
SCENE_TO_PERSONA = {
    "小空间": "城市小户型/租房年轻人",
    "宿舍": "大学生（Back to School 季）",
    "租房": "租房族（不能打孔、搬家频繁）",
    "儿童房": "宝妈/有孩家庭",
    "办公": "居家办公白领",
    "门后/挂门": "空间受限的租房族/学生",
    "衣帽间": "注重穿搭的年轻女性",
    "卧室": "大众家庭用户",
    "客厅": "注重装饰的有房家庭",
    "浴室": "大众家庭用户",
    "厨房": "大众家庭用户",
}

COLOR = {
    "白色": ["white"],
    "黑色": ["black"],
    "奶油色": ["cream", "ivory", "off white", "beige"],
    "金色": ["gold", "brass"],
    "银色": ["silver", "chrome"],
    "原木色": ["wood", "wooden", "natural", "oak", "walnut"],
    "粉色": ["pink", "blush"],
    "绿色": ["green", "sage", "olive"],
    "蓝色": ["blue", "navy"],
    "灰色": ["grey", "gray"],
    "透明/亚克力": ["clear", "acrylic", "transparent"],
}

PATTERN_SHAPE = {
    "波浪纹": ["wavy", "wave", "squiggle", "ripple", "curvy"],
    "拱形": ["arch", "arched"],
    "圆形": ["round", "circle", "circular"],
    "不规则": ["irregular", "asymmetrical", "asymmetric", "organic", "cloud"],
    "长方形": ["rectangle", "rectangular"],
    "椭圆": ["oval"],
    "格纹/棋盘": ["checkered", "checkerboard", "plaid", "gingham"],
    "藤编": ["rattan", "wicker", "woven"],
}

STYLE = {
    "ins风/Danish Pastel": ["aesthetic", "danish pastel", "pastel", "cute", "preppy"],
    "复古": ["vintage", "retro", "antique"],
    "现代简约": ["modern", "minimalist", "minimal", "simple"],
    "波西米亚": ["boho", "bohemian"],
    "中古/Mid-century": ["mid century", "mid-century", "mcm"],
    "农舍风": ["farmhouse", "rustic"],
    "奶油风": ["cream", "creamy", "neutral"],
}

MATERIAL = {
    "实木": ["solid wood", "wood", "wooden", "pine", "bamboo"],
    "金属": ["metal", "iron", "aluminum", "aluminium", "steel"],
    "塑料/树脂": ["plastic", "resin", "pvc", "pu"],
    "玻璃": ["glass", "shatterproof", "tempered"],
    "布艺": ["fabric", "linen", "velvet", "boucle"],
}

# 尺寸：关键词中的英寸写法单独用正则解析，这里是定性词
SIZE_WORDS = {
    "全身/大号": ["full length", "full body", "floor", "large", "big", "oversized", "tall", "standing"],
    "小号/桌面": ["small", "mini", "tabletop", "desk", "handheld"],
    "中号": ["medium"],
}

# 功能卖点
FEATURE = {
    "带灯/LED": ["led", "lighted", "light up", "with lights"],
    "免打孔": ["no drill", "no drilling", "adhesive", "stick on", "damage free"],
    "可折叠/可收纳": ["foldable", "collapsible", "folding", "stackable"],
    "带置物/收纳": ["with storage", "with shelves", "with shelf", "organizer", "storage"],
    "防爆/安全": ["shatterproof", "shatter proof", "safety", "unbreakable"],
    "可移动/带轮": ["rolling", "with wheels", "portable", "movable"],
}

ATTRIBUTE_DIMENSIONS = {
    "scene": SCENE,
    "color": COLOR,
    "pattern_shape": PATTERN_SHAPE,
    "style": STYLE,
    "material": MATERIAL,
    "size": SIZE_WORDS,
    "feature": FEATURE,
}

DIMENSION_LABELS = {
    "scene": "应用场景",
    "color": "颜色",
    "pattern_shape": "款式/形状/纹理",
    "style": "风格",
    "material": "材质",
    "size": "尺寸",
    "feature": "功能卖点",
}

# VOC 主题：评论中提到即计数；在差评（<=3 星）中的占比即"痛点强度"
VOC_THEMES = {
    "破损/运输": ["broken", "shattered", "cracked", "arrived damaged", "damaged", "chipped", "packaging", "shipping"],
    "安装难": ["hard to install", "difficult to assemble", "instructions", "assembly", "screws", "hardware", "install", "mount", "mounting"],
    "不稳/易倒": ["wobbly", "wobble", "tip over", "tipped", "fell", "unstable", "flimsy", "falls"],
    "成像变形": ["distorted", "distortion", "warped", "funhouse", "blurry", "not clear"],
    "尺寸不符": ["smaller than", "bigger than", "too small", "too big", "size is off", "not as described", "dimensions"],
    "颜色不符": ["color is off", "different color", "looks yellow", "not white", "color was", "color difference"],
    "做工/质感差": ["cheap", "cheaply made", "plastic", "flimsy", "poor quality", "rough edges", "peeling", "scratched"],
    "气味": ["smell", "odor", "smells"],
    "粘胶/挂钩失效": ["adhesive", "fell off", "won't stick", "doesn't stick", "hooks", "strips"],
    "颜值/好看": ["beautiful", "gorgeous", "cute", "aesthetic", "love the look", "stylish", "pretty"],
    "性价比": ["worth", "value", "price", "affordable", "for the price"],
    "适合小空间": ["small space", "small apartment", "dorm", "fits perfectly", "perfect size", "compact"],
}

# 主题 -> 产品改进建议
VOC_IMPROVEMENT = {
    "破损/运输": "升级包装：EPE 珍珠棉 + 护角 + 蜂窝纸板，做 ISTA-6A 跌落测试；镜面可改防爆膜/亚克力镜",
    "安装难": "免工具/卡扣安装，附视频二维码；挂墙 + 落地 + 挂门三合一配件",
    "不稳/易倒": "加宽支脚、加防倾倒墙绳、底部防滑垫",
    "成像变形": "提高镜面平整度（4mm+ 银镜或 HD 玻璃），背板加加强筋",
    "尺寸不符": "主图标注真实尺寸与人物比例参照图，Listing 写清楚英寸/厘米",
    "颜色不符": "主图实拍校色，补充自然光场景图，颜色命名与实物一致",
    "做工/质感差": "提升边框材质（实木/金属替代 PS 塑料），边缘打磨工艺",
    "气味": "选用低 VOC 材料，出厂前散味，Listing 说明无味",
    "粘胶/挂钩失效": "升级 3M 胶条 / 加金属挂钩双保险，并说明可承重数据",
}
