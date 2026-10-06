"""Offline AI SCOUT regression tests; no external APIs or billing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_ai_scout as scout

W1 = "wrld_95883f50-4838-4cea-9e80-3347c5caaf5e"
W2 = "wrld_aa51adba-1554-4d53-b9a5-fa1501ed32d2"


class AiScoutTests(unittest.TestCase):

    def test_candidate_pool_keeps_approved_and_labels_unapproved(self):
        worlds = [
            {"id": W1, "name": "Immersive Club", "author": "Maker",
             "chartEligible": True, "genres": ["IMMERSIVE", "LTCGI"]},
            {"id": W2, "name": "Not a club", "author": "Maker",
             "chartEligible": False, "genres": ["IMMERSIVE"]},
        ]
        new_world = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        discoveries = [{"id": new_world, "name": "Deep DJ", "authorHint": "Artist",
                        "confidenceScore": 100}]
        result = scout.candidate_pool(worlds, discoveries)
        self.assertEqual({item["id"] for item in result}, {W1, new_world})
        first = next(item for item in result if item["id"] == W1)
        self.assertIn("IMMERSIVE", first["signals"])
        self.assertNotIn("visualPotential", first)
        discovered = next(item for item in result if item["id"] == new_world)
        self.assertEqual(discovered["sourceType"], "discovery")
        self.assertIn("vrcmap.com/world/", discovered["url"])

    def test_invalid_ai_ratings_never_publish(self):
        data = {"id": W1, "visualPotential": 85,
                "factors": {"visual": 5, "lighting": 4, "spatial": 3, "originality": 4}}
        self.assertTrue(scout.valid_result(data))
        self.assertFalse(scout.valid_result({**data, "visualPotential": True}))
        self.assertFalse(scout.valid_result({**data, "visualPotential": 101}))
        self.assertFalse(scout.valid_result({**data, "factors": {**data["factors"], "lighting": 10}}))

    def test_without_api_key_no_fabricated_scores(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            (data_dir / "worlds.json").write_text(json.dumps([
                {"id": W1, "name": "Club Immersive", "author": "Maker",
                 "chartEligible": True, "genres": ["IMMERSIVE"]}
            ]))
            (data_dir / "world-candidates.json").write_text("[]")
            with patch.object(scout, "DATA", data_dir), patch.object(
                scout, "OUTPUT", data_dir / "ai-scout.json"
            ):
                result = scout.build_catalog("")
            self.assertFalse(result["modelConfigured"])
            self.assertEqual(result["summary"]["totalCandidates"], 1)
            self.assertEqual(result["scored"], [])
            self.assertEqual(result["candidates"][0]["id"], W1)
            self.assertNotIn("visualPotential", result["candidates"][0])

    def test_model_response_requires_visual_evidence(self):
        good = {"canJudge": True, "visual": 4, "lighting": 4,
                "spatial": 3, "originality": 5,
                "reasonJa": "照明と構図に工夫が見られます。",
                "cautionsJa": "World内での実際の見え方は未確認です。"}
        with patch.object(scout, "post_json", return_value={
            "candidates": [{"content": {"parts": [{"text": json.dumps(good)}]}}]
        }):
            result = scout.evaluate_image("Club", "Creator", "image/png", b"imagedata", "fake-key")
        self.assertEqual(result["visualPotential"], 80)
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["method"], "single-thumbnail-ai-image-assessment")

    def test_gemini_request_includes_image_and_json_mode(self):
        good = {"canJudge": True, "visual": 5, "lighting": 3,
                "spatial": 4, "originality": 4,
                "reasonJa": "空間に工夫があります。",
                "cautionsJa": "音響は判定できません。"}
        called = {}

        def fake_post(url, payload, headers, timeout):
            called.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(good)}]}}]}

        with patch.object(scout, "post_json", side_effect=fake_post):
            score = scout.evaluate_image("Club", "Creator", "image/png", b"imagebytes", "test-key")
        self.assertEqual(score["visualPotential"], 80)
        self.assertIn("generativelanguage.googleapis.com", called["url"])
        self.assertTrue(called["url"].endswith(":generateContent"))
        self.assertEqual(called["headers"], {"x-goog-api-key": "test-key"})
        self.assertEqual(called["payload"]["generationConfig"]["responseMimeType"], "application/json")
        image = called["payload"]["contents"][0]["parts"][1]["inlineData"]
        self.assertEqual(image["mimeType"], "image/png")
        self.assertEqual(image["data"], __import__("base64").b64encode(b"imagebytes").decode("ascii"))

    def test_gemini_empty_response_fails_safely(self):
        with patch.object(scout, "post_json", return_value={"candidates": []}):
            with self.assertRaises(ValueError):
                scout.evaluate_image("Club", "Creator", "image/png", b"imagebytes", "test-key")

    def test_old_http_404_attempts_are_retried_after_model_switch(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            (data_dir / "worlds.json").write_text(json.dumps([
                {"id": W1, "name": "Club Immersive", "author": "Maker",
                 "chartEligible": True, "genres": ["IMMERSIVE"]}
            ]))
            (data_dir / "world-candidates.json").write_text("[]")
            (data_dir / "ai-scout.json").write_text(json.dumps({
                "scored": [], "attempts": {W1: {
                    "checkedAt": scout.utc_now().isoformat(),
                    "status": "http-unavailable"
                }}
            }))
            with patch.object(scout, "DATA", data_dir), patch.object(
                scout, "OUTPUT", data_dir / "ai-scout.json"
            ), patch.object(scout, "fetch_world_visuals", return_value={} ) as fetch:
                result = scout.build_catalog("test-key")
            fetch.assert_called_once_with([W1])
            self.assertEqual(result["summary"]["assessed"], 0)

    def test_gemini_model_http_404_fails_job_visibly(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            (data_dir / "worlds.json").write_text(json.dumps([
                {"id": W1, "name": "Club Immersive", "author": "Maker",
                 "chartEligible": True, "genres": ["IMMERSIVE"]}
            ]))
            (data_dir / "world-candidates.json").write_text("[]")
            with patch.object(scout, "DATA", data_dir), patch.object(
                scout, "OUTPUT", data_dir / "ai-scout.json"
            ), patch.object(scout, "fetch_world_visuals", return_value={W1: {}}), patch.object(
                scout, "fetch_image", return_value=("image/png", b"imagebytes")
            ), patch.object(scout, "evaluate_image", side_effect=HTTPError(
                "https://generativelanguage.googleapis.com", 404, "Not Found", {}, None
            )):
                with self.assertRaisesRegex(RuntimeError, "Gemini API rejected model"):
                    scout.build_catalog("test-key")

    def test_image_that_is_not_a_world_gets_no_score(self):
        with patch.object(scout, "post_json", return_value={
            "candidates": [{"content": {"parts": [{"text": json.dumps({"canJudge": False})}]}}]
        }):
            result = scout.evaluate_image("Club", "Creator", "image/png", b"imagedata", "fake-key")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
