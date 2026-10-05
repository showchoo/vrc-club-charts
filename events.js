const fmtDate = new Intl.DateTimeFormat('ja-JP', {
  month: 'short',
  day: 'numeric',
  weekday: 'short',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short'
});

function esc(s='') {
  return String(s).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}

function eventCard(e) {
  const start = new Date(e.start);
  const tags = (e.genres || []).slice(0,4).map(g => `<span class="tag">${esc(g)}</span>`).join('');
  const world = e.worldId
    ? `<a href="worlds/${esc(e.worldId)}.html">${esc(e.worldName || e.worldId)}</a>`
    : esc(e.worldName || 'World TBA');
  const link = e.url
    ? `<a class="event-link" href="${esc(e.url)}" target="_blank" rel="noreferrer">DETAILS ↗</a>`
    : '';
  return `<article class="event-card">
    <div class="event-date">${esc(fmtDate.format(start))}</div>
    <h3>${esc(e.name)}</h3>
    <div class="event-world">${world}</div>
    <div class="event-organizer">by ${esc(e.organizer || '—')}</div>
    <div class="tags">${tags}</div>
    ${link}
  </article>`;
}

async function initEvents() {
  const grid = document.getElementById('eventGrid');
  const empty = document.getElementById('eventEmpty');
  const count = document.getElementById('eventCount');
  try {
    const res = await fetch('data/events.json', {cache:'no-store'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const events = await res.json();
    const now = Date.now();
    const upcoming = events
      .filter(e => e && e.start && new Date(e.start).getTime() >= now - 6 * 60 * 60 * 1000)
      .sort((a,b) => new Date(a.start) - new Date(b.start));
    count.textContent = `${upcoming.length} upcoming`;
    grid.innerHTML = upcoming.map(eventCard).join('');
    empty.hidden = upcoming.length > 0;
  } catch (err) {
    count.textContent = 'Data error';
    empty.hidden = false;
    console.error(err);
  }
}

initEvents();
