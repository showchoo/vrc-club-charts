"""Public page must label video-only scores and never claim verified equipment."""
import unittest
from scripts import build_static_pages as page
from scripts import build_vercel

WORLD = {
    "id": "wrld_7eaf3905-10f8-4528-9aa3-8b1a4ccc2d05",
    "name": "Synthetic unit test world", "genres": ["DJ"],
    "author": "Unit Test", "totals": {}, "weekly": {},
}
VIDEO = {
    "worldId": WORLD["id"], "visualScore": 84, "evidenceCoverage": 4,
    "evidenceType": "consented-video-ai-provisional",
    "independentInWorldInspection": False,
    "djPlaybackVerified": False, "equipmentFunctionalityVerified": False,
    "craftsmanshipScore": None,
}


class VideoRenderingTests(unittest.TestCase):
    def test_optional_video_visual_is_separate_and_provisional(self):
        html = page.world_page(WORLD, [], [], {}, VIDEO)
        self.assertIn("内部動画の暫定ビジュアル評価", html)
        self.assertIn("84/100", html)
        self.assertIn("DJ機器の動作・音質・最適化性能は未検証", html)
        self.assertIn("Craftsmanship Rankingの点数・順位には算入しません", html)
        self.assertIn("NOT SCORED", html)

    def test_sanitized_sighted_equipment_and_timestamp_without_function_claim(self):
        preview = {**VIDEO, "facilityObservations": [
            {"kind": "dj_booth", "timestampSeconds": 2.0,
             "confidence": .95, "equipmentFunctionalityVerified": False,
             "privateUser": "should never render"},
            {"kind": "<script>alert(1)</script>", "timestampSeconds": 2.0,
             "confidence": .99, "equipmentFunctionalityVerified": False},
            {"kind": "dj_decks", "timestampSeconds": 3.0,
             "confidence": .85, "equipmentFunctionalityVerified": True},
        ]}
        html = page.world_page(WORLD, [], [], {}, preview)
        self.assertIn("映像で見えた設備（AI推定）", html)
        self.assertIn("DJブース", html)
        self.assertIn("2.0s", html)
        self.assertIn("DJ配信・動画再生・操作・音響などの機能は確認していません", html)
        self.assertNotIn("privateUser", html)
        self.assertNotIn("should never render", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("DJ機材らしきもの", html)

    def test_no_video_does_not_display_provisional_score(self):
        html = page.world_page(WORLD, [], [])
        self.assertNotIn("内部動画の暫定ビジュアル評価", html)
        self.assertNotIn("84/100", html)

    def test_unsubstantiated_video_claims_are_not_displayed(self):
        for change in [
            {"independentInWorldInspection": True},
            {"djPlaybackVerified": True},
            {"craftsmanshipScore": 85},
            {"evidenceType": "thumbnail-only"},
            {"visualScore": True},
            {"visualScore": 999},
        ]:
            with self.subTest(change=change):
                html = page.world_page(WORLD, [], [], {}, {**VIDEO, **change})
                self.assertNotIn("内部動画の暫定ビジュアル評価", html)

    def test_site_includes_public_numeric_feed_only(self):
        self.assertIn("interior-visual-estimates.json", build_vercel.DATA_FILES)


if __name__ == "__main__":
    unittest.main()
