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

    def test_strong_club_title_can_be_verified(self):
        raw = "<h1>Neon Club</h1><p>by:</p><p>Maker</p><p>DJ stage dancefloor techno club nightlife</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            item = worlds.detail_candidate(WORLD, "vrcmap_cafe",
                                          "https://vrcmap.com", 28)
        self.assertIsNotNone(item)
        self.assertEqual(item["authorHint"], "Maker")
        self.assertGreaterEqual(item["confidenceScore"], 75)
        self.assertIn("+explicit-club-name", item["reasons"])

    def test_fight_club_not_treated_as_nightlife(self):
        raw = "<h1>Fighting Club</h1><p>club DJ party music</p>"
        with patch.object(worlds, "fetch_text", return_value=raw):
            item = worlds.detail_candidate(WORLD, "vrcmap_music",
                                          "https://vrcmap.com", 28)
        self.assertIsNone(item)


if __name__ == "__main__":
    unittest.main()
