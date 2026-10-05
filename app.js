const state = { lang: 'ja', worlds: [], events: [], reviewScores: null };

const copy = {
  ja: {
    heroTitle: 'VRChatクラブを、<br><em>作り込みで比べる。</em>',
    heroCopy: '人気順では見つからない、空間・照明・音響・ギミックの完成度。まずは世界中のクラブ情報を集め、レビュアー評価が揃ったところから本当のCraftsmanship Rankingへ移行します。',
    missionTitle: '人気ではなく、<br>作り込みで選ぶ。',
    missionCopy: 'VisitsやFavoritesは「人気」の参考にはなります。でも、このサイトが最終的に答えたいのは「VRChatで最も作り込まれたクラブはどこか？」です。'
  },
  en: {
    heroTitle: 'Rank VRChat clubs<br><em>by craftsmanship.</em>',
    heroCopy: 'Beyond popularity: spatial design, lighting, sound and interaction. We are building the directory first, then moving to a reviewer-based Craftsmanship Ranking as panel reviews accumulate.',
    missionTitle: 'Not popularity.<br>Craftsmanship.',
    missionCopy: 'Visits and Favorites can show popularity. The question this project ultimately wants to answer is: which VRChat clubs are the most carefully crafted?'
  }
};

const fmt = new Intl.NumberFormat('en-US');

function esc(value='') {
  return String(value).replace(/[&<>'"]/g, ch => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[ch]));
}

function worldDetailUrl(id) { return `worlds/${id}.html`; }
function eventDetailUrl(id) { return id ? `events/${id}.html` : 'events.html'; }

function applyLanguage() {
  const t = copy[state.lang];
  document.getElementById('heroTitle').innerHTML = t.heroTitle;
  document.getElementById('heroCopy').textContent = t.heroCopy;
  document.getElementById('missionTitle').innerHTML = t.missionTitle;
  document.getElementById('missionCopy').textContent = t.missionCopy;
  document.getElementById('langToggle').textContent = state.lang === 'ja' ? 'EN' : 'JA';
}

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
    .slice(0, 8);
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

function renderWorlds() {
  const available = state.worlds.filter(w => w.availabilityStatus !== 'unavailable');
  document.getElementById('metricWorlds').textContent = fmt.format(available.length);
  document.getElementById('metricPanel').textContent = fmt.format(state.reviewScores?.summary?.scoredWorlds || 0);

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
  const when = new Intl.DateTimeFormat(state.lang === 'ja' ? 'ja-JP' : 'en-US', {
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
    .slice(0, 4);
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
    renderWorlds();
    renderEvents();
  } catch (err) {
    console.error(err);
    document.getElementById('focusWorldGrid').innerHTML = '<div class="focus-loading">Data unavailable.</div>';
    document.getElementById('focusEvents').innerHTML = '<div class="focus-loading">Event data unavailable.</div>';
  }
}

document.getElementById('langToggle')?.addEventListener('click', () => {
  state.lang = state.lang === 'ja' ? 'en' : 'ja';
  applyLanguage();
  renderEvents();
});

applyLanguage();
load();
