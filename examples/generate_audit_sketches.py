"""Predeclared simple/clean/cluttered line-drawing suite. No model-dependent selection."""
import json
import random
from pathlib import Path
from PIL import Image,ImageDraw
from examples.generate_sketches import generate as clean_samples

def generate():
    clean=clean_samples();folder=Path(__file__).parent/'audit-sketches';folder.mkdir(exist_ok=True)
    cases=[]
    for cat in ['burger','fries','icecream','drink','nuggets','coffee']:
        im=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(im)
        def line(points):d.line(points,fill='#292923',width=6,joint='curve')
        if cat=='burger':
            line([(130,160),(160,102),(220,82),(300,82),(360,110),(390,160),(130,160)])
            line([(130,187),(390,187)]);line([(130,216),(390,216)]);line([(130,245),(155,275),(365,275),(390,245),(130,245)])
        elif cat=='fries':
            for x,top in [(170,70),(210,90),(250,55),(290,85),(330,65)]:line([(x,top),(x,215)])
            line([(140,190),(175,310),(325,310),(365,190),(250,220),(140,190)])
        elif cat=='icecream':
            line([(180,215),(256,340),(330,215),(180,215)])
            for box in [(173,120,260,218),(235,120,335,218),(205,65,300,165)]:d.arc(box,180,355,fill='#292923',width=6)
        elif cat=='drink':
            line([(180,120),(200,310),(320,310),(342,120),(180,120)])
            line([(260,120),(280,40),(330,40)])
        elif cat=='nuggets':
            for x,y in [(140,110),(280,90),(180,230),(330,220)]:line([(x,y),(x+53,y-10),(x+80,y+30),(x+58,y+65),(x+3,y+60),(x-12,y+23),(x,y)])
        else:
            line([(155,150),(167,265),(192,285),(295,285),(320,260),(330,150)])
            d.ellipse((153,135,333,168),outline='#292923',width=6);d.arc((308,170,393,256),270,90,fill='#292923',width=6)
            line([(210,110),(198,85),(212,60)]);line([(270,110),(257,85),(271,60)])
        for level in ['simple','clean','cluttered']:
            if level=='simple':sample=im
            else:sample=Image.open(clean/(cat+'.png')).convert('RGB')
            if level=='cluttered':
                sample=sample.rotate(17,resample=Image.Resampling.BICUBIC,fillcolor='white')
                d2=ImageDraw.Draw(sample);rng=random.Random(20261024)
                for _ in range(24):
                    x,y=rng.randrange(30,480),rng.randrange(30,350)
                    d2.line((x,y,x+rng.randrange(-40,41),y+rng.randrange(-30,31)),fill='#8d8c80',width=3)
            filename=f'{cat}-{level}.png';sample.save(folder/filename)
            cases.append({'file':filename,'expected':cat,'complexity':level,'kind':'food'})
    Image.open(clean/'unknown.png').save(folder/'house.png')
    cases.append({'file':'house.png','expected':'unknown','complexity':'negative','kind':'nonfood'})
    for shape in ['star','scribble','circle','blank']:
        im=Image.new('RGB',(512,384),'white');d=ImageDraw.Draw(im)
        if shape=='star':d.line([(250,50),(285,150),(400,150),(310,220),(340,330),(250,265),(155,330),(185,220),(95,150),(215,150),(250,50)],fill='black',width=6)
        elif shape=='circle':d.ellipse((150,70,360,300),outline='black',width=6)
        elif shape=='scribble':
            rng=random.Random(4026);d.line([(rng.randrange(100,400),rng.randrange(70,330)) for _ in range(12)],fill='black',width=6)
        im.save(folder/(shape+'.png'));cases.append({'file':shape+'.png','expected':'blank' if shape=='blank' else 'unknown','complexity':'negative','kind':'blank' if shape=='blank' else 'nonfood'})
    (folder/'manifest.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
    return folder,cases

if __name__=='__main__':print(generate()[0])
