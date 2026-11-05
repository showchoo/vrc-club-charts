"""Private calibration workspaces: discovery, idempotence and safe scoring."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import auto_prepare_facility_calibration as workspace
from scripts import calibrate_facility_recognition as cal
from scripts.evaluate_interior_video import DIMENSIONS, media_sha256
from scripts.inspection_facility_inventory import FACILITIES


WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def make_pair(folder: Path, draft_dir: Path, name="one", model="gemini-3.5-flash-lite"):
    video = folder / (name + ".mp4")
    video.write_bytes(("synthetic " + name).encode("utf-8") * 300)
    digest = media_sha256(video)
    dims = {
        k: {"status": "unclear", "score": None, "note": "not observed",
            "evidence": []} for k in DIMENSIONS
    }
    facilities = {
        k: {"visibility": "unclear", "evidence": []}
        for k in FACILITIES
    }
    facilities["dj_booth"] = {
        "visibility": "visible", "evidence": [
            {"timestamp_seconds": 2.0, "confidence": .95},
        ],
    }
    draft = {
        "schemaVersion": 1, "status": "draft_video_assessment",
        "rankingEligible": False, "worldId": WORLD,
        "method": {"kind": "gemini_video_analysis", "model": model,
                   "independentInWorldInspection": False},
        "consent": {"recordingConsentConfirmed": True},
        "evidence": {"type": "interior_video", "source": "owner-recorded",
                     "sha256": digest, "durationSeconds": 4.0,
                     "durationSource": "ffprobe"},
        "visualQuality": {"status": "ok", "sampledFrames": 4,
                          "visualChangeIntervals": 2, "framesWithDetail": 4},
        "analysis": {"summary": "untrusted private text",
                     "dimensions": dims, "facilities": facilities},
    }
    path = draft_dir / (name + ".draft.json")
    path.write_text(json.dumps(draft), encoding="utf-8")
    return video, path, digest


def reviewed_label(label_dir: Path, digest: str, *, world_id=WORLD, complete=True):
    output = label_dir / ("facility-labels-" + digest[:16] + ".json")
    data = {
        "schemaVersion": 1, "worldId": world_id,
        "mediaSha256": digest, "reviewedEntireRecording": complete,
        "scope": "appearance_only_within_this_video_not_entire_vrchat_world",
        "notEquipmentFunctionalityVerification": True,
        "labels": {name: "not_visible" for name in FACILITIES},
    }
    data["labels"]["dj_booth"] = "visible"
    output.write_text(json.dumps(data), encoding="utf-8")
    return output


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.videos = self.base / "videos"
        self.drafts = self.base / "drafts"
        self.labels = self.base / "Downloads"
        self.out = self.base / "private-calibration"
        for path in [self.videos, self.drafts, self.labels]:
            path.mkdir()
        # Synthetic test files lack a real MP4 container. Real synthetic
        # FFmpeg files exercise the real FFprobe check in CI smoke tests.
        self.probe = patch.object(cal, "verify_mp4", return_value={
            "metadataVerified": True, "durationSeconds": 4.0,
            "audioTracks": 0,
        })
        self.probe.start()
        self.addCleanup(self.probe.stop)

    def run_batch(self):
        return workspace.prepare_and_score(
            video_dir=self.videos, draft_dir=self.drafts,
            work_dir=self.out, label_dir=self.labels,
        )

    def test_one_command_generates_local_unreviewed_review_queue(self):
        _, _, digest = make_pair(self.videos, self.drafts)
        result = self.run_batch()
        self.assertEqual(result["status"], "review-queue-ready")
        self.assertEqual(result["newReviewPages"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["reviewed"], 0)
        self.assertEqual(result["metricsByModel"], [])
        self.assertFalse(result["networkUsed"])
        self.assertFalse(result["publicSiteChanged"])
        self.assertFalse(result["equipmentFunctionalityVerified"])
        index = Path(result["reviewIndex"]).read_text(encoding="utf-8")
        self.assertIn("未確認", index)
        self.assertIn(digest[:16], index)
        self.assertIn(".review.html", index)
        self.assertNotIn("untrusted private text", index)
        self.assertEqual(len(list((self.out / "review").glob("*.review.html"))), 1)

    def test_second_run_reuses_review_without_overwrite(self):
        make_pair(self.videos, self.drafts)
        a = self.run_batch()
        review = next((self.out / "review").glob("*.review.html"))
        review.write_text("do not overwrite this private review")
        b = self.run_batch()
        self.assertEqual(a["newReviewPages"], 1)
        self.assertEqual(b["newReviewPages"], 0)
        self.assertEqual(b["reusedReviewPages"], 1)
        self.assertEqual(review.read_text(encoding="utf-8"), "do not overwrite this private review")

    def test_downloaded_review_is_automatically_included_in_metrics(self):
        _, _, digest = make_pair(self.videos, self.drafts)
        self.run_batch()
        reviewed_label(self.labels, digest)
        result = self.run_batch()
        self.assertEqual(result["reviewed"], 1)
        self.assertEqual(result["pending"], 0)
        self.assertEqual(len(result["metricsByModel"]), 1)
        self.assertEqual(result["metricsByModel"][0]["microF1"], 1.0)
        metrics = json.loads(Path(result["metricsByModel"][0]["report"]).read_text())
        self.assertEqual(metrics["reviewedClips"], 1)
        self.assertFalse(metrics["readyForUnattendedDeployment"])
        self.assertFalse(metrics["equipmentFunctionalityVerified"])
        self.assertNotIn("untrusted private text", json.dumps(metrics))
        self.assertIn("確認済み", Path(result["reviewIndex"]).read_text(encoding="utf-8"))

    def test_incomplete_label_is_reported_but_never_scored(self):
        _, _, digest = make_pair(self.videos, self.drafts)
        reviewed_label(self.labels, digest, complete=False)
        result = self.run_batch()
        self.assertEqual(result["reviewed"], 0)
        self.assertEqual(result["invalidLabels"], 1)
        self.assertEqual(result["metricsByModel"], [])
        self.assertIn("ラベル不一致", Path(result["reviewIndex"]).read_text())

    def test_wrong_video_hash_is_skipped_without_generating_synthetic_labels(self):
        v, d, digest = make_pair(self.videos, self.drafts)
        v.write_bytes(b"changed" * 600)
        result = self.run_batch()
        self.assertEqual(result["status"], "no-matching-consented-analysis")
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["ignoredDrafts"], 1)
        self.assertFalse(self.out.exists())

    def test_multiple_model_versions_produce_separate_reports(self):
        _, _, sha1 = make_pair(self.videos, self.drafts, name="one")
        _, _, sha2 = make_pair(self.videos, self.drafts, name="two",
                              model="gemini-other-version")
        reviewed_label(self.labels, sha1)
        reviewed_label(self.labels, sha2)
        result = self.run_batch()
        self.assertEqual(result["reviewed"], 2)
        self.assertEqual(len(result["metricsByModel"]), 2)
        self.assertEqual(len(list(self.out.glob("calibration-metrics-*.json"))), 2)

    def test_private_git_folder_cannot_be_used_for_output(self):
        make_pair(self.videos, self.drafts)
        with self.assertRaisesRegex(cal.FacilityCalibrationError, "outside git"):
            workspace.prepare_and_score(
                video_dir=self.videos, draft_dir=self.drafts,
                work_dir=workspace.ROOT / "data", label_dir=self.labels,
            )
        with self.assertRaisesRegex(cal.FacilityCalibrationError, "outside git"):
            workspace.prepare_and_score(
                video_dir=self.videos, draft_dir=self.drafts,
                work_dir=self.out, label_dir=workspace.ROOT / "data",
            )

    def test_empty_folder_is_not_misreported_as_successful_accuracy_measurement(self):
        result = self.run_batch()
        self.assertEqual(result["status"], "no-matching-consented-analysis")
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["reviewed"], 0) if "reviewed" in result else self.assertEqual(result["ignoredDrafts"], 0)


if __name__ == "__main__":
    unittest.main()
