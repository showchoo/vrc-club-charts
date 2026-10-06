(() => {
  'use strict';
  const form = document.getElementById('worldSuggestionForm');
  const input = document.getElementById('worldSuggestionUrl');
  const status = document.getElementById('worldSuggestionStatus');
  const submit = document.getElementById('worldSuggestionButton');
  if (!form || !input || !status || !submit) return;
  const ENDPOINT = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-submit';
  const KEY = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';
  const ID = /^wrld_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  function extractId(value) {
    try {
      const url = new URL(String(value || '').trim());
      const match = /^\/home\/world\/(wrld_[0-9a-f-]{36})(?:\/info)?\/?$/i.exec(url.pathname);
      if (url.protocol !== 'https:' || url.hostname !== 'vrchat.com' ||
          url.username || url.password || url.search || url.hash ||
          !match || !ID.test(match[1])) return null;
      return match[1].toLowerCase();
    } catch (_) { return null; }
  }
  function message(text, kind) {
    status.textContent = text;
    status.className = 'world-suggestion-status ' + (kind || '');
    status.hidden = false;
  }
  function token() {
    try {
      let value = localStorage.getItem('vcc-suggestion-visitor');
      if (!value) {
        value = crypto.randomUUID();
        localStorage.setItem('vcc-suggestion-visitor', value);
      }
      return value;
    } catch (_) { return crypto.randomUUID(); }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const id = extractId(input.value);
    if (!id) {
      message('vrchat.com/home/world/… のWorld URLを入力してください。', 'error');
      input.focus();
      return;
    }
    submit.disabled = true;
    submit.textContent = '公式情報を確認中…';
    message('VRChatの公開状態と登録状況を確認しています。', 'pending');
    try {
      const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers: {'Content-Type':'application/json', 'apikey':KEY},
        body:JSON.stringify({
          url:input.value.trim(),
          visitorToken:token(),
          website:form.elements.namedItem('website')?.value || ''
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(String(data?.error || '受付に失敗しました。'));
      if (data.status === 'already_listed') {
        message('すでに掲載されています。Worlds一覧からご覧ください。', 'success');
      } else if (data.status === 'approved') {
        message('登録済みのWorldです。掲載ページへの反映をご確認ください。', 'success');
      } else if (data.status === 'needs_review') {
        message('投稿済みです。クラブ判定の証拠が不足しているため確認待ちです。', 'pending');
      } else if (data.alreadySubmitted) {
        message('このWorldはすでに投稿されています。判定・掲載結果をお待ちください。', 'pending');
      } else {
        message('投稿を受け付けました。公開情報をAIが判定し、条件を満たせば自動掲載されます。', 'success');
        form.reset();
      }
    } catch (error) {
      message(error instanceof Error ? error.message : '送信できませんでした。', 'error');
    } finally {
      submit.disabled = false;
      submit.textContent = 'Worldを投稿する →';
    }
  });
})();
