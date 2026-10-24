import asyncio
import json
import pytest
import httpx
from contextlib import asynccontextmanager
from types import SimpleNamespace
from pathlib import Path
from backend.errors import AppError
from backend.mcp_client import OfficialClient,LiveGateway,render
from backend.service import MealService

@pytest.mark.parametrize('status,expected,retries',[(401,'mcp_401',1),(403,'mcp_403',1),(429,'mcp_429',2),(503,'mcp_503',2)])
def test_real_sdk_transport_error_handling_without_external_calls(monkeypatch,status,expected,retries):
    import mcp.client.streamable_http as transport
    monkeypatch.setenv('MCD_MCP_TOKEN','test-token');attempts=[]
    @asynccontextmanager
    async def failure(*args,**kwargs):
        attempts.append(True)
        raise httpx.HTTPStatusError('credentials must not be returned',request=httpx.Request('POST','https://mcp.mcd.cn'),response=httpx.Response(status))
        yield
    async def no_wait(*args):pass
    monkeypatch.setattr(transport,'streamable_http_client',failure);monkeypatch.setattr('backend.mcp_client.asyncio.sleep',no_wait)
    with pytest.raises(AppError) as e:OfficialClient().tools()
    assert e.value.code==expected and 'test-token' not in str(e.value) and len(attempts)==retries

def test_timeout_retries_once_and_redacts_exception(monkeypatch):
    import mcp.client.streamable_http as transport
    monkeypatch.setenv('MCD_MCP_TOKEN','test-token');attempts=[]
    @asynccontextmanager
    async def failure(*args,**kwargs):
        attempts.append(True);raise TimeoutError('test-token');yield
    async def no_wait(*args):pass
    monkeypatch.setattr(transport,'streamable_http_client',failure);monkeypatch.setattr('backend.mcp_client.asyncio.sleep',no_wait)
    with pytest.raises(AppError) as e:OfficialClient().tools()
    assert e.value.code=='mcp_timeout' and len(attempts)==2 and 'test-token' not in str(e.value)

def test_blank_token_status_is_not_configured(client,monkeypatch):
    monkeypatch.setenv('MCD_MCP_TOKEN','   ');assert not client.get('/api/status').json['token_configured']

def test_cart_mapping_preserves_identifiers_and_quantities():
    template={'rows':{'$map':'items','template':{'sku':'$item.id','number':'$item.qty','fixed':'normal'}}}
    assert render(template,{'items':[{'id':'x','qty':2},{'id':'y','qty':1}]})=={'rows':[{'sku':'x','number':2,'fixed':'normal'},{'sku':'y','number':1,'fixed':'normal'}]}

def test_gateway_rejects_wrong_tool_for_quote():
    g=LiveGateway();g.bindings={'quote':{'tool':'query-meals','arguments':{}}}
    with pytest.raises(AppError) as e:g.execute('quote',{})
    assert e.value.code=='bindings_invalid'

def test_gateway_rejects_non_success_business_envelope():
    g=LiveGateway();g.bindings={'quote':{'tool':'calculate-price','arguments':{},'success_path':'status','success_value':'ok'}}
    g.client=SimpleNamespace(call=lambda *args:{'status':'failed','amount':0})
    with pytest.raises(AppError) as e:g.execute('quote',{})
    assert e.value.code=='mcp_business_error'

@pytest.mark.parametrize('rows',[None,{},[{'id':None,'name':'汉堡'}],[{'id':'a','name':None}],[{'id':'a','name':'汉堡'},{'id':'a','name':'鸡块'}]])
def test_live_menu_never_fabricates_ids_or_names(rows):
    g=LiveGateway();g.bindings={'menu':{'tool':'query-meals','arguments':{},'items':'rows','id':'id','name':'name'}}
    g.client=SimpleNamespace(call=lambda *args:{'rows':rows})
    with pytest.raises(AppError):MealService(g).menu('live','mock')

def test_empty_live_menu_does_not_use_demo():
    g=LiveGateway();g.bindings={'menu':{'tool':'query-meals','arguments':{},'items':'rows','id':'id','name':'name'}}
    g.client=SimpleNamespace(call=lambda *args:{'rows':[]})
    assert MealService(g).menu('live','mock')==[]

def test_expired_final_quote_search_is_not_returned(monkeypatch):
    from backend.catalog import demo_menu
    from backend.optimizer import repair
    now=[0.0]
    class Slow:
        def quote(self,*args):now[0]+=60;return {'amount_cents':100,'official':True}
    monkeypatch.setattr('backend.optimizer.monotonic',lambda:now[0])
    with pytest.raises(AppError) as e:repair(Slow(),'live','mock',{'b1':1},demo_menu(),{'budget_cents':3000})
    assert e.value.code=='repair_timeout'

def test_no_matches_api_is_empty_and_recoverable():
    from backend.app import create_app
    class Empty(MealService):
        def menu(self,*args):return []
    c=create_app(Empty()).test_client()
    assert c.post('/api/match',json={'mode':'live','store_id':'mock','category':'burger'}).json=={'products':[],'source':'live'}
    assert c.get('/api/status').status_code==200

def test_release_manifest_excludes_unreviewed_files(tmp_path):
    from scripts.package_release import release_files
    (tmp_path/'scripts').mkdir();(tmp_path/'frontend/dist/assets').mkdir(parents=True)
    (tmp_path/'scripts/release-manifest.json').write_text(json.dumps({'files':['README.md']}))
    (tmp_path/'README.md').write_text('public');(tmp_path/'private-notes.json').write_text('not public')
    (tmp_path/'frontend/dist/index.html').write_text('<script src="/assets/a.js"></script>')
    (tmp_path/'frontend/dist/assets/a.js').write_text('console.log(1)')
    (tmp_path/'frontend/dist/assets/private.json').write_text('not public')
    assert {p.relative_to(tmp_path).as_posix() for p in release_files(tmp_path)}=={'README.md','frontend/dist/index.html','frontend/dist/assets/a.js'}

def test_gitignore_sensitive_paths_and_schema():
    from scripts.audit_release import ignore_checks
    assert all(x['passed'] for x in ignore_checks().values())

def test_live_runner_cannot_pass_without_token(monkeypatch):
    monkeypatch.delenv('MCD_MCP_TOKEN',raising=False)
    from scripts.verify_live import verify
    r=verify();assert r['status']=='blocked' and not r['authenticated_business_chain']
