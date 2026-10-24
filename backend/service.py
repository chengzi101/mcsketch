import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from backend.catalog import demo_menu
from backend.errors import AppError
from backend.matching import category_of
from backend.mcp_client import LiveGateway, path_get

def integer(value, name, low=0, high=100000):
    if type(value) is not int or not low <= value <= high:
        raise AppError(f"{name}须为 {low}–{high} 之间的整数")
    return value

def cents(value, unit):
    if unit not in {"yuan", "cents"}:
        raise AppError("金额单位必须明确为 yuan 或 cents", "schema_drift",502)
    try:
        d = Decimal(str(value)) * (100 if unit == "yuan" else 1)
        if not d.is_finite() or d < 0 or d != d.to_integral_value():
            raise ValueError
        return int(d)
    except (InvalidOperation, ValueError, TypeError):
        raise AppError("官方金额不可解析，请核对金额字段和单位", "schema_drift", 502) from None

def fingerprint(mode, store, cart):
    return hashlib.sha256(json.dumps([mode,store,sorted(cart.items())], ensure_ascii=False).encode()).hexdigest()[:16]

def live_rows(data, path):
    rows = path_get(data,path)
    if not isinstance(rows,list) or any(not isinstance(x,dict) for x in rows):
        raise AppError("官方数据中的列表结构无法映射", "schema_drift",502)
    return rows

def live_id(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)) or not str(value).strip():
        raise AppError("官方记录缺少有效 ID，未生成替代 ID", "schema_drift",502)
    return str(value)

def live_name(value):
    if not isinstance(value,str) or not value.strip():
        raise AppError("官方记录缺少有效名称，未生成替代名称", "schema_drift",502)
    return value

class MealService:
    def __init__(self, live=None):
        self.live = live or LiveGateway()

    def stores(self, mode, address):
        if mode == "demo":
            return [dict(id="demo-studio", name="灵感餐厅 · 演示门店", address="虚拟门店，仅供本地体验")]
        data, spec = self.live.execute("stores", dict(address=address))
        try:
            return [dict(id=live_id(path_get(x,spec["id"])), name=live_name(path_get(x,spec["name"])), address=path_get(x,spec["address"]) or "地址未提供") for x in live_rows(data,spec["items"])]
        except (KeyError, TypeError, IndexError, ValueError, AttributeError):
            raise AppError("门店数据映射失效", "schema_drift", 502) from None

    def menu(self, mode, store):
        if mode == "demo":
            if store != "demo-studio":
                raise AppError("请选择演示门店")
            return demo_menu()
        if not store:
            raise AppError("请先选择门店")
        data, spec = self.live.execute("menu", dict(store_id=store))
        try:
            result = []
            for x in live_rows(data, spec["items"]):
                name = live_name(path_get(x,spec["name"]))
                p = dict(id=live_id(path_get(x,spec["id"])), name=name, category=x.get('visualCategory',category_of(name)), source="live", price_verified=False, price_cents=None, kcal=None, protein=None, fat=None, tags=[], allergens_verified=False, nutrition_source="missing")
                if spec.get("price"):
                    raw_price=path_get(x,spec["price"])
                    p["price_cents"] = None if raw_price is None or raw_price=="" else cents(raw_price,spec["price_unit"])
                result.append(p)
            if len({p["id"] for p in result}) != len(result):
                raise AppError("菜单 ID 重复，请先映射唯一商品规格；未合并不同商品", "schema_drift",502)
            return result
        except (KeyError, TypeError, IndexError, ValueError, AttributeError):
            raise AppError("菜单数据映射失效", "schema_drift", 502) from None

    def enrich(self, product, store):
        updated = dict(product)
        config = self.live.config()
        try:
            if config.get("detail"):
                data, spec = self.live.execute("detail", dict(store_id=store, product_id=product["id"]))
                if self.live.uses_official_defaults():
                    from backend.mcp_client.official import detail_metadata
                    updated.update(detail_metadata(data['data']))
                if spec.get("tags"):
                    tags = path_get(data,spec["tags"])
                    valid = isinstance(tags,list) and all(isinstance(t,str) and t in {"milk","beef","chicken","gluten","caffeine"} for t in tags)
                    updated["tags"] = tags if valid else []
                    updated["allergens_verified"] = valid
            if not config.get("nutrition"):
                return updated
            nutrition, ns = self.live.execute("nutrition", dict(store_id=store, product_id=product["id"], product_name=product["name"]))
            # Configuration must identify an exact matching nutrition row; never fuzzy join.
            rows = live_rows(nutrition, ns["items"])
            target_name=updated.get('nutrition_name',product['name'])
            row = next((x for x in rows if str(path_get(x,ns["name"])) == target_name), None)
            if row:
                for field in ("kcal", "protein", "fat"):
                    if ns.get(field):
                        raw = path_get(row,ns[field])
                        if raw is not None:
                            if isinstance(raw,bool):
                                raise ValueError
                            number = float(raw)
                            if not math.isfinite(number) or number < 0:
                                raise ValueError
                            updated[field] = number
                updated["nutrition_source"] = "official_exact_name"
            return updated
        except (KeyError, TypeError, IndexError, ValueError):
            raise AppError("详情或营养字段映射失效", "schema_drift", 502) from None

    def cart(self, rows, menu):
        if not isinstance(rows, list) or not 1 <= len(rows) <= 12:
            raise AppError("购物车需要 1–12 种餐品")
        known, cart = {p["id"] for p in menu}, {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"),str) or row.get("id") not in known:
                raise AppError("购物车含当前门店不存在的商品")
            qty = integer(row.get("qty"), "数量",1,6)
            cart[row["id"]] = cart.get(row["id"],0) + qty
        if sum(cart.values()) > 6:
            raise AppError("首版每次最多推荐 6 份餐品")
        return cart

    def quote(self, mode, store, cart, menu):
        by_id = {p["id"]:p for p in menu}
        if mode == "demo":
            amount = sum(by_id[i]["price_cents"]*q for i,q in cart.items())
        else:
            data, spec = self.live.execute("quote", dict(store_id=store, items=[dict(id=i,qty=q) for i,q in sorted(cart.items())]))
            try:
                amount = cents(path_get(data,spec["amount"]),spec["amount_unit"])
            except (KeyError, IndexError, TypeError):
                raise AppError("核价返回结构变化，未生成报价", "schema_drift",502) from None
        return dict(amount_cents=amount, source=mode, official=mode == "live", fingerprint=fingerprint(mode,store,cart), created_at=datetime.now(timezone.utc).isoformat(), expires_in_seconds=120, message="官方核价，以官方实时渠道为准" if mode == "live" else "样例金额 · 非官方售价")
