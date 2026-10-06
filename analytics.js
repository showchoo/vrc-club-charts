(() => {
  const endpoint = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/analytics-track';
  const apiKey = 'sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK';

  if (navigator.doNotTrack === '1') return;

  const url = new URL(location.href);
  let path = url.pathname.replace(/^\/vrc-club-charts(?=\/|$)/, '') || '/';
  if (!path.startsWith('/')) path = '/' + path;

  let referrerHost = null;
  try {
    if (document.referrer) {
      const ref = new URL(document.referrer);
      if (ref.hostname !== location.hostname) referrerHost = ref.host;
    }
  } catch (_) {}

  const payload = {
    path,
    referrerHost,
    utmSource: url.searchParams.get('utm_source'),
    utmMedium: url.searchParams.get('utm_medium'),
    utmCampaign: url.searchParams.get('utm_campaign')
  };

  const send = () => fetch(endpoint, {
    method: 'POST',
    keepalive: true,
    headers: {
      'apikey': apiKey,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  }).catch(() => {});

  if ('requestIdleCallback' in window) {
    requestIdleCallback(send, {timeout: 1800});
  } else {
    setTimeout(send, 500);
  }
})();