"""Offline tests: human says AI booth candidate is not actually visible."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import review_facility_keyframes as review

WORLD = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
SHA = "ab" * 32


def create_private_evidence(root: Path, *, kind="dj_booth") -> Path:
    folder = root / f"{WORLD}_{SHA}"
    folder.mkdir()
    image = f"{kind}_005000ms.jpg"
    (folder / image).write_bytes(b"\xff\xd8" + b"image content" * 50 + b"\xff\xd9")
    (folder / "index.html").write_text("old original", encoding="utf-8")
    (folder / "frames.json").write_text(json.dumps({
        "schemaVersion": 1, "status": "local-private-unreviewed",
        "worldId": WORLD, "mediaSha256": SHA, "frameCount": 1,
        "items": [{
            "kind": kind, "file": image, "timestampSeconds": 5.0,
            "confidence": 0.9, "humanReviewed": False,
            "equipmentFunctionalityVerified": False,
        }],
        "publiclyShareable": False, "equipmentFunctionalityVerified": False,
    }), encoding="utf-8")
    return folder


class ReviewKeyframeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_model_prompt_forbids_stage_inference_for_elevated_dj_booth(self):
        from scripts.inspection_facility_inventory import MODEL_INSTRUCTIONS
        self.assertIn("raised stage", MODEL_INSTRUCTIONS)
        self.assertIn("out of camera view or occluded", MODEL_INSTRUCTIONS)
        self.assertIn('return "not_visible" for dj_booth', MODEL_INSTRUCTIONS)

    def test_human_false_positive_note_stays_private_and_original_unchanged(self):
        folder = create_private_evidence(self.root)
        original_manifest = (folder / "frames.json").read_bytes()
        original_index = (folder / "index.html").read_bytes()
        with patch.object(review, "atomic_json", wraps=review.atomic_json) as save:
            result = review.record_review(
                folder, facility="dj_booth", verdict="not-visible-from-vantage",
                reason="raised-area-out-of-view")
        self.assertEqual(result["status"], "private-human-appearance-review")
        self.assertFalse(result["publiclyShareable"])
        self.assertEqual(save.call_count, 1)
        self.assertEqual((folder / "frames.json").read_bytes(), original_manifest)
        self.assertEqual((folder / "index.html").read_bytes(), original_index)
        saved = json.loads((folder / "human-review.json").read_text())
        self.assertEqual(saved["mediaSha256"], SHA)
        self.assertFalse(saved["publiclyShareable"])
        self.assertFalse(saved["equipmentFunctionalityVerified"])
        self.assertEqual(saved["reviews"], [{
            "kind": "dj_booth", "verdict": "not-visible-from-vantage",
            "reason": "raised-area-out-of-view",
            "humanReviewed": True, "equipmentFunctionalityVerified": False,
        }])
        page = (folder / "reviewed-index.html").read_text(encoding="utf-8")
        self.assertIn("この撮影位置から対象を確認できない", page)
        self.assertIn("対象が段差・高所にあり", page)
        self.assertIn("Worldに設備が存在しない証明ではありません", page)
        self.assertIn("dj_booth_005000ms.jpg", page)
        self.assertIn("noindex", page)
        self.assertNotIn("<script", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_repeat_same_review_is_idempotent_but_conflicts_fail_closed(self):
        folder = create_private_evidence(self.root)
        args = dict(facility="dj_booth", verdict="not-visible-from-vantage",
                    reason="raised-area-out-of-view")
        first = review.record_review(folder, **args)
        second = review.record_review(folder, **args)
        self.assertEqual(first["reviewedIndex"], second["reviewedIndex"])
        records = json.loads((folder / "human-review.json").read_text())["reviews"]
        self.assertEqual(len(records), 1)
        with self.assertRaisesRegex(review.HumanReviewError, "Conflicting review"):
            review.record_review(folder, facility="dj_booth",
                                 verdict="visible-appearance-only",
                                 reason="raised-area-out-of-view")
        self.assertEqual(json.loads((folder / "human-review.json").read_text())["reviews"], records)

    def test_refuses_to_review_without_cli_confirmation(self):
        folder = create_private_evidence(self.root)
        with patch.object(review, "record_review",
                          side_effect=AssertionError("Must not mutate")):
            with self.assertRaises(SystemExit) as caught:
                review.main([
                    "--frames-dir", str(folder), "--facility", "dj_booth",
                    "--verdict", "not-visible-from-vantage", "--reason",
                    "raised-area-out-of-view",
                ])
        self.assertEqual(caught.exception.code, 2)
        self.assertFalse((folder / "human-review.json").exists())

    def test_refuses_unlisted_facility_and_any_public_manifest(self):
        folder = create_private_evidence(self.root)
        with self.assertRaisesRegex(review.HumanReviewError, "not among"):
            review.record_review(folder, facility="stage",
                                 verdict="uncertain", reason="other-visibility-issue")
        manifest_path = folder / "frames.json"
        data = json.loads(manifest_path.read_text())
        data["publiclyShareable"] = True
        manifest_path.write_text(json.dumps(data))
        with self.assertRaisesRegex(review.HumanReviewError, "private"):
            review.record_review(folder, facility="dj_booth",
                                 verdict="not-visible-from-vantage",
                                 reason="raised-area-out-of-view")
        self.assertFalse((folder / "human-review.json").exists())

    def test_refuses_forged_world_folder_and_missing_image(self):
        folder = create_private_evidence(self.root)
        folder.rename(self.root / "wrong-name")
        renamed = self.root / "wrong-name"
        with self.assertRaisesRegex(review.HumanReviewError, "Folder"):
            review.record_review(renamed, facility="dj_booth",
                                 verdict="not-visible-from-vantage",
                                 reason="raised-area-out-of-view")
        renamed.rename(folder)
        (folder / "dj_booth_005000ms.jpg").unlink()
        with self.assertRaisesRegex(review.HumanReviewError, "Missing local"):
            review.record_review(folder, facility="dj_booth",
                                 verdict="not-visible-from-vantage",
                                 reason="raised-area-out-of-view")
        self.assertFalse((folder / "human-review.json").exists())

    def test_render_escapes_file_and_labels_from_trusted_allowlist(self):
        folder = create_private_evidence(self.root)
        result = review.record_review(
            folder, facility="dj_booth", verdict="uncertain",
            reason="ai-confused-stage")
        text = Path(result["reviewedIndex"]).read_text(encoding="utf-8")
        self.assertIn("AIが舞台・スクリーン等を設備と誤認", text)
        self.assertNotIn("equipmentFunctionalityVerified", text)


if __name__ == "__main__":
    unittest.main()
