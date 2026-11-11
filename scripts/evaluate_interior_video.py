#!/usr/bin/env python3
"""Opt-in VRChat interior-video evaluation; NEVER modifies public rankings."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    from scripts.inspection_facility_inventory import MODEL_INSTRUCTIONS, validate_facilities
except ModuleNotFoundError:
    from inspection_facility_inventory import MODEL_INSTRUCTIONS, validate_facilities

WORLD_ID = re.compile(r"^wrld_[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$")
ALLOWED_SUFFIXES = {".mp4", ".mov", ".webm", ".avi", ".mpeg", ".mpg"}
MAX_BYTES = 250 * 1024 * 1024
DIMENSIONS = (
    "visual_design", "lighting_design", "spatial_design", "originality",
    "interactive_gimmicks", "dj_equipment", "live_playback", "audio_quality",
    "performance_optimization",
)
# Video alone is not a performance benchmark or an independent functional test.
UNSCORABLE = {"live_playback", "audio_quality", "performance_optimization", "dj_equipment", "interactive_gimmicks"}
ROOT = Path(__file__).resolve().parents[1]

PROMPT = """You are analyzing a recorded walkthrough of one VRChat world for VRC Club Charts.
Analyze only what can be directly seen/heard in THIS VIDEO, without extrapolating.
It is NOT proof that you have independently visited, operated, or benchmarked the world.
Do NOT claim that a DJ stream, URL player, mixer, buttons or scripts function merely
because they are visible. Do not infer sound quality, real-time FPS, lag or optimization
from a compressed recording. If an interaction is demonstrated on camera, describe the
observable outcome and label it a recorded demonstration, not a live verification.
Omit all user names, avatar identities, conversations, personal data and background music
identification from the output. Evaluate only the world environment, not people.

Return a JSON object with keys: summary (string), dimensions (object), and facilities (object).
Dimensions must have exactly these keys:
visual_design, lighting_design, spatial_design, originality, interactive_gimmicks,
dj_equipment, live_playback, audio_quality, performance_optimization.
Each dimension is an object with keys:
status ('observed', 'not_observed', 'unclear'), score (integer 0..5 or null),
note (short string), evidence (list of up to three {timestamp_seconds: nonnegative
number, observation: string, confidence: number 0..1}).
Scores may be used ONLY for directly visible visual_design, lighting_design,
spatial_design, originality, and ONLY when you provide timestamped evidence.
For all other dimensions score MUST be null. If unsure, status='unclear', score=null.
Do not fabricate video moments or assert validation of unseen equipment.
""" + MODEL_INSTRUCTIONS


def media_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_media(path: Path) -> int:
    if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("A local video file with a supported extension is required")
    size = path.stat().st_size
    if not 0 < size <= MAX_BYTES:
        raise ValueError("Video must be nonempty and at most 250 MiB for this pilot")
    return size


def validate_analysis(value: object) -> dict:
    if not isinstance(value, dict) or not isinstance(value.get("summary"), str):
        raise ValueError("Analysis must be an object with a text summary")
    dims = value.get("dimensions")
    if not isinstance(dims, dict) or set(dims) != set(DIMENSIONS):
        raise ValueError("Analysis must include each required dimension exactly once")
    validated = {}
    for key in DIMENSIONS:
        raw = dims[key]
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid dimension {key}")
        status, score, evidence = raw.get("status"), raw.get("score"), raw.get("evidence")
        note = raw.get("note")
        if status not in {"observed", "not_observed", "unclear"}:
            raise ValueError(f"Invalid status in {key}")
        if not isinstance(note, str) or len(note) > 500:
            raise ValueError(f"Invalid note in {key}")
        if not isinstance(evidence, list) or len(evidence) > 3:
            raise ValueError(f"Invalid evidence count in {key}")
        points = []
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid timestamp evidence in {key}")
            moment, observation, confidence = (
                item.get("timestamp_seconds"), item.get("observation"), item.get("confidence"))
            if (isinstance(moment, bool) or not isinstance(moment, (int, float)) or
                not 0 <= moment <= 36000 or moment != moment):
                raise ValueError(f"Invalid evidence timestamp in {key}")
            if not isinstance(observation, str) or not 1 <= len(observation) <= 300:
                raise ValueError(f"Invalid evidence description in {key}")
            if (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or
                not 0 <= confidence <= 1 or confidence != confidence):
                raise ValueError(f"Invalid evidence confidence in {key}")
            points.append({"timestamp_seconds": moment, "observation": observation,
                           "confidence": confidence})
        if score is not None:
            if (key in UNSCORABLE or status != "observed" or not points or
                isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 5):
                raise ValueError(f"Unsupported score or missing evidence in {key}")
        if status != "observed" and points:
            raise ValueError(f"Unobserved dimension cannot have timestamp evidence: {key}")
        validated[key] = {"status": status, "score": score, "note": note, "evidence": points}
    result = {"summary": value["summary"][:1000], "dimensions": validated}
    if "facilities" in value:
        if value["facilities"] is None:
            raise ValueError("Facilities cannot be null if supplied")
        result["facilities"] = validate_facilities(value["facilities"])
    return result


# A direct video request avoids the separate Files API upload endpoint.
# 12 MiB of raw data becomes ~16 MiB base64, leaving room under the
# documented 20 MB total request guidance for inline generateContent.
MAX_INLINE_VIDEO_BYTES = 12 * 1024 * 1024
VIDEO_MIME_TYPES = {
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".webm": "video/webm", ".avi": "video/avi",
    ".mpeg": "video/mpeg", ".mpg": "video/mpeg",
}


def ask_gemini(video: Path, model: str) -> dict:
    """Analyze a consented video. Inline small clips; use Files API only when needed.

    The source video remains unchanged. Each attempt sends one generation
    request; errors are not automatically retried with another transport.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is required to analyze a video")
    if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]{2,55}", model):
        raise ValueError("Invalid Gemini model name")
    try:
        from google import genai
        from google.genai import types, errors as genai_errors
    except ImportError as exc:
        raise RuntimeError("Install the optional google-genai Python package") from exc

    size = validate_media(video)
    mime = VIDEO_MIME_TYPES[video.suffix.lower()]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    file_ref = None
    phase = "inline-video-request" if size <= MAX_INLINE_VIDEO_BYTES else "file-upload"
    try:
        if size <= MAX_INLINE_VIDEO_BYTES:
            # Google documents inline video as a supported input option for
            # short recordings. Never read unbounded media into memory.
            part = types.Part(inline_data=types.Blob(
                data=video.read_bytes(), mime_type=mime))
        else:
            file_ref = client.files.upload(
                file=str(video), config=types.UploadFileConfig(mime_type=mime))
            phase = "file-processing"
            deadline = time.monotonic() + 180
            while True:
                state = getattr(file_ref.state, "name", str(file_ref.state or ""))
                if state == "ACTIVE":
                    break
                if state == "FAILED":
                    raise RuntimeError("Gemini video preprocessing failed")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Gemini video preprocessing exceeded 180 seconds")
                time.sleep(5)
                file_ref = client.files.get(name=file_ref.name)
            part = file_ref
        phase = "model-request"
        output = client.models.generate_content(
            model=model, contents=[PROMPT, part],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
        )
        if not output.text:
            raise RuntimeError("Gemini returned an empty analysis")
        return validate_analysis(json.loads(output.text))
    except genai_errors.APIError as exc:
        # The raw upstream exception can contain HTML and request identifiers.
        # Do not print it or its chain, and never expose an API key or video.
        code = getattr(exc, "code", None)
        status = str(code) if type(code) is int and 100 <= code <= 599 else "unknown"
        raise RuntimeError(
            f"Gemini {phase} failed (HTTP {status}). "
            "Check API key access, model availability, and proxy/network settings. "
            "No automatic retry or ranking update was performed."
        ) from None
    finally:
        # Best effort; the local video never enters GitHub or the production DB.
        if file_ref is not None and getattr(file_ref, "name", None):
            try:
                client.files.delete(name=file_ref.name)
            except Exception:
                print("WARNING: remote uploaded file could not be deleted automatically", file=sys.stderr)


