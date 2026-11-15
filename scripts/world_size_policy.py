"""Conservative, reversible public World size exclusion policy.

This applies ONLY to VRC Club Charts public listing. The original catalog,
owner favorites, reviews and Supabase records are not deleted.

A single third-party reported File size is not an official current PC bundle
measurement. It is labeled as source-reported evidence, not an audited fact.
Unknown or malformed sizes NEVER cause a delisting.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "data" / "world-size-evidence.json"
LIMIT_MB = 100.0
MAX_AGE_DAYS = 45
WORLD_ID = re.compile(r"wrld_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
SOURCE = "vrcw-reported-file-size"
MAX_EVIDENCE_BYTES = 200_000


class WorldSizePolicyError(ValueError):
    pass


def validated_evidence(value: object, today: dt.date | None = None) -> dict[str, dict]:
    """Strict evidence validation. Invalid rows fail closed on *delisting*.

    We do not silently use corrupted/stale information to remove anything.
    """
    if not isinstance(value, dict) or value.get("schemaVersion") != 1 or not isinstance(value.get("worlds"), list):
        raise WorldSizePolicyError("invalid-size-evidence-schema")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    result = {}
    for item in value["worlds"]:
        if not isinstance(item, dict) or set(item) != {
            "id", "sizeMB", "source", "sourceUrl", "checkedOn",
            "platformInterpretation", "sourceField",
        }:
            raise WorldSizePolicyError("invalid-size-evidence-record")
        wid = item["id"]
        size = item["sizeMB"]
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid) or wid in result:
            raise WorldSizePolicyError("invalid-or-duplicate-world-id")
        if (type(size) not in (int, float) or not math.isfinite(size) or
                not 0 < size <= 10_000):
            raise WorldSizePolicyError("invalid-world-file-size")
        if (item["source"] != SOURCE or
                item["sourceUrl"] != f"https://en.vrcw.net/world/detail/{wid}" or
                item["sourceField"] != "File size" or
                item["platformInterpretation"] != "unspecified-single-reported-build"):
            raise WorldSizePolicyError("invalid-size-evidence-source")
        try:
            date = dt.date.fromisoformat(item["checkedOn"])
        except (TypeError, ValueError):
            raise WorldSizePolicyError("invalid-size-observation-date") from None
        if date > today:
            raise WorldSizePolicyError("future-size-observation")
        result[wid] = {**item, "fresh": (today - date).days <= MAX_AGE_DAYS}
    return result


def excluded_world_ids(path: Path | None = None, *, today: dt.date | None = None) -> set[str]:
    """Only fresh explicit <=100 MB reports are delisted; unknown remain.

    Fail-open for public visibility if the *optional third-party size file*
    is missing/corrupt, avoiding accidental mass deletion.
    """
    file = path if path is not None else EVIDENCE_PATH
    try:
        if not file.is_file() or file.stat().st_size > MAX_EVIDENCE_BYTES:
            return set()
        evidence = json.loads(file.read_text(encoding="utf-8"))
        parsed = validated_evidence(evidence, today=today)
    except (WorldSizePolicyError, OSError, ValueError, TypeError):
        return set()
    return {
        wid for wid, row in parsed.items()
        if row["fresh"] and row["sizeMB"] <= LIMIT_MB
    }
