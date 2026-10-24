"""Read-only official acceptance runner; never records raw account/location responses."""
import argparse
import json
import os
import logging
import sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import ROOT
from backend.errors import AppError
from backend.service import MealService
from backend.matching import match
from backend.optimizer import repair

def verify(requests=None, schema_output=None):
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'authenticated_business_chain':False,'tool_calls':{},'stages':[]}
    if not os.getenv('MCD_MCP_TOKEN','').strip():
        return {**report,'status':'blocked','reason':'missing_token','configuration':'.env: MCD_MCP_TOKEN'}
    service=MealService()
    call=service.live.client.call
    def tracked_call(name,arguments):
        entry=report['tool_calls'].setdefault(name,{'successful_calls':0,'failed_calls':0})
        try:
            result=call(name,arguments)
            if isinstance(result,dict) and result.get('success') is True:entry['successful_calls']+=1
            else:entry['failed_calls']+=1
            return result
        except AppError:
            entry['failed_calls']+=1
            raise
    service.live.client.call=tracked_call
    try:
        tools=service.live.client.tools();names=[t['name'] for t in tools]
        report['stages'].append({'stage':'tools/list','status':'passed','tools':names})
        if {'query-nearby-stores','query-meals','query-meal-detail','list-nutrition-foods','calculate-price'}-set(names):
            raise AppError('官方当前账户未返回全部所需工具','missing_tools',502)
        if schema_output:
            p=Path(schema_output).resolve()
            if not p.is_relative_to(ROOT/'private'):raise AppError('schema 输出必须位于 private/ 内')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(tools,ensure_ascii=False,indent=2),encoding='utf-8')
        if requests is None:return {**report,'status':'schema_only','reason':'business_inputs_not_supplied'}
        cfg=service.live.config()
        if not cfg.get('detail') or not cfg.get('nutrition'):
            raise AppError('完整验收需要 detail 与 nutrition 的实际映射','bindings_incomplete',503)
        stores=service.stores('live',requests.get('address',''))
        if not stores:raise AppError('附近门店为空，业务验收未完成','empty_stores',502)
        report['stages'].append({'stage':'nearby_stores','status':'passed','count':len(stores)})
        store=requests.get('store_id') or stores[0]['id']
        if store not in {s['id'] for s in stores}:raise AppError('指定门店不在查询结果中')
        menu=service.menu('live',store)
        if not menu:raise AppError('门店菜单为空，业务验收未完成','empty_menu',502)
        report['stages'].append({'stage':'available_menu','status':'passed','count':len(menu)})
        candidates=match(menu,requests.get('category','burger'))
        if not candidates:raise AppError('该类别无匹配餐品','empty_matches',502)
        report['stages'].append({'stage':'category_match','status':'passed','count':len(candidates)})
        enriched=service.enrich(candidates[0],store)
        report['stages'].append({'stage':'detail_nutrition','status':'passed' if enriched.get('kcal') is not None else 'data_missing','nutrition_present':enriched.get('kcal') is not None})
        cart=service.cart(requests.get('items'),menu);quote=service.quote('live',store,cart,menu)
        if not quote['official']:raise AppError('Live 返回来源不正确')
        report['stages'].append({'stage':'calculate_price','status':'passed','amount_cents':quote['amount_cents']})
        if requests.get('avoid') or requests.get('max_kcal') is not None:menu=[service.enrich(p,store) for p in menu]
        result=repair(service,'live',store,cart,menu,requests);checks=[]
        for plan in result['plans']:
            if not plan['feasible']:
                checks.append({'strategy':plan['code'],'status':'infeasible'});continue
            fresh=service.quote('live',store,{i['id']:i['qty'] for i in plan['items']},menu)
            if not fresh['official'] or fresh['amount_cents']!=plan['quote']['amount_cents'] or fresh['amount_cents']>requests['budget_cents']:
                raise AppError('方案重新核价发生变化或不满足预算，请重新计算','requote_changed',502)
            checks.append({'strategy':plan['code'],'status':'passed','amount_cents':fresh['amount_cents'],'within_budget':True,'changed_from_original':dict((i['id'],i['qty']) for i in plan['items'])!=cart})
        report['stages'].append({'stage':'repair_requote','status':'passed' if all(c['status']=='passed' for c in checks) else 'infeasible','plans':checks})
        complete=enriched.get('kcal') is not None and all(c['status']=='passed' for c in checks)
        return {**report,'status':'passed' if complete else 'incomplete','authenticated_business_chain':complete}
    except AppError as e:
        return {**report,'status':'failed','reason':e.code,'message':str(e)}

if __name__=='__main__':
    # SDK diagnostics are not part of a public acceptance log.
    logging.disable(logging.CRITICAL)
    parser=argparse.ArgumentParser();parser.add_argument('--requests');parser.add_argument('--schema-output');args=parser.parse_args()
    payload=json.loads(Path(args.requests).read_text(encoding='utf-8')) if args.requests else None
    result=verify(payload,args.schema_output)
    out=ROOT/'artifacts/mcp-live-audit.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['status']=='passed' else 2)
