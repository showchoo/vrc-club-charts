const state = { view: 'overall', genre: 'ALL', query: '', lang: 'ja', data: null };

const copy = {
  ja: {
    weekly: 'WEEKLY VR NIGHTLIFE INDEX',
    heroA: '今週、行くべき', heroB: 'VRChatクラブ。',
    heroCopy: '来場の伸びと、お気に入り増加。そして空間・照明・音響・ギミックの作り込み。人気だけでは見つからないクラブを毎週ランキングします。',
    methodTitle: '順位を「人気だけ」にしない。', trendTitle:'Trending 55%',
    trendCopy:'前週からのVisits増加とFavorites増加を中心に算出。古い定番だけが上位を独占しないよう、伸びを重視します。',
    craftTitle:'Craftsmanship 45%', craftCopy:'Visual / Lighting / Sound / Spatial / Interaction / Originality / Optimizationを編集部評価。順位の購入は不可。',
    updateTitle:'Weekly refresh', updateCopy:'公開ワールドIDを週1回スナップショット化し、差分だけを静的JSONへ反映。閲覧時にVRChat APIを呼ばない設計です。',
    pitchTitle:'クラブを登録する。', pitchCopy:'Creator submission は公開ベータ後に受付予定です。ランキング順位そのものを販売することはありません。', submitSoon:'登録受付は準備中'
  },
  en: {
    weekly: 'WEEKLY VR NIGHTLIFE INDEX',
    heroA: 'The VRChat clubs', heroB: 'worth entering now.',
    heroCopy: 'Weekly growth, favorite momentum, and editorial craft scores for spatial design, lighting, sound and interaction — not just lifetime popularity.',
    methodTitle: 'Popularity is only half the story.', trendTitle:'Trending 55%',
    trendCopy:'Weighted from weekly visit growth and favorite growth, so old classics do not automatically dominate the chart.',
    craftTitle:'Craftsmanship 45%', craftCopy:'Editorial scoring across Visual, Lighting, Sound, Spatial, Interaction, Originality and Optimization. Rankings are never for sale.',
    updateTitle:'Weekly refresh', updateCopy:'Public world IDs are snapshotted weekly and compiled to static JSON. Page views never call the VRChat API.',
    pitchTitle:'Submit a club.', pitchCopy:'Creator submissions will open after public beta. Ranking positions will never be sold.', submitSoon:'Submission coming soon'
  }
};

const fmt = new Intl.NumberFormat('en-US');
const scoreOf = (w) => {
  const value = w.scores?.[state.view];
  return value == null ? -1 : Number(value);
};

function worldUrl(id) { return `https://vrchat.com/home/world/${id}`; }
function formatDelta(n) { return n == null ? 'collecting' : `${n >= 0 ? '+' : ''}${fmt.format(n)}`; }

function setView(view) {
  state.view = view;
  document.querySelectorAll('[data-view]').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  const labels = {
    overall: ['WEEKLY CHART', state.lang === 'ja' ? '総合ランキング' : 'Overall ranking', state.lang === 'ja' ? '週間トレンドと編集部の作り込み評価を合成。' : 'Weekly momentum + editorial craftsmanship.'],
    trending: ['MOMENTUM', state.lang === 'ja' ? '急上昇ランキング' : 'Trending ranking', state.lang === 'ja' ? '今週、実際に伸びたクラブを優先。' : 'Prioritizes clubs gaining attention this week.'],
    craftsmanship: ['EDITORIAL', state.lang === 'ja' ? '作り込み度ランキング' : 'Craftsmanship ranking', state.lang === 'ja' ? '空間・照明・音響・独創性を100点で評価。' : 'Spatial, lighting, audio and originality scored out of 100.']
  }[view];
  document.getElementById('chartKicker').textContent = labels[0];
  document.getElementById('chartTitle').textContent = labels[1];
  const seedTrend = state.data?.status !== 'live' && view === 'trending';
  const seedOverall = state.data?.status !== 'live' && view === 'overall';
  document.getElementById('chartDescription').textContent = seedTrend
    ? (state.lang === 'ja' ? '2回目のスナップショット後に週間差分が有効になります。' : 'Weekly momentum activates after the second snapshot.')
    : seedOverall
      ? (state.lang === 'ja' ? '現在はSeedモード。週間データが揃うまで暫定Craftsmanship順です。' : 'Seed mode: provisional Craftsmanship order until weekly data is available.')
      : labels[2];
  render();
}

function buildGenres(worlds) {
  const genres = ['ALL', ...new Set(worlds.flatMap(w => w.genres || []))];
  const wrap = document.getElementById('genreFilters');
  wrap.innerHTML = '';
  genres.slice(0, 10).forEach(g => {
    const b = document.createElement('button');
    b.className = `chip${state.genre === g ? ' active' : ''}`;
    b.textContent = g;
    b.onclick = () => { state.genre = g; buildGenres(worlds); render(); };
    wrap.appendChild(b);
  });
}

function visibleScore(w) {
  if (state.data?.status !== 'live' && state.view === 'trending') return '—';
  const value = w.scores?.[state.view];
  return value == null ? '—' : Number(value).toFixed(1);
}

