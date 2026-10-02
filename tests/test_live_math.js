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
const caseInsensitive = math.position(rooms,'sample_01',[100,20],[]);
assert.equal(caseInsensitive.mode,'auto','scene lookup is case-insensitive like the bridge room table');
close(caseInsensitive.point[0],-700);close(caseInsensitive.point[1],500);

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

const nativeMap={x:[2,0,10],y:[0,3,5]};
const native=math.position({},'Unmapped_01',[12,15],[],[7,8],nativeMap);
assert.equal(native.mode,'native');
close(native.point[0],29);close(native.point[1],24);
const legacySketchPoint=[-1413.38,1699.94];
const legacy=math.position({},'Room_CrowCourt',[30,26],[],legacySketchPoint,nativeMap,'legacy-room-transform');
assert.equal(legacy.mode,'legacy','legacy bridge coordinates are already Sketch coordinates');
close(legacy.point[0],legacySketchPoint[0]);close(legacy.point[1],legacySketchPoint[1]);
assert.equal(math.position({},'Unmapped_01',[12,15],[],[NaN,8],nativeMap),null,
  'invalid native coordinates must not become a marker');
const manuallyCalibrated=math.position(rooms,'Sample_01',[110,20],[first],[7,8],nativeMap);
assert.equal(manuallyCalibrated.mode,'anchored','an explicit room calibration takes precedence over native geometry');
close(manuallyCalibrated.point[0],-705);close(manuallyCalibrated.point[1],510);
const legacyFallback=math.position(rooms,'Sample_01',[120,20],[],null,nativeMap);
assert.equal(legacyFallback.mode,'auto','older bridge clients keep using researched room transforms');

console.log('Live map position math: all assertions passed.');
