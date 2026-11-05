#!/usr/bin/env python3
"""Compile PRIVATE AI video drafts into a *visual-only* provisional public feed.

Never verifies VRChat attendance, DJ playback, optimization or craftsmanship.
No cloud calls, Git operations or website deployment in this module.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import atomic_json, ROOT
    from scripts.evaluate_interior_video import validate_analysis, WORLD_ID
    from scripts.dj_stream_policy import published_worlds, load_verified
    from scripts.inspection_evidence_timeline import audit_timeline, EvidenceTimelineError
    from scripts.inspection_facility_inventory import public_facility_observations
except ModuleNotFoundError:
    from auto_process_interior_queue import atomic_json, ROOT
    from evaluate_interior_video import validate_analysis, WORLD_ID
    from dj_stream_policy import published_worlds, load_verified
    from inspection_evidence_timeline import audit_timeline, EvidenceTimelineError
    from inspection_facility_inventory import public_facility_observations

WEIGHTS = {"visual_design": 20, "lighting_design": 20,
           "spatial_design": 15, "originality": 10}
MIN_COVERAGE_WEIGHT = 45
MIN_MEAN_EVIDENCE_CONFIDENCE = 0.70
MAX_ITEMS = 500


def assess_draft(raw: dict) -> dict | None:
    """Exposes numeric observations only: no model prose, frame or user images."""
    if not isinstance(raw, dict) or raw.get("schemaVersion") != 1:
        raise ValueError("Invalid video report version")
    if raw.get("status") != "draft_video_assessment" or raw.get("rankingEligible") is not False:
        raise ValueError("Only private draft assessments are accepted")
    wid = raw.get("worldId")
    if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid):
        raise ValueError("Invalid worldId")
    evidence = raw.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("type") != "interior_video":
        raise ValueError("Video provenance missing")
    if evidence.get("source") not in {"creator-provided", "owner-recorded"}:
        raise ValueError("Unrecognized video source")
    sha = evidence.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Media SHA256 missing or malformed")
    method = raw.get("method")
    if not isinstance(method, dict) or method.get("independentInWorldInspection") is not False:
        raise ValueError("Independent inspection must not be claimed")
    consent = raw.get("consent")
    if not isinstance(consent, dict) or any(consent.get(k) is not True for k in (
        "recordingConsentConfirmed", "aiAnalysisConsentConfirmed",
        "permissionToPublishVisualEstimate",
    )):
        return None

    # The model can cite any timestamp syntactically; public estimates
    # require locally proven clip duration and in-range evidence moments.
    audit_timeline(raw)
    result = validate_analysis(raw.get("analysis"))
    observed = {}
    confidences = []
    for key, weight in WEIGHTS.items():
        dim = result["dimensions"][key]
        if dim["status"] != "observed" or dim["score"] is None:
            continue
        points = dim["evidence"]
        if not points or min(p["confidence"] for p in points) < MIN_MEAN_EVIDENCE_CONFIDENCE:
            continue
        confidences.extend(p["confidence"] for p in points)
        observed[key] = {"score": dim["score"], "weight": weight}
    coverage = sum(d["weight"] for d in observed.values())
    if coverage < MIN_COVERAGE_WEIGHT or len(observed) < 3:
        return None

    score = round(100 * sum(x["score"] * x["weight"] / 5
                            for x in observed.values()) / coverage)
    time_value = raw.get("assessedAtUtc")
    if not isinstance(time_value, str):
        raise ValueError("Missing assessment timestamp")
    try:
        moment = dt.datetime.fromisoformat(time_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid assessment timestamp") from exc
    if moment.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return {
        "worldId": wid, "visualScore": score,
        "evidenceCoverage": len(observed), "maxCategories": len(WEIGHTS),
        "observedCategories": sorted(observed),
        "meanEvidenceConfidence": round(sum(confidences) / len(confidences), 3),
        "assessedAtUtc": moment.astimezone(dt.timezone.utc).isoformat(),
        "evidenceType": "consented-video-ai-provisional",
        "mediaSha256Prefix": sha[:12],
        "facilityObservations": public_facility_observations(
            result.get("facilities"), duration_seconds=evidence["durationSeconds"],
        ),
        "independentInWorldInspection": False,
        "djPlaybackVerified": False,
        "equipmentFunctionalityVerified": False,
        "craftsmanshipScore": None,
    }


def compile_feed(draft_dir: Path, *, eligible_ids: set[str]) -> dict:
    if not draft_dir.is_dir():
        raise ValueError("Draft directory is missing")
    files = sorted(draft_dir.glob("*.draft.json"))
    if len(files) > MAX_ITEMS:
        raise ValueError("Too many drafts in one batch")
    latest = {}
    skipped = 0
    for file in files:
        # A bad report should not silently claim zero or leak private data.
        raw = json.loads(file.read_text(encoding="utf-8"))
        item = assess_draft(raw)
        if item is None or item["worldId"] not in eligible_ids:
            skipped += 1
            continue
        key = item["worldId"]
        if key not in latest or (
            item["assessedAtUtc"], item["mediaSha256Prefix"]
        ) > (
            latest[key]["assessedAtUtc"], latest[key]["mediaSha256Prefix"]
        ):
            latest[key] = item
    items = sorted(latest.values(), key=lambda x: (-x["visualScore"], x["worldId"]))
    return {
        "schemaVersion": 1, "method": "consented-video-visual-only-provisional",
        "updatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "worlds": items,
        "disclaimer": (
            "Visual-only estimates from consented recordings. No independent in-world "
            "visit, live DJ equipment test, audio measurement or optimization benchmark."
        ),
    }


def eligible_catalog_ids() -> set[str]:
    catalog = json.loads((ROOT / "data/worlds.json").read_text(encoding="utf-8"))
    published = published_worlds(catalog, load_verified())
    return {w["id"] for w in published if w.get("availabilityStatus") != "unavailable"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--publish-provisional", action="store_true",
                   help="Explicitly allow data/interior-visual-estimates.json as output")
    args = p.parse_args(argv)
    try:
        out = args.out.expanduser().resolve()
        published_path = ROOT / "data" / "interior-visual-estimates.json"
        if out.is_relative_to(ROOT):
            if not args.publish_provisional or out != published_path:
                raise ValueError("Repository output requires --publish-provisional to the exact feed path")
        draft_dir = args.draft_dir.expanduser().resolve(strict=True)
        if draft_dir.is_relative_to(ROOT):
            raise ValueError("Private video drafts must be outside the repository")
        feed = compile_feed(draft_dir, eligible_ids=eligible_catalog_ids())
        atomic_json(out, feed)
        print(json.dumps({"status": "compiled", "worlds": len(feed["worlds"]),
                          "output": str(out)}, ensure_ascii=False))
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        p.exit(2, "ERROR: " + str(exc) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
