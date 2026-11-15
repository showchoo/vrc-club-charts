#!/usr/bin/env python3
"""Read-only 20-World integration probe for publicly mirrored VRChat PC sizes."""
from __future__ import annotations

import datetime as dt
import json

try:
    from scripts.update_world_sizes import CATALOG, fetch_batch, extract_windows_rows
except ModuleNotFoundError:
    from update_world_sizes import CATALOG, fetch_batch, extract_windows_rows


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    ids = sorted({
        row["id"] for row in catalog
        if isinstance(row, dict) and isinstance(row.get("id"), str)
    })[:20]
    today = dt.datetime.now(dt.timezone.utc).date()
    try:
        results = fetch_batch(ids)
        accepted = extract_windows_rows(results, set(ids), today)
        print(json.dumps({
            "status": "read-only-dolthub-pc-source-check",
            "worldsQueried": len(ids),
            "packageRowsReturned": len(results),
            "freshUnambiguousWindowsPackages": len(accepted),
            "staleOrUnknownWorlds": len(ids) - len(accepted),
            "windowsExamples": [
                {"worldId": key,
                 "sizeBytes": value["sizeBytes"],
                 "metadataScrapedOn": value["metadataScrapedOn"],
                 "wouldDelist": value["sizeBytes"] <= 100 * 1024 * 1024}
                for key, value in list(accepted.items())[:4]
            ],
            "databaseModified": False,
            "catalogModified": False,
        }, indent=2, ensure_ascii=False))
    except Exception as exc:
        # This integration probe must FAIL when the SQL/HTTP source stops
        # working; a green check would give false confidence.
        print(json.dumps({"status": "failed", "type": type(exc).__name__}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
