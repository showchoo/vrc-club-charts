"""Strict audit of evidence timestamps against a locally measured MP4 duration.

This never connects to VRChat or Gemini. It cannot confirm that model
descriptions match the actual frames, only reject impossible timestamps,
unverified media metadata and footage known to be black/stalled.
"""
from __future__ import annotations

import math

try:
    from scripts.evaluate_interior_video import validate_analysis
except ModuleNotFoundError:
    from evaluate_interior_video import validate_analysis

MAX_SECONDS = 125.0
TIMESTAMP_TOLERANCE = 0.25
DURATION_SOURCE = "ffprobe"


class EvidenceTimelineError(ValueError):
    """An AI result cannot be grounded to the actual duration/quality evidence."""


def verified_duration(value: object) -> float:
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or
        not math.isfinite(value) or not 2 <= value <= MAX_SECONDS):
        raise EvidenceTimelineError("Missing or implausible FFprobe video duration")
    return float(value)


def audit_timeline(report: dict) -> dict:
    """Validate every model-supplied timestamp before a video is publishable."""
    if not isinstance(report, dict) or not isinstance(report.get("evidence"), dict):
        raise EvidenceTimelineError("Missing report/video provenance")
    evidence = report["evidence"]
    duration = verified_duration(evidence.get("durationSeconds"))
    if evidence.get("durationSource") != DURATION_SOURCE:
        raise EvidenceTimelineError("Actual duration must be verified by FFprobe")
    quality = report.get("visualQuality")
    if not isinstance(quality, dict) or quality.get("status") != "ok":
        raise EvidenceTimelineError("Unusable or unverified visual footage")
    for key, threshold in (
        ("sampledFrames", 2),
        ("visualChangeIntervals", 1),
        ("framesWithDetail", 2),
    ):
        number = quality.get(key)
        if isinstance(number, bool) or not isinstance(number, int) or number < threshold:
            raise EvidenceTimelineError("Insufficient verified frame evidence: " + key)
    analysis = validate_analysis(report.get("analysis"))
    observed_dimensions = 0
    checked_points = 0
    for name, dimension in analysis["dimensions"].items():
        if dimension["status"] == "observed":
            observed_dimensions += 1
        for point in dimension["evidence"]:
            timestamp = point["timestamp_seconds"]
            if timestamp > duration + TIMESTAMP_TOLERANCE:
                raise EvidenceTimelineError(
                    "Model cited a time beyond the verified recording duration"
                )
            checked_points += 1
    return {
        "timelineChecked": True,
        "durationSeconds": duration,
        "evidencePointsChecked": checked_points,
        "observedDimensions": observed_dimensions,
        "timestampToleranceSeconds": TIMESTAMP_TOLERANCE,
        "independentSceneProof": False,
        "equipmentFunctionalityVerified": False,
    }


def attach_verified_timeline(report: dict, *, metadata: dict, visual_quality: dict) -> dict:
    """Attach locally derived metadata, then fail closed if AI cites absent frames.

    This annotates only an already-local private draft report, not the public
    data feed. Caller must have derived metadata from the exact video bytes.
    """
    if (not isinstance(metadata, dict) or metadata.get("metadataVerified") is not True
        or metadata.get("audioTracks") != 0):
        raise EvidenceTimelineError("Missing valid local FFprobe verification")
    duration = verified_duration(metadata.get("durationSeconds"))
    if not isinstance(report, dict) or not isinstance(report.get("evidence"), dict):
        raise EvidenceTimelineError("Missing draft report evidence")
    enriched = {**report,
                "evidence": {**report["evidence"], "durationSeconds": duration,
                             "durationSource": DURATION_SOURCE},
                "visualQuality": visual_quality}
    enriched["timelineAudit"] = audit_timeline(enriched)
    return enriched
