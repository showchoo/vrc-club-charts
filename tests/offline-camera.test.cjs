'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const nav = require('../experiments/offline-camera/navigation.js');

test('offline route visits each simulated objective once without wall collisions', () => {
  const segments = nav.planInspection();
  assert.equal(segments.length, nav.FEATURES.length);
  assert.deepEqual(new Set(segments.map(s => s.targetId)),
    new Set(nav.FEATURES.map(f => f.id)));
  for (const s of segments) {
    assert.ok(s.route.length >= 1);
    for (const point of s.route) assert.equal(nav.isWalkable(point), true);
    for (let i = 1; i < s.route.length; i += 1) {
      const a = s.route[i-1], b = s.route[i];
      assert.equal(Math.abs(a.x-b.x)+Math.abs(a.y-b.y), 1);
    }
  }
});

test('route planner can detour around a simulated new obstruction', () => {
  const base = nav.shortestPath(nav.START, {x: 16, y: 2});
  assert.ok(base && base.length > 3);
  const blocked = new Set([base[1].x + ',' + base[1].y]);
  const rerouted = nav.shortestPath(nav.START, {x: 16, y: 2}, blocked);
  assert.ok(rerouted && rerouted.length >= base.length);
  assert.equal(rerouted.some(p => blocked.has(p.x + ',' + p.y)), false);
});

test('unreachable targets are rejected instead of being silently skipped', () => {
  const blocked = new Set(['15,2', '16,1', '17,2', '16,3']);
  assert.equal(nav.shortestPath(nav.START, {x:16,y:2}, blocked), null);
  assert.throws(() => nav.planInspection(nav.START, nav.FEATURES, blocked),
    /Unreachable feature/);
});

test('a blocked start or unsafe frame parameters fail closed', () => {
  assert.throws(() => nav.planInspection({x:0, y:0}), /Starting cell/);
  const plan = nav.planInspection();
  for (const n of [-1, 0, 101, 1.5]) {
    assert.throws(() => nav.makeTimeline(plan, n, 2), /Unsafe frame/);
  }
  assert.throws(() => nav.makeTimeline(plan, 2, 501), /Unsafe frame/);
});

test('camera timeline covers each objective and stays within synthetic map', () => {
  const plan = nav.planInspection();
  const frames = nav.makeTimeline(plan, 2, 9);
  assert.ok(frames.length > 20 && frames.length < 420);
  assert.deepEqual(frames.at(-1).visited,
    plan.map(segment => segment.targetId));
  for (const frame of frames) {
    assert.ok(frame.x >= 1 && frame.x <= nav.WIDTH - 2);
    assert.ok(frame.y >= 1 && frame.y <= nav.HEIGHT - 2);
    assert.ok(Number.isFinite(frame.yaw));
  }
  const summary = nav.summarize(plan, 12, frames.length);
  assert.equal(summary.actualVRChatVisit, false);
  assert.equal(summary.equipmentFunctionalityVerified, false);
  assert.equal(summary.worldCount, 0);
});

test('offline experiment never requests camera, mic, account or networking', () => {
  const root = path.resolve(__dirname, '../experiments/offline-camera');
  const js = fs.readFileSync(path.join(root,'camera.js'),'utf8');
  const html = fs.readFileSync(path.join(root,'index.html'),'utf8');
  assert.match(js, /canvas\.captureStream\(FPS\)/);
  assert.match(js, /new MediaRecorder\(stream/);
  assert.match(js, /recorder\.stop\(\)/);
  assert.match(js, /Escape/);
  assert.match(js, /actualVRChatVisit: false/);
  assert.match(html, /navigation\.js/);
  assert.match(html, /camera\.js/);
  for (const forbidden of [
    /navigator\.mediaDevices\.getUserMedia\s*\(/,
    /\bfetch\s*\(/, /\bWebSocket\s*\(/,
    /\bXMLHttpRequest\b/, /\bOSC\b.*(?:send|connect)\s*\(/,
    /vrchat\.com\/api/i,
  ]) {
    assert.doesNotMatch(js, forbidden);
  }
});
