(() => {
  'use strict';

  const root = document.getElementById('aiScoutSection');
  const status = document.getElementById('aiScoutStatus');
  const grid = document.getElementById('aiScoutGrid');
  if (!root || !status || !grid) return;

  const metaEndpoint = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-meta';
  const publicKey = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';
  const allowedWorld = /^wrld_[0-9a-fA-F-]{36}$/;

  const el = (name, cls, value) => {
    const node = document.createElement(name);
    if (cls) node.className = cls;
    if (value != null) node.textContent = String(value);
    return node;
  };

  function drawCard(item, index, isAssessed, thumbnail) {
    const card = el('article', 'ai-scout-card');
    const link = el('a', 'ai-scout-link');
    if (item.sourceType === 'discovery') {
      link.href = 'https://vrcmap.com/world/' + item.id;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    } else {
      link.href = 'worlds/' + item.id + '.html';
    }

    const media = el('div', 'ai-scout-media');
    if (thumbnail && /^https:\/\/api\.vrchat\.cloud\//i.test(thumbnail)) {
      const image = document.createElement('img');
      image.src = thumbnail;
      image.alt = '';
      image.loading = 'lazy';
      image.decoding = 'async';
      media.appendChild(image);
    } else {
      media.appendChild(el('span', 'ai-scout-placeholder', 'VCC / DISCOVERY'));
    }
    media.appendChild(el('span', 'ai-scout-number', isAssessed ? ('VISUAL ' + String(index + 1).padStart(2, '0')) : 'DISCOVERY'));
    link.appendChild(media);

    const copy = el('div', 'ai-scout-copy');
    const meta = el('div', 'ai-scout-meta');
    meta.appendChild(el('span', '', isAssessed ? 'ビジュアル評価' : 'DISCOVERY'));
    if (isAssessed && Number.isInteger(item.visualPotential)) {
      const score = el('strong', 'ai-scout-score', item.visualPotential);
      score.appendChild(el('small', '', '/100'));
      meta.appendChild(score);
    } else {
      meta.appendChild(el('span', 'ai-scout-wait', '評価前'));
    }
    copy.appendChild(meta);
    copy.appendChild(el('h3', '', item.name || 'World'));
    copy.appendChild(el('p', 'ai-scout-author', 'by ' + (item.author || 'Unknown')));

    const signals = Array.isArray(item.signals) && item.signals.length ?
      item.signals.slice(0, 5).join(' / ') : 'NIGHTLIFE WORLD';
    copy.appendChild(el('p', 'ai-scout-reason', isAssessed ?
      (item.reasonJa || '公開画像の印象から推定した参考評価です。') :
      '発見の手がかり · ' + signals));

    const caution = isAssessed ?
      (item.cautionsJa || '内部の音響・操作性・動作性能は未評価です。') :
      item.sourceType === 'discovery' ?
        '探索中のWorldです。公式ディレクトリへの掲載は未確定です。' :
        '画像評価前のWorldです。表示タグは発見の手がかりです。';
    copy.appendChild(el('p', 'ai-scout-caution', caution));
    link.appendChild(copy);
    card.appendChild(link);
    return card;
  }

  async function load() {
    try {
      const [scoutRes, worldRes] = await Promise.all([
        fetch('data/ai-scout.json', {cache: 'no-store'}),
        fetch('data/weekly-ranking.json', {cache: 'no-store'}).catch(() => null)
      ]);
      if (!scoutRes.ok) throw new Error('Scout data unavailable');
      const data = await scoutRes.json();
      const worldData = worldRes?.ok ? await worldRes.json().catch(() => ({})) : {};
      const worlds = Array.isArray(worldData.worlds) ? worldData.worlds : [];
      const valid = item => item && allowedWorld.test(item.id) &&
        (item.sourceType === 'catalog' || item.sourceType === 'discovery');
      const scored = (Array.isArray(data.scored) ? data.scored : []).filter(item =>
        valid(item) && item.sourceType === 'catalog' &&
        Number.isInteger(item.visualPotential) &&
        item.visualPotential >= 0 && item.visualPotential <= 100
      );
      const pending = (Array.isArray(data.candidates) ? data.candidates : []).filter(valid);
      const isAssessed = scored.length > 0;
      const scoredIds = new Set(scored.map(item => item.id));
      const records = [...scored, ...pending.filter(item => !scoredIds.has(item.id))].slice(0, 6);
      const count = Number(data.summary?.totalCandidates ?? pending.length);
      status.textContent = isAssessed ?
        'ビジュアル評価 ' + scored.length + '件 · 画像ベースの参考値' :
        count + ' WORLDS DISCOVERED / ' +
        (data.modelConfigured ? 'VISUAL EVALUATION IN PROGRESS' : 'VISUAL EVALUATION PAUSED');
      grid.replaceChildren();
      if (!records.length) {
        grid.appendChild(el('div', 'ai-scout-empty',
          'クラブWorldを探しています。画像の分析ができたWorldからビジュアル評価を紹介します。'));
        return;
      }
      const byId = new Map(worlds.map(w => [w.id, w]));
      const thumbnails = new Map();
      const drawRecords = () => {
        grid.replaceChildren();
        records.forEach((record, i) => {
          const world = byId.get(record.id);
          const thumbnail = thumbnails.get(record.id) || (world && (world.thumbnail || world.imageUrl)) || '';
          grid.appendChild(drawCard(record, i, scoredIds.has(record.id), thumbnail));
        });
      };
      drawRecords();
      const ids = records.filter(r => r.sourceType === 'catalog').map(r => r.id).slice(0, 12);
      if (ids.length) {
        try {
          const reply = await fetch(metaEndpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json', apikey: publicKey},
            body: JSON.stringify({ids})
          });
          if (reply.ok) {
            const payload = await reply.json();
            for (const item of payload.items || []) {
              if (ids.includes(item.world_id)) {
                thumbnails.set(item.world_id, item.thumbnail_url || item.image_url || '');
              }
            }
          }
        } catch (_) {}
      }
      if (thumbnails.size) drawRecords();
    } catch (_) {
      status.textContent = 'DISCOVERY DATA UNAVAILABLE';
      grid.replaceChildren(el('div', 'ai-scout-empty',
        'クラブ探索データを読み込めませんでした。しばらくしてからお試しください。'));
    }
  }

  load();
})();