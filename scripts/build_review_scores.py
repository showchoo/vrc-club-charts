#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRAFT_MAX = {
    "visual": 20,
    "lighting": 20,
    "sound": 15,
    "spatial": 15,
    "interaction": 10,
    "originality": 10,
    "optimization": 10,
}


def mean(values):
    return sum(values) / len(values) if values else None


def stddev(values):
    if len(values) < 2:
        return None
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def iso_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main():
    worlds = json.loads((ROOT / "data/worlds.json").read_text(encoding="utf-8"))
    reviewers = json.loads((ROOT / "data/reviewers.json").read_text(encoding="utf-8"))
    reviews = json.loads((ROOT / "data/reviews.json").read_text(encoding="utf-8"))

    world_ids = {w["id"] for w in worlds}
    active_reviewers = {
        str(r.get("id")): r for r in reviewers
        if r.get("id") and r.get("status", "active") == "active"
    }

    grouped = defaultdict(list)
    for review in reviews:
        if review.get("status", "published") != "published":
            continue
        if review.get("conflict") is True:
            continue
        world_id = str(review.get("worldId") or "")
        reviewer_id = str(review.get("reviewerId") or "")
        if world_id not in world_ids or reviewer_id not in active_reviewers:
            continue

        scores = review.get("scores") or {}
        normalized = {}
        valid = True
        for key, maximum in CRAFT_MAX.items():
            value = scores.get(key)
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= maximum:
                valid = False
                break
            normalized[key] = float(value)
        if not valid:
            continue

        grouped[world_id].append({
            "reviewerId": reviewer_id,
            "reviewedAt": review.get("reviewedAt"),
            "scores": normalized,
            "total": sum(normalized.values()),
        })

    rows = []
    for world_id, items in grouped.items():
        # One published review per reviewer per world; newest entry wins.
        by_reviewer = {}
        for item in items:
            rid = item["reviewerId"]
            current = by_reviewer.get(rid)
            if current is None or str(item.get("reviewedAt") or "") >= str(current.get("reviewedAt") or ""):
                by_reviewer[rid] = item
        items = list(by_reviewer.values())

        n = len(items)
        category = {
            key: round(mean([r["scores"][key] for r in items]), 2)
            for key in CRAFT_MAX
        }
        totals = [r["total"] for r in items]
        raw_score = round(sum(category.values()), 2)
        spread = stddev(totals)

        if n >= 5:
            status = "ranked"
            public_score = raw_score
        elif n >= 3:
            status = "provisional"
            public_score = raw_score
        else:
            status = "collecting"
            public_score = None

        if n >= 5 and spread is not None and spread <= 6:
            confidence = "high"
        elif n >= 3:
            confidence = "medium"
        else:
            confidence = "low"

        dates = [str(r.get("reviewedAt") or "") for r in items if r.get("reviewedAt")]
        rows.append({
            "worldId": world_id,
            "status": status,
            "score": public_score,
            "reviewCount": n,
            "confidence": confidence,
            "scoreSpread": round(spread, 2) if spread is not None else None,
            "criteria": category if n >= 3 else None,
            "lastReviewedAt": max(dates) if dates else None,
        })

    rows.sort(key=lambda r: (
        r["score"] is not None,
        r["score"] if r["score"] is not None else -1,
        r["reviewCount"],
    ), reverse=True)

    payload = {
        "updatedAt": iso_now(),
        "methodVersion": "1.0",
        "summary": {
            "reviewers": len(active_reviewers),
            "reviews": sum(r["reviewCount"] for r in rows),
            "scoredWorlds": sum(r["score"] is not None for r in rows),
            "rankedWorlds": sum(r["status"] == "ranked" for r in rows),
        },
        "worlds": rows,
    }
    (ROOT / "data/review-scores.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Built panel scores: {payload['summary']['reviews']} reviews, "
        f"{payload['summary']['scoredWorlds']} scored worlds, "
        f"{payload['summary']['rankedWorlds']} ranked worlds"
    )


if __name__ == "__main__":
    main()
