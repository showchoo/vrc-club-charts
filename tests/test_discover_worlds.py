"""No-network tests for broader VRCmap discovery and nightlife filtering."""
import unittest
from unittest.mock import patch

from scripts import discover_worlds as worlds

WORLD = "wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


class VrcmapRotationTests(unittest.TestCase):
    def test_multiple_categories_are_eligible_for_discovery(self):
        sources = {name for name, _, _ in worlds.LISTING_SOURCES}
        self.assertTrue({"vrcmap_music", "vrcmap_new", "vrcmap_cafe",
                         "vrcmap_japan", "vrcmap_trending", "vrcmap_chill"} <= sources)

    def test_related_links_only_follow_similar_section(self):
        source = (
            '<a href="/world/wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa">More by author</a>'
            '<h2>Similar Worlds</h2>'
            '<a href="/world/wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb">Club Two</a>'
            '<a href="/world/wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb">Duplicate</a>'
            '<a href="/world/wrld_cccccccc-cccc-cccc-cccc-cccccccccccc">Night Club</a>'
        )
        self.assertEqual(worlds.related_world_ids(source), [
            "wrld_bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "wrld_cccccccc-cccc-cccc-cccc-cccccccccccc",
        ])

    def test_related_links_require_similar_worlds_heading(self):
        self.assertEqual(worlds.related_world_ids(
            '<a href="/world/wrld_aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa">More author</a>'
        ), [])

    def test_strong_club_title_can_be_verified(self):
        raw = "<h1>Neon Club</h1><p>by:</p><p>Maker</p><p>DJ stage dancefloor techno club nightlife</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            item = worlds.detail_candidate(WORLD, "vrcmap_cafe",
                                          "https://vrcmap.com", 28)
        self.assertIsNotNone(item)
        self.assertEqual(item["authorHint"], "Maker")
        self.assertGreaterEqual(item["confidenceScore"], 75)
        self.assertIn("+explicit-club-name", item["reasons"])

    def test_diagnostic_counters_do_not_relax_admission(self):
        stats = {}
        raw = "<h1>Art Gallery</h1><p>Paintings and sculpture</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            self.assertIsNone(worlds.detail_candidate(
                WORLD, "vrcmap_music", "https://vrcmap.com", 28, stats
            ))
        self.assertEqual(stats, {"no_nightlife_signal": 1})

        raw = "<h1>Fighting Club</h1><p>DJ dancefloor club</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            self.assertIsNone(worlds.detail_candidate(
                WORLD, "vrcmap_music", "https://vrcmap.com", 28, stats
            ))
        self.assertEqual(stats.get("excluded_title"), 1)
        self.assertNotIn("qualified", stats)

    def test_fight_club_not_treated_as_nightlife(self):
        raw = "<h1>Fighting Club</h1><p>club DJ party music</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            item = worlds.detail_candidate(WORLD, "vrcmap_music",
                                          "https://vrcmap.com", 28)
        self.assertIsNone(item)


if __name__ == "__main__":
    unittest.main()
