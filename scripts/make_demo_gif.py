"""Compose actual captured screenshots; no fabricated UI or model results."""
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parents[1]/"docs"/"screenshots"
files=[root/"desktop.png",root/"repair.png",root/"fries.png"]
frames=[]
for path in files:
    image=Image.open(path).convert("RGB")
    # Equal scaling only; preserve entire captured page in each frame.
    image.thumbnail((900,2000))
    frames.append(image)
w=max(i.width for i in frames);h=max(i.height for i in frames)
canvases=[]
for image in frames:
    page=Image.new("RGB",(w,h),"#f8f6ef");page.paste(image,((w-image.width)//2,0));canvases.append(page)
canvases[0].save(root/"demo.gif",save_all=True,append_images=canvases[1:],duration=[2500,3500,2500],loop=0,optimize=True)
print(root/"demo.gif")
