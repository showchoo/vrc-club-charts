"""No-network tests for the optional, robots-aware Sia VR discovery source."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import discover_sia_vr as source


WORLD = "wrld_12345678-1234-1234-1234-123456789abc"


class SiaVRDiscoveryTests(unittest.TestCase):
    def test_listing_only_accepts_local_article_links(self):
        html = (
            '<a href="/vrchat-world-1234">Club</a>'
            '<a href="https://sia-vr.com/vrchat-world-1234">Duplicate</a>'
            '<a href="https://evil.example/vrchat-world-5678">External</a>'
            '<a href="/category/building/club">Category</a>'
        )
        self.assertEqual(source.article_urls(html), ["https://sia-vr.com/vrchat-world-1234"])

    def test_article_requires_official_world_link(self):
        html = (
            '<h1>Neon Club</h1>'
            '<a href="https://not-vrchat.com/home/world/' + WORLD + '">Wrong domain</a>'
            '<a href="https://vrchat.com/home/world/' + WORLD + '/info">Official</a>'
        )
        self.assertEqual(source.extract_world_article(html), (WORLD, "Neon Club"))
        self.assertIsNone(source.extract_world_article(
            '<h1>Neon Club</h1><a href="https://other.test/home/world/' + WORLD + '">No</a>'
        ))

    def test_denied_robots_policy_blocks_every_fetch(self):
        class Denied:
            def can_fetch(self, agent, url):
                return False
        with patch.object(source, "robots_policy", return_value=Denied()), patch.object(
                source, "fetch_text") as fetch:
            items, report = source.collect_candidates("2026-10-23")
        self.assertEqual(items, [])
        self.assertEqual(report["status"], "robots_disallowed")
        fetch.assert_not_called()

    def test_public_listing_yields_leads_without_publishing(self):
        class Allowed:
            def can_fetch(self, agent, url):
                return True

        def fake_fetch(url):
            if "/category/" in url:
                return '<a href="/vrchat-world-1234">Club</a>'
            return '<h1>Neon Club</h1><a href="https://vrchat.com/home/world/' + WORLD + '/info">VRChat World</a>'

        with tempfile.TemporaryDirectory() as directory, patch.object(
                source, "STATE", Path(directory) / "state.json"), patch.object(
                source, "robots_policy", return_value=Allowed()), patch.object(
                source, "fetch_text", side_effect=fake_fetch):
            leads, report = source.collect_candidates("2026-10-23")
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["leads"], 1)
        self.assertEqual(leads[0]["id"], WORLD)
        self.assertEqual(leads[0]["sourceCategories"], ["sia_vr_club"])
        self.assertNotIn("releaseStatus", leads[0])
        self.assertNotIn("chartEligible", leads[0])


if __name__ == "__main__":
    unittest.main()
