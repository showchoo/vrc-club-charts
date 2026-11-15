#!/usr/bin/env python3
"""One-request public DoltHub VRChat World PC package size probe (no credentials)."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
import urllib.error

WORLD_ID = "wrld_cb038e55-713b-4aa7-a1d2-d4f37a403c92"
BASE = "https://www.dolthub.com/api/v1alpha1/hiinaspace/vrcwscrape/main"
QUERY = (
    "SELECT fm.world_id, fm.file_type, fm.last_scrape_time, "
    "JSON_UNQUOTE(JSON_EXTRACT(fm.file_metadata, '$.name')) AS package_name, "
    "JSON_UNQUOTE(JSON_EXTRACT(fm.file_metadata, "
    "CONCAT('$.versions[', JSON_LENGTH(fm.file_metadata, '$.versions') - 1, "
    "'].file.sizeInBytes'))) AS latest_size_bytes "
    "FROM file_metadata fm WHERE fm.world_id = '" + WORLD_ID + "' "
    "AND fm.file_type = 'UNITY_PACKAGE' LIMIT 5"
)

def main():
    u = BASE + "?" + urllib.parse.urlencode({"q": QUERY})
    req = urllib.request.Request(u, headers={
        "Accept": "application/json",
        "User-Agent": "VRCClubCharts/1.0 (+https://github.com/showchoo/vrc-club-charts)"
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read(100_001)
            print(json.dumps({"httpStatus": response.status, "bytes": len(raw)}))
        if len(raw) > 100_000:
            raise ValueError("response-too-large")
        data = json.loads(raw.decode("utf-8"))
        print(json.dumps({
            "queryStatus": data.get("query_execution_status"),
            "message": str(data.get("query_execution_message") or "")[:250],
            "columnNames": [x.get("columnName") for x in data.get("schema", []) if isinstance(x, dict)],
            "rows": data.get("rows", [])[:5],
        }, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as exc:
        print(json.dumps({"httpStatus": exc.code, "error": "http-error"}))
    except Exception as exc:
        print(json.dumps({"errorType": type(exc).__name__}))

if __name__ == "__main__":
    main()
