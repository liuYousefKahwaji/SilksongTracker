const assert = require('node:assert/strict');
const math = require('../web/live-position.js');

const rooms = {
  Sample_01: {source:[100,20],sketch:[500,-700],real:.6,imag:0,reflected:false,anchors:4},
  Other_01: {source:[0,0],sketch:[800,-900],real:.65,imag:0,reflected:false,anchors:3},
};
const close = (actual,expected) => assert.ok(Math.abs(actual-expected)<1e-8,`${actual} != ${expected}`);

const automatic = math.position(rooms,'Sample_01',[100,20],[]);
assert.equal(automatic.mode,'auto');
close(automatic.point[0],-700);close(automatic.point[1],500);

const first={source:[110,20],sketch:[-705,510]};
const anchored=math.position(rooms,'Sample_01',[110,20],[first]);
assert.equal(anchored.mode,'anchored');
close(anchored.point[0],-705);close(anchored.point[1],510);
close(math.position(rooms,'Sample_01',[120,20],[first]).point[1],516);

const fallback=math.position(rooms,'Unknown_02',[10,10],[{source:[10,10],sketch:[-800,700]}]);
assert.equal(fallback.confidence,'global');
close(fallback.point[0],-800);close(fallback.point[1],700);

assert.equal(math.solveAnchors([first,{source:[120,20],sketch:[-705,516]}],math.priorForScene(rooms,'Sample_01').matrix),null,
  'nearby points must not amplify clicking error');
assert.equal(math.solveAnchors([first,{source:[160,20],sketch:[-670,510]}],math.priorForScene(rooms,'Sample_01').matrix),null,
  'a direction inconsistent with the room map must be rejected');

const second={source:[160,20],sketch:[-705,545]};
const refined=math.position(rooms,'Sample_01',[160,20],[first,second]);
assert.equal(refined.mode,'calibrated');
close(refined.point[0],second.sketch[0]);close(refined.point[1],second.sketch[1]);
close(math.position(rooms,'Sample_01',[170,20],[first,second]).point[1],552);

console.log('Live calibration math: 8 checks passed.');