def create_report(world_id: str, video: Path, source: str, analysis: dict, model: str) -> dict:
    if not WORLD_ID.fullmatch(world_id):
        raise ValueError("Invalid VRChat World ID")
    if source not in {"owner-recorded", "creator-provided"}:
        raise ValueError("Invalid evidence source")
    size = validate_media(video)
    normalized = validate_analysis(analysis)
    return {
        "schemaVersion": 1, "worldId": world_id, "status": "draft_video_assessment",
        "assessedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "evidence": {
            "type": "interior_video", "source": source, "sha256": media_sha256(video),
            "bytes": size, "timestampBasis": "video_seconds_model_estimated",
        },
        "method": {"kind": "gemini_video_analysis", "model": model,
                   "independentInWorldInspection": False},
        "analysis": normalized,
        "rankingEligible": False, "livePlaybackIndependentlyVerified": False,
        "limitations": [
            "Model-proposed timestamps and observations require human verification.",
            "Video alone does not verify live streaming, audio fidelity or optimization.",
            "This report is never added to public rankings automatically.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--world-id", required=True)
    p.add_argument("--video", type=Path, required=True)
    p.add_argument("--source", choices=["owner-recorded", "creator-provided"], required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--analyze", action="store_true", help="Upload local video to Gemini and analyze")
    group.add_argument("--analysis-json", type=Path, help="Validate an existing offline JSON analysis")
    p.add_argument("--confirm-sharing", action="store_true",
                   help="Confirm recording consent/rights and (if --analyze) cloud upload")
    args = p.parse_args(argv)

    try:
        video = args.video.expanduser().resolve(strict=True)
        dest = args.out.expanduser().resolve()
        if dest.is_relative_to(ROOT):
            raise ValueError("Draft assessment must be saved outside the repository")
        if dest.exists():
            raise ValueError("Output already exists; refusing to overwrite")
        if not WORLD_ID.fullmatch(args.world_id):
            raise ValueError("Invalid VRChat World ID")
        validate_media(video)
        if not args.confirm_sharing:
            raise ValueError("Use --confirm-sharing only after checking recording consent and rights")
        analysis = (ask_gemini(video, args.model) if args.analyze
                    else validate_analysis(json.loads(args.analysis_json.read_text(encoding="utf-8"))))
        report = create_report(args.world_id, video, args.source, analysis, args.model)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, RuntimeError, TimeoutError, json.JSONDecodeError) as exc:
        p.exit(2, f"ERROR: {exc}\n")
    print(f"Saved DRAFT assessment to {dest}; no ranking or repository changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
