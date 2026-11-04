"""DJ tag admission and independent live stream evidence regression tests."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import dj_stream_policy as policy

ROOT = Path(__file__).resolve().parents[1]
W1 = "wrld_2095ba41-f0b8-4ed3-a00d-3f0e9a4e2a79"
W2 = "wrld_b2d9f284-3a77-4a8a-a58e-f8427f87ba79"


def evidence(wid=W1, status="verified"):
    return {
        "worldId": wid, "status": status,
        "method": "live-playback-tested", "verifiedAt": "2026-10-20",
        "verifiedBy": "Test visitor", "platform": "PC",
        "evidenceUrl": "https://example.org/notes/dj-live-playback-test",
    }


class DJStreamPolicyTests(unittest.TestCase):
    def load(self, entries):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "dj-stream-verifications.json"
            path.write_text(json.dumps({"worlds": entries}), encoding="utf-8")
            return policy.load_verified(path)

    def test_live_verified_worlds_require_independent_proof(self):
        self.assertEqual(list(self.load([evidence()])), [W1])
        for altered in [
            {"status": "needs-review"}, {"status": "unsupported"},
        ]:
            self.assertEqual(self.load([{**evidence(), **altered}]), {})
        for invalid in [
            {"method": "photo-only"},
            {"verifiedAt": "2100-01-01"},
            {"verifiedBy": ""},
            {"platform": "Quest"},
            {"evidenceUrl": "http://example.org/proof"},
            {"evidenceUrl": "https://user:secret@example.org/proof"},
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.load([{**evidence(), **invalid}])

    def test_doubled_world_id_rejected(self):
        with self.assertRaises(ValueError):
            self.load([evidence(), evidence()])

    def test_exact_dj_tag_auto_lists_without_claiming_live_playback(self):
        confirmed = self.load([evidence(W1)])
        catalog = [
            {"id": W1, "name": "Live tested", "genres": ["CLUB"], "chartEligible": True},
            {"id": W2, "name": "DJ tagged", "genres": ["CLUB", "DJ"],
             "chartEligible": True},
        ]
        visible = policy.published_worlds(catalog, confirmed)
        self.assertEqual([row["id"] for row in visible], [W1, W2])
        self.assertEqual(visible[0]["publicationBasis"], "live-playback-verified")
        self.assertTrue(visible[0]["djStreamTested"])
        self.assertEqual(visible[1]["publicationBasis"], "dj-tag")
        self.assertIsNone(visible[1]["djStreamVerification"])
        self.assertFalse(visible[1]["djStreamTested"])
        self.assertEqual([row["id"] for row in policy.published_worlds(catalog, {})], [W2])
        self.assertEqual(
            policy.published_worlds([{**catalog[1], "releaseStatus": "private"}], {}), [])

    def test_dj_tag_is_exact_not_a_name_description_or_ai_guess(self):
        self.assertTrue(policy.is_dj_tag("DJ"))
        self.assertTrue(policy.is_dj_tag("author_tag_DJ"))
        for tag in ("DJVU", "DJs", "dj booth", "AUDIO LINK", "author_tag_djbooth"):
            self.assertFalse(policy.is_dj_tag(tag))
        catalog = [
            {"id": W1, "name": "DJ Events", "genres": ["MUSIC"], "description": "DJ"},
            {"id": W2, "name": "Music", "genres": ["DJs", "AUDIOLINK"]},
        ]
        self.assertEqual(policy.published_worlds(catalog, {}), [])
        tagged = {"id": W1, "name": "Official", "genres": ["CLUB"],
                  "officialTags": ["author_tag_DJ"]}
        self.assertEqual(len(policy.published_worlds([tagged], {})), 1)
        self.assertEqual(policy.published_worlds(
            [{**tagged, "availabilityStatus": "unavailable"}], {}), [])

    def test_publication_basis_does_not_fabricate_verification_on_second_pass(self):
        source = [{"id": W2, "genres": ["DJ"], "name": "Stage"}]
        first = policy.published_worlds(source, {})
        second = policy.published_worlds(first, {})
        self.assertEqual(first, second)
        self.assertFalse(second[0]["djStreamTested"])

    def test_stale_scout_scores_and_discovery_candidates_do_not_leak(self):
        confirmed = self.load([evidence(W1)])
        source = {
            "scored": [
                {"id": W1, "sourceType": "catalog", "visualPotential": 77},
                {"id": W2, "sourceType": "catalog", "visualPotential": 95}],
            "candidates": [
                {"id": W2, "sourceType": "discovery"},
                {"id": W1, "sourceType": "catalog"}],
            "attempts": {W1: {"status": "assessed"}, W2: {"status": "assessed"}},
            "summary": {"totalCandidates": 99, "assessed": 2},
        }
        result = policy.sanitize_ai_scout(source, confirmed)
        self.assertEqual([x["id"] for x in result["scored"]], [W1])
        self.assertEqual(result["candidates"], [])
        self.assertEqual(list(result["attempts"]), [W1])
        self.assertEqual(result["summary"]["totalCandidates"], 1)
        blank = policy.sanitize_ai_scout(source, {})
        self.assertEqual(blank["scored"], [])
        self.assertEqual(blank["candidates"], [])

    def test_public_world_feeds_are_not_stale_after_policy_change(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        headers = next(row["headers"] for row in config["headers"]
                       if row["source"].startswith("/data/"))
        cc = next(row["value"] for row in headers
                  if row["key"] == "Cache-Control")
        self.assertIn("no-store", cc)
        for path in ("app.js", "ai-scout.js", "community-reviews.js"):
            code = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("weekly-ranking.json?v=dj-live-verified-01", code)
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("app.js?v=20261105-dj-live-verified-01", home)

    def test_current_site_has_no_unverified_public_world_pages(self):
        """A clean static build does not leak old catalog Worlds by direct URLs."""
        verified = policy.load_verified()
        ranking = json.loads((ROOT / "data/weekly-ranking.json").read_text(encoding="utf-8"))
        expected = {w["id"] for w in policy.published_worlds(ranking["worlds"], verified)}
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [sys.executable, "scripts/build_static_pages.py", temp],
                cwd=ROOT, check=True, text=True,
                capture_output=True,
            )
            out = Path(temp)
            published = {p.stem for p in (out / "worlds").glob("wrld_*.html")}
            self.assertEqual(published, expected)
            self.assertEqual(
                {p.stem for p in out.glob("wrld_*.html")}, expected)
            feed = json.loads((out / "data/weekly-ranking.json").read_text(encoding="utf-8"))
            self.assertEqual({x["id"] for x in feed["worlds"]}, expected)
            self.assertEqual(feed["publicationPolicy"], "dj-tag-or-verified-live-stream")
            scout = json.loads((out / "data/ai-scout.json").read_text(encoding="utf-8"))
            self.assertEqual(
                {x["id"] for x in scout["scored"] + scout["candidates"]} - expected, set())
            self.assertIn("Generated ", result.stdout)


if __name__ == "__main__":
    unittest.main()
