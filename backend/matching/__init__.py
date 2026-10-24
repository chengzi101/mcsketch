from backend.errors import AppError

CATEGORIES = {"burger": "汉堡", "fries": "薯条", "icecream": "冰淇淋", "drink": "饮料", "nuggets": "鸡块", "coffee": "咖啡"}
KEYWORDS = {"burger": ["汉堡", "巨无霸", "麦辣鸡腿", "板烧", "麦香鸡", "麦香鱼", "牛堡"], "fries": ["薯条"], "icecream": ["冰淇淋", "圆筒", "新地", "麦旋风"], "drink": ["可乐", "汽水", "饮料", "雪碧", "果汁", "纯悦", "柠檬红茶"], "nuggets": ["鸡块", "麦乐鸡"], "coffee": ["咖啡", "美式", "拿铁", "奶铁"]}

def category_of(name):
    return next((k for k, words in KEYWORDS.items() if any(w in name for w in words)), "unknown")

def match(menu, category):
    if not isinstance(category, str) or category not in CATEGORIES:
        raise AppError("请选择支持的食物类别")
    return [dict(p, reason=f"你确认了{CATEGORIES[category]}，与当前菜单的商品类别一致") for p in menu if p["category"] == category][:3]
