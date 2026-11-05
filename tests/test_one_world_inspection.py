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
                draft_path.write_text(json.dumps({
                    "worldId": WORLD, "evidence": {"sha256": digest},
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
