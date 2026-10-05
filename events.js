const state = { events: [], genre: 'ALL', source: 'ALL', query: '' };

const fmtStart = new Intl.DateTimeFormat('ja-JP', {
  month: 'short',
  day: 'numeric',
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short'
});
const fmtEndTime = new Intl.DateTimeFormat('ja-JP', {
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short'
});

function eventDetailUrl(id) { return id ? `events/${id}.html` : 'events.html'; }

function esc(s='') {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function eventStatus(e, now=Date.now()) {
  const start = new Date(e.start).getTime();
  const end = e.end ? new Date(e.end).getTime() : start + 4 * 60 * 60 * 1000;
  if (now >= start && now <= end) return 'LIVE NOW';
  if (start > now && start - now <= 24 * 60 * 60 * 1000) return 'NEXT 24H';
  return 'UPCOMING';
}

function eventTime(e) {
  const start = new Date(e.start);
  if (!e.end) return fmtStart.format(start);
  return `${fmtStart.format(start)} — ${fmtEndTime.format(new Date(e.end))}`;
}

function eventCard(e) {
  const tags = (e.genres || []).slice(0,4).map(g => `<span class="tag">${esc(g)}</span>`).join('');
  const world = e.worldId
    ? `<a href="worlds/${esc(e.worldId)}.html">${esc(e.worldName || e.worldId)}</a>`
    : esc(e.worldName || 'World / instance TBA');
  const link = e.url
    ? `<a class="event-link" href="${esc(e.url)}" target="_blank" rel="noreferrer">PUBLIC INFO ↗</a>`
    : '';
  const status = eventStatus(e);
  const provenance = e.autoImported ? 'PUBLIC FEED' : 'CURATED';
  return `<article class="event-card ${status === 'LIVE NOW' ? 'event-live' : ''} ${e.autoImported ? 'event-auto' : 'event-curated'}">
    <div class="event-card-top"><span class="event-date">${esc(eventTime(e))}</span><span class="event-badges"><span class="event-provenance">${provenance}</span><span class="event-status">${status}</span></span></div>
    <h3><a class="world-title-link" href="${eventDetailUrl(e.id)}">${esc(e.name)}</a></h3>
    <div class="event-world">${world}</div>
    <div class="event-organizer">by ${esc(e.organizer || '—')}</div>
    <div class="tags">${tags}</div>
    ${link}
  </article>`;
}

function upcomingEvents() {
  const now = Date.now();
  return state.events
    .filter(e => {
      if (!e || !e.start) return false;
      const start = new Date(e.start).getTime();
      const end = e.end ? new Date(e.end).getTime() : start + 6 * 60 * 60 * 1000;
      return end >= now;
    })
    .sort((a,b) => new Date(a.start) - new Date(b.start));
}

function renderSourceFilters() {
  const wrap = document.getElementById('eventSourceFilters');
  if (!wrap) return;
  const options = [
    ['ALL', 'ALL'],
    ['CURATED', 'CURATED'],
    ['PUBLIC', 'PUBLIC FEED'],
  ];
  wrap.innerHTML = '';
  options.forEach(([value, label]) => {
    const b = document.createElement('button');
    b.className = `chip${state.source === value ? ' active' : ''}`;
    b.type = 'button';
    b.textContent = label;
    b.onclick = () => { state.source = value; renderSourceFilters(); render(); };
    wrap.appendChild(b);
  });
}

function renderFilters() {
  const available = new Set(upcomingEvents().flatMap(e => e.genres || []));
  const preferred = ['ALL','DJ','MUSIC','DANCE','PSYTRANCE','PSY-TRANCE','QUEST','ANISON','IDOLM@STER','EVENT'];
  const filters = preferred.filter(g => g === 'ALL' || available.has(g));
  const wrap = document.getElementById('eventFilters');
  if (!wrap) return;
  wrap.innerHTML = '';
  filters.forEach(g => {
    const b = document.createElement('button');
    b.className = `chip${state.genre === g ? ' active' : ''}`;
    b.type = 'button';
    b.textContent = g;
    b.onclick = () => { state.genre = g; renderFilters(); render(); };
    wrap.appendChild(b);
  });
}

function render() {
  const all = upcomingEvents();
  const q = state.query.trim().toLowerCase();
  const items = all.filter(e => {
    const genreOk = state.genre === 'ALL' || (e.genres || []).includes(state.genre);
    const sourceOk = state.source === 'ALL'
      || (state.source === 'PUBLIC' && e.autoImported)
      || (state.source === 'CURATED' && !e.autoImported);
    const hay = `${e.name || ''} ${e.organizer || ''} ${e.worldName || ''} ${(e.genres || []).join(' ')}`.toLowerCase();
    return genreOk && sourceOk && (!q || hay.includes(q));
  });

  const grid = document.getElementById('eventGrid');
  const empty = document.getElementById('eventEmpty');
  const count = document.getElementById('eventCount');
  const live = items.filter(e => eventStatus(e) === 'LIVE NOW').length;
  count.textContent = live
    ? `${items.length} shown / ${all.length} upcoming · ${live} live`
    : `${items.length} shown / ${all.length} upcoming`;
  grid.innerHTML = items.map(eventCard).join('');
  empty.hidden = items.length > 0;
}

async function initEvents() {
  const count = document.getElementById('eventCount');
  try {
    const res = await fetch('data/events.json', {cache:'no-store'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.events = await res.json();
    renderSourceFilters();
    renderFilters();
    render();
  } catch (err) {
    count.textContent = 'Data error';
    document.getElementById('eventEmpty').hidden = false;
    console.error(err);
  }
}

document.getElementById('eventSearch')?.addEventListener('input', e => {
  state.query = e.target.value;
  render();
});

initEvents();
