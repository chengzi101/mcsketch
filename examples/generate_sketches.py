"""Small authored line drawings, independent of model inference, not a benchmark."""
from pathlib import Path
from PIL import Image, ImageDraw

def generate(root=None):
    root = Path(root or Path(__file__).parent / "sketches")
    root.mkdir(parents=True,exist_ok=True)
    for category in ["burger","fries","icecream","drink","nuggets","coffee","unknown"]:
        im=Image.new("RGB",(512,384),"white");d=ImageDraw.Draw(im)
        def line(points, color="#272722",width=7):d.line(points,fill=color,width=width,joint="curve")
        if category=="burger":
            d.arc((112,76,400,270),180,360,fill="#272722",width=8);line([(112,174),(400,174)])
            line([(112,192),(150,205),(190,191),(235,206),(275,191),(315,206),(355,191),(400,200)],"#649768",10)
            d.rounded_rectangle((112,219,400,246),radius=11,outline="#272722",width=7)
            d.arc((112,224,400,300),0,180,fill="#272722",width=7);line([(112,263),(400,263)])
            for x,y in [(175,132),(235,108),(288,119),(340,143)]:line([(x,y),(x+9,y-5)],width=4)
        elif category=="fries":
            for x,top in [(145,82),(185,59),(225,90),(265,49),(305,73),(345,95)]:
                d.rectangle((x,top,x+19,221),outline="#272722",width=5)
            line([(133,183),(175,310),(340,310),(382,183),(260,212),(133,183)],"#e33c36",8)
        elif category=="icecream":
            line([(180,205),(256,343),(333,205),(180,205)],"#272722",6)
            for x in [200,225,250,275]:line([(x,211),(x+35,270)],"#b59054",3)
            line([(182,205),(163,184),(176,153),(203,149),(193,125),(213,101),(244,100),(236,81),(257,44),(280,82),(278,105),(309,112),(318,137),(306,150),(337,163),(345,190),(327,205),(182,205)],width=6)
        elif category=="drink":
            line([(174,117),(195,319),(326,319),(347,117),(174,117)],"#272722",7)
            d.ellipse((160,97,360,130),outline="#272722",width=6)
            line([(265,105),(284,43),(338,43)],"#e33c36",7)
            d.ellipse((218,184,306,253),outline="#e33c36",width=6)
        elif category=="nuggets":
            for box in [(112,94,222,176),(257,79,370,170),(147,217,262,294),(287,210,394,295)]:
                d.rounded_rectangle(box,radius=26,outline="#272722",width=7)
                d.arc((box[0]+15,box[1]+15,box[2]-15,box[3]-15),180,255,fill="#b59054",width=3)
        elif category=="coffee":
            line([(140,160),(155,266),(179,287),(284,287),(308,266),(325,160)],width=7)
            d.ellipse((137,140,327,184),outline="#272722",width=7)
            d.arc((295,171,393,266),270,90,fill="#272722",width=7)
            d.arc((110,268,357,317),0,180,fill="#272722",width=6)
            for x in [183,232,281]:line([(x,119),(x-9,99),(x+5,80),(x,57)],width=5)
        else:
            line([(120,210),(256,75),(394,210),(120,210)]);line([(155,212),(155,329),(358,329),(358,212)])
            d.rectangle((230,250,285,329),outline="#272722",width=6)
        im.save(root/f"{category}.png")
    return root

if __name__=="__main__":print(generate())
