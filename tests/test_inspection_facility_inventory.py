"""Facility visibility is *not* DJ device functionality; tests run fully offline."""
import copy
import json
import math
import unittest
from scripts import inspection_facility_inventory as inv
from scripts.evaluate_interior_video import DIMENSIONS, validate_analysis
from scripts.inspection_evidence_timeline import attach_verified_timeline, EvidenceTimelineError


def facility_fixture():
    return {
        kind: {
            "visibility": "visible" if kind in {"dj_booth", "dj_decks", "video_screen"} else "unclear",
            "evidence": (
                [{"timestamp_seconds": 2.0, "confidence": 0.91}]
                if kind == "dj_booth" else
                [{"timestamp_seconds": 2.5, "confidence": 0.85}]
                if kind == "dj_decks" else
                [{"timestamp_seconds": 3.0, "confidence": 0.72}]
                if kind == "video_screen" else []
            ),
        }
        for kind in inv.FACILITIES
    }


def model_report(facilities=None):
    dims = {
        key: {"status": "unclear", "score": None, "note": "not scored", "evidence": []}
        for key in DIMENSIONS
    }
    return {
        "evidence": {"type": "interior_video", "sha256": "a" * 64},
        "analysis": {
            "summary": "Synthetic sample",
            "dimensions": dims,
            "facilities": facilities if facilities is not None else facility_fixture(),
        },
    }


def clip_meta():
    return {"metadataVerified": True, "audioTracks": 0, "durationSeconds": 4.0}


def quality_meta():
    return {
        "status": "ok", "sampledFrames": 4,
        "visualChangeIntervals": 2, "framesWithDetail": 4,
    }


class FacilityTests(unittest.TestCase):
    def test_strict_model_schema_supports_optional_legacy_drafts(self):
        fixture = model_report()["analysis"]
        normalized = validate_analysis(fixture)
        self.assertEqual(normalized["facilities"]["dj_booth"]["visibility"], "visible")
        self.assertEqual(normalized["dimensions"]["dj_equipment"]["score"], None)
        old = {"summary": fixture["summary"], "dimensions": fixture["dimensions"]}
        self.assertNotIn("facilities", validate_analysis(old))

    def test_public_inventory_is_numeric_allowlisted_and_no_operating_claims(self):
        items = inv.public_facility_observations(facility_fixture(), duration_seconds=4.0)
        self.assertEqual([item["kind"] for item in items], ["dj_booth", "dj_decks"])
        self.assertEqual(items[0]["timestampSeconds"], 2)
        self.assertFalse(any(x["equipmentFunctionalityVerified"] for x in items))
        self.assertNotIn("observation", json.dumps(items))

    def test_bad_payload_types_and_additional_strings_rejected(self):
        cases = []
        incomplete = facility_fixture()
        del incomplete["dj_booth"]
        cases.append(incomplete)
        wrong = facility_fixture()
        wrong["dj_booth"]["visibility"] = ["visible"]
        cases.append(wrong)
        extra = facility_fixture()
        extra["dj_decks"]["evidence"][0]["userId"] = "private avatar name"
        cases.append(extra)
        missing = facility_fixture()
        missing["dj_booth"]["evidence"] = []
        cases.append(missing)
        bad_time = facility_fixture()
        bad_time["dj_booth"]["evidence"][0]["timestamp_seconds"] = math.nan
        cases.append(bad_time)
        bad_confidence = facility_fixture()
        bad_confidence["dj_decks"]["evidence"][0]["confidence"] = True
        cases.append(bad_confidence)
        for payload in cases:
            with self.subTest(payload=repr(payload)[:40]), self.assertRaises(ValueError):
                inv.validate_facilities(payload)

    def test_facility_future_timestamp_blocks_draft_instead_of_publishing(self):
        report = model_report()
        report["analysis"]["facilities"]["dj_booth"]["evidence"][0]["timestamp_seconds"] = 50.0
        with self.assertRaisesRegex(EvidenceTimelineError, "Facility evidence"):
            attach_verified_timeline(report, metadata=clip_meta(),
                                     visual_quality=quality_meta())

    def test_real_timeline_counts_visual_facility_sightings(self):
        enriched = attach_verified_timeline(model_report(), metadata=clip_meta(),
                                            visual_quality=quality_meta())
        self.assertEqual(enriched["timelineAudit"]["facilityEvidencePointsChecked"], 3)
        self.assertFalse(enriched["timelineAudit"]["equipmentFunctionalityVerified"])

    def test_public_serializer_drops_injected_unknown_and_operational_claims(self):
        raw = [
            {"kind": "dj_booth", "timestampSeconds": 1.0,
             "confidence": .99, "equipmentFunctionalityVerified": False,
             "secret":"never copy"},
            {"kind": "dj_booth", "timestampSeconds": 1.0,
             "confidence": .99, "equipmentFunctionalityVerified": False},
            {"kind": "<script>", "timestampSeconds": 2,
             "confidence": .99, "equipmentFunctionalityVerified": False},
            {"kind": "dj_decks", "timestampSeconds": 1.5,
             "confidence": .95, "equipmentFunctionalityVerified": True},
            {"kind": "lighting_rig", "timestampSeconds": float("inf"),
             "confidence": 1.0, "equipmentFunctionalityVerified": False},
        ]
        safe = inv.sanitize_public_facilities(raw)
        self.assertEqual(len(safe), 1)
        self.assertEqual(safe[0]["kind"], "dj_booth")
        self.assertNotIn("secret", json.dumps(safe))
        self.assertNotIn("script", json.dumps(safe))

    def test_no_visual_facilities_means_no_false_claims(self):
        unknown = {
            kind: {"visibility": "unclear", "evidence": []}
            for kind in inv.FACILITIES
        }
        self.assertEqual(inv.public_facility_observations(unknown, duration_seconds=4), [])


if __name__ == "__main__":
    unittest.main()
