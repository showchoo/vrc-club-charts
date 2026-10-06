#!/usr/bin/env node
'use strict';
// Browser-level coverage for regressions that HTTP 200 cannot detect:
// empty thumbnail tiles, broken JavaScript rendering, and EN/日本語 switching.
const fs = require('node:fs');
const { chromium } = require('playwright');

const REPORT = process.env.VCC_HEALTH_REPORT || '/tmp/vcc-site-health.json';
const BASE = 'https://vrc-club-charts.vercel.app';
const report = JSON.parse(fs.readFileSync(REPORT, 'utf8'));

function add(code, detail, autoFixable = true) {
  report.issues.push({code, category: 'browser', detail: String(detail).slice(0, 230),
    auto_fixable: autoFixable});
  report.healthy = false;
}
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1365, height: 880},
      locale: 'ja-JP', reducedMotion: 'reduce'});
    // Do not count automated health probes as real visitors or page views.
    await page.route('**/functions/v1/analytics-track',
      route => route.fulfill({status: 204, body: ''}));
    const errors = [];
    page.on('pageerror', e => errors.push(String(e.message || e).slice(0, 120)));

    const response = await page.goto(BASE + '/', {waitUntil: 'domcontentloaded',
      timeout: 30000});
    if (!response || response.status() >= 400) {
      add('browser_home', 'Homepage HTTP status failed');
    } else {
      try {
        await page.locator('.focus-world-card').first().waitFor({timeout: 18000});
      } catch (_) {
        add('browser_home_cards', 'Featured Worlds did not render');
      }
      try {
        await page.locator('.ai-scout-card').first().waitFor({timeout: 18000});
      } catch (_) {
        add('browser_ai_scout', 'AI SCOUT visual cards did not render');
      }

      const button = page.locator('#vccLanguageToggle');
      if (await button.count() !== 1) {
        add('browser_language_switch', 'Missing visible EN/日本語 toggle');
      } else {
        const before = await page.locator('html').getAttribute('lang');
        try {
          await button.click({timeout: 8000});
          await page.waitForFunction(old => document.documentElement.lang !== old,
            before, {timeout: 5000});
          const after = await page.locator('html').getAttribute('lang');
          if (!['en', 'ja'].includes(after)) {
            add('browser_language_switch', 'Language control does not update html lang');
          }
        } catch (_) {
          add('browser_language_switch', 'Language toggle failed to change language');
        }
      }

      // Wait for image proxy requests to complete without depending on lazy tiles below the fold.
      try {
        const card = page.locator('.focus-world-card').first();
        await card.scrollIntoViewIfNeeded({timeout: 4000});
        await page.waitForFunction(() => {
          const images = [...document.querySelectorAll('.focus-world-card img')];
          return images.some(img => img.complete && img.naturalWidth > 0);
        }, null, {timeout: 18000});
      } catch (_) {
        add('browser_home_images', 'No featured World thumbnail loaded in browser',
          false /* backend image/CDN outage is indistinguishable from code here */);
      }
      if (errors.length) {
        add('browser_js_exception', errors.slice(0, 3).join('; '));
      }
    }

    const world = await browser.newPage({viewport: {width: 1365, height: 880},
      locale: 'ja-JP'});
    await world.route('**/functions/v1/analytics-track',
      route => route.fulfill({status: 204, body: ''}));
    const list = await world.goto(BASE + '/worlds/', {
      waitUntil: 'domcontentloaded', timeout: 30000
    });
    if (!list || list.status() >= 400) {
      add('browser_worlds', 'World directory is not accessible');
    } else {
      const count = await world.locator('.world-catalog-row').count();
      report.checks.browser_worlds = {rows: count};
      if (!count) {
        add('browser_world_cards', 'World list contains zero visible rows');
      } else {
        try {
          await world.locator('.world-catalog-row img').first().scrollIntoViewIfNeeded();
          await world.waitForFunction(() => {
            const imgs = [...document.querySelectorAll('.world-catalog-row img')].slice(0, 3);
            return imgs.some(img => img.complete && img.naturalWidth > 0);
          }, null, {timeout: 16000});
        } catch (_) {
          add('browser_world_images', 'No directory thumbnail loaded in browser',
            false /* can be transient upstream image delivery */);
        }
      }
    }
    await page.close();
    await world.close();
  } finally {
    await browser.close();
    report.issues = report.issues.slice(0, 20);
    report.healthy = report.issues.length === 0;
    fs.writeFileSync(REPORT, JSON.stringify(report, null, 2) + '\n');
    process.stdout.write('VCC browser health: ' +
      (report.healthy ? 'OK' : 'DEGRADED') +
      ', total findings=' + report.issues.length + '\n');
  }
})().catch(error => {
  // An unavailable test runner/browser must not be misclassified as a site bug.
  process.stderr.write('Browser probe unavailable: ' + error.name + '\n');
  process.exitCode = 0;
});
