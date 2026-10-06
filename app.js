const state = { worlds: [], events: [], editorScores: [] };
const WORLD_META_ENDPOINT = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-meta';
const WORLD_THUMB_ENDPOINT = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-thumb';
const SUPABASE_PUBLIC_KEY = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';

const fmt = new Intl.NumberFormat('en-US');

function esc(value='') {
  return String(value).replace(/[&<>'"]/g, ch => ({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[ch]));
}

function worldDetailUrl(id) { return `worlds/${id}.html`; }
function eventDetailUrl(id) { return id ? `events/${id}.html` : 'events.html'; }

// Catalog ranking snapshots intentionally omit all image URLs. The public
// world-thumb Edge Function already proxies verified, cached VRChat images;
// use it on first render rather than waiting for a separate metadata POST.
function worldImage(w) {
  const id = String(w?.id || '');
  if (/^wrld_[0-9a-fA-F-]{36}$/.test(id)) {
    return WORLD_THUMB_ENDPOINT + '?id=' + encodeURIComponent(id);
  }
  return w?.thumbnail || w?.imageUrl || '';
}

function handleWorldImageError(event) {
  const img = event.target;
  if (!(img instanceof HTMLImageElement)) return;
  const fallbackClass = img.dataset.worldImageFallback;
  if (!['focus-world-placeholder', 'editor-pick-placeholder'].includes(fallbackClass)) return;
  const placeholder = document.createElement('div');
  placeholder.className = fallbackClass;
  placeholder.textContent = 'VRC';
  img.replaceWith(placeholder);
}

document.addEventListener('error', handleWorldImageError, true);

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


function shareCampaign(w) {
  return 'editors_pick_' + String(w?.id || 'world').replace(/^wrld_/, '').slice(0, 8);
}

function shareWorldUrl(w) {
  const url = new URL(worldDetailUrl(w.id), location.href);
  url.searchParams.set('utm_source', 'x');
  url.searchParams.set('utm_medium', 'social');
  url.searchParams.set('utm_campaign', shareCampaign(w));
  return url.toString();
}

function shareOnX(score, w) {
  const text = `VRC Club Charts EDITOR'S PICK\n${w.name} — ${Number(score.total_score || 0)}/100\n人気ではなく、作り込みで評価。`;
  const intent = 'https://x.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(shareWorldUrl(w));
  window.open(intent, '_blank', 'noopener,noreferrer');
}

function wrapCanvasText(ctx, value, x, y, maxWidth, lineHeight, maxLines=2) {
  const chars = [...String(value || '')];
  const lines = [];
  let line = '';
  for (const ch of chars) {
    const test = line + ch;
    if (line && ctx.measureText(test).width > maxWidth) {
      lines.push(line);
      line = ch;
      if (lines.length >= maxLines) break;
    } else {
      line = test;
    }
  }
  if (lines.length < maxLines && line) lines.push(line);
  if (lines.length === maxLines && chars.join('').length > lines.join('').length) {
    let last = lines[lines.length - 1];
    while (last && ctx.measureText(last + '…').width > maxWidth) last = last.slice(0, -1);
    lines[lines.length - 1] = last + '…';
  }
  lines.forEach((part, i) => ctx.fillText(part, x, y + i * lineHeight));
  return y + Math.max(1, lines.length) * lineHeight;
}

function drawCover(ctx, image, x, y, width, height) {
  const iw = image.width || 1;
  const ih = image.height || 1;
  const scale = Math.max(width / iw, height / ih);
  const sw = width / scale;
  const sh = height / scale;
  const sx = (iw - sw) / 2;
  const sy = (ih - sh) / 2;
  ctx.drawImage(image, sx, sy, sw, sh, x, y, width, height);
}

async function loadShareImage(w) {
  async function loadProxy() {
    const response = await fetch(WORLD_THUMB_ENDPOINT + '?id=' + encodeURIComponent(w.id), {
      headers:{'apikey':SUPABASE_PUBLIC_KEY}
    });
    if (!response.ok) throw new Error('thumbnail unavailable');
    const blob = await response.blob();
    if ('createImageBitmap' in window) return await createImageBitmap(blob);
    return await new Promise((resolve, reject) => {
      const url = URL.createObjectURL(blob);
      const image = new Image();
      image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
      image.onerror = () => { URL.revokeObjectURL(url); reject(new Error('image decode failed')); };
      image.src = url;
    });
  }

  try {
    return await loadProxy();
  } catch (_) {
    try {
      const visuals = await fetchWorldVisuals([w.id]);
      mergeWorldVisuals(visuals);
      return await loadProxy();
    } catch (_) {
      return null;
    }
  }
}

async function saveEditorShareCard(score, w, button) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = 'GENERATING…';
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 1200;
    canvas.height = 630;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas unavailable');

    const bg = ctx.createLinearGradient(0, 0, 1200, 630);
    bg.addColorStop(0, '#081116');
    bg.addColorStop(.58, '#0b171d');
    bg.addColorStop(1, '#091014');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, 1200, 630);

    const image = await loadShareImage(w);
    if (image) {
      ctx.save();
      ctx.beginPath();
      ctx.rect(610, 0, 590, 630);
      ctx.clip();
      drawCover(ctx, image, 610, 0, 590, 630);
      ctx.restore();

      const fade = ctx.createLinearGradient(500, 0, 960, 0);
      fade.addColorStop(0, '#081116');
      fade.addColorStop(.35, 'rgba(8,17,22,.94)');
      fade.addColorStop(1, 'rgba(8,17,22,.16)');
      ctx.fillStyle = fade;
      ctx.fillRect(500, 0, 700, 630);

      const shade = ctx.createLinearGradient(0, 300, 0, 630);
      shade.addColorStop(0, 'rgba(5,12,16,0)');
      shade.addColorStop(1, 'rgba(5,12,16,.82)');
      ctx.fillStyle = shade;
      ctx.fillRect(610, 250, 590, 380);
    } else {
      const glow = ctx.createRadialGradient(930, 260, 20, 930, 260, 390);
      glow.addColorStop(0, 'rgba(233,196,119,.22)');
      glow.addColorStop(1, 'rgba(233,196,119,0)');
      ctx.fillStyle = glow;
      ctx.fillRect(520, 0, 680, 630);
    }

    ctx.fillStyle = '#e9c477';
    ctx.fillRect(64, 58, 92, 4);
    ctx.font = '700 22px system-ui, sans-serif';
    ctx.letterSpacing = '2px';
    ctx.fillText("VRC CLUB CHARTS / EDITOR'S PICK", 64, 102);

    ctx.fillStyle = '#f4fbfd';
    ctx.font = '800 60px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const titleBottom = wrapCanvasText(ctx, w.name, 64, 182, 585, 68, 2);

    ctx.fillStyle = '#8aa4ad';
    ctx.font = '500 24px system-ui, sans-serif';
    ctx.fillText('by ' + (w.author || '—'), 66, titleBottom + 6);

    ctx.fillStyle = '#ffe3a0';
    ctx.font = '800 92px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.fillText(String(Number(score.total_score || 0)), 62, 430);
    const numberWidth = ctx.measureText(String(Number(score.total_score || 0))).width;
    ctx.fillStyle = '#927f58';
    ctx.font = '700 25px ui-monospace, SFMono-Regular, Menlo, monospace';
    ctx.fillText('/100', 72 + numberWidth, 429);

    const cells = [
      ['VISUAL', score.visual, 20], ['LIGHT', score.lighting, 20],
      ['SOUND', score.sound, 15], ['SPATIAL', score.spatial, 15],
      ['INTERACT', score.interaction, 10], ['ORIGINAL', score.originality, 10],
      ['OPT', score.optimization, 10]
    ];
    let cx = 64;
    let cy = 476;
    ctx.font = '700 15px ui-monospace, SFMono-Regular, Menlo, monospace';
    for (const [label, value, maximum] of cells) {
      const cellWidth = 126;
      if (cx + cellWidth > 635) { cx = 64; cy += 48; }
      ctx.fillStyle = 'rgba(255,255,255,.055)';
      ctx.fillRect(cx, cy, cellWidth - 8, 34);
      ctx.fillStyle = '#9ab0b8';
      ctx.fillText(label + ' ' + value + '/' + maximum, cx + 9, cy + 22);
      cx += cellWidth;
    }

    ctx.fillStyle = 'rgba(255,255,255,.16)';
    ctx.fillRect(64, 592, 1072, 1);
    ctx.fillStyle = '#78919a';
    ctx.font = '600 17px system-ui, sans-serif';
    ctx.fillText('CRAFTSMANSHIP, NOT POPULARITY', 64, 618);
    ctx.textAlign = 'right';
    ctx.fillStyle = '#e9c477';
    ctx.fillText('vrc-club-charts.vercel.app', 1136, 618);
    ctx.textAlign = 'left';

    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png', .94));
    if (!blob) throw new Error('Could not create image');
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'vcc-editors-pick-' + String(w.id).replace(/[^a-zA-Z0-9_-]+/g, '-') + '.png';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  } catch (error) {
    console.error(error);
    button.textContent = 'CARD ERROR';
    setTimeout(() => { button.textContent = original; }, 1800);
    button.disabled = false;
    return;
  }
  button.textContent = 'CARD SAVED';
  setTimeout(() => { button.textContent = original; button.disabled = false; }, 1400);
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
    ? `<img src="${esc(imageSrc)}" alt="" loading="lazy" decoding="async" data-world-image-fallback="focus-world-placeholder" />`
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
    return `<article class="editor-pick-card">
      <a class="editor-pick-main" href="${worldDetailUrl(w.id)}">
        <div class="editor-pick-media">${imageSrc ? `<img src="${esc(imageSrc)}" alt="" loading="lazy" decoding="async" data-world-image-fallback="editor-pick-placeholder" />` : '<div class="editor-pick-placeholder">VRC</div>'}</div>
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
      </a>
      <div class="editor-pick-actions">
        <button class="editor-share-x" type="button" data-editor-share-x="${esc(w.id)}">SHARE ON X ↗</button>
        <button class="editor-share-card" type="button" data-editor-share-card="${esc(w.id)}">SAVE CARD PNG ↓</button>
      </div>
    </article>`;
  }).join('');

  wrap.querySelectorAll('[data-editor-share-x]').forEach(button => {
    button.addEventListener('click', () => {
      const id = button.dataset.editorShareX;
      const score = picks.find(row => row.world_id === id);
      const world = byId.get(id);
      if (score && world) shareOnX(score, world);
    });
  });
  wrap.querySelectorAll('[data-editor-share-card]').forEach(button => {
    button.addEventListener('click', async () => {
      const id = button.dataset.editorShareCard;
      const score = picks.find(row => row.world_id === id);
      const world = byId.get(id);
      if (score && world) await saveEditorShareCard(score, world, button);
    });
  });
}

