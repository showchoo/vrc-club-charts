#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reviewers.json"

SUPABASE_URL = "https://ypqpgpetrriirywrzikj.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_sP01_V4fqjJYHM80xxkDqg_P8h9ccYK"


def fetch_supabase_reviewers() -> list[dict]:
    url = (
        f"{SUPABASE_URL}/rest/v1/reviewers_public"
        "?select=id,name,status,tags,approved_at&order=approved_at.asc"
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

    remote = fetch_supabase_reviewers()
    for row in remote:
        rid = str(row.get("id") or "").strip()
        name = str(row.get("name") or "").strip()
        if not rid or not name:
            continue
        merged[rid] = {
            "id": rid,
            "name": name,
            "status": str(row.get("status") or "active"),
            "tags": row.get("tags") if isinstance(row.get("tags"), list) else [],
            "approvedAt": row.get("approved_at"),
            "source": "supabase",
        }

    reviewers = sorted(merged.values(), key=lambda r: (str(r.get("name", "")).casefold(), str(r.get("id", ""))))
    OUT.write_text(json.dumps(reviewers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Synced reviewers: {len(remote)} Supabase / {len(reviewers)} total")


if __name__ == "__main__":
    main()
