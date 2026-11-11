"""Offline validation of AI-generated in-world video reports; no network calls."""
from __future__ import annotations

import json
import os
import sys
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


def fake_google_sdk(client):
    """Make a google-genai stand-in: unit tests never install an SDK or send data."""
    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")
    errors = ModuleType("google.genai.errors")

    class ApiError(Exception):
        def __init__(self, code, raw):
            self.code = code
            super().__init__(raw)

    types.Part = lambda inline_data: {"inline_data": inline_data}
    types.Blob = lambda **kwargs: kwargs
    types.UploadFileConfig = lambda **kwargs: kwargs
    types.GenerateContentConfig = lambda **kwargs: kwargs
    errors.APIError = ApiError
    genai.Client = lambda api_key: client
    genai.types = types
    genai.errors = errors
    google.genai = genai
    return {
        "google": google, "google.genai": genai,
        "google.genai.types": types, "google.genai.errors": errors,
    }, ApiError


class VideoAssessmentTests(unittest.TestCase):
    def test_small_mp4_uses_inline_and_never_calls_file_upload(self):
        client = SimpleNamespace(files=Mock(), models=Mock())
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(sample()))
        modules, _ = fake_google_sdk(client)
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "short.mp4"
            video.write_bytes(b"synthetic not a real video")
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
                analysis = evaluator.ask_gemini(video, "gemini-3.5-flash-lite")
        self.assertEqual(analysis["summary"], sample()["summary"])
        client.files.upload.assert_not_called()
        client.files.delete.assert_not_called()
        args = client.models.generate_content.call_args.kwargs
        self.assertEqual(args["model"], "gemini-3.5-flash-lite")
        self.assertEqual(args["contents"][1]["inline_data"]["mime_type"], "video/mp4")
        self.assertEqual(args["contents"][1]["inline_data"]["data"], b"synthetic not a real video")
        self.assertEqual(args["config"]["response_mime_type"], "application/json")

    def test_large_mp4_uses_file_api_with_mime_and_deletes_remote_afterward(self):
        client = SimpleNamespace(files=Mock(), models=Mock())
        client.files.upload.return_value = SimpleNamespace(
            name="files/test", state=SimpleNamespace(name="ACTIVE"))
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(sample()))
        modules, _ = fake_google_sdk(client)
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "long.mp4"
            with video.open("wb") as f:
                f.truncate(evaluator.MAX_INLINE_VIDEO_BYTES + 1)
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
                with patch.object(Path, "read_bytes", side_effect=AssertionError("No huge inline read")):
                    result = evaluator.ask_gemini(video, "gemini-3.5-flash-lite")
        self.assertEqual(result["summary"], sample()["summary"])
        self.assertEqual(client.files.upload.call_args.kwargs["config"], {"mime_type": "video/mp4"})
        client.files.delete.assert_called_once_with(name="files/test")

    def test_400_from_api_is_redacted_not_printed_as_traceback(self):
        client = SimpleNamespace(files=Mock(), models=Mock())
        modules, ApiError = fake_google_sdk(client)
        client.models.generate_content.side_effect = ApiError(
            400, "sensitive raw provider error api-key-1234")
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "short.mp4"
            video.write_bytes(b"synthetic media")
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
                with self.assertRaisesRegex(RuntimeError, "model-request failed \\(HTTP 400\\)") as caught:
                    evaluator.ask_gemini(video, "gemini-3.5-flash-lite")
        self.assertNotIn("api-key-1234", str(caught.exception))
        client.files.upload.assert_not_called()

    def test_failure_in_file_upload_is_redacted_and_not_retried(self):
        client = SimpleNamespace(files=Mock(), models=Mock())
        modules, ApiError = fake_google_sdk(client)
        client.files.upload.side_effect = ApiError(400, "do not echo HTML response")
        with tempfile.TemporaryDirectory() as d:
            video = Path(d) / "long.mp4"
            with video.open("wb") as f:
                f.truncate(evaluator.MAX_INLINE_VIDEO_BYTES + 1)
            with patch.dict(sys.modules, modules), patch.dict(os.environ, {"GEMINI_API_KEY": "fake"}):
                with self.assertRaisesRegex(RuntimeError, "file-upload failed \\(HTTP 400\\)") as caught:
                    evaluator.ask_gemini(video, "gemini-3.5-flash-lite")
        self.assertNotIn("do not echo", str(caught.exception))
        self.assertEqual(client.files.upload.call_count, 1)
        client.models.generate_content.assert_not_called()

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