function renderWorlds() {
  const available = state.worlds.filter(w => w.availabilityStatus !== 'unavailable');
  document.getElementById('metricWorlds').textContent = fmt.format(available.length);

  const grid = document.getElementById('focusWorldGrid');
  const chosen = pickWorlds(available);
  grid.innerHTML = chosen.length
    ? chosen.map(worldCard).join('')
    : '<div class="focus-loading">ワールド情報を表示できません。</div>';
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
  // Each feed is independent: an editor API outage must not blank Worlds or Events.
  async function safeJson(url, options) {
    try {
      const response = await fetch(url, options);
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return await response.json();
    } catch (error) {
      console.warn('Unable to load ' + url, error);
      return null;
    }
  }

  const [worldData, eventData, editorData] = await Promise.all([
    safeJson('data/weekly-ranking.json', {cache:'no-store'}),
    safeJson('data/events.json', {cache:'no-store'}),
    safeJson('https://ypqpgpetrriirywrzikj.supabase.co/rest/v1/editor_world_scores?select=*', {
      cache:'no-store',
      headers:{'apikey':'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK'}
    })
  ]);

  state.worlds = Array.isArray(worldData?.worlds) ? worldData.worlds : [];
  state.events = Array.isArray(eventData) ? eventData : [];
  state.editorScores = Array.isArray(editorData) ? editorData : [];
  renderEditorPicks();
  renderWorlds();
  renderEvents();

  if (!worldData) {
    document.getElementById('focusWorldGrid').innerHTML = '<div class="focus-loading">ワールド情報を表示できません。</div>';
  }
  if (!eventData) {
    document.getElementById('focusEvents').innerHTML = '<div class="focus-loading">イベント情報を表示できません。</div>';
  }

  if (!state.worlds.length) return;
  const byId = new Map(state.worlds.map(w => [w.id,w]));
  const editorIds = state.editorScores.filter(r => r.editor_pick === true)
    .sort((a,b)=>Number(b.total_score||0)-Number(a.total_score||0)).slice(0,3).map(r=>r.world_id);
  const targetIds = pickWorlds(state.worlds).map(w=>w.id);
  const visualIds = [...new Set([...editorIds,...targetIds])]
    .filter(id=>byId.has(id) && !worldImage(byId.get(id))).slice(0,20);
  if (visualIds.length) {
    try {
      const visuals = await fetchWorldVisuals(visualIds);
      if (mergeWorldVisuals(visuals)) {
        renderEditorPicks();
        renderWorlds();
      }
    } catch (error) {
      console.warn('World thumbnail enrichment unavailable', error);
    }
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
