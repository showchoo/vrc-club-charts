"""Quantitative facility-detection review is entirely local and never publishes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import calibrate_facility_recognition as calibration
from scripts.evaluate_interior_video import DIMENSIONS, media_sha256
from scripts.inspection_facility_inventory import FACILITIES


def make_case(folder: Path, *, video_name="test.mp4"):
    video = folder / video_name
    video.write_bytes((b"fake synthetic non-person video" + video_name.encode()) * 100)
    sha = media_sha256(video)
    facilities = {
        kind: {"visibility": "unclear", "evidence": []}
        for kind in FACILITIES
    }
    for kind, confidence in [
        ("dj_booth", .95), ("dj_decks", .90), ("interactive_control", .70),
    ]:
        facilities[kind] = {
            "visibility": "visible",
            "evidence": [{"timestamp_seconds": 2.0, "confidence": confidence}],
        }
    dims = {
        kind: {"status": "unclear", "score": None, "note": "synthetic", "evidence": []}
        for kind in DIMENSIONS
    }
    report = {
        "schemaVersion": 1, "worldId": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05",
        "status": "draft_video_assessment", "rankingEligible": False,
        "evidence": {
            "type": "interior_video", "sha256": sha,
            "source": "owner-recorded", "durationSource": "ffprobe",
            "durationSeconds": 5.0,
        },
        "consent": {"recordingConsentConfirmed": True,
                    "aiAnalysisConsentConfirmed": True,
                    "permissionToPublishVisualEstimate": False},
        "analysis": {"summary": "private text must stay private",
                     "dimensions": dims, "facilities": facilities},
        "visualQuality": {
            "status": "ok", "sampledFrames": 5,
            "visualChangeIntervals": 3, "framesWithDetail": 5,
        },
    }
    draft = folder / (video_name + ".draft.json")
    draft.write_text(json.dumps(report), encoding="utf-8")
    labels = {
        "schemaVersion": 1, "worldId": report["worldId"],
        "mediaSha256": sha, "reviewedEntireRecording": True,
        "scope": "appearance_only_within_this_video_not_entire_vrchat_world",
        "labels": {
            "dj_booth": "visible", "dj_decks": "not_visible",
            "video_screen": "visible", "lighting_rig": "not_visible",
            "stage": "uncertain", "interactive_control": "visible",
        },
        "notEquipmentFunctionalityVerification": True,
    }
    label_file = folder / (video_name + ".labels.json")
    label_file.write_text(json.dumps(labels), encoding="utf-8")
    return video, draft, label_file


def manifest(folder: Path, cases: list[tuple[Path, Path, Path]]) -> Path:
    p = folder / "calibration.json"
    p.write_text(json.dumps({"schemaVersion": 1, "cases": [
        {"video": v.name, "draft": d.name, "labels": l.name}
        for v, d, l in cases
    ]}), encoding="utf-8")
    return p


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        # Fixtures contain synthetic bytes. FFprobe is tested separately
        # against real MP4 in the project's integration smoke test.
        probe = patch.object(calibration, "verify_mp4", return_value={
            "metadataVerified": True, "durationSeconds": 5.0, "audioTracks": 0,
        })
        probe.start()
        self.addCleanup(probe.stop)

    def test_make_template_requires_actual_matching_video_and_stays_unreviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video, draft, labels = make_case(folder)
            target = folder / "generated-labels.json"
            with patch.object(calibration, "score_dataset", side_effect=AssertionError("No scores")):
                outcome = calibration.create_label_template(draft, video, target)
            self.assertEqual(outcome["status"], "unreviewed-template-created")
            stored = json.loads(target.read_text(encoding="utf-8"))
            self.assertFalse(stored["reviewedEntireRecording"])
            self.assertEqual(set(stored["labels"]), set(FACILITIES))
            self.assertEqual(set(stored["labels"].values()), {"unreviewed"})
            self.assertFalse(outcome["eligibleForMetrics"])
            review = Path(outcome["reviewHtml"])
            self.assertTrue(review.is_file())
            source = review.read_text(encoding="utf-8")
            self.assertIn("DJ設備の認識精度を確認", source)
            self.assertIn(video.as_uri(), source)
            self.assertIn('connect-src &#39;none&#39;', source.replace("'", "&#39;"))
            self.assertIn("URL.createObjectURL", source)
            self.assertNotIn("https://", source)
            self.assertNotIn("http://", source)
            self.assertNotIn("private text must stay private", source)
            with self.assertRaises(FileExistsError):
                calibration.create_label_template(draft, video, target)

    def test_known_confusion_matrix_and_undefined_class_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            paths = make_case(folder)
            outcome = calibration.score_dataset(manifest(folder, [paths]))
        classes = outcome["classes"]
        self.assertEqual(outcome["reviewedClips"], 1)
        self.assertEqual(classes["dj_booth"]["tp"], 1)
        self.assertEqual(classes["dj_decks"]["fp"], 1)
        self.assertEqual(classes["video_screen"]["fn"], 1)
        self.assertEqual(classes["lighting_rig"]["tn"], 1)
        self.assertEqual(classes["interactive_control"]["fn"], 1)
        self.assertEqual(classes["stage"]["unknown"], 1)
        self.assertIsNone(classes["stage"]["precision"])
        self.assertEqual(outcome["micro"]["precision"], .5)
        self.assertEqual(outcome["micro"]["recall"], .3333)
        self.assertEqual(outcome["micro"]["f1"], .4)
        self.assertFalse(outcome["enoughSamplesForPreliminaryReview"])
        self.assertFalse(outcome["readyForUnattendedDeployment"])
        self.assertFalse(outcome["equipmentFunctionalityVerified"])
        self.assertNotIn("private text must stay private", json.dumps(outcome))

    def test_refuse_unreviewed_or_incomplete_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video, draft, label_file = make_case(folder)
            m = manifest(folder, [(video, draft, label_file)])
            for edit in [
                lambda x: x.update(reviewedEntireRecording=False),
                lambda x: x["labels"].update(dj_booth="unreviewed"),
                lambda x: x["labels"].pop("dj_decks"),
                lambda x: x.update(notEquipmentFunctionalityVerification=False),
                lambda x: x.update(mediaSha256="a"*64),
            ]:
                fresh = json.loads(label_file.read_text(encoding="utf-8"))
                edit(fresh)
                label_file.write_text(json.dumps(fresh), encoding="utf-8")
                with self.assertRaises(calibration.FacilityCalibrationError):
                    calibration.score_dataset(m)
                # Restore clean state for the next corruption case.
                _, _, backup = make_case(folder)
                self.assertEqual(backup, label_file)

    def test_source_video_replacement_does_not_calibrate_against_stale_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video, draft, labels = make_case(folder)
            video.write_bytes(b"replacement video" * 300)
            with self.assertRaisesRegex(calibration.FacilityCalibrationError, "hash"):
                calibration.score_dataset(manifest(folder, [(video, draft, labels)]))

    def test_duplicate_and_remote_manifest_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            case = make_case(folder)
            with self.assertRaisesRegex(calibration.FacilityCalibrationError, "Duplicate"):
                calibration.score_dataset(manifest(folder, [case, case]))
            bad_manifest = folder / "calibration.json"
            data = json.loads(bad_manifest.read_text(encoding="utf-8"))
            data["cases"] = [{**data["cases"][0],
                              "draft": "https://fake.invalid/report.json"}]
            bad_manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(calibration.FacilityCalibrationError, "local"):
                calibration.score_dataset(bad_manifest)

    def test_out_of_range_timestamp_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video, draft, labels = make_case(folder)
            data = json.loads(draft.read_text(encoding="utf-8"))
            data["analysis"]["facilities"]["dj_booth"]["evidence"][0]["timestamp_seconds"] = 999
            draft.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Facility evidence"):
                calibration.score_dataset(manifest(folder, [(video, draft, labels)]))

    def test_fake_probe_duration_rejected_before_ground_truth_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video, draft, label_file = make_case(folder)
            with patch.object(calibration, "verify_mp4",
                              return_value={"metadataVerified": True,
                                            "durationSeconds": 2.0, "audioTracks": 0}):
                with self.assertRaisesRegex(calibration.FacilityCalibrationError, "durations differ"):
                    calibration.score_dataset(manifest(folder, [(video, draft, label_file)]))

    def test_no_false_precision_claim_with_zero_positive_examples(self):
        metrics = calibration._score(0, 0, 0, 7)
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["f1"])
        self.assertEqual(metrics["evaluated"], 7)

    def test_template_or_results_cannot_be_written_to_public_git_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            video, draft, labels = make_case(Path(tmp))
            with self.assertRaisesRegex(calibration.FacilityCalibrationError, "outside the repository"):
                calibration.create_label_template(
                    draft, video, calibration.ROOT / "data" / "human-labels.json")
            with self.assertRaisesRegex(calibration.FacilityCalibrationError, "outside the repository"):
                calibration.private_destination(calibration.ROOT / "README.md")


if __name__ == "__main__":
    unittest.main()
