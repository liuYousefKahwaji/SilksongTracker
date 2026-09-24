/* Based on Hollow Tracker: Leaflet CRS.Simple, offline tiles, icon markers,
 * stable pin links, category filters and popups. Source positions are preserved. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const node = (tag, cls, text) => {const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e;};
  let data, map, pins, labels, connections, entrances, tileLayer, selected=null, category=null, scope=null;
  let style=new URLSearchParams(location.search).get('style')||localStorage.getItem('ss.map.style')||'sketch';
  if(style!=='real')style='sketch';
  const meta=()=>style==='sketch'?data.sketch:data.image;
  const position=m=>{const p=m[style==='sketch'?'pos2':'pos'];return Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)?p:null;};
  const objects=new Map(), cats=new Map(), shown=new Set(), interiorByMember=new Map(), sketchGroupByMember=new Map();
  const sketchGroups=[];
  const liveMath=window.SilksongLiveMath;
  let live=null,livePin=null,calibration={},pendingAnchor=null,autoRooms={},calibrationNotice='',noticeUntil=0;
  try {calibration=JSON.parse(localStorage.getItem('ss.map.live.calibration.v2')||'{}')||{};} catch {}
  function liveDetail(text){
    if(pendingAnchor)text='Click Hornet’s exact spot on Sketch to set calibration point '+(pendingAnchor.index+1)+'.';
    else if(Date.now()<noticeUntil)text=calibrationNotice;
    $('#live-detail').textContent=text;
  }
  function liveNotice(text){calibrationNotice=text;noticeUntil=Date.now()+6500;liveDetail(text);}
  function redrawLive(){
    const hide=()=>{if(livePin){map.removeLayer(livePin);livePin=null;}};
    const connected=live?.connected&&live.position;
    $('#live-status').textContent=connected?'Live: connected':'Live: waiting';
    $('#calibrate-hornet').disabled=!connected||style!=='sketch';
    $('#center-hornet').disabled=true;
    if(!connected){hide();liveDetail('Waiting for the optional local bridge.');return;}
    const scene=live.position.scene,anchors=calibration[scene]||[];
    $('#calibrate-hornet').textContent=anchors.length===1?'Capture calibration point 2':anchors.length===2?'Replace calibration':'Calibrate current room';
    if(style!=='sketch'){hide();liveDetail('Live position appears on Sketch only.');return;}
    const located=liveMath.position(autoRooms,scene,[live.position.x,live.position.y],anchors);
    if(!located){hide();liveDetail('No automatic map anchor for this room. Calibrate two positions here to fit Hornet’s movement.');return;}
    const p=located.point;
    const bounds=L.latLngBounds(data.sketch.bounds);
    if(!p||!bounds.contains(p)){hide();liveDetail('Position is outside Sketch. Clear and redo this room’s calibration.');return;}
    if(livePin)livePin.setLatLng(p);
    else {
      livePin=L.marker(p,{zIndexOffset:10000,icon:L.icon({iconUrl:'/hornet-head-source.png',className:'hornet-live',iconSize:[36,48],iconAnchor:[18,47],popupAnchor:[0,-36]}),title:'Hornet · live position',alt:'Hornet live position'}).addTo(map);
      livePin.bindPopup('Hornet · live position');
    }
    $('#center-hornet').disabled=false;
    const room=autoRooms[scene];
    liveDetail(located.mode==='auto'&&room.anchors>=3?'Auto-located from '+room.anchors+' matched map points.':located.mode==='auto'&&room.anchors===2?'Auto-located from two matched points; exact movement may vary.':located.mode==='auto'?'Approximate position aligned to one matched map point.':located.mode==='calibrated'?'Two-point calibration saved; movement scale and direction now follow both captures.':room?.anchors>=3?'First point saved; capture a second position to fit movement scale and direction.':'First point saved; movement remains approximate until point 2.');
  }
  async function pollLive(){
    try {const response=await fetch('/api/live-position',{cache:'no-store'});if(response.ok)live=await response.json();else live=null;}
    catch {live=null;}
    if(map&&data){
      redrawLive();
    }
  }
  let hidden=new Set(), query='', onlyLeft=false, manual={}, manualKey='';
  try {hidden=new Set(JSON.parse(localStorage.getItem('ss.map.hidden.v2')||'null')||[]);onlyLeft=localStorage.getItem('ss.map.left')==='1';} catch {}
  const NEVER_DIM=new Set(['benches','bellway','ventrica','maps']);
  function image(file, alt='') {const e=node('img');e.src='/map/icons/'+encodeURIComponent(file);e.alt=alt;return e;}
  function message(text) {$('#map-message').textContent=text;$('#map-message').hidden=!text;}
  function persist(){localStorage.setItem('ss.map.hidden.v2',JSON.stringify([...hidden]));localStorage.setItem('ss.map.left',onlyLeft?'1':'0');}
  function loadManual(){
    const key='ss.map.manual.v1.'+(data.saveKey||'no-save');
    if(key===manualKey)return;
    manualKey=key;manual={};
    try {const saved=JSON.parse(localStorage.getItem(key)||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))for(const [id,value] of Object.entries(saved))if(value==='left'||value==='complete')manual[id]=value;} catch {}
  }
  function manualStatus(m){return m.tracking==='unverified'&&manual[m.id]||m.status;}
  function setManual(m,value){
    if(value)manual[m.id]=value;else delete manual[m.id];
    try {localStorage.setItem(manualKey,JSON.stringify(manual));}
    catch {$('#marks-status').textContent='Browser storage is unavailable. Export a backup before closing this page.';}
    if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
    draw();
  }
  function exportMarks(){
    const marks=Object.fromEntries(Object.entries(manual).filter(([id,value])=>data.markers.some(m=>m.id===id&&m.tracking==='unverified')&&['left','complete'].includes(value)));
    const backup={format:'silksong-tracker-map-marks',version:1,saveKey:data.saveKey||'no-save',slot:data.slot??null,marks};
    const url=URL.createObjectURL(new Blob([JSON.stringify(backup,null,2)+'\n'],{type:'application/json'}));
    const link=node('a');link.href=url;link.download='silksong-map-marks-slot-'+(data.slot??'none')+'.json';document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    $('#marks-status').textContent='Exported '+Object.keys(marks).length+' manual mark(s). This file contains no save data or location names.';
  }
  async function importMarks(file){
    if(!file)return;
    try {
      if(file.size>1024*1024)throw Error('Backup is too large.');
      const backup=JSON.parse(await file.text());
      if(!backup||backup.format!=='silksong-tracker-map-marks'||backup.version!==1||!backup.marks||typeof backup.marks!=='object'||Array.isArray(backup.marks))throw Error('Not a supported manual-mark backup.');
      const permitted=new Set(data.markers.filter(m=>m.tracking==='unverified').map(m=>m.id));
      const entries=Object.entries(backup.marks);
      if(entries.some(([id,value])=>!permitted.has(id)||!['left','complete'].includes(value)))throw Error('Backup contains invalid or unknown marks.');
      const otherSave=backup.saveKey!==data.saveKey;
      const target=data.hasSave?'selected slot '+data.slot:'the no-save profile';
      const question='Replace all manual marks for '+target+' with '+entries.length+' mark(s) from this backup?'+(otherSave?'\n\nWarning: it was exported for a different save or computer.':'');
      if(!window.confirm(question)){$('#marks-status').textContent='Import cancelled; current marks were kept.';return;}
      const replacement=Object.fromEntries(entries);
      localStorage.setItem(manualKey,JSON.stringify(replacement));manual=replacement;
      for(const m of data.markers)if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
      draw();$('#marks-status').textContent='Imported '+entries.length+' manual mark(s) for '+target+'.';
    }catch(err){$('#marks-status').textContent='Import failed: '+err.message;}
  }
  function resetLayers(){hidden=new Set(['shortcut','permFlags','rosary','shard','rosaryitem','sharditem','tradable','memento','silkeater','npc','wish','questitem','arena']);persist();}
  function title(m){return m.name.replace(/^(Tool|Ability|Upgrade|Boss)\s*-\s*/i,'');}
  function matches(m){return (!scope||scope.has(m.id))&&(!category||m.cat===category)&&(!query||(m.name+' '+cats.get(m.cat).name).toLowerCase().includes(query));}
  function eligible(m){if(m.id===selected)return true;if(onlyLeft&&manualStatus(m)!=='left')return false;if(query||category||scope)return matches(m);return !hidden.has(m.cat);}
  function visible(m){if(!position(m))return false;if(style==='sketch'&&sketchGroupByMember.has(m.id))return false;return eligible(m);}
  function icon(m){const size=map&&map.getZoom()<1?16:28;return L.icon({iconUrl:'/map/icons/'+encodeURIComponent(m.icon),iconSize:[size,size],iconAnchor:[size/2,size/2],popupAnchor:[0,-size/2],className:'pin'+(manualStatus(m)==='complete'&&!NEVER_DIM.has(m.cat)?' done':'')+(selected===m.id?' selected':'')});}
  function popup(m){
    const box=node('div'),heading=node('div','popup-heading');
    heading.append(image(m.icon),node('b',null,title(m)));box.append(heading,node('div','popup-category',cats.get(m.cat).name));
    const status=m.tracking==='reference'?'Reference location':m.tracking==='unverified'&&manual[m.id]?'Manually marked '+(manual[m.id]==='complete'?'complete':'incomplete'):m.tracking==='unverified'?'Tracking needs verification':!data.hasSave?'No save loaded':m.status==='unavailable'?'Alternative already owned':m.status==='complete'?'Collected / completed':m.status==='left'?'Not completed':'Save data unavailable';
    box.append(node('span','popup-state '+manualStatus(m),status));
    if(m.trackingNote)box.append(node('p','popup-note',m.trackingNote));
    if(m.tracking==='unverified'){
      const controls=node('div','popup-manual');
      const done=node('button',null,'Mark done'),left=node('button',null,'Mark left');
      done.onclick=e=>{L.DomEvent.stop(e);setManual(m,'complete');};left.onclick=e=>{L.DomEvent.stop(e);setManual(m,'left');};controls.append(done,left);
      if(manual[m.id]){const clear=node('button',null,'Clear mark');clear.onclick=e=>{L.DomEvent.stop(e);setManual(m,null);};controls.append(clear);}
      box.append(controls,node('p','popup-note','Manual marks stay in this browser for this save; they do not change the game file.'));
    }
    if(Array.isArray(m.acts))box.append(node('p','popup-note','Act '+m.acts.join(' / ')));
    const note=typeof m.note==='string'?m.note:typeof m.notes==='string'?m.notes:'';
    if(note)box.append(node('p','popup-note',note));
    const links=node('div','popup-links');
    for(const entry of m.entries||[]){const a=node('a',null,'Open '+entry.name+' in checklist ↗');a.href='/?focus='+encodeURIComponent(entry.id);links.append(a);}
    const own=node('a',null,'Link to this location');own.href='/map?focus='+encodeURIComponent(m.id)+'&style='+style;links.append(own);box.append(links);
    if(['bellway','ventrica'].includes(m.cat)){
      box.append(node('p','popup-note','Other '+cats.get(m.cat).name.toLowerCase()));
      const travel=node('div','popup-travel');
      for(const peer of data.markers.filter(p=>p.cat===m.cat&&p.id!==m.id)){const b=node('button',null,peer.name.replace(/^.*? - /,''));b.onclick=()=>focus(peer);travel.append(b);}box.append(travel);
    }
    return box;
  }
  function marker(m){
    if(!objects.has(m.id)){
      const pin=L.marker(position(m),{icon:icon(m),title:title(m),alt:title(m),riseOnHover:true,keyboard:true});
      pin.bindPopup(()=>popup(m),{maxWidth:330,autoPan:true});
      pin.on('click',()=>{selected=m.id;for(const item of data.markers)if(objects.has(item.id))objects.get(item.id).setIcon(icon(item));const url=new URL(location.href);url.searchParams.set('focus',m.id);url.searchParams.set('style',style);history.replaceState(null,'',url);});
      objects.set(m.id,pin);
    }
    return objects.get(m.id);
  }
  function sketchGroupPopup(group,members){
    const box=node('div'),heading=node('div','popup-heading');
    heading.append(image(members[0].icon),node('b',null,group.interior?.name&&group.interior.name!=='Interior'?group.interior.name:'Locations here'));
    box.append(heading,node('div','popup-category',members.length+' location'+(members.length===1?'':'s')+' at this map point'));
    const list=node('div','sketch-stack-list');
    for(const m of members){
      const item=node('button','sketch-stack-item');item.append(image(m.icon),node('span',null,title(m)));
      if(manualStatus(m)==='complete')item.append(node('small',null,'✓'));
      item.onclick=()=>focus(m);list.append(item);
    }
    box.append(list);
    if(group.interior){const open=node('button','interior-open','View in Screenshots');open.onclick=()=>openInterior(group.interior);box.append(open);}
    return box;
  }
  function drawSketchGroups(){
    entrances.clearLayers();
    if(style!=='sketch')return;
    for(const group of sketchGroups){
      const members=group.members.filter(eligible);
      if(!members.length)continue;
      if(members.length===1){
        const m=members[0],pin=L.marker(group.pos,{icon:icon(m),title:title(m),alt:title(m),keyboard:true,riseOnHover:true});
        pin.on('click',()=>focus(m));pin.addTo(entrances);continue;
      }
      const representative=members[0],size=24;
      const html='<img alt="" src="/map/icons/'+encodeURIComponent(representative.icon)+'"><small>'+members.length+'</small>';
      const stackIcon=L.divIcon({className:'sketch-stack'+(members.every(m=>manualStatus(m)==='complete')?' done':''),html,iconSize:[size,size],iconAnchor:[size/2,size/2]});
      const pin=L.marker(group.pos,{icon:stackIcon,title:members.length+' locations',alt:members.length+' locations',keyboard:true,riseOnHover:true});
      pin.bindPopup(()=>sketchGroupPopup(group,members),{maxWidth:300});pin.addTo(entrances);
      pin.getElement()?.setAttribute('aria-label',members.length+' locations at this map point');
    }
  }
  function openInterior(interior){
    selected=null;setStyle('real');
    const all=interior.members.map(id=>data.markers.find(m=>m.id===id)).filter(Boolean),members=all.filter(eligible);
    const points=members.map(m=>L.latLng(m.pos));
    if(points.length)map.fitBounds(L.latLngBounds(points),{padding:[90,90],maxZoom:3});
    message((interior.name==='Interior'?'Detailed map':interior.name)+' · '+members.length+' visible location'+(members.length===1?'':'s'));
    history.replaceState(null,'','/map?interior='+encodeURIComponent(interior.id)+'&style=real');
  }
  function draw(){
    const wanted=new Set(data.markers.filter(visible).map(m=>m.id));
    for(const id of shown)if(!wanted.has(id)){pins.removeLayer(objects.get(id));shown.delete(id);}
    for(const m of data.markers)if(wanted.has(m.id)&&!shown.has(m.id)){marker(m).addTo(pins);shown.add(m.id);}
    drawSketchGroups();
    $('#visible-count').textContent=data.markers.filter(m=>position(m)&&eligible(m)).length+' locations';
    const reference=data.markers.filter(m=>m.tracking==='reference').length,unverified=data.markers.filter(m=>m.tracking==='unverified').length;
    $('#tracking-summary').textContent=reference+' reference locations · '+unverified+' objectives awaiting verified save rules. These can be marked manually; Only left includes confirmed and manually marked incomplete locations. An explicitly focused pin stays visible.';
    $('#save-status').textContent=data.saveError?'Slot '+data.slot+' · save unreadable':data.hasSave?'Slot '+data.slot+' · '+data.markers.filter(m=>m.status==='complete').length+' completed':'No save loaded';
    $('#save-status').title=data.saveError||'';
    const result=$('#results'); result.replaceChildren();result.hidden=!(query||category||scope);
    if(!result.hidden){
      const found=data.markers.filter(m=>matches(m)&&(!onlyLeft||manualStatus(m)==='left'||m.id===selected));
      result.append(node('h2',null,found.length+' locations'));
      for(const m of found.slice(0,100)){const b=node('button','result'),label=node('span',null,title(m));label.append(node('small',null,cats.get(m.cat).name+(!position(m)?' · Screenshots only':style==='sketch'&&sketchGroupByMember.has(m.id)?' · Stacked location':'')));b.append(image(m.icon),label);b.onclick=()=>focus(m);result.append(b);}
      if(!found.length)result.append(node('p','empty-results','No mapped location matches this search.'));
      if(found.length>100)result.append(node('p','help','Showing the first 100 results. All matching pins remain on the map.'));
    }
  }
  function focus(m){
    const inside=interiorByMember.get(m.id),stacked=sketchGroupByMember.has(m.id),missing=!position(m);
    if(missing||(style==='sketch'&&stacked))setStyle('real');
    selected=m.id;draw();map.setView(position(m),Math.min(3,meta().maxZoom),{animate:false});
    const pin=marker(m);pin.setIcon(icon(m));pin.openPopup();
    message(missing?'This location has no researched sketch position; showing Screenshots.':inside?'Opened its exact location in Screenshots.':'');history.replaceState(null,'','/map?focus='+encodeURIComponent(m.id)+'&style='+style);
  }
  function setStyle(next){
    const oldCentre=map.getCenter(),oldZoom=map.getZoom(),oldMax=meta().maxZoom;
    const anchor=data.markers.filter(m=>Array.isArray(m.pos2)&&m.pos2.every(Number.isFinite)).sort((a,b)=>oldCentre.distanceTo(L.latLng(position(a)))-oldCentre.distanceTo(L.latLng(position(b))))[0];
    const oldAnchor=anchor&&position(anchor);
    style=next;localStorage.setItem('ss.map.style',style);
    pendingAnchor=null;
    const info=meta(),bounds=L.latLngBounds(info.bounds);
    if(tileLayer)map.removeLayer(tileLayer);
    map.stop();map.setMaxBounds(null);map.setMaxZoom(info.maxZoom);map.stop();
    const valid=new Set(style==='sketch'?info.validTiles:data.validTiles),blank='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    const Tiles=L.TileLayer.extend({getTileUrl(c){return valid.has(c.z+'/'+c.x+'_'+c.y)?L.TileLayer.prototype.getTileUrl.call(this,c):blank;}});
    tileLayer=new Tiles(info.url,{tileSize:info.tileSize,minZoom:-2,minNativeZoom:0,maxNativeZoom:info.maxZoom,maxZoom:info.maxZoom,noWrap:true,bounds,keepBuffer:2,attribution:'Map: RainingChain & IdoManti · © Team Cherry'}).addTo(map);
    connections.clearLayers();
    if(style==='real')for(const line of data.connections||[]){
      const cls=line.kind==='smallGaps'?'short':line.kind==='largeGapsConnectingOverMaps'?'over-map':'over-void';
      L.polyline([line.from,line.to],{className:'room-connection '+cls,color:'#9ba7aa',weight:cls==='short'?2:3,opacity:cls==='over-map'?.55:.8,dashArray:cls==='short'?'3 4':'7 7',interactive:false}).addTo(connections);
    }
    for(const m of data.markers)if(objects.has(m.id)&&position(m))objects.get(m.id).setLatLng(position(m));
    labels.clearLayers();
    for(const label of data.labels){
      if(!position(label)||label.name!==label.name.toUpperCase())continue;
      const text=node('span',null,label.name);
      L.marker(position(label),{interactive:false,keyboard:false,icon:L.divIcon({className:'map-label',html:text.outerHTML,iconSize:null})}).addTo(labels);
    }
    $('#map-style').textContent=style==='sketch'?'Screenshots':'Sketch';
    $('#map-style').setAttribute('aria-label','Switch to '+(style==='sketch'?'Screenshots':'Sketch')+' map');
    $('#map').setAttribute('data-map-style',style);
    const chosen=data.markers.find(m=>m.id===selected);
    map.closePopup();draw();
    if(chosen&&style==='sketch'&&sketchGroupByMember.has(chosen.id)){
      const group=sketchGroupByMember.get(chosen.id);selected=null;draw();map.setView(group.pos,Math.min(oldZoom,info.maxZoom),{animate:false});
      history.replaceState(null,'','/map?style=sketch');
    }else if(chosen&&position(chosen)){map.setView(position(chosen),Math.min(oldZoom,info.maxZoom),{animate:false});marker(chosen).openPopup();}
    else if(anchor){const p=position(anchor);map.setView([p[0]+oldCentre.lat-oldAnchor[0],p[1]+oldCentre.lng-oldAnchor[1]],Math.min(oldZoom+info.maxZoom-oldMax,info.maxZoom),{animate:false});}
    else map.fitBounds(bounds);
    map.setMaxBounds(bounds.pad(.12));
    message(chosen&&style==='sketch'&&sketchGroupByMember.has(chosen.id)?'This location shares a Sketch point. Click the numbered icon to choose it.':chosen&&!position(chosen)?'This location has no researched sketch position. Switch to Screenshots to see it.':'');
    const url=new URL(location.href);url.searchParams.set('style',style);history.replaceState(null,'',url);
    tidyLabels();
    redrawLive();
  }
  function buildLayers(){
    const host=$('#layers');host.replaceChildren();
    for(const group of data.groups){
      const section=node('section','layer-group'),heading=node('label','group-title'),check=node('input');check.type='checkbox';
      const members=data.categories.filter(c=>c.group===group.id);
      check.checked=members.some(c=>!hidden.has(c.id));
      check.onchange=()=>{for(const c of members)check.checked?hidden.delete(c.id):hidden.add(c.id);persist();buildLayers();draw();};
      heading.append(check,image(group.icon),node('span',null,group.name));section.append(heading);
      for(const c of members){
        const row=node('label','layer-row'),cb=node('input');cb.type='checkbox';cb.checked=!hidden.has(c.id);
        cb.onchange=()=>{cb.checked?hidden.delete(c.id):hidden.add(c.id);selected=null;persist();draw();};
        row.append(cb,image(c.icon),node('span',null,c.name),node('small',null,String(data.markers.filter(m=>m.cat===c.id).length)));section.append(row);
      }host.append(section);
    }
  }
  function tidyLabels(){
    const occupied=[];
    document.querySelectorAll('.map-label').forEach(label=>{
      label.style.visibility='visible';
      const r=label.querySelector('span').getBoundingClientRect();
      if(occupied.some(b=>r.left<b.right+5&&r.right>b.left-5&&r.top<b.bottom+4&&r.bottom>b.top-4))label.style.visibility='hidden';
      else occupied.push(r);
    });
  }
  function indexGroups(){
    interiorByMember.clear();sketchGroupByMember.clear();sketchGroups.length=0;
    for(const interior of data.interiors||[])for(const id of interior.members)interiorByMember.set(id,interior);
    const byPosition=new Map();
    for(const m of data.markers)if(Array.isArray(m.pos2)&&m.pos2.length===2){const key=JSON.stringify(m.pos2);if(!byPosition.has(key))byPosition.set(key,[]);byPosition.get(key).push(m);}
    for(const members of byPosition.values())if(members.length>1){
      const group={pos:members[0].pos2,members,interior:interiorByMember.get(members[0].id)};
      sketchGroups.push(group);for(const m of members)sketchGroupByMember.set(m.id,group);
    }
  }
  async function boot(){
    try{
      const res=await fetch('/api/map');if(!res.ok)throw Error('Map data could not be loaded.');data=await res.json();
      try {const transforms=await fetch('/api/live-transforms').then(r=>r.json());autoRooms=transforms.rooms||{};} catch {}
      loadManual();
      for(const c of data.categories)cats.set(c.id,c);
      indexGroups();
      if(!localStorage.getItem('ss.map.hidden.v2'))resetLayers();
      const bounds=L.latLngBounds(meta().bounds);
      map=L.map('map',{crs:L.CRS.Simple,minZoom:-1,maxZoom:meta().maxZoom,zoomSnap:.5,zoomAnimation:false,maxBounds:bounds.pad(.12),maxBoundsViscosity:.8,attributionControl:true});
      connections=L.layerGroup().addTo(map);pins=L.layerGroup().addTo(map);labels=L.layerGroup().addTo(map);entrances=L.layerGroup().addTo(map);
      map.fitBounds(bounds);
      setStyle(style);map.fitBounds(bounds);
      $('#map-style').onclick=()=>setStyle(style==='sketch'?'real':'sketch');
      $('#center-hornet').onclick=()=>{if(livePin)map.setView(livePin.getLatLng(),Math.max(map.getZoom(),1));};
      $('#calibrate-hornet').onclick=()=>{
        if(!live?.connected||!live.position||style!=='sketch')return;
        const scene=live.position.scene,anchors=calibration[scene]||[];
        pendingAnchor={scene,source:[live.position.x,live.position.y],index:anchors.length===1?1:0};
        noticeUntil=0;
        liveDetail('');
      };
      $('#reset-calibration').onclick=()=>{
        if(!live?.position)return;
        delete calibration[live.position.scene];pendingAnchor=null;noticeUntil=0;
        localStorage.setItem('ss.map.live.calibration.v2',JSON.stringify(calibration));redrawLive();
      };
      $('#map').addEventListener('click',event=>{
        if(!pendingAnchor||style!=='sketch')return;
        event.preventDefault();event.stopImmediatePropagation();
        const {scene,source,index}=pendingAnchor;pendingAnchor=null;
        const current=live?.position;
        if(!live?.connected||!current||current.scene!==scene||Math.hypot(current.x-source[0],current.y-source[1])>3){
          liveNotice('Hornet moved or changed rooms before the click. Stand still and capture again.');redrawLive();return;
        }
        const clicked=map.mouseEventToLatLng(event),point={source,sketch:[clicked.lat,clicked.lng]};
        const first=(calibration[scene]||[])[0];
        if(index===1&&first){
          const prior=liveMath.priorForScene(autoRooms,scene);
          if(!prior||!liveMath.solveAnchors([first,point],prior.matrix)){
            liveNotice('Points are too close or inconsistent. Keep point 1, move farther, then capture point 2 again.');redrawLive();return;
          }
          calibration[scene]=[first,point];
          localStorage.setItem('ss.map.live.calibration.v2',JSON.stringify(calibration));
          liveNotice('Two-point calibration saved. Scale and direction now follow both positions.');
        }else{
          calibration[scene]=[point];
          localStorage.setItem('ss.map.live.calibration.v2',JSON.stringify(calibration));
          liveNotice('Point 1 saved. Move a good distance in this room, then capture point 2 to fit movement accurately.');
        }
        redrawLive();
      },true);
      pollLive();setInterval(pollLive,750);
      map.on('zoomend moveend resize',tidyLabels);
      tidyLabels();
      map.on('zoomend',()=>{for(const m of data.markers)if(objects.has(m.id))objects.get(m.id).setIcon(icon(m));});
      new ResizeObserver(()=>map.invalidateSize({animate:false})).observe($('#map'));
      buildLayers();draw();
      const params=new URLSearchParams(location.search),id=params.get('focus'),entry=params.get('entry'),interiorId=params.get('interior');
      if(id){const m=data.markers.find(m=>m.id===id);if(m)focus(m);else message('This location is not in the current map dataset.');}
      else if(interiorId){const interior=(data.interiors||[]).find(x=>x.id===interiorId);if(interior)openInterior(interior);}
      else if(entry){
        const link=data.links[entry];
        if(link){const found=data.markers.filter(m=>link.ids.includes(m.id));if(found.length===1)focus(found[0]);else{scope=new Set(link.ids);category=link.category;query='';$('#map-search').value=query;draw();const located=found.filter(position);if(located.length)map.fitBounds(L.latLngBounds(located.map(position)),{padding:[80,80],maxZoom:meta().maxZoom});message(link.kind==='components'?'Component locations for '+link.name:found.length+' locations for '+link.name);}}
        else message('No researched location is linked to this checklist entry yet.');
      }else if(params.get('search')){query=params.get('search').toLowerCase();$('#map-search').value=params.get('search');draw();const found=data.markers.filter(matches);if(found.length===1)focus(found[0]);else {const located=found.filter(position);if(located.length)map.fitBounds(L.latLngBounds(located.map(position)),{padding:[60,60],maxZoom:meta().maxZoom});}}
      $('#map-search').oninput=()=>{query=$('#map-search').value.trim().toLowerCase();selected=null;category=null;scope=null;message('');draw();};
      $('#map-search').onkeydown=e=>{if(e.key==='Enter'){const m=data.markers.find(matches);if(m)focus(m);}};
      $('#only-left').checked=onlyLeft;$('#only-left').onchange=()=>{onlyLeft=$('#only-left').checked;selected=null;persist();draw();};
      $('#fit').onclick=()=>{selected=null;category=null;scope=null;query='';$('#map-search').value='';map.closePopup();message('');draw();map.fitBounds(L.latLngBounds(meta().bounds));history.replaceState(null,'','/map?style='+style);};
      $('#all-layers').onclick=()=>{hidden.clear();selected=null;persist();buildLayers();draw();};
      $('#no-layers').onclick=()=>{hidden=new Set(data.categories.map(c=>c.id));selected=null;query='';category=null;scope=null;$('#map-search').value='';persist();buildLayers();draw();};
      $('#default-layers').onclick=()=>{resetLayers();onlyLeft=false;$('#only-left').checked=false;selected=null;category=null;scope=null;query='';$('#map-search').value='';persist();buildLayers();draw();};
      $('#export-marks').onclick=exportMarks;
      $('#import-marks').onclick=()=>$('#marks-file').click();
      $('#marks-file').onchange=async e=>{await importMarks(e.target.files[0]);e.target.value='';};
      $('#toggle-layers').onclick=()=>{const mobile=matchMedia('(max-width:600px)').matches;$('#workspace').classList.toggle(mobile?'mobile-open':'collapsed');$('#toggle-layers').setAttribute('aria-expanded',String(mobile?$('#workspace').classList.contains('mobile-open'):!$('#workspace').classList.contains('collapsed')));map.invalidateSize();};
      document.addEventListener('keydown',e=>{if(e.key==='Escape'&&pendingAnchor){pendingAnchor=null;redrawLive();}if(e.key==='/'&&document.activeElement!==$('#map-search')){e.preventDefault();$('#map-search').focus();}});
      let signature='';
      const events=new EventSource('/events');events.addEventListener('state',async event=>{
        const state=JSON.parse(event.data),sig=JSON.stringify([state.hasSave,state.slot,state.groups]);
        if(sig===signature)return;signature=sig;
        const updated=await fetch('/api/map').then(r=>r.json());data=updated;loadManual();indexGroups();
        for(const m of data.markers)if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
        draw();
      });
    }catch(err){$('#error').hidden=false;$('#error').textContent='Could not load the map: '+err.message;}
  }
  boot();
})();
