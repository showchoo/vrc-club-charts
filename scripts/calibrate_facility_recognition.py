#!/usr/bin/env python3
"""PRIVATE calibration of visible DJ facility predictions against labeled videos.

No VRChat client actions, Gemini calls, internet, or publishing. This program
never claims equipment functionality or independently verified DJ streaming.
Metrics measure how well AI appearance labels match operator-reviewed footage;
an empty or synthetic test set is NOT evidence of real-world accuracy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

try:
    from scripts.evaluate_interior_video import media_sha256, validate_media, WORLD_ID
    from scripts.facility_calibration_review_ui import render_review_screen
    from scripts.inspection_evidence_timeline import audit_timeline
    from scripts.inspection_facility_inventory import (
        FACILITIES, MIN_PUBLIC_CONFIDENCE, validate_facilities,
    )
    from scripts.auto_process_interior_queue import atomic_json, ROOT
except ModuleNotFoundError:
    from evaluate_interior_video import media_sha256, validate_media, WORLD_ID
    from facility_calibration_review_ui import render_review_screen
    from inspection_evidence_timeline import audit_timeline
    from inspection_facility_inventory import FACILITIES, MIN_PUBLIC_CONFIDENCE, validate_facilities
    from auto_process_interior_queue import atomic_json, ROOT

MAX_JSON_BYTES = 1024 * 1024
MAX_CLIPS = 200
LABELS = frozenset({"visible", "not_visible", "uncertain", "unreviewed"})
COMPLETE_LABELS = frozenset({"visible", "not_visible", "uncertain"})


class FacilityCalibrationError(ValueError):
    """Invalid private provenance or insufficient review for calibration."""


def private_destination(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_relative_to(ROOT):
        raise FacilityCalibrationError("Private labels/reports must remain outside the repository")
    return resolved


def read_small_json(path: Path) -> dict:
    source = path.expanduser().resolve(strict=True)
    if not source.is_file() or source.stat().st_size > MAX_JSON_BYTES:
        raise FacilityCalibrationError("Invalid or oversized private JSON file")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise FacilityCalibrationError("Expected a JSON object")
    return data


def validate_draft(draft: dict, video: Path) -> tuple[str, str, dict]:
    if (draft.get("schemaVersion") != 1 or
        draft.get("status") != "draft_video_assessment" or
        draft.get("rankingEligible") is not False):
        raise FacilityCalibrationError("Expected a private, unranked video draft")
    evidence = draft.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("type") != "interior_video":
        raise FacilityCalibrationError("Missing private video provenance")
    digest = evidence.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise FacilityCalibrationError("Missing full video SHA-256")
    rights = draft.get("consent")
    if not isinstance(rights, dict) or rights.get("recordingConsentConfirmed") is not True:
        raise FacilityCalibrationError("Owner/participant recording rights not attested")
    video = video.expanduser().resolve(strict=True)
    validate_media(video)
    if media_sha256(video) != digest:
        raise FacilityCalibrationError("Local video hash differs from draft report")
    audit_timeline(draft)
    analysis = draft.get("analysis")
    facilities = validate_facilities(analysis.get("facilities") if isinstance(analysis, dict) else None)
    if facilities is None:
        raise FacilityCalibrationError("Legacy draft has no six-category facility predictions")
    world_id = draft.get("worldId")
    if not isinstance(world_id, str) or not WORLD_ID.fullmatch(world_id):
        raise FacilityCalibrationError("Invalid World ID")
    return world_id, digest, facilities


def create_label_template(draft_path: Path, video_path: Path, out_path: Path) -> dict:
    """No footage uploaded or exported. Template is explicitly NOT a review."""
    draft = read_small_json(draft_path)
    world_id, digest, _ = validate_draft(draft, video_path)
    destination = private_destination(out_path)
    screen_file = destination.with_suffix(".review.html")
    if destination.exists() or screen_file.exists():
        raise FileExistsError("Refusing to overwrite existing human annotation or review screen")
    labels = {
        "schemaVersion": 1, "worldId": world_id, "mediaSha256": digest,
        "reviewedEntireRecording": False,
        "scope": "appearance_only_within_this_video_not_entire_vrchat_world",
        "labels": {name: "unreviewed" for name in FACILITIES},
        "notEquipmentFunctionalityVerification": True,
    }
    # The UI shows the SOURCE VIDEO locally; it cannot certify that anyone
    # actually watched the entire clip. Browser completion is human-attested.
    screen = render_review_screen(template=labels, video=video_path)
    atomic_json(destination, labels)
    screen_file.write_text(screen, encoding="utf-8")
    return {"status": "unreviewed-template-created",
            "categories": len(FACILITIES), "eligibleForMetrics": False,
            "labelFile": str(destination), "reviewHtml": str(screen_file),
            "modelUsed": False, "networkUsed": False}


def _check_label(labels: dict, *, world_id: str, digest: str) -> dict:
    if (labels.get("schemaVersion") != 1 or
        labels.get("worldId") != world_id or labels.get("mediaSha256") != digest or
        labels.get("scope") != "appearance_only_within_this_video_not_entire_vrchat_world" or
        labels.get("notEquipmentFunctionalityVerification") is not True):
        raise FacilityCalibrationError("Labels do not match the source video or scope")
    if labels.get("reviewedEntireRecording") is not True:
        raise FacilityCalibrationError("Full video review must be explicitly confirmed")
    values = labels.get("labels")
    if not isinstance(values, dict) or set(values) != set(FACILITIES):
        raise FacilityCalibrationError("Labels must cover all six facility classes")
    if any(not isinstance(v, str) or v not in COMPLETE_LABELS for v in values.values()):
        raise FacilityCalibrationError("Label all categories or mark uncertain; do not leave unreviewed")
    return values


def _local_entry_path(manifest: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip() or "://" in raw:
        raise FacilityCalibrationError("Only local file paths are supported")
    value = Path(raw).expanduser()
    return (value if value.is_absolute() else manifest.parent / value).resolve(strict=True)


def _score(tp: int, fp: int, fn: int, tn: int) -> dict:
    prec = round(tp / (tp + fp), 4) if tp + fp else None
    recall = round(tp / (tp + fn), 4) if tp + fn else None
    f1 = round(2 * tp / (2 * tp + fp + fn), 4) if 2 * tp + fp + fn else None
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "evaluated": tp + fp + fn + tn,
        "precision": prec, "recall": recall, "f1": f1,
    }


def score_dataset(manifest_path: Path) -> dict:
    """Operator labels must refer to the exact original videos and drafts."""
    manifest_path = manifest_path.expanduser().resolve(strict=True)
    if manifest_path.is_relative_to(ROOT):
        raise FacilityCalibrationError("Private calibration manifest must be outside the repository")
    manifest = read_small_json(manifest_path)
    cases = manifest.get("cases")
    if manifest.get("schemaVersion") != 1 or not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CLIPS:
        raise FacilityCalibrationError("Manifest must contain 1..200 reviewed cases")
    counts = {name: {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "unknown": 0}
              for name in FACILITIES}
    seen = set()
    for item in cases:
        if not isinstance(item, dict) or set(item) != {"draft", "video", "labels"}:
            raise FacilityCalibrationError("Each case requires draft, video and labels local paths")
        draft_path = _local_entry_path(manifest_path, item["draft"])
        video_path = _local_entry_path(manifest_path, item["video"])
        labels_path = _local_entry_path(manifest_path, item["labels"])
        draft = read_small_json(draft_path)
        world_id, digest, predictions = validate_draft(draft, video_path)
        label = _check_label(read_small_json(labels_path), world_id=world_id, digest=digest)
        unique = (world_id, digest)
        if unique in seen:
            raise FacilityCalibrationError("Duplicate video World and hash in dataset")
        seen.add(unique)
        for kind in FACILITIES:
            actual = label[kind]
            if actual == "uncertain":
                counts[kind]["unknown"] += 1
                continue
            visible = predictions[kind]["visibility"] == "visible"
            confident = visible and any(
                point["confidence"] >= MIN_PUBLIC_CONFIDENCE
                for point in predictions[kind]["evidence"]
            )
            # Same threshold as the public provisional visual appearance feed.
            positive = confident
            if actual == "visible":
                counts[kind]["tp" if positive else "fn"] += 1
            else:
                counts[kind]["fp" if positive else "tn"] += 1
    classes = {kind: {**_score(**{name: counts[kind][name] for name in ("tp", "fp", "fn", "tn")}),
                      "unknown": counts[kind]["unknown"]}
               for kind in FACILITIES}
    total = {name: sum(counts[kind][name] for kind in FACILITIES)
             for name in ("tp", "fp", "fn", "tn")}
    micro = _score(**total)
    sufficiently_sampled = len(seen) >= 30 and all(
        classes[k]["tp"] + classes[k]["fn"] >= 10 and
        classes[k]["fp"] + classes[k]["tn"] >= 10
        for k in FACILITIES
    )
    return {
        "schemaVersion": 1, "status": "local-operator-labeled-calibration",
        "threshold": MIN_PUBLIC_CONFIDENCE,
        "reviewedClips": len(seen), "classes": classes,
        "micro": micro, "unknownCategoryReviews": sum(counts[k]["unknown"] for k in FACILITIES),
        "enoughSamplesForPreliminaryReview": sufficiently_sampled,
        "readyForUnattendedDeployment": False,
        "equipmentFunctionalityVerified": False,
        "notes": (
            "Compared against operator labels for the FULL video, not entire Worlds. "
            "An omitted or low-confidence prediction counts as a negative. "
            "Null precision/recall means the denominator is zero. "
            "Operator labels and any synthetic fixtures are not independent ground truth."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("make-template", help="Create unreviewed local annotation template")
    create.add_argument("--draft", type=Path, required=True)
    create.add_argument("--video", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    score = commands.add_parser("score", help="Score operator-labeled full videos")
    score.add_argument("--manifest", type=Path, required=True)
    score.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "make-template":
            result = create_label_template(args.draft, args.video, args.out)
        else:
            target = private_destination(args.out)
            if target.exists():
                raise FileExistsError("Refusing to overwrite existing calibration results")
            result = score_dataset(args.manifest)
            atomic_json(target, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
