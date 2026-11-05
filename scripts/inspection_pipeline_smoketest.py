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
except ModuleNotFoundError:
    from inspection_media_verify import verify_mp4
    from inspection_visual_quality import assess_video_quality
    from evaluate_interior_video import DIMENSIONS, create_report, media_sha256
    from compile_interior_visual_estimates import compile_feed
    from build_static_pages import world_page

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
    return {"summary": "Synthetic test only; no VRChat World was visited",
            "dimensions": dims}


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
        report["consent"] = {
            "recordingConsentConfirmed": True,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublishVisualEstimate": True,
        }
        draft = output / (SYNTHETIC_WORLD + "_" + report["evidence"]["sha256"][:16] + ".draft.json")
        draft.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        feed = compile_feed(output, eligible_ids={SYNTHETIC_WORLD})
        scores = feed.get("worlds", [])
        if len(scores) != 1 or scores[0].get("visualScore") != 60:
            raise RuntimeError("Provisional visual scoring failed")
        if scores[0].get("craftsmanshipScore") is not None:
            raise RuntimeError("Provisional video score was mistaken for Craftsmanship")
        world = {
            "id": SYNTHETIC_WORLD, "name": "SYNTHETIC TEST ONLY",
            "author": "Local test fixture", "genres": ["DJ"],
            "totals": {}, "weekly": {}, "editorialStatus": "unreviewed",
        }
        html = world_page(world, [], [], {}, scores[0])
        if ("内部動画の暫定ビジュアル評価" not in html
                or "60/100" not in html
                or "Craftsmanship Rankingの点数・順位には算入しません" not in html
                or "NOT SCORED" not in html):
            raise RuntimeError("Public World detail page failed provisional evidence boundary checks")
        return {
            "status": "passed",
            "capture": "synthetic_H264_MP4",
            "codec": evidence["codec"],
            "durationSeconds": evidence["durationSeconds"],
            "audioTracks": evidence["audioTracks"],
            "videoDigestVerified": True,
            "movingVisualQuality": quality["status"],
            "blankVideoRejected": True,
            "consentedDraftCompiled": True,
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
