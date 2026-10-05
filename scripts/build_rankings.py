#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRAFT_MAX = {'visual':20, 'lighting':20, 'sound':15, 'spatial':15, 'interaction':10, 'originality':10, 'optimization':10}


def craft_score(e: dict) -> float:
    # Category maxima encode the weights and sum to 100. Clamp malformed values.
    total = 0.0
    for key, maximum in CRAFT_MAX.items():
        value = float(e.get(key, 0) or 0)
        total += min(max(value, 0.0), float(maximum))
    return total


def normalize_log(values):
    vals = [max(0, float(v or 0)) for v in values]
    logs = [math.log1p(v) for v in vals]
    hi, lo = max(logs, default=0), min(logs, default=0)
    if hi <= lo:
        return [0.0 for _ in logs]
    return [(x-lo)/(hi-lo)*100 for x in logs]


def load_snapshots():
    items = []
    for p in sorted((ROOT/'data/snapshots').glob('*.json')):
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            date = dt.date.fromisoformat(data['capturedAt'])
            items.append((date, data))
        except Exception:
            pass
    return items


def main():
    seeds = json.loads((ROOT/'data/worlds.json').read_text(encoding='utf-8'))
    seed_by_id = {w['id']: w for w in seeds}
    snaps = load_snapshots()

    latest = snaps[-1] if snaps else None
    prior = None
    if latest:
        target = latest[0] - dt.timedelta(days=6)
        candidates = [s for s in snaps[:-1] if s[0] <= target]
        prior = candidates[-1] if candidates else (snaps[-2] if len(snaps) > 1 else None)

    latest_map = {w['id']:w for w in latest[1]['worlds']} if latest else {}
    prior_map = {w['id']:w for w in prior[1]['worlds']} if prior else {}

    rows = []
    for wid, seed in seed_by_id.items():
        now, old = latest_map.get(wid, {}), prior_map.get(wid, {})
        dv = None if not (now and old) else max(0, (now.get('visits') or 0) - (old.get('visits') or 0))
        df = None if not (now and old) else max(0, (now.get('favorites') or 0) - (old.get('favorites') or 0))
        rows.append({
            'id': wid,
            'name': now.get('name') or seed.get('name'),
            'author': now.get('author') or seed.get('author'),
            'genres': seed.get('genres', []),
            'weekly': {'visits': dv, 'favorites': df},
            '_craft': craft_score(seed.get('editorial', {})),
            '_visits': dv or 0,
            '_favs': df or 0,
        })

    nv = normalize_log([r['_visits'] for r in rows])
    nf = normalize_log([r['_favs'] for r in rows])
    has_trend = prior is not None
    for i, r in enumerate(rows):
        trend = (nv[i]*0.65 + nf[i]*0.35) if has_trend else 0.0
        overall = (trend*0.55 + r['_craft']*0.45) if has_trend else r['_craft']
        r['scores'] = {'trending': round(trend,1), 'craftsmanship': round(r['_craft'],1), 'overall': round(overall,1)}
        for k in ['_craft','_visits','_favs']: r.pop(k, None)

    rows.sort(key=lambda r: r['scores']['overall'], reverse=True)
    payload = {
        'status': 'live' if has_trend else 'seed',
        'updatedAt': latest[0].isoformat() if latest else 'MVP seed — weekly deltas begin after 2 snapshots',
        'methodVersion': '0.2',
        'worlds': rows,
    }
    (ROOT/'data/weekly-ranking.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Built ranking for {len(rows)} worlds; status={payload['status']}")

if __name__ == '__main__':
    main()