function discoveryCard(w) {
  return `<article class="discovery-card">
    <div class="discovery-topline"><span>PENDING REVIEW</span><a href="${worldUrl(w.id)}" target="_blank" rel="noreferrer">↗</a></div>
    <h3>${escapeHtml(w.name)}</h3>
    <div class="author">by ${escapeHtml(w.author || '—')}</div>
    <div class="tags">${(w.genres || []).slice(0,4).map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>
  </article>`;
}

function card(w, rank) {
  return `<article class="podium-card">
    <div class="rank-badge">${String(rank).padStart(2,'0')}</div>
    <h3>${escapeHtml(w.name)}</h3>
    <div class="author">by ${escapeHtml(w.author || '—')}</div>
    <div class="tags">${(w.genres || []).slice(0,4).map(t=>`<span class="tag">${escapeHtml(t)}</span>`).join('')}</div>
    <div class="score-line">
      <div><div class="score-big">${visibleScore(w)}</div><div class="score-label">${state.view} score</div></div>
      <div class="delta">${formatDelta(w.weekly?.visits)} visits</div>
    </div>
  </article>`;
}

function row(w, rank) {
  return `<article class="rank-row">
    <div class="rank-index">${String(rank).padStart(2,'0')}</div>
    <div><div class="world-name">${escapeHtml(w.name)}</div><div class="world-meta">${escapeHtml(w.author || '—')} · ${(w.genres||[]).join(' / ')}</div></div>
    <div class="metric"><strong>${visibleScore(w)}</strong><span>score</span></div>
    <div class="metric"><strong>${formatDelta(w.weekly?.visits)}</strong><span>7d visits</span></div>
    <div class="metric"><strong>${formatDelta(w.weekly?.favorites)}</strong><span>7d favs</span></div>
    <a class="world-link" href="${worldUrl(w.id)}" target="_blank" rel="noreferrer" title="Open in VRChat">↗</a>
  </article>`;
}

function escapeHtml(s='') { return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

function render() {
  if (!state.data) return;
  const q = state.query.trim().toLowerCase();
  const worlds = state.data.worlds.filter(w => {
    const genreOk = state.genre === 'ALL' || (w.genres || []).includes(state.genre);
    const hay = `${w.name} ${w.author} ${(w.genres||[]).join(' ')}`.toLowerCase();
    return genreOk && (!q || hay.includes(q));
  });

  const discovery = worlds.filter(w => w.editorialStatus === 'unreviewed');
  let ranked = worlds.filter(w => {
    if (state.view === 'trending' && state.data.status === 'live') return true;
    return w.editorialStatus !== 'unreviewed';
  });

  ranked.sort((a,b) => scoreOf(b) - scoreOf(a));
  const top = ranked.slice(0,3), rest = ranked.slice(3);
  document.getElementById('podium').innerHTML = top.map((w,i)=>card(w,i+1)).join('');
  document.getElementById('ranking').innerHTML = rest.map((w,i)=>row(w,i+4)).join('');
  document.getElementById('emptyState').hidden = ranked.length > 0;

  const discoverySection = document.getElementById('discoverySection');
  const discoveryGrid = document.getElementById('discoveryGrid');
  if (discoverySection && discoveryGrid) {
    discoverySection.hidden = discovery.length === 0;
    discoveryGrid.innerHTML = discovery
      .sort((a,b) => a.name.localeCompare(b.name))
      .map(discoveryCard)
      .join('');
  }
}

function applyLanguage() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll('[data-i18n]').forEach(el => el.textContent = copy[state.lang][el.dataset.i18n]);
  document.getElementById('langToggle').textContent = state.lang === 'ja' ? 'EN' : 'JA';
  document.getElementById('searchInput').placeholder = state.lang === 'ja' ? 'ワールド名・作者・ジャンル' : 'World, creator or genre';
  const discoveryTitle = document.getElementById('discoveryTitle');
  const discoveryNote = document.getElementById('discoveryNote');
  if (discoveryTitle) discoveryTitle.textContent = state.lang === 'ja' ? '掲載候補 / 未レビュー' : 'Discovery / pending review';
  if (discoveryNote) discoveryNote.textContent = state.lang === 'ja'
    ? 'World IDと公開状態を確認済み。作り込み評価は現地確認後にランキングへ反映します。'
    : 'World identity and public status verified. Editorial craft scoring follows an in-world review.';
  setView(state.view);
}

async function init() {
  try {
    const res = await fetch('data/weekly-ranking.json', {cache:'no-store'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.data = await res.json();
    document.getElementById('dataStatus').textContent = state.data.status === 'live' ? 'LIVE DATA' : 'MVP SEED';
    document.getElementById('updatedAt').textContent = state.data.updatedAt || '—';
    document.getElementById('worldCount').textContent = `${state.data.worlds.length} worlds`;
    buildGenres(state.data.worlds);
    render();
  } catch (e) {
    document.getElementById('dataStatus').textContent = 'DATA ERROR';
    document.getElementById('chartDescription').textContent = 'data/weekly-ranking.json を読み込めませんでした。ローカルではHTTPサーバー経由で開いてください。';
    console.error(e);
  }
}

document.querySelectorAll('[data-view]').forEach(el => el.addEventListener('click', () => setView(el.dataset.view)));
document.getElementById('searchInput').addEventListener('input', e => { state.query = e.target.value; render(); });
document.getElementById('langToggle').addEventListener('click', () => { state.lang = state.lang === 'ja' ? 'en' : 'ja'; applyLanguage(); });
init();
