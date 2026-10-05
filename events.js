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
  return `<article class="event-card ${status === 'LIVE NOW' ? 'event-live' : ''}">
    <div class="event-card-top"><span class="event-date">${esc(eventTime(e))}</span><span class="event-status">${status}</span></div>
    <h3><a class="world-title-link" href="${eventDetailUrl(e.id)}">${esc(e.name)}</a></h3>
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
      .filter(e => {
        if (!e || !e.start) return false;
        const end = e.end ? new Date(e.end).getTime() : new Date(e.start).getTime() + 6 * 60 * 60 * 1000;
        return end >= now;
      })
      .sort((a,b) => new Date(a.start) - new Date(b.start));
    const live = upcoming.filter(e => eventStatus(e, now) === 'LIVE NOW').length;
    count.textContent = live ? `${upcoming.length} upcoming · ${live} live` : `${upcoming.length} upcoming`;
    grid.innerHTML = upcoming.map(eventCard).join('');
    empty.hidden = upcoming.length > 0;
  } catch (err) {
    count.textContent = 'Data error';
    empty.hidden = false;
    console.error(err);
  }
}

initEvents();
