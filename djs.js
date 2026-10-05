const state = { genre: 'ALL', djs: [] };

function djProfileUrl(id) { return `djs/${id}.html`; }

function esc(s='') {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function renderFilters() {
  const available = new Set(state.djs.flatMap(d => d.genres || []));
  const preferred = ['ALL','PSY-TRANCE','FULL-ON','HI-TECH','PROGRESSIVE HOUSE','PROGRESSIVE PSYTRANCE',"DRUM'N'BASS",'GOA TRANCE','KAWAII'];
  const filters = preferred.filter(g => g === 'ALL' || available.has(g));
  const wrap = document.getElementById('djFilters');
  wrap.innerHTML = '';
  filters.forEach(g => {
    const b = document.createElement('button');
    b.className = `chip${state.genre === g ? ' active' : ''}`;
    b.textContent = g;
    b.onclick = () => { state.genre = g; renderFilters(); render(); };
    wrap.appendChild(b);
  });
}

function djCard(d) {
  const genres = (d.genres || []).map(g => `<span class="tag">${esc(g)}</span>`).join('');
  const crews = (d.affiliations || []).join(' / ');
  const source = d.source ? `<a class="dj-source" href="${esc(d.source)}" target="_blank" rel="noreferrer">SOURCE ↗</a>` : '';
  return `<article class="dj-card">
    <div class="dj-card-index">DJ</div>
    <h3>${d.id ? `<a class="world-title-link" href="${djProfileUrl(d.id)}">${esc(d.name)}</a>` : esc(d.name)}</h3>
    <div class="dj-role">${esc(d.role || 'DJ')}</div>
    <div class="dj-affiliation">${esc(crews)}</div>
    <div class="tags">${genres}</div>
    ${source}
  </article>`;
}

function render() {
  const items = state.djs
    .filter(d => state.genre === 'ALL' || (d.genres || []).includes(state.genre))
    .sort((a,b) => a.name.localeCompare(b.name));
  document.getElementById('djGrid').innerHTML = items.map(djCard).join('');
  document.getElementById('djCount').textContent = `${items.length} profiles · non-ranked`;
}

async function init() {
  try {
    const res = await fetch('data/djs.json', {cache:'no-store'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.djs = await res.json();
    renderFilters();
    render();
  } catch (err) {
    document.getElementById('djCount').textContent = 'Data error';
    console.error(err);
  }
}
init();
