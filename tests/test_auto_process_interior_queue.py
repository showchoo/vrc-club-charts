"""Offline tests for opt-in batch video evaluation; no API requests occur."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import auto_process_interior_queue as queue
from scripts.evaluate_interior_video import DIMENSIONS

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def fake_analysis():
    return {"summary": "Synthetic fixture", "dimensions": {
        key: {"status": "unclear", "score": None, "note": "not observed", "evidence": []}
        for key in DIMENSIONS
    }}


def make_manifest(folder, *, consent=True, publish=False):
    mp4 = folder / "creator-video.mp4"
    mp4.write_bytes(b"fake video, no real users or audio")
    manifest = folder / "input.json"
    manifest.write_text(json.dumps({
        "schemaVersion": 1,
        "videos": [{
            "worldId": WORLD,
            "video": mp4.name,
            "source": "creator-provided",
            "recordingConsentConfirmed": consent,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublish": publish,
        }],
    }), encoding="utf-8")
    return manifest


class QueueTests(unittest.TestCase):
    def setUp(self):
        # Historical fixtures contain fake bytes; FFmpeg integration is tested
        # independently with genuine encoded MP4 files.
        probe = patch.object(queue, "verify_mp4", return_value={
            "metadataVerified": True, "audioTracks": 0, "durationSeconds": 8.0,
        })
        quality = patch.object(queue, "assess_video_quality",
                               return_value={"status": "ok", "reasons": [],
                                             "sampledFrames": 8,
                                             "visualChangeIntervals": 3,
                                             "framesWithDetail": 8})
        probe.start()
        quality.start()
        self.addCleanup(probe.stop)
        self.addCleanup(quality.stop)

    def test_dry_run_without_cloud_key_does_not_contact_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            with patch.object(queue, "ask_gemini", side_effect=AssertionError("network")):
                result = queue.process_queue(manifest, folder / "drafts", max_items=2,
                                             model="gemini-3.5-flash-lite",
                                             allow_upload=False, dry_run=True)
            self.assertEqual(result["pending"], 1)
            self.assertEqual(result["selected"], 1)
            self.assertFalse((folder / "drafts").exists())

    def test_one_analysis_then_no_duplicate_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            out = folder / "private"
            with patch.dict(queue.os.environ, {"GEMINI_API_KEY": "test"}):
                with patch.object(queue, "ask_gemini", side_effect=[fake_analysis()]) as model:
                    result = queue.process_queue(manifest, out, max_items=4,
                                                 model="gemini-3.5-flash-lite", allow_upload=True)
                    self.assertEqual(result["succeeded"], 1)
                    again = queue.process_queue(manifest, out, max_items=4,
                                                model="gemini-3.5-flash-lite", allow_upload=True)
                    self.assertEqual(again["processed"], 0)
                    self.assertEqual(model.call_count, 1)
            files = list(out.glob("*.draft.json"))
            self.assertEqual(len(files), 1)
            data = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertFalse(data["rankingEligible"])
            self.assertFalse(data["consent"]["permissionToPublishVisualEstimate"])
            self.assertNotIn(str(folder), files[0].read_text(encoding="utf-8"))
            self.assertTrue((out / "processing-journal.json").exists())

    def test_cached_video_permission_changes_without_second_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            out = folder / "private"
            with patch.dict(queue.os.environ, {"GEMINI_API_KEY": "test"}):
                with patch.object(queue, "ask_gemini", return_value=fake_analysis()) as model:
                    queue.process_queue(manifest, out, max_items=1,
                        model="gemini-3.5-flash-lite", allow_upload=True)
                    changed = json.loads(manifest.read_text(encoding="utf-8"))
                    changed["videos"][0]["permissionToPublish"] = True
                    manifest.write_text(json.dumps(changed), encoding="utf-8")
                    result = queue.process_queue(manifest, out, max_items=1,
                        model="gemini-3.5-flash-lite", allow_upload=True)
                    self.assertEqual(result["permissionChanges"], 1)
                    self.assertEqual(result["processed"], 0)
                    self.assertEqual(model.call_count, 1)
            saved = json.loads(next(out.glob("*.draft.json")).read_text(encoding="utf-8"))
            self.assertTrue(saved["consent"]["permissionToPublishVisualEstimate"])

    def test_unusable_footage_rejected_once_without_cloud_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            out = folder / "private"
            with (patch.dict(queue.os.environ, {"GEMINI_API_KEY": "test"}),
                  patch.object(queue, "assess_video_quality", return_value={
                      "status": "unusable", "reasons": ["almost_all_frames_black"],
                  }),
                  patch.object(queue, "ask_gemini", side_effect=AssertionError("Do not upload"))):
                first = queue.process_queue(manifest, out, max_items=1,
                    model="gemini-3.5-flash-lite", allow_upload=True)
                second = queue.process_queue(manifest, out, max_items=1,
                    model="gemini-3.5-flash-lite", allow_upload=True)
            self.assertEqual(first["rejected"], 1)
            self.assertEqual(first["failed"], 0)
            self.assertEqual(second["processed"], 0)
            self.assertEqual(list(out.glob("*.draft.json")), [])
            journal = json.loads((out / "processing-journal.json").read_text(encoding="utf-8"))
            self.assertEqual(list(journal["jobs"].values())[0]["status"], "rejected")

    def test_hallucinated_timestamp_rejected_once_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder, publish=True)
            out = folder / "private"
            analysis = fake_analysis()
            analysis["dimensions"]["visual_design"] = {
                "status": "observed", "score": 3, "note": "test only",
                "evidence": [{"timestamp_seconds": 900,
                              "observation": "Impossible moment", "confidence": .99}],
            }
            with (patch.dict(queue.os.environ, {"GEMINI_API_KEY": "test"}),
                  patch.object(queue, "ask_gemini", return_value=analysis) as model):
                first = queue.process_queue(manifest, out, max_items=1,
                                            model="gemini-3.5-flash-lite", allow_upload=True)
                second = queue.process_queue(manifest, out, max_items=1,
                                             model="gemini-3.5-flash-lite", allow_upload=True)
            self.assertEqual(first["rejected"], 1)
            self.assertEqual(first["succeeded"], 0)
            self.assertEqual(first["failed"], 0)
            self.assertEqual(second["processed"], 0)
            self.assertEqual(model.call_count, 1)
            self.assertEqual(list(out.glob("*.draft.json")), [])
            state = json.loads((out / "processing-journal.json").read_text(encoding="utf-8"))
            self.assertEqual(list(state["jobs"].values())[0]["errorType"], "EvidenceTimelineError")

    def test_manifest_rejects_uncleared_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder, consent=False)
            with self.assertRaisesRegex(ValueError, "Recording consent"):
                queue.parse_manifest(manifest)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["videos"][0]["recordingConsentConfirmed"] = True
            data["videos"][0]["video"] = "https://example.com/watch.mp4"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                queue.parse_manifest(manifest)

    def test_live_run_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            with patch.object(queue, "ask_gemini", side_effect=AssertionError("network")):
                with self.assertRaisesRegex(ValueError, "allow-cloud-upload"):
                    queue.process_queue(manifest, folder / "drafts", max_items=2,
                        model="gemini-3.5-flash-lite", allow_upload=False)

    def test_failed_jobs_back_off_and_stop_after_three(self):
        t0 = dt.datetime(2026, 11, 6, tzinfo=dt.timezone.utc)
        job = {"worldId": WORLD}
        self.assertTrue(queue.should_process(job, None, t0))
        failed = {"status": "failed", "attempts": 1, "lastAttempt": t0.isoformat()}
        self.assertFalse(queue.should_process(job, failed, t0 + dt.timedelta(hours=23)))
        self.assertTrue(queue.should_process(job, failed, t0 + dt.timedelta(hours=24)))
        self.assertFalse(queue.should_process(job, {**failed, "attempts": 3},
                                             t0 + dt.timedelta(days=30)))
        self.assertFalse(queue.should_process(job, {"status": "complete"},
                                             t0 + dt.timedelta(days=30)))

    def test_output_inside_repo_and_high_batch_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            with self.assertRaisesRegex(ValueError, "must be 1 to 4"):
                queue.process_queue(manifest, folder, max_items=100,
                                    model="gemini-3.5-flash-lite", allow_upload=False,
                                    dry_run=True)
            with self.assertRaisesRegex(ValueError, "outside the git repository"):
                queue.process_queue(manifest, queue.ROOT / "data", max_items=1,
                                    model="gemini-3.5-flash-lite", allow_upload=False,
                                    dry_run=True)

    def test_failed_provider_call_is_journaled_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = make_manifest(folder)
            with patch.dict(queue.os.environ, {"GEMINI_API_KEY": "sensitive_test_key"}):
                with patch.object(queue, "ask_gemini", side_effect=RuntimeError("sensitive_test_key")):
                    result = queue.process_queue(manifest, folder / "out", max_items=1,
                        model="gemini-3.5-flash-lite", allow_upload=True)
            self.assertEqual(result["failed"], 1)
            content = (folder / "out" / "processing-journal.json").read_text(encoding="utf-8")
            self.assertNotIn("sensitive_test_key", content)
            self.assertIn('"errorType": "RuntimeError"', content)


if __name__ == "__main__":
    unittest.main()
