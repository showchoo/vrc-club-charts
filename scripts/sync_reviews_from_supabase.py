#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reviews.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"


def fetch_published_reviews() -> list[dict]:
    url = (
        f"{SUPABASE_URL}/rest/v1/reviews_public"
        "?select=id,world_id,reviewer_id,conflict,reviewed_at,visual,lighting,sound,spatial,interaction,originality,optimization,comment,status,published_at"
        "&order=published_at.asc"
    )
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Accept": "application/json",
            "User-Agent": "VRC-Club-Charts-CI/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    existing = []
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []

    merged = {
        str(item.get("id")): item
        for item in existing
        if isinstance(item, dict) and item.get("id")
    }

    remote = fetch_published_reviews()
    for row in remote:
        review_id = str(row.get("id") or "").strip()
        world_id = str(row.get("world_id") or "").strip()
        reviewer_id = str(row.get("reviewer_id") or "").strip()
        if not review_id or not world_id or not reviewer_id:
            continue
        merged[review_id] = {
            "id": review_id,
            "worldId": world_id,
            "reviewerId": reviewer_id,
            "conflict": bool(row.get("conflict")),
            "status": "published",
            "reviewedAt": str(row.get("reviewed_at") or ""),
            "scores": {
                "visual": row.get("visual"),
                "lighting": row.get("lighting"),
                "sound": row.get("sound"),
                "spatial": row.get("spatial"),
                "interaction": row.get("interaction"),
                "originality": row.get("originality"),
                "optimization": row.get("optimization"),
            },
            "comment": str(row.get("comment") or ""),
            "source": "supabase",
        }

    reviews = sorted(
        merged.values(),
        key=lambda r: (str(r.get("reviewedAt", "")), str(r.get("id", ""))),
    )
    OUT.write_text(json.dumps(reviews, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced reviews: {len(remote)} Supabase / {len(reviews)} total")


if __name__ == "__main__":
    main()
