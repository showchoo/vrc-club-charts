#!/usr/bin/env python3
"""Consent-gated, idempotent processing of locally provided VRChat interior videos.

This runs after capture; it neither starts VRChat nor automates any VRChat access.
Outputs remain private and never alter the public Craftsmanship Ranking.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    from scripts.evaluate_interior_video import (
        WORLD_ID, ask_gemini, create_report, media_sha256, validate_media,
    )
except ModuleNotFoundError:
    from evaluate_interior_video import (
        WORLD_ID, ask_gemini, create_report, media_sha256, validate_media,
    )

try:
    from scripts.inspection_media_verify import verify_mp4, MediaVerificationError
    from scripts.inspection_visual_quality import assess_video_quality, VisualQualityError
except ModuleNotFoundError:
    from inspection_media_verify import verify_mp4, MediaVerificationError
    from inspection_visual_quality import assess_video_quality, VisualQualityError

ROOT = Path(__file__).resolve().parents[1]
SOURCE_TYPES = frozenset({"creator-provided", "owner-recorded"})
MAX_PER_RUN = 4
FAILURE_RETRY_HOURS = 24
MAX_RETRIES = 3


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_manifest(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("Manifest must be schemaVersion=1 JSON object")
    videos = data.get("videos")
    if not isinstance(videos, list) or len(videos) > 1000:
        raise ValueError("videos must be an array with at most 1000 entries")
    valid = []
    seen = set()
    for index, record in enumerate(videos):
        if not isinstance(record, dict):
            raise ValueError(f"Entry {index} must be an object")
        wid, name, source = (record.get("worldId"), record.get("video"), record.get("source"))
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid):
            raise ValueError(f"Invalid worldId in entry {index}")
        if not isinstance(name, str) or not name.strip() or "://" in name:
            raise ValueError(f"Only local video file paths are supported in entry {index}")
        if source not in SOURCE_TYPES:
            raise ValueError(f"Invalid source in entry {index}")
        if record.get("recordingConsentConfirmed") is not True:
            raise ValueError(f"Recording consent required for entry {index}")
        if record.get("aiAnalysisConsentConfirmed") is not True:
            raise ValueError(f"AI upload consent required for entry {index}")
        path_value = Path(name).expanduser()
        if not path_value.is_absolute():
            path_value = path.parent / path_value
        media = path_value.resolve(strict=True)
        validate_media(media)
        digest = media_sha256(media)
        job_id = wid + ":" + digest
        if job_id in seen:
            raise ValueError("Duplicate world/video in manifest: " + wid)
        seen.add(job_id)
        valid.append({
            "worldId": wid, "video": media, "source": source, "sha256": digest,
            "jobId": job_id,
            "permissionToPublish": record.get("permissionToPublish") is True,
        })
    return valid


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".tmp", prefix=".vcc-",
            dir=path.parent, delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"schemaVersion": 1, "jobs": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("schemaVersion") != 1 or not isinstance(state.get("jobs"), dict):
        raise ValueError("Invalid processing journal")
    return state


def should_process(job: dict, history: dict | None, now: dt.datetime) -> bool:
    if not history:
        return True
    if history.get("status") in {"complete", "rejected"}:
        # Different video bytes always create a different jobId.
        return False
    attempts = history.get("attempts", 0)
    if not isinstance(attempts, int) or attempts >= MAX_RETRIES:
        return False
    last = history.get("lastAttempt")
    if not isinstance(last, str):
        return False
    try:
        since = dt.datetime.fromisoformat(last)
        if since.tzinfo is None:
            return False
    except ValueError:
        return False
    return now - since >= dt.timedelta(hours=FAILURE_RETRY_HOURS)


def process_queue(manifest: Path, output: Path, *, max_items: int, model: str,
                  allow_upload: bool, dry_run: bool = False) -> dict:
    if not 1 <= max_items <= MAX_PER_RUN:
        raise ValueError("max_items must be 1 to 4")
    if not re.fullmatch(r"gemini-[A-Za-z0-9.-]{2,60}", model):
        raise ValueError("Invalid Gemini model name")
    manifest = manifest.expanduser().resolve(strict=True)
    output = output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Private videos and results must be stored outside the git repository")
    entries = parse_manifest(manifest)
    journal_path = output / "processing-journal.json"
    state = load_state(journal_path)
    timestamp = now_utc()
    pending = [
        job for job in entries
        if should_process(job, state["jobs"].get(job["jobId"]), timestamp)
    ]
    selected = pending[:max_items]
    if dry_run:
        return {
            "status": "dry-run", "manifestVideos": len(entries),
            "pending": len(pending), "selected": len(selected),
            "alreadyDoneOrCoolingDown": len(entries) - len(pending),
        }
    if not allow_upload:
        raise ValueError("--allow-cloud-upload is required for real AI processing")
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY must be set locally")
    output.mkdir(parents=True, exist_ok=True)
    # Owner may grant or revoke public numeric-score permission later. Never
    # reupload the footage merely to edit that consent flag.
    permission_edits = 0
    for job in entries:
        prior = state["jobs"].get(job["jobId"], {})
        if prior.get("status") != "complete":
            continue
        filename = prior.get("resultFile")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("Unsafe cached draft path")
        draft_file = output / filename
        if not draft_file.is_file():
            continue
        draft = json.loads(draft_file.read_text(encoding="utf-8"))
        if draft.get("worldId") != job["worldId"] or draft.get("evidence", {}).get("sha256") != job["sha256"]:
            raise ValueError("Stored video report provenance mismatch")
        consent = draft.get("consent", {})
        if consent.get("permissionToPublishVisualEstimate") != job["permissionToPublish"]:
            consent["permissionToPublishVisualEstimate"] = job["permissionToPublish"]
            draft["consent"] = consent
            atomic_json(draft_file, draft)
            permission_edits += 1
    succeeded, failed, rejected = 0, 0, 0
    for job in selected:
        prior = state["jobs"].get(job["jobId"], {})
        attempts = prior.get("attempts", 0) + 1
        entry = {
            "worldId": job["worldId"], "videoSha256": job["sha256"],
            "status": "failed", "attempts": attempts,
            "lastAttempt": now_utc().isoformat(), "source": job["source"],
        }
        try:
            # Only actual viable, decoded interior footage may reach Gemini.
            # This check runs AFTER user consent but BEFORE any API upload.
            metadata = verify_mp4(job["video"])
            quality = assess_video_quality(job["video"], metadata=metadata)
            if quality["status"] != "ok":
                entry.update(status="rejected", errorType="InsufficientVisualCoverage",
                             visualQuality=quality)
                rejected += 1
                state["jobs"][job["jobId"]] = entry
                atomic_json(journal_path, state)
                continue
            # No external URLs. Provider upload is within the explicit opt-in.
            result = ask_gemini(job["video"], model)
            report = create_report(job["worldId"], job["video"],
                                   job["source"], result, model)
            report["visualQuality"] = quality
            report["consent"] = {
                "recordingConsentConfirmed": True,
                "aiAnalysisConsentConfirmed": True,
                "permissionToPublishVisualEstimate": job["permissionToPublish"],
            }
            destination = output / (job["worldId"] + "_" + job["sha256"][:16] + ".draft.json")
            if destination.exists():
                raise FileExistsError("Draft already exists; refusing to overwrite")
            atomic_json(destination, report)
            entry.update(status="complete", resultFile=destination.name)
            succeeded += 1
        except Exception as exc:
            # Record the type, never secrets, raw model output or personal footage.
            entry["errorType"] = type(exc).__name__
            failed += 1
        state["jobs"][job["jobId"]] = entry
        atomic_json(journal_path, state)
    return {"status": "complete", "permissionChanges": permission_edits,
            "manifestVideos": len(entries),
            "pendingAtStart": len(pending), "processed": len(selected),
            "succeeded": succeeded, "failed": failed, "rejected": rejected,
            "remaining": len(pending) - len(selected),
            "journal": str(journal_path)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out-dir", type=Path,
                   default=Path.home() / "Videos" / "VRCClubCharts" / "private-evaluations")
    p.add_argument("--max-videos", type=int, default=2)
    p.add_argument("--model", default="gemini-3.5-flash-lite")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--run", action="store_true")
    p.add_argument("--allow-cloud-upload", action="store_true")
    args = p.parse_args(argv)
    try:
        summary = process_queue(args.manifest, args.out_dir,
                                max_items=args.max_videos, model=args.model,
                                allow_upload=args.allow_cloud_upload,
                                dry_run=args.dry_run)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        p.exit(2, "ERROR: " + str(exc) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary.get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
