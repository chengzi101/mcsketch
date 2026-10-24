import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Board} from '../src/components/board.ts';

function fixture(){
  const handlers={};
  const ctx={fillRect(){},beginPath(){},moveTo(){},lineTo(){},arc(){},fill(){},stroke(){}};
  const canvas={getContext:()=>ctx,addEventListener:(name,fn)=>{handlers[name]=fn;},setPointerCapture(){},getBoundingClientRect:()=>({left:0,top:0,width:1000,height:740})};
  let prevented=false;
  const event=(x=10,y=10)=>({button:0,pointerId:1,clientX:x,clientY:y,preventDefault(){prevented=true;}});
  return{board:new Board(canvas),handlers,event,prevented:()=>prevented,ctx};
}
test('drawing suppresses browser text drag and retains the complete pointer path',()=>{
  const f=fixture();let changes=0;f.board.onChange=()=>changes++;
  f.handlers.pointerdown(f.event());f.handlers.pointermove(f.event(300,200));f.handlers.pointermove(f.event(600,300));f.handlers.pointerup();
  assert.equal(f.prevented(),true);assert.equal(changes,1);
  assert.deepEqual(f.board.strokes[0].points,[{x:10,y:10},{x:300,y:200},{x:600,y:300}]);
});
test('eraser is undoable and a cancelled pointer still ends the active stroke',()=>{
  const f=fixture();f.handlers.pointerdown(f.event());f.handlers.pointerup();
  f.board.erase=true;f.handlers.pointerdown(f.event(30,30));f.handlers.pointermove(f.event(80,80));f.handlers.pointercancel();
  assert.equal(f.board.current,null);assert.equal(f.board.strokes[1].erase,true);
  f.board.undo();assert.equal(f.board.strokes.length,1);assert.equal(f.board.strokes[0].erase,false);
  f.board.clear();assert.equal(f.board.empty,true);
});
