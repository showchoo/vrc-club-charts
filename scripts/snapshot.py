#!/usr/bin/env python3
"""Capture a conservative weekly snapshot for a curated list of public VRChat worlds.

No VRChat login is used or stored. The collector calls GET /worlds/{worldId}, which the
community API docs describe as usable without authentication. Set VRC_USER_AGENT to a
properly identifying value before automation is enabled.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, random, re, sys, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.vrchat.cloud/api/1/worlds/{}"
WORLD_ID_RE = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")


def request_world(world_id: str, user_agent: str) -> dict:
    req = Request(API.format(world_id), headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-jitter", action="store_true", help="skip randomized start delay")
    p.add_argument("--interval", type=int, default=65, help="seconds between world requests")
    args = p.parse_args()

    ua = os.getenv("VRC_USER_AGENT", "").strip()
    if not ua:
        print("ERROR: set VRC_USER_AGENT, e.g. 'VRCClubCharts/0.1 https://your-site.example/contact'", file=sys.stderr)
        return 2

    worlds = json.loads((ROOT / "data/worlds.json").read_text(encoding="utf-8"))
    if not isinstance(worlds, list) or not worlds:
        print("ERROR: data/worlds.json must be a non-empty array", file=sys.stderr)
        return 2
    for seed in worlds:
        wid = str(seed.get("id", ""))
        if not WORLD_ID_RE.fullmatch(wid):
            print(f"ERROR: invalid VRChat world id: {wid!r}", file=sys.stderr)
            return 2
    if not args.no_jitter:
        delay = random.randint(0, 900)
        print(f"Randomized start delay: {delay}s")
        time.sleep(delay)

    captured = []
    for i, seed in enumerate(worlds):
        if i:
            time.sleep(max(args.interval, 1))
        try:
            w = request_world(seed["id"], ua)
            captured.append({
                "id": seed["id"],
                "name": w.get("name") or seed.get("name"),
                "author": w.get("authorName") or seed.get("author"),
                "visits": w.get("visits"),
                "favorites": w.get("favorites"),
                "capacity": w.get("capacity"),
                "recommendedCapacity": w.get("recommendedCapacity"),
                "releaseStatus": w.get("releaseStatus"),
                "thumbnailImageUrl": w.get("thumbnailImageUrl"),
                "imageUrl": w.get("imageUrl"),
                "updatedAt": w.get("updated_at") or w.get("updatedAt"),
            })
            print(f"OK {seed['id']} {captured[-1]['name']}")
        except HTTPError as e:
            print(f"HTTP {e.code} for {seed['id']}", file=sys.stderr)
            if e.code == 429:
                print("Rate limited; stopping instead of retrying aggressively.", file=sys.stderr)
                return 3
        except (URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"ERROR {seed['id']}: {e}", file=sys.stderr)

    day = dt.datetime.now(dt.timezone.utc).date().isoformat()
    out = ROOT / "data/snapshots" / f"{day}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"capturedAt": day, "worlds": captured}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
