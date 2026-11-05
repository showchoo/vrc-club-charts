#!/usr/bin/env python3
"""Turn local inspector captures into a consent-gated automatic AI evaluation queue.

No VRChat account, OSC, API, GitHub upload, or public ranking changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.auto_process_interior_queue import atomic_json, process_queue, ROOT
    from scripts.evaluate_interior_video import WORLD_ID, validate_media
except ModuleNotFoundError:
    from auto_process_interior_queue import atomic_json, process_queue, ROOT
    from evaluate_interior_video import WORLD_ID, validate_media


def discover_captures(folder: Path) -> list[dict]:
    if not folder.is_dir():
        raise ValueError("Local capture directory does not exist")
    logs = sorted(folder.glob("*.inspection.json"))
    if len(logs) > 1000:
        raise ValueError("Too many local inspector logs")
    discovered = []
    seen = set()
    for log in logs:
        item = json.loads(log.read_text(encoding="utf-8"))
        if not isinstance(item, dict) or item.get("schemaVersion") != 1:
            continue
        wid = item.get("worldId")
        record = item.get("recording")
        if not isinstance(wid, str) or not WORLD_ID.fullmatch(wid) or not isinstance(record, dict):
            continue
        if item.get("instanceAccess") != "owner_attested_private_no_other_participants":
            continue
        if item.get("stopReason") in {"error", "page_hidden"}:
            continue
        if record.get("audio") is not False or record.get("error"):
            continue
        if not isinstance(record.get("frames"), int) or record["frames"] < 12:
            continue
        filename = record.get("filename")
        if not isinstance(filename, str) or not filename.startswith(wid + "_"):
            continue
        if filename != Path(filename).name or not filename.endswith(".mp4"):
            continue
        video = folder / filename
        if not video.is_file():
            continue
        try:
            validate_media(video)
        except ValueError:
            continue
        if video.name in seen:
            continue
        seen.add(video.name)
        discovered.append({
            "worldId": wid, "video": str(video.resolve()),
            "source": "owner-recorded",
        })
    return discovered


def build_and_process(capture_dir: Path, output_dir: Path, *, dry_run: bool,
                      attest_all: bool, upload_allowed: bool,
                      max_videos: int, model: str) -> dict:
    capture_dir = capture_dir.expanduser().resolve(strict=True)
    output_dir = output_dir.expanduser().resolve()
    if output_dir.is_relative_to(ROOT):
        raise ValueError("Private files must remain outside the repository")
    clips = discover_captures(capture_dir)
    if dry_run:
        return {"status": "dry-run", "eligibleLocalCaptures": len(clips)}
    if not attest_all:
        raise ValueError("Recording/copyright/participant consent must be confirmed")
    if not upload_allowed:
        raise ValueError("Cloud upload must be explicitly authorized")
    manifest = {"schemaVersion": 1, "videos": [
        {**clip, "recordingConsentConfirmed": True,
         "aiAnalysisConsentConfirmed": True,
         "permissionToPublish": False}
        for clip in clips
    ]}
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "private-auto-manifest.json"
    atomic_json(manifest_path, manifest)
    return process_queue(manifest_path, output_dir, max_items=max_videos,
                         model=model, allow_upload=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path,
                        default=Path.home() / "Videos" / "VRCClubCharts")
    parser.add_argument("--out-dir", type=Path,
                        default=Path.home() / "Videos" / "VRCClubCharts" / "private-evaluations")
    parser.add_argument("--max-videos", type=int, default=2)
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--dry-run", action="store_true")
    choice.add_argument("--run", action="store_true")
    parser.add_argument("--attest-recording-rights", action="store_true")
    parser.add_argument("--allow-cloud-upload", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_and_process(
            args.capture_dir, args.out_dir, dry_run=args.dry_run,
            attest_all=args.attest_recording_rights,
            upload_allowed=args.allow_cloud_upload,
            max_videos=args.max_videos, model=args.model,
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("failed") else 0


if __name__ == "__main__":
    raise SystemExit(main())
