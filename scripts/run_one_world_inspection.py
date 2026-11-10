#!/usr/bin/env python3
"""One command: manual World entry -> local capture -> optional AI draft -> optional visual preview push.

This does not log in to VRChat, join new Worlds, claim to test DJ playback,
or start the existing public ranking service. It only orchestrates modules
that already require explicit owner consent and local control.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.inspection_preflight import preflight
    from scripts.windows_vrchat_inspector import inspect, MAX_SECONDS, WORLD_ID_RE
    from scripts.auto_process_interior_queue import atomic_json, process_queue, ROOT
    from scripts.evaluate_interior_video import validate_media, media_sha256
    from scripts.publish_interior_visual_previews import release
    from scripts.inspection_media_verify import verify_mp4, MediaVerificationError
    from scripts.inspection_visual_quality import assess_video_quality, VisualQualityError
    from scripts.inspection_evidence_timeline import audit_timeline, EvidenceTimelineError
    from scripts.inspection_facility_keyframes import export_frame_evidence, FrameEvidenceError
except ModuleNotFoundError:
    from inspection_preflight import preflight
    from windows_vrchat_inspector import inspect, MAX_SECONDS, WORLD_ID_RE
    from auto_process_interior_queue import atomic_json, process_queue, ROOT
    from evaluate_interior_video import validate_media, media_sha256
    from publish_interior_visual_previews import release
    from inspection_media_verify import verify_mp4, MediaVerificationError
    from inspection_visual_quality import assess_video_quality, VisualQualityError
    from inspection_evidence_timeline import audit_timeline, EvidenceTimelineError
    from inspection_facility_keyframes import export_frame_evidence, FrameEvidenceError


def run_inspection(*, world_id: str, captures: Path, seconds: int = 60,
                   use_ai_motion: bool = False, analyze_video: bool = False,
                   publish_visual: bool = False, private_confirmed: bool = False,
                   automation_risk_confirmed: bool = False,
                   recording_rights_confirmed: bool = False,
                   gemini_upload_confirmed: bool = False,
                   publishing_rights_confirmed: bool = False,
                   model: str = "gemini-3.5-flash-lite",
                   sweep_motion: bool = False,
                   platform_authorization_confirmed: bool = False) -> dict:
    if use_ai_motion and sweep_motion:
        raise ValueError("Cannot use AI movement and bounded sweep in the same capture")
    if sweep_motion and not platform_authorization_confirmed:
        raise ValueError("A bounded OSC sweep requires explicit platform authorization confirmation")
    if not isinstance(world_id, str) or not WORLD_ID_RE.fullmatch(world_id):
        raise ValueError("Provide the ID of the World already entered manually")
    if not 5 <= seconds <= MAX_SECONDS:
        raise ValueError("Duration must be 5 to 120 seconds")
    if publish_visual and not analyze_video:
        raise ValueError("Publishing requires --analyze-video")
    if (use_ai_motion or analyze_video) and not gemini_upload_confirmed:
        raise ValueError("AI operation requires explicit cloud upload consent")
    if analyze_video and not recording_rights_confirmed:
        raise ValueError("Video analysis requires recording/participant rights confirmation")
    if publish_visual and not publishing_rights_confirmed:
        raise ValueError("Publication requires additional publishing-rights confirmation")
    if (use_ai_motion or sweep_motion) and not automation_risk_confirmed:
        raise ValueError("Automation risk acknowledgement is required")
    if not private_confirmed:
        raise ValueError("The owner must confirm a private, participant-free World instance")

    root = captures.expanduser().resolve()
    if root.is_relative_to(ROOT):
        raise ValueError("Captures must remain outside the source repository")
    checks = preflight(wants_ai=use_ai_motion, wants_video_ai=analyze_video,
                       wants_sweep=sweep_motion)
    if not checks["ready"]:
        missing = [c["check"] for c in checks["checks"] if c["required"] and not c["ok"]]
        raise RuntimeError("Preflight failed (no capture or API requests attempted): " +
                           ", ".join(missing))

    # The user must already have opened the correct World. There is no direct
    # evidence that this manually supplied World ID matches the scene.
    report = inspect(
        world_id=world_id, out_dir=root, seconds=seconds,
        ai=use_ai_motion, evaluate=False,
        confirm_private=private_confirmed,
        accept_risk=automation_risk_confirmed,
        confirm_upload=gemini_upload_confirmed,
        model=model, sweep=sweep_motion,
        platform_authorization_confirmed=platform_authorization_confirmed,
    )
    recording = report.get("recording") or {}
    result = {
        "schemaVersion": 1,
        "worldId": world_id,
        "status": "capture-complete",
        "recording": recording.get("filename"),
        "frames": recording.get("frames", 0),
        "captureStopReason": report.get("stopReason"),
        "rankingsChanged": False,
        "worldEnteredByHuman": True,
        "equipmentFunctionalityVerified": False,
    }

    if sweep_motion and (
        not isinstance(report.get("sweep"), dict)
        or report["sweep"].get("status") != "completed"
    ):
        result["status"] = "capture-incomplete"
        result["detail"] = "Bounded camera sweep stopped or produced incomplete observations; no analysis or publication"
        return result

    if (report.get("error") or recording.get("error") or
        not recording.get("filename") or
        not isinstance(recording.get("frames"), int) or recording["frames"] < 12 or
        recording.get("bytes", 0) <= 0):
        result["status"] = "capture-failed"
        result["detail"] = "Recording failed or was too short; analysis/publishing skipped"
        return result

    video = root / recording["filename"]
    if video.name != recording["filename"]:
        raise ValueError("Invalid recorded video filename")
    validate_media(video)
    try:
        metadata = verify_mp4(video, max_seconds=seconds)
    except MediaVerificationError as exc:
        result["status"] = "capture-invalid"
        result["detail"] = str(exc)
        return result
    result["mediaVerification"] = metadata
    try:
        quality = assess_video_quality(video, metadata=metadata)
        result["visualQuality"] = quality
    except (VisualQualityError, OSError) as exc:
        result["status"] = "capture-unusable"
        result["detail"] = "Visual inspection could not decode usable frames"
        return result
    if quality["status"] != "ok":
        result["status"] = "capture-unusable"
        result["detail"] = "No useful interior survey motion or visible detail"
        return result
    if not analyze_video:
        return result

    private_dir = root / "private-evaluations"
    if private_dir.resolve().is_relative_to(ROOT):
        raise ValueError("Private evaluations must be outside the repository")
    manifest = private_dir / "one-run-consent-manifest.json"
    manifest_data = {
        "schemaVersion": 1,
        "videos": [{
            "worldId": world_id, "video": str(video.resolve()),
            "source": "owner-recorded", "recordingConsentConfirmed": True,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublish": bool(publish_visual),
        }],
    }
    atomic_json(manifest, manifest_data)
    processed = process_queue(manifest, private_dir, max_items=1, model=model,
                              allow_upload=True)
    result["analysis"] = {
        "succeeded": processed.get("succeeded", 0),
        "failed": processed.get("failed", 0),
        "privateDraftFolder": str(private_dir),
    }
    if processed.get("failed", 0):
        result["status"] = "analysis-failed"
        return result
    # A stale draft for another recording of the same World is not proof
    # that THIS newly captured video was analyzed. Validate its exact hash.
    digest = media_sha256(video)
    expected_draft = private_dir / (world_id + "_" + digest[:16] + ".draft.json")
    if not expected_draft.is_file():
        result["status"] = "analysis-not-confirmed"
        return result
    draft = json.loads(expected_draft.read_text(encoding="utf-8"))
    if (draft.get("worldId") != world_id or
        (draft.get("evidence") or {}).get("sha256") != digest or
        draft.get("rankingEligible") is not False):
        result["status"] = "analysis-provenance-mismatch"
        return result
    try:
        result["timelineAudit"] = audit_timeline(draft)
    except (EvidenceTimelineError, ValueError):
        result["status"] = "analysis-provenance-mismatch"
        result["detail"] = "Model timestamps or local visual proof do not match recorded MP4"
        return result
    # Store timestamp-grounded JPEGs locally for the owner's private review.
    # This stage never uploads screenshots or adds any functionality claim.
    try:
        evidence_result = export_frame_evidence(
            draft, video, private_dir / "private-keyframes"
        )
        result["privateFrameEvidence"] = evidence_result
    except (FrameEvidenceError, ValueError, OSError) as exc:
        result["status"] = "private-evidence-extraction-failed"
        result["detail"] = type(exc).__name__
        # Fail closed: an incomplete evidence review must not auto-publish.
        return result
    result["status"] = "private-analysis-complete"
    if publish_visual:
        publication = release(private_dir, publish_and_push=True,
                              copyright_clearance_confirmed=True)
        result["publication"] = publication
        result["rankingsChanged"] = False  # public visual previews are NOT rankings
        result["status"] = "visual-feed-pushed" if publication.get("published") else "visual-feed-unchanged"
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnose", action="store_true",
                        help="Read-only preflight; no VRChat input, capture or API calls")
    parser.add_argument("--world-id", help="Must match the World the owner manually opened")
    parser.add_argument("--seconds", type=int, default=45)
    parser.add_argument("--capture-dir", type=Path,
                        default=Path.home() / "Videos" / "VRCClubCharts")
    parser.add_argument("--model", default="gemini-3.5-flash-lite")
    parser.add_argument("--ai-explore", action="store_true",
                        help="Opt-in Gemini OSC movement; requires platform permission")
    parser.add_argument("--sweep", action="store_true",
                        help="Opt-in stationary locally observed OSC sweep")
    parser.add_argument("--confirm-platform-authorization", action="store_true",
                        help="Operator confirms authorization to automate the official client")
    parser.add_argument("--analyze-video", action="store_true")
    parser.add_argument("--publish-visual", action="store_true",
                        help="Push only separately labeled, provisional video visuals")
    parser.add_argument("--private-instance-confirmed", action="store_true")
    parser.add_argument("--acknowledge-automation-risk", action="store_true")
    parser.add_argument("--confirm-recording-rights", action="store_true")
    parser.add_argument("--confirm-gemini-upload", action="store_true")
    parser.add_argument("--confirm-publishing-rights", action="store_true")
    args = parser.parse_args(argv)

    if args.diagnose:
        report = preflight(wants_ai=args.ai_explore,
                           wants_video_ai=args.analyze_video)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready"] else 1
    try:
        summary = run_inspection(
            world_id=args.world_id, captures=args.capture_dir,
            seconds=args.seconds, use_ai_motion=args.ai_explore,
            analyze_video=args.analyze_video, publish_visual=args.publish_visual,
            private_confirmed=args.private_instance_confirmed,
            automation_risk_confirmed=args.acknowledge_automation_risk,
            recording_rights_confirmed=args.confirm_recording_rights,
            gemini_upload_confirmed=args.confirm_gemini_upload,
            publishing_rights_confirmed=args.confirm_publishing_rights,
            model=args.model,
            sweep_motion=args.sweep,
            platform_authorization_confirmed=args.confirm_platform_authorization,
        )
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] not in {"capture-incomplete", "capture-failed", "capture-invalid", "capture-unusable", "analysis-failed", "analysis-not-confirmed", "analysis-provenance-mismatch", "private-evidence-extraction-failed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
