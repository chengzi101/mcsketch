"""Bounded, deterministic exhaustive search. Hard locks != soft favorites."""
from collections import Counter
from itertools import product
from math import prod
from time import monotonic
from backend.errors import AppError
from backend.service import integer

def repair(service, mode, store, cart, menu, options):
    budget = integer(options.get("budget_cents"), "预算（分）", 0,100000)
    locked = options.get("locked_ids", [])
    favorites = options.get("favorite_ids", [])
    avoid = options.get("avoid", [])
    if not all(isinstance(v,list) and all(isinstance(x,str) for x in v) for v in [locked,favorites,avoid]):
        raise AppError("约束参数格式错误")
    if not set(locked+favorites) <= set(cart) or not set(avoid) <= {"milk","beef","chicken","gluten","caffeine"}:
        raise AppError("约束包含未知商品或忌口")
    max_kcal = options.get("max_kcal")
    if max_kcal is not None:
        integer(max_kcal, "热量上限", 1,10000)
    by_id = {p["id"]:p for p in menu}
    def allowed(p):
        return (not avoid or p.get("allergens_verified",False)) and not set(avoid).intersection(p.get("tags",[])) and (max_kcal is None or p.get("kcal") is not None)
    slots = [i for i,q in sorted(cart.items()) for _ in range(q)]
    choices = []
    for i in slots:
        group = [p["id"] for p in sorted(menu,key=lambda p:p["id"]) if p["category"] == by_id[i]["category"] and allowed(p) and ((i not in locked and by_id[i]["category"] != "unknown") or p["id"] == i)]
        if mode=='live' and i not in locked:
            # Bound the candidate set before *official* evaluation. Reference
            # prices select at most two alternatives, never determine payment.
            alternatives=sorted((j for j in group if j!=i),key=lambda j:(by_id[j].get('price_cents') is None,by_id[j].get('price_cents') or 0,j))[:2]
            group=([i] if i in group else [])+alternatives
        choices.append(group)
    count = prod(map(len,choices))
    if count > 100000:
        raise AppError("候选组合过多，请减少购物车商品或缩小菜单")
    deadline = monotonic() + 100
    original = service.quote(mode,store,cart,menu)
    pool, seen = [], set()
    for combo in product(*choices):
        candidate = dict(Counter(combo))
        key = tuple(sorted(candidate.items()))
        if key in seen:
            continue
        seen.add(key)
        if max_kcal is not None and sum(by_id[i]["kcal"]*q for i,q in candidate.items()) > max_kcal:
            continue
        changes = sum(max(0,q-candidate.get(i,0)) for i,q in cart.items())
        lost = sum(max(0,cart[i]-candidate.get(i,0)) for i in favorites)
        pool.append(dict(items=[dict(id=i,qty=q) for i,q in key], changed=changes, favorite_lost=lost, key=key))
    # Live: quote every feasible candidate; cap rather than silently prune using unverified prices.
    if mode == "live" and len(pool) > 36:
        raise AppError("Live 候选超过 36 组，请锁定商品或缩小菜单后重试；不会用估价跳过核价")
    feasible = []
    for p in pool:
        if monotonic() > deadline:
            raise AppError("核价搜索超时，请缩小候选范围后重试；未返回不完整的最优方案", "repair_timeout",504)
        p["quote"] = service.quote(mode,store,dict(p["key"]),menu)
        if monotonic() > deadline:
            raise AppError("核价搜索超时，请缩小候选范围后重试；未返回不完整的最优方案", "repair_timeout",504)
        if p["quote"]["amount_cents"] <= budget:
            feasible.append(p)
    strategies = [("A", "最少修改", lambda p:(p["changed"],p["quote"]["amount_cents"],p["key"])), ("B", "价格优先", lambda p:(p["quote"]["amount_cents"],p["changed"],p["key"])), ("C", "偏好优先", lambda p:(p["favorite_lost"],p["changed"],p["quote"]["amount_cents"],p["key"]))]
    plans = []
    for code,title,rank in strategies:
        if not feasible:
            plans.append(dict(code=code,title=title,feasible=False,reason="没有同时满足预算、忌口、锁定和热量上限的方案。可提高预算或放宽约束。"))
            continue
        p = min(feasible,key=rank)
        final = dict(p["key"])
        removed = [f"{by_id[i]['name']} ×{q-final.get(i,0)}" for i,q in cart.items() if q > final.get(i,0)]
        added = [f"{by_id[i]['name']} ×{q-cart.get(i,0)}" for i,q in final.items() if q > cart.get(i,0)]
        plans.append(dict(code=code,title=title,feasible=True,items=p["items"],quote=p["quote"],changed=p["changed"],favorite_lost=p["favorite_lost"],removed=removed,added=added,delta_cents=p["quote"]["amount_cents"]-original["amount_cents"],within_budget=True,reason="保持每类餐品的份数，满足全部硬约束；" + {"A":"优先减少修改份数。","B":"优先降低核价金额。","C":"优先保留标记为想吃的商品。"}[code]))
    note="不同策略可能得到相同方案；不为制造差异牺牲约束。"
    if mode=='live':note+=' Live 搜索仅覆盖原商品与每槽位最多两个同类参考价较低的替代候选；最终金额逐组官方核价，不声称全菜单最优。'
    return dict(original=[dict(id=i,qty=q) for i,q in sorted(cart.items())], original_quote=original, budget_cents=budget, searched=len(pool), plans=plans, note=note)
