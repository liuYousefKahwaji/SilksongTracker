/* Based on Hollow Tracker: Leaflet CRS.Simple, offline tiles, icon markers,
 * stable pin links, category filters and popups. Source positions are preserved. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const node = (tag, cls, text) => {const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e;};
  let data, map, pins, labels, connections, entrances, tileLayer, selected=null, category=null, scope=null, viewPersistenceReady=false;
  const MAP_VIEW_KEY='ss.map.view.v1';
  function readSavedViews(){try{const value=JSON.parse(localStorage.getItem(MAP_VIEW_KEY)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}catch{return {};}}
  function persistMapView(){
    if(!viewPersistenceReady||!map||!data)return;
    try{
      const views=readSavedViews(),centre=map.getCenter();
      views[style]={centre:[centre.lat,centre.lng],zoom:map.getZoom(),search:$('#map-search')?.value||''};
      localStorage.setItem(MAP_VIEW_KEY,JSON.stringify(views));
    }catch{}
  }
  function persistUserMapView(){
    if(!viewPersistenceReady)return;
    persistMapView();
    const url=new URL(location.href),hadDeepLink=['focus','entry','interior','search'].some(key=>url.searchParams.has(key));
    if(hadDeepLink){url.search='';url.searchParams.set('style',style);history.replaceState(null,'',url);}
  }
  async function apiJson(url,options={}){
    const response=await fetch(url,{cache:'no-store',...options});
    if(!response.ok){let detail;try{detail=(await response.json()).error;}catch{}throw Error(detail||`Request failed (${response.status})`);}
    return response.json();
  }
  let style=new URLSearchParams(location.search).get('style')||localStorage.getItem('ss.map.style')||'sketch';
  if(style!=='real')style='sketch';
  const meta=()=>style==='sketch'?data.sketch:data.image;
  const position=m=>{const p=m[style==='sketch'?'pos2':'pos'];return Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)?p:null;};
  const objects=new Map(), cats=new Map(), shown=new Set(), interiorByMember=new Map(), sketchGroupByMember=new Map(), shortcutFilterByMarker=new Map();
  const sketchGroups=[];
  const SHORTCUT_FILTER_PREFIX='shortcut-filter:';
  let shortcutFilters=[];
  const liveMath=window.SilksongLiveMath;
  let live=null,livePin=null,calibration={},pendingAnchor=null,autoRooms={},nativeMap=null,nativeRoomInfo={},calibrationNotice='',noticeUntil=0;
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
    const located=liveMath.position(autoRooms,scene,[live.position.x,live.position.y],anchors,live.position.map,nativeMap,live.position.mapMode);
    if(!located){hide();liveDetail('No automatic map position for game scene “'+scene+'”. Please report this exact scene name so it can be added to the room coverage audit.');return;}
    const p=located.point;
    const bounds=L.latLngBounds(data.sketch.bounds);
    if(!p||!bounds.contains(p)){hide();liveDetail('Position is outside Sketch. Clear and redo this room’s calibration.');return;}
    if(livePin)livePin.setLatLng(p);
    else {
      livePin=L.marker(p,{zIndexOffset:10000,icon:L.icon({iconUrl:'/hornet-head-source.png',className:'hornet-live',iconSize:[36,48],iconAnchor:[18,47],popupAnchor:[0,-36]}),title:'Hornet · live position',alt:'Hornet live position'}).addTo(map);
      livePin.bindPopup('Hornet · live position');
    }
    $('#center-hornet').disabled=false;
    if(located.mode==='native'){
      const mapMode=live.position.mapMode||'',roomInfo=nativeRoomInfo[scene.toLowerCase()];
      if(mapMode==='last-known'||roomInfo?.inheritLastPosition)
        liveDetail('Showing the last overworld location while Hornet is in this interior or special scene; movement inside it is not on the world map.');
      else if(mapMode==='area-anchor'||(roomInfo?.anchorOnly&&roomInfo?.anchorSource&&roomInfo.anchorSource!=='in-game-map-room-anchor'))
        liveDetail('Placed at an approximate parent/area map anchor. The game has no independent world-map geometry for this scene.');
      else if(mapMode==='room-anchor'||roomInfo?.anchorOnly)
        liveDetail('Placed at this room’s exact in-game map anchor. The game has no room silhouette here, so movement within this room is not mapped.');
      else liveDetail('Auto-located from the game’s own room-map geometry.');
      return;
    }
    if(located.mode==='legacy'){
      liveDetail('Auto-positioned with a researched legacy room transform. The room lacks native overworld map geometry; treat fine alignment as approximate.');
      return;
    }
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
  function manuallyTrackable(m){return m.tracking==='unverified'||m.tracking==='waypoint';}
  function manualStatus(m){return manuallyTrackable(m)&&manual[m.id]||m.status;}
  function setManual(m,value){
    if(value)manual[m.id]=value;else delete manual[m.id];
    try {localStorage.setItem(manualKey,JSON.stringify(manual));}
    catch {$('#marks-status').textContent='Browser storage is unavailable. Export a backup before closing this page.';}
    if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
    draw();
  }
  function exportMarks(){
    const marks=Object.fromEntries(Object.entries(manual).filter(([id,value])=>data.markers.some(m=>m.id===id&&manuallyTrackable(m))&&['left','complete'].includes(value)));
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
      const permitted=new Set(data.markers.filter(manuallyTrackable).map(m=>m.id));
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
  function resetLayers(){hidden=new Set(['permFlags','rosary','shard','rosaryitem','sharditem','tradable','memento','silkeater','npc','wish','questitem','arena']);setShortcutFiltersVisible(false);persist();}
  function indexShortcutFilters(){
    const groups=new Map(),directions={Up:0,Down:1,Left:2,Right:3};
    shortcutFilterByMarker.clear();
    for(const m of data.markers.filter(item=>item.cat==='shortcut')){
      let family, label, order=0;
      if(m.name.startsWith('Requires ')){family='requirement';label=m.name;order=0;}
      else if(m.name.startsWith('One-Way Shortcut - ')){const direction=m.name.slice('One-Way Shortcut - '.length);family='arrow';label='One-way arrows · '+direction;order=directions[direction]??99;}
      else if(m.name.startsWith('Intersection - ')){family='route-extra';label='Intersections';order=0;}
      else if(m.name.startsWith('Requirement Unknown')){family='route-extra';label='Unknown requirements';order=1;}
      else if(m.name.startsWith('Unlocked ')){family='route-extra';label='Unlocked route notes';order=2;}
      else {family='route-extra';label='Other route notes';order=3;}
      const id=SHORTCUT_FILTER_PREFIX+label.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
      let group=groups.get(id);
      if(!group){group={id,label,family,order,icon:m.icon,members:[]};groups.set(id,group);}
      group.members.push(m);shortcutFilterByMarker.set(m.id,id);
    }
    const familyOrder={requirement:0,arrow:1,'route-extra':2};
    shortcutFilters=[...groups.values()].sort((a,b)=>familyOrder[a.family]-familyOrder[b.family]||a.order-b.order||a.label.localeCompare(b.label));
    // Older preferences treated the parent as an independent switch. Migrate
    // an old parent-off state to the new tree model, where that means no children selected.
    if(hidden.has('shortcut'))for(const filter of shortcutFilters)hidden.add(filter.id);
    syncShortcutParent();
  }
  function syncShortcutParent(){if(shortcutFilters.some(filter=>!hidden.has(filter.id)))hidden.delete('shortcut');else hidden.add('shortcut');}
  function setShortcutFiltersVisible(visible){for(const filter of shortcutFilters)visible?hidden.delete(filter.id):hidden.add(filter.id);syncShortcutParent();}
  function groupLayerKeys(categories){return categories.flatMap(c=>c.id==='shortcut'?shortcutFilters.map(filter=>filter.id):[c.id]);}
  function setGroupLayersVisible(keys,visible){for(const key of keys)visible?hidden.delete(key):hidden.add(key);syncShortcutParent();}
  function title(m){return m.name.replace(/^(Tool|Ability|Upgrade|Boss)\s*-\s*/i,'');}
  function matches(m){return (!scope||scope.has(m.id))&&(!category||m.cat===category)&&(!query||(m.name+' '+cats.get(m.cat).name).toLowerCase().includes(query));}
  function eligible(m){if(m.id===selected)return true;if(onlyLeft&&manualStatus(m)!=='left')return false;if(query||category||scope)return matches(m);return !hidden.has(m.cat)&&!hidden.has(shortcutFilterByMarker.get(m.id));}
  function visible(m){if(!position(m))return false;if(style==='sketch'&&sketchGroupByMember.has(m.id))return false;return eligible(m);}
  function icon(m){const size=map&&map.getZoom()<1?16:28;return L.icon({iconUrl:'/map/icons/'+encodeURIComponent(m.icon),iconSize:[size,size],iconAnchor:[size/2,size/2],popupAnchor:[0,-size/2],className:'pin'+(manualStatus(m)==='complete'&&!NEVER_DIM.has(m.cat)?' done':'')+(selected===m.id?' selected':'')});}
  function popup(m){
    const box=node('div'),heading=node('div','popup-heading');
    heading.append(image(m.icon),node('b',null,title(m)));box.append(heading,node('div','popup-category',cats.get(m.cat).name));
    let status;
    if(m.tracking==='waypoint')status=manual[m.id]==='complete'?'Manually marked visited':manual[m.id]==='left'?'Manually marked not visited':'Not marked visited';
    else if(m.tracking==='reference')status='Reference location';
    else if(m.tracking==='unverified'&&manual[m.id])status='Manually marked '+(manual[m.id]==='complete'?'complete':'incomplete');
    else if(m.tracking==='unverified')status='Tracking needs verification';
    else if(!data.hasSave)status='No save loaded';
    else if(m.status==='unavailable')status='Alternative already owned';
    else if(m.status==='complete')status='Collected / completed';
    else if(m.status==='left')status='Not completed';
    else status='Save data unavailable';
    box.append(node('span','popup-state '+manualStatus(m),status));
    if(m.trackingNote)box.append(node('p','popup-note',m.trackingNote));
    if(manuallyTrackable(m)){
      const controls=node('div','popup-manual');
      const done=node('button',null,m.tracking==='waypoint'?'Mark visited':'Mark done'),left=node('button',null,m.tracking==='waypoint'?'Mark not visited':'Mark left');
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
    const reference=data.markers.filter(m=>m.tracking==='reference').length,unverified=data.markers.filter(m=>m.tracking==='unverified').length,waypoints=data.markers.filter(m=>m.tracking==='waypoint').length;
    $('#tracking-summary').textContent=waypoints+' route waypoints (mark visited manually) · '+reference+' reference locations · '+unverified+' objectives awaiting verified save rules. Only left keeps route waypoints until marked visited, plus confirmed or manually marked incomplete locations. An explicitly focused pin stays visible.';
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
    persistMapView();
  }
  function buildLayers(){
    const host=$('#layers');host.replaceChildren();
    for(const group of data.groups){
      const section=node('section','layer-group'),heading=node('label','group-title'),check=node('input');check.type='checkbox';
      const members=data.categories.filter(c=>c.group===group.id);
      const keys=groupLayerKeys(members),active=keys.filter(key=>!hidden.has(key)).length;
      check.checked=active===keys.length;check.indeterminate=active>0&&active<keys.length;
      check.onchange=()=>{setGroupLayersVisible(keys,check.checked);persist();buildLayers();draw();};
      heading.append(check,image(group.icon),node('span',null,group.name));section.append(heading);
      for(const c of members){
        const row=node('label','layer-row'),cb=node('input');cb.type='checkbox';
        if(c.id==='shortcut'){
          const activeFilters=shortcutFilters.filter(filter=>!hidden.has(filter.id)).length;
          cb.checked=activeFilters===shortcutFilters.length;cb.indeterminate=activeFilters>0&&activeFilters<shortcutFilters.length;
          cb.onchange=()=>{setShortcutFiltersVisible(cb.checked);selected=null;persist();buildLayers();draw();};
        }else cb.checked=!hidden.has(c.id);
        if(c.id!=='shortcut')cb.onchange=()=>{cb.checked?hidden.delete(c.id):hidden.add(c.id);selected=null;persist();buildLayers();draw();};
        row.append(cb,image(c.icon),node('span',null,c.name),node('small',null,String(data.markers.filter(m=>m.cat===c.id).length)));section.append(row);
        if(c.id==='shortcut')for(const filter of shortcutFilters){
          const subrow=node('label','layer-row layer-subrow'),subcheck=node('input');subcheck.type='checkbox';subcheck.checked=!hidden.has(filter.id);subrow.style.paddingLeft='32px';subrow.style.fontSize='11px';subrow.style.color='var(--muted)';
          subcheck.onchange=()=>{subcheck.checked?hidden.delete(filter.id):hidden.add(filter.id);syncShortcutParent();selected=null;persist();buildLayers();draw();};
          subrow.append(subcheck,image(filter.icon),node('span',null,filter.label),node('small',null,String(filter.members.length)));section.append(subrow);
        }
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
      try {const transforms=await fetch('/api/live-transforms').then(r=>r.json());autoRooms=transforms.rooms||{};nativeMap=transforms.nativeMap||null;nativeRoomInfo=transforms.nativeRooms||{};} catch {}
      loadManual();
      for(const c of data.categories)cats.set(c.id,c);
      indexShortcutFilters();
      indexGroups();
      if(!localStorage.getItem('ss.map.hidden.v2'))resetLayers();
      const bounds=L.latLngBounds(meta().bounds);
      map=L.map('map',{crs:L.CRS.Simple,minZoom:-1,maxZoom:meta().maxZoom,zoomSnap:.5,zoomAnimation:false,maxBounds:bounds.pad(.12),maxBoundsViscosity:.8,attributionControl:true});
      connections=L.layerGroup().addTo(map);pins=L.layerGroup().addTo(map);labels=L.layerGroup().addTo(map);entrances=L.layerGroup().addTo(map);
      map.fitBounds(bounds);
      setStyle(style);
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
      map.on('zoomend moveend',persistUserMapView);
      window.addEventListener('pagehide',persistMapView);
      tidyLabels();
      map.on('zoomend',()=>{for(const m of data.markers)if(objects.has(m.id))objects.get(m.id).setIcon(icon(m));});
      new ResizeObserver(()=>map.invalidateSize({animate:false})).observe($('#map'));
      buildLayers();draw();
      const workspace=$('#workspace'),toggleLayers=$('#toggle-layers'),smallLayout=matchMedia('(max-width:600px)').matches;
      const savedLayersOpen=localStorage.getItem('ss.map.layers-open');
      const layersOpen=savedLayersOpen===null?!smallLayout:savedLayersOpen==='1';
      workspace.classList.toggle('mobile-open',smallLayout&&layersOpen);
      workspace.classList.toggle('collapsed',!smallLayout&&!layersOpen);
      toggleLayers.setAttribute('aria-expanded',String(layersOpen));
      const params=new URLSearchParams(location.search),id=params.get('focus'),entry=params.get('entry'),interiorId=params.get('interior');
      const savedView=readSavedViews()[style];
      if(id){const m=data.markers.find(m=>m.id===id);if(m)focus(m);else message('This location is not in the current map dataset.');}
      else if(interiorId){const interior=(data.interiors||[]).find(x=>x.id===interiorId);if(interior)openInterior(interior);}
      else if(entry){
        const link=data.links[entry];
        if(link){const found=data.markers.filter(m=>link.ids.includes(m.id));if(found.length===1)focus(found[0]);else{scope=new Set(link.ids);category=link.category;query='';$('#map-search').value=query;draw();const located=found.filter(position);if(located.length)map.fitBounds(L.latLngBounds(located.map(position)),{padding:[80,80],maxZoom:meta().maxZoom});message(link.kind==='components'?'Component locations for '+link.name:found.length+' locations for '+link.name);}}
        else message('No researched location is linked to this checklist entry yet.');
      }else if(params.get('search')){query=params.get('search').toLowerCase();$('#map-search').value=params.get('search');draw();const found=data.markers.filter(matches);if(found.length===1)focus(found[0]);else {const located=found.filter(position);if(located.length)map.fitBounds(L.latLngBounds(located.map(position)),{padding:[60,60],maxZoom:meta().maxZoom});}}
      else {
        if(savedView&&Array.isArray(savedView.centre)&&savedView.centre.length===2&&savedView.centre.every(Number.isFinite)){
          query=typeof savedView.search==='string'?savedView.search.trim().toLowerCase():'';$('#map-search').value=typeof savedView.search==='string'?savedView.search:'';draw();
          const zoom=Number.isFinite(savedView.zoom)?Math.max(-1,Math.min(meta().maxZoom,savedView.zoom)):map.getZoom();
          map.setView(savedView.centre,zoom,{animate:false});
        }else map.fitBounds(L.latLngBounds(meta().bounds));
      }
      viewPersistenceReady=true;persistMapView();
      $('#map-search').oninput=()=>{query=$('#map-search').value.trim().toLowerCase();selected=null;category=null;scope=null;message('');draw();history.replaceState(null,'','/map?style='+style);persistMapView();};
      $('#map-search').onkeydown=e=>{if(e.key==='Enter'){const m=data.markers.find(matches);if(m)focus(m);}};
      $('#only-left').checked=onlyLeft;$('#only-left').onchange=()=>{onlyLeft=$('#only-left').checked;selected=null;persist();draw();};
      $('#fit').onclick=()=>{selected=null;category=null;scope=null;query='';$('#map-search').value='';map.closePopup();message('');draw();map.fitBounds(L.latLngBounds(meta().bounds));history.replaceState(null,'','/map?style='+style);persistMapView();};
      $('#all-layers').onclick=()=>{hidden.clear();selected=null;persist();buildLayers();draw();};
      $('#no-layers').onclick=()=>{hidden=new Set(data.categories.map(c=>c.id));for(const filter of shortcutFilters)hidden.add(filter.id);selected=null;query='';category=null;scope=null;$('#map-search').value='';persist();buildLayers();draw();persistMapView();};
      $('#default-layers').onclick=()=>{resetLayers();onlyLeft=false;$('#only-left').checked=false;selected=null;category=null;scope=null;query='';$('#map-search').value='';persist();buildLayers();draw();persistMapView();};
      $('#export-marks').onclick=exportMarks;
      $('#import-marks').onclick=()=>$('#marks-file').click();
      $('#marks-file').onchange=async e=>{await importMarks(e.target.files[0]);e.target.value='';};
      $('#toggle-layers').onclick=()=>{const mobile=matchMedia('(max-width:600px)').matches;$('#workspace').classList.toggle(mobile?'mobile-open':'collapsed');const open=mobile?$('#workspace').classList.contains('mobile-open'):!$('#workspace').classList.contains('collapsed');$('#toggle-layers').setAttribute('aria-expanded',String(open));localStorage.setItem('ss.map.layers-open',open?'1':'0');map.invalidateSize();};
      $('#refresh-map').onclick=async()=>{
        const button=$('#refresh-map'),status=$('#refresh-map-status');button.disabled=true;button.textContent='↻ Scanning…';status.classList.remove('error');status.textContent='Reading save files…';persistMapView();
        try{
          const state=await apiJson('/api/refresh',{method:'POST'});status.textContent='Updating map…';
          const updated=await apiJson('/api/map');
          data=updated;loadManual();cats.clear();for(const c of data.categories)cats.set(c.id,c);indexGroups();
          if(selected&&!data.markers.some(m=>m.id===selected))selected=null;
          for(const m of data.markers)if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
          draw();redrawLive();persistMapView();
          status.textContent=state.error||updated.saveError?'Scan finished · save unreadable':updated.hasSave?'Map refreshed':'No save found';
        }catch(error){status.textContent='Refresh failed · '+error.message;status.classList.add('error');}
        finally{button.disabled=false;button.textContent='↻ Refresh';}
      };
      document.addEventListener('keydown',e=>{if(e.key==='Escape'&&pendingAnchor){pendingAnchor=null;redrawLive();}if(e.key==='/'&&document.activeElement!==$('#map-search')){e.preventDefault();$('#map-search').focus();}});
      let signature='';
      const events=new EventSource('/events');events.addEventListener('state',async event=>{
        const state=JSON.parse(event.data),sig=JSON.stringify([state.hasSave,state.slot,state.path,state.selectedSaveIndex,state.groups]);
        if(sig===signature)return;signature=sig;
        try{
          const updated=await apiJson('/api/map');data=updated;loadManual();cats.clear();for(const c of data.categories)cats.set(c.id,c);indexGroups();
          for(const m of data.markers)if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
          draw();redrawLive();
        }catch{}
      });
    }catch(err){$('#error').hidden=false;$('#error').textContent='Could not load the map: '+err.message;}
  }
  boot();
})();
