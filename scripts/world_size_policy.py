"""Reversible public DJ World delisting using PC-specific package metadata.

Only the standalone Windows asset bundle qualifies. Unknown, Quest-only,
ambiguous, stale, or invalid metadata never results in a removal.
Original catalogs, reviews, favorites and Supabase records are preserved.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "world-size-evidence.json"
LIMIT_BYTES = 100 * 1024 * 1024  # 100 MiB, inclusive
MAX_AGE_DAYS = 90
MAX_EVIDENCE_BYTES = 250_000
WORLD_ID = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
FILE_ID = re.compile(r"file_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
SOURCE = "hiinaspace-vrcwscrape-dolthub-vrchat-file-metadata"
SOURCE_URL = "https://www.dolthub.com/repositories/hiinaspace/vrcwscrape"
SOURCE_FIELD = "versions[last].file.sizeInBytes"
PLATFORM = "standalonewindows"


class WorldSizePolicyError(ValueError):
    pass


def validated_evidence(value: object, today: dt.date | None = None) -> dict[str, dict]:
    """Check provenance, integer bytes and ORIGINAL metadata scrape date."""
    if not isinstance(value, dict) or value.get("schemaVersion") != 2 or not isinstance(value.get("worlds"), list):
        raise WorldSizePolicyError("invalid-pc-size-evidence-schema")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    result = {}
    required = {
        "id", "sizeBytes", "source", "sourceUrl", "checkedOn",
        "metadataScrapedOn", "platform", "sourceField",
        "packageFileId", "packageVersion",
    }
    for item in value["worlds"]:
        if not isinstance(item, dict) or set(item) != required:
            raise WorldSizePolicyError("invalid-pc-size-evidence-record")
        wid, fid, size = item["id"], item["packageFileId"], item["sizeBytes"]
        if (not isinstance(wid, str) or not WORLD_ID.fullmatch(wid)
                or wid in result or not isinstance(fid, str)
                or not FILE_ID.fullmatch(fid)):
            raise WorldSizePolicyError("invalid-world-or-package-id")
        if (type(size) is not int or not 0 < size <= 10 * 1024 ** 3
                or type(item["packageVersion"]) is not int
                or not 1 <= item["packageVersion"] <= 1_000_000):
            raise WorldSizePolicyError("invalid-pc-size-or-version")
        if (item["source"] != SOURCE or item["sourceUrl"] != SOURCE_URL
                or item["platform"] != PLATFORM or
                item["sourceField"] != SOURCE_FIELD):
            raise WorldSizePolicyError("untrusted-pc-size-source")
        try:
            checked = dt.date.fromisoformat(item["checkedOn"])
            scraped = dt.date.fromisoformat(item["metadataScrapedOn"])
        except (TypeError, ValueError):
            raise WorldSizePolicyError("invalid-pc-size-observation-date") from None
        if (checked > today or scraped > today or scraped > checked):
            raise WorldSizePolicyError("pc-size-metadata-dates-inconsistent")
        # A fresh read of a stale mirror DOES NOT make the data fresh.
        result[wid] = {**item, "fresh": (today - checked).days <= MAX_AGE_DAYS
                       and (today - scraped).days <= MAX_AGE_DAYS}
    return result


def excluded_world_ids(path: Path | None = None, *, today: dt.date | None = None) -> set[str]:
    """Only ≤100MiB fresh, platform-verified Windows builds are excluded."""
    file = path if path is not None else EVIDENCE_PATH
    try:
        if not file.is_file() or file.stat().st_size > MAX_EVIDENCE_BYTES:
            return set()
        parsed = validated_evidence(
            json.loads(file.read_text(encoding="utf-8")), today=today)
    except (OSError, ValueError, TypeError):
        return set()
    return {
        wid for wid, item in parsed.items()
        if item["fresh"] and item["sizeBytes"] <= LIMIT_BYTES
    }
