#!/usr/bin/env python3
"""Refresh source-reported public VRChat World file sizes, conservatively.

Only reads publicly available VRCW HTML for IDs already in VCC's catalog.
Never authenticates to VRChat, downloads any world asset, changes Supabase,
or deletes catalog/history records. The listing policy (world_size_policy)
reads only the bounded evidence file and decides what to hide from the site.

Third-party "File size" may be stale or platform-ambiguous: the registry
explicitly labels it as an unspecified single reported build. Unknowns
and any parse/network failures do NOT create removals.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from scripts.world_size_policy import (
        EVIDENCE_PATH, SOURCE, WORLD_ID, LIMIT_MB, validated_evidence,
    )
except ModuleNotFoundError:
    from world_size_policy import (
        EVIDENCE_PATH, SOURCE, WORLD_ID, LIMIT_MB, validated_evidence,
    )

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "worlds.json"
SOURCE_ROOT = "https://en.vrcw.net/world/detail/"
USER_AGENT = "VRCClubCharts/1.0 (+https://github.com/showchoo/vrc-club-charts)"
MAX_HTML_BYTES = 600_000
MAX_WORLDS = 250
MAX_SECONDS = 600
MIN_GAP_SECONDS = .7
PAGE_SIZE_RE = re.compile(
    r"\bFile\s+size\s*[:：]?\s*(\d{1,5}(?:\.\d{1,3})?)\s*MB\b", re.I,
)
TAG = re.compile(r"(?is)<[^>]*>")
SCRIPTS = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
WS = re.compile(r"\s+")


class SizeCollectionError(ValueError):
    pass


def extract_reported_size(page: str, world_id: str) -> float | None:
    """Trust only an exact World ID and an unambiguous displayed MB value."""
    if (not isinstance(page, str) or len(page) > MAX_HTML_BYTES or
            not WORLD_ID.fullmatch(world_id)):
        return None
    # A broken redirect/login page must not silently become a size claim.
    if world_id not in page:
        return None
    sanitized = SCRIPTS.sub(" ", page)
    plain = WS.sub(" ", html.unescape(TAG.sub(" ", sanitized)))
    numbers = PAGE_SIZE_RE.findall(plain)
    if len(numbers) != 1:
        return None
    size = float(numbers[0])
    if not 0 < size <= 10000:
        return None
    return size


def fetch_public_size(world_id: str) -> float | None:
    if not WORLD_ID.fullmatch(world_id):
        raise SizeCollectionError("invalid-world-id")
    req = urllib.request.Request(
        SOURCE_ROOT + world_id,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status != 200:
            return None
        mime = response.headers.get_content_type()
        if mime != "text/html":
            return None
        raw = response.read(MAX_HTML_BYTES + 1)
        if len(raw) > MAX_HTML_BYTES:
            return None
        return extract_reported_size(raw.decode("utf-8", errors="replace"), world_id)


def collect(*, catalog_path: Path = CATALOG,
            output_path: Path = EVIDENCE_PATH,
            max_requests: int = 200,
            today: dt.date | None = None,
            fetcher=None,
            sleep=None) -> dict:
    if type(max_requests) is not int or not 1 <= max_requests <= MAX_WORLDS:
        raise SizeCollectionError("invalid-scan-budget")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or len(catalog) > MAX_WORLDS:
        raise SizeCollectionError("invalid-catalog-size")
    ids = sorted(set(row["id"] for row in catalog
                     if isinstance(row, dict) and
                     isinstance(row.get("id"), str) and
                     WORLD_ID.fullmatch(row["id"])))
    if output_path.exists():
        raw = json.loads(output_path.read_text(encoding="utf-8"))
        prior = validated_evidence(raw, today=today)
    else:
        prior = {}
    # Preserve historical (but stale) source observations without using them
    # for a new public delisting until refreshed.
    output = {wid: row for wid, row in prior.items() if wid in ids}
    fetch = fetcher if fetcher is not None else fetch_public_size
    pause = sleep if sleep is not None else time.sleep
    requests = errors = no_size = newly_measured = 0
    started = time.monotonic()
    # Sort unknown first, then oldest source observations, to avoid a
    # few familiar Worlds consuming every daily scan budget.
    order = sorted(ids, key=lambda wid: (
        1 if wid in output else 0,
        output.get(wid, {}).get("checkedOn", ""),
        wid))
    for wid in order:
        if requests >= max_requests or time.monotonic() - started >= MAX_SECONDS:
            break
        # Freshly checked Worlds need no second fetch the same day.
        if wid in output and output[wid]["checkedOn"] == today.isoformat():
            continue
        if requests:
            pause(MIN_GAP_SECONDS)
        requests += 1
        try:
            size = fetch(wid)
        except (OSError, ValueError, TimeoutError, urllib.error.URLError):
            errors += 1
            # Polite stop on repetitive access failures; never brute-force.
            if errors >= 5 and newly_measured == 0:
                break
            continue
        if size is None:
            no_size += 1
            continue
        if type(size) not in (float, int) or not 0 < size <= 10000:
            errors += 1
            continue
        row = {
            "id": wid, "sizeMB": round(float(size), 3),
            "source": SOURCE, "sourceUrl": SOURCE_ROOT + wid,
            "checkedOn": today.isoformat(),
            "platformInterpretation": "unspecified-single-reported-build",
            "sourceField": "File size",
        }
        output[wid] = row
        newly_measured += 1
    data = {
        "schemaVersion": 1,
        "policy": "Exclude recently observed source-reported single-build size <=100MB; unknown remain visible",
        "worlds": [output[wid] for wid in sorted(output)],
    }
    validated_evidence(data, today=today)
    formatted = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if len(formatted.encode("utf-8")) > 200_000:
        raise SizeCollectionError("size-registry-too-large")
    if not output_path.exists() or output_path.read_text(encoding="utf-8") != formatted:
        output_path.write_text(formatted, encoding="utf-8")
    eligible = sum(1 for r in output.values()
                   if (today - dt.date.fromisoformat(r["checkedOn"])).days <= 45
                   and r["sizeMB"] <= LIMIT_MB)
    return {
        "status": "size-evidence-refresh",
        "catalogWorlds": len(ids),
        "pagesRequested": requests,
        "pagesUnusable": no_size,
        "fetchErrors": errors,
        "measurementsRecorded": newly_measured,
        "knownWorldSizes": len(output),
        "eligibleForPublicDelisting": eligible,
        "unknownWorldsNotRemoved": len(ids) - len(output),
        "source": SOURCE_ROOT,
        "sourceNotOfficialVRChat": True,
        "sourcePlatformNotIndependentlyVerified": True,
        "catalogEntriesDeleted": 0,
        "supabaseRowsDeleted": 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=200)
    args = parser.parse_args(argv)
    try:
        result = collect(max_requests=args.max_requests)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {type(exc).__name__}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
