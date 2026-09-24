/* Room-scoped world -> Sketch math. No native GameMap coordinates are used. */
(function (root) {
  'use strict';
  const median = values => {const sorted=[...values].sort((a,b)=>a-b);return sorted[Math.floor(sorted.length/2)];};
  function priorForScene(rooms,scene){
    if(rooms[scene])return {matrix:matrixOf(rooms[scene]),confidence:'room'};
    const prefix=scene.split('_')[0];
    const trusted=Object.entries(rooms).filter(([,room])=>(room.anchors||0)>=3);
    const area=trusted.filter(([name])=>name.split('_')[0]===prefix).map(([,room])=>room);
    const all=trusted.map(([,room])=>room);
    const candidates=area.length?area:all;
    if(!candidates.length)return null;
    return {matrix:{real:median(candidates.map(r=>r.real)),imag:median(candidates.map(r=>r.imag)),reflected:candidates.filter(r=>r.reflected).length>candidates.length/2},confidence:area.length?'area':'global'};
  }
  function matrixOf(room){return {real:room.real,imag:room.imag,reflected:!!room.reflected};}
  function apply(point,source,sketch,matrix){
    const dx=point[0]-source[0],dy=(point[1]-source[1])*(matrix.reflected?-1:1);
    return [sketch[0]+matrix.imag*dx+matrix.real*dy,
            sketch[1]+matrix.real*dx-matrix.imag*dy];
  }
  function solveAnchors(anchors,matrix){
    if(!Array.isArray(anchors)||anchors.length!==2)return null;
    const [a,b]=anchors,dx=b.source[0]-a.source[0],dy=b.source[1]-a.source[1];
    const targetX=b.sketch[1]-a.sketch[1],targetY=b.sketch[0]-a.sketch[0];
    const worldDistance=Math.hypot(dx,dy),mapDistance=Math.hypot(targetX,targetY);
    if(worldDistance<25||mapDistance<12)return null;
    const priorAngle=Math.atan2(matrix.imag,matrix.real),priorScale=Math.hypot(matrix.real,matrix.imag),candidates=[];
    for(const reflected of [!!matrix.reflected,!matrix.reflected]){
      const sourceY=dy*(reflected?-1:1),denominator=dx*dx+sourceY*sourceY;
      const real=(targetX*dx+targetY*sourceY)/denominator;
      const imag=(targetY*dx-targetX*sourceY)/denominator;
      const scale=Math.hypot(real,imag);
      if(!Number.isFinite(scale)||scale<.1||scale>1.5)continue;
      const angle=Math.atan2(imag,real),angleError=Math.abs((angle-priorAngle+Math.PI)%(2*Math.PI)-Math.PI);
      if(angleError>Math.PI/180*35)continue;
      candidates.push({score:angleError+Math.abs(Math.log(scale/priorScale))*.05,matrix:{...matrix,real,imag,reflected}});
    }
    return candidates.sort((a,b)=>a.score-b.score)[0]?.matrix||null;
  }
  function position(rooms,scene,world,anchors){
    const room=rooms[scene],prior=priorForScene(rooms,scene);
    if(!prior)return null;
    if(anchors?.length){
      const matrix=anchors.length===2?solveAnchors(anchors,prior.matrix):prior.matrix;
      if(!matrix)return null;
      return {point:apply(world,anchors[0].source,anchors[0].sketch,matrix),
              mode:anchors.length===2?'calibrated':'anchored',confidence:prior.confidence};
    }
    if(!room)return null;
    return {point:apply(world,room.source,[room.sketch[1],room.sketch[0]],matrixOf(room)),mode:'auto',confidence:room.quality||'multi-landmark'};
  }
  const api={priorForScene,apply,solveAnchors,position};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.SilksongLiveMath=api;
})(typeof window!=='undefined'?window:globalThis);
