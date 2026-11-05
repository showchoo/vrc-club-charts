"""Offline validation of AI-generated in-world video reports; no network calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import evaluate_interior_video as evaluator

WORLD_ID = "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05"


def sample():
    return {
        "summary": "Visible DJ stage and lighting; no direct proof of stream operation.",
        "dimensions": {
            dim: {"status": "unclear", "score": None, "note": "Not visible", "evidence": []}
            for dim in evaluator.DIMENSIONS
        },
    }


class VideoAssessmentTests(unittest.TestCase):
    def test_valid_visual_video_does_not_publish_or_verify_playback(self):
        data = sample()
        data["dimensions"]["visual_design"] = {
            "status": "observed", "score": 4, "note": "Stage decor",
            "evidence": [{"timestamp_seconds": 12, "observation": "Layered lights around a DJ stage", "confidence": 0.8}],
        }
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "interior.mp4"
            video.write_bytes(b"synthetic test video data")
            report = evaluator.create_report(WORLD_ID, video, "creator-provided", data,
                                             "gemini-3.5-flash-lite")
            self.assertEqual(report["analysis"]["dimensions"]["visual_design"]["score"], 4)
            self.assertFalse(report["rankingEligible"])
            self.assertFalse(report["livePlaybackIndependentlyVerified"])
            self.assertEqual(report["evidence"]["source"], "creator-provided")
            self.assertEqual(len(report["evidence"]["sha256"]), 64)

    def test_rejects_performance_or_playback_score_even_when_model_claims_confidence(self):
        for name in evaluator.UNSCORABLE:
            data = sample()
            data["dimensions"][name] = {"status": "observed", "score": 5,
                                          "note": "Looks convincing",
                                          "evidence": [{"timestamp_seconds": 4, "observation": "Display visible", "confidence": 0.99}]}
            with self.subTest(name=name), self.assertRaises(ValueError):
                evaluator.validate_analysis(data)

    def test_unobserved_visual_must_not_be_scored(self):
        data = sample()
        data["dimensions"]["visual_design"]["score"] = 4
        with self.assertRaises(ValueError):
            evaluator.validate_analysis(data)

    def test_bad_timestamp_and_injected_fields_are_rejected(self):
        for timestamp in [-1, float("nan"), 999999, True]:
            data = sample()
            data["dimensions"]["visual_design"] = {
                "status": "observed", "score": 5, "note": "Stage",
                "evidence": [{"timestamp_seconds": timestamp, "observation": "Stage seen", "confidence": 0.8}],
            }
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                evaluator.validate_analysis(data)
        data = sample()
        data["dimensions"]["unexpected"] = data["dimensions"]["visual_design"]
        with self.assertRaises(ValueError):
            evaluator.validate_analysis(data)

    def test_cli_does_not_send_video_without_explicit_consent(self):
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "test.mp4"
            video.write_bytes(b"test")
            source = Path(d) / "analysis.json"
            source.write_text(json.dumps(sample()))
            out = Path(d) / "output.json"
            with patch.object(evaluator, "ask_gemini", side_effect=AssertionError("network called")):
                with self.assertRaises(SystemExit) as exc:
                    evaluator.main(["--world-id", WORLD_ID, "--video", str(video),
                                    "--source", "owner-recorded", "--analysis-json",
                                    str(source), "--out", str(out)])
            self.assertEqual(exc.exception.code, 2)
            self.assertFalse(out.exists())

    def test_cli_offline_json_writes_local_draft_only(self):
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "test.mp4"
            video.write_bytes(b"test")
            source = Path(d) / "analysis.json"
            source.write_text(json.dumps(sample()))
            out = Path(d) / "output.json"
            self.assertEqual(evaluator.main(["--world-id", WORLD_ID, "--video", str(video),
                "--source", "owner-recorded", "--analysis-json", str(source), "--out",
                str(out), "--confirm-sharing"]), 0)
            result = json.loads(out.read_text())
            self.assertFalse(result["rankingEligible"])
            self.assertNotIn("path", json.dumps(result).lower())


if __name__ == "__main__":
    unittest.main()
