const state = { worlds: [], events: [], reviewScores: null, editorScores: [] };
const WORLD_META_ENDPOINT = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-meta';
const SUPABASE_PUBLIC_KEY = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';

const fmt = new Intl.NumberFormat('en-US');

function esc(value='') {
  return String(value).replace(/[&<>'"]/g, ch => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[ch]));
}

function worldDetailUrl(id) { return `worlds/${id}.html`; }
function eventDetailUrl(id) { return id ? `events/${id}.html` : 'events.html'; }

function worldImage(w) {
  return w?.thumbnail || w?.imageUrl || '';
}

async function fetchWorldVisuals(ids) {
  const unique = [...new Set((ids || []).filter(Boolean))].slice(0, 20);
  if (!unique.length) return [];
  try {
    const response = await fetch(WORLD_META_ENDPOINT, {
      method:'POST',
      headers:{
        'apikey':SUPABASE_PUBLIC_KEY,
        'Content-Type':'application/json'
      },
      body:JSON.stringify({ids:unique})
    });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data?.items) ? data.items : [];
  } catch (_) {
    return [];
  }
}

function mergeWorldVisuals(items) {
  if (!Array.isArray(items) || !items.length) return false;
  const byId = new Map(state.worlds.map(w => [w.id, w]));
  let changed = false;
  for (const row of items) {
    const w = byId.get(row.world_id);
    if (!w) continue;
    const image = row.thumbnail_url || row.image_url || '';
    if (image && w.thumbnail !== image) {
      w.thumbnail = image;
      w.imageUrl = row.image_url || w.imageUrl;
      changed = true;
    }
  }
  return changed;
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
    .slice(0, 6);
}

function worldCard(w) {
  const imageSrc = worldImage(w);
  const image = imageSrc
    ? `<img src="${esc(imageSrc)}" alt="" loading="lazy" decoding="async" />`
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

function editorScoreMap() {
  return new Map((state.editorScores || []).map(row => [row.world_id, row]));
}

function renderEditorPicks() {
  const section = document.getElementById('editorPicksSection');
  const wrap = document.getElementById('editorPicks');
  if (!section || !wrap) return;

  const byId = new Map(state.worlds.map(w => [w.id, w]));
  const editors = editorScoreMap();
  const picks = (state.editorScores || [])
    .filter(r => r.editor_pick === true && byId.has(r.world_id))
    .sort((a,b) => Number(b.total_score || 0) - Number(a.total_score || 0))
    .slice(0, 3);

  if (!picks.length) {
    section.hidden = true;
    wrap.innerHTML = '';
    return;
  }

  section.hidden = false;
  wrap.innerHTML = picks.map((r,i) => {
    const w = byId.get(r.world_id);
    const imageSrc = worldImage(w);
    return `<a class="editor-pick-card" href="${worldDetailUrl(w.id)}">
      <div class="editor-pick-media">${imageSrc ? `<img src="${esc(imageSrc)}" alt="" loading="lazy" decoding="async" />` : '<div class="editor-pick-placeholder">VRC</div>'}</div>
      <div class="editor-pick-body">
      <div class="editor-pick-top">
        <span>EDITOR'S PICK ${String(i+1).padStart(2,'0')}</span>
        <b>${Number(r.total_score || 0)}<small>/100</small></b>
      </div>
      <h3>${esc(w.name)}</h3>
      <p class="editor-pick-author">by ${esc(w.author || '—')}</p>
      ${r.note ? `<p class="editor-pick-note">${esc(r.note)}</p>` : ''}
      <div class="editor-pick-breakdown">
        <span>V ${r.visual}/20</span><span>L ${r.lighting}/20</span><span>S ${r.sound}/15</span>
        <span>SP ${r.spatial}/15</span><span>I ${r.interaction}/10</span>
        <span>O ${r.originality}/10</span><span>OPT ${r.optimization}/10</span>
      </div>
      </div>
    </a>`;
  }).join('');
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
  const editors = editorScoreMap();
  const rows = (state.reviewScores?.worlds || [])
    .filter(r => Number.isFinite(Number(r.score)))
    .map(r => ({...r, world: byId.get(r.worldId)}))
    .filter(r => r.world)
    .sort((a,b) => Number(b.score) - Number(a.score));

  if (!rows.length) {
    board.innerHTML = `<div class="ranking-empty">
      <div class="ranking-empty-visual" aria-hidden="true">
        <span data-text="00">00</span>
        <b>AWAITING REVIEWS</b>
      </div>
      <div class="ranking-empty-copy">
        <span>OFFICIAL PANEL RANKING</span>
        <strong>正式ランキング準備中</strong>
        <p>3人以上の独立レビューが揃ったワールドから順位を公開します。人気順や仮点数では埋めません。</p>
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
      const editor = editors.get(w.id);
      const editorMeta = editor ? ` · EDITOR ${Number(editor.total_score)}${editor.editor_pick ? " ★" : ""}` : '';
      const imageSrc = worldImage(w);
      return `<a class="panel-rank-row ${i === 0 ? 'rank-first' : ''}" href="${worldDetailUrl(w.id)}">
        <span class="panel-rank-no">${String(i+1).padStart(2,'0')}</span>
        <span class="panel-rank-thumb">${imageSrc ? `<img src="${esc(imageSrc)}" alt="" loading="lazy" decoding="async" />` : '<i>VRC</i>'}</span>
        <span class="panel-rank-world">
          <small>${status} · ${r.reviewCount} REVIEWS · ${confidence} CONFIDENCE${editorMeta}</small>
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
    const [worldRes,eventRes,reviewRes,editorRes] = await Promise.all([
      fetch('data/weekly-ranking.json', {cache:'no-store'}),
      fetch('data/events.json', {cache:'no-store'}),
      fetch('data/review-scores.json', {cache:'no-store'}),
      fetch('https://ypqpgpetrriirywrzikj.supabase.co/rest/v1/editor_world_scores?select=*', {
        cache:'no-store',
        headers:{'apikey':'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK'}
      })
    ]);
    if (!worldRes.ok) throw new Error('World data unavailable');
    state.worlds = (await worldRes.json()).worlds || [];
    state.events = eventRes.ok ? await eventRes.json() : [];
    state.reviewScores = reviewRes.ok ? await reviewRes.json() : null;
    state.editorScores = editorRes.ok ? await editorRes.json() : [];
    renderEditorPicks();
    renderCraftRanking();
    renderWorlds();
    renderEvents();

    const byId = new Map(state.worlds.map(w => [w.id,w]));
    const editorIds = (state.editorScores || []).filter(r => r.editor_pick === true).sort((a,b)=>Number(b.total_score||0)-Number(a.total_score||0)).slice(0,3).map(r=>r.world_id);
    const rankIds = (state.reviewScores?.worlds || []).filter(r=>Number.isFinite(Number(r.score))).sort((a,b)=>Number(b.score)-Number(a.score)).slice(0,10).map(r=>r.worldId);
    const targetIds = pickWorlds(state.worlds).map(w=>w.id);
    const visualIds = [...new Set([...editorIds,...rankIds,...targetIds])].filter(id=>byId.has(id) && !worldImage(byId.get(id))).slice(0,20);
    if (visualIds.length) {
      const visuals = await fetchWorldVisuals(visualIds);
      if (mergeWorldVisuals(visuals)) {
        renderEditorPicks();
        renderCraftRanking();
        renderWorlds();
      }
    }
  } catch (err) {
    console.error(err);
    const ranking = document.getElementById('craftRanking');
    if (ranking) ranking.innerHTML = '<div class="ranking-loading">Panel ranking unavailable.</div>';
    document.getElementById('focusWorldGrid').innerHTML = '<div class="focus-loading">Data unavailable.</div>';
    document.getElementById('focusEvents').innerHTML = '<div class="focus-loading">Event data unavailable.</div>';
  }
}

load();


function initRankingScene() {
  const hero = document.querySelector('.ranking-hero');
  const scene = document.querySelector('.ranking-scene');
  if (!hero || !scene || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  let raf = 0;
  let tx = 0;
  let ty = 0;
  let cx = 0;
  let cy = 0;

  function draw() {
    cx += (tx - cx) * 0.075;
    cy += (ty - cy) * 0.075;
    const sx = cx.toFixed(3);
    const sy = cy.toFixed(3);
    scene.style.setProperty('--scene-x', sx);
    scene.style.setProperty('--scene-y', sy);
    hero.style.setProperty('--scene-x', sx);
    hero.style.setProperty('--scene-y', sy);
    if (Math.abs(tx - cx) > 0.002 || Math.abs(ty - cy) > 0.002) {
      raf = requestAnimationFrame(draw);
    } else {
      raf = 0;
    }
  }

  hero.addEventListener('pointermove', e => {
    const r = hero.getBoundingClientRect();
    tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
    ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
    if (!raf) raf = requestAnimationFrame(draw);
  }, {passive:true});

  hero.addEventListener('pointerleave', () => {
    tx = 0;
    ty = 0;
    if (!raf) raf = requestAnimationFrame(draw);
  }, {passive:true});
}

initRankingScene();
