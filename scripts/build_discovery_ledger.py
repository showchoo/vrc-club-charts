#!/usr/bin/env python3
"""Append-only evidence ledger and coverage report for club World discovery.

The source of truth for public catalog membership is still data/worlds.json.
This ledger preserves candidate evidence even after a source stops listing a
World, and never converts event/location hints into AI scores.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEDGER = DATA / "world-discovery-ledger.json"
REPORT = DATA / "discovery-report.json"
ID_RE = re.compile(r"\bwrld_[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", re.I)
MAX_EVIDENCE_PER_WORLD = 32


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def ids_in(value) -> list[str]:
    """Extract exact IDs from public metadata, not from arbitrary nested objects."""
    if not isinstance(value, str):
        return []
    return list(dict.fromkeys(x.group(0).lower() for x in ID_RE.finditer(value[:5000])))


def event_ids(event: dict) -> list[str]:
    """Never infer IDs from a similar World name, organizer or event/group ID."""
    found = []
    for key in ("worldId", "world_id", "worldUrl", "world_url", "location", "description", "url"):
        found.extend(ids_in(event.get(key)))
    return list(dict.fromkeys(found))


def event_leads(events: list[dict], source: str, today: str) -> list[dict]:
    results: dict[str, dict] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        for wid in event_ids(event):
            existing = results.get(wid)
            event_ref = str(event.get("url") or "")[:400]
            event_name = str(event.get("worldName") or event.get("name") or "")[:120]
            if not existing:
                results[wid] = {
                    "id": wid, "name": event_name or "Event venue (unverified)",
                    "authorHint": "", "source": event_ref,
                    "sourceCategories": [source], "confidenceScore": 60,
                    "confidence": "event-evidence-only",
                    "reasons": ["explicit-world-id-in-public-event", "needs-venue-review"],
                    "firstDiscoveredAt": today, "lastSeenAt": today,
                }
    return list(results.values())


def _record(observations: dict[str, dict], wid: str, today: str, *, kind: str,
            ref: str, name: str = "", author: str = ""):
    ids = ids_in(wid)
    if len(ids) != 1 or ids[0] != wid.lower():
        return
    key = ids[0]
    row = observations.setdefault(key, {"id": key, "name": "", "authorHint": "",
                                        "sources": {}})
    if name and (not row["name"] or kind == "catalog"):
        row["name"] = str(name).strip()[:120]
    if author and (not row["authorHint"] or kind == "catalog"):
        row["authorHint"] = str(author).strip()[:120]
    evidence_key = (str(kind)[:45], str(ref)[:400])
    row["sources"][evidence_key] = today


def build_ledger(today: str | None = None):
    today = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
    catalog = load(DATA / "worlds.json", [])
    pending = load(DATA / "world-candidates.json", [])
    nominations = load(DATA / "discovery-seeds.json", [])
    previous = load(LEDGER, [])
    events_auto = load(DATA / "events-auto.json", [])
    events_curated = load(DATA / "events.json", [])
    state = load(DATA / "discovery-state.json", {})
    decision_audit=load(DATA / "world-candidate-ai-decisions.json", [])
    # Explicitly non-public Worlds do not appear even as historical leads in
    # the public discovery ledger/report. Their IDs remain only in the
    # internal suppression audit so crawlers cannot add them again.
    excluded_ids={
        str(row.get("id") or "").lower() for row in decision_audit
        if isinstance(row, dict) and row.get("status")=="excluded_nonpublic"
        and ids_in(row.get("id"))
    } if isinstance(decision_audit,list) else set()

    if not isinstance(catalog, list) or not isinstance(pending, list):
        raise ValueError("World catalog and discovery queue must be arrays")
    observations: dict[str, dict] = {}
    active_ids = set()
    pending_ids = set()

    for item in catalog:
        if not isinstance(item, dict) or not ids_in(item.get("id")):
            continue
        wid = str(item["id"]).lower()
        if wid in excluded_ids:
            continue
        active_ids.add(wid)
        _record(observations, wid, today, kind="catalog",
                ref=str(item.get("source") or "data/worlds.json"),
                name=str(item.get("name") or ""), author=str(item.get("author") or ""))

    for item in pending:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id", "")).lower()
        if not ids_in(wid) or wid in active_ids or wid in excluded_ids:
            continue
        pending_ids.add(wid)
        categories = item.get("sourceCategories")
        categories = categories if isinstance(categories, list) else ["unclassified"]
        for kind in categories[:12]:
            _record(observations, wid, today, kind=str(kind),
                    ref=str(item.get("source") or "")[:400],
                    name=str(item.get("name") or ""),
                    author=str(item.get("authorHint") or ""))

    for item in nominations:
        if not isinstance(item, dict):
            continue
        wid = str(item.get("id") or "").lower()
        if ids_in(wid) and wid not in excluded_ids:
            _record(observations, wid, today,
                    kind="nominated-url" if item.get("type") != "source-listed-club" else "source-reference",
                    ref=str(item.get("source") or ""),
                    name=str(item.get("nameHint") or ""))

    for source, events in (("event-curated", events_curated), ("event-feed", events_auto)):
        if not isinstance(events, list):
            continue
        for item in events:
            if not isinstance(item, dict):
                continue
            for wid in event_ids(item):
                if wid in excluded_ids:
                    continue
                _record(observations, wid, today, kind=source,
                        ref=str(item.get("url") or "")[:400],
                        name=str(item.get("worldName") or ""))

    old_by_id = {
        row.get("id"): row for row in previous if isinstance(row, dict)
        and isinstance(row.get("id"), str) and ids_in(row["id"])
    } if isinstance(previous, list) else {}

    result = []
    for wid in sorted((set(observations) | set(old_by_id)) - excluded_ids):
        obs = observations.get(wid, {})
        old = old_by_id.get(wid, {})
        known = {}
        for e in old.get("evidence", []):
            if not isinstance(e, dict):
                continue
            key = (str(e.get("source") or "")[:45], str(e.get("ref") or "")[:400])
            if not key[0]:
                continue
            known[key] = {"source": key[0], "ref": key[1],
                          "firstSeenAt": str(e.get("firstSeenAt") or today),
                          "lastSeenAt": str(e.get("lastSeenAt") or today)}
        for (kind, ref), seen_on in obs.get("sources", {}).items():
            entry = known.setdefault((kind, ref), {
                "source": kind, "ref": ref,
                "firstSeenAt": today, "lastSeenAt": today
            })
            entry["lastSeenAt"] = seen_on
        # Most recently observed sources are retained; drop only surplus
        # evidence references, never the World itself.
        evidence = sorted(known.values(), key=lambda e: (
            e["lastSeenAt"], e["source"], e["ref"]), reverse=True)[:MAX_EVIDENCE_PER_WORLD]
        status = ("published" if wid in active_ids else
                  "pending" if wid in pending_ids else
                  "historical")
        result.append({
            "id": wid,
            "name": obs.get("name") or str(old.get("name") or "")[:120],
            "authorHint": obs.get("authorHint") or str(old.get("authorHint") or "")[:120],
            "firstSeenAt": str(old.get("firstSeenAt") or today),
            "lastSeenAt": today if obs else str(old.get("lastSeenAt") or today),
            "status": status,
            "evidence": evidence,
        })

    sources = Counter()
    for entry in result:
        sources.update({e["source"] for e in entry["evidence"]})
    health = state.get("sourceHealth", {}) if isinstance(state, dict) else {}
    report = {
        "updatedAt": today, "registeredWorlds": len(active_ids),
        "pendingCandidates": len(pending_ids), "totalTrackedWorlds": len(result),
        "historicalOnly": sum(x["status"] == "historical" for x in result),
        "bySource": dict(sorted(sources.items())),
        "sourceHealth": health if isinstance(health, dict) else {},
        "disclaimer": "Observed public World IDs, not a census of every VRChat club.",
    }
    return result, report


def main():
    entries, report = build_ledger()
    LEDGER.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Discovery ledger: {totalTrackedWorlds} tracked, {registeredWorlds} registered, "
          "{pendingCandidates} pending, {historicalOnly} historical".format(**report))


if __name__ == "__main__":
    main()
