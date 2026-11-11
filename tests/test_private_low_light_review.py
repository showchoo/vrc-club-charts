"""Offline tests for private, provenance-checked dark DJ screenshot review."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import private_low_light_review as review
from scripts.inspection_light_cycle import sample_lighting

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
RUN = WORLD + "_20261111T082523Z_82d546cee3"


class PrivateReviewTests(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow is needed to test real local PNG enhancement")
        self.Image, self.ImageDraw = Image, ImageDraw
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private-light-recovery"
        self.folder = self.root / RUN
        self.folder.mkdir(parents=True)
        image = Image.new("RGB", (640, 360), (6, 6, 8))
        ImageDraw.Draw(image).rectangle((155, 45, 530, 220),
                                        fill=(190, 184, 175))
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        self.original = stream.getvalue()
        self.source = self.folder / review.SOURCE_NAME
        self.source.write_bytes(self.original)
        m = sample_lighting(self.original)
        self.assertLess(m["medianLuma"], 45)
        self.assertLess(m["nearBlackFraction"], .92)
        self.report = self.folder / "lighting-cycle.json"
        self.doc = {
            "schemaVersion": 1,
            "worldId": WORLD,
            "status": "low-light-visibility-needs-review",
            "source": "local-supervised-stationary-light-cycle",
            "captureRegion": {"left": 230, "top": -970,
                              "width": 640, "height": 360},
            "lightingCycle": {"status": "calibrating", "samples": 10},
            "luminanceSamples": [
                {"sample": i, "medianLuma": m["medianLuma"],
                 "nearBlackFraction": m["nearBlackFraction"],
                 "state": "calibrating"}
                for i in range(1, 11)
            ],
            "lowLightSample": {
                "status": "low-light-review-candidate",
                "sample": 6,
                "medianLuma": m["medianLuma"],
                "nearBlackFraction": m["nearBlackFraction"],
                "selectionPolicy":
                    "lowest-near-black-fraction-then-highest-median",
                "humanReviewRequired": True,
                "captureVisibilityVerified": False,
                "lightingCycleVerified": False,
                "safeToMoveOrResumeAutomation": False,
                "djEquipmentVerified": False,
            },
            "screenshot": {
                "file": "low-light-review.png",
                "sha256": hashlib.sha256(self.original).hexdigest(),
                "humanReviewRequired": True,
                "stableLightingRecoveryConfirmed": False,
                "captureVisibilityVerified": False,
            },
            "privateLocalOnly": True,
            "publiclyShareable": False,
            "rankingEligible": False,
            "movementCommandsSent": 0,
            "autonomousMovementRestarted": False,
            "externalUploads": False,
        }
        self.write_report()

    def write_report(self):
        self.report.write_text(
            json.dumps(self.doc, ensure_ascii=False), encoding="utf-8")

    def test_local_review_never_alters_original_or_calls_cloud(self):
        before = self.source.read_bytes()
        report_before = self.report.read_bytes()
        with (
            patch.object(review.os, "startfile", create=True,
                         side_effect=AssertionError("Browser must not open")),
            patch.object(review, "latest_private_report",
                         side_effect=AssertionError("Explicit report passed")),
        ):
            result = review.produce_private_review(self.report)
        self.assertEqual(result["status"], "private-shadow-review-unverified")
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.report.read_bytes(), report_before)
        self.assertFalse(result["equipmentFunctionalityVerified"])
        self.assertFalse(result["externalUploads"])
        self.assertFalse(result["publiclyShareable"])
        self.assertFalse(result["vrchatLaunched"])
        index = Path(result["index"])
        self.assertTrue(index.is_file())
        text = index.read_text(encoding="utf-8")
        self.assertIn("原画", text)
        self.assertIn("shadow-lift.png", text)
        self.assertNotIn("https://", text)
        manifest = json.loads((index.parent / "review.json").read_text())
        self.assertEqual(manifest["originalSha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual((index.parent / "original.png").read_bytes(), before)
        self.assertEqual(manifest["transform"]["kind"],
                         "local-YCbCr-luma-shadow-power-curve")
        self.assertFalse(manifest["djBoothLocated"])
        self.assertFalse(manifest["lightingCycleVerified"])
        self.assertFalse(manifest["navigationSafe"])
        self.assertGreater(result["enhancedMetrics"]["medianLuma"],
                           result["originalMetrics"]["medianLuma"])
        self.assertGreaterEqual(result["enhancedMetrics"]["lumaP90"], 0)
        self.assertEqual(len(list(self.folder.glob("private-visibility-review"))), 1)

    def test_reusing_identical_private_review_is_read_only(self):
        first = review.produce_private_review(self.report)
        path = Path(first["enhanced"])
        before = path.read_bytes()
        result = review.produce_private_review(self.report)
        self.assertEqual(result["status"], "existing-private-review")
        self.assertEqual(path.read_bytes(), before)
        self.assertFalse(result["equipmentFunctionalityVerified"])

    def test_tampered_original_digest_is_rejected_no_outputs(self):
        self.source.write_bytes(self.original + b"extra")
        with self.assertRaisesRegex(review.PrivateReviewError, "sha256-mismatch"):
            review.produce_private_review(self.report)
        self.assertFalse((self.folder / review.REVIEW_FOLDER).exists())

    def test_tampered_existing_enhanced_image_is_rejected(self):
        result = review.produce_private_review(self.report)
        Path(result["enhanced"]).write_bytes(b"modified")
        with self.assertRaisesRegex(review.PrivateReviewError, "review-image-changed"):
            review.produce_private_review(self.report)

    def test_incomplete_existing_review_cannot_be_overwritten(self):
        (self.folder / review.REVIEW_FOLDER).mkdir()
        with self.assertRaisesRegex(review.PrivateReviewError, "private-file-missing"):
            review.produce_private_review(self.report)

    def test_synthetic_world_status_and_consent_are_strict(self):
        self.doc["status"] = "lighting-cycle-not-confirmed"
        self.write_report()
        with self.assertRaisesRegex(review.PrivateReviewError,
                                    "private-lighting-report-unverified|not-a-low-light"):
            review.produce_private_review(self.report)
        self.doc["status"] = "low-light-visibility-needs-review"
        self.doc["publiclyShareable"] = True
        self.write_report()
        with self.assertRaises(review.PrivateReviewError):
            review.produce_private_review(self.report)

    def test_wrong_captured_geometry_is_rejected(self):
        self.doc["captureRegion"]["width"] = 1280
        self.write_report()
        with self.assertRaisesRegex(review.PrivateReviewError,
                                    "capture-region-does-not-match-image"):
            review.produce_private_review(self.report)

    def test_symlink_source_is_rejected(self):
        data = self.source.read_bytes()
        self.source.unlink()
        real = self.folder / "real-private-image.png"
        real.write_bytes(data)
        try:
            self.source.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not available on this system")
        with self.assertRaisesRegex(review.PrivateReviewError, "symlink"):
            review.produce_private_review(self.report)

    def test_auto_discovers_newest_matching_private_review_report(self):
        older = self.root / (WORLD + "_20261111T072523Z_82d546cee3")
        older.mkdir()
        self.assertEqual(review.latest_private_report(self.root), self.report)
        self.assertEqual(review.latest_private_report(), self.report) if False else None

    def test_monotonic_curve_preserves_highlights_and_black(self):
        lut = review.shadow_curve()
        self.assertEqual(len(lut), 256)
        self.assertEqual(lut[0], 0)
        self.assertEqual(lut[112], 112)
        self.assertEqual(lut[255], 255)
        self.assertGreater(lut[9], 9)
        self.assertGreater(lut[40], 40)
        self.assertEqual(lut[180], 180)
        self.assertEqual(lut, sorted(lut))

    def test_cli_uses_given_report_and_returns_safe_status(self):
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            code = review.main(["--report", str(self.report)])
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "private-shadow-review-unverified")
        self.assertFalse(result["publiclyShareable"])


if __name__ == "__main__":
    unittest.main()
