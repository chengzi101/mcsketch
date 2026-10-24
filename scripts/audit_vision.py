"""Real API PNG preprocessing + instrumented CLIP.forward; keeps every failure."""
import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import ROOT,create_app
from backend.vision import Vision
from examples.generate_audit_sketches import generate
from transformers import CLIPModel

def run():
    folder,cases=generate();vision=Vision();client=create_app(vision=vision).test_client();calls=[];results=[]
    forward=CLIPModel.forward
    def traced(model,*args,**kwargs):
        calls.append(True);return forward(model,*args,**kwargs)
    with patch.object(CLIPModel,'forward',traced):
        for case in cases:
            png=(folder/case['file']).read_bytes();before=len(calls);start=time.perf_counter()
            response=client.post('/api/recognize',json={'image':'data:image/png;base64,'+base64.b64encode(png).decode()})
            data=response.json;top=data.get('candidates',[]);guess=top[0]['category'] if top else None
            passed=(response.status_code==400 if case['kind']=='blank' else data.get('status')=='ok' and (guess==case['expected'] if case['kind']=='food' else data.get('uncertain') is True))
            record={**case,'http_status':response.status_code,'png_sha256':hashlib.sha256(png).hexdigest(),'real_forward_calls':len(calls)-before,'seconds':round(time.perf_counter()-start,3),'passed':passed,'response':data}
            results.append(record);print(case['file'],guess,'uncertain='+str(data.get('uncertain')),'PASS' if passed else 'FAIL',flush=True)
    food=[r for r in results if r['kind']=='food']
    report={'model':'openai/clip-vit-base-patch32','revision':'3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268','scope':'Author-generated deterministic line drawings; no independent accuracy claim','total':len(results),'food_cases':len(food),'food_top1_correct':sum(r['passed'] for r in food),'nonfood_abstained':sum(r['passed'] for r in results if r['kind']=='nonfood'),'real_forward_calls':len(calls),'results':results}
    (ROOT/'artifacts/vision-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':
    r=run();print(json.dumps({k:v for k,v in r.items() if k!='results'},ensure_ascii=False,indent=2))
    sys.exit(1 if any(x['response'].get('status')=='manual' for x in r['results']) else 0)
