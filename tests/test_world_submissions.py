"""Tests for conservative, source-grounded AI admission of submitted Worlds."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import review_world_submissions as review

ID = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
META = {
    "id": ID,
    "name": "Encode Night",
    "authorName": "DJ Maker",
    "releaseStatus": "public",
    "description": "Nightclub with DJ booth and dance floor for dance music events",
    "tags": ["club", "audiolink"],
}
GOOD = {"verdict": "club", "confidence": 0.96,
        "evidence": ["DJ booth", "dance floor"],
        "reasonJa": "DJ用会場の説明あり", "imageConsidered": False}


class SubmissionAITests(unittest.TestCase):
    def test_official_nonpublic_world_never_passes_verification(self):
        with patch.object(review, "get_json", return_value={
            **META, "releaseStatus": "private"
        }):
            with self.assertRaises(review.NonPublicWorldError):
                review.public_metadata(ID)

    def test_confirmed_private_world_has_specific_exclusion_exception(self):
        with patch.object(review, "get_json", return_value={
            **META, "releaseStatus": "private"
        }):
            with self.assertRaises(review.NonPublicWorldError) as error:
                review.public_metadata(ID)
            self.assertEqual(error.exception.release_status, "private")

    def test_missing_release_status_is_not_proof_of_privacy(self):
        metadata={**META}
        metadata.pop("releaseStatus")
        with patch.object(review,"get_json",return_value=metadata):
            with self.assertRaises(ValueError) as error:
                review.public_metadata(ID)
            self.assertNotIsInstance(error.exception,review.NonPublicWorldError)

    def test_user_submitted_private_world_is_excluded_not_held_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            worlds=Path(tmp)/"worlds.json"
            decisions=Path(tmp)/"decisions.json"
            worlds.write_text("[]",encoding="utf-8")
            decisions.write_text("[]",encoding="utf-8")
            with patch.object(review,"WORLDS",worlds),patch.object(
                review,"DECISIONS",decisions),patch.object(
                review,"queue_items",return_value=[{"world_id":ID}]),patch.object(
                review,"public_metadata",
                side_effect=review.NonPublicWorldError("private")),patch.object(
                review,"classify_world") as classify,patch.dict(
                review.os.environ,{"GEMINI_API_KEY":"fake-test-key"}):
                review.main()
            self.assertEqual(json.loads(worlds.read_text(encoding="utf-8")),[])
            self.assertEqual(json.loads(decisions.read_text(encoding="utf-8"))[0]["status"],
                             "excluded_nonpublic")
            classify.assert_not_called()

    def test_confident_club_with_independent_evidence_can_approve(self):
        self.assertTrue(review.may_auto_approve(GOOD, META))

    def test_ai_confidence_alone_never_auto_approves(self):
        self.assertFalse(review.may_auto_approve(GOOD, {
            **META, "name": "Some world", "description": "Just a lounge", "tags": []
        }))
        self.assertFalse(review.may_auto_approve(
            {**GOOD, "confidence": 0.89}, META))
        self.assertFalse(review.may_auto_approve(
            {**GOOD, "evidence": []}, META))
        self.assertFalse(review.may_auto_approve(
            {**GOOD, "verdict": "uncertain"}, META))

    def test_unrelated_club_name_is_insufficient(self):
        self.assertFalse(review.may_auto_approve(GOOD, {
            **META, "name": "Chess Club",
            "description": "Board games and puzzles in a relaxing lounge",
            "tags": ["games"],
        }))

    def test_official_high_confidence_approval_writes_no_visual_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            worlds = Path(tmp) / "worlds.json"
            decisions = Path(tmp) / "decisions.json"
            worlds.write_text("[]", encoding="utf-8")
            decisions.write_text("[]", encoding="utf-8")
            with patch.object(review,"WORLDS",worlds), patch.object(
                review,"DECISIONS",decisions), patch.object(
                review,"queue_items",return_value=[{"world_id": ID}]
            ), patch.object(review,"public_metadata",return_value=META), patch.object(
                review,"classify_world",return_value=GOOD
            ), patch.dict(review.os.environ,{"GEMINI_API_KEY":"mock-test-key"}):
                review.main()
                result=json.loads(worlds.read_text(encoding="utf-8"))
                pending=json.loads(decisions.read_text(encoding="utf-8"))
                self.assertEqual(len(result),1)
                self.assertEqual(result[0]["id"], ID)
                self.assertTrue(result[0]["chartEligible"])
                self.assertEqual(result[0]["editorialStatus"], "unreviewed")
                self.assertNotIn("scores", result[0])
                self.assertEqual(pending[0]["status"],"approved")

    def test_ambiguous_world_is_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            worlds = Path(tmp) / "worlds.json"
            decisions = Path(tmp) / "decisions.json"
            worlds.write_text("[]", encoding="utf-8")
            decisions.write_text("[]", encoding="utf-8")
            with patch.object(review,"WORLDS",worlds), patch.object(
                review,"DECISIONS",decisions), patch.object(
                review,"queue_items",return_value=[{"world_id":ID}]
            ), patch.object(review,"public_metadata",return_value=META), patch.object(
                review,"classify_world",return_value={**GOOD,"confidence":0.65}
            ), patch.dict(review.os.environ,{"GEMINI_API_KEY":"mock-test-key"}):
                review.main()
                self.assertEqual(json.loads(worlds.read_text(encoding="utf-8")),[])
                self.assertEqual(json.loads(decisions.read_text(encoding="utf-8"))[0]["status"],"needs_review")

    def test_structured_gemini_fenced_json_with_safe_output_limit(self):
        text = '```json\n' + json.dumps(GOOD) + '\n```'
        result = {"candidates": [{"finishReason": "STOP",
                 "content": {"parts": [{"text": text}]}}]}
        raw = json.dumps(result).encode("utf-8")
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, *args): return raw
        requests=[]
        def fake_open(req, **kwargs):
            requests.append(json.loads(req.data))
            return FakeResponse()
        with patch.object(review, "image_part", return_value=None), patch.object(
            review.urllib.request, "urlopen", side_effect=fake_open
        ):
            assessment=review.classify_world(META,"dummy-key")
        self.assertEqual(assessment["verdict"], "club")
        self.assertEqual(requests[0]["generationConfig"]["maxOutputTokens"], 1024)

    def test_incomplete_gemini_output_is_never_accepted(self):
        raw=json.dumps({"candidates":[{
            "finishReason":"MAX_TOKENS",
            "content":{"parts":[{"text":'{"verdict":"club"'}]}
        }]}).encode("utf-8")
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self,*args): return None
            def read(self,*args): return raw
        with patch.object(review,"image_part",return_value=None),patch.object(
            review.urllib.request,"urlopen",return_value=FakeResponse()
        ):
            with self.assertRaisesRegex(ValueError,"incomplete"):
                review.classify_world(META,"dummy-key")

    def test_empty_api_key_does_not_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            worlds=Path(tmp)/"worlds.json"
            decisions=Path(tmp)/"decisions.json"
            worlds.write_text("[]",encoding="utf-8")
            decisions.write_text("[]",encoding="utf-8")
            with patch.object(review,"WORLDS",worlds), patch.object(
                review,"DECISIONS",decisions), patch.object(
                review,"queue_items",return_value=[{"world_id":ID}]
            ), patch.dict(review.os.environ,{"GEMINI_API_KEY":""}):
                review.main()
                self.assertEqual(worlds.read_text(encoding="utf-8"),"[]")


if __name__=="__main__":
    unittest.main()
