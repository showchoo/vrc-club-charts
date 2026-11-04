"""Publication policy for DJ-tagged and independently live-stream-tested Worlds.

An exact DJ tag or explicitly recorded site-owner favorite confirmation permits listing.
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
OWNER_REGISTRY = ROOT / "data" / "owner-favorite-confirmations.json"
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



def load_owner_confirmed(path: Path | None = None) -> dict[str, dict]:
    """Read explicitly attested owner favorites, never infer from favorite counts.

    This is a *user assertion* of in-world functionality, distinct from
    independent technical confirmation. It is not for untrusted visitor forms.
    """
    source = path if path is not None else OWNER_REGISTRY
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("worlds"), list):
        raise ValueError("Owner favorite confirmation registry must contain worlds")
    confirmed = {}
    for record in payload["worlds"]:
        if not isinstance(record, dict):
            raise ValueError("Invalid owner favorite confirmation")
        wid = record.get("worldId")
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid) or wid in confirmed:
            raise ValueError("Duplicate or invalid owner favorite World ID")
        if (record.get("confirmation") != "owner-attested-live-playback" or
                record.get("releaseStatusAtSubmission") != "public" or
                record.get("source") != f"https://vrchat.com/home/world/{wid}/info"):
            raise ValueError(f"Unverified origin of owner favorite {wid}")
        date = record.get("attestedAt")
        try:
            when = dt.date.fromisoformat(date)
        except (ValueError, TypeError):
            raise ValueError(f"Owner confirmation date invalid for {wid}") from None
        # Owner statement was made in Japan; allow the local 2026-11-05 date
        # even when GitHub Actions is still on 2026-11-04 UTC.
        jst = dt.timezone(dt.timedelta(hours=9))
        if when > dt.datetime.now(jst).date():
            raise ValueError(f"Owner confirmation date in future for {wid}")
        confirmed[wid] = {
            "status": "owner-attested",
            "attestedAt": date,
            "method": "owner-asserted-in-world-live-playback",
            "source": record["source"],
        }
    return confirmed


def published_worlds(worlds: list[dict], verified: dict[str, dict]) -> list[dict]:
    """Admit exact DJ tags or genuine verification; keep publication basis explicit.

    The visible DJ tag is a *directory* admission rule, never proof of playback.
    This function is idempotent so the ranking and static builders may both use it.
    """
    # Exact owner confirmations are admitted as a separately labeled trust
    # source. They do NOT receive the independently verified stream badge.
    owner_confirmed = load_owner_confirmed()
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
        owner_proof = owner_confirmed.get(wid)
        dj_tag = has_dj_tag(item)
        if not (dj_tag or proof or owner_proof):
            continue
        basis = ("live-playback-verified" if proof else
                 "owner-favorite-confirmed" if owner_proof else "dj-tag")
        result.append({
            **item,
            "publicationBasis": basis,
            "djStreamVerification": proof if proof else None,
            "djStreamTested": bool(proof),
            "ownerStreamConfirmation": owner_proof,
            "djStreamOwnerConfirmed": bool(owner_proof),
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
