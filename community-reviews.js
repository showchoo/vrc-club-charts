(() => {
  'use strict';

  const endpoint = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/community-reviews';
  const visualEndpoint = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-meta';
  const publicKey = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';
  const categories = ['visual', 'lighting', 'sound', 'spatial', 'interaction', 'originality', 'optimization'];
  const worldIdPattern = /^wrld_[0-9a-fA-F-]{36}$/;
  const feed = document.getElementById('communityReviewFeed');
  const preview = document.getElementById('communityReviewPreview');
  const form = document.getElementById('reviewSubmitForm');

  const node = (tag, className, value) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (value != null) el.textContent = String(value);
    return el;
  };

  function renderReview(item) {
    const card = node('article', 'community-review-item');
    const header = node('div', 'community-review-header');
    const name = node('strong', '', item.display_name || 'Visitor');
    const date = node('time', '', item.reviewed_at || '');
    header.append(name, date);
    card.append(header);

    const world = node('a', 'community-review-world', item.world_name || item.world_id || 'World');
    if (worldIdPattern.test(item.world_id)) world.href = 'worlds/' + item.world_id + '.html';
    else world.removeAttribute('href');
    card.append(world);

    const total = categories.reduce((sum, key) => sum + (Number(item[key]) || 0), 0);
    const score = node('p', 'community-review-score', '個人の参考評価 · ' + total + '/100');
    card.append(score);

    const comment = node('p', 'community-review-comment', item.comment || '');
    card.append(comment);
    if (item.conflict) card.append(node('span', 'community-review-conflict', '関係者による投稿'));
    return card;
  }

  async function loadFeed() {
    const target = feed || preview;
    if (!target) return;
    try {
      const response = await fetch(endpoint + '?limit=' + (feed ? '12' : '3'), { cache: 'no-store' });
      if (!response.ok) throw new Error('feed');
      const data = await response.json();
      const reviews = Array.isArray(data.reviews) ? data.reviews : [];
      target.replaceChildren();
      if (!reviews.length) {
        target.append(node('p', 'community-review-empty',
          '掲載中の体験レビューはまだありません。最初の現地レポートをお待ちしています。'));
        return;
      }
      for (const review of reviews) target.append(renderReview(review));
    } catch (_) {
      target.replaceChildren(node('p', 'community-review-empty', '体験レビューを読み込めませんでした。'));
    }
  }

  async function initForm() {
    if (!form) return;
    const select = document.getElementById('reviewWorldSelect');
    const status = document.getElementById('reviewSubmitStatus');
    const totalNode = document.getElementById('reviewTotal');
    const previewBox = document.getElementById('reviewWorldPreview');
    const media = document.getElementById('reviewWorldPreviewMedia');
    const previewName = document.getElementById('reviewWorldPreviewName');
    const previewAuthor = document.getElementById('reviewWorldPreviewAuthor');
    const timezoneOffset = new Date().getTimezoneOffset() * 60000;
    const today = new Date(Date.now() - timezoneOffset).toISOString().slice(0, 10);
    form.elements.reviewed_at.value = today;
    form.elements.reviewed_at.max = today;

    let visitorToken = '';
    try {
      visitorToken = localStorage.getItem('vccCommunityVisitor') || '';
      if (!/^[0-9a-f-]{36}$/i.test(visitorToken)) {
        visitorToken = crypto.randomUUID();
        localStorage.setItem('vccCommunityVisitor', visitorToken);
      }
      form.elements.display_name.value = localStorage.getItem('vccCommunityDisplayName') || '';
    } catch (_) {
      visitorToken = crypto.randomUUID();
    }

    let available = [];
    try {
      const response = await fetch('data/weekly-ranking.json', { cache: 'no-store' });
      if (!response.ok) throw new Error('worlds');
      const data = await response.json();
      available = (Array.isArray(data.worlds) ? data.worlds : [])
        .filter(w => w?.chartEligible === true && w?.availabilityStatus !== 'unavailable' && worldIdPattern.test(w.id))
        .sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ja'));
      for (const world of available) {
        const option = node('option', '', world.name || world.id);
        option.value = world.id;
        select.append(option);
      }
    } catch (_) {
      status.textContent = 'World一覧を読み込めませんでした。再読み込みしてください。';
      status.dataset.state = 'error';
    }

    async function showWorld() {
      const world = available.find(w => w.id === select.value);
      previewBox.hidden = !world;
      if (!world) return;
      previewName.textContent = world.name || world.id;
      previewAuthor.textContent = 'by ' + (world.author || '—');
      media.replaceChildren();
      const cached = world.thumbnail || world.imageUrl || '';
      if (cached && /^https:\/\/api\.vrchat\.cloud\//i.test(cached)) {
        const img = node('img');
        img.src = cached;
        img.alt = '';
        img.loading = 'lazy';
        media.append(img);
        return;
      }
      media.append(node('span', '', 'VRC'));
      try {
        const response = await fetch(visualEndpoint, {
          method: 'POST', headers: { apikey: publicKey, 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: [world.id] })
        });
        if (!response.ok) return;
        const data = await response.json();
        const visual = data?.items?.find(item => item.world_id === world.id);
        const image = visual?.thumbnail_url || visual?.image_url || '';
        if (image && select.value === world.id && /^https:\/\/api\.vrchat\.cloud\//i.test(image)) {
          const img = node('img');
          img.src = image;
          img.alt = '';
          img.loading = 'lazy';
          media.replaceChildren(img);
        }
      } catch (_) {}
    }

    select.addEventListener('change', showWorld);
    function updateTotal() {
      totalNode.textContent = String(categories.reduce((sum, key) =>
        sum + (Number(form.elements[key].value) || 0), 0));
    }
    categories.forEach(name => form.elements[name].addEventListener('input', updateTotal));

    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      const scores = {};
      for (const name of categories) scores[name] = Number(form.elements[name].value);
      const data = {
        displayName: form.elements.display_name.value.trim(),
        worldId: select.value,
        reviewedAt: form.elements.reviewed_at.value,
        conflict: form.elements.conflict.checked,
        scores,
        comment: form.elements.comment.value.trim(),
        visitorToken,
        website: form.elements.website.value
      };
      button.disabled = true;
      status.textContent = 'レビューを送信しています…';
      status.dataset.state = 'loading';
      try {
        const reply = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', apikey: publicKey },
          body: JSON.stringify(data)
        });
        const result = await reply.json().catch(() => ({}));
        if (!reply.ok) throw new Error(result.error || '送信できませんでした。');
        try { localStorage.setItem('vccCommunityDisplayName', data.displayName); } catch (_) {}
        form.reset();
        form.elements.reviewed_at.value = today;
        form.elements.display_name.value = data.displayName;
        previewBox.hidden = true;
        updateTotal();
        status.textContent = 'レビューを受け付けました。内容確認後に掲載されます。ご投稿ありがとうございます。';
        status.dataset.state = 'success';
      } catch (err) {
        status.textContent = err instanceof Error ? err.message : '送信できませんでした。';
        status.dataset.state = 'error';
      } finally { button.disabled = false; }
    });
  }

  loadFeed();
  initForm();
})();
