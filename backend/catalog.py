"""Demo fixtures are deliberately fictional, never advertised as official prices."""
from copy import deepcopy

def demo_menu():
    rows = [
        ("b1", "双层牛肉堡", "burger", 2300, 520, 26, 27, ["beef", "milk", "gluten"]),
        ("b2", "经典鸡肉堡", "burger", 1600, 430, 20, 19, ["chicken", "gluten"]),
        ("b3", "迷你牛肉堡", "burger", 1100, 300, 15, 13, ["beef", "gluten"]),
        ("f1", "金黄薯条 · 大份", "fries", 1500, 420, 5, 20, []),
        ("f2", "金黄薯条 · 小份", "fries", 800, 220, 3, 10, []),
        ("i1", "香草冰淇淋", "icecream", 900, 180, 4, 5, ["milk"]),
        ("i2", "迷你香草杯", "icecream", 600, 110, 2, 3, ["milk"]),
        ("d1", "气泡可乐 · 中杯", "drink", 1000, 150, 0, 0, []),
        ("d2", "无糖气泡饮", "drink", 600, 0, 0, 0, []),
        ("n1", "金酥鸡块 · 六块", "nuggets", 1500, 280, 17, 17, ["chicken", "gluten"]),
        ("n2", "金酥鸡块 · 四块", "nuggets", 1000, 190, 11, 11, ["chicken", "gluten"]),
        ("c1", "拿铁咖啡", "coffee", 1500, 150, 7, 8, ["milk", "caffeine"]),
        ("c2", "黑咖啡", "coffee", 900, None, None, None, ["caffeine"]),
    ]
    return deepcopy([dict(id=i, name=n, category=c, price_cents=p, kcal=k, protein=pr, fat=f, tags=t, allergens_verified=True, source="demo", nutrition_source="demo", price_verified=False) for i,n,c,p,k,pr,f,t in rows])
