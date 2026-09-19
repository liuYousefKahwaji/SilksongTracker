/* Based on Hollow Tracker: Leaflet CRS.Simple, offline tiles, icon markers,
 * stable pin links, category filters and popups. Source positions are preserved. */
(() => {
  'use strict';
  const $ = s => document.querySelector(s);
  const node = (tag, cls, text) => {const e=document.createElement(tag); if(cls)e.className=cls; if(text!==undefined)e.textContent=text; return e;};
  let data, map, pins, labels, tileLayer, selected=null, category=null, scope=null;
  let style=new URLSearchParams(location.search).get('style')||localStorage.getItem('ss.map.style')||'sketch';
  if(style!=='real')style='sketch';
  const meta=()=>style==='sketch'?data.sketch:data.image;
  const position=m=>{const p=m[style==='sketch'?'pos2':'pos'];return Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)?p:null;};
  const objects=new Map(), cats=new Map(), shown=new Set();
  let hidden=new Set(), query='', onlyLeft=false;
  try {hidden=new Set(JSON.parse(localStorage.getItem('ss.map.hidden.v2')||'null')||[]);onlyLeft=localStorage.getItem('ss.map.left')==='1';} catch {}
  const NEVER_DIM=new Set(['benches','bellway','ventrica','maps']);
  function image(file, alt='') {const e=node('img');e.src='/map/icons/'+encodeURIComponent(file);e.alt=alt;return e;}
  function message(text) {$('#map-message').textContent=text;$('#map-message').hidden=!text;}
  function persist(){localStorage.setItem('ss.map.hidden.v2',JSON.stringify([...hidden]));localStorage.setItem('ss.map.left',onlyLeft?'1':'0');}
  function resetLayers(){hidden=new Set(['shortcut','permFlags','rosary','shard','rosaryitem','sharditem','tradable','memento','silkeater','npc','wish','questitem','arena']);persist();}
  function title(m){return m.name.replace(/^(Tool|Ability|Upgrade|Boss)\s*-\s*/i,'');}
  function matches(m){return (!scope||scope.has(m.id))&&(!category||m.cat===category)&&(!query||(m.name+' '+cats.get(m.cat).name).toLowerCase().includes(query));}
  function visible(m){if(!position(m))return false;if(m.id===selected)return true;if(onlyLeft&&m.status!=='left')return false;if(query||category||scope)return matches(m);return !hidden.has(m.cat);}
  function icon(m){const size=map&&map.getZoom()<1?16:28;return L.icon({iconUrl:'/map/icons/'+encodeURIComponent(m.icon),iconSize:[size,size],iconAnchor:[size/2,size/2],popupAnchor:[0,-size/2],className:'pin'+(m.status==='complete'&&!NEVER_DIM.has(m.cat)?' done':'')+(selected===m.id?' selected':'')});}
  function popup(m){
    const box=node('div'),heading=node('div','popup-heading');
    heading.append(image(m.icon),node('b',null,title(m)));box.append(heading,node('div','popup-category',cats.get(m.cat).name));
    const status=m.tracking==='reference'?'Reference location':m.tracking==='unverified'?'Tracking needs verification':!data.hasSave?'No save loaded':m.status==='unavailable'?'Alternative already owned':m.status==='complete'?'Collected / completed':m.status==='left'?'Not completed':'Save data unavailable';
    box.append(node('span','popup-state '+m.status,status));
    if(m.trackingNote)box.append(node('p','popup-note',m.trackingNote));
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
  function draw(){
    const wanted=new Set(data.markers.filter(visible).map(m=>m.id));
    for(const id of shown)if(!wanted.has(id)){pins.removeLayer(objects.get(id));shown.delete(id);}
    for(const m of data.markers)if(wanted.has(m.id)&&!shown.has(m.id)){marker(m).addTo(pins);shown.add(m.id);}
    $('#visible-count').textContent=shown.size+' pins';
    const reference=data.markers.filter(m=>m.tracking==='reference').length,unverified=data.markers.filter(m=>m.tracking==='unverified').length;
    $('#tracking-summary').textContent=reference+' reference locations · '+unverified+' objectives awaiting verified tracking. Only left shows confirmed incomplete objectives; an explicitly focused pin stays visible.';
    $('#save-status').textContent=data.hasSave?'Save loaded · '+data.markers.filter(m=>m.status==='complete').length+' completed':'No save loaded';
    const result=$('#results'); result.replaceChildren();result.hidden=!(query||category||scope);
    if(!result.hidden){
      const found=data.markers.filter(m=>matches(m)&&(!onlyLeft||m.status==='left'||m.id===selected));
      result.append(node('h2',null,found.length+' locations'));
      for(const m of found.slice(0,100)){const b=node('button','result'),label=node('span',null,title(m));label.append(node('small',null,cats.get(m.cat).name+(!position(m)?' · Screenshots only':'')));b.append(image(m.icon),label);b.onclick=()=>focus(m);result.append(b);}
      if(!found.length)result.append(node('p','empty-results','No mapped location matches this search.'));
      if(found.length>100)result.append(node('p','help','Showing the first 100 results. All matching pins remain on the map.'));
    }
  }
  function focus(m){
    const missing=!position(m);
    if(missing)setStyle('real');
    selected=m.id;draw();map.setView(position(m),Math.min(3,meta().maxZoom),{animate:false});
    const pin=marker(m);pin.setIcon(icon(m));pin.openPopup();
    message(missing?'This location has no researched sketch position; showing Screenshots.':'');history.replaceState(null,'','/map?focus='+encodeURIComponent(m.id)+'&style='+style);
  }
  function setStyle(next){
    const oldCentre=map.getCenter(),oldZoom=map.getZoom(),oldMax=meta().maxZoom;
    const anchor=data.markers.filter(m=>Array.isArray(m.pos2)&&m.pos2.every(Number.isFinite)).sort((a,b)=>oldCentre.distanceTo(L.latLng(position(a)))-oldCentre.distanceTo(L.latLng(position(b))))[0];
    const oldAnchor=anchor&&position(anchor);
    style=next;localStorage.setItem('ss.map.style',style);
    const info=meta(),bounds=L.latLngBounds(info.bounds);
    if(tileLayer)map.removeLayer(tileLayer);
    map.setMaxZoom(info.maxZoom);map.setMaxBounds(bounds.pad(.12));
    const valid=new Set(style==='sketch'?info.validTiles:data.validTiles),blank='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    const Tiles=L.TileLayer.extend({getTileUrl(c){return valid.has(c.z+'/'+c.x+'_'+c.y)?L.TileLayer.prototype.getTileUrl.call(this,c):blank;}});
    tileLayer=new Tiles(info.url,{tileSize:info.tileSize,minZoom:-2,minNativeZoom:0,maxNativeZoom:info.maxZoom,maxZoom:info.maxZoom,noWrap:true,bounds,keepBuffer:2,attribution:'Map: RainingChain & IdoManti · © Team Cherry'}).addTo(map);
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
    if(chosen&&position(chosen)){map.setView(position(chosen),Math.min(oldZoom,info.maxZoom),{animate:false});marker(chosen).openPopup();}
    else if(anchor){const p=position(anchor);map.setView([p[0]+oldCentre.lat-oldAnchor[0],p[1]+oldCentre.lng-oldAnchor[1]],Math.min(oldZoom+info.maxZoom-oldMax,info.maxZoom),{animate:false});}
    else map.fitBounds(bounds);
    message(chosen&&!position(chosen)?'This location has no researched sketch position. Switch to Screenshots to see it.':'');
    const url=new URL(location.href);url.searchParams.set('style',style);history.replaceState(null,'',url);
    tidyLabels();
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
  async function boot(){
    try{
      const res=await fetch('/api/map');if(!res.ok)throw Error('Map data could not be loaded.');data=await res.json();
      for(const c of data.categories)cats.set(c.id,c);
      if(!localStorage.getItem('ss.map.hidden.v2'))resetLayers();
      const bounds=L.latLngBounds(meta().bounds);
      map=L.map('map',{crs:L.CRS.Simple,minZoom:-1,maxZoom:meta().maxZoom,zoomSnap:.5,maxBounds:bounds.pad(.12),maxBoundsViscosity:.8,attributionControl:true});
      pins=L.layerGroup().addTo(map);labels=L.layerGroup().addTo(map);
      map.fitBounds(bounds);
      setStyle(style);map.fitBounds(bounds);
      $('#map-style').onclick=()=>setStyle(style==='sketch'?'real':'sketch');
      map.on('zoomend moveend resize',tidyLabels);
      tidyLabels();
      map.on('zoomend',()=>{for(const m of data.markers)if(objects.has(m.id))objects.get(m.id).setIcon(icon(m));});
      new ResizeObserver(()=>map.invalidateSize({animate:false})).observe($('#map'));
      buildLayers();draw();
      const params=new URLSearchParams(location.search),id=params.get('focus'),entry=params.get('entry');
      if(id){const m=data.markers.find(m=>m.id===id);if(m)focus(m);else message('This location is not in the current map dataset.');}
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
      $('#toggle-layers').onclick=()=>{const mobile=matchMedia('(max-width:600px)').matches;$('#workspace').classList.toggle(mobile?'mobile-open':'collapsed');$('#toggle-layers').setAttribute('aria-expanded',String(mobile?$('#workspace').classList.contains('mobile-open'):!$('#workspace').classList.contains('collapsed')));map.invalidateSize();};
      document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==$('#map-search')){e.preventDefault();$('#map-search').focus();}});
      let signature='';
      const events=new EventSource('/events');events.addEventListener('state',async event=>{
        const state=JSON.parse(event.data),sig=JSON.stringify([state.hasSave,state.slot,state.groups]);
        if(sig===signature)return;signature=sig;
        const updated=await fetch('/api/map').then(r=>r.json());data=updated;
        for(const m of data.markers)if(objects.has(m.id)){objects.get(m.id).setIcon(icon(m));objects.get(m.id).setPopupContent(()=>popup(m));}
        draw();
      });
    }catch(err){$('#error').hidden=false;$('#error').textContent='Could not load the map: '+err.message;}
  }
  boot();
})();
