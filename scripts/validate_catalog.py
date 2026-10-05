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
    events_auto = json.loads((ROOT / "data/events-auto.json").read_text(encoding="utf-8"))
    djs = json.loads((ROOT / "data/djs.json").read_text(encoding="utf-8"))
    reviewers = json.loads((ROOT / "data/reviewers.json").read_text(encoding="utf-8"))
    reviews = json.loads((ROOT / "data/reviews.json").read_text(encoding="utf-8"))
    review_scores = json.loads((ROOT / "data/review-scores.json").read_text(encoding="utf-8"))

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

    if not isinstance(events_auto, list):
        fail("data/events-auto.json must be an array")
        errors += 1
    else:
        manual_ids = {str(e.get("id", "")).strip() for e in events if isinstance(e, dict)}
        seen_auto_ids = set()
        for i, event in enumerate(events_auto, start=1):
            if not isinstance(event, dict):
                fail(f"auto event #{i}: must be an object")
                errors += 1
                continue
            eid = str(event.get("id", "")).strip()
            if not eid or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,95}", eid):
                fail(f"auto event #{i}: valid lowercase id is required")
                errors += 1
            elif eid in seen_auto_ids:
                fail(f"duplicate auto event id: {eid}")
                errors += 1
            else:
                seen_auto_ids.add(eid)
            if eid in manual_ids:
                fail(f"auto event collides with curated event id: {eid}")
                errors += 1
            name = str(event.get("name", "")).strip()
            start = str(event.get("start", "")).strip()
            organizer = str(event.get("organizer", "")).strip()
            url = str(event.get("url", "")).strip()
            source = str(event.get("source", "")).strip()
            if not name or not start or not organizer or not url or not source:
                fail(f"auto event #{i}: name, start, organizer, url and source are required")
                errors += 1
            try:
                dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
            except ValueError:
                fail(f"auto event #{i}: start must be ISO 8601 with timezone")
                errors += 1
            if event.get("autoImported") is not True:
                fail(f"auto event #{i}: autoImported must be true")
                errors += 1

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

    reviewer_ids = set()
    if not isinstance(reviewers, list):
        fail("data/reviewers.json must be an array")
        errors += 1
    else:
        for i, reviewer in enumerate(reviewers, start=1):
            rid = str(reviewer.get("id", "")).strip()
            name = str(reviewer.get("name", "")).strip()
            if not rid or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", rid):
                fail(f"reviewer #{i}: valid lowercase id is required")
                errors += 1
            elif rid in reviewer_ids:
                fail(f"duplicate reviewer id: {rid}")
                errors += 1
            else:
                reviewer_ids.add(rid)
            if not name:
                fail(f"reviewer #{i}: name is required")
                errors += 1
            if reviewer.get("status", "active") not in {"active", "inactive"}:
                fail(f"reviewer #{i}: status must be active or inactive")
                errors += 1

    review_ids = set()
    if not isinstance(reviews, list):
        fail("data/reviews.json must be an array")
        errors += 1
    else:
        for i, review in enumerate(reviews, start=1):
            review_id = str(review.get("id", "")).strip()
            world_id = str(review.get("worldId", "")).strip()
            reviewer_id = str(review.get("reviewerId", "")).strip()
            if not review_id or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,95}", review_id):
                fail(f"review #{i}: valid lowercase id is required")
                errors += 1
            elif review_id in review_ids:
                fail(f"duplicate review id: {review_id}")
                errors += 1
            else:
                review_ids.add(review_id)
            if world_id not in seen:
                fail(f"review #{i}: unknown worldId {world_id!r}")
                errors += 1
            if reviewer_id not in reviewer_ids:
                fail(f"review #{i}: unknown reviewerId {reviewer_id!r}")
                errors += 1
            if not isinstance(review.get("conflict", False), bool):
                fail(f"review #{i}: conflict must be boolean")
                errors += 1
            if review.get("status", "published") not in {"draft", "published", "withdrawn"}:
                fail(f"review #{i}: unsupported status")
                errors += 1
            reviewed_at = str(review.get("reviewedAt", "")).strip()
            try:
                dt.datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            except ValueError:
                fail(f"review #{i}: reviewedAt must be ISO 8601")
                errors += 1
            scores = review.get("scores")
            if not isinstance(scores, dict):
                fail(f"review #{i}: scores object is required")
                errors += 1
            else:
                for key, maximum in CRAFT_MAX.items():
                    value = scores.get(key)
                    if not isinstance(value, (int, float)) or not 0 <= value <= maximum:
                        fail(f"review #{i}: scores.{key} must be 0..{maximum}")
                        errors += 1

    score_rows = review_scores.get("worlds", []) if isinstance(review_scores, dict) else None
    if not isinstance(score_rows, list):
        fail("data/review-scores.json must contain a worlds array")
        errors += 1
    else:
        score_world_ids = set()
        for i, row in enumerate(score_rows, start=1):
            wid = str(row.get("worldId", "")).strip()
            if wid not in seen:
                fail(f"review score #{i}: unknown worldId {wid!r}")
                errors += 1
            if wid in score_world_ids:
                fail(f"duplicate review score worldId: {wid}")
                errors += 1
            score_world_ids.add(wid)
            status = row.get("status")
            if status not in {"collecting", "provisional", "ranked"}:
                fail(f"review score #{i}: invalid status {status!r}")
                errors += 1
            count = row.get("reviewCount")
            if not isinstance(count, int) or count < 0:
                fail(f"review score #{i}: reviewCount must be a non-negative integer")
                errors += 1
            score = row.get("score")
            if status == "collecting" and score is not None:
                fail(f"review score #{i}: collecting status must not publish a score")
                errors += 1
            if status in {"provisional", "ranked"} and not isinstance(score, (int, float)):
                fail(f"review score #{i}: scored status requires numeric score")
                errors += 1
            if status == "collecting" and isinstance(count, int) and count >= 3:
                fail(f"review score #{i}: collecting status requires fewer than 3 reviews")
                errors += 1
            if status == "provisional" and isinstance(count, int) and not 3 <= count <= 4:
                fail(f"review score #{i}: provisional status requires 3 or 4 reviews")
                errors += 1
            if status == "ranked" and isinstance(count, int) and count < 5:
                fail(f"review score #{i}: ranked status requires at least 5 reviews")
                errors += 1

    if errors:
        print(f"Validation failed with {errors} error(s).", file=sys.stderr)
        return 1

    print(f"Catalog OK: {len(worlds)} worlds, {len(ranked_ids)} ranking rows, {len(events)} curated events, {len(events_auto)} auto events, {len(djs)} DJs, {len(reviewers)} reviewers, {len(reviews)} reviews")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
