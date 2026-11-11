"""Strict, low-privilege DJ/club facility *appearance* evidence from video.

A facility in a frame is not proof of streaming, interoperability, sound,
hardware operation, permissions or optimization. All free-form observations
stay private. Public outputs only use allowlisted facility IDs and numeric
relative timestamps/confidence, never model descriptions or user identities.
"""
from __future__ import annotations

import math

FACILITIES = (
    "dj_booth", "dj_decks", "video_screen", "lighting_rig", "stage",
    "interactive_control",
)
LABELS_JA = {
    "dj_booth": "DJブース",
    "dj_decks": "DJ機材らしきもの",
    "video_screen": "映像スクリーン",
    "lighting_rig": "照明設備",
    "stage": "ステージ",
    "interactive_control": "操作パネルらしきもの",
}
MAX_EVIDENCE_PER_FACILITY = 2
MIN_PUBLIC_CONFIDENCE = 0.80
MAX_VIDEO_SECONDS = 125.0

MODEL_INSTRUCTIONS = """
In addition to summary and dimensions, return facilities as an object with
exactly these keys: dj_booth, dj_decks, video_screen, lighting_rig, stage,
interactive_control. For each facility return EXACTLY:
{ "visibility": "visible" | "not_visible" | "unclear",
  "evidence": [{"timestamp_seconds": number, "confidence": number}] }
Use "visible" ONLY for a distinctive directly visible object in the supplied
recording, with at most 2 real timestamps (seconds into this video) and
confidence in [0,1]; otherwise use "unclear" and an empty evidence array.
"not_visible" means not observed in the shown frames, NOT proof the facility
does not exist elsewhere in the World. If the object might be decoration or an
unrecognized UI, use "unclear". A raised stage, empty platform, lighting,
video screen, or a DJ-themed room must NEVER by itself be counted as a
visible DJ booth or DJ decks. If the DJ platform is elevated, behind a wall,
out of camera view or occluded, return "not_visible" for dj_booth unless
its actual booth structure is distinctly visible in at least one frame.
When visibility is ambiguous, use "unclear" instead of inventing a 90% sighting.
Do not infer whether any equipment operates,
supports live streaming, has URL access, or works for DJs. Do not identify users.
Never quote on-screen text, avatars, usernames or personal information.
"""


def validate_facilities(data: object) -> dict | None:
    """Strictly normalize Gemini facility observations; None supports old drafts."""
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) != set(FACILITIES):
        raise ValueError("Facilities must include exactly the allowlisted categories")
    normalized = {}
    for kind in FACILITIES:
        item = data[kind]
        if not isinstance(item, dict) or set(item) != {"visibility", "evidence"}:
            raise ValueError("Invalid facility category contents")
        visibility = item["visibility"]
        if not isinstance(visibility, str) or visibility not in {"visible", "not_visible", "unclear"}:
            raise ValueError("Invalid facility visibility state")
        evidence = item["evidence"]
        if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE_PER_FACILITY:
            raise ValueError("Invalid facility evidence count")
        if visibility != "visible" and evidence:
            raise ValueError("Unseen facilities cannot carry visible frame evidence")
        if visibility == "visible" and not evidence:
            raise ValueError("Visible facilities require timestamped evidence")
        points = []
        for point in evidence:
            if not isinstance(point, dict) or set(point) != {"timestamp_seconds", "confidence"}:
                raise ValueError("Facility evidence may contain only time and confidence")
            moment, confidence = point["timestamp_seconds"], point["confidence"]
            if (isinstance(moment, bool) or not isinstance(moment, (int, float)) or
                not math.isfinite(moment) or not 0 <= moment <= 36000 or
                isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or
                not math.isfinite(confidence) or not 0 <= confidence <= 1):
                raise ValueError("Invalid facility timestamp or confidence")
            points.append({"timestamp_seconds": float(moment), "confidence": float(confidence)})
        normalized[kind] = {"visibility": visibility, "evidence": points}
    return normalized


def public_facility_observations(facilities: dict | None, *, duration_seconds: float) -> list[dict]:
    """Emit only high-confidence, time-valid appearances; never functionality."""
    if facilities is None:
        return []
    valid = validate_facilities(facilities)
    if (isinstance(duration_seconds, bool) or
        not isinstance(duration_seconds, (int, float)) or
        not math.isfinite(duration_seconds) or not 2 <= duration_seconds <= MAX_VIDEO_SECONDS):
        raise ValueError("No independently verified video duration")
    observations = []
    for kind in FACILITIES:
        item = valid[kind]
        if item["visibility"] != "visible":
            continue
        points = [p for p in item["evidence"]
                  if p["confidence"] >= MIN_PUBLIC_CONFIDENCE and
                  p["timestamp_seconds"] <= duration_seconds + .25]
        if not points:
            continue
        strongest = max(points, key=lambda p: (p["confidence"], -p["timestamp_seconds"]))
        observations.append({
            "kind": kind, "timestampSeconds": round(strongest["timestamp_seconds"], 2),
            "confidence": round(strongest["confidence"], 3),
            "equipmentFunctionalityVerified": False,
        })
    return observations


def sanitize_public_facilities(raw: object) -> list[dict]:
    """Whitelist site JSON against untrusted entries and HTML injection."""
    if not isinstance(raw, list):
        return []
    seen = set()
    cleaned = []
    for item in raw[:24]:
        if not isinstance(item, dict):
            continue
        kind, second, confidence = (
            item.get("kind"), item.get("timestampSeconds"), item.get("confidence"),
        )
        if kind not in FACILITIES or kind in seen:
            continue
        if (item.get("equipmentFunctionalityVerified") is not False or
            isinstance(second, bool) or not isinstance(second, (int, float)) or
            not math.isfinite(second) or second < 0 or second > MAX_VIDEO_SECONDS + .25 or
            isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or
            not math.isfinite(confidence) or confidence < MIN_PUBLIC_CONFIDENCE or confidence > 1):
            continue
        seen.add(kind)
        cleaned.append({
            "kind": kind, "timestampSeconds": round(second, 2),
            "confidence": round(confidence, 3),
            "equipmentFunctionalityVerified": False,
        })
    return cleaned
