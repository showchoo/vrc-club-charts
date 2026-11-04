"""Fail-closed publication gate for VRChat DJ live-stream-capable Worlds.

AI scores, club tags, DJ booth thumbnails and mere video-player presence are
never proof that a *live stream* can be played by event attendees.
The source catalog remains intact; this registry controls what is published.
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
    """No record can publish unless independent live-stream evidence exists."""
    return [
        {**item, "djStreamVerification": verified[item["id"]]}
        for item in worlds
        if isinstance(item, dict) and item.get("id") in verified
        and item.get("availabilityStatus") != "unavailable"
        and str(item.get("releaseStatus") or "").casefold() not in {"private", "hidden"}
    ]


def sanitize_ai_scout(source: dict, verified: dict[str, dict]) -> dict:
    """Hide all unverified and candidate-only Worlds from the public AI feed."""
    if not isinstance(source, dict):
        source = {}
    def allowed(record):
        return (isinstance(record, dict)
                and record.get("sourceType") == "catalog"
                and record.get("id") in verified)
    scored = [row for row in source.get("scored", []) if allowed(row)] if isinstance(source.get("scored"), list) else []
    scored_ids = {row["id"] for row in scored}
    candidates = [row for row in source.get("candidates", [])
                  if allowed(row) and row["id"] not in scored_ids] if isinstance(source.get("candidates"), list) else []
    attempts = source.get("attempts", {})
    attempts = {wid: value for wid, value in attempts.items() if wid in verified} if isinstance(attempts, dict) else {}
    summary = dict(source.get("summary") or {})
    summary.update(totalCandidates=len(scored)+len(candidates),
                   assessed=len(scored), pending=len(candidates), newAssessments=0)
    return {**source, "summary": summary, "scored": scored,
            "candidates": candidates, "attempts": attempts}
