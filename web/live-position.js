/* Room-scoped world -> Sketch math. No native GameMap coordinates are used. */
(function (root) {
  'use strict';
  const median = values => {const sorted=[...values].sort((a,b)=>a-b);return sorted[Math.floor(sorted.length/2)];};
  function priorForScene(rooms,scene){
    if(rooms[scene])return {matrix:matrixOf(rooms[scene]),confidence:'room'};
    const prefix=scene.split('_')[0];
    const area=Object.entries(rooms).filter(([name,room])=>name.split('_')[0]===prefix&&!room.reflected).map(([,room])=>room);
    const all=Object.values(rooms).filter(room=>!room.reflected);
    const candidates=area.length?area:all;
    if(!candidates.length)return null;
    return {matrix:{real:median(candidates.map(r=>r.real)),imag:median(candidates.map(r=>r.imag)),reflected:false},confidence:area.length?'area':'global'};
  }
  function matrixOf(room){return {real:room.real,imag:room.imag,reflected:!!room.reflected};}
  function apply(point,source,sketch,matrix){
    const dx=point[0]-source[0],dy=(point[1]-source[1])*(matrix.reflected?-1:1);
    return [sketch[0]+matrix.imag*dx+matrix.real*dy,
            sketch[1]+matrix.real*dx-matrix.imag*dy];
  }
  function refine(anchors,matrix){
    if(!Array.isArray(anchors)||anchors.length!==2)return null;
    const [a,b]=anchors,world=Math.hypot(b.source[0]-a.source[0],b.source[1]-a.source[1]);
    if(world<35)return null;
    const expected=apply(b.source,a.source,a.sketch,matrix);
    const ex=expected[1]-a.sketch[1],ey=expected[0]-a.sketch[0];
    const ox=b.sketch[1]-a.sketch[1],oy=b.sketch[0]-a.sketch[0];
    const e2=ex*ex+ey*ey,actual=Math.hypot(ox,oy);
    if(e2<225||actual<15)return null;
    const scale=(ex*ox+ey*oy)/e2;
    const sideways=Math.abs(ex*oy-ey*ox)/Math.sqrt(e2);
    if(scale<.5||scale>1.5||sideways>Math.max(8,actual*.2))return null;
    return {...matrix,real:matrix.real*scale,imag:matrix.imag*scale};
  }
  function position(rooms,scene,world,anchors){
    const room=rooms[scene],prior=priorForScene(rooms,scene);
    if(!prior)return null;
    if(anchors?.length){
      const matrix=anchors.length===2?refine(anchors,prior.matrix):prior.matrix;
      if(!matrix)return null;
      return {point:apply(world,anchors[0].source,anchors[0].sketch,matrix),
              mode:anchors.length===2?'refined':'anchored',confidence:prior.confidence};
    }
    if(!room)return null;
    return {point:apply(world,room.source,[room.sketch[1],room.sketch[0]],matrixOf(room)),mode:'auto',confidence:'room'};
  }
  const api={priorForScene,apply,refine,position};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.SilksongLiveMath=api;
})(typeof window!=='undefined'?window:globalThis);
