const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const { runInNewContext } = require('node:vm');

const script = readFileSync(join(__dirname, '..', 'analytics.js'), 'utf8');

function simulate({ excluded = null, doNotTrack = '0', store = new Map() } = {}) {
  let setting = excluded;
  let sent = 0;
  const messages = [];
  const callbacks = [];
  const context = {
    URL,
    navigator: { doNotTrack },
    location: { href: 'https://vrc-club-charts.vercel.app/worlds/' },
    document: { referrer: '' },
    localStorage: {
      getItem: key => key === 'vccAnalyticsExcludeMe' ? setting : (store.get(key) || null),
      setItem: (key, value) => store.set(key, String(value))
    },
    crypto: { randomUUID: () => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' },
    window: { requestIdleCallback: cb => { callbacks.push(cb); } },
    requestIdleCallback: cb => { callbacks.push(cb); },
    fetch: (_, init) => {
      sent++;
      messages.push(JSON.parse(init.body));
      return Promise.resolve({ ok: true });
    }
  };
  runInNewContext(script, context, { timeout: 1500 });
  return {
    pending: () => callbacks.length,
    flush: () => callbacks.forEach(cb => cb()),
    setExcluded: value => { setting = value; },
    sent: () => sent,
    messages: () => messages,
    storedKeys: () => [...store.keys()]
  };
}

test('opted-out owner pageview is not sent', () => {
  const session = simulate({ excluded: '1' });
  session.flush();
  assert.equal(session.sent(), 0);
  assert.equal(session.pending(), 0);
});

test('visitors who have not opted out are tracked', () => {
  const session = simulate();
  session.flush();
  assert.equal(session.sent(), 1);
});

test('administrator may switch tracking back on', () => {
  const session = simulate({ excluded: '0' });
  session.flush();
  assert.equal(session.sent(), 1);
});

test('enabling exclusion before idle callback prevents the pageview', () => {
  const session = simulate({ excluded: '0' });
  assert.equal(session.pending(), 1);
  session.setExcluded('1');
  session.flush();
  assert.equal(session.sent(), 0);
});

test('Do Not Track remains respected', () => {
  const session = simulate({ excluded: '0', doNotTrack: '1' });
  session.flush();
  assert.equal(session.sent(), 0);
});

test('one browser receives a stable random token across page views', () => {
  const store = new Map();
  const first = simulate({ store });
  first.flush();
  const second = simulate({ store });
  second.flush();
  assert.equal(first.messages()[0].visitorId, 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
  assert.equal(second.messages()[0].visitorId, first.messages()[0].visitorId);
  assert.equal(store.size, 1);
});

test('owner opt-out creates no persistent analytics identifier', () => {
  const session = simulate({ excluded: '1' });
  session.flush();
  assert.equal(session.sent(), 0);
  assert.equal(session.storedKeys().length, 0);
});

test('Do Not Track creates no analytics identifier', () => {
  const session = simulate({ doNotTrack: '1' });
  session.flush();
  assert.equal(session.storedKeys().length, 0);
});
