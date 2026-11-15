#!/usr/bin/env python3
"""Read public official-origin file metadata mirror to check VRChat PC World size.

Uses *only* Hiina's public DoltHub SQL mirror of VRChat's file metadata API:
standalonewindows Unity packages and exact versioned sizeInBytes. Never
downloads Worlds, joins VRChat or uses user credentials. Old/unknown data
cannot remove a World from the public catalog.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from scripts.world_size_policy import (
        EVIDENCE_PATH, SOURCE, SOURCE_URL, SOURCE_FIELD, PLATFORM,
        WORLD_ID, FILE_ID, LIMIT_BYTES, MAX_AGE_DAYS, MAX_EVIDENCE_BYTES,
        validated_evidence, excluded_world_ids,
    )
except ModuleNotFoundError:
    from world_size_policy import (
        EVIDENCE_PATH, SOURCE, SOURCE_URL, SOURCE_FIELD, PLATFORM,
        WORLD_ID, FILE_ID, LIMIT_BYTES, MAX_AGE_DAYS, MAX_EVIDENCE_BYTES,
        validated_evidence, excluded_world_ids,
    )

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/worlds.json"
SQL_URL = "https://www.dolthub.com/api/v1alpha1/hiinaspace/vrcwscrape/main"
USER_AGENT = "VRCClubCharts/1.0 (+https://github.com/showchoo/vrc-club-charts)"
MAX_WORLDS = 250
MAX_REQUESTS = 20
BATCH = 20
MAX_RESPONSE_BYTES = 180_000
MIN_GAP_SECONDS = .8
MAX_SCAN_SECONDS = 480


class SizeCollectionError(ValueError):
    pass


def make_query(world_ids: list[str]) -> str:
    if (not isinstance(world_ids, list) or not 1 <= len(world_ids) <= BATCH or
            len(world_ids) != len(set(world_ids)) or
            any(not isinstance(wid, str) or not WORLD_ID.fullmatch(wid)
                for wid in world_ids)):
        raise SizeCollectionError("invalid-batch-world-ids")
    ids = ",".join("'" + wid + "'" for wid in world_ids)
    # Returning ONLY the latest version of each file; metadata versions for
    # old published Worlds can have dozens of previous revisions.
    version_index = "CONCAT('$.versions[', JSON_LENGTH(fm.file_metadata, '$.versions') - 1"
    return (
        "SELECT fm.world_id, fm.file_id, fm.last_scrape_time, "
        "JSON_UNQUOTE(JSON_EXTRACT(fm.file_metadata, '$.name')) AS package_name, "
        "JSON_UNQUOTE(JSON_EXTRACT(fm.file_metadata, " +
        version_index + ", '].version'))) AS package_version, "
        "JSON_UNQUOTE(JSON_EXTRACT(fm.file_metadata, " +
        version_index + ", '].file.sizeInBytes'))) AS size_bytes "
        "FROM file_metadata fm "
        "WHERE fm.file_type = 'UNITY_PACKAGE' "
        "AND fm.scrape_status = 'SUCCESS' "
        "AND fm.world_id IN (" + ids + ") LIMIT " + str(BATCH * 4)
    )


def fetch_batch(world_ids: list[str]) -> list[dict]:
    query = make_query(world_ids)
    url = SQL_URL + "?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as response:
        if response.status != 200:
            raise SizeCollectionError("mirror-non-200")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise SizeCollectionError("mirror-response-too-large")
    data = json.loads(raw)
    if (not isinstance(data, dict) or
            data.get("query_execution_status") != "Success" or
            not isinstance(data.get("rows"), list) or
            len(data["rows"]) > BATCH * 4):
        raise SizeCollectionError("mirror-sql-incomplete")
    return data["rows"]


def parse_scrape_date(value: object) -> dt.date | None:
    if not isinstance(value, str) or len(value) > 35:
        return None
    # The source uses "YYYY-MM-DD HH:MM:SS", timestamps interpreted UTC.
    try:
        return dt.date.fromisoformat(value[:10]) if re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?",
            value,
        ) else None
    except ValueError:
        return None


def extract_windows_rows(rows: object, requested: set[str],
                         today: dt.date) -> dict[str, dict]:
    """Only a unique recent *Windows* package can qualify for delisting.

    Duplicated, contradictory, Quest-only or too-old metadata is ignored.
    """
    if not isinstance(rows, list):
        raise SizeCollectionError("invalid-mirror-rows")
    candidates: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SizeCollectionError("invalid-mirror-row")
        wid = row.get("world_id")
        if wid not in requested:
            raise SizeCollectionError("mirror-world-id-unexpected")
        package = row.get("package_name")
        if not isinstance(package, str):
            continue
        name = package.casefold()
        if "standalonewindows" not in name or "android" in name or "_quest_" in name:
            continue
        file_id = row.get("file_id")
        version, size = row.get("package_version"), row.get("size_bytes")
        scraped = parse_scrape_date(row.get("last_scrape_time"))
        if (not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id)
                or scraped is None or scraped > today
                or (today - scraped).days > MAX_AGE_DAYS
                or not isinstance(version, str) or not version.isdecimal()
                or not isinstance(size, str) or not size.isdecimal()):
            continue
        v, n = int(version), int(size)
        if not (1 <= v <= 1_000_000 and 0 < n <= 10 * 1024 ** 3):
            continue
        candidates.setdefault(wid, []).append({
            "id": wid, "sizeBytes": n, "source": SOURCE,
            "sourceUrl": SOURCE_URL, "checkedOn": today.isoformat(),
            "metadataScrapedOn": scraped.isoformat(),
            "platform": PLATFORM, "sourceField": SOURCE_FIELD,
            "packageFileId": file_id, "packageVersion": v,
        })
    # If multiple current Windows packages for one World disagree, decline
    # to use ANY of them as evidence for a public removal.
    result = {}
    for wid, group in candidates.items():
        # Legitimate duplicate identical metadata should not count twice.
        distinct = {(r["packageFileId"], r["packageVersion"], r["sizeBytes"]) for r in group}
        if len(distinct) == 1:
            result[wid] = group[0]
    return result


def collect(*, catalog_path: Path = CATALOG, output_path: Path = EVIDENCE_PATH,
            max_requests: int = MAX_REQUESTS, today: dt.date | None = None,
            fetcher=None, sleep=None) -> dict:
    if type(max_requests) is not int or not 1 <= max_requests <= MAX_REQUESTS:
        raise SizeCollectionError("invalid-scan-request-budget")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or len(catalog) > MAX_WORLDS:
        raise SizeCollectionError("invalid-catalog")
    ids = sorted(set(row["id"] for row in catalog
                     if isinstance(row, dict) and
                     isinstance(row.get("id"), str) and
                     WORLD_ID.fullmatch(row["id"])))
    # Legacy, ambiguous VRCW records are NOT converted to PC sizes.
    prior = {}
    if output_path.exists():
        old = json.loads(output_path.read_text(encoding="utf-8"))
        if old.get("schemaVersion") == 2:
            prior = validated_evidence(old, today=today)
    output = {
        wid: {k: v for k, v in row.items() if k != "fresh"}
        for wid, row in prior.items() if wid in ids
    }
    fetch = fetcher if fetcher is not None else fetch_batch
    pause = sleep if sleep is not None else time.sleep
    order = sorted(ids, key=lambda wid: (
        1 if wid in output and prior[wid]["fresh"] else 0,
        output.get(wid, {}).get("checkedOn", ""), wid))
    requests = errors = scanned = measured = stale_or_unusable = 0
    started = time.monotonic()
    for offset in range(0, len(order), BATCH):
        if requests >= max_requests or time.monotonic() - started > MAX_SCAN_SECONDS:
            break
        batch = order[offset:offset + BATCH]
        if not batch:
            continue
        if requests:
            pause(MIN_GAP_SECONDS)
        requests += 1
        scanned += len(batch)
        try:
            rows = fetch(batch)
            parsed = extract_windows_rows(rows, set(batch), today)
        except (OSError, ValueError, TypeError, urllib.error.URLError):
            errors += 1
            if errors >= 3 and measured == 0:
                break
            continue
        for wid in batch:
            if wid not in parsed:
                stale_or_unusable += 1
                continue
            # Don't downgrade a previously newer mirrored observation.
            row = parsed[wid]
            if wid in output and output[wid]["metadataScrapedOn"] > row["metadataScrapedOn"]:
                continue
            output[wid] = row
            measured += 1
    document = {
        "schemaVersion": 2,
        "policy": "Only recent Windows Unity package size <=100MiB can delist a World; unknown stays",
        "worlds": [output[wid] for wid in sorted(output)],
    }
    validated_evidence(document, today=today)
    formatted = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if len(formatted.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise SizeCollectionError("pc-size-registry-too-large")
    if not output_path.exists() or output_path.read_text(encoding="utf-8") != formatted:
        output_path.write_text(formatted, encoding="utf-8")
    fresh = sum((today - dt.date.fromisoformat(r["metadataScrapedOn"])).days <= MAX_AGE_DAYS
                for r in output.values())
    small = sum(r["sizeBytes"] <= LIMIT_BYTES and
                (today - dt.date.fromisoformat(r["metadataScrapedOn"])).days <= MAX_AGE_DAYS
                for r in output.values())
    return {
        "status": "pc-size-evidence-refresh",
        "catalogWorlds": len(ids),
        "worldsScanned": scanned,
        "apiRequests": requests,
        "fetchErrors": errors,
        "rowsWithNoFreshUnambiguousWindowsPackage": stale_or_unusable,
        "freshWindowsSizes": fresh,
        "eligibleForPublicDelisting": small,
        "unknownOrStaleWorldsNotRemoved": len(ids) - fresh,
        "sizeLimitBytesInclusive": LIMIT_BYTES,
        "source": SOURCE_URL,
        "actualWorldFilesDownloaded": 0,
        "catalogEntriesDeleted": 0,
        "supabaseRowsDeleted": 0,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    args = p.parse_args(argv)
    try:
        result = collect(max_requests=args.max_requests)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        p.exit(2, f"ERROR: {type(exc).__name__}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
