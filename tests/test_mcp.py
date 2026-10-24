import asyncio
import httpx
import pytest
from mcp.types import CallToolResult, TextContent
from backend.mcp_client import OfficialClient, LiveGateway, error_kind, unpack
from backend.service import MealService
from backend.errors import AppError

def test_sdk_import():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    assert callable(streamable_http_client) and ClientSession

def test_structured_result():assert unpack(CallToolResult(content=[],structuredContent={'real':True}))=={'real':True}
def test_json_text_result():assert unpack(CallToolResult(content=[TextContent(type='text',text='{"amount":12}')]))=={'amount':12}
def test_business_error():
    with pytest.raises(AppError):unpack(CallToolResult(content=[],isError=True))

@pytest.mark.parametrize('status',[401,429,503])
def test_http_errors(status):
    e=httpx.HTTPStatusError('secret is never surfaced',request=httpx.Request('GET','https://mcp.mcd.cn'),response=httpx.Response(status))
    assert error_kind(ExceptionGroup('outer',[e]))==str(status)

def test_timeout():assert error_kind(TimeoutError())=='timeout'

def test_schema_validation_and_allowed_tool(monkeypatch):
    from mcp.types import ListToolsResult, Tool
    class Session:
        async def list_tools(self,cursor=None):return ListToolsResult(tools=[Tool(name='query-meals',inputSchema={'type':'object','required':['store'],'properties':{'store':{'type':'string'}}})])
        async def call_tool(self,name,args):return CallToolResult(content=[],structuredContent={'items':[]})
    client=OfficialClient()
    async def session(operation):return await operation(Session())
    monkeypatch.setattr(client,'_session',session)
    with pytest.raises(AppError):client.call('query-meals',{})
    assert client.call('query-meals',{'store':'abc'})=={'items':[]}

def test_live_quote_uses_official_total():
    gateway=LiveGateway();gateway.bindings={'quote':{'tool':'calculate-price','arguments':{'selected':'$items','restaurant':'$store_id'},'amount':'payload.pay','amount_unit':'yuan'}}
    class Mock:
        def call(self,name,args):
            assert name=='calculate-price';assert args=={'selected':[{'id':'real-a','qty':2}],'restaurant':'store-1'}
            return {'payload':{'pay':'17.25'}}
    gateway.client=Mock();s=MealService(gateway)
    q=s.quote('live','store-1',{'real-a':2},[])
    assert q['amount_cents']==1725 and q['official']

def test_live_mapping_drift():
    gateway=LiveGateway();gateway.bindings={'quote':{'tool':'calculate-price','arguments':{},'amount':'payload.pay','amount_unit':'yuan'}}
    class Mock:
        def call(self,*a):return {'changed':True}
    gateway.client=Mock()
    with pytest.raises(AppError,match='结构'):MealService(gateway).quote('live','x',{'i':1},[])

def test_official_sdk_roundtrip_against_mock_mcp():
    from mcp.server.fastmcp import FastMCP
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    server=FastMCP('mcsketch-test-only',stateless_http=True,json_response=True)
    @server.tool(name='query-meals')
    def meals(store:str)->dict:
        return {'sample_only':True,'store':store,'items':[]}
    application=server.streamable_http_app()
    async def run():
        async with server.session_manager.run():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application)) as http:
                async with streamable_http_client('http://127.0.0.1:8000/mcp',http_client=http) as streams:
                    async with ClientSession(streams[0],streams[1]) as s:
                        await s.initialize()
                        listing=await s.list_tools()
                        assert listing.tools[0].name=='query-meals'
                        assert listing.tools[0].inputSchema['properties']['store']['type']=='string'
                        result=unpack(await s.call_tool('query-meals',{'store':'mock-store'}))
                        assert result['sample_only'] and result['store']=='mock-store'
    asyncio.run(run())

def test_live_optimizer_obeys_nonlinear_official_quote():
    from backend.catalog import demo_menu
    from backend.optimizer import repair
    class MockService:
        def quote(self,mode,store,cart,menu):
            # A mock promotion makes the expensive list-price pair cheapest.
            amount=1000 if cart=={'b1':1,'f1':1} else 1900 if cart=={'b3':1,'f2':1} else 3000
            return {'amount_cents':amount,'official':True,'source':'live'}
    result=repair(MockService(),'live','mock',{'b1':1,'f1':1},demo_menu(),{'budget_cents':2000})
    assert result['plans'][1]['quote']['amount_cents']==1000
    assert result['plans'][1]['items']==[{'id':'b1','qty':1},{'id':'f1','qty':1}]

def test_partial_quote_failure_never_returns_optimum():
    from backend.catalog import demo_menu
    from backend.optimizer import repair
    class MockService:
        def quote(self,mode,store,cart,menu):
            if 'b2' in cart:raise AppError('mock timeout','mcp_timeout',502)
            return {'amount_cents':1000,'official':True,'source':'live'}
    with pytest.raises(AppError,match='timeout'):
        repair(MockService(),'live','mock',{'b1':1},demo_menu(),{'budget_cents':2000})

def test_missing_live_nutrition_mapping_remains_unknown():
    gateway=LiveGateway();gateway.bindings={}
    product={'id':'mock','name':'Mock item','kcal':None,'tags':[],'allergens_verified':False}
    assert MealService(gateway).enrich(product,'mock')==product

def test_unknown_live_allergen_tags_are_not_treated_as_safe():
    gateway=LiveGateway();gateway.bindings={'detail':{'tool':'query-meal-detail','arguments':{},'tags':'allergens'}}
    class Mock:
        def call(self,*args):return {'allergens':['unmapped-official-tag']}
    gateway.client=Mock()
    r=MealService(gateway).enrich({'id':'mock','name':'Mock item','kcal':None,'tags':[],'allergens_verified':False},'mock')
    assert r['allergens_verified'] is False and r['tags']==[]
