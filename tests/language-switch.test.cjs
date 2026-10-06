'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const { test } = require('node:test');

const root = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'i18n.js'), 'utf8');
const scripts = [];
const fakeDocument = {
  readyState: 'loading',
  addEventListener: (event, fn) => scripts.push({event, fn}),
};
const world = {};
vm.runInNewContext(src, {window: world, document: fakeDocument});
const translate = world.VCCLanguage.translate;

test('Shared language module initializes but does not require DOM before ready', () => {
  assert.equal(typeof translate, 'function');
  assert.equal(scripts[0]?.event, 'DOMContentLoaded');
});

test('English translations cover primary home, World search and field-note flows', () => {
  assert.equal(translate('ビジュアル評価ランキング', 'en'), 'Visual Impression Chart');
  assert.equal(translate('個性が光る、クラブを探す。', 'en'), 'Discover clubs with character.');
  assert.equal(translate('まだ知らない、次のフロアへ。', 'en'), 'Discover your next floor.');
  assert.equal(translate('World名・制作者・ジャンル', 'en'), 'World name, creator or genre');
  assert.equal(translate('訪問レビューを投稿する。', 'en'), 'Share your World experience.');
  assert.equal(translate('すでに掲載されています。Worlds一覧からご覧ください。', 'en'),
    'This World is already listed. Find it in the Worlds directory.');
  assert.equal(translate('プライバシーポリシー', 'en'), 'Privacy Policy');
});

test('Japanese translation is reversible and World labels retain exact case and whitespace', () => {
  assert.equal(translate('  ビジュアル評価ランキング  ', 'ja'),
    '  ビジュアル評価ランキング  ');
  assert.equal(translate('  ビジュアル評価ランキング  ', 'en'),
    '  Visual Impression Chart  ');
  assert.equal(translate('Cyberpunk City Rave', 'en'), 'Cyberpunk City Rave');
  assert.equal(translate('VRC CLUB CHARTS', 'en'), 'VRC CLUB CHARTS');
});

test('Dynamic World count and analytics coverage are translated', () => {
  assert.equal(translate(
    '102のWorldを収録。クラブ・DJ・レイヴなど、まだ知らないWorldを探せます。ビジュアルの参考スコアと、訪問した人の体験レビューを分けて紹介します.', 'en'),
    '102のWorldを収録。クラブ・DJ・レイヴなど、まだ知らないWorldを探せます。ビジュアルの参考スコアと、訪問した人の体験レビューを分けて紹介します.');
  assert.match(translate(
    '102のWorldを収録。クラブ・DJ・レイヴなど、まだ知らないWorldを探せます。ビジュアルの参考スコアと、訪問した人の体験レビューを分けて紹介します。', 'en'
  ), /Discover 102 Worlds/);
  assert.match(translate(
    '掲載 100件 / 確認待ち 2件 / 履歴保存 210件（最終集計 2026-10-07）', 'en'
  ), /Listed 100 \/ Pending 2 \/ Tracked 210/);
});

test('All public root pages and static generator load the language switch', () => {
  for (const filename of ['index.html','about.html','privacy.html',
                          'reviewer.html','events.html','djs.html']) {
    const html = fs.readFileSync(path.join(root,filename),'utf8');
    assert.match(html, /<script src="i18n\.js\?v=20261007-bilingual-01" defer><\/script>/,
      filename + ' missing locale script');
  }
  const builder = fs.readFileSync(path.join(root,'scripts/build_static_pages.py'),'utf8');
  assert.match(builder, /src="\{prefix\}i18n\.js\?v=20261007-bilingual-01"/);
  const build = fs.readFileSync(path.join(root,'scripts/build_vercel.py'),'utf8');
  assert.match(build, /"i18n\.js"/);
  const pages = fs.readFileSync(path.join(root,'.github/workflows/pages.yml'),'utf8');
  assert.match(pages, /cp .*i18n\.js/);
});

test('Language toggle retains persisted user choice and detects browser language', () => {
  assert.match(src, /localStorage\.getItem\(STORE\)/);
  assert.match(src, /localStorage\.setItem\(STORE, next\)/);
  assert.match(src, /navigator\.language\.toLowerCase\(\)\.startsWith\('ja'\)/);
  assert.match(src, /MutationObserver\(queueUpdate\)/);
  assert.match(src, /document\.documentElement\.lang = language/);
  assert.match(src, /data-vcc-no-translate/);
  assert.match(src, /'vcc:language-change'/);
});
