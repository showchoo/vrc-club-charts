#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, json, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRAFT_MAX = {'visual':20, 'lighting':20, 'sound':15, 'spatial':15, 'interaction':10, 'originality':10, 'optimization':10}


def craft_score(e: dict) -> float:
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
    public_path = ROOT/'data/weekly-ranking.json'
    try:
        previous_public = json.loads(public_path.read_text(encoding='utf-8')) if public_path.exists() else {}
    except Exception:
        previous_public = {}
    snaps = load_snapshots()

    latest = snaps[-1] if snaps else None
    prior = None
    if latest:
        target = latest[0] - dt.timedelta(days=6)
        candidates = [s for s in snaps[:-1] if s[0] <= target]
        prior = candidates[-1] if candidates else (snaps[-2] if len(snaps) > 1 else None)

    latest_map = {w['id']:w for w in latest[1]['worlds']} if latest else {}
    prior_map = {w['id']:w for w in prior[1]['worlds']} if prior else {}
    latest_skipped = {w.get('id'): w.get('status') for w in latest[1].get('skipped', [])} if latest else {}

    rows = []
    for wid, seed in seed_by_id.items():
        now, old = latest_map.get(wid, {}), prior_map.get(wid, {})
        dv = None if not (now and old) else max(0, (now.get('visits') or 0) - (old.get('visits') or 0))
        df = None if not (now and old) else max(0, (now.get('favorites') or 0) - (old.get('favorites') or 0))
        editorial_status = seed.get('editorialStatus') or ('provisional' if seed.get('editorial') else 'unreviewed')
        craft = craft_score(seed.get('editorial', {})) if editorial_status != 'unreviewed' else None
        rows.append({
            'id': wid,
            'name': now.get('name') or seed.get('name'),
            'author': now.get('author') or seed.get('author'),
            'genres': seed.get('genres', []),
            'editorialStatus': editorial_status,
            'releaseStatus': now.get('releaseStatus') or seed.get('releaseStatus'),
            'availabilityStatus': 'unavailable' if latest_skipped.get(wid) in {'http_404', 'http_403'} else 'available',
            'thumbnail': now.get('thumbnailImageUrl') or now.get('imageUrl') or seed.get('thumbnail'),
            'capacity': now.get('capacity'),
            'recommendedCapacity': now.get('recommendedCapacity'),
            'worldUpdatedAt': now.get('updatedAt'),
            'totals': {
                'visits': now.get('visits'),
                'favorites': now.get('favorites'),
            },
            'weekly': {'visits': dv, 'favorites': df},
            '_craft': craft,
            '_visits': dv or 0,
            '_favs': df or 0,
        })

    nv = normalize_log([r['_visits'] for r in rows])
    nf = normalize_log([r['_favs'] for r in rows])
    has_trend = prior is not None
    for i, r in enumerate(rows):
        trend = (nv[i]*0.65 + nf[i]*0.35) if has_trend else 0.0
        craft = r['_craft']
        overall = (trend*0.55 + craft*0.45) if (has_trend and craft is not None) else (craft if craft is not None else None)
        r['scores'] = {
            'trending': round(trend,1),
            'craftsmanship': round(craft,1) if craft is not None else None,
            'overall': round(overall,1) if overall is not None else None,
        }
        for k in ['_craft','_visits','_favs']: r.pop(k, None)

    def positions(items, score_key):
        eligible = [r for r in items if (r.get('scores') or {}).get(score_key) is not None]
        eligible.sort(key=lambda r: ((r.get('scores') or {}).get(score_key) or -1), reverse=True)
        return {r['id']: i + 1 for i, r in enumerate(eligible)}

    prev_rows = previous_public.get('worlds', []) if isinstance(previous_public, dict) else []
    prev_overall = positions(prev_rows, 'overall')
    prev_trending = positions(prev_rows, 'trending') if previous_public.get('status') == 'live' else {}
    prev_craft = positions(prev_rows, 'craftsmanship')

    cur_overall = positions(rows, 'overall')
    cur_trending = positions(rows, 'trending') if has_trend else {}
    cur_craft = positions(rows, 'craftsmanship')

    for r in rows:
        wid = r['id']
        movement = {}
        for key, current_map, previous_map in [
            ('overall', cur_overall, prev_overall),
            ('trending', cur_trending, prev_trending),
            ('craftsmanship', cur_craft, prev_craft),
        ]:
            if wid not in current_map:
                movement[key] = None
            elif wid not in previous_map:
                movement[key] = 'new'
            else:
                movement[key] = previous_map[wid] - current_map[wid]
        r['movement'] = movement

    rows.sort(key=lambda r: (r['scores']['overall'] is not None, r['scores']['overall'] or -1), reverse=True)
    payload = {
        'status': 'live' if has_trend else 'seed',
        'updatedAt': latest[0].isoformat() if latest else 'MVP seed — weekly deltas begin after 2 snapshots',
        'methodVersion': '0.3',
        'worlds': rows,
    }
    public_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Built ranking for {len(rows)} worlds; status={payload['status']}")

if __name__ == '__main__':
    main()
