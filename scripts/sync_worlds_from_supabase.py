#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "worlds.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"


def fetch_approved_worlds() -> list[dict]:
    url = (
        f"{SUPABASE_URL}/rest/v1/worlds_public"
        "?select=id,name,author,genres,chart_eligible,source,approved_at"
        "&chart_eligible=eq.true&order=approved_at.asc"
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
        data = json.loads(response.read().decode("utf-8"))
        return data if isinstance(data, list) else []


def main() -> None:
    existing = json.loads(OUT.read_text(encoding="utf-8"))
    if not isinstance(existing, list):
        raise SystemExit("data/worlds.json must be an array")

    merged = {
        str(item.get("id")): item
        for item in existing
        if isinstance(item, dict) and item.get("id")
    }

    remote = fetch_approved_worlds()
    for row in remote:
        wid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        author = str(row.get("author") or "").strip()
        if not wid or not name or not author:
            continue

        current = merged.get(wid, {})
        merged[wid] = {
            **current,
            "id": wid,
            "name": name,
            "author": author,
            "genres": row.get("genres") if isinstance(row.get("genres"), list) else ["CLUB"],
            "editorialStatus": current.get("editorialStatus", "unreviewed"),
            "chartEligible": True,
            "source": row.get("source") or current.get("source"),
            "discoveredBy": "auto-discovery",
            "approvedAt": row.get("approved_at"),
        }

    worlds = sorted(merged.values(), key=lambda w: str(w.get("name", "")).casefold())
    OUT.write_text(json.dumps(worlds, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced Worlds: {len(remote)} Supabase additions / {len(worlds)} total")


if __name__ == "__main__":
    main()
