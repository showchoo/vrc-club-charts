"""Offline timeline validation: no VRChat client, videos, model calls, or uploads."""
from __future__ import annotations

import math
import unittest
from scripts import inspection_evidence_timeline as timeline
from scripts.evaluate_interior_video import DIMENSIONS


def report(timestamp: float = 3.0) -> dict:
    dims = {key: {"status": "unclear", "score": None,
                  "note": "unknown", "evidence": []} for key in DIMENSIONS}
    dims["visual_design"] = {
        "status": "observed", "score": 3, "note": "synthetic",
        "evidence": [{"timestamp_seconds": timestamp,
                      "observation": "mock lamp", "confidence": .9}],
    }
    return {
        "evidence": {"type": "interior_video", "sha256": "a" * 64},
        "analysis": {"summary": "Synthetic", "dimensions": dims},
    }


def meta():
    return {"metadataVerified": True, "audioTracks": 0,
            "durationSeconds": 4.0}


def visual():
    return {"status": "ok", "sampledFrames": 4,
            "visualChangeIntervals": 2, "framesWithDetail": 4}


class TimelineTests(unittest.TestCase):
    def test_verified_media_adds_private_duration_and_audits_every_point(self):
        enriched = timeline.attach_verified_timeline(report(), metadata=meta(),
                                                     visual_quality=visual())
        self.assertTrue(enriched["timelineAudit"]["timelineChecked"])
        self.assertEqual(enriched["evidence"]["durationSource"], "ffprobe")
        self.assertEqual(enriched["timelineAudit"]["evidencePointsChecked"], 1)
        self.assertFalse(enriched["timelineAudit"]["equipmentFunctionalityVerified"])

    def test_timestamp_outside_video_even_if_under_generic_limit_rejected(self):
        for value in (4.4, 12.0, 3600.0):
            with self.subTest(value=value), self.assertRaisesRegex(
                timeline.EvidenceTimelineError, "beyond the verified"
            ):
                timeline.attach_verified_timeline(report(value),
                                                  metadata=meta(), visual_quality=visual())

    def test_within_quarter_second_tolerance(self):
        r = timeline.attach_verified_timeline(report(4.2),
                                              metadata=meta(), visual_quality=visual())
        self.assertEqual(r["timelineAudit"]["evidencePointsChecked"], 1)

    def test_missing_source_cannot_claim_verified_clip(self):
        evidence = timeline.attach_verified_timeline(report(), metadata=meta(),
                                                     visual_quality=visual())
        del evidence["evidence"]["durationSource"]
        with self.assertRaisesRegex(timeline.EvidenceTimelineError, "FFprobe"):
            timeline.audit_timeline(evidence)

    def test_missing_quality_or_unmoving_video_is_unpublishable(self):
        for bad in (
            {**visual(), "status": "unusable"},
            {**visual(), "visualChangeIntervals": 0},
            {**visual(), "sampledFrames": True},
            None,
        ):
            with self.subTest(bad=bad), self.assertRaises(timeline.EvidenceTimelineError):
                timeline.attach_verified_timeline(report(), metadata=meta(),
                                                  visual_quality=bad)

    def test_invalid_local_duration_cannot_be_attested(self):
        for duration in (None, 0, -1, True, float("nan"), float("inf"), 500):
            with self.subTest(duration=duration), self.assertRaises(timeline.EvidenceTimelineError):
                timeline.attach_verified_timeline(report(),
                    metadata={**meta(), "durationSeconds": duration},
                    visual_quality=visual())

    def test_audio_raises_provenance_error(self):
        with self.assertRaisesRegex(timeline.EvidenceTimelineError, "FFprobe"):
            timeline.attach_verified_timeline(report(),
                metadata={**meta(), "audioTracks": 1},
                visual_quality=visual())

    def test_draft_report_is_not_mutated(self):
        original = report()
        audited = timeline.attach_verified_timeline(original, metadata=meta(),
                                                    visual_quality=visual())
        self.assertNotIn("durationSeconds", original["evidence"])
        self.assertIn("durationSeconds", audited["evidence"])


if __name__ == "__main__":
    unittest.main()
