"""Offline: human-verified movement can differ from low-res scene-change detector."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import inspection_position_feedback as feedback

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"


def fixture(folder: Path) -> Path:
    folder.mkdir()
    before = b"synthetic screenshot before" * 20
    after = b"synthetic screenshot after" * 20
    for name, data in (("before.png", before), ("after.png", after)):
        (folder / name).write_bytes(data)
    report = {
        "schemaVersion": 1, "worldId": WORLD, "direction": "forward",
        "stepSeconds": 0.2, "stepCountMax": 1, "stepsAttempted": 1,
        "source": "local-osc-private-single-position-step",
        "positionVerified": False, "distanceMeters": None,
        "collisionSafetyVerified": False, "equipmentFunctionalityVerified": False,
        "noPublicRankingChanges": True, "noExternalNetworkOrCloudUploads": True,
        "status": "sent-unverified", "visualChangeDetected": False,
        "visualDifferenceScore": 0.00038,
        "frames": [
            {"file": name, "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in (("before.png", before), ("after.png", after))
        ],
        "privateLocalOnly": True,
    }
    path = folder / "position-step.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


class PositionFeedbackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / (WORLD + "_20261111T053943Z_0d74d0c97d")
        self.report = fixture(self.folder)

    def test_operator_moved_despite_near_zero_image_delta_is_separate_feedback(self):
        original = self.report.read_bytes()
        original_before = (self.folder / "before.png").read_bytes()
        original_after = (self.folder / "after.png").read_bytes()
        visual = {
            "status": "computed", "meanAbsPixelDifference": .00051,
            "maxTileMeanDifference": .004,
            "movementAutomaticallyVerified": False,
        }
        with patch.object(feedback, "compare_frames", return_value=visual):
            result = feedback.save_feedback(self.report, observation="moved")
        self.assertEqual(result["status"], "private-human-movement-observation")
        self.assertEqual(result["observedMovement"], "moved")
        self.assertFalse(result["independentPositionVerified"])
        self.assertEqual(self.report.read_bytes(), original)
        self.assertEqual((self.folder / "before.png").read_bytes(), original_before)
        self.assertEqual((self.folder / "after.png").read_bytes(), original_after)
        stored = json.loads(Path(result["reportFile"]).read_text(encoding="utf-8"))
        self.assertTrue(stored["humanObservedMovement"])
        self.assertFalse(stored["independentPositionVerified"])
        self.assertIsNone(stored["metersMoved"])
        self.assertFalse(stored["collisionSafetyVerified"])
        self.assertFalse(stored["publiclyShareable"])
        self.assertFalse(stored["equipmentFunctionalityVerified"])
        self.assertEqual(stored["visualDiagnostics"]["maxTileMeanDifference"], .004)
        self.assertEqual(len(stored["sourceFrameHashes"]), 2)
        index = Path(result["index"]).read_text(encoding="utf-8")
        self.assertIn("操作者が目視で前進", index)
        self.assertIn("移動前", index)
        self.assertIn("移動後", index)
        self.assertIn("noindex", index)
        self.assertNotIn("<script", index)

    def test_idempotent_confirmation_and_conflicting_reversal_rejected(self):
        with patch.object(feedback, "compare_frames", return_value={
            "status": "computed", "movementAutomaticallyVerified": False}):
            first = feedback.save_feedback(self.report, observation="moved")
            second = feedback.save_feedback(self.report, observation="moved")
        self.assertEqual(second["status"], "existing-human-feedback")
        self.assertEqual(first["reportFile"], second["reportFile"])
        original_bytes = Path(first["reportFile"]).read_bytes()
        with self.assertRaisesRegex(feedback.PositionFeedbackError, "Conflicting"):
            feedback.save_feedback(self.report, observation="did-not-move")
        self.assertEqual(Path(first["reportFile"]).read_bytes(), original_bytes)

    def test_never_infers_movement_when_human_unsure(self):
        with patch.object(feedback, "compare_frames", return_value={
            "status": "computed", "meanAbsPixelDifference": .1,
            "movementAutomaticallyVerified": False}):
            result = feedback.save_feedback(self.report, observation="uncertain")
        saved = json.loads(Path(result["reportFile"]).read_text())
        self.assertEqual(saved["observedMovement"], "uncertain")
        self.assertFalse(saved["humanObservedMovement"])
        self.assertFalse(saved["independentPositionVerified"])

    def test_modified_image_hash_fails_before_any_feedback_write(self):
        (self.folder / "after.png").write_bytes(b"changed-after-original-record")
        with (patch.object(feedback, "compare_frames", side_effect=AssertionError("No decoding")),
              self.assertRaisesRegex(feedback.PositionFeedbackError, "checksum mismatch")):
            feedback.save_feedback(self.report, observation="moved")
        self.assertFalse((self.folder / "position-step-feedback.json").exists())

    def test_tampered_report_cannot_upgrade_review_or_public_rankings(self):
        report = json.loads(self.report.read_text())
        report["status"] = "completed"
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(feedback.PositionFeedbackError, "private single-step"):
            feedback.save_feedback(self.report, observation="moved")
        report["status"] = "sent-unverified"
        report["noPublicRankingChanges"] = False
        self.report.write_text(json.dumps(report))
        with self.assertRaisesRegex(feedback.PositionFeedbackError, "private single-step"):
            feedback.save_feedback(self.report, observation="moved")
        self.assertFalse((self.folder / "position-step-feedback.json").exists())

    def test_cli_requires_explicit_operator_confirmation(self):
        with patch.object(feedback, "save_feedback", side_effect=AssertionError("No write")):
            with self.assertRaises(SystemExit) as raised:
                feedback.main(["--report", str(self.report), "--observed", "moved"])
            self.assertEqual(raised.exception.code, 2)
        self.assertFalse((self.folder / "position-step-feedback.json").exists())

    def test_rejects_repository_storage_and_invalid_operator_choice(self):
        with self.assertRaisesRegex(feedback.PositionFeedbackError, "Invalid human"):
            feedback.save_feedback(self.report, observation="DJ-booth-confirmed")
        with self.assertRaises(ValueError):
            feedback.validate_original(feedback.ROOT / "scripts" / "position-step.json")

    def test_pixel_lookback_preserves_subtle_motion_as_diagnostic_not_proof(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Optional Pillow unavailable on CI runner")
        import io
        first = Image.new("RGB", (384, 240), (30, 30, 30))
        second = Image.new("RGB", (384, 240), (30, 30, 30))
        ImageDraw.Draw(first).rectangle((60, 80, 290, 172), outline=(95, 95, 95), width=3)
        ImageDraw.Draw(second).rectangle((61, 80, 291, 172), outline=(95, 95, 95), width=3)
        x, y = io.BytesIO(), io.BytesIO()
        first.save(x, format="PNG")
        second.save(y, format="PNG")
        report = feedback.compare_frames(
            x.getvalue(), y.getvalue(),
            preview_file=self.folder / "difference-amplified.png")
        self.assertEqual(report["status"], "computed")
        self.assertGreater(report["meanAbsPixelDifference"], 0)
        self.assertGreater(report["fractionPixelsDifferenceAbove3"], 0)
        self.assertGreater(report["maxTileMeanDifference"], 0)
        self.assertFalse(report["movementAutomaticallyVerified"])
        self.assertTrue((self.folder / "difference-amplified.png").is_file())

    def test_same_frame_has_zero_diagnostic_difference(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Optional Pillow unavailable on CI runner")
        import io
        image = Image.new("RGB", (384, 240), (18, 18, 18))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        report = feedback.compare_frames(
            stream.getvalue(), stream.getvalue(),
            preview_file=self.folder / "difference-amplified.png")
        self.assertEqual(report["meanAbsPixelDifference"], 0.0)
        self.assertEqual(report["fractionPixelsDifferenceAbove3"], 0.0)
        self.assertEqual(report["fractionPixelsDifferenceAbove10"], 0.0)


if __name__ == "__main__":
    unittest.main()
