import base64
import io
import pytest
from PIL import Image, ImageDraw
from backend.errors import AppError
from backend.optimizer import repair
from backend.service import cents, fingerprint
from backend.vision import read_png
from backend.matching import match

def test_demo_status(client):
    r=client.get('/api/status');assert r.status_code==200;assert 'token_configured' in r.json
    assert 'token' not in r.json

def test_demo_menu(client):
    r=client.post('/api/menu',json={});assert r.status_code==200
    assert all(p['source']=='demo' and not p['price_verified'] for p in r.json['products'])

@pytest.mark.parametrize('category',['burger','fries','icecream','drink','nuggets','coffee'])
def test_all_categories(client,category):
    r=client.post('/api/match',json={'category':category})
    assert 1<=len(r.json['products'])<=3
    assert all(p['category']==category for p in r.json['products'])

def test_no_match():assert match([], 'burger')==[]

def test_unknown_category(client):assert client.post('/api/match',json={'category':'cat'}).status_code==400

def test_missing_nutrition(client):
    r=client.post('/api/detail',json={'id':'c2'});assert r.json['product']['kcal'] is None

@pytest.mark.parametrize('qty',[0,-1,1.5,True,7,'2',None])
def test_invalid_quantity(client,qty):assert client.post('/api/quote',json={'items':[{'id':'b1','qty':qty}]}).status_code==400

def test_unknown_item(client):assert client.post('/api/quote',json={'items':[{'id':'fake','qty':1}]}).status_code==400

def test_empty_cart(client):assert client.post('/api/quote',json={'items':[]}).status_code==400

def test_total_quantity(client):assert client.post('/api/quote',json={'items':[{'id':'b1','qty':4},{'id':'f1','qty':3}]}).status_code==400

def test_quote_integer_cents(client):
    r=client.post('/api/quote',json={'items':[{'id':'b1','qty':1},{'id':'f1','qty':1},{'id':'d1','qty':1}]})
    assert r.json['amount_cents']==4800;assert not r.json['official']

def test_quote_fingerprint():
    assert fingerprint('demo','a',{'x':1})!=fingerprint('demo','a',{'x':2})
    assert fingerprint('live','a',{'x':1})!=fingerprint('demo','a',{'x':1})

def test_three_strategies(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1},{'id':'f1','qty':1},{'id':'d1','qty':1}],'budget_cents':3000})
    assert r.status_code==200
    plans=r.json['plans'];assert len(plans)==3;assert all(p['feasible'] and p['quote']['amount_cents']<=3000 for p in plans)
    assert plans[1]['quote']['amount_cents']==2500
    assert all(sum(x['qty'] for x in p['items'])==3 for p in plans)

def test_deterministic(service):
    menu=service.menu('demo','demo-studio');args=(service,'demo','demo-studio',{'b1':1,'f1':1},menu,{'budget_cents':3000})
    a,b=repair(*args),repair(*args)
    assert [p['items'] for p in a['plans']]==[p['items'] for p in b['plans']]

def test_hard_lock(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1},{'id':'f1','qty':1}],'budget_cents':3000,'locked_ids':['b1']})
    assert all(not p['feasible'] for p in r.json['plans'])

def test_soft_favorite(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1},{'id':'f1','qty':1}],'budget_cents':3200,'favorite_ids':['b1']})
    p=r.json['plans'][2];assert {'id':'b1','qty':1} in p['items'];assert p['favorite_lost']==0

def test_impossible_budget(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1}],'budget_cents':0})
    assert all(not p['feasible'] for p in r.json['plans'])

def test_avoid(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1}],'budget_cents':3000,'avoid':['beef']})
    assert all(p['items']==[{'id':'b2','qty':1}] for p in r.json['plans'])

def test_avoid_all(client):
    r=client.post('/api/repair',json={'items':[{'id':'b1','qty':1}],'budget_cents':3000,'avoid':['gluten']})
    assert all(not p['feasible'] for p in r.json['plans'])

def test_calorie_unknown_excluded(client):
    r=client.post('/api/repair',json={'items':[{'id':'c1','qty':1}],'budget_cents':3000,'max_kcal':50})
    assert all(not p['feasible'] for p in r.json['plans'])

@pytest.mark.parametrize('budget',[True,-1,1.2,'3000'])
def test_invalid_budget(client,budget):
    assert client.post('/api/repair',json={'items':[{'id':'b1','qty':1}],'budget_cents':budget}).status_code==400

def test_png_validation():
    im=Image.new('RGB',(50,50),'white');b=io.BytesIO();im.save(b,format='PNG')
    with pytest.raises(AppError,match='空'):read_png('data:image/png;base64,'+base64.b64encode(b.getvalue()).decode())
    ImageDraw.Draw(im).line((5,5,30,40),fill='black',width=3);b=io.BytesIO();im.save(b,format='PNG')
    assert read_png('data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()).size==(50,50)

@pytest.mark.parametrize('image',[None,'bad','data:image/png;base64,???','data:image/jpeg;base64,aaa'])
def test_invalid_image(client,image):assert client.post('/api/recognize',json={'image':image}).status_code==400

def test_manual_fallback(monkeypatch):
    from backend.vision import Vision
    import sys
    monkeypatch.setitem(sys.modules,'torch',None)
    r=Vision().predict(Image.new('RGB',(50,50),'red'));assert r['status']=='manual';assert r['candidates']==[]

def test_cross_origin(client):assert client.post('/api/quote',json={},headers={'Origin':'https://evil.example'}).status_code==403
def test_bad_json(client):assert client.post('/api/menu',json=[]).status_code==400
def test_no_token(client,monkeypatch):
    monkeypatch.delenv('MCD_MCP_TOKEN',raising=False)
    r=client.get('/api/live/tools');assert r.status_code==503;assert r.json['code']=='missing_token'

def test_no_order_tools(client):
    r=client.post('/api/live/call',json={'tool':'create-order','arguments':{}});assert r.status_code==400

@pytest.mark.parametrize('raw,expected',[('12.30',1230),('0.01',1),('0',0)])
def test_decimal(raw,expected):assert cents(raw,'yuan')==expected

@pytest.mark.parametrize('raw',['NaN','-1','abc','1.001'])
def test_bad_money(raw):
    with pytest.raises(AppError):cents(raw,'yuan')

@pytest.mark.parametrize('path,payload',[
    ('menu',{'mode':[]}),('match',{'category':[]}),
    ('quote',{'items':[{'id':{},'qty':1}]}),
    ('live/call',{'tool':[],'arguments':{}}),
])
def test_malformed_types_return_400(client,path,payload):
    assert client.post('/api/'+path,json=payload).status_code==400
