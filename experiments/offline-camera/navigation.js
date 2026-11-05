/* Offline, deterministic navigation baseline. No VRChat account, APIs or OSC. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root && typeof root === 'object') root.VCCOfflineNavigator = api;
})(typeof window === 'object' ? window : undefined, function () {
  'use strict';
  const WIDTH = 20;
  const HEIGHT = 12;
  const START = Object.freeze({ x: 2, y: 2 });
  const FEATURES = Object.freeze([
    Object.freeze({ id: 'dj-booth', label: 'DJ BOOTH', x: 16, y: 2, tint: '#5ef3ff' }),
    Object.freeze({ id: 'dance-floor', label: 'DANCE FLOOR', x: 10, y: 6, tint: '#ff79dd' }),
    Object.freeze({ id: 'lighting-rig', label: 'LIGHTING', x: 16, y: 9, tint: '#ffe38d' }),
    Object.freeze({ id: 'lounge', label: 'LOUNGE', x: 3, y: 9, tint: '#b9a5ff' }),
  ]);
  const WALLS = Object.freeze([
    [6, 2], [6, 3], [6, 4], [6, 6], [6, 7],
    [12, 2], [12, 4], [12, 5], [12, 6],
    [8, 8], [9, 8], [11, 8], [12, 8],
  ]);
  const DEFAULT_BLOCKS = new Set(WALLS.map(([x, y]) => x + ',' + y));
  const key = (p) => p.x + ',' + p.y;
  const same = (a, b) => a.x === b.x && a.y === b.y;
  const valid = (p) => p && Number.isInteger(p.x) && Number.isInteger(p.y) &&
    p.x >= 1 && p.x < WIDTH - 1 && p.y >= 1 && p.y < HEIGHT - 1;

  function isWalkable(p, extraBlocks = []) {
    const blocked = extraBlocks instanceof Set ? extraBlocks : new Set(extraBlocks);
    return Boolean(valid(p) && !DEFAULT_BLOCKS.has(key(p)) && !blocked.has(key(p)));
  }

  function shortestPath(from, to, extraBlocks = []) {
    if (!isWalkable(from, extraBlocks) || !isWalkable(to, extraBlocks)) return null;
    const queue = [{ x: from.x, y: from.y }];
    const before = new Map([[key(from), null]]);
    for (let head = 0; head < queue.length; head += 1) {
      const here = queue[head];
      if (same(here, to)) {
        const route = [];
        let p = here;
        while (p) {
          route.push({ x: p.x, y: p.y });
          p = before.get(key(p));
        }
        return route.reverse();
      }
      for (const delta of [[1, 0], [0, 1], [-1, 0], [0, -1]]) {
        const next = { x: here.x + delta[0], y: here.y + delta[1] };
        if (!isWalkable(next, extraBlocks) || before.has(key(next))) continue;
        before.set(key(next), here);
        queue.push(next);
      }
    }
    return null;
  }

  function planInspection(start = START, features = FEATURES, extraBlocks = []) {
    if (!isWalkable(start, extraBlocks)) throw new Error('Starting cell is obstructed');
    const unvisited = new Map(features.map(f => [f.id, f]));
    if (unvisited.size !== features.length) throw new Error('Duplicate feature id');
    const segments = [];
    let current = { x: start.x, y: start.y };
    while (unvisited.size) {
      let closest = null;
      for (const feature of unvisited.values()) {
        const route = shortestPath(current, feature, extraBlocks);
        if (!route) throw new Error('Unreachable feature: ' + feature.id);
        if (!closest || route.length < closest.route.length) {
          closest = { feature, route };
        }
      }
      segments.push({
        targetId: closest.feature.id,
        targetLabel: closest.feature.label,
        route: closest.route,
      });
      current = { x: closest.feature.x, y: closest.feature.y };
      unvisited.delete(closest.feature.id);
    }
    return segments;
  }

  function makeTimeline(segments, framesPerCell = 2, dwellFrames = 8) {
    if (!Number.isInteger(framesPerCell) || framesPerCell < 1 || framesPerCell > 100 ||
        !Number.isInteger(dwellFrames) || dwellFrames < 0 || dwellFrames > 500) {
      throw new Error('Unsafe frame parameters');
    }
    const timeline = [];
    let yaw = 0;
    const visited = [];
    let current = { ...START };
    for (const segment of segments) {
      if (!Array.isArray(segment.route) || !segment.route.length ||
          !same(segment.route[0], current)) throw new Error('Discontinuous inspection route');
      for (let i = 1; i < segment.route.length; i += 1) {
        const a = segment.route[i - 1];
        const b = segment.route[i];
        if (Math.abs(a.x - b.x) + Math.abs(a.y - b.y) !== 1 ||
            !isWalkable(b)) throw new Error('Unsafe navigation segment');
        yaw = Math.atan2(b.y - a.y, b.x - a.x);
        for (let f = 1; f <= framesPerCell; f += 1) {
          const t = f / framesPerCell;
          timeline.push({
            x: a.x + (b.x - a.x) * t,
            y: a.y + (b.y - a.y) * t,
            yaw, currentTarget: segment.targetId,
            visited: visited.slice(), state: 'travel',
          });
        }
      }
      current = { ...segment.route[segment.route.length - 1] };
      visited.push(segment.targetId);
      for (let f = 0; f < dwellFrames; f += 1) {
        timeline.push({
          x: current.x, y: current.y,
          yaw: yaw + (f - dwellFrames / 2) * 0.045,
          currentTarget: segment.targetId,
          visited: visited.slice(), state: 'observation',
        });
      }
    }
    return timeline;
  }

  function summarize(segments, fps, frameCount) {
    return {
      mode: 'offline-synthetic-only',
      actualVRChatVisit: false,
      equipmentFunctionalityVerified: false,
      worldCount: 0,
      targetSequence: segments.map(s => s.targetId),
      plannedGridSteps: segments.reduce((n, s) => n + s.route.length - 1, 0),
      videoDurationSeconds: frameCount / fps,
      notes: 'Deterministic grid search, synthetic scene. NOT an AI vision evaluation or VRChat evidence.',
    };
  }

  return Object.freeze({
    WIDTH, HEIGHT, START, FEATURES, WALLS, isWalkable,
    shortestPath, planInspection, makeTimeline, summarize,
  });
});
