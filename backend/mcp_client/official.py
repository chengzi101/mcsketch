"""Adapters verified against authenticated MCP responses on 2026-10-24.

No account, store, location or product IDs are embedded here. These are request
field names and response paths actually returned by the official service.
"""
import copy
import json
import re
from backend.errors import AppError
from backend.matching import category_of

DEFAULT_BINDINGS = {
    "stores":{"tool":"query-nearby-stores","arguments":{"beType":1,"searchType":2,"city":"$city","keyword":"$keyword"},"items":"data","id":"storeCode","name":"storeName","address":"address","success_path":"success","success_value":True},
    "menu":{"tool":"query-meals","arguments":{"storeCode":"$store_id","orderType":1,"beType":1},"items":"data.meals","id":"code","name":"name","price":"currentPrice","price_unit":"yuan","success_path":"success","success_value":True},
    "detail":{"tool":"query-meal-detail","arguments":{"storeCode":"$store_id","orderType":1,"beType":1,"code":"$product_id"},"success_path":"success","success_value":True},
    "nutrition":{"tool":"list-nutrition-foods","arguments":{},"items":"data","name":"productName","kcal":"energyKcal","protein":"protein","fat":"fat","success_path":"success","success_value":True},
    "quote":{"tool":"calculate-price","arguments":{"storeCode":"$store_id","orderType":1,"beType":1},"amount":"data.price","amount_unit":"cents","success_path":"success","success_value":True},
}

def search_context(context):
    address=context.get('address','').strip()
    parts=re.split(r'\s+|[,，]',address,maxsplit=1)
    if len(parts)!=2 or not all(x.strip() for x in parts):
        raise AppError('请输入“城市 位置关键词”，用空格分隔，例如：上海 人民广场')
    return {**context,'city':parts[0].strip(),'keyword':parts[1].strip()}

def decode_nutrition_table(text):
    """Strict flat comma-delimited TOON table, the observed official format.

    Not a general TOON implementation. Unsupported headers, quoting, row width
    or declared-count changes fail closed rather than inventing nutrition.
    """
    if not isinstance(text,str) or len(text)>2_000_000:
        raise AppError('官方营养表格式不受支持','schema_drift',502)
    lines=text.splitlines()
    header=re.fullmatch(r'\[(\d+)\]\{([A-Za-z][A-Za-z0-9]*(?:,[A-Za-z][A-Za-z0-9]*)*)\}:',lines[0] if lines else '')
    if not header or int(header[1])>10000:
        raise AppError('官方营养表头变化','schema_drift',502)
    fields=header[2].split(',')
    if len(set(fields))!=len(fields):raise AppError('官方营养表列重复','schema_drift',502)
    def cells(line):
        result=[];start=0;quoted=False;escaped=False
        for i,ch in enumerate(line):
            if escaped:escaped=False;continue
            if ch=='\\' and quoted:escaped=True;continue
            if ch=='"':quoted=not quoted
            elif ch==',' and not quoted:result.append(line[start:i]);start=i+1
        if quoted or escaped:raise ValueError
        result.append(line[start:]);parsed=[]
        for value in result:
            if value.startswith('"'):
                value=json.loads(value)
                if not isinstance(value,str):raise ValueError
            elif value=='null':value=None
            elif value in ('true','false'):value=value=='true'
            elif re.fullmatch(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?',value):value=json.loads(value)
            parsed.append(value)
        return parsed
    try:
        rows=[]
        for line in lines[1:]:
            if not line.startswith('  '):raise ValueError
            values=cells(line[2:])
            if len(values)!=len(fields):raise ValueError
            rows.append(dict(zip(fields,values)))
        if len(rows)!=int(header[1]):raise ValueError
        return rows
    except (ValueError,TypeError):
        raise AppError('官方营养表行数、列数或引号变化','schema_drift',502) from None

def normalize_menu(response):
    result=copy.deepcopy(response);data=result['data'];meals=data['meals']
    if not isinstance(meals,dict):raise AppError('官方菜单字典格式变化','schema_drift',502)
    rows=[]
    for code,meal in meals.items():
        if not isinstance(meal,dict):raise AppError('官方菜单条目格式变化','schema_drift',502)
        row={**meal,'code':code}
        name=meal.get('name','')
        # Visual recommendations handle individual foods, not multi-food meal
        # bundles or membership/with-order offers that need separate choices.
        bundle=any(w in name for w in ['套餐','人餐','件套','拼盘','分享','组合','随心配','开心乐园','大堡口福']) or 'withOrder' in meal
        row['visualCategory']='unknown' if bundle else category_of(name)
        rows.append(row)
    data['meals']=rows
    return result

def default_modification(data):
    result=[]
    for group in data.get('modification',{}).get('items',[]):
        for v in group['values']:
            qty=v['selectedQuantity']
            if type(qty) is not int or qty<0:raise AppError('官方默认特制数量无效','schema_drift',502)
            key=v.get('selectedKey') if qty else v.get('unselectedKey')
            if qty and not isinstance(key,str):raise AppError('官方默认特制缺少已选键值','schema_drift',502)
            if key is not None:result.append({'code':v['code'],'key':key,'quantity':qty})
    return {'values':result} if result else None

def default_quote_item(detail,quantity):
    line={'productCode':detail['code'],'quantity':quantity}
    mod=default_modification(detail)
    if mod:line['modification']=mod
    rounds=[]
    for r in detail['rounds']:
        choices=[]
        for choice in r['choices']:
            if choice['isDefault']==1 and choice['quantity']>0:
                child={'code':choice['code'],'quantity':choice['quantity']}
                mod=default_modification(choice)
                if mod:child['modification']=mod
                choices.append(child)
        if not choices:raise AppError('商品没有可核实的默认搭配，暂不自动核价','default_selection_missing',502)
        rounds.append({'round':str(r['id']),'comboItemList':choices})
    if rounds:line['roundList']=rounds
    return line

def detail_metadata(detail):
    rounds=detail['rounds'];defaults=[c for r in rounds for c in r['choices'] if c['isDefault']==1 and c['quantity']>0]
    nutrition_name=detail['name'] if not rounds else defaults[0]['name'] if len(rounds)==1 and len(defaults)==1 and defaults[0]['quantity']==1 else None
    return {'nutrition_name':nutrition_name,'default_selection':[c['name'] for c in defaults] or [detail['name']],'support_modify':bool(detail.get('supportModify',False))}
