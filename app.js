const state = { worlds: [], events: [], reviewScores: null };

const fmt = new Intl.NumberFormat('en-US');

function esc(value='') {
  return String(value).replace(/[&<>'"]/g, ch => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[ch]));
}

function worldDetailUrl(id) { return `worlds/${id}.html`; }
function eventDetailUrl(id) { return id ? `events/${id}.html` : 'events.html'; }

function pickWorlds(worlds) {
  return worlds
    .filter(w => w.availabilityStatus !== 'unavailable')
    .sort((a,b) => {
      const aReady = a.thumbnail ? 1 : 0;
      const bReady = b.thumbnail ? 1 : 0;
      if (aReady !== bReady) return bReady - aReady;
      const af = Number(a.totals?.favorites || 0);
      const bf = Number(b.totals?.favorites || 0);
      if (af !== bf) return bf - af;
      return String(a.name).localeCompare(String(b.name));
    })
    .slice(0, 6);
}

function worldCard(w) {
  const image = w.thumbnail
    ? `<img src="${esc(w.thumbnail)}" alt="" loading="lazy" decoding="async" />`
    : '<div class="focus-world-placeholder">VRC</div>';
  const tags = (w.genres || []).slice(0,3).map(g=>`<span>${esc(g)}</span>`).join('');
  return `<a class="focus-world-card" href="${worldDetailUrl(w.id)}">
    <div class="focus-world-media">${image}</div>
    <div class="focus-world-copy">
      <div class="focus-world-label">${w.chartEligible === false ? 'DIRECTORY' : 'WORLD'}</div>
      <h3>${esc(w.name)}</h3>
      <p>by ${esc(w.author || '—')}</p>
      <div class="focus-world-tags">${tags}</div>
    </div>
    <b>↗</b>
  </a>`;
}

function renderCraftRanking() {
  const board = document.getElementById('craftRanking');
  if (!board) return;

  const summary = state.reviewScores?.summary || {};
  const rankedCount = Number(summary.rankedWorlds || 0);
  const scoredCount = Number(summary.scoredWorlds || 0);
  const reviewCount = Number(summary.reviews || 0);
  const reviewerCount = Number(summary.reviewers || 0);

  document.getElementById('metricRanked').textContent = fmt.format(rankedCount);
  document.getElementById('metricPanel').textContent = fmt.format(scoredCount);
  document.getElementById('metricReviews').textContent = fmt.format(reviewCount);
  document.getElementById('metricReviewers').textContent = fmt.format(reviewerCount);

  const byId = new Map(state.worlds.map(w => [w.id, w]));
  const rows = (state.reviewScores?.worlds || [])
    .filter(r => Number.isFinite(Number(r.score)))
    .map(r => ({...r, world: byId.get(r.worldId)}))
    .filter(r => r.world)
    .sort((a,b) => Number(b.score) - Number(a.score));

  if (!rows.length) {
    board.innerHTML = `<div class="ranking-empty">
      <div class="ranking-empty-mark">—</div>
      <div>
        <span>OFFICIAL PANEL RANKING</span>
        <strong>まだ正式順位はありません。</strong>
        <p>3人以上の独立したレビュアー評価が集まったワールドから、ここにCraftsmanship Rankingが表示されます。仮の点数や人気順で埋めることはしません。</p>
      </div>
      <a class="secondary-button" href="reviewer.html">HOW IT WORKS ↗</a>
    </div>`;
    return;
  }

  board.innerHTML = `<div class="ranking-table">
    ${rows.slice(0,10).map((r,i) => {
      const w = r.world;
      const status = String(r.status || 'provisional').toUpperCase();
      const confidence = String(r.confidence || 'low').toUpperCase();
      return `<a class="panel-rank-row ${i === 0 ? 'rank-first' : ''}" href="${worldDetailUrl(w.id)}">
        <span class="panel-rank-no">${String(i+1).padStart(2,'0')}</span>
        <span class="panel-rank-world">
          <small>${status} · ${r.reviewCount} REVIEWS · ${confidence} CONFIDENCE</small>
          <strong>${esc(w.name)}</strong>
          <em>by ${esc(w.author || '—')}</em>
        </span>
        <span class="panel-rank-score"><b>${Number(r.score).toFixed(1)}</b><small>/ 100</small></span>
        <span class="panel-rank-arrow">↗</span>
      </a>`;
    }).join('')}
  </div>`;
}

function renderWorlds() {
  const available = state.worlds.filter(w => w.availabilityStatus !== 'unavailable');
  document.getElementById('metricWorlds').textContent = fmt.format(available.length);

  const grid = document.getElementById('focusWorldGrid');
  const chosen = pickWorlds(available);
  grid.innerHTML = chosen.length
    ? chosen.map(worldCard).join('')
    : '<div class="focus-loading">World data unavailable.</div>';
}

function eventStatus(e, now=Date.now()) {
  const start = new Date(e.start).getTime();
  const end = e.end ? new Date(e.end).getTime() : start + 4*60*60*1000;
  if (now >= start && now <= end) return 'LIVE';
  return 'NEXT';
}

function eventCard(e) {
  const d = new Date(e.start);
  const when = new Intl.DateTimeFormat('ja-JP', {
    month:'short', day:'numeric', weekday:'short', hour:'2-digit', minute:'2-digit'
  }).format(d);
  const source = e.autoImported ? 'PUBLIC FEED' : 'CURATED';
  return `<a class="focus-event-row" href="${eventDetailUrl(e.id)}">
    <div class="focus-event-time"><span>${esc(when)}</span><b>${eventStatus(e)}</b></div>
    <div class="focus-event-name">
      <small>${source}</small>
      <strong>${esc(e.name)}</strong>
      <span>${esc(e.worldName || 'VRChat event instance')}</span>
    </div>
    <i>↗</i>
  </a>`;
}

function renderEvents() {
  const now = Date.now();
  const upcoming = state.events
    .filter(e => {
      if (!e?.start) return false;
      const start = new Date(e.start).getTime();
      const end = e.end ? new Date(e.end).getTime() : start + 6*60*60*1000;
      return end >= now;
    })
    .sort((a,b) => new Date(a.start) - new Date(b.start))
    .slice(0, 3);
  const wrap = document.getElementById('focusEvents');
  wrap.innerHTML = upcoming.length
    ? upcoming.map(eventCard).join('')
    : '<div class="focus-loading">Upcoming events are being collected.</div>';
}

async function load() {
  try {
    const [worldRes,eventRes,reviewRes] = await Promise.all([
      fetch('data/weekly-ranking.json', {cache:'no-store'}),
      fetch('data/events.json', {cache:'no-store'}),
      fetch('data/review-scores.json', {cache:'no-store'})
    ]);
    if (!worldRes.ok) throw new Error('World data unavailable');
    state.worlds = (await worldRes.json()).worlds || [];
    state.events = eventRes.ok ? await eventRes.json() : [];
    state.reviewScores = reviewRes.ok ? await reviewRes.json() : null;
    renderCraftRanking();
    renderWorlds();
    renderEvents();
  } catch (err) {
    console.error(err);
    const ranking = document.getElementById('craftRanking');
    if (ranking) ranking.innerHTML = '<div class="ranking-loading">Panel ranking unavailable.</div>';
    document.getElementById('focusWorldGrid').innerHTML = '<div class="focus-loading">Data unavailable.</div>';
    document.getElementById('focusEvents').innerHTML = '<div class="focus-loading">Event data unavailable.</div>';
  }
}

load();
