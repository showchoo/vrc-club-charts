#!/usr/bin/env python3
"""Optional write-only mirror of private discovery records to Supabase.

Set SUPABASE_SERVICE_ROLE_KEY as a GitHub Actions secret to opt in.
Without the secret, static JSON publishing continues normally.
Never place the service role key in frontend code, commit, or log output.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"
API = "https://ypqpgpetrriirywrzikj.supabase.co/rest/v1"


def post_rows(path: str, rows: list[dict], key: str):
    body = json.dumps(rows, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API + path, body, method="POST", headers={
            "apikey": key, "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
            "User-Agent": "VRCClubCharts/DiscoverySync/1.0",
        }
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status not in (200, 201, 204):
            raise ValueError("Unexpected Supabase sync status")


def main():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        print("INFO: private Supabase discovery mirror not configured; local JSON is authoritative")
        return
    if key.startswith(("sb_publishable_", "sb_anon_")):
        raise ValueError("A public Supabase key cannot write private discovery records")

    records = json.loads((DATA / "world-discovery-ledger.json").read_text(encoding="utf-8"))
    report = json.loads((DATA / "discovery-report.json").read_text(encoding="utf-8"))
    if not isinstance(records, list) or not isinstance(report, dict):
        raise ValueError("Discovery records or report invalid")
    rows = [{
        "world_id": r["id"], "name": r.get("name") or "",
        "author_hint": r.get("authorHint") or "",
        "first_seen_on": r["firstSeenAt"], "last_seen_on": r["lastSeenAt"],
        "status": r["status"], "evidence": r["evidence"],
    } for r in records]
    for i in range(0, len(rows), 100):
        post_rows("/world_discovery_records?on_conflict=world_id", rows[i:i + 100], key)
    post_rows("/world_discovery_runs?on_conflict=observed_on", [{
        "observed_on": report["updatedAt"],
        "registered_worlds": report["registeredWorlds"],
        "pending_candidates": report["pendingCandidates"],
        "total_tracked_worlds": report["totalTrackedWorlds"],
        "historical_only": report["historicalOnly"],
        "sources": report["bySource"], "source_health": report["sourceHealth"],
    }], key)
    print(f"Synced {len(rows)} discovery records to private Supabase tables")


if __name__ == "__main__":
    main()
