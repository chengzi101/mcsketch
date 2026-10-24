type Point = {x:number,y:number};
type Stroke = {points:Point[],color:string,width:number,erase:boolean};
export class Board {
  canvas:HTMLCanvasElement; ctx:CanvasRenderingContext2D;
  strokes:Stroke[]=[]; current:Stroke|null=null; color='#272722'; width=7; erase=false;
  onChange=()=>{};
  constructor(canvas:HTMLCanvasElement) {
    this.canvas=canvas; this.ctx=canvas.getContext('2d')!;
    canvas.width=1000; canvas.height=740;
    canvas.addEventListener('pointerdown',e=>{
      if(e.button!==0) return;
      e.preventDefault();
      canvas.setPointerCapture(e.pointerId);
      this.current={points:[this.point(e)],color:this.color,width:this.width,erase:this.erase};
      this.paint();
    });
    canvas.addEventListener('pointermove',e=>{
      if(!this.current) return;
      this.current.points.push(this.point(e)); this.paint();
    });
    const end=()=>{if(this.current){this.strokes.push(this.current);this.current=null;this.onChange();this.paint();}};
    canvas.addEventListener('pointerup',end); canvas.addEventListener('pointercancel',end);
    this.paint();
  }
  point(e:PointerEvent):Point {const r=this.canvas.getBoundingClientRect();return{x:(e.clientX-r.left)*1000/r.width,y:(e.clientY-r.top)*740/r.height};}
  paint() {
    const c=this.ctx;c.fillStyle='white';c.fillRect(0,0,1000,740);
    for(const s of [...this.strokes,...(this.current?[this.current]:[])]) {
      c.strokeStyle=s.erase?'white':s.color;c.fillStyle=c.strokeStyle;c.lineWidth=s.width;c.lineCap='round';c.lineJoin='round';
      c.beginPath();c.moveTo(s.points[0].x,s.points[0].y);
      for(const p of s.points)c.lineTo(p.x,p.y);
      if(s.points.length===1){c.arc(s.points[0].x,s.points[0].y,s.width/2,0,Math.PI*2);c.fill();} else c.stroke();
    }
  }
  undo(){this.strokes.pop();this.paint();this.onChange();}
  clear(){this.strokes=[];this.current=null;this.paint();this.onChange();}
  png(){return this.canvas.toDataURL('image/png');}
  get empty(){return this.strokes.length===0;}
}
