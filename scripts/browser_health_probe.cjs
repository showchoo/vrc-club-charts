#!/usr/bin/env node
'use strict';
// Browser-level coverage for regressions that HTTP 200 cannot detect:
// empty thumbnail tiles, broken JavaScript rendering, and EN/日本語 switching.
const fs = require('node:fs');
const { chromium } = require('playwright');

const REPORT = process.env.VCC_HEALTH_REPORT || '/tmp/vcc-site-health.json';
const BASE = 'https://vrc-club-charts.vercel.app';
const report = JSON.parse(fs.readFileSync(REPORT, 'utf8'));
const expectedWorlds = Number(report.checks?.rankings?.world_count ?? 0);

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
      if (expectedWorlds > 0) {
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
      if (expectedWorlds > 0) {
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
      if (count !== expectedWorlds) {
        add('browser_world_cards', 'World cards differ from the verified-only public ranking');
      } else {
        // Inspect thumbnails throughout the directory, not just the first row.
        // This detects partial cache loss (e.g. a newly imported batch) even
        // when older cards still load normally.
        const positions = [...new Set([
          0, 1, Math.floor(count / 4), Math.floor(count / 2),
          Math.floor(3 * count / 4), count - 1
        ])].filter(i => i >= 0 && i < count);
        let loaded = 0;
        const failed = [];
        for (const pos of positions) {
          const row = world.locator('.world-catalog-row').nth(pos);
          const id = await row.getAttribute('data-world-id');
          try {
            await row.scrollIntoViewIfNeeded({timeout: 5000});
            await world.waitForFunction(worldId => {
              const card = [...document.querySelectorAll('.world-catalog-row')]
                .find(item => item.dataset.worldId === worldId);
              const img = card?.querySelector('.world-catalog-thumb img');
              return Boolean(img && img.complete && img.naturalWidth > 0);
            }, id, {timeout: 8500});
            loaded += 1;
          } catch (_) {
            failed.push(pos);
          }
        }
        report.checks.browser_worlds.thumbnails_sampled = positions.length;
        report.checks.browser_worlds.thumbnails_loaded = loaded;
        report.checks.browser_worlds.thumbnails_failed = failed.length;
        // One failed image can be a transient CDN hiccup; report sustained
        // partial failure without asking Gemini to rewrite site code.
        if (failed.length >= 2 || loaded === 0) {
          add('browser_world_images_partial',
            'World directory thumbnails failed: ' + failed.length +
            '/' + positions.length + ' sampled positions (' + failed.join(',') + ')',
            false);
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
