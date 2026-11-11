"""Private frame evidence extractor: source and consent checks, no cloud calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts import inspection_facility_keyframes as frames
from scripts.evaluate_interior_video import DIMENSIONS, media_sha256, create_report
from scripts.inspection_facility_inventory import FACILITIES

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def fixture(video: Path, *, rights=True, facility="dj_booth", confidence=.92, timestamp=2.0):
    dims = {
        key: {"status": "unclear", "score": None, "note": "test", "evidence": []}
        for key in DIMENSIONS
    }
    appearances = {
        kind: {
            "visibility": "visible" if kind == facility else "unclear",
            "evidence": (
                [{"timestamp_seconds": timestamp, "confidence": confidence}]
                if kind == facility else []
            ),
        }
        for kind in FACILITIES
    }
    return {
        "schemaVersion": 1, "worldId": WORLD,
        "status": "draft_video_assessment", "rankingEligible": False,
        "evidence": {
            "type": "interior_video", "source": "owner-recorded",
            "sha256": media_sha256(video),
            "durationSeconds": 4.0, "durationSource": "ffprobe",
        },
        "analysis": {
            "summary": "Synthetic analysis", "dimensions": dims,
            "facilities": appearances,
        },
        "visualQuality": {
            "status": "ok", "sampledFrames": 4,
            "visualChangeIntervals": 2, "framesWithDetail": 4,
        },
        "consent": {
            "recordingConsentConfirmed": rights,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublishVisualEstimate": False,
        },
    }


class FrameKeyframeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.video = self.dir / "synthetic.mp4"
        self.video.write_bytes(b"synthetic fixture only" * 150)
        patcher = patch.object(frames, "verify_mp4", return_value={
            "metadataVerified": True, "durationSeconds": 4.0,
            "audioTracks": 0,
        })
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_ffmpeg(self, cmd, **kwargs):
        self.assertIn("-nostdin", cmd)
        self.assertIn("-frames:v", cmd)
        self.assertIn("scale=640:-2", cmd)
        self.assertIn("-n", cmd)
        self.assertTrue(Path(cmd[-1]).name.startswith("dj_booth_"))
        Path(cmd[-1]).write_bytes(b"\xff\xd8" + b"x" * 1024 + b"\xff\xd9")
        return CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    def test_real_direct_cli_draft_is_recovered_offline_with_explicit_rights(self):
        """Matches the direct --analyze --confirm-sharing draft from Windows."""
        original = create_report(
            WORLD, self.video, "owner-recorded",
            fixture(self.video)["analysis"], "gemini-3.5-flash-lite")
        self.assertNotIn("consent", original)
        self.assertNotIn("durationSeconds", original["evidence"])
        quality = {
            "status": "ok", "sampledFrames": 4,
            "visualChangeIntervals": 2, "framesWithDetail": 4,
        }
        with (patch.object(frames.shutil, "which", return_value="/fake/ffmpeg"),
              patch.object(frames, "assess_video_quality", return_value=quality) as quality_check,
              patch.object(frames.subprocess, "run", side_effect=self.fake_ffmpeg)):
            outcome = frames.export_frame_evidence(
                original, self.video, self.dir / "out",
                authorize_direct_draft=True)
        self.assertEqual(outcome["status"], "local-private-unreviewed")
        self.assertEqual(outcome["frameCount"], 1)
        self.assertTrue(Path(outcome["index"]).is_file())
        self.assertNotIn("consent", original, "User's original draft must not be rewritten")
        quality_check.assert_called_once()
        manifest = json.loads((Path(outcome["index"]).parent / "frames.json").read_text())
        self.assertFalse(manifest["publiclyShareable"])
        self.assertFalse(manifest["equipmentFunctionalityVerified"])

    def test_direct_cli_draft_without_explicit_rights_is_rejected(self):
        original = create_report(
            WORLD, self.video, "owner-recorded",
            fixture(self.video)["analysis"], "gemini-3.5-flash-lite")
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No extraction")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "permission"):
                frames.export_frame_evidence(original, self.video, self.dir / "out")
        self.assertFalse((self.dir / "out").exists())

    def test_direct_cli_cannot_override_existing_refusal_of_consent(self):
        original = create_report(
            WORLD, self.video, "owner-recorded",
            fixture(self.video)["analysis"], "gemini-3.5-flash-lite")
        original["consent"] = {"recordingConsentConfirmed": False}
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No extraction")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "permission"):
                frames.export_frame_evidence(
                    original, self.video, self.dir / "out",
                    authorize_direct_draft=True)
        self.assertFalse((self.dir / "out").exists())

    def test_direct_cli_cannot_authorize_mismatched_file_or_untrusted_method(self):
        original = create_report(
            WORLD, self.video, "owner-recorded",
            fixture(self.video)["analysis"], "gemini-3.5-flash-lite")
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No extraction")):
            fake = json.loads(json.dumps(original))
            fake["method"]["kind"] = "untrusted"
            with self.assertRaisesRegex(frames.FrameEvidenceError, "direct video-analysis"):
                frames.export_frame_evidence(
                    fake, self.video, self.dir / "out",
                    authorize_direct_draft=True)
            fake = json.loads(json.dumps(original))
            fake["evidence"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(frames.FrameEvidenceError, "SHA-256"):
                frames.export_frame_evidence(
                    fake, self.video, self.dir / "out",
                    authorize_direct_draft=True)

    def test_direct_cli_unusable_video_stops_without_frames(self):
        original = create_report(
            WORLD, self.video, "owner-recorded",
            fixture(self.video)["analysis"], "gemini-3.5-flash-lite")
        quality = {"status": "poor"}
        with (patch.object(frames, "assess_video_quality", return_value=quality),
              patch.object(frames.subprocess, "run", side_effect=AssertionError("No extraction"))):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "quality"):
                frames.export_frame_evidence(
                    original, self.video, self.dir / "out",
                    authorize_direct_draft=True)
        self.assertFalse((self.dir / "out").exists())

    def test_sighting_creates_local_jpeg_json_and_offline_html(self):
        with (patch.object(frames.shutil, "which", return_value="/usr/bin/ffmpeg"),
              patch.object(frames.subprocess, "run", side_effect=self.fake_ffmpeg) as ffmpeg):
            result = frames.export_frame_evidence(
                fixture(self.video), self.video, self.dir / "private")
        self.assertEqual(result["status"], "local-private-unreviewed")
        self.assertEqual(result["frameCount"], 1)
        self.assertFalse(result["functionalityVerified"])
        page = Path(result["index"])
        self.assertTrue(page.exists())
        html = page.read_text(encoding="utf-8")
        self.assertIn("DJブース", html)
        self.assertIn("確認状態: 未確認", html)
        self.assertIn("noindex", html)
        self.assertNotIn("<script", html)
        self.assertNotIn("http", html)
        self.assertNotIn(str(self.video), html)
        self.assertTrue(next(page.parent.glob("*.jpg")).read_bytes().startswith(b"\xff\xd8"))
        manifest = json.loads((page.parent / "frames.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["mediaSha256"], media_sha256(self.video))
        self.assertEqual(manifest["items"][0]["kind"], "dj_booth")
        self.assertFalse(manifest["items"][0]["equipmentFunctionalityVerified"])
        self.assertFalse(manifest["publiclyShareable"])
        self.assertEqual(ffmpeg.call_count, 1)

    def test_repeated_run_reuses_complete_matching_private_evidence(self):
        with (patch.object(frames.shutil, "which", return_value="/fake/ffmpeg"),
              patch.object(frames.subprocess, "run", side_effect=self.fake_ffmpeg) as encode):
            first = frames.export_frame_evidence(
                fixture(self.video), self.video, self.dir / "private")
            second = frames.export_frame_evidence(
                fixture(self.video), self.video, self.dir / "private")
        self.assertEqual(first["status"], "local-private-unreviewed")
        self.assertEqual(second["status"], "existing-private-evidence")
        self.assertEqual(second["frameCount"], 1)
        self.assertEqual(encode.call_count, 1)

    def test_incomplete_prior_folder_fails_instead_of_overwriting(self):
        prior = self.dir / "private" / f"{WORLD}_{media_sha256(self.video)}"
        prior.mkdir(parents=True)
        (prior / "index.html").write_text("incomplete", encoding="utf-8")
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No overwrites")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "incomplete"):
                frames.export_frame_evidence(
                    fixture(self.video), self.video, self.dir / "private")

    def test_unconsented_video_never_starts_ffmpeg(self):
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No decoding")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "permission"):
                frames.export_frame_evidence(
                    fixture(self.video, rights=False), self.video, self.dir / "out")
        self.assertFalse((self.dir / "out").exists())

    def test_report_must_match_actual_video_hash(self):
        report = fixture(self.video)
        self.video.write_bytes(b"source bytes were replaced" * 150)
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No decoding")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "SHA-256 differs"):
                frames.export_frame_evidence(report, self.video, self.dir / "out")

    def test_facility_after_duration_fails_closed(self):
        report = fixture(self.video, timestamp=9.0)
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No decoding")):
            with self.assertRaisesRegex(ValueError, "beyond"):
                frames.export_frame_evidence(report, self.video, self.dir / "out")

    def test_low_confidence_does_not_export_any_image(self):
        report = fixture(self.video, confidence=.6)
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No decoding")):
            result = frames.export_frame_evidence(report, self.video, self.dir / "out")
        self.assertEqual(result["frameCount"], 0)
        self.assertEqual(result["status"], "no-high-confidence-facilities")
        self.assertFalse((self.dir / "out").exists())

    def test_private_output_in_git_repo_is_refused(self):
        with patch.object(frames.subprocess, "run", side_effect=AssertionError("No decoding")):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "source repository"):
                frames.export_frame_evidence(fixture(self.video), self.video,
                                             frames.ROOT / "data" / "private")

    def test_unexpected_output_from_ffmpeg_never_has_completed_manifest(self):
        with (patch.object(frames.shutil, "which", return_value="/fake/ffmpeg"),
              patch.object(frames.subprocess, "run", return_value=CompletedProcess(
                  [], 1, stdout=b"", stderr=b"error"))):
            with self.assertRaisesRegex(frames.FrameEvidenceError, "failed to extract"):
                frames.export_frame_evidence(fixture(self.video), self.video, self.dir / "out")
        self.assertEqual(list((self.dir / "out").rglob("frames.json")), [])

    def test_draft_must_be_unranked_and_private(self):
        report = fixture(self.video)
        report["rankingEligible"] = True
        with self.assertRaisesRegex(frames.FrameEvidenceError, "unranked"):
            frames.export_frame_evidence(report, self.video, self.dir / "out")


if __name__ == "__main__":
    unittest.main()
