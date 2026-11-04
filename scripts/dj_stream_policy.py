"""Publication policy for DJ-tagged and independently live-stream-tested Worlds.

An exact DJ tag permits listing without proof of a working live-stream player.
Only independently tested/creator-confirmed evidence earns a LIVE VERIFIED label.
Unknown or explicitly non-public Worlds must not be represented as verified.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "data" / "dj-stream-verifications.json"
WORLD_ID = re.compile(r"^wrld_[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}$")
METHODS = {"live-playback-tested", "creator-confirmed-live-playback"}

POLICY = "dj-tag-or-verified-live-stream"


def is_dj_tag(tag: object) -> bool:
    """Match DJ tags, not World names, descriptions, DJVU or DJ booth text."""
    return isinstance(tag, str) and tag.strip().casefold() in {"dj", "author_tag_dj"}


def has_dj_tag(world: dict) -> bool:
    """Use catalog genres (existing visible tags) or retained VRChat official tags."""
    if not isinstance(world, dict):
        return False
    for key in ("genres", "officialTags"):
        tags = world.get(key, [])
        if isinstance(tags, list) and any(is_dj_tag(tag) for tag in tags):
            return True
    return False



def load_verified(registry_path: Path | None = None) -> dict[str, dict]:
    """Only explicitly verified entries with dated, HTTPS evidence may publish."""
    path = registry_path if registry_path is not None else REGISTRY
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("worlds"), list):
        raise ValueError("DJ stream verification registry must contain a worlds list")
    verified = {}
    seen = set()
    for entry in payload["worlds"]:
        if not isinstance(entry, dict):
            raise ValueError("Invalid DJ stream evidence row")
        wid = entry.get("worldId")
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid) or wid in seen:
            raise ValueError("Invalid or duplicate World ID in DJ stream registry")
        seen.add(wid)
        status = entry.get("status", "needs-review")
        if status not in {"verified", "needs-review", "unsupported"}:
            raise ValueError(f"Invalid DJ stream verification status for {wid}")
        if status != "verified":
            continue
        method = entry.get("method")
        by = entry.get("verifiedBy")
        evidence = entry.get("evidenceUrl")
        date = entry.get("verifiedAt")
        platform = entry.get("platform")
        if method not in METHODS or not isinstance(by, str) or not by.strip():
            raise ValueError(f"DJ livestream verification needs named evidence source: {wid}")
        if platform not in {"PC", "PC-and-Quest"}:
            raise ValueError(f"DJ livestream verification needs tested platform: {wid}")
        if not isinstance(evidence, str):
            raise ValueError(f"DJ livestream verification evidence URL missing: {wid}")
        url = urlsplit(evidence)
        if url.scheme != "https" or not url.hostname or url.username or url.password or len(evidence) > 800:
            raise ValueError(f"DJ livestream verification evidence URL invalid: {wid}")
        try:
            tested = dt.date.fromisoformat(date)
        except (TypeError, ValueError):
            raise ValueError(f"DJ livestream verification date invalid: {wid}") from None
        if tested > dt.datetime.now(dt.timezone.utc).date():
            raise ValueError(f"DJ livestream verification date cannot be future: {wid}")
        verified[wid] = {
            "status": "verified", "method": method,
            "verifiedAt": date, "verifiedBy": by.strip(),
            "evidenceUrl": evidence, "platform": platform,
        }
    return verified


def published_worlds(worlds: list[dict], verified: dict[str, dict]) -> list[dict]:
    """Admit exact DJ tags or genuine verification; keep publication basis explicit.

    The visible DJ tag is a *directory* admission rule, never proof of playback.
    This function is idempotent so the ranking and static builders may both use it.
    """
    result = []
    for item in worlds:
        if not isinstance(item, dict):
            continue
        wid = item.get("id")
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid):
            continue
        status = str(item.get("releaseStatus") or "").strip().casefold()
        if status in {"private", "hidden", "unpublished", "pending"}:
            continue
        if item.get("availabilityStatus") == "unavailable":
            continue
        if item.get("chartEligible") is False:
            continue
        proof = verified.get(wid)
        dj_tag = has_dj_tag(item)
        if not (dj_tag or proof):
            continue
        result.append({
            **item,
            "publicationBasis": "live-playback-verified" if proof else "dj-tag",
            "djStreamVerification": proof if proof else None,
            "djStreamTested": bool(proof),
        })
    return result


def sanitize_ai_scout(source: dict, admitted: dict[str, object]) -> dict:
    """Hide all non-admitted and discovery-only Worlds from the public AI feed."""
    if not isinstance(source, dict):
        source = {}
    def allowed(record):
        return (isinstance(record, dict)
                and record.get("sourceType") == "catalog"
                and record.get("id") in admitted)
    scored = [row for row in source.get("scored", []) if allowed(row)] if isinstance(source.get("scored"), list) else []
    scored_ids = {row["id"] for row in scored}
    candidates = [row for row in source.get("candidates", [])
                  if allowed(row) and row["id"] not in scored_ids] if isinstance(source.get("candidates"), list) else []
    attempts = source.get("attempts", {})
    attempts = {wid: value for wid, value in attempts.items() if wid in admitted} if isinstance(attempts, dict) else {}
    summary = dict(source.get("summary") or {})
    summary.update(totalCandidates=len(scored)+len(candidates),
                   assessed=len(scored), pending=len(candidates), newAssessments=0)
    return {**source, "summary": summary, "scored": scored,
            "candidates": candidates, "attempts": attempts}
