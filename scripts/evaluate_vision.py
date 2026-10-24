"""Run real inference and preserve all results, including failures and uncertainty."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import ROOT
from backend.vision import Vision
from examples.generate_sketches import generate
from PIL import Image

if __name__=="__main__":
    folder=generate();model=Vision();results=[]
    for image in [folder / (name+".png") for name in ["burger","coffee","drink","fries","icecream","nuggets","unknown"]]:
        start=time.perf_counter();r=model.predict(Image.open(image).convert("RGB"))
        r.update(sample=image.name,expected=image.stem,seconds=round(time.perf_counter()-start,2))
        results.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
        if r["status"]=="manual":break
    out=ROOT/"artifacts"/"vision-evaluation.json";out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
