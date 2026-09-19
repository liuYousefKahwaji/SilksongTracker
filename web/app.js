(() => {
  const $ = (s) => document.querySelector(s);
  let state = null;
  const slug = (x) => x.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const esc = (x) => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function json(url, opts) { const r = await fetch(url, opts); if (!r.ok) throw new Error(await r.text()); return r.json(); }
  function statusLabel(s) { return s === 'complete' ? 'Done' : s === 'left' ? 'Left' : 'Unknown'; }
  function render() {
    if (!state) return;
    const sum = state.summary || {}; const has = state.hasSave;
    $('#percent').textContent = has ? (sum.percent ?? 0) : '—';
    $('#meter-fill').style.width = `${has ? (sum.percent || 0) : 0}%`;
    $('#complete').textContent = has ? `${sum.complete} / ${sum.total}` : `— / ${sum.total || 100}`;
    $('#left').textContent = has ? `${sum.left} left · ${sum.unknown} unverified` : 'unknown until a save is loaded';
    $('#slot').textContent = has ? `Slot ${state.slot}` : '—';
    $('#version').textContent = state.saveVersion || (has ? 'version not exposed' : 'No save detected');
    $('#hero-note').textContent = has ? `${sum.left} completion point${sum.left === 1 ? '' : 's'} remaining` : 'Waiting for a Silksong save';
    const banner = $('#save-banner'); banner.className = `notice ${has ? 'loaded' : 'waiting'}`;
    banner.querySelector('strong').textContent = state.error ? 'Save needs attention' : has ? `Slot ${state.slot} loaded` : 'No save loaded';
    banner.querySelector('span').innerHTML = esc(state.error || (has ? `${state.path || ''} · the tracker is read-only` : 'Start Silksong once and this page will discover <code>userN.dat</code> automatically.'));
    const q = $('#search').value.trim().toLowerCase(), onlyLeft = $('#only-left').checked, hideUnknown = $('#hide-unknown').checked, hideSupporting = $('#hide-supporting').checked;
    const visibleSections = [];
    for (const group of state.groups || []) {
      if (hideSupporting && !group.points) continue;
      const entries = (group.entries || []).filter(e => (!q || `${e.name} ${group.name}`.toLowerCase().includes(q)) && (!onlyLeft || e.status === 'left') && (!hideUnknown || e.status !== 'unknown'));
      if (!entries.length) continue;
      visibleSections.push({group, entries});
    }
    $('#section-nav').innerHTML = visibleSections.map(({group}) => `<a href="#${esc(group.id)}"><span>${esc(group.icon || '•')}</span>${esc(group.name)}<em>${group.complete ?? 0}/${group.total || group.entryTotal || group.entries.length}</em></a>`).join('');
    $('#sections').innerHTML = visibleSections.map(({group, entries}) => `<section class="group" id="${esc(group.id)}"><div class="group-head"><div><span class="group-icon">${esc(group.icon || '•')}</span><h2>${esc(group.name)}</h2><small>${group.points ? `${group.points} official point${group.points === 1 ? '' : 's'}` : 'supporting checklist'}</small></div><strong>${group.complete ?? 0}<i>/${group.total || group.entryTotal || entries.length}</i></strong></div><div class="cards">${entries.map(e => `<article class="entry ${e.status}${e.id === initial ? ' entry-focused' : ''}" id="${esc(e.id)}" data-name="${esc(e.name)}"><div class="entry-mark">${e.status === 'complete' ? '✓' : e.status === 'left' ? '·' : '?'}</div>${e.map ? `<img class="entry-icon" src="/map/icons/${encodeURIComponent(e.map.icon)}" alt="">` : ''}<div class="entry-body"><b>${esc(e.name)}</b><small>${statusLabel(e.status)}${e.note ? ` · ${esc(e.note)}` : ''}</small></div>${e.map ? `<a class="map-link" href="/map?entry=${encodeURIComponent(e.id)}" title="${e.map.kind === 'components' ? 'Show component locations' : 'Show on map'}">⌖</a>` : `<span class="map-unlinked" title="No researched map location linked yet">—</span>`}</article>`).join('')}</div></section>`).join('') || `<div class="empty"><b>No matching entries</b><span>Try another search or clear a filter.</span></div>`;
  }
  const initial = new URLSearchParams(location.search).get('focus');
  let focused = false;
  function focusEntry() { if (!initial || focused) return; const entry = document.getElementById(initial); if (entry) { focused = true; entry.scrollIntoView({block:'center'}); entry.classList.add('entry-focused'); } }
  async function load() { try { state = await json('/api/state'); render(); focusEntry(); } catch (e) { $('#save-banner').className = 'notice error'; $('#save-banner span').textContent = e.message; } }
  $('#refresh').addEventListener('click', async () => { $('#refresh').disabled = true; try { state = await json('/api/refresh', {method:'POST'}); render(); } finally { $('#refresh').disabled = false; } });
  ['search','only-left','hide-unknown','hide-supporting'].forEach(id => $(`#${id}`).addEventListener(id === 'search' ? 'input' : 'change', render));
  if (initial) { const all = ['only-left','hide-unknown','hide-supporting']; all.forEach(id => $('#'+id).checked = false); }
  load();
  if (window.EventSource) { const events = new EventSource('/events'); events.addEventListener('state', e => { try { state = JSON.parse(e.data); render(); } catch (_) {} }); }
})();
