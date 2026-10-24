"""Synthetic fixtures using shapes observed live; no account/store response data."""
import copy
import pytest
from backend.errors import AppError
from backend.mcp_client import LiveGateway
from backend.mcp_client.official import (
    decode_nutrition_table, normalize_menu, default_modification,
    default_quote_item, detail_metadata, search_context,
)
from backend.service import MealService


def test_observed_toon_numbers_quotes_and_null():
    rows=decode_nutrition_table('[2]{productName,energyKcal,protein}:\n  "mock,food",123.5,2\n  "mock\\\"food",null,0')
    assert rows==[{'productName':'mock,food','energyKcal':123.5,'protein':2}, {'productName':'mock"food','energyKcal':None,'protein':0}]


@pytest.mark.parametrize('text',[
    '[2]{name,kcal}:\n  mock,2', '[1]{name,kcal}:\n  mock,2,3',
    '[1]{name,kcal}:\nmock,2', '[1]{name,kcal}:\n  "broken,2',
    '[1]{name,name}:\n  mock,2', '{}', None,
])
def test_toon_drift_fails_closed(text):
    with pytest.raises(AppError):decode_nutrition_table(text)


def test_observed_menu_dictionary_and_bundle_exclusion():
    data={'data':{'meals':{'mock-a':{'name':'麦香鸡','currentPrice':'12.50'},'mock-b':{'name':'汉堡三件套','currentPrice':'23'},'mock-c':{'name':'薯条','withOrder':{}}}}}
    result=normalize_menu(data)['data']['meals']
    assert result[0]['code']=='mock-a' and result[0]['visualCategory']=='burger'
    assert result[1]['visualCategory']==result[2]['visualCategory']=='unknown'
    assert isinstance(data['data']['meals'],dict)  # Original untouched.


def test_default_selected_and_unselected_modifications():
    data={'modification':{'items':[{'values':[
        {'code':'mock-a','selectedQuantity':1,'selectedKey':'on','unselectedKey':'off'},
        {'code':'mock-b','selectedQuantity':0,'unselectedKey':'off'},
        {'code':'mock-c','selectedQuantity':0},
    ]}]}}
    assert default_modification(data)=={'values':[{'code':'mock-a','key':'on','quantity':1},{'code':'mock-b','key':'off','quantity':0}]}


def test_selected_modification_requires_actual_key():
    with pytest.raises(AppError):default_modification({'modification':{'items':[{'values':[{'code':'mock','selectedQuantity':1}]}]}})


def test_default_round_preserves_actual_choice_and_quantity():
    detail={'code':'mock-root','name':'可乐','rounds':[{'id':1,'choices':[
        {'code':'mock-small','name':'可乐小杯','isDefault':1,'quantity':1},
        {'code':'mock-large','name':'可乐大杯','isDefault':0,'quantity':1},
    ]}]}
    assert default_quote_item(detail,2)=={'productCode':'mock-root','quantity':2,'roundList':[{'round':'1','comboItemList':[{'code':'mock-small','quantity':1}]}]}
    assert detail_metadata(detail)['nutrition_name']=='可乐小杯'
    detail['rounds'][0]['choices'][0]['isDefault']=0
    with pytest.raises(AppError):default_quote_item(detail,1)


@pytest.mark.parametrize('address',['上海','', '  '])
def test_search_needs_city_and_keyword(address):
    with pytest.raises(AppError):search_context({'address':address})


def test_official_gateway_pickup_prices_cache_and_exact_nutrition(monkeypatch,tmp_path):
    monkeypatch.setenv('MCD_BINDINGS_FILE',str(tmp_path/'absent.json'))
    gateway=LiveGateway();calls=[]
    detail={'code':'mock-fries','name':'中薯条','rounds':[],'supportModify':False}
    class Mock:
        def call(self,name,args):
            calls.append((name,copy.deepcopy(args)))
            assert 'beCode' not in args
            if name=='query-meals':
                assert args=={'storeCode':'mock-store','orderType':1,'beType':1}
                return {'success':True,'data':{'meals':{'mock-fries':{'name':'薯条','currentPrice':'13.50'}}}}
            if name=='query-meal-detail':return {'success':True,'data':copy.deepcopy(detail)}
            if name=='list-nutrition-foods':
                assert args=={}
                return {'success':True,'data':'[2]{productName,energyKcal,protein,fat}:\n  薯条,999,9,9\n  中薯条,289,4,14'}
            if name=='calculate-price':
                assert args['items']==[{'productCode':'mock-fries','quantity':2}]
                # Intentionally differs from menu-price sum.
                return {'success':True,'data':{'originalPrice':2700,'discount':100,'price':2600}}
            if name=='query-nearby-stores':
                assert args=={'beType':1,'searchType':2,'city':'测试城','keyword':'公开地标'}
                return {'success':True,'data':[]}
            raise AssertionError(name)
    gateway.client=Mock();service=MealService(gateway)
    assert service.stores('live','测试城 公开地标')==[]
    menu=service.menu('live','mock-store');p=menu[0]
    assert p['price_cents']==1350 and not p['price_verified'] and p['source']=='live'
    enriched=service.enrich(p,'mock-store')
    assert enriched['kcal']==289 and enriched['nutrition_source']=='official_exact_name'
    assert not enriched['allergens_verified']
    for _ in range(2):
        q=service.quote('live','mock-store',{'mock-fries':2},menu)
        assert q['amount_cents']==2600 and q['official']
    assert sum(n=='query-meal-detail' for n,_ in calls)==1
    assert sum(n=='calculate-price' for n,_ in calls)==2
    assert service.menu('demo','demo-studio')[0]['source']=='demo'


def test_default_business_failure_never_uses_payload(monkeypatch,tmp_path):
    monkeypatch.setenv('MCD_BINDINGS_FILE',str(tmp_path/'absent.json'))
    gateway=LiveGateway()
    class Mock:
        def call(self,*args):return {'success':False,'data':{'meals':{}}}
    gateway.client=Mock()
    with pytest.raises(AppError) as e:MealService(gateway).menu('live','mock-store')
    assert e.value.code=='mcp_business_error'
