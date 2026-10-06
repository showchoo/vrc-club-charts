"use strict";

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');
const homepage = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const scout = fs.readFileSync(path.join(root, 'ai-scout.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

function isolatedHelper(source, declarations, functionName, endIndent = '') {
  const parts = declarations.map(re => {
    const match = source.match(re);
    assert.ok(match, 'Missing declaration ' + re);
    return match[0];
  });
  const body = source.match(new RegExp('function ' + functionName +
    '\\([^)]*\\) \\{[\\s\\S]*?\\n' + endIndent + '\\}'));
  assert.ok(body, 'Missing function ' + functionName);
  return vm.runInNewContext([...parts, body[0], functionName].join('\n'));
}

const HOME_PROXY = 'https://ypqpgpetrriirywrzikj.supabase.co/functions/v1/world-thumb';
const ID = 'wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92';

test('Featured and editor World cards get proxy images despite null snapshot thumbnail', () => {
  const worldImage = isolatedHelper(homepage,
    [/^const WORLD_THUMB_ENDPOINT = .*;$/m], 'worldImage');
  assert.equal(worldImage({id: ID, thumbnail: null}), HOME_PROXY + '?id=' + ID);
  assert.equal(worldImage({id: ID, thumbnail: '', imageUrl: ''}), HOME_PROXY + '?id=' + ID);
  assert.equal(worldImage({id: 'bad-id', thumbnail: 'https://example.com/image.jpg'}),
    'https://example.com/image.jpg');
  assert.match(homepage, /data-world-image-fallback="focus-world-placeholder"/);
  assert.match(homepage, /data-world-image-fallback="editor-pick-placeholder"/);
  assert.match(homepage, /document\.addEventListener\('error', handleWorldImageError, true\)/);
});

test('AI SCOUT uses a cached thumbnail proxy for catalog Worlds without second metadata POST', () => {
  const coverSource = isolatedHelper(scout, [
    /^  const thumbEndpoint = .*;$/m,
    /^  const allowedWorld = .*;$/m
  ], 'coverSource', '  ');
  assert.equal(coverSource({id:ID,sourceType:'catalog'}, ''), HOME_PROXY + '?id=' + ID);
  assert.equal(coverSource({id:ID,sourceType:'discovery'}, ''), '');
  assert.equal(coverSource({id:'bad',sourceType:'catalog'}, ''), '');
  assert.equal(coverSource({id:ID,sourceType:'discovery'}, 'https://api.vrchat.cloud/allowed'),
    'https://api.vrchat.cloud/allowed');
  assert.equal(coverSource({id:ID,sourceType:'discovery'}, 'https://evil.example/a'), '');
  assert.match(scout, /image\.addEventListener\('error'/);
  assert.doesNotMatch(scout, /fetch\(metaEndpoint/);
});

test('Homepage references freshly versioned JavaScript assets', () => {
  assert.match(html, /app\.js\?v=20261007-home-thumbs-01/);
  assert.match(html, /ai-scout\.js\?v=20261007-home-thumbs-01/);
});
