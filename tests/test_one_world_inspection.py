"""Mocked integration tests: no VRChat, network, Gemini or Git push."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_one_world_inspection as run
from scripts import inspection_preflight as doctor

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def captured(world: str, root: Path, *, frames: int = 25, failed: bool = False):
    name = world + "_20261106T003000Z.mp4"
    data = b"mock-small-captured-video"
    (root / name).write_bytes(data)
    return {"worldId": world, "stopReason": "completed",
            "recording": {"filename": name, "frames": frames,
                          "bytes": len(data), **({"error": "invalid"} if failed else {})}}


class OneWorldPipelineTests(unittest.TestCase):
    def setUp(self):
        # Historical integration fixtures contain synthetic bytes, not actual
        # H.264. Separate verification behavior is covered by FFprobe unit tests.
        patcher = patch.object(run, "verify_mp4", return_value={
            "codec": "h264", "durationSeconds": 3.25,
            "metadataVerified": True, "audioTracks": 0,
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        quality_patch = patch.object(run, "assess_video_quality", return_value={
            "status": "ok", "sampledFrames": 4, "reasons": [],
        })
        quality_patch.start()
        self.addCleanup(quality_patch.stop)
        frames_patch = patch.object(run, "export_frame_evidence", return_value={
            "status": "no-high-confidence-facilities", "frameCount": 0,
            "functionalityVerified": False,
        })
        frames_patch.start()
        self.addCleanup(frames_patch.stop)

    def common(self, d: str):
        return {"world_id": WORLD, "captures": Path(d), "seconds": 10,
                "private_confirmed": True}

    def test_record_only_does_not_contact_ai_or_github(self):
        with tempfile.TemporaryDirectory() as d:
            def mock_capture(**kwargs):
                self.assertFalse(kwargs["ai"])
                self.assertFalse(kwargs["evaluate"])
                return captured(WORLD, Path(d))
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=mock_capture),
                  patch.object(run, "process_queue", side_effect=AssertionError("AI called")),
                  patch.object(run, "release", side_effect=AssertionError("Git called"))):
                result = run.run_inspection(**self.common(d))
            self.assertEqual(result["status"], "capture-complete")
            self.assertFalse(result["rankingsChanged"])
            self.assertNotIn("analysis", result)

    def test_capture_then_ai_then_explicit_public_preview(self):
        with tempfile.TemporaryDirectory() as d:
            def fake_analysis(manifest, out, **kwargs):
                data = json.loads(manifest.read_text(encoding="utf-8"))
                video = Path(data["videos"][0]["video"])
                digest = run.media_sha256(video)
                draft_path = out / (WORLD + "_" + digest[:16] + ".draft.json")
                from scripts.evaluate_interior_video import DIMENSIONS
                dimensions = {key: {"status": "unclear", "score": None,
                                    "note": "not verified", "evidence": []}
                              for key in DIMENSIONS}
                draft_path.write_text(json.dumps({
                    "worldId": WORLD,
                    "evidence": {"sha256": digest, "durationSeconds": 3.25,
                                 "durationSource": "ffprobe"},
                    "analysis": {"summary": "test only", "dimensions": dimensions},
                    "visualQuality": {"status": "ok", "sampledFrames": 4,
                                      "visualChangeIntervals": 2, "framesWithDetail": 4},
                    "rankingEligible": False,
                }), encoding="utf-8")
                return {"succeeded": 1, "failed": 0}
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", side_effect=fake_analysis) as ai,
                  patch.object(run, "release", return_value={"published": True, "status": "pushed"}) as push):
                result = run.run_inspection(
                    **self.common(d), analyze_video=True, publish_visual=True,
                    recording_rights_confirmed=True, gemini_upload_confirmed=True,
                    publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "visual-feed-pushed")
            self.assertFalse(result["rankingsChanged"])
            manifest = json.loads((Path(d) / "private-evaluations" /
                                   "one-run-consent-manifest.json").read_text())
            self.assertEqual(len(manifest["videos"]), 1)
            self.assertTrue(manifest["videos"][0]["permissionToPublish"])
            self.assertTrue(manifest["videos"][0]["recordingConsentConfirmed"])
            self.assertEqual(ai.call_count, 1)
            self.assertEqual(push.call_count, 1)
            self.assertTrue(push.call_args.kwargs["copyright_clearance_confirmed"])

    def test_no_approval_refuses_without_activating_client(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(run, "inspect", side_effect=AssertionError("client used")):
                with self.assertRaisesRegex(ValueError, "upload consent"):
                    run.run_inspection(**self.common(d), analyze_video=True,
                                       recording_rights_confirmed=True)
                with self.assertRaisesRegex(ValueError, "recording/participant rights"):
                    run.run_inspection(**self.common(d), analyze_video=True,
                                       gemini_upload_confirmed=True)
                with self.assertRaisesRegex(ValueError, "Publishing requires"):
                    run.run_inspection(**self.common(d), publish_visual=True)
                with self.assertRaisesRegex(ValueError, "publishing-rights"):
                    run.run_inspection(**self.common(d), analyze_video=True,
                                       publish_visual=True, recording_rights_confirmed=True,
                                       gemini_upload_confirmed=True)

    def test_preflight_failure_does_not_capture_or_run_ai(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": False,
                   "checks": [{"check": "ffmpeg", "required": True, "ok": False}]}),
                  patch.object(run, "inspect", side_effect=AssertionError("client used"))):
                with self.assertRaisesRegex(RuntimeError, "ffmpeg"):
                    run.run_inspection(**self.common(d))

    def test_missing_local_join_proof_fails_before_recorder(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "corroborate_world", return_value={
                      "status": "unconfirmed", "reason": "join-too-old",
                  }),
                  patch.object(run, "inspect", side_effect=AssertionError("No recording allowed"))):
                result = run.run_inspection(**self.common(d), verify_world_log=True)
            self.assertEqual(result["status"], "world-log-unconfirmed")
            self.assertEqual(result["detail"], "join-too-old")
            self.assertFalse(result["rankingsChanged"])

    def test_log_switch_after_capture_never_uploads_or_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "corroborate_world", side_effect=[
                      {"status": "corroborated", "joinFingerprint": "A"},
                      {"status": "corroborated", "joinFingerprint": "B"},
                  ]) as logs,
                  patch.object(run, "inspect",
                               side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue",
                               side_effect=AssertionError("No Gemini after switch")),
                  patch.object(run, "release",
                               side_effect=AssertionError("No publication after switch"))):
                result = run.run_inspection(
                    **self.common(d), verify_world_log=True, analyze_video=True,
                    publish_visual=True, recording_rights_confirmed=True,
                    gemini_upload_confirmed=True, publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "world-log-changed")
            self.assertEqual(logs.call_count, 2)
            self.assertFalse(result["rankingsChanged"])

    def test_matching_log_before_and_after_capture_records_restricted_proof(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "corroborate_world", return_value={
                      "status": "corroborated", "joinFingerprint": "private-hash",
                  }),
                  patch.object(run, "inspect",
                               side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", side_effect=AssertionError("No AI by default"))):
                result = run.run_inspection(**self.common(d), verify_world_log=True)
            self.assertEqual(result["status"], "capture-complete")
            self.assertTrue(result["worldLogCorroborated"])
            self.assertTrue(result["worldLogDoesNotVerifyParticipantAbsence"])
            self.assertNotIn("private-hash", json.dumps(result))

    def test_early_stop_never_uploads_or_publishes_even_with_video_frames(self):
        for reason in ("user_ctrl_c", "window_unfocused", "navigation_safety_stop", None):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as d:
                report = captured(WORLD, Path(d))
                if reason is None:
                    del report["stopReason"]
                else:
                    report["stopReason"] = reason
                with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                      patch.object(run, "inspect", return_value=report),
                      patch.object(run, "process_queue",
                                   side_effect=AssertionError("No Gemini upload after early stop")),
                      patch.object(run, "release",
                                   side_effect=AssertionError("No site publication after early stop"))):
                    result = run.run_inspection(
                        **self.common(d), analyze_video=True, publish_visual=True,
                        recording_rights_confirmed=True, gemini_upload_confirmed=True,
                        publishing_rights_confirmed=True)
                self.assertEqual(result["status"], "capture-incomplete")
                self.assertFalse(result["rankingsChanged"])

    def test_failed_or_too_short_capture_never_uploads_or_publishes(self):
        for options in ({"frames": 2}, {"failed": True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as d:
                with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                      patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d), **options)),
                      patch.object(run, "process_queue", side_effect=AssertionError("AI called")),
                      patch.object(run, "release", side_effect=AssertionError("Git called"))):
                    result = run.run_inspection(**self.common(d),
                        analyze_video=True, recording_rights_confirmed=True,
                        gemini_upload_confirmed=True)
                self.assertEqual(result["status"], "capture-failed")

    def test_failed_cloud_analysis_never_publishes(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", return_value={"succeeded": 0, "failed": 1}),
                  patch.object(run, "release", side_effect=AssertionError("Git called"))):
                result = run.run_inspection(**self.common(d), analyze_video=True,
                    publish_visual=True, recording_rights_confirmed=True,
                    gemini_upload_confirmed=True, publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "analysis-failed")

    def test_stale_report_for_same_world_cannot_authorize_publication(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "private-evaluations"
            old.mkdir()
            (old / (WORLD + "_old.draft.json")).write_text(
                json.dumps({"worldId": WORLD, "rankingEligible": False}),
                encoding="utf-8",
            )
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", return_value={"succeeded": 0, "failed": 0}),
                  patch.object(run, "release", side_effect=AssertionError("Never publish"))):
                result = run.run_inspection(**self.common(d),
                    analyze_video=True, publish_visual=True,
                    recording_rights_confirmed=True, gemini_upload_confirmed=True,
                    publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "analysis-not-confirmed")

    def test_corrupt_capture_aborts_before_model_upload_or_site_update(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "verify_mp4", side_effect=run.MediaVerificationError("bad MP4")),
                  patch.object(run, "process_queue", side_effect=AssertionError("AI must not run")),
                  patch.object(run, "release", side_effect=AssertionError("Git must not run"))):
                result = run.run_inspection(**self.common(d),
                    analyze_video=True, publish_visual=True,
                    recording_rights_confirmed=True, gemini_upload_confirmed=True,
                    publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "capture-invalid")
            self.assertIn("bad MP4", result["detail"])

    def test_unusable_recording_never_reaches_ai_or_publication(self):
        with tempfile.TemporaryDirectory() as d:
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "assess_video_quality", return_value={
                      "status": "unusable", "reasons": ["almost_all_frames_black"],
                  }),
                  patch.object(run, "process_queue", side_effect=AssertionError("must not upload")),
                  patch.object(run, "release", side_effect=AssertionError("must not publish"))):
                result = run.run_inspection(**self.common(d), analyze_video=True,
                    publish_visual=True, recording_rights_confirmed=True,
                    gemini_upload_confirmed=True, publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "capture-unusable")
            self.assertEqual(result["visualQuality"]["reasons"], ["almost_all_frames_black"])

    def test_fake_timestamp_report_never_reaches_git_publication(self):
        with tempfile.TemporaryDirectory() as d:
            def fake_analysis(manifest, out, **kwargs):
                from scripts.evaluate_interior_video import DIMENSIONS
                info = json.loads(manifest.read_text(encoding="utf-8"))
                digest = run.media_sha256(Path(info["videos"][0]["video"]))
                dimensions = {key: {"status": "unclear", "score": None,
                                    "note": "unknown", "evidence": []}
                              for key in DIMENSIONS}
                dimensions["visual_design"] = {
                    "status": "observed", "score": 5, "note": "fake",
                    "evidence": [{"timestamp_seconds": 50.0,
                                  "observation": "Impossible frame", "confidence": .99}],
                }
                (out / (WORLD + "_" + digest[:16] + ".draft.json")).write_text(
                    json.dumps({"worldId": WORLD, "evidence": {
                        "sha256": digest, "durationSeconds": 3.25,
                        "durationSource": "ffprobe"},
                        "analysis": {"summary": "fake", "dimensions": dimensions},
                        "visualQuality": {"status": "ok", "sampledFrames": 4,
                                          "visualChangeIntervals": 2,
                                          "framesWithDetail": 4},
                        "rankingEligible": False}), encoding="utf-8")
                return {"succeeded": 1, "failed": 0}
            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", side_effect=fake_analysis),
                  patch.object(run, "release", side_effect=AssertionError("Must not publish"))):
                result = run.run_inspection(**self.common(d), analyze_video=True,
                    publish_visual=True, recording_rights_confirmed=True,
                    gemini_upload_confirmed=True, publishing_rights_confirmed=True)
            self.assertEqual(result["status"], "analysis-provenance-mismatch")

    def test_failed_private_frame_extraction_stops_auto_publication(self):
        with tempfile.TemporaryDirectory() as d:
            def fake_analysis(manifest, out, **kwargs):
                from scripts.evaluate_interior_video import DIMENSIONS
                info = json.loads(manifest.read_text(encoding="utf-8"))
                digest = run.media_sha256(Path(info["videos"][0]["video"]))
                dimensions = {
                    key: {"status": "unclear", "score": None,
                          "note": "unknown", "evidence": []}
                    for key in DIMENSIONS
                }
                (out / (WORLD + "_" + digest[:16] + ".draft.json")).write_text(
                    json.dumps({
                        "schemaVersion": 1, "worldId": WORLD,
                        "status": "draft_video_assessment", "rankingEligible": False,
                        "evidence": {"sha256": digest, "durationSeconds": 3.25,
                                     "durationSource": "ffprobe"},
                        "analysis": {"summary": "synthetic", "dimensions": dimensions},
                        "visualQuality": {"status": "ok", "sampledFrames": 4,
                                          "visualChangeIntervals": 2, "framesWithDetail": 4},
                    }), encoding="utf-8")
                return {"succeeded": 1, "failed": 0}

            with (patch.object(run, "preflight", return_value={"ready": True, "checks": []}),
                  patch.object(run, "inspect", side_effect=lambda **kw: captured(WORLD, Path(d))),
                  patch.object(run, "process_queue", side_effect=fake_analysis),
                  patch.object(run, "export_frame_evidence",
                               side_effect=run.FrameEvidenceError("missing frame")),
                  patch.object(run, "release", side_effect=AssertionError("must not publish"))):
                outcome = run.run_inspection(**self.common(d),
                    analyze_video=True, publish_visual=True,
                    recording_rights_confirmed=True, gemini_upload_confirmed=True,
                    publishing_rights_confirmed=True)
            self.assertEqual(outcome["status"], "private-evidence-extraction-failed")
            self.assertFalse(outcome["rankingsChanged"])

    def test_ai_motion_remains_separate_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(run, "inspect", side_effect=AssertionError("client used")):
                with self.assertRaisesRegex(ValueError, "risk acknowledgement"):
                    run.run_inspection(**self.common(d), use_ai_motion=True,
                                       gemini_upload_confirmed=True)

    def test_preflight_is_read_only_and_never_prints_secret(self):
        with (patch.object(doctor.platform, "system", return_value="Linux"),
              patch.object(doctor.shutil, "which", return_value=None),
              patch.object(doctor, "dependency_exists", return_value=False),
              patch.dict(doctor.os.environ, {"GEMINI_API_KEY": "super-secret-test"}, clear=False)):
            report = doctor.preflight(wants_ai=True, wants_video_ai=True)
        self.assertFalse(report["ready"])
        self.assertTrue(report["doesNotAccessVRChatOrCloud"])
        self.assertNotIn("super-secret-test", json.dumps(report))
        self.assertTrue(any(c["check"] == "osc" and not c["required"] for c in report["checks"]))


if __name__ == "__main__":
    unittest.main()
