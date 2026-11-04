"""Offline regression coverage for Gemini grounded DJ-live research."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts import dj_stream_research as research

W1 = "wrld_2095ba41-f0b8-4ed3-a00d-3f0e9a4e2a79"
W2 = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"
NOW = dt.datetime(2026, 11, 5, tzinfo=dt.timezone.utc)


def world(wid=W1, name="VRChat DJ room"):
    return {"id": wid, "name": name, "author": "Maker",
            "genres": ["CLUB", "MUSIC"], "chartEligible": True}


def gemini(verdict="evidence_found", indices=None, support=None, official=False):
    if indices is None:
        indices = [0]
    if support is None:
        support = [0]
    response = {
        "verdict": verdict,
        "summaryJa": "制作者の公開資料にライブ配信URLの入力手順がある。",
        "sourceIndices": indices,
        "officialDescriptionExplicitlySupportsLiveInput": official,
    }
    return {
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": json.dumps(response, ensure_ascii=False)}]},
            "groundingMetadata": {
                "webSearchQueries": ["exact world DJ live playback"],
                "groundingChunks": [
                    {"web": {"uri": "https://maker.example/live-dj", "title": "Maker guide"}},
                    {"web": {"uri": "https://other.example/article", "title": "Music party"}},
                ],
                "groundingSupports": [
                    {"segment": {"text": "Guide"}, "groundingChunkIndices": support}],
            }
        }]
    }


class GeminiGroundedEvidenceTests(unittest.TestCase):
    def test_grounded_source_is_reported_as_clue_not_published(self):
        r = research.parse_grounded_reply(gemini(), W1, None)
        self.assertEqual(r["status"], "evidence_found")
        self.assertTrue(r["requiresHumanVerification"])
        self.assertEqual(r["sources"][0]["url"], "https://maker.example/live-dj")
        self.assertEqual(r["groundingQueries"], ["exact world DJ live playback"])

    def test_api_grounding_supports_can_supply_sources_without_model_indices(self):
        result = research.parse_grounded_reply(
            gemini(indices=[], support=[0]), W1, None)
        self.assertEqual(result["status"], "evidence_found")
        self.assertEqual(result["sources"][0]["url"], "https://maker.example/live-dj")

    def test_source_not_supported_by_grounding_is_not_evidence(self):
        r = research.parse_grounded_reply(gemini(support=[1]), W1, None)
        self.assertEqual(r["status"], "needs_review")
        self.assertEqual(r["sources"], [])

    def test_model_cannot_invent_a_grounding_index(self):
        r = research.parse_grounded_reply(gemini(indices=[6]), W1, None)
        self.assertEqual(r["status"], "needs_review")
        self.assertFalse(r["sources"])

    def test_no_search_grounding_never_counts_as_a_web_source(self):
        raw = gemini()
        raw["candidates"][0]["groundingMetadata"] = {}
        self.assertEqual(research.parse_grounded_reply(raw, W1, None)["status"],
                         "needs_review")

    def test_negative_requires_explicit_cited_claim(self):
        with_support = research.parse_grounded_reply(
            gemini(verdict="negative_evidence"), W1, None)
        self.assertEqual(with_support["status"], "negative_evidence")
        no_support = research.parse_grounded_reply(
            gemini(verdict="negative_evidence", support=[]), W1, None)
        self.assertEqual(no_support["status"], "needs_review")

    def test_explicit_official_description_requires_matching_id(self):
        meta = {"id": W1, "description": "DJ live stream URL input supported"}
        grounded = gemini(indices=[], support=[], official=True)
        accepted = research.parse_grounded_reply(grounded, W1, meta)
        self.assertEqual(accepted["status"], "evidence_found")
        self.assertEqual(accepted["sources"][0]["url"],
                         "https://vrchat.com/home/world/" + W1 + "/info")
        self.assertEqual(research.parse_grounded_reply(
            grounded, W2, meta)["status"], "needs_review")
        self.assertFalse(research.explicit_live_text(
            "A nice DJ booth with AudioLink and YouTube player."))

    def test_model_fenced_json_and_invalid_reply_handling(self):
        data = gemini()
        obj = data["candidates"][0]["content"]["parts"][0]["text"]
        data["candidates"][0]["content"]["parts"][0]["text"] = "```json\n" + obj + "\n```"
        self.assertEqual(research.parse_grounded_reply(data, W1, None)["status"],
                         "evidence_found")
        data["candidates"][0]["finishReason"] = "MAX_TOKENS"
        with self.assertRaises(ValueError):
            research.parse_grounded_reply(data, W1, None)

    def test_non_https_and_credentials_never_count_as_sources(self):
        for bad in ["http://example.org", "https://user:password@example.org/path",
                    "javascript:alert(1)", "https://a.example/path space"]:
            self.assertFalse(research.valid_https(bad))
        result = gemini()
        result["candidates"][0]["groundingMetadata"]["groundingChunks"][0]["web"]["uri"] = (
            "http://not-secure.example/")
        self.assertEqual(research.parse_grounded_reply(result, W1, None)["status"],
                         "needs_review")


class ResearchQueueTests(unittest.TestCase):
    def test_starts_with_unverified_dj_worlds_and_skips_verified(self):
        catalog = [world(W1), world(W2, "Simple space")]
        selected = research.select_worlds(catalog, {}, {W1: {}}, NOW, 4)
        self.assertEqual([x["id"] for x in selected], [W2])

    def test_dj_tagged_world_is_already_listable_so_skip_paid_search(self):
        tagged={**world(W1), "genres":["CLUB","DJ"]}
        untagged=world(W2, "Untagged club")
        selected=research.select_worlds([tagged,untagged], {}, {}, NOW, 4)
        self.assertEqual([w["id"] for w in selected],[W2])

    def test_no_repeat_within_cooldown(self):
        prior = {"id": W1, "checkedAt": NOW.isoformat(), "status": "needs_review"}
        self.assertFalse(research.due(prior, NOW + dt.timedelta(days=44)))
        self.assertTrue(research.due(prior, NOW + dt.timedelta(days=46)))
        failed = {**prior, "status": "research_unavailable"}
        self.assertFalse(research.due(failed, NOW + dt.timedelta(days=2)))
        self.assertTrue(research.due(failed, NOW + dt.timedelta(days=4)))

    def test_missing_key_makes_no_requests_or_new_records(self):
        with patch.object(research, "ask_gemini") as request:
            records, notice = research.research([world()], [], {}, "", 4, NOW)
        self.assertEqual(records, [])
        self.assertEqual(notice, [])
        request.assert_not_called()

    def test_research_records_evidence_without_touching_public_registry(self):
        clue = {"status": "evidence_found", "summaryJa": "説明あり",
                "sources": [{"url": "https://maker.example/guide", "title": "Guide"}],
                "requiresHumanVerification": True}
        with patch.object(research, "public_metadata", return_value={
            "id": W1, "name": "DJ room", "releaseStatus": "public",
        }), patch.object(research, "ask_gemini", return_value=clue) as ai:
            rows, notification = research.research([world()], [], {}, "test-key", 4, NOW)
        ai.assert_called_once()
        self.assertEqual(rows[0]["status"], "evidence_found")
        self.assertEqual(rows[0]["metadataStatus"], "official_public")
        self.assertEqual(len(notification), 1)
        self.assertIn("掲載承認ではありません", research.notice_markdown(notification))
        self.assertIn("World ID: `" + W1 + "`", research.notice_markdown(notification))

    def test_official_nonpublic_skips_gemini(self):
        with patch.object(research, "public_metadata",
                          side_effect=research.NonPublicWorldError("private")), patch.object(
                          research, "ask_gemini") as ai:
            rows, notification = research.research([world()], [], {}, "test-key", 4, NOW)
        self.assertEqual(rows[0]["status"], "non_public")
        self.assertEqual(notification, [])
        ai.assert_not_called()

    def test_official_http_401_still_performs_grounded_search(self):
        with patch.object(research, "public_metadata", side_effect=urllib.error.HTTPError(
            "https://api.vrchat.cloud/", 401, "Unauthorized", {}, None
        )), patch.object(research, "ask_gemini", return_value={
            "status": "needs_review", "summaryJa": "未確認", "sources": [],
            "requiresHumanVerification": True,
        }) as ai:
            rows, _ = research.research([world()], [], {}, "test-key", 4, NOW)
        self.assertEqual(rows[0]["metadataStatus"], "unavailable")
        self.assertEqual(rows[0]["status"], "needs_review")
        self.assertIsNone(ai.call_args.args[1])

    def test_gemini_failure_stays_pending_not_false_non_support(self):
        with patch.object(research, "public_metadata", return_value={"id": W1}), patch.object(
            research, "ask_gemini", side_effect=ValueError("malformed model output")
        ):
            rows, found = research.research([world()], [], {}, "test-key", 4, NOW)
        self.assertEqual(rows[0]["status"], "research_unavailable")
        self.assertEqual(found, [])
        self.assertEqual(rows[0]["errorType"], "ValueError")

    def test_reviewed_evidence_not_notified_again_without_changes(self):
        clue = {"status": "evidence_found", "summaryJa": "確認候補",
                "sources": [{"url": "https://maker.example/live", "title": "Guide"}]}
        older = {"id": W1, "name": "VRChat DJ room", "author": "Maker",
                 "status": "evidence_found", "sources": clue["sources"],
                 "checkedAt": (NOW - dt.timedelta(days=50)).isoformat()}
        with patch.object(research, "public_metadata", return_value={"id": W1}), patch.object(
                research, "ask_gemini", return_value=clue):
            rows, found = research.research([world()], [older], {}, "test-key", 4, NOW)
        self.assertEqual(rows[0]["status"], "evidence_found")
        self.assertEqual(found, [])

    def test_invalid_catalog_records_not_queued(self):
        selected = research.select_worlds(
            [{"id": "../hack", "name": "Club"}, {"id": W1, "name": ""}], {}, {}, NOW, 5)
        self.assertEqual(selected, [])


if __name__ == "__main__":
    unittest.main()
