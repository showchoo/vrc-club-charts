"""Offline tests: no Gemini calls or external screenshots are made."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import analyze_private_scene_still as analyzer
from scripts.inspection_facility_inventory import FACILITIES
from scripts.inspection_light_cycle import sample_lighting

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
RUN = WORLD + "_20261111T082523Z_82d546cee3"


def model_views():
    output = {}
    for view in ("original", "shadowLift"):
        rows = {}
        for kind in FACILITIES:
            visible = kind in ("video_screen", "stage")
            # One invented booth visible only after contrast enhancement must
            # NOT become a candidate: no independent source-frame evidence.
            if kind == "dj_booth" and view == "shadowLift":
                visible = True
            rows[kind] = {
                "visibility": "visible" if visible else "unclear",
                "confidence": .93 if visible else 0.0,
            }
        output[view] = rows
    return output


class PrivateStillTests(unittest.TestCase):
    def setUp(self):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            self.skipTest("Pillow required for synthetic PNG tests")
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.folder = Path(self.work.name) / RUN
        self.folder.mkdir()
        self.report = self.folder / "lighting-cycle.json"
        image = Image.new("RGB", (640, 360), (5, 5, 8))
        ImageDraw.Draw(image).rectangle((140, 65, 495, 248),
                                        fill=(180, 190, 200))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        original = buffer.getvalue()
        (self.folder / "low-light-review.png").write_bytes(original)
        m = sample_lighting(original)
        self.assertLess(m["medianLuma"], 45)
        self.assertLess(m["nearBlackFraction"], .92)
        self.doc = {
            "schemaVersion": 1,
            "worldId": WORLD,
            "status": "low-light-visibility-needs-review",
            "source": "local-supervised-stationary-light-cycle",
            "captureRegion": {
                "left": 230, "top": -970, "width": 640, "height": 360},
            "lightingCycle": {"status": "calibrating", "samples": 10},
            "luminanceSamples": [
                {"sample": i, "medianLuma": m["medianLuma"],
                 "nearBlackFraction": m["nearBlackFraction"], "state": "calibrating"}
                for i in range(1, 11)
            ],
            "lowLightSample": {
                "status": "low-light-review-candidate",
                "sample": 6, "medianLuma": m["medianLuma"],
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
                "sha256": hashlib.sha256(original).hexdigest(),
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
        self.report.write_text(json.dumps(self.doc), encoding="utf-8")

    def test_requires_two_explicit_operator_consents_even_with_fake_ai(self):
        requests = []
        def fake_ai(*args):
            requests.append(args)
            return model_views()
        for recording, upload in ((False, False), (True, False),
                                  (False, True)):
            with self.subTest(recording=recording, upload=upload):
                with self.assertRaisesRegex(analyzer.StillFacilityError, "consent"):
                    analyzer.generate_private_facility_draft(
                        report_path=self.report,
                        recording_rights_confirmed=recording,
                        gemini_upload_confirmed=upload,
                        inference_fn=fake_ai)
        self.assertEqual(requests, [])
        self.assertFalse((self.folder / "private-visibility-review").exists())

    def test_model_output_is_strictly_allowlisted(self):
        good = model_views()
        self.assertEqual(analyzer.validate_model_output(good)["original"]["stage"]["visibility"],
                         "visible")
        for mutant in [
            {"original": good["original"]},
            {**good, "explanation": "possibly username"},
            {"original": {**good["original"], "speaker": {}},
             "shadowLift": good["shadowLift"]},
        ]:
            with self.subTest(mutant=mutant), self.assertRaises(analyzer.StillFacilityError):
                analyzer.validate_model_output(mutant)
        for bad in (True, -0.1, 1.2, float("nan"), "high"):
            modified = model_views()
            modified["original"]["stage"]["confidence"] = bad
            with self.subTest(value=bad), self.assertRaises(analyzer.StillFacilityError):
                analyzer.validate_model_output(modified)
        modified = model_views()
        modified["original"]["stage"]["visibility"] = []
        with self.assertRaises(analyzer.StillFacilityError):
            analyzer.validate_model_output(modified)
        modified = model_views()
        modified["original"]["stage"]["chat"] = "do not log"
        with self.assertRaises(analyzer.StillFacilityError):
            analyzer.validate_model_output(modified)

    def test_only_candidates_visible_in_both_views_and_unverified(self):
        candidates = analyzer.conservative_candidates(model_views())
        self.assertEqual(set(candidates), set(FACILITIES))
        self.assertEqual(candidates["stage"]["status"],
                         "appearance-candidate-unreviewed")
        self.assertEqual(candidates["video_screen"]["status"],
                         "appearance-candidate-unreviewed")
        self.assertEqual(candidates["dj_booth"]["status"],
                         "insufficient-still-evidence")
        for item in candidates.values():
            self.assertFalse(item["equipmentFunctionalityVerified"])
            self.assertFalse(item["independentCorroboration"])
            self.assertTrue(item["humanReviewRequired"])

    def test_analysis_with_mock_provider_produces_private_draft_only(self):
        calls = []
        def fake_ai(original, lifted, model):
            calls.append(model)
            self.assertTrue(original.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertTrue(lifted.startswith(b"\x89PNG\r\n\x1a\n"))
            return model_views()
        result = analyzer.generate_private_facility_draft(
            report_path=self.report, recording_rights_confirmed=True,
            gemini_upload_confirmed=True, inference_fn=fake_ai)
        self.assertEqual(calls, [analyzer.DEFAULT_MODEL])
        self.assertEqual(result["status"], "private-image-appearance-draft")
        self.assertEqual(set(result["appearanceCandidates"]),
                         {"stage", "video_screen"})
        self.assertTrue(result["newGeminiRequestMade"])
        self.assertFalse(result["equipmentFunctionalityVerified"])
        self.assertFalse(result["publiclyShareable"])
        self.assertFalse(result["liveDJStreamingVerified"])
        draft = json.loads(Path(result["draft"]).read_text(encoding="utf-8"))
        self.assertFalse(draft["imagesIndependent"])
        self.assertFalse(draft["modelConfidenceCalibrated"])
        self.assertFalse(draft["navigationSafe"])
        self.assertFalse(draft["equipmentFunctionalityVerified"])
        self.assertFalse(draft["rankingEligible"])
        self.assertEqual(draft["facilityCandidates"]["dj_booth"]["status"],
                         "insufficient-still-evidence")
        self.assertEqual(Path(result["draft"]).parent.name,
                         "private-visibility-review")
        self.assertNotIn("AI notes:", Path(result["draft"]).read_text())

    def test_existing_draft_prevents_second_network_request(self):
        analyzer.generate_private_facility_draft(
            report_path=self.report, recording_rights_confirmed=True,
            gemini_upload_confirmed=True,
            inference_fn=lambda *args: model_views())
        def no_repeat(*args):
            raise AssertionError("Never repeat a private upload")
        output = analyzer.generate_private_facility_draft(
            report_path=self.report, recording_rights_confirmed=True,
            gemini_upload_confirmed=True, inference_fn=no_repeat)
        self.assertEqual(output["status"],
                         "existing-private-image-appearance-draft")
        self.assertFalse(output["newGeminiRequestMade"])

    def test_changed_world_id_and_candidates_in_stored_draft_rejected(self):
        result = analyzer.generate_private_facility_draft(
            report_path=self.report, recording_rights_confirmed=True,
            gemini_upload_confirmed=True,
            inference_fn=lambda *args: model_views())
        path = Path(result["draft"])
        draft = json.loads(path.read_text())
        draft["worldId"] = "wrld_11111111-1111-1111-1111-111111111111"
        path.write_text(json.dumps(draft))
        with self.assertRaisesRegex(analyzer.StillFacilityError,
                                    "existing-private-draft-provenance-invalid"):
            analyzer.generate_private_facility_draft(
                report_path=self.report, recording_rights_confirmed=True,
                gemini_upload_confirmed=True,
                inference_fn=lambda *args: None)

    def test_malformed_model_payload_does_not_leave_draft(self):
        def invalid(*args):
            return {"usernames": ["private"]}
        with self.assertRaises(analyzer.StillFacilityError):
            analyzer.generate_private_facility_draft(
                report_path=self.report, recording_rights_confirmed=True,
                gemini_upload_confirmed=True, inference_fn=invalid)
        self.assertFalse(list(self.folder.rglob("still-facilities-*.json")))

    def test_gemini_error_is_sanitized_in_operator_output(self):
        def bad(*args):
            raise RuntimeError("some-secret-token")
        with self.assertRaisesRegex(analyzer.StillFacilityError,
                                    "private-image-inference-failed") as raised:
            analyzer.generate_private_facility_draft(
                report_path=self.report, recording_rights_confirmed=True,
                gemini_upload_confirmed=True, inference_fn=bad)
        self.assertNotIn("some-secret", str(raised.exception))

    def test_default_cli_is_verified_read_only(self):
        output = io.StringIO()
        with (
            patch.object(analyzer, "call_gemini",
                         side_effect=AssertionError("No image API call")),
            patch.object(analyzer, "produce_private_review",
                         side_effect=AssertionError("No files by default")),
            redirect_stdout(output),
        ):
            code = analyzer.main(["--report", str(self.report)])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "dry-run-private-still-verified")
        self.assertFalse(report["newGeminiRequestMade"])
        self.assertEqual(report["filesCreated"], 0)
        self.assertFalse((self.folder / "private-visibility-review").exists())

    def test_image_upload_encoding_resizes_and_strips_metadata(self):
        from PIL import Image
        original = (self.folder / "low-light-review.png").read_bytes()
        jpeg = analyzer._jpeg_for_inline(original)
        self.assertLess(len(jpeg), 3 * 1024 * 1024)
        with Image.open(io.BytesIO(jpeg)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertLessEqual(image.width, 1280)
            self.assertLessEqual(image.height, 1280)
            self.assertFalse(image.info.get("exif"))

    def test_invalid_model_does_not_trigger_analyzer(self):
        with self.assertRaisesRegex(analyzer.StillFacilityError, "invalid-model-name"):
            analyzer.generate_private_facility_draft(
                report_path=self.report, model="../private",
                recording_rights_confirmed=True,
                gemini_upload_confirmed=True,
                inference_fn=lambda *args: None)

    def test_no_gemini_key_causes_no_upload(self):
        original = (self.folder / "low-light-review.png").read_bytes()
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaisesRegex(analyzer.StillFacilityError,
                                        "gemini-api-key-not-configured"):
                analyzer.call_gemini(original, original, analyzer.DEFAULT_MODEL)


if __name__ == "__main__":
    unittest.main()
