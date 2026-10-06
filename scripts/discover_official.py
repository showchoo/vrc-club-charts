#!/usr/bin/env python3
"""Best-effort public VRChat World search; never bypass API authentication."""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from scripts.discover_vrcw import (BLOCKED_NAME, CLUB_NAME, STATE, USER_AGENT, WORLD_ID, read_json)
except ModuleNotFoundError:
    from discover_vrcw import (BLOCKED_NAME, CLUB_NAME, STATE, USER_AGENT, WORLD_ID, read_json)

TERMS = ("club", "nightclub", "rave", "dj", "クラブ", "ディスコ")
API = "https://api.vrchat.cloud/api/1/worlds"


def query_worlds(term: str, offset: int) -> list[dict]:
    url = API + "?" + urllib.parse.urlencode({
        "search": term, "sort": "relevance", "n": 100,
        "offset": offset, "releaseStatus": "public",
    })
    req = urllib.request.Request(url, headers={
        "User-Agent": os.environ.get("VRC_USER_AGENT", "").strip() or USER_AGENT,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read(1_500_000))
    if not isinstance(payload, list):
        raise ValueError("VRChat World search was not an array")
    return payload


def collect_candidates(today: str) -> tuple[list[dict], bool]:
    state = read_json(STATE, {})
    state = state if isinstance(state, dict) else {}
    positions = state.get("officialNextOffset", {})
    positions = positions if isinstance(positions, dict) else {}
    new_positions = dict(positions)
    found = {}
    success = False
    for term in TERMS:
        # Take the highest-ranked page each time plus a rotating historic page.
        offset = max(100, int(positions.get(term, 100)))
        for index in (0, offset):
            try:
                results = query_worlds(term, index)
            except urllib.error.HTTPError as exc:
                print(f"WARN: official World search {term!r} HTTP {exc.code}")
                if exc.code in {401, 403, 429}:
                    # Respect API authorization / rate limits. Other sources
                    # and direct nominated World lookups are separate.
                    return list(found.values()), success
                break
            except (OSError, ValueError, urllib.error.URLError) as exc:
                print(f"WARN: official World search {term!r}: {type(exc).__name__}")
                break

            success = True
            print(f"Official World search {term!r} offset={index}: {len(results)} items")
            if index and len(results) < 100:
                new_positions[term] = 100
            elif index:
                new_positions[term] = offset + 100

            for item in results:
                if not isinstance(item, dict):
                    continue
                wid = str(item.get("id") or "")
                name = str(item.get("name") or "").strip()[:120]
                author = str(item.get("authorName") or "").strip()[:120]
                if not WORLD_ID.fullmatch(wid) or not name or not author:
                    continue
                if BLOCKED_NAME.search(name) or not CLUB_NAME.search(name):
                    continue
                if str(item.get("releaseStatus", "public")).lower() not in {"public"}:
                    continue
                categories = ["vrchat_search"]
                score = 91
                old = found.get(wid)
                if old:
                    old["sourceCategories"] = categories
                    continue
                found[wid] = {
                    "id": wid, "name": name, "authorHint": author,
                    "source": "https://vrchat.com/home/world/" + wid + "/info",
                    "sourceCategories": categories,
                    "confidenceScore": score,
                    "confidence": "high",
                    "reasons": ["source:official-world-search", "+explicit-club-name"],
                    "firstDiscoveredAt": today, "lastSeenAt": today,
                }
        # Do not monopolize public API requests; the workflow is daily.
    if success:
        # Preserve VRCW cursor and admission cooldown state.
        updated = read_json(STATE, {})
        updated = updated if isinstance(updated, dict) else {}
        updated["officialNextOffset"] = new_positions
        updated["updatedAt"] = today
        STATE.write_text(json.dumps(updated, ensure_ascii=False, indent=2)
                         + "\n", encoding="utf-8")
    return list(found.values()), success


if __name__ == "__main__":
    candidates, ok = collect_candidates(dt.datetime.now(dt.timezone.utc).date().isoformat())
    print(f"Official search candidates: {len(candidates)}, available={ok}")
