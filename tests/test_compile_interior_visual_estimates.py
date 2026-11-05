"""Video-only scores must not be mislabeled as world craftsmanship or DJ tests."""
from __future__ import annotations
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from scripts import compile_interior_visual_estimates as c
from scripts.evaluate_interior_video import DIMENSIONS

WORLD = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def fixture(allowed=True):
    evidence = [{"timestamp_seconds": 5, "observation": "Synthetic stage",
                 "confidence": 0.85}]
    dimensions = {d: {"status": "unclear", "score": None,
                      "note": "Not observed", "evidence": []} for d in DIMENSIONS}
    for d in ("visual_design", "lighting_design", "spatial_design", "originality"):
        dimensions[d] = {"status": "observed", "score": 4,
                         "note": "Visible synthetic interior", "evidence": evidence}
    return {
        "schemaVersion": 1, "worldId": WORLD,
        "status": "draft_video_assessment", "rankingEligible": False,
        "assessedAtUtc": "2026-11-06T02:00:00+00:00",
        "method": {"kind": "gemini_video_analysis",
                   "independentInWorldInspection": False},
        "evidence": {"type": "interior_video", "source": "creator-provided",
                     "sha256": "a" * 64, "durationSeconds": 10.0,
                     "durationSource": "ffprobe"},
        "visualQuality": {
            "status": "ok", "sampledFrames": 10,
            "visualChangeIntervals": 4, "framesWithDetail": 10,
        },
        "consent": {
            "recordingConsentConfirmed": True,
            "aiAnalysisConsentConfirmed": True,
            "permissionToPublishVisualEstimate": allowed,
        },
        "analysis": {"summary": "This could include private user text; do not publish",
                     "dimensions": dimensions},
    }


class VisualFeedTests(unittest.TestCase):
    def test_publishes_only_consented_visual_provisional_values(self):
        report = c.assess_draft(fixture())
        self.assertEqual(report["worldId"], WORLD)
        self.assertEqual(report["visualScore"], 80)
        self.assertEqual(report["evidenceCoverage"], 4)
        self.assertIsNone(report["craftsmanshipScore"])
        self.assertFalse(report["djPlaybackVerified"])
        self.assertFalse(report["independentInWorldInspection"])
        self.assertNotIn("private user", json.dumps(report))

    def test_no_permission_means_no_public_entry(self):
        self.assertIsNone(c.assess_draft(fixture(False)))

    def test_low_evidence_confidence_does_not_create_score(self):
        report = fixture()
        for dim in report["analysis"]["dimensions"].values():
            for ev in dim["evidence"]:
                ev["confidence"] = 0.45
        self.assertIsNone(c.assess_draft(report))

    def test_incomplete_visual_evidence_does_not_create_score(self):
        report = fixture()
        for key in ("spatial_design", "originality"):
            report["analysis"]["dimensions"][key] = {
                "status": "unclear", "score": None,
                "note": "Not observed", "evidence": [],
            }
        self.assertIsNone(c.assess_draft(report))

    def test_denies_false_verified_inspection_claim_and_extra_fields(self):
        report = fixture()
        report["method"]["independentInWorldInspection"] = True
        with self.assertRaises(ValueError):
            c.assess_draft(report)
        report["method"]["independentInWorldInspection"] = False
        report["analysis"]["dimensions"]["unapproved"] = {
            "status": "observed", "score": 5, "note": "fake", "evidence": [],
        }
        with self.assertRaises(ValueError):
            c.assess_draft(report)

    def test_nonexistent_video_timestamp_cannot_support_published_score(self):
        report = fixture()
        report["analysis"]["dimensions"]["visual_design"]["evidence"][0]["timestamp_seconds"] = 99.0
        with self.assertRaisesRegex(ValueError, "beyond the verified recording"):
            c.assess_draft(report)

    def test_legacy_draft_without_verified_duration_is_unpublishable(self):
        report = fixture()
        del report["evidence"]["durationSeconds"]
        with self.assertRaisesRegex(ValueError, "duration"):
            c.assess_draft(report)

    def test_unusable_visual_quality_cannot_be_published(self):
        report = fixture()
        report["visualQuality"]["status"] = "unusable"
        with self.assertRaisesRegex(ValueError, "Unusable"):
            c.assess_draft(report)

    def test_catalog_gate_and_latest_by_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            a = fixture()
            (folder / "01.draft.json").write_text(json.dumps(a), encoding="utf-8")
            b = fixture()
            b["assessedAtUtc"] = "2026-11-07T02:00:00+00:00"
            b["analysis"]["dimensions"]["visual_design"]["score"] = 5
            (folder / "02.draft.json").write_text(json.dumps(b), encoding="utf-8")
            feed = c.compile_feed(folder, eligible_ids={WORLD})
            self.assertEqual(len(feed["worlds"]), 1)
            self.assertGreater(feed["worlds"][0]["visualScore"], 80)
            self.assertEqual(feed["method"], "consented-video-visual-only-provisional")
            feed2 = c.compile_feed(folder, eligible_ids=set())
            self.assertEqual(feed2["worlds"], [])

    def test_refuses_private_output_in_arbitrary_repository_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "fixture.draft.json").write_text(json.dumps(fixture()), encoding="utf-8")
            with self.assertRaises(SystemExit) as ctx:
                c.main(["--draft-dir", str(folder), "--out",
                        str(c.ROOT / "data" / "weekly-ranking.json")])
            self.assertEqual(ctx.exception.code, 2)

    def test_rejects_invalid_consent_and_bad_provenance(self):
        report = fixture()
        report["consent"]["permissionToPublishVisualEstimate"] = "yes"
        self.assertIsNone(c.assess_draft(report))
        report["consent"]["permissionToPublishVisualEstimate"] = True
        report["evidence"]["sha256"] = "../secrets"
        with self.assertRaises(ValueError):
            c.assess_draft(report)


if __name__ == "__main__":
    unittest.main()
