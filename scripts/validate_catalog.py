#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORLD_ID_RE = re.compile(r"^wrld_[0-9a-fA-F-]{36}$")
CRAFT_MAX = {
    "visual": 20,
    "lighting": 20,
    "sound": 15,
    "spatial": 15,
    "interaction": 10,
    "originality": 10,
    "optimization": 10,
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)


def main() -> int:
    errors = 0
    worlds = json.loads((ROOT / "data/worlds.json").read_text(encoding="utf-8"))
    ranking = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))

    if not isinstance(worlds, list) or not worlds:
        fail("data/worlds.json must be a non-empty array")
        return 1

    seen = set()
    for i, w in enumerate(worlds, start=1):
        wid = str(w.get("id", ""))
        if not WORLD_ID_RE.fullmatch(wid):
            fail(f"world #{i} has invalid id: {wid!r}")
            errors += 1
        if wid in seen:
            fail(f"duplicate world id: {wid}")
            errors += 1
        seen.add(wid)

        if not str(w.get("name", "")).strip():
            fail(f"{wid}: missing name")
            errors += 1
        if not str(w.get("author", "")).strip():
            fail(f"{wid}: missing author")
            errors += 1

        status = w.get("editorialStatus") or ("provisional" if w.get("editorial") else "unreviewed")
        if status not in {"provisional", "reviewed", "unreviewed"}:
            fail(f"{wid}: unsupported editorialStatus {status!r}")
            errors += 1

        editorial = w.get("editorial")
        if status != "unreviewed":
            if not isinstance(editorial, dict):
                fail(f"{wid}: reviewed/provisional world needs editorial scores")
                errors += 1
            else:
                for key, maximum in CRAFT_MAX.items():
                    value = editorial.get(key)
                    if not isinstance(value, (int, float)) or not 0 <= value <= maximum:
                        fail(f"{wid}: editorial.{key} must be 0..{maximum}")
                        errors += 1

        genres = w.get("genres")
        if not isinstance(genres, list) or not all(isinstance(g, str) and g.strip() for g in genres):
            fail(f"{wid}: genres must be a non-empty-string array")
            errors += 1

    ranked_ids = [w.get("id") for w in ranking.get("worlds", [])]
    unknown = sorted(set(ranked_ids) - seen)
    if unknown:
        fail(f"weekly-ranking contains unknown ids: {unknown}")
        errors += 1

    missing = sorted(seen - set(ranked_ids))
    if missing:
        fail(f"weekly-ranking is missing {len(missing)} registry ids")
        errors += 1

    if len(ranked_ids) != len(set(ranked_ids)):
        fail("weekly-ranking contains duplicate ids")
        errors += 1

    if errors:
        print(f"Validation failed with {errors} error(s).", file=sys.stderr)
        return 1

    print(f"Catalog OK: {len(worlds)} worlds, {len(ranked_ids)} ranking rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
