#!/usr/bin/env python3
"""Offline end-to-end check using a REAL synthetic MP4 (no VRChat, network or AI).

Verifies H.264 creation -> FFprobe metadata -> content SHA-256 -> private
draft schema -> consent-gated visual estimate -> clearly labeled World page.
Everything is kept in a disposable temporary folder and deleted afterward.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from scripts.inspection_media_verify import verify_mp4
    from scripts.inspection_visual_quality import assess_video_quality
    from scripts.evaluate_interior_video import DIMENSIONS, create_report, media_sha256
    from scripts.compile_interior_visual_estimates import compile_feed
    from scripts.build_static_pages import world_page
    from scripts.inspection_evidence_timeline import attach_verified_timeline
    from scripts.inspection_facility_inventory import FACILITIES
    from scripts.inspection_facility_keyframes import export_frame_evidence
    from scripts.calibrate_facility_recognition import create_label_template, score_dataset
    from scripts.auto_prepare_facility_calibration import prepare_and_score
    from scripts.dj_audio_playback_test import make_clip as make_dj_audio_clip, verify as verify_dj_audio
except ModuleNotFoundError:
    from inspection_media_verify import verify_mp4
    from inspection_visual_quality import assess_video_quality
    from evaluate_interior_video import DIMENSIONS, create_report, media_sha256
    from compile_interior_visual_estimates import compile_feed
    from build_static_pages import world_page
    from inspection_evidence_timeline import attach_verified_timeline
    from inspection_facility_inventory import FACILITIES
    from inspection_facility_keyframes import export_frame_evidence
    from calibrate_facility_recognition import create_label_template, score_dataset
    from auto_prepare_facility_calibration import prepare_and_score
    from dj_audio_playback_test import make_clip as make_dj_audio_clip, verify as verify_dj_audio

SYNTHETIC_WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"
VISIBLE = ("visual_design", "lighting_design", "spatial_design", "originality")


def synthetic_analysis() -> dict:
    """Fixed fixture, NOT an AI assessment of any VRChat World."""
    dims = {name: {"status": "unclear", "score": None,
                   "note": "Not demonstrated", "evidence": []}
            for name in DIMENSIONS}
    for name in VISIBLE:
        dims[name] = {
            "status": "observed", "score": 3, "note": "Synthetic test pattern",
            "evidence": [{"timestamp_seconds": 1.0,
                          "observation": "Synthetic video color-pattern frame",
                          "confidence": 0.95}],
        }
    # Fixed simulated category sightings. The synthetic MP4 does not contain
    # any actual DJ booth, so this is ONLY an output-schema integration test.
    equipment = {
        name: {
            "visibility": "visible" if name == "dj_booth" else "unclear",
            "evidence": (
                [{"timestamp_seconds": 1.0, "confidence": 0.94}]
                if name == "dj_booth" else []
            ),
        }
        for name in FACILITIES
    }
    return {"summary": "Synthetic test only; no VRChat World was visited",
            "dimensions": dims, "facilities": equipment}


def smoke_test() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg not available")
    if not shutil.which("ffprobe"):
        raise RuntimeError("FFprobe not available")
    with tempfile.TemporaryDirectory(prefix="vcc-real-mp4-smoke-") as temp:
        directory = Path(temp)
        clip = directory / "synthetic.mp4"
        output = directory / "private-drafts"
        output.mkdir()
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "testsrc2=duration=4:size=640x360:rate=4",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(clip),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=25)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Could not generate a synthetic H.264 clip") from exc
        evidence = verify_mp4(clip, max_seconds=10)
        if evidence["audioTracks"] != 0 or evidence["durationSeconds"] < 3:
            raise RuntimeError("Synthetic video integrity verification failed")
        quality = assess_video_quality(clip, metadata=evidence)
        if quality["status"] != "ok" or quality["visualChangeIntervals"] < 2:
            raise RuntimeError("Moving test footage was incorrectly rejected by quality gate")
        # A different, genuine MP4 that is entirely black must be rejected
        # before it could ever reach Gemini.
        blank = directory / "synthetic-blank.mp4"
        black_cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=640x360:r=4:d=4",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "27",
            "-pix_fmt", "yuv420p", str(blank),
        ]
        try:
            subprocess.run(black_cmd, check=True, capture_output=True, timeout=25)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Could not generate black negative test video") from exc
        black_meta = verify_mp4(blank, max_seconds=10)
        black_quality = assess_video_quality(blank, metadata=black_meta)
        if black_quality["status"] != "unusable" or (
            "almost_all_frames_black" not in black_quality["reasons"]
        ):
            raise RuntimeError("Black video incorrectly accepted as an interior inspection")
        report = create_report(
            SYNTHETIC_WORLD, clip, "creator-provided",
            synthetic_analysis(), "gemini-3.5-flash-lite",
        )
        if report["evidence"]["sha256"] != media_sha256(clip):
            raise RuntimeError("Video digest mismatch")
        report = attach_verified_timeline(report, metadata=evidence,
                                         visual_quality=quality)
        report["consent"] = {
            "recordingConsentConfirmed": True,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublishVisualEstimate": True,
        }
        extracted = export_frame_evidence(report, clip, directory / "private-keyframes")
        if extracted["status"] != "local-private-unreviewed" or extracted["frameCount"] != 1:
            raise RuntimeError("Synthetic facility keyframe extraction failed")
        index_path = Path(extracted["index"])
        private_report = json.loads((index_path.parent / "frames.json").read_text(encoding="utf-8"))
        candidates = list(index_path.parent.glob("*.jpg"))
        if (len(candidates) != 1 or not candidates[0].read_bytes().startswith(bytes.fromhex("ffd8"))
                or private_report["mediaSha256"] != media_sha256(clip)
                or private_report["publiclyShareable"] is not False
                or private_report["equipmentFunctionalityVerified"] is not False):
            raise RuntimeError("Private keyframe or evidence provenance invalid")
        if ("未確認" not in index_path.read_text(encoding="utf-8")
                or "DJブース" not in index_path.read_text(encoding="utf-8")):
            raise RuntimeError("Private offline evidence index missing required disclaimer")
        draft = output / (SYNTHETIC_WORLD + "_" + report["evidence"]["sha256"][:16] + ".draft.json")
        draft.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        # Test the FULL local review/metrics chain using SYNTHETIC assumptions:
        # the test video contains no DJ booth, and these labels are synthetic
        # fixtures only, not real annotations or an AI accuracy claim.
        annotations = output / "synthetic-calibration-template.json"
        template_result = create_label_template(draft, clip, annotations)
        if not Path(template_result["reviewHtml"]).is_file():
            raise RuntimeError("Offline local annotation page was not created")
        ground_truth = json.loads(annotations.read_text(encoding="utf-8"))
        ground_truth["reviewedEntireRecording"] = True  # test-only simulation
        ground_truth["labels"] = {
            name: "not_visible" for name in FACILITIES
        }
        ground_truth["labels"]["dj_booth"] = "visible"  # synthetic assumption
        completed = output / "synthetic-calibration-completed.json"
        completed.write_text(json.dumps(ground_truth), encoding="utf-8")
        calibration_manifest = output / "synthetic-calibration-manifest.json"
        calibration_manifest.write_text(json.dumps({
            "schemaVersion": 1, "cases": [{
                "draft": str(draft), "video": str(clip),
                "labels": str(completed),
            }],
        }), encoding="utf-8")
        synthetic_metrics = score_dataset(calibration_manifest)
        if (synthetic_metrics["reviewedClips"] != 1
                or synthetic_metrics["micro"]["tp"] != 1
                or synthetic_metrics["readyForUnattendedDeployment"] is not False
                or synthetic_metrics["equipmentFunctionalityVerified"] is not False):
            raise RuntimeError("Synthetic calibration dataset validation failed")
        # End-to-end private workspace: discover the exact video and draft,
        # produce local review HTML, then detect completed downloaded labels.
        downloaded = directory / "Downloads"
        downloaded.mkdir()
        workspace = directory / "private-workspace"
        empty = prepare_and_score(
            video_dir=directory, draft_dir=output,
            work_dir=workspace, label_dir=downloaded,
        )
        if (empty["status"] != "review-queue-ready"
                or empty["pending"] != 1 or empty["reviewed"] != 0
                or empty["newReviewPages"] != 1):
            raise RuntimeError("Private batch review discovery failed")
        completed_download = downloaded / ("facility-labels-" + report["evidence"]["sha256"][:16] + ".json")
        completed_download.write_text(json.dumps(ground_truth), encoding="utf-8")
        reviewed = prepare_and_score(
            video_dir=directory, draft_dir=output,
            work_dir=workspace, label_dir=downloaded,
        )
        if (reviewed["reviewed"] != 1 or reviewed["pending"] != 0
                or reviewed["reusedReviewPages"] != 1
                or len(reviewed["metricsByModel"]) != 1
                or reviewed["metricsByModel"][0]["microF1"] != 1.0):
            raise RuntimeError("Private batch automatic calibration scoring failed")
        feed = compile_feed(output, eligible_ids={SYNTHETIC_WORLD})
        scores = feed.get("worlds", [])
        if len(scores) != 1 or scores[0].get("visualScore") != 60:
            raise RuntimeError("Provisional visual scoring failed")
        if scores[0].get("craftsmanshipScore") is not None:
            raise RuntimeError("Provisional video score was mistaken for Craftsmanship")
        facilities = scores[0].get("facilityObservations", [])
        if (len(facilities) != 1 or facilities[0].get("kind") != "dj_booth"
                or facilities[0].get("equipmentFunctionalityVerified") is not False):
            raise RuntimeError("DJ equipment appearance incorrectly serialized")
        world = {
            "id": SYNTHETIC_WORLD, "name": "SYNTHETIC TEST ONLY",
            "author": "Local test fixture", "genres": ["DJ"],
            "totals": {}, "weekly": {}, "editorialStatus": "unreviewed",
        }
        html = world_page(world, [], [], {}, scores[0])
        if ("内部動画の暫定ビジュアル評価" not in html
                or "60/100" not in html
                or "Craftsmanship Rankingの点数・順位には算入しません" not in html
                or "NOT SCORED" not in html
                or "映像で見えた設備（AI推定）" not in html
                or "DJブース" not in html
                or "DJ配信・動画再生・操作・音響などの機能は確認していません" not in html):
            raise RuntimeError("Public World detail page failed provisional evidence boundary checks")
        # A wholly synthetic audio end-to-end test: original licensed clip,
        # independently reencoded audio, and local analysis. This is NOT
        # evidence of VRChat playback; a human-supplied isolated test recording
        # is still required for real-world corroboration.
        tone_source = directory / "synthetic-dj-original.mp4"
        generated = make_dj_audio_clip(tone_source)
        if not generated["audioTestSequenceConfirmed"]:
            raise RuntimeError("Original DJ audio test sequence was not generated")
        separate_capture = directory / "synthetic-dj-reencoded.mp4"
        transcode = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(tone_source), "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            str(separate_capture),
        ]
        try:
            subprocess.run(transcode, check=True, capture_output=True, timeout=25)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError("Unable to build separate audio test recording") from exc
        audio_check = verify_dj_audio(
            original=tone_source, recording=separate_capture,
            out=directory / "synthetic-dj-audio-check.json",
            recording_rights_confirmed=True,
        )
        if audio_check["status"] != "test_audio_sequence_detected":
            raise RuntimeError("Synthetic test audio pattern was not detected")
        audio_private = json.loads(Path(audio_check["report"]).read_text(encoding="utf-8"))
        if (audio_private["equipmentFunctionalityVerified"] is not False
                or audio_private["actualSpeakerOrHeadsetOutputVerified"] is not False
                or audio_private["liveDjStreamVerified"] is not False):
            raise RuntimeError("Synthetic audio wrongly presented as verified VRChat playback")
        return {
            "status": "passed",
            "capture": "synthetic_H264_MP4",
            "codec": evidence["codec"],
            "durationSeconds": evidence["durationSeconds"],
            "audioTracks": evidence["audioTracks"],
            "videoDigestVerified": True,
            "evidenceTimelineAudited": report["timelineAudit"]["timelineChecked"],
            "movingVisualQuality": quality["status"],
            "blankVideoRejected": True,
            "consentedDraftCompiled": True,
            "syntheticFacilitySchemaVerified": True,
            "privateKeyframeJpegVerified": True,
            "privateEvidenceHtmlVerified": True,
            "syntheticCalibrationMetricsVerified": True,
            "privateCalibrationWorkspaceVerified": True,
            "realWorldAccuracyMeasured": False,
            "syntheticDjAudioPatternDetected": True,
            "realVrchatAudioPlaybackMeasured": False,
            "equipmentFunctionalityVerified": False,
            "siteVisualPreviewRendered": True,
            "previewVisualScore": scores[0]["visualScore"],
            "publishedCraftsmanshipScore": False,
            "touchedVRChat": False,
            "usedGemini": False,
            "usedNetwork": False,
            "temporaryDataRemoved": True,
        }


if __name__ == "__main__":
    try:
        print(json.dumps(smoke_test(), ensure_ascii=False, indent=2))
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit("ERROR: offline smoke test failed: " + str(exc)) from exc
