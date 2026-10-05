#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_ID_RE = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")
CRAFT_MAX = {
    "visual": 20,
    "lighting": 20,
    "sound": 15,
    "spatial": 15,
    "interaction": 10,
    "originality": 10,
    "optimization": 10,
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def main() -> int:
    errors = 0
    worlds = json.loads((ROOT / "data/worlds.json").read_text(encoding="utf-8"))
    ranking = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
    events = json.loads((ROOT / "data/events.json").read_text(encoding="utf-8"))
    djs = json.loads((ROOT / "data/djs.json").read_text(encoding="utf-8"))

    if not isinstance(worlds, list) or not worlds:
        fail("data/worlds.json must be a non-empty array")
        return 1

    seen = set()
    for i, w in enumerate(worlds, start=1):
        wid = str(w.get("id", ""))
        if not WORLD_ID_RE.fullmatch(wid):
            fail(f"world #{i} has invalid id: {wid!r}")
            errors += 1
        if wid in seen:
            fail(f"duplicate world id: {wid}")
            errors += 1
        seen.add(wid)

        if not str(w.get("name", "")).strip():
            fail(f"{wid}: missing name")
            errors += 1
        if not str(w.get("author", "")).strip():
            fail(f"{wid}: missing author")
            errors += 1

        status = w.get("editorialStatus") or ("provisional" if w.get("editorial") else "unreviewed")
        if status not in {"provisional", "reviewed", "unreviewed"}:
            fail(f"{wid}: unsupported editorialStatus {status!r}")
            errors += 1

        editorial = w.get("editorial")
        if status != "unreviewed":
            if not isinstance(editorial, dict):
                fail(f"{wid}: reviewed/provisional world needs editorial scores")
                errors += 1
            else:
                for key, maximum in CRAFT_MAX.items():
                    value = editorial.get(key)
                    if not isinstance(value, (int, float)) or not 0 <= value <= maximum:
                        fail(f"{wid}: editorial.{key} must be 0..{maximum}")
                        errors += 1

        genres = w.get("genres")
        if not isinstance(genres, list) or not all(isinstance(g, str) and g.strip() for g in genres):
            fail(f"{wid}: genres must be a non-empty-string array")
            errors += 1
        if not isinstance(w.get("chartEligible"), bool):
            fail(f"{wid}: chartEligible must be boolean")
            errors += 1

    ranked_ids = [w.get("id") for w in ranking.get("worlds", [])]
    unknown = sorted(set(ranked_ids) - seen)
    if unknown:
        fail(f"weekly-ranking contains unknown ids: {unknown}")
        errors += 1

    missing = sorted(seen - set(ranked_ids))
    if missing:
        fail(f"weekly-ranking is missing {len(missing)} registry ids")
        errors += 1

    if len(ranked_ids) != len(set(ranked_ids)):
        fail("weekly-ranking contains duplicate ids")
        errors += 1

    if not isinstance(events, list):
        fail("data/events.json must be an array")
        errors += 1
    else:
        seen_events = set()
        seen_event_ids = set()
        for i, event in enumerate(events, start=1):
            event_id = str(event.get("id", "")).strip()
            if not event_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,95}", event_id):
                fail(f"event #{i}: valid lowercase id is required")
                errors += 1
            elif event_id in seen_event_ids:
                fail(f"duplicate event id: {event_id}")
                errors += 1
            else:
                seen_event_ids.add(event_id)
            name = str(event.get("name", "")).strip()
            start = str(event.get("start", "")).strip()
            wid = str(event.get("worldId", "")).strip()
            world_name = str(event.get("worldName", "")).strip()
            organizer = str(event.get("organizer", "")).strip()
            if not name or not start or not organizer:
                fail(f"event #{i}: name, start and organizer are required")
                errors += 1
                continue
            if not wid and not world_name:
                fail(f"event #{i}: either worldId or worldName is required")
                errors += 1
            if wid and not WORLD_ID_RE.fullmatch(wid):
                fail(f"event #{i}: invalid worldId {wid!r}")
                errors += 1
            try:
                dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError:
                fail(f"event #{i}: start must be ISO 8601 with timezone")
                errors += 1
            key = (name.casefold(), start, wid)
            if key in seen_events:
                fail(f"duplicate event: {name} at {start}")
                errors += 1
            seen_events.add(key)

    if not isinstance(djs, list):
        fail("data/djs.json must be an array")
        errors += 1
    else:
        seen_djs = set()
        seen_dj_ids = set()
        for i, dj in enumerate(djs, start=1):
            dj_id = str(dj.get("id", "")).strip()
            name = str(dj.get("name", "")).strip()
            if not dj_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", dj_id):
                fail(f"dj #{i}: valid lowercase id is required")
                errors += 1
            elif dj_id in seen_dj_ids:
                fail(f"duplicate DJ id: {dj_id}")
                errors += 1
            else:
                seen_dj_ids.add(dj_id)
            if not name:
                fail(f"dj #{i}: name is required")
                errors += 1
                continue
            key = name.casefold()
            if key in seen_djs:
                fail(f"duplicate DJ name: {name}")
                errors += 1
            seen_djs.add(key)
            genres = dj.get("genres", [])
            if not isinstance(genres, list) or not all(isinstance(g, str) and g.strip() for g in genres):
                fail(f"dj #{i}: genres must be a string array")
                errors += 1

    if isinstance(events, list) and isinstance(djs, list):
        valid_dj_ids = {str(d.get("id", "")).strip() for d in djs if d.get("id")}
        for i, event in enumerate(events, start=1):
            for dj_id in event.get("djIds", []) or []:
                if dj_id not in valid_dj_ids:
                    fail(f"event #{i}: unknown djId {dj_id!r}")
                    errors += 1

    if errors:
        print(f"Validation failed with {errors} error(s).", file=sys.stderr)
        return 1

    print(f"Catalog OK: {len(worlds)} worlds, {len(ranked_ids)} ranking rows, {len(events)} events, {len(djs)} DJs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
